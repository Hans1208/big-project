import unittest

from integration_readiness import find_analysis_contract_gaps, find_consult_response_gaps


class IntegrationReadinessTests(unittest.TestCase):
    def test_full_analysis_requires_all_schema_fields(self):
        self.assertIn("full analysis payload missing: eligibility", find_analysis_contract_gaps({"summary": "x"}))

    def test_projected_consult_response_reports_unavailable_fields(self):
        response = {"consult_summary": "x", "consult_case_type": "친족", "consult_case_subtype": "이혼 및 위자료", "consult_extracted": {}, "consult_timeline": [], "related_statutes": [], "related_precedents": []}
        gaps = find_consult_response_gaps(response)
        self.assertIn("full analysis projection required before validation: checklist_json", gaps)


if __name__ == "__main__":
    unittest.main()
