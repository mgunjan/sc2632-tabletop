import json
import unittest
import run_provider as r


class OrderParity(unittest.TestCase):
    def test_runtime_order_preserves_states_labels_and_legacy_file(self):
        path = r.pilot.OUT/'cases.json'; original = path.read_bytes(); items = json.loads(original)
        ordered = r.runtime_questions(items)
        self.assertEqual(path.read_bytes(), original)
        for before, after in zip(items, ordered):
            self.assertEqual(before, after)  # dictionary equality checks semantic content
            if after['question'] == r.pilot.da.QUESTION['control']:
                self.assertEqual(list(after['question']['criteria']), list(r.pilot.da.CONTROLS))
        self.assertNotEqual(list(items[0]['question']['criteria']), list(ordered[0]['question']['criteria']))

    def test_an_unknown_question_cannot_be_silently_rewritten(self):
        with self.assertRaises(ValueError): r.runtime_questions([{'question': {'type': 'choice', 'criteria': {'x': 'X'}}}])


if __name__ == '__main__': unittest.main()
