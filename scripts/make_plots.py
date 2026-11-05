"""Plot empirical ASR-versus-budget only from official AgentDojo checker records.

Input JSONL: each attempt has trial_id, condition, defense_id, language,
attempt (1-based), success (official checker bool), validated_by_me (bool),
checker='agentdojo.TaskSuite.run_task_with_pipeline'. One trial may contain
many attempt records; an attempt curve counts each trial as a single unit.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

def load_attempts(path):
    groups=defaultdict(list)
    for line_number,line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            raise ValueError(f"blank line {line_number}")
        row=json.loads(line)
        required={"trial_id","condition","defense_id","language","attempt",
                  "success","validated_by_me","checker"}
        if not required.issubset(row):
            raise ValueError(f"line {line_number}: missing required fields")
        if row["checker"]!="agentdojo.TaskSuite.run_task_with_pipeline":
            raise ValueError("rejecting non-AgentDojo evaluator rows")
        if row["condition"] not in ("C3","C4"):
            raise ValueError("budget curves require adaptive C3/C4 attempts")
        if type(row["success"]) is not bool or type(row["attempt"]) is not int or row["attempt"] < 1:
            raise ValueError("invalid attempt or official success outcome")
        if type(row["validated_by_me"]) is not bool:
            raise ValueError("translation validation status must be boolean")
        key=(row["condition"],row["defense_id"],row["language"],row["trial_id"])
        groups[key].append(row)
    for key,rows in groups.items():
        attempts=sorted(r["attempt"] for r in rows)
        if attempts!=list(range(1,len(rows)+1)):
            raise ValueError(f"trial {key}: duplicate/missing attempt numbers")
    return groups

def curves(groups):
    by_cell=defaultdict(list)
    for (condition,defense,language,trial),rows in groups.items():
        ordered=sorted(rows,key=lambda x:x["attempt"])
        validation="validated" if all(r["validated_by_me"] for r in ordered) else "unvalidated"
        first=next((r["attempt"] for r in ordered if r["success"]),None)
        by_cell[(condition,defense,language,validation)].append((first,len(ordered)))
    result={}
    for key, trials in sorted(by_cell.items()):
        largest=max(total for _,total in trials)
        result[key]=[]
        for budget in range(1,largest+1):
            # Correct censoring: denominator includes only trials observed at budget B.
            at_risk=[first for first,total in trials if total>=budget or (first is not None and first<=budget)]
            if not at_risk:
                continue
            hits=sum(first is not None and first<=budget for first in at_risk)
            result[key].append((budget,hits/len(at_risk),hits,len(at_risk)))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="data/runs/official-attempts.jsonl")
    p.add_argument("--output-dir",default="results/figures")
    args=p.parse_args()
    if not Path(args.input).exists():
        raise SystemExit("Missing official checked attempt records; no plots created")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    data=curves(load_attempts(args.input))
    out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    for defense in sorted({key[1] for key in data}):
        fig,ax=plt.subplots(figsize=(8,5))
        for (condition,d,language,status),points in data.items():
            if d!=defense:
                continue
            ax.plot([x[0] for x in points],[x[1] for x in points],
                    marker="o",label=f"{condition} / {language} ({status})")
        ax.set(xlabel="Attacker evaluation budget",ylabel="Observed success rate",
               ylim=(0,1),title="AgentDojo attack success versus budget — "+defense)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out/("budget_"+defense+".png"),dpi=160)
        plt.close(fig)
    print("Saved",len({key[1] for key in data}),"defense figures to",out)

if __name__=="__main__":
    main()
