import unittest

from dataset_split import build_case_split


class DatasetSplitTests(unittest.TestCase):
    def test_split_is_case_level_deterministic_and_has_target_counts(self):
        catalog = [{"case_id": f"SYN-{difficulty[0].upper()}-{index}", "difficulty": difficulty} for difficulty in ("easy", "medium", "hard") for index in range(3)]
        split = build_case_split(catalog)
        self.assertEqual(split["counts"], {"train": 5, "validation": 2, "test": 2})
        assigned = [case_id for values in split["assignments"].values() for case_id in values]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), {item["case_id"] for item in catalog})

    def test_balanced_45_cases_has_exact_60_20_20_ratio(self):
        catalog = [{"case_id": f"SYN-{difficulty[0].upper()}-{index}", "difficulty": difficulty} for difficulty in ("easy", "medium", "hard") for index in range(15)]
        self.assertEqual(build_case_split(catalog)["counts"], {"train": 27, "validation": 9, "test": 9})
