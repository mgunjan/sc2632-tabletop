"""Regression tests for full-coverage Laya minibatches and class weighting."""
import random
import unittest

from train_coverage_laya import coverage_batches, frequency_class_weights


class CoverageTrainingTests(unittest.TestCase):
    def test_shuffled_epochs_visit_every_row_once_with_partial_tail(self):
        batches = coverage_batches(23, 8, random.Random(19))
        flattened = [i for batch in batches for i in batch]
        self.assertEqual([len(batch) for batch in batches], [8, 8, 7])
        self.assertEqual(sorted(flattened), list(range(23)))
        self.assertEqual(len(flattened), len(set(flattened)))

    def test_rejects_empty_or_nonpositive_batch_inputs(self):
        with self.assertRaises(ValueError):
            coverage_batches(0, 8, random.Random(19))
        with self.assertRaises(ValueError):
            coverage_batches(10, 0, random.Random(19))

    def test_inverse_frequency_weights_equalize_class_contribution(self):
        import torch
        labels = torch.tensor([0] * 2 + [1] * 3 + [2] * 5 + [3] * 30)
        weights = frequency_class_weights(labels)
        self.assertAlmostEqual(float(weights[labels].mean()), 1.0, places=6)
        contributions = [float(weights[i] * (labels == i).sum()) for i in range(4)]
        for value in contributions[1:]:
            self.assertAlmostEqual(value, contributions[0], places=5)

    def test_class_weight_power_is_bounded(self):
        import torch
        labels = torch.tensor([0, 0, 1, 1, 2, 2, 3, 3])
        with self.assertRaises(ValueError):
            frequency_class_weights(labels, power=0)
        with self.assertRaises(ValueError):
            frequency_class_weights(labels, power=1.1)


if __name__ == '__main__':
    unittest.main()
