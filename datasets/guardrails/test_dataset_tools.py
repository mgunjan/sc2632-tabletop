"""Do not convert vacuous, ambiguous or excluded checks into verified labels."""
import unittest

from build_corpus import verify_expectation
from fetch_upstream import safe_member
from run_upstream import json_results


class DatasetTools(unittest.TestCase):
    def setUp(self):
        self.expected = {'policy': 'privilege', 'kind': 'Pod', 'result': 'fail'}
        self.row = {'ID': 1, 'POLICY': 'privilege', 'RULE': '', 'RESOURCE': 'v1/Pod/team/workload',
                    'REASON': 'Ok', 'RESULT': 'Pass'}

    def test_contract_pass_does_not_mean_policy_pass(self):
        observed = verify_expectation(self.expected, 'team/workload', [self.row])
        self.assertTrue(observed['verified_expectation'])
        self.assertIsNone(observed['direct_policy_result'])
        self.assertEqual(self.expected['result'], 'fail')

    def test_excluded_is_not_verification(self):
        observed = verify_expectation(self.expected, 'workload', [{**self.row, 'REASON': 'Excluded'}])
        self.assertFalse(observed['verified_expectation'])

    def test_missing_or_failed_check_is_not_verification(self):
        for rows in ([], [{**self.row, 'RESULT': 'Fail'}]):
            self.assertFalse(verify_expectation(self.expected, 'workload', rows)['verified_expectation'])

    def test_duplicate_observations_are_ambiguous(self):
        self.assertFalse(verify_expectation(self.expected, 'workload', [self.row, self.row])['verified_expectation'])

    def test_namespace_and_kind_cannot_be_borrowed(self):
        for row in ({**self.row, 'RESOURCE': 'v1/Pod/other/workload'},
                    {**self.row, 'RESOURCE': 'apps/v1/Deployment/team/workload'}):
            self.assertFalse(verify_expectation(self.expected, 'team/workload', [row])['verified_expectation'])

    def test_json_progress_is_not_a_result(self):
        self.assertEqual(json_results('Loading [stuff]\n[{"note":"not an observation"}]'), [])
        self.assertEqual(json_results('Loading...\n[{"RESULT":"Pass"}]\nTest Summary'), [{'RESULT': 'Pass'}])

    def test_archive_path_escape_is_rejected(self):
        for name in ('../outside.scap', '/absolute.scap', 'traces/../../outside.scap'):
            with self.assertRaises(ValueError):
                safe_member(name)


if __name__ == '__main__':
    unittest.main()
