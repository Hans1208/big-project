import unittest
from pathlib import Path

from generation_registry import build_generation_plan


class GenerationRegistryTests(unittest.TestCase):
    def test_plan_contains_hash_without_secrets(self):
        root = Path(__file__).parent.parent / "data"
        plan = build_generation_plan([{"case_id": "SYN-E-001", "difficulty": "easy", "transcript_path": "02_transcripts/SYN-E-001.txt"}], root, "gemini-2.5-flash")
        self.assertEqual(plan[0]["answer_generator"], "gemini_structured_output_v1")
        self.assertEqual(len(plan[0]["transcript_sha256"]), 64)
        self.assertNotIn("key", " ".join(plan[0].keys()).lower())


if __name__ == "__main__":
    unittest.main()
