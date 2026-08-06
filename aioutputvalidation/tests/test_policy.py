import unittest

from policy import load_policy


class PolicyTests(unittest.TestCase):
    def test_policy_is_ordered_and_versioned(self):
        policy = load_policy()
        self.assertEqual(policy.policy_version, "0.1.0")
        self.assertLess(policy.review_probability_threshold, policy.high_risk_probability_threshold)
