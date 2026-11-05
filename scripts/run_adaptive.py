"""Adaptive preflight and deterministic MOCK search (never report mock ASR)."""
import argparse
import json
from pathlib import Path
import yaml
from src.attack.search import run_search
from src.llm.client import Client, load_config
from src.eval.agentdojo_adapter import AgentDojoUnavailable, require_agentdojo

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true")
    p.add_argument("--approve-over-200", action="store_true")
    args=p.parse_args()
    config=load_config()
    exp=yaml.safe_load(Path("config/experiment.yaml").read_text())
    lang=yaml.safe_load(Path("config/languages.yaml").read_text())
    langs=[x["id"] for x in lang["languages"] if not x["id"].startswith("FILL_IN")]
    pairs=exp["pairs"]
    b=exp["adaptive_budget"]
    defenses=len(exp["defenses"])
    # Each proposal + evaluation is at least an attacker and a victim call.
    lower=pairs*b*defenses*2*2 # C3 and C4
    print(json.dumps({"pairs":pairs,"budget_per_pair":b,"defenses":defenses,
                      "adaptive_conditions":["C3","C4"],"minimum_model_calls":lower,
                      "breakdown":"pairs x B x defenses x 2 conditions x 2 role calls; "
                        "excludes AgentDojo additional victim turns, retries and translation"},indent=2))
    if args.mock:
        client=Client(config={**config,"provider":"mock"})
        def propose(initial, history, condition, languages):
            client.chat("attacker",[{"role":"user","content":initial+" "+str(len(history))}])
            return {"text":"MOCK_NOT_AN_ATTACK","language":"en","script":"Latn",
                    "code_mix_ratio":0,"strategy":"mock"}
        result=run_search(propose=propose,evaluate=lambda text: {"success":False,
                "visible_defense_output":"MOCK ONLY"},initial="placeholder",
                condition="C3",languages=["en"],budget=b,
                log_path=Path("data/runs/mock-adaptive.jsonl"))
        print(json.dumps({"label":"MOCK HARNESS ONLY / NOT ASR",
                          "attempts":result["attempts"],"first_success":result["first_success"]}))
        return
    if lower > 200 and not args.approve_over_200:
        raise SystemExit("Approval required: pass --approve-over-200 after reviewing call budget")
    require_agentdojo()
    raise SystemExit("Official AgentDojo adaptive feedback adapter not wired; no real run performed")

if __name__=="__main__":
    main()
