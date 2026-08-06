import unittest

from dataset_governance import validate_manifest
from scenario_manifest import build_role_separated_manifest


class ScenarioManifestTests(unittest.TestCase):
    def test_assigns_three_distinct_roles(self):
        catalog = [{"case_id": "SYN-E-001", "difficulty": "easy", "spec_path": "01_case_specs/SYN-E-001.md"}, {"case_id": "SYN-M-001", "difficulty": "medium", "spec_path": "01_case_specs/SYN-M-001.md"}, {"case_id": "SYN-H-001", "difficulty": "hard", "spec_path": "01_case_specs/SYN-H-001.md"}]
        manifest = build_role_separated_manifest(catalog, ["a", "b", "c"])
        self.assertEqual(validate_manifest(manifest), [])

    def test_requires_three_people(self):
        with self.assertRaises(ValueError):
            build_role_separated_manifest([], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
