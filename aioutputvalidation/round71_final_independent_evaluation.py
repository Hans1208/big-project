"""Evaluate the completed final Round 71 independent review."""
import json
from pathlib import Path
import round69_large_independent_evaluation as shared

ROOT=Path(__file__).parent
shared.OUT=ROOT/"data"/"71_round71_final_independent_v3"
if __name__=="__main__":
    report=shared.evaluate()
    report.update({"round":71,"scope":"final_independent_30_per_tier"})
    (shared.OUT/"round71_final_independent_evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
