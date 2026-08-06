import unittest

from contrastive import recall_at_k, triplet_margin_loss


class ContrastiveTests(unittest.TestCase):
    def test_loss_rewards_positive_pair(self):
        self.assertEqual(triplet_margin_loss([1, 0], [1, 0], [0, 1]), 0.0)
        self.assertGreater(triplet_margin_loss([1, 0], [0, 1], [1, 0]), 0.0)

    def test_recall_at_k(self):
        score = recall_at_k([["A", "B"], ["D", "C"]], ["A", "C"], k=2)
        self.assertEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
