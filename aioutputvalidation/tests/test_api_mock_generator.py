import json
import tempfile
import unittest
from pathlib import Path

from api_mock_generator import GENERATOR_ID, build_prompt, write_bundle


class ApiMockGeneratorTests(unittest.TestCase):
    def test_prompt_requires_no_added_facts(self):
        prompt = build_prompt("합성 상담 내용")
        self.assertIn("사실을 추가", prompt)
        self.assertIn("summary", prompt)

    def test_bundle_contains_no_label_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "candidate.json"
            write_bundle("SYN-E-001", {"summary": "x"}, path)
            bundle = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(bundle["answer_generator"], GENERATOR_ID)
        self.assertNotIn("is_hallucination", bundle)


if __name__ == "__main__":
    unittest.main()
