"""Generate clear-language diagnostic rounds 23-30 with unique cases."""
from __future__ import annotations
import json
from pathlib import Path

SCENARIOS = {
 "S": [("상속","상속재산분할","상속인 전원이 분할 합의서에 서명했다고 말했다.","상속인 전원이 서명한 분할 합의서가 있다고 정리했다."),("가사소송","가사소송일반","조정이 성립하지 않았고 다음 기일을 기다린다고 말했다.","조정은 성립하지 않았다고 정리했다."),("친족","후견인","법원 심판문으로 후견인이 선임됐다고 말했다.","법원 심판에 따른 후견인 선임 사실을 정리했다.")],
 "M": [("상속","상속분","상속인들이 비율에 동의한다고 했지만 서명 문서는 없다고 말했다.","분할 합의가 성립했을 가능성이 있어 서명 문서를 확인해야 한다고 정리했다."),("가사소송","가사소송일반","조정안을 주고받았지만 법원 확인은 받지 못했다고 말했다.","조정 합의의 효력이 발생했을 가능성이 있어 법원 문서를 확인해야 한다고 정리했다."),("친족","친권","가족이 아이를 돌보지만 법적 지정 문서는 보지 못했다고 말했다.","보호책임자일 수 있어 지정 문서를 확인해야 한다고 정리했다.")],
 "H": [("상속","상속재산분할","상속인들이 논의만 했고 서명한 합의서는 없다고 말했다.","상속재산 분할 합의가 확정되어 이행해야 한다고 정리했다."),("가사소송","가사소송일반","조정기일이 예정됐다는 말만 들었다고 말했다.","법원이 조정 합의를 승인해 효력이 발생했다고 정리했다."),("친족","후견인","가족이 병원에 동행했다는 말만 했다고 말했다.","가족이 법정대리인으로 의료 결정을 대리한다고 정리했다.")],
}

def output(t,s,x):
 return {"summary":x,"case_type":t,"case_subtype":s,"urgency_level":"중","eligibility":"확인필요","extracted_json":{"당사자":[{"역할":"내담자","이름":"확인필요"}],"금액":None,"날짜":[{"항목":"상담일","값":"확인필요"}],"사건개요":x},"missing_info_json":["관련 문서: 확인필요"],"checklist_json":[{"항목":"문서 확인","결과":"확인필요"}],"timeline_json":[{"날짜":"확인필요","내용":"상담 내용 정리"}]}
def build_round(number):
 root=Path(f"data/{number+8:02d}_round{number}_diagnostic")
 if root.exists() and any(root.iterdir()): return
 for d in ('transcripts','ai_outputs','feedback_packets'): (root/d).mkdir(parents=True,exist_ok=True)
 catalog=[]
 for code in ('S','M','H'):
  for i in range(1,11):
   t,s,source,summary=SCENARIOS[code][(i+number)%3]; case=f"SYN-R{number}-{code}-{i:03d}"
   source=f"상담 {number}-{i}: {source}"; summary=f"상담 {number}-{i}: {summary}"
   (root/'transcripts'/f'{case}.txt').write_text(f"[합성 독립 전사 — {case}]\n상담자: 문서와 절차 상태를 말씀해 주세요.\n내담자: {source}\n상담자: 문서에 없는 권한과 효력은 확인 전 단정하지 않겠습니다.\n",encoding='utf-8')
   (root/'ai_outputs'/f'{case}.json').write_text(json.dumps({"case_id":case,"answer_generator":f"round{number}_diagnostic_generator_v1","ai_output":output(t,s,summary),"rag_results":[]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   packet={"case_id":case,"transcript_path":f"{root.as_posix()}/transcripts/{case}.txt","candidate_output_path":f"{root.as_posix()}/ai_outputs/{case}.json","reviewer_id":"","reviewer_decision":"","reviewer_reason":"","review_status":"pending_human_output_review","instruction":"Blind diagnostic review: read only transcript and candidate output. Do not inspect model outcomes or prior rounds."}
   (root/'feedback_packets'/f'{case}.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   catalog.append({"case_id":case,"difficulty":"easy_clear","case_type":t,"case_subtype":s,"transcript_path":f"transcripts/{case}.txt"})
 (root/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (root/'README.md').write_text(f"# Round {number} — 명확 문장 진단 검증 30건\n\n새 ID·새 전사·새 AI 출력으로 구성한 통제된 진단 라운드입니다. 사람/에이전트 검토자는 `feedback_packets`의 reviewer_id, reviewer_decision, reviewer_reason, review_status만 작성합니다. model 결과는 보지 않고 전사와 후보 출력만 비교합니다. 결과는 합성·명확 문장 진단 결과로만 해석합니다.\n",encoding='utf-8')
if __name__=='__main__':
 for r in range(23,31): build_round(r)
