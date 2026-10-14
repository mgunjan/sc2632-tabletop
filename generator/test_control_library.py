"""Control coverage, provenance and governance checks; no live cluster access."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import control_library as lib
import generate as g


class Controls(unittest.TestCase):
    def test_vocabulary_templates_and_test_references_are_bound(self):
        catalog = lib.load()
        self.assertEqual(len(catalog['controls']), 10)
        self.assertEqual(sum(c['implementation'] is not None for c in catalog['controls'].values()), 7)
        bad = copy.deepcopy(catalog)
        bad['controls']['egress_profile']['policy'] = 'arbitrary-policy'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'catalog.json'; p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError): lib.load(p)

    def test_duplicate_identity_and_escaping_paths_are_rejected(self):
        catalog = lib.load()
        for change in ['id', 'path']:
            bad = copy.deepcopy(catalog)
            if change == 'id': bad['controls']['egress_profile']['id'] = bad['controls']['restrict_registry']['id']
            else: bad['controls']['egress_profile']['tests'] = ['/etc/passwd']
            with tempfile.TemporaryDirectory() as d:
                p = Path(d)/'catalog.json'; p.write_text(json.dumps(bad))
                with self.assertRaises(ValueError): lib.load(p)

    def test_review_does_not_turn_metadata_into_executed_evidence(self):
        spec = json.loads((lib.ROOT/'generator/spec-a.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            r = lib.review(spec, Path(d))
            self.assertFalse(r['promotion_allowed'])
            self.assertEqual(r['catalog_sha256'], hashlib.sha256(lib.CATALOG.read_bytes()).hexdigest())
            self.assertTrue(all(c['evidence_status'] == 'NOT_EXECUTED_BY_CATALOG_REVIEW' for c in r['controls']))
            manual = next(c for c in r['controls'] if c['key'] == 'restrict_api_access')
            self.assertIsNone(manual['rendered_sha256'])
            self.assertEqual(manual['status'], 'HUMAN_IMPLEMENTATION_REQUIRED')
            rendered = g.render_policies(spec, 'Deny')['deny-privilege-escalation.yaml']
            record = next(c for c in r['controls'] if c['key'] == 'deny_privilege_escalation')
            self.assertEqual(record['rendered_sha256'], hashlib.sha256(rendered.encode()).hexdigest())
            self.assertIn('runAsNonRoot', ' '.join(record['limits']))

    def test_exception_limit_and_unknown_controls_cannot_disappear(self):
        spec = json.loads((lib.ROOT/'generator/spec-a.json').read_text())
        spec['exceptions'][0]['ttl_hours'] = 48
        r = lib.review(spec)
        self.assertTrue(any(c['status'] == 'EXCEPTION_LIMIT_EXCEEDED' for c in r['controls']))
        spec['controls']['unknown'] = {'enabled': True, 'in_intent': True}
        with self.assertRaises(g.SpecInvalid): lib.review(spec)

    def test_shared_artifact_writer_attaches_catalog_review(self):
        spec = json.loads((lib.ROOT/'generator/spec-b.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            g.write_policy_artifacts(spec, Path(d))
            r = json.loads((Path(d)/'control-review.json').read_text())
            self.assertFalse(r['promotion_allowed'])
            self.assertIn('ACG-IAM-002', lib.pr_section(r))


if __name__ == '__main__': unittest.main()
