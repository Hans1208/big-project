import unittest

from round63_independent_holdout_builder import HIGH, REVIEW, SAFE, make_case
from validator import schema_errors


class Round63IndependentHoldoutBuilderTests(unittest.TestCase):
    def test_builds_new_schema_valid_cases_for_each_tier(self):
        for group, item in (("S", SAFE[0]), ("M", REVIEW[0]), ("H", HIGH[0])):
            bundle, transcript = make_case(group, 1, item)
            self.assertTrue(bundle["case_id"].startswith("SYN-R63-"))
            self.assertFalse(schema_errors(bundle["ai_output"]))
            self.assertIn("합성 독립 전사", transcript)
