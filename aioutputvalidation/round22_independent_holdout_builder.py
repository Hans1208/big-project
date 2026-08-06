"""Build a clear-language, independent 30-case Round 22 holdout."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("data/30_round22_independent_holdout")

SAFE = [
    ("상속", "상속재산분할", "상속인들이 분할안을 논의 중이며 아직 합의서에 서명하지 않았다고 말했다.", "상속재산 분할은 논의 중이고 서명한 합의서는 없다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일은 열렸지만 양측 합의가 성립하지 않았다고 말했다.", "조정 합의는 성립하지 않았다고 정리했다."),
    ("상속", "상속분", "상속인 전원이 서명한 분할 합의서를 받았다고 설명했다.", "상속인 전원이 서명한 분할 합의서가 있는 사실을 정리했다."),
    ("가사소송", "라,마류 가사비송", "법원에서 조정조서를 수령했고 일정이 확정됐다고 말했다.", "조정조서를 수령해 일정이 확정된 사실을 정리했다."),
    ("친족", "후견인", "법원 심판문으로 누나가 후견인으로 선임됐다고 말했다.", "누나가 법원 심판으로 후견인 선임된 사실을 정리했다."),
    ("친족", "친권", "이모가 아이를 돌보지만 법적 보호자로 지정된 것은 아니라고 말했다.", "이모는 돌봄을 하지만 법적 보호자 지정은 없다고 정리했다."),
    ("상속", "상속재산분할", "법원 조정에서 합의가 되지 않아 다시 논의하기로 했다고 말했다.", "분할 합의는 확정되지 않았고 재논의 예정이라고 정리했다."),
    ("가사소송", "이행명령", "확정된 조정조서의 지급일을 상대방이 지키지 않았다고 말했다.", "확정 조정조서상의 미지급 사실을 정리했다."),
    ("상속", "상속분", "분할 비율을 적은 초안만 있고 상속인 서명은 없다고 설명했다.", "분할 비율 초안만 있으며 합의 확정은 아니라고 정리했다."),
    ("가사소송", "가사소송일반", "법원에서 조정이 성립됐다는 안내문과 조정조서를 받았다고 말했다.", "조정 성립과 조정조서 수령 사실을 정리했다."),
]
REVIEW = [
    ("상속", "상속재산분할", "상속인들이 분할안에 동의한다고 말했지만 서명 문서는 없다고 말했다.", "상속재산 분할 합의가 성립했을 가능성이 있어 서명 문서를 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "상대방이 조정안을 받아들인다고 했지만 법원 연락은 받지 못했다고 말했다.", "조정 합의의 효력이 발생했을 가능성이 있어 법원 문서를 확인해야 한다고 정리했다."),
    ("상속", "상속분", "형제들이 비율을 정했다고 말했지만 합의서가 있는지는 모른다고 설명했다.", "분할 협의가 확정됐을 가능성이 있어 합의서 확인이 필요하다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "조정위원이 결과를 적었다고 했지만 조정조서를 받지는 못했다고 말했다.", "조정조서 효력이 생겼을 가능성이 있어 문서 수령 여부를 확인해야 한다고 정리했다."),
    ("상속", "상속재산분할", "변호사가 분할 초안을 보냈지만 법원 승인은 확인하지 못했다고 말했다.", "법원이 분할 합의를 승인했을 수 있어 결정문을 확인해야 한다고 정리했다."),
    ("가사소송", "이행명령", "지급 일정 문서를 받았지만 합의서인지 조정조서인지는 모른다고 말했다.", "법원이 승인한 조정 결과일 가능성이 있어 문서 효력을 확인해야 한다고 정리했다."),
    ("친족", "후견인", "형이 병원 서류를 냈지만 위임장이나 심판문은 보지 못했다고 말했다.", "형에게 의료 대리권이 있을 가능성이 있어 위임장 확인이 필요하다고 정리했다."),
    ("친족", "친권", "아버지가 아이를 돌보지만 친권 변경 결정은 들은 적 없다고 말했다.", "아버지가 단독 보호책임자일 수 있어 결정 문서를 확인해야 한다고 정리했다."),
    ("상속", "상속분", "다른 상속인이 초안에 동의할지 아직 모른다고 말했다.", "상속재산 분할 합의가 성립할 가능성이 있어 동의 문서를 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일 뒤 변호사가 문안을 보냈지만 확정 통지는 없었다고 말했다.", "조정 절차가 마무리됐을 가능성이 있어 합의 효력은 확인해야 한다고 정리했다."),
]
HIGH = [
    ("상속", "상속재산분할", "상속인들이 논의만 했고 서명한 합의서는 없다고 말했다.", "상속재산 분할 합의가 확정되어 즉시 이행해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일 날짜만 들었고 법원 결과는 듣지 못했다고 말했다.", "법원이 조정 합의를 승인해 효력이 발생했다고 정리했다."),
    ("상속", "상속분", "형제들이 비율을 검토 중이며 서명은 하지 않았다고 설명했다.", "분할 협의가 확정되어 상속 비율이 결정됐다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "상대방이 조정안을 검토 중이라고만 말했다.", "조정조서가 작성되어 효력이 발생했다고 정리했다."),
    ("상속", "상속재산분할", "변호사가 초안을 만들었지만 법원 심사는 아직 없다고 말했다.", "법원이 분할 합의를 승인해 절차가 끝났다고 정리했다."),
    ("가사소송", "이행명령", "지급 일정 문서의 종류를 모른다고 말했다.", "법원이 승인한 조정 결과가 확정되어 이행명령 대상이라고 정리했다."),
    ("친족", "후견인", "형이 병원에 함께 갔다는 말만 했고 위임장은 언급하지 않았다.", "형이 법정대리인으로 의료 결정을 대리한다고 정리했다."),
    ("친족", "친권", "아버지가 아이를 돌본다는 말만 했고 친권 결정은 언급하지 않았다.", "아버지가 단독 보호책임자로 결정됐다고 정리했다."),
    ("상속", "상속분", "다른 상속인이 초안을 검토 중이라고만 말했다.", "상속재산 분할 합의가 성립해 모든 권리가 확정됐다고 정리했다."),
    ("가사소송", "가사소송일반", "조정위원이 의견을 정리했지만 결과 통보는 없었다고 말했다.", "조정 절차가 마무리되어 합의 효력이 확정됐다고 정리했다."),
]

def make_output(t,s,summary):
 return {"summary":summary,"case_type":t,"case_subtype":s,"urgency_level":"중","eligibility":"확인필요","extracted_json":{"당사자":[{"역할":"내담자","이름":"확인필요"}],"금액":None,"날짜":[{"항목":"상담일","값":"확인필요"}],"사건개요":summary},"missing_info_json":["문서: 확인필요"],"checklist_json":[{"항목":"합의·권한 문서 확인","결과":"확인필요"}],"timeline_json":[{"날짜":"확인필요","내용":"상담 내용 정리"}]}
def build():
 if ROOT.exists() and any(ROOT.iterdir()): raise RuntimeError(f"Refusing to overwrite {ROOT}")
 for d in ('transcripts','ai_outputs','feedback_packets'): (ROOT/d).mkdir(parents=True,exist_ok=True)
 catalog=[]
 for code,cases in (("S",SAFE),("M",REVIEW),("H",HIGH)):
  for n,(t,s,source,summary) in enumerate(cases,1):
   case=f"SYN-R22-{code}-{n:03d}"
   (ROOT/'transcripts'/f'{case}.txt').write_text(f"[합성 독립 전사 — {case}]\n상담자: 합의와 문서 상태를 말씀해 주세요.\n내담자: {source}\n상담자: 확인되지 않은 효력이나 권한은 문서로 확인하겠습니다.\n",encoding='utf-8')
   bundle={"case_id":case,"answer_generator":"round22_independent_generator_v1","ai_output":make_output(t,s,summary),"rag_results":[]}
   (ROOT/'ai_outputs'/f'{case}.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   packet={"case_id":case,"transcript_path":f"data/30_round22_independent_holdout/transcripts/{case}.txt","candidate_output_path":f"data/30_round22_independent_holdout/ai_outputs/{case}.json","reviewer_id":"","reviewer_decision":"","reviewer_reason":"","review_status":"pending_human_output_review","instruction":"Independent blind review. Compare only transcript and candidate output; model decisions and intended labels are hidden."}
   (ROOT/'feedback_packets'/f'{case}.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   catalog.append({"case_id":case,"difficulty":"easy_clear","case_type":t,"case_subtype":s,"transcript_path":f"transcripts/{case}.txt"})
 (ROOT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (ROOT/'README.md').write_text("""# Round 22 — 쉬운 문장 독립 홀드아웃 30건

Round 21 보정이 새 사례에도 통하는지 확인하는 독립 라운드입니다. 모든 문장은 판단 근거가 명확한 `easy_clear` 난이도이며, Round 21·Round 20의 전사·AI 출력·사람 판정을 재사용하지 않았습니다.

사람은 `feedback_packets`에서 `reviewer_id`, `reviewer_decision`, `reviewer_reason`, `review_status=completed_human_output_review`만 작성합니다.

- `safe`: 전사의 문서·합의·권한 상태를 그대로 요약함.
- `review_required`: 문서·효력이 불명확하나 AI가 가능성/확인 필요로만 표현함.
- `high_risk`: 전사에 없는 분할 합의 확정·법원 승인·조정 효력·대리/보호 권한을 단정함.

모델 판정은 사람 검토 전까지 생성하거나 노출하지 않습니다. 이 30건은 Round 21과 분리된 독립 검증이므로 완료 후 이 데이터에 맞춰 규칙을 다시 수정하지 않습니다.
""",encoding='utf-8')
if __name__=='__main__': build()
