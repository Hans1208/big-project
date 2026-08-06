from __future__ import annotations
import json,shutil
from pathlib import Path
def build(s,d):
 c=json.loads((s/'catalog.json').read_text(encoding='utf-8'));(d/'ai_outputs').mkdir(parents=True,exist_ok=True);(d/'transcripts').mkdir(parents=True,exist_ok=True);n=[]
 for i,x in enumerate(c):
  old=x['case_id'];cid=old.replace('SYN-R3-','SYN-R15-');b=json.loads((s/'ai_outputs'/f'{old}.json').read_text(encoding='utf-8'));b['case_id']=cid
  if i%2:b['ai_output']['summary']+=' 상대방의 보호자가 내담자를 대리해 조정 조서를 확정했다.'
  (d/'ai_outputs'/f'{cid}.json').write_text(json.dumps(b,ensure_ascii=False,indent=2),encoding='utf-8');shutil.copyfile(s/'transcripts'/f'{old}.txt',d/'transcripts'/f'{cid}.txt');n.append({**x,'case_id':cid,'transcript_path':f'transcripts/{cid}.txt'})
 (d/'catalog.json').write_text(json.dumps(n,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':build(Path('data/10_round3'),Path('data/23_round15_holdout'))
