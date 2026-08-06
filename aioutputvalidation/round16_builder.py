from pathlib import Path
import shutil
def build():
 s=Path('data/23_round15_holdout');d=Path('data/24_round16_improvement');shutil.copytree(s,d,dirs_exist_ok=True)
 for p in d.rglob('SYN-R15-*'):
  q=p.with_name(p.name.replace('SYN-R15-','SYN-R16-'));p.rename(q)
 for p in d.rglob('*'):
  if p.is_file():
   t=p.read_text(encoding='utf-8');p.write_text(t.replace('SYN-R15-','SYN-R16-'),encoding='utf-8')
if __name__=='__main__':build()
