import unittest

from dataset_governance import validate_manifest


def record(case_id, difficulty, authors=("a", "b", "c")):
    return {"case_id": case_id, "difficulty": difficulty, "source_type": "synthetic", "scenario_author": authors[0], "answer_generator": authors[1], "gold_labeler": authors[2]}


class DatasetGovernanceTests(unittest.TestCase):
    def test_balanced_separated_manifest_passes(self):
        records = [record("E", "easy"), record("M", "medium"), record("H", "hard")]
        self.assertEqual(validate_manifest(records), [])

    def test_role_overlap_and_missing_difficulty_are_blocked(self):
        records = [record("E", "easy", ("a", "a", "c"))]
        errors = validate_manifest(records)
        self.assertTrue(any("distinct people" in error for error in errors))
        self.assertTrue(any("medium" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
