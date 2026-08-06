import json
import unittest
from collections import Counter
from pathlib import Path


class ScenarioCatalogTests(unittest.TestCase):
    def test_catalog_is_balanced_and_all_specs_exist(self):
        root = Path(__file__).parent.parent / "data"
        catalog = json.loads((root / "scenario_catalog.json").read_text(encoding="utf-8"))
        difficulty_counts = Counter(item["difficulty"] for item in catalog)
        self.assertEqual(set(difficulty_counts), {"easy", "medium", "hard"})
        self.assertEqual(len(set(difficulty_counts.values())), 1)
        self.assertGreaterEqual(next(iter(difficulty_counts.values())), 3)
        for item in catalog:
            self.assertTrue((root / item["spec_path"]).is_file())
            self.assertTrue((root / item["transcript_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
