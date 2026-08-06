import unittest

from evaluation import cluster_bootstrap_intervals, evaluate_hallucination_predictions, select_threshold_by_f1


class EvaluationTests(unittest.TestCase):
    def test_metrics_are_calculated_correctly(self):
        result = evaluate_hallucination_predictions([True, True, False, False], [0.9, 0.2, 0.8, 0.1])
        self.assertEqual((result.true_positive, result.false_positive, result.true_negative, result.false_negative), (1, 1, 1, 1))
        self.assertEqual(result.precision, 0.5)
        self.assertEqual(result.recall, 0.5)
        self.assertEqual(result.f1, 0.5)

    def test_rejects_mismatched_input(self):
        with self.assertRaises(ValueError):
            evaluate_hallucination_predictions([True], [])

    def test_selects_safe_f1_threshold(self):
        selection = select_threshold_by_f1([True, True, False, False], [0.9, 0.7, 0.6, 0.1])
        self.assertEqual(selection.threshold, 0.7)
        self.assertEqual(selection.metrics.recall, 1.0)

    def test_case_clustered_bootstrap_returns_metric_intervals(self):
        intervals = cluster_bootstrap_intervals(["A", "A", "B", "B"], [True, False, True, False], [0.9, 0.1, 0.8, 0.2], 0.5, iterations=20)
        self.assertEqual(set(intervals), {"accuracy", "precision", "recall", "f1"})
        self.assertTrue(all(0 <= low <= high <= 1 for low, high in intervals.values()))


if __name__ == "__main__":
    unittest.main()
