"""Reproduce descriptive tables from official (not mock) JSONL records."""
import argparse
import csv
import json
from pathlib import Path
from research.validate_results import summarize

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="data/runs/official-results.jsonl")
    p.add_argument("--output",default="results/tables/outcomes.csv")
    args=p.parse_args()
    if not Path(args.input).exists():
        raise SystemExit("No official result file; cannot produce an ASR table")
    report=summarize(Path(args.input))
    if any("mock" in row["outcomes"] for row in report["groups"]):
        raise SystemExit("mock outputs are not official AgentDojo results")
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    fields=["split","condition","language","total","scored","successes",
            "success_rate_scored_only","wilson_95_scored_only","outcomes"]
    with out.open("w",newline="",encoding="utf-8") as fh:
        writer=csv.DictWriter(fh,fieldnames=fields)
        writer.writeheader()
        for row in report["groups"]:
            writer.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v
                             for k,v in row.items()})
    print(out)

if __name__=="__main__":
    main()
