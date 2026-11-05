import json
from pathlib import Path
import tempfile
import pytest
from scripts.make_plots import load_attempts, curves

CHECK="agentdojo.TaskSuite.run_task_with_pipeline"

def row(trial,attempt,success):
    return {"trial_id":trial,"condition":"C3","defense_id":"none",
            "language":"en","attempt":attempt,"success":success,
            "validated_by_me":True,"checker":CHECK}

def test_curves_deduplicate_success_per_trial():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"attempts.jsonl"
        rows=[row("a",1,False),row("a",2,True),
              row("b",1,False),row("b",2,False)]
        path.write_text("".join(json.dumps(x)+"\n" for x in rows))
        series=next(iter(curves(load_attempts(path)).values()))
        assert series[0][2:]==(0,2)
        assert series[1][2:]==(1,2)

def test_reject_unofficial_checker():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/"attempts.jsonl"
        x=row("a",1,True)
        x["checker"]="mock"
        path.write_text(json.dumps(x)+"\n")
        with pytest.raises(ValueError,match="non-AgentDojo"):
            load_attempts(path)
