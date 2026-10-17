"""Integrity checks for evidence boundaries and source-derived supervision."""
from pathlib import Path
import tempfile
import unittest

import yaml
from build import Builder, assertions_for, content_hash, policybench_entries, selected_sigma
from audit import gator_cases


class EvidenceBoundaries(unittest.TestCase):
    def test_source_symlink_aliases_keep_distinct_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'target.yaml';target.write_text('kind: Pod')
            alias=root/'alias.yaml';alias.symlink_to(target)
            builder=Builder.__new__(Builder);builder.paths={'test':root};builder.inventory={}
            self.assertEqual(builder.file('test',target),'target.yaml')
            self.assertEqual(builder.file('test',alias),'alias.yaml')
            self.assertEqual(builder.inventory['test:target.yaml']['sha256'],builder.inventory['test:alias.yaml']['sha256'])

    def test_repeated_resource_declarations_do_not_collide(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'resource.yaml').write_text('apiVersion: v1\nkind: Pod\nmetadata: {name: p}\n')
            (root/'suite.yaml').write_text('apiVersion: cli.kyverno.io/v1alpha1\nkind: Test\nresources: [resource.yaml]\npolicies: []\nresults:\n- policy: privilege\n  kind: Pod\n  result: fail\n  resources: [p, p]\n')
            builder=Builder.__new__(Builder);builder.paths={'test':root};builder.inventory={};builder.records=[];builder.errors=[]
            builder.sources={'test':{'revision':'a'*40,'url':'https://example.org/repo.git','license_id':'Apache-2.0'}}
            builder.manifests('test',root)
            self.assertEqual(len(builder.records),2)
            self.assertNotEqual(builder.records[0]['id'],builder.records[1]['id'])
            self.assertEqual(builder.records[0]['content_sha256'],builder.records[1]['content_sha256'])

    def test_gator_case_pass_remains_bound_to_suite_and_test(self):
        text='=== RUN   owner\n    --- PASS: allowed (0.01s)\nok\t/data/gatekeeper-library/library/labels/suite.yaml\t0.01s\n'
        self.assertEqual(gator_cases(text), [('library/labels/suite.yaml','owner','allowed','PASS')])

    def test_incomplete_gator_output_is_not_verification(self):
        with self.assertRaises(ValueError):
            gator_cases('=== RUN   owner\n    --- PASS: allowed (0.01s)\n')

    def test_false_and_zero_assertions_are_retained(self):
        case = yaml.safe_load('assertions:\n- violations: no\n- violations: 0\n')
        assertions = assertions_for(case)
        self.assertIs(assertions[0]['violations'], False)
        self.assertEqual(assertions[1]['violations'], 0)

    def test_changed_expected_outcome_is_not_an_exact_duplicate(self):
        a = {'inputs': {'kind': 'Pod'}, 'target': {'result': 'pass'}}
        b = {'inputs': {'kind': 'Pod'}, 'target': {'result': 'fail'}}
        self.assertNotEqual(content_hash(a), content_hash(b))

    def test_key_order_is_not_artificial_novelty(self):
        self.assertEqual(content_hash({'x': 1, 'y': 2}), content_hash({'y': 2, 'x': 1}))

    def test_scope_filter_excludes_unrelated_windows_rules(self):
        self.assertFalse(selected_sigma({'logsource': {'product': 'windows'}}))
        self.assertTrue(selected_sigma({'logsource': {'product': 'kubernetes'}}))

    def test_natural_language_does_not_include_fixture_metadata(self):
        rows = policybench_entries('## intent_one\n- category: kubernetes_admission\n- fixtures: private_slug\n\nDeny privileged Pods.\n')
        self.assertEqual(rows[0]['text'], 'Deny privileged Pods.')
        self.assertEqual(rows[0]['fixtures'], 'private_slug')

    def test_linked_fixture_cannot_escape_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'repo';root.mkdir()
            (Path(folder)/'outside.yaml').write_text('kind: Secret')
            builder = Builder.__new__(Builder);builder.paths = {'test': root}
            with self.assertRaises(ValueError):
                builder.linked('test', root/'suite.yaml', '../outside.yaml')

    def test_source_expectation_is_separate_from_candidate_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'fixture.yaml';path.write_text('kind: Pod')
            builder=Builder.__new__(Builder)
            builder.paths={'test':root};builder.records=[];builder.inventory={}
            builder.sources={'test':{'revision':'a'*40,'url':'https://example.org/repo.git','license_id':'Apache-2.0'}}
            row=builder.add('test',path,0,'behavior_case',{'resource':{'kind':'Pod'}},{'result':'fail'})
            self.assertNotIn('target',row['inputs'])
            self.assertEqual(row['target']['result'],'fail')
            self.assertFalse(row['independent_response_label'])
            self.assertEqual(row['execution_status'],'not_executed')
            self.assertEqual(row['training_split'],'unassigned')


if __name__=='__main__':unittest.main()
