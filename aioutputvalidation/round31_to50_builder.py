"""NOTE: despite the filename, this generates rounds 51-54 (range(51, 55) below),
not rounds 31-50 — the real round-31-to-50 diagnostic data already lives in
data/39_round31_diagnostic .. data/58_round50_diagnostic, produced some other way.
Nothing in this project imports or reads this module's output
(data/59_round51_diagnostic), so it is orphaned; round51_holdout_builder.py is the
script that actually feeds Round 51 (into data/59_round51_holdout instead). Kept
as-is rather than deleted or renamed since no downstream code depends on it either
way, but do not assume this is where Round 31-50 or Round 51 data comes from.
"""
from pathlib import Path
import json

T={
"S":("상속","상속재산분할","상속인 전원이 합의서에 서명했다고 말했다.","상속인 전원의 서명 합의서가 있다고 정리했다."),
"M":("가사소송","가사소송일반","조정안을 검토했지만 법원 확인은 받지 못했다고 말했다.","조정 합의 효력 여부는 법원 문서 확인이 필요하다고 정리했다."),
"H":("상속","상속재산분할","상속인들이 논의만 했고 합의서는 없다고 말했다.","상속재산 분할 합의가 확정되어 이행해야 한다고 정리했다.")}
def output(t,s,x):
 return {"summary":x,"case_type":t,"case_subtype":s,"urgency_level":"중","eligibility":"확인필요","extracted_json":{"당사자":[{"역할":"내담자","이름":"확인필요"}],"금액":None,"날짜":[{"항목":"상담일","값":"확인필요"}],"사건개요":x},"missing_info_json":["문서: 확인필요"],"checklist_json":[{"항목":"문서 확인","결과":"확인필요"}],"timeline_json":[{"날짜":"확인필요","내용":"상담 내용 정리"}]}
for r in range(51,55):
 root=Path(f"data/{r+8:02d}_round{r}_diagnostic")
 if root.exists() and any(root.iterdir()): continue
 for d in ('transcripts','ai_outputs','feedback_packets'): (root/d).mkdir(parents=True,exist_ok=True)
 catalog=[]
 for code in ('S','M','H'):
  for i in range(1,11):
   t,s,source,summary=T[code];cid=f"SYN-R{r}-{code}-{i:03d}";source=f"사례 {r}-{i}: {source}";summary=f"사례 {r}-{i}: {summary}"
   (root/'transcripts'/f'{cid}.txt').write_text(f"[합성 전사 — {cid}]\n상담자: 문서와 절차 상태를 말씀해 주세요.\n내담자: {source}\n상담자: 확인되지 않은 효력과 권한은 문서로 확인하겠습니다.\n",encoding='utf-8')
   (root/'ai_outputs'/f'{cid}.json').write_text(json.dumps({"case_id":cid,"answer_generator":f"round{r}_generator_v1","ai_output":output(t,s,summary),"rag_results":[]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   p={"case_id":cid,"transcript_path":f"{root.as_posix()}/transcripts/{cid}.txt","candidate_output_path":f"{root.as_posix()}/ai_outputs/{cid}.json","reviewer_id":"","reviewer_decision":"","reviewer_reason":"","review_status":"pending_human_output_review","instruction":"Blind review: compare only transcript and candidate output."}
   (root/'feedback_packets'/f'{cid}.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   catalog.append({"case_id":cid,"difficulty":"easy_clear","case_type":t,"case_subtype":s,"transcript_path":f"transcripts/{cid}.txt"})
 (root/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (root/'README.md').write_text(f"# Round {r} 진단 검증 30건\n\n새 ID·새 전사·새 AI 출력으로 구성된 블라인드 검토 패킷입니다.\n",encoding='utf-8')
