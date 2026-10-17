#!/usr/bin/env python3
"""Normalize source-authored references, fixtures and response proposals into separate record types."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import platform

import yaml
from collect import HERE, sha, verify_source


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str)


def content_hash(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def policybench_entries(text):
    rows = []
    for part in re.split(r'^## ', text, flags=re.M)[1:]:
        lines = part.strip().splitlines()
        fields = {'id': lines[0].strip()}
        body = []
        for line in lines[1:]:
            match = re.match(r'^- (category|subcategory|fixtures|tags):\s*(.*)', line)
            if match:
                fields[match[1]] = match[2]
            elif line.strip() and line.strip() != '---':
                body.append(line.strip())
        fields['text'] = '\n'.join(body)
        rows.append(fields)
    return rows


def assertions_for(case):
    # Keep upstream assertions, including explicit false/zero values, verbatim.
    return case.get('assertions', [])


def technique_ids(value):
    return sorted(set(re.findall(r'\bT\d{4}(?:\.\d{3})?\b', encode(value), flags=re.I)))


def selected_sigma(doc):
    source = doc.get('logsource', {})
    return (source.get('product', '').lower() in
            {'linux', 'kubernetes', 'aws', 'azure', 'gcp', 'gcloud', 'docker', 'github'}
            or source.get('category', '').lower() in {'container', 'kubernetes', 'docker'})


class Builder:
    def __init__(self, paths):
        self.lock = json.loads((HERE/'sources.lock.json').read_text())
        self.sources = {s['name']: s for s in self.lock['sources']}
        self.paths = paths
        self.records = []
        self.inventory = {}
        self.errors = []

    def file(self, source, path):
        root = self.paths[source].resolve()
        if not path.resolve().is_relative_to(root):
            raise ValueError('Source symlink escapes checkout')
        try:
            relative = str(path.absolute().relative_to(self.paths[source].absolute()))
        except ValueError:
            relative = str(path.resolve().relative_to(root))
        key = source+':'+relative
        if key not in self.inventory:
            self.inventory[key] = {'source': source, 'path': relative, 'bytes': path.stat().st_size,
                                   'sha256': sha(path), 'parse_status': 'source_read'}
        return relative

    def data(self, source, path):
        relative = self.file(source, path)
        try:
            if path.suffix == '.json':
                result = [json.loads(path.read_text())]
            else:
                result = list(yaml.load_all(path.read_text(), Loader=getattr(yaml, 'CSafeLoader', yaml.SafeLoader)))
            # Normalize YAML timestamps and map keys into deterministic JSON representation.
            result = json.loads(json.dumps(result, default=str))
            self.inventory[source+':'+relative]['parse_status'] = 'parsed'
            return result
        except (ValueError, yaml.YAMLError, UnicodeError) as error:
            self.inventory[source+':'+relative]['parse_status'] = 'error'
            self.errors.append({'source': source, 'path': relative, 'error': str(error)[:1000]})
            return []

    def linked(self, source, origin, name):
        path = (origin.parent/name).resolve()
        if not path.is_relative_to(self.paths[source].resolve()) or not path.is_file():
            raise ValueError('Missing/escaping fixture dependency: '+source+':'+str(name))
        return path

    def add(self, source, path, key, record_type, inputs, target=None, name=None, family=None, role='reference', **extra):
        relative = self.file(source, path)
        source_info = self.sources[source]
        prefix = 'kyverno' if source in {'kyverno-policies', 'kyverno-legacy'} else source
        family = family or name or str(path.parent.relative_to(self.paths[source]))
        row = {'id': source+':'+relative+':'+str(key), 'record_type': record_type,
               'family_id': prefix+':'+str(family), 'role': role,
               'inputs': inputs, 'target': target, 'target_origin': 'upstream_authored' if target is not None else None,
               'execution_status': 'not_executed', 'independent_response_label': False,
               'training_split': 'unassigned', 'model_input_review_required': True,
               'name': name, 'source': {'name': source, 'revision': source_info['revision'], 'path': relative,
               'url': source_info['url'].removesuffix('.git')+'/blob/'+source_info['revision']+'/'+relative,
               'sha256': self.inventory[source+':'+relative]['sha256'], 'license': source_info['license_id']},
               'content_sha256': content_hash({'record_type': record_type, 'inputs': inputs, 'target': target}), **extra}
        self.records.append(row)
        return row

    def manifests(self, source, root, include_fixture_resources=False):
        for path in sorted(root.rglob('*.yaml')):
            if any(p in {'.git', 'vendor', 'node_modules'} for p in path.parts):
                continue
            for index, doc in enumerate(self.data(source, path)):
                if not isinstance(doc, dict):
                    continue
                kind = doc.get('kind', '')
                api = doc.get('apiVersion', '')
                meta = doc.get('metadata', {})
                relative = path.relative_to(self.paths[source])
                fixture = any(p.startswith('.') or p in {'test', 'tests', 'testdata', 'samples', 'artifacthub'} for p in relative.parts)
                role = 'historical' if 'artifacthub' in relative.parts else ('fixture' if fixture else 'reference')
                if api.startswith(('kyverno.io/', 'policies.kyverno.io/')) and kind.endswith('Policy'):
                    self.add(source, path, index, 'admission_policy', doc, name=meta.get('name'), role=role)
                elif kind in {'ConstraintTemplate', 'Assign', 'AssignMetadata', 'ModifySet'}:
                    self.add(source, path, index, 'admission_policy', doc, name=meta.get('name'), role=role)
                elif kind in {'KubeArmorPolicy', 'KubeArmorHostPolicy', 'KubeArmorClusterPolicy', 'TracingPolicy', 'TracingPolicyNamespaced'}:
                    self.add(source, path, index, 'runtime_policy', doc, name=meta.get('name'), role=role)
                elif kind in {'NetworkPolicy', 'CiliumNetworkPolicy', 'CiliumClusterwideNetworkPolicy', 'GlobalNetworkPolicy'}:
                    self.add(source, path, index, 'network_policy', doc, name=meta.get('name'), role=role)
                elif api.startswith('chainsaw.kyverno.io/') and kind == 'Test':
                    self.add(source, path, index, 'workflow_fixture', {'workflow': doc}, role='fixture')
                elif api.startswith('cli.kyverno.io/') and kind == 'Test':
                    resources = []
                    for name in doc.get('resources', []):
                        linked = self.linked(source, path, name)
                        for resource in self.data(source, linked):
                            if isinstance(resource, dict):
                                resources.extend(resource.get('items', []) if resource.get('kind') == 'List' else [resource])
                    policies = [self.data(source, self.linked(source, path, p)) for p in doc.get('policies', [])]
                    context = {key: self.data(source, self.linked(source, path, doc[key])) for key in ('variables', 'context', 'userinfo') if key in doc}
                    for number, expected in enumerate(doc.get('results', [])):
                        for ri, resource_name in enumerate(expected.get('resources', [])):
                            names = resource_name.split('/')
                            matched = [r for r in resources if r.get('kind') == expected.get('kind') and r.get('metadata', {}).get('name') == names[-1]
                                       and (len(names) == 1 or r.get('metadata', {}).get('namespace', 'default') == names[-2])]
                            inputs = {'resource': matched[0] if len(matched) == 1 else None, 'policies': policies, 'context': context}
                            self.add(source, path, f'{index}:{number}:{ri}:{resource_name}', 'behavior_case', inputs, expected,
                                     family=expected.get('policy'), role='fixture',
                                     upstream_result_index=number, upstream_resource_index=ri,
                                     missing_unique_resource=len(matched) != 1)
                elif include_fixture_resources and fixture and kind and api:
                    self.add(source, path, index, 'resource_fixture', doc, role='fixture')

    def gatekeeper(self):
        source = 'gatekeeper-library'
        root = self.paths[source]/'library'
        self.manifests(source, root)
        for path in sorted(root.rglob('suite.yaml')):
            for suite in self.data(source, path):
                if not isinstance(suite, dict):
                    continue
                for ti, test in enumerate(suite.get('tests', [])):
                    dependencies = {k: self.data(source, self.linked(source, path, test[k]))
                                    for k in ('template', 'constraint') if k in test}
                    inventory = [self.data(source, self.linked(source, path, p)) for p in test.get('inventory', [])]
                    for ci, case in enumerate(test.get('cases', [])):
                        obj = self.data(source, self.linked(source, path, case['object'])) if case.get('object') else None
                        self.add(source, path, f'{ti}:{ci}', 'behavior_case',
                                 {'object': obj, 'dependencies': dependencies, 'inventory': inventory},
                                 {'assertions': assertions_for(case)}, name=case.get('name'),
                                 upstream_test_name=test.get('name'),
                                 family=str(path.parent.relative_to(root)), role='fixture')

    def falco(self, source, root):
        for path in sorted(root.rglob('*.yaml')):
            if 'vendor' in path.parts or path.stat().st_size > 2000000:
                continue
            for doc in self.data(source, path):
                if not isinstance(doc, list):
                    continue
                for index, entity in enumerate(doc):
                    if not isinstance(entity, dict):
                        continue
                    key = next((k for k in ('rule', 'macro', 'list') if k in entity), None)
                    if key:
                        parts = path.relative_to(self.paths[source]).parts
                        fixture = any(p in {'test', 'tests', 'testdata'} or p.startswith('dummy') for p in parts) or 'example' in path.name
                        self.add(source, path, index, 'detection_rule' if key == 'rule' else 'detection_dependency', entity,
                                 name=entity[key], family=entity[key], dependency_kind=key,
                                 role='fixture' if fixture else 'reference',
                                 technique_ids=technique_ids(entity))

    def kubescape(self):
        source = 'kubescape-regolibrary'
        root = self.paths[source]
        for pattern, record_type in [('controls/*.json', 'posture_control'), ('rules/*/rule.metadata.json', 'posture_rule')]:
            for path in sorted(root.glob(pattern)):
                for doc in self.data(source, path):
                    if isinstance(doc, dict):
                        if record_type == 'posture_rule':
                            implementations=[]
                            for implementation in sorted(path.parent.glob('*.rego')):
                                relative=self.file(source,implementation)
                                implementations.append({'path':relative,'sha256':self.inventory[source+':'+relative]['sha256'],
                                                        'source_code':implementation.read_text()})
                            doc={**doc,'implementation_sources':implementations}
                        self.add(source, path, 0, record_type, doc, name=doc.get('name'), family=doc.get('controlID') or path.parent.name)
        for path in sorted((root/'rules').glob('*/test/**/expected.json')):
            values = self.data(source, path)
            resources = []
            for p in sorted((path.parent/'input').rglob('*')):
                if p.suffix in {'.json', '.yaml', '.yml'}:
                    resources.extend(self.data(source, p))
            self.add(source, path, 0, 'behavior_case', {'resources': resources}, {'expected_output': values},
                     family=path.relative_to(root).parts[1], role='fixture')

    def pss(self):
        source = 'kubernetes'
        root = self.paths[source]/'staging/src/k8s.io/pod-security-admission/test/testdata'
        for path in sorted(root.rglob('*.yaml')):
            parts = path.relative_to(root).parts
            if len(parts) != 4 or parts[2] not in {'pass', 'fail'}:
                continue
            for index, doc in enumerate(self.data(source, path)):
                family = re.sub(r'\d+$', '', path.stem)
                self.add(source, path, index, 'behavior_case',
                         {'resource': doc, 'level': parts[0], 'kubernetes_version': parts[1]},
                         {'expected_policy_result': parts[2], 'origin': 'upstream_generated_fixture_directory'},
                         family=family, role='fixture')

    def other(self):
        source = 'sigma'
        for path in sorted((self.paths[source]/'rules').rglob('*.yml')):
            for index, doc in enumerate(self.data(source, path)):
                if isinstance(doc, dict) and doc.get('detection') and selected_sigma(doc):
                    self.add(source, path, index, 'detection_rule', doc, name=doc.get('title'), family=doc.get('id'), technique_ids=technique_ids(doc))
        source = 'atomic-red-team'
        for path in sorted((self.paths[source]/'atomics').glob('*/*.yaml')):
            for doc in self.data(source, path):
                if not isinstance(doc, dict):
                    continue
                for index, atomic in enumerate(doc.get('atomic_tests', [])):
                    if {'linux', 'containers', 'iaas'} & set(atomic.get('supported_platforms', [])):
                        self.add(source, path, index, 'attack_procedure', atomic, name=atomic.get('name'), family=doc.get('attack_technique'),
                                 technique_ids=[doc.get('attack_technique')], execution_permitted_by_builder=False)
        for source, pattern in [('stratus-red-team', 'docs/attack-techniques/*/*.md'), ('kubehound', 'docs/reference/attacks/*.md')]:
            for path in sorted(self.paths[source].glob(pattern)):
                if path.stem == 'index':
                    continue
                text = path.read_text()
                self.add(source, path, 0, 'attack_reference', {'text': text}, name=path.stem, technique_ids=technique_ids(text), execution_permitted_by_builder=False)
        source = 'falco-talon'
        for name in ('rules.yaml', 'rules_override.yaml'):
            path = self.paths[source]/name
            if not path.exists():
                continue
            for doc in self.data(source, path):
                if not isinstance(doc, list):
                    continue
                for index, item in enumerate(doc):
                    if not isinstance(item, dict):
                        continue
                    key = 'rule' if 'rule' in item else 'action'
                    if key in item:
                        self.add(source, path, index, 'response_mapping' if key == 'rule' else 'response_action', item,
                                 name=item[key], target_origin_note='upstream example; no measured response outcome')
        source = 'policybench'
        path = self.paths[source]/'data/policybench-nl-v1.0.md'
        for item in policybench_entries(path.read_text()):
            self.add(source, path, item['id'], 'natural_language_intent', {'text': item['text']}, name=item['id'],
                     family=item['id'], category=item.get('category'), private_evaluation_fixtures_available=False)

    def attack(self):
        source = 'attack-stix-data'
        path = self.paths[source]/'enterprise-attack/enterprise-attack.json'
        data = self.data(source, path)[0]
        objects = {o['id']: o for o in data['objects']}
        chosen = {o['id'] for o in objects.values() if o['type'] == 'attack-pattern'
                  and set(o.get('x_mitre_platforms', [])) & {'Containers', 'Linux', 'IaaS'}
                  and not o.get('revoked') and not o.get('x_mitre_deprecated')}
        relationships = [o for o in objects.values() if o['type'] == 'relationship'
                         and not o.get('revoked') and not o.get('x_mitre_deprecated')
                         and o.get('target_ref') in chosen
                         and o.get('relationship_type') in {'mitigates', 'detects', 'subtechnique-of'}]
        chosen.update(o['source_ref'] for o in relationships if o['source_ref'] in objects)
        for key in sorted(chosen):
            obj = objects[key]
            self.add(source, path, key, 'attack_technique' if obj['type'] == 'attack-pattern' else 'defense_reference', obj,
                     name=obj.get('name'), family=key, technique_ids=technique_ids(obj))
        for obj in relationships:
            self.add(source, path, obj['id'], 'defense_relationship', obj, family=obj['target_ref'])

    def falco_fixtures(self):
        source = 'falco-event-generator'
        root = self.paths[source]
        for path in sorted((root/'events/syscall').glob('*.go')):
            text = path.read_text()
            if 'events.Register(' in text:
                self.add(source,path,0,'generator_definition',{'source_code':text},name=path.stem,
                         role='fixture',execution_permitted_by_builder=False)
        for directory in ('events/k8saudit/yaml','samples','test/events'):
            for path in sorted((root/directory).rglob('*.yaml')):
                for index, doc in enumerate(self.data(source,path)):
                    if isinstance(doc,dict) and isinstance(doc.get('tests'),list):
                        for ti,test in enumerate(doc['tests']):
                            target={key:test[key] for key in ('rule','expectedOutcome') if key in test}
                            inputs={key:value for key,value in test.items() if key not in target}
                            self.add(source,path,f'{index}:{ti}','generator_definition',inputs,target,
                                     name=test.get('name'),role='fixture',execution_permitted_by_builder=False)
                    elif isinstance(doc,dict):
                        self.add(source,path,index,'generator_definition',doc,role='fixture',execution_permitted_by_builder=False)
        source='falco-testing'
        for directory in ('tests/data/rules','tests/data/captures','tests/falco'):
            for path in sorted((self.paths[source]/directory).glob('*.go')):
                self.add(source,path,0,'test_definition',{'source_code':path.read_text()},name=path.stem,
                         role='fixture',execution_permitted_by_builder=False)

    def recorded_events(self):
        source='splunk-attack-data';root=self.paths[source]
        for path in sorted(root.glob('datasets/**/*.yml')):
            if str(path.parent.relative_to(root)) not in self.sources[source]['sparse_paths']:
                continue
            for index,doc in enumerate(self.data(source,path)):
                if isinstance(doc,dict):
                    self.add(source,path,index,'recorded_dataset_context',doc,name=doc.get('id') or path.stem,
                             family=str(path.parent.relative_to(root)),role='fixture',
                             per_event_maliciousness_labels_available=False)
        for item in self.sources[source]['large_files']:
            path=root/item['path'];payload=root.parent/'large-objects'/item['sha256']
            if payload.stat().st_size!=item['bytes'] or sha(payload)!=item['sha256']:
                raise ValueError('Recorded log differs from locked LFS digest')
            text=payload.read_text()
            try:
                data=json.loads(text)
                events=data if isinstance(data,list) else [data]
                event_format='json'
            except ValueError:
                events=[];event_format='lines'
                for line in text.splitlines():
                    if not line.strip():continue
                    try:events.append(json.loads(line))
                    except ValueError:events.append({'raw_line':line})
            for index,event in enumerate(events):
                self.add(source,path,index,'recorded_event',{'event':event},role='fixture',
                         family='capture:'+item['sha256'],large_object_sha256=item['sha256'],
                         large_object_bytes=item['bytes'],event_format=event_format,
                         per_event_maliciousness_label=None)

    def build(self, out):
        for source in self.lock['sources']:
            verify_source(self.paths[source['name']], source)
        for source in ('kyverno-policies', 'kyverno-legacy', 'kubearmor-policies'):
            self.manifests(source, self.paths[source], True)
        self.manifests('tetragon', self.paths['tetragon']/ 'examples', True)
        self.manifests('tetragon', self.paths['tetragon']/ 'testdata', True)
        self.manifests('tetragon', self.paths['tetragon']/ 'pkg/sensors/tracing/testdata', True)
        self.gatekeeper()
        self.falco('falco-rules', self.paths['falco-rules']/ 'rules')
        self.falco('falco-plugins', self.paths['falco-plugins']/ 'plugins')
        self.kubescape()
        self.pss()
        self.other()
        self.attack()
        self.falco_fixtures()
        self.recorded_events()
        self.finish(out)

    def finish(self, out):
        ids = [r['id'] for r in self.records]
        if len(ids) != len(set(ids)):
            repeated = [key for key, count in Counter(ids).items() if count > 1]
            raise ValueError('Duplicate stable IDs: '+repr(repeated[:10]))
        by_hash = defaultdict(list)
        for row in self.records:
            by_hash[row['content_sha256']].append(row)
        duplicates = []
        for key, rows in sorted(by_hash.items()):
            if len(rows) > 1:
                duplicates.append({'sha256': key, 'ids': [r['id'] for r in rows], 'count': len(rows)})
        pairs = []
        for row in self.records:
            if row['role'] != 'reference' or row['record_type'] not in {'admission_policy', 'runtime_policy', 'network_policy', 'posture_control', 'posture_rule', 'detection_rule'}:
                continue
            doc = row['inputs']
            annotations = doc.get('metadata', {}).get('annotations', {})
            text = (doc.get('description') or doc.get('desc') or annotations.get('policies.kyverno.io/description')
                    or annotations.get('description') or annotations.get('kubearmor-policy-description'))
            if isinstance(text, str) and len(text.strip()) >= 30:
                pairs.append({'id': 'description:'+row['id'], 'inputs': {'intent_text': text.strip()},
                              'target': {'candidate_record_id': row['id']}, 'family_id': row['family_id'],
                              'source': row['source'], 'label_status': 'source_description_alignment',
                              'independent_expert_label': False, 'training_split': 'unassigned',
                              'allowed_use': 'weak supervision for retrieval; not incident response qualification'})
        out.mkdir(parents=True, exist_ok=False)
        files = []
        for name, rows in [('records.jsonl', sorted(self.records, key=lambda r:r['id'])),
                           ('intent-pairs.jsonl', sorted(pairs,key=lambda r:r['id'])),
                           ('files.jsonl', sorted(self.inventory.values(),key=lambda r:(r['source'],r['path']))),
                           ('duplicates.jsonl', duplicates), ('parse-errors.jsonl', self.errors)]:
            path = out/name
            path.write_text(''.join(encode(r)+'\n' for r in rows))
            files.append({'path': name, 'rows': len(rows), 'bytes': path.stat().st_size, 'sha256': sha(path)})
        coverage = {'schema_version': '1.0.0', 'collected_date': '2026-10-17',
                    'builder_sha256': sha(Path(__file__)), 'collector_sha256': sha(HERE/'collect.py'),
                    'python_version': platform.python_version(), 'pyyaml_version': yaml.__version__,
                    'sources_lock_sha256': sha(HERE/'sources.lock.json'), 'source_count': len(self.sources),
                    'records': len(self.records), 'unique_record_payloads': len(by_hash),
                    'exact_duplicate_groups': len(duplicates), 'source_files_read': len(self.inventory),
                    'by_type': dict(sorted(Counter(r['record_type'] for r in self.records).items())),
                    'by_source': dict(sorted(Counter(r['source']['name'] for r in self.records).items())),
                    'by_role': dict(Counter(r['role'] for r in self.records)), 'intent_alignment_pairs': len(pairs),
                    'parse_errors': len(self.errors), 'new_engine_executions_in_this_builder': 0,
                    'independently_labelled_response_decisions': 0, 'hosted_model_api_calls': 0,
                    'split_status': 'unassigned; exact duplicates and policy families must stay together; near-duplicate review remains required',
                    'not_all_collected_definitions_are_executed': True,
                    'raw_corpus_distribution': 'Local cache; per-source licenses and notices retained. No blanket relicensing.',
                    'files': files}
        (out/'MANIFEST.json').write_text(json.dumps(coverage,indent=2)+'\n')
        print(json.dumps(coverage,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--legacy-cache', type=Path, help='Reuse the earlier pinned source cache')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    names = [s['name'] for s in json.loads((HERE/'sources.lock.json').read_text())['sources']]
    paths = {name: args.cache/name for name in names}
    if args.legacy_cache:
        for name in names:
            if not paths[name].exists() and (args.legacy_cache/name).exists():
                paths[name] = args.legacy_cache/name
    Builder(paths).build(args.out)
