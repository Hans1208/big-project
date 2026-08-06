"""Evaluate completed Round 70 authority-ambiguity calibration reviews."""
import json
from pathlib import Path
from observation_builder import build_observation, e5_embedders
from output_validation_runner import load_runtime_manifest, validate_observation

ROOT=Path(__file__).parent; OUT=ROOT/"data"/"70_round70_authority_calibration"
def evaluate():
    packets=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT/"output_review_packets").glob("SYN-*.json"))]
    if any(p.get("review_status") not in {"completed","reviewed","completed_human_output_review","human_output_review_complete"} or p.get("reviewer_decision") not in {"safe","review_required","high_risk"} for p in packets): raise ValueError("incomplete output review")
    manifest=load_runtime_manifest(ROOT/"models"/"active"/"manifest.json"); model=json.loads((ROOT/manifest["model_path"]).read_text(encoding="utf-8")); q,e=e5_embedders("intfloat/multilingual-e5-small")
    results=[]; (OUT/"validation_results").mkdir(exist_ok=True)
    for path in sorted((OUT/"ai_outputs").glob("SYN-*.json")):
        bundle=json.loads(path.read_text(encoding="utf-8")); transcript=(OUT/"transcripts"/f"{bundle['case_id']}.txt").read_text(encoding="utf-8"); result=validate_observation(build_observation(bundle,transcript,q,e),model,float(manifest["decision_threshold"]),manifest["active_model_version"]); results.append(result); (OUT/"validation_results"/path.name).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    human={p["case_id"]:p["reviewer_decision"] for p in packets}; exact=sum(r["decision"]==human[r["case_id"]] for r in results); review=sum(r["decision"]=="review_required" for r in results)
    report={"round":70,"scope":"authority_ambiguity_calibration","reviewed_outputs":len(results),"exact_decision_agreement":round(exact/len(results),4),"review_required_predictions":review,"decisions":{r["case_id"]:r["decision"] for r in results}}
    (OUT/"round70_authority_calibration_evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); return report
if __name__=="__main__": print(json.dumps(evaluate(),ensure_ascii=False,indent=2))
