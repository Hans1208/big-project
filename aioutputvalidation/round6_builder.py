"""Create a fresh mixed batch with different explicit-conflict wording."""
from __future__ import annotations
import json, shutil
from pathlib import Path

def build(source: Path, destination: Path) -> None:
    catalog=json.loads((source/'catalog.json').read_text(encoding='utf-8')); (destination/'ai_outputs').mkdir(parents=True,exist_ok=True); (destination/'transcripts').mkdir(parents=True,exist_ok=True)
    new=[]
    for i,item in enumerate(catalog):
        old=item['case_id']; case_id=old.replace('SYN-R3-','SYN-R6-'); bundle=json.loads((source/'ai_outputs'/f'{old}.json').read_text(encoding='utf-8')); bundle['case_id']=case_id
        if i % 2 == 0:
            text='상대방은 2023-12-31에 법원 절차를 완료했고 손해액 12,345,678원을 이미 지급했다.'
            bundle['ai_output']['summary'] += ' '+text; bundle['ai_output']['timeline_json'].append({'날짜':'2023-12-31','내용':text})
        (destination/'ai_outputs'/f'{case_id}.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8'); shutil.copyfile(source/'transcripts'/f'{old}.txt',destination/'transcripts'/f'{case_id}.txt')
        new.append({**item,'case_id':case_id,'transcript_path':f'transcripts/{case_id}.txt'})
    (destination/'catalog.json').write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': build(Path('data/10_round3'),Path('data/13_round6_independent')); print('Created 30 independent mixed outputs')
