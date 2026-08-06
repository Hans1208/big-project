import unittest

from fact_conflict import explicit_conflicts, unsupported_assertions


class FactConflictTests(unittest.TestCase):
    def test_detects_unmatched_date_amount_and_finality(self):
        conflicts = explicit_conflicts(["상대방은 2024-01-15에 서면으로 인정했고 금액은 98,765,432원으로 확정되었다."], "전사에는 금액과 날짜를 확인 중이라고 되어 있다.")
        self.assertIn("unmatched_specific_date", conflicts)
        self.assertIn("unmatched_specific_amount", conflicts)
        self.assertIn("unmatched_finality_statement", conflicts)

    def test_flags_unsupported_contextual_assertion_for_review(self):
        result = unsupported_assertions(["상대방이 책임을 부인하고 있다는 정황이 있습니다."], "내담자는 관련 자료를 정리 중입니다.")
        self.assertEqual(result, ["책임을 부인"])

    def test_detects_unmatched_relationship_or_representation_fact(self):
        conflicts = explicit_conflicts(["내담자의 배우자가 상대방을 대리하여 이미 합의서를 작성했다."], "내담자는 관련 자료를 정리 중입니다.")
        self.assertIn("unmatched_relationship_or_representation_fact", conflicts)

    def test_uncertain_unmatched_relation_requires_review_not_high_risk(self):
        claim = "이모가 법정 보호자일 가능성이 있어 지정 문서를 확인해야 합니다."
        transcript = "이모가 아이를 돌보고 있으나 법적 지정 여부는 말하지 않았습니다."
        self.assertNotIn("unmatched_relationship_or_representation_fact", explicit_conflicts([claim], transcript))
        self.assertIn("unmatched_uncertain_relation_or_finality_claim", unsupported_assertions([claim], transcript))

    def test_unmatched_inheritance_partition_finality_is_high_risk(self):
        claim = "상속재산 분할 합의가 확정되어 모두 이행 의무가 있습니다."
        transcript = "상속인들이 분할 방법을 논의 중이며 합의서는 작성하지 않았습니다."
        self.assertIn("unmatched_relationship_or_representation_fact", explicit_conflicts([claim], transcript))

    def test_unmatched_mediation_approval_is_high_risk(self):
        claim = "법원이 조정 합의를 승인해 효력이 발생했습니다."
        transcript = "조정기일에서 제안서를 받았을 뿐 법원 결론은 듣지 못했습니다."
        self.assertIn("unmatched_relationship_or_representation_fact", explicit_conflicts([claim], transcript))

    def test_detects_unmatched_registration_or_court_finality(self):
        conflicts = explicit_conflicts(["법원이 개명을 허가해 등록까지 마쳤다."], "개명 신청서를 준비하고 있다.")
        self.assertIn("unmatched_finality_statement", conflicts)

    def test_detects_unmatched_final_custody_or_visitation_order(self):
        claim = "어머니의 단독 친권이 법원에서 확정됐고 법원이 격주 토요일 면접교섭을 허가했습니다."
        conflicts = explicit_conflicts([claim], "부모가 양육을 의논하고 있고 면접 일정도 정해지지 않았습니다.")
        self.assertIn("unmatched_finality_statement", conflicts)

    def test_cautious_authority_statement_is_review_not_high_risk(self):
        claim = "외삼촌의 학교 업무 대리 권한은 위임 근거 확인이 필요합니다."
        self.assertNotIn("unmatched_relationship_or_representation_fact", explicit_conflicts([claim], "외삼촌이 학교 상담에 동행했습니다."))
        self.assertIn("unmatched_uncertain_relation_or_finality_claim", unsupported_assertions([claim], "외삼촌이 학교 상담에 동행했습니다."))

    def test_negated_finality_statement_is_not_flagged(self):
        claim = "상속인들이 서류를 검토 중이며 정정이 완료되지 않았습니다."
        transcript = "상속인들이 서류를 준비하고 있습니다."
        self.assertNotIn("unmatched_finality_statement", explicit_conflicts([claim], transcript))

    def test_unnegated_finality_statement_is_still_flagged(self):
        claim = "상속인들의 정정이 완료돼 새 증명서가 발급됐습니다."
        transcript = "상속인들이 서류를 준비하고 있습니다."
        self.assertIn("unmatched_finality_statement", explicit_conflicts([claim], transcript))

    def test_negated_relationship_fact_is_not_flagged(self):
        claim = "외삼촌은 대리 권한이 없습니다."
        transcript = "외삼촌이 학교 상담에 동행했습니다."
        self.assertNotIn("unmatched_relationship_or_representation_fact", explicit_conflicts([claim], transcript))

    def test_negated_unsupported_assertion_term_is_not_flagged(self):
        result = unsupported_assertions(["상대방이 책임을 부인하지 않았다는 취지로 말했습니다."], "내담자는 관련 자료를 정리 중입니다.")
        self.assertEqual(result, [])
