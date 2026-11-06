"""Run C1 official AgentDojo checks; C2 requires translations and separate approval.

By default prints call budget and exits in mock mode without scoring.
"""
import argparse
import json
from pathlib import Path
import yaml
from src.llm.client import Client, load_config
from src.eval.agentdojo_adapter import verify_defenses, load_workspace
from src.eval.build_pipeline import build_pipeline
from src.eval.trials import run_english_static_pair, append_trial

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true")
    p.add_argument("--condition", choices=["C1"], default="C1")
    p.add_argument("--split", choices=["dev", "tune", "test"], default="dev")
    p.add_argument("--permit-heldout-test", action="store_true")
    p.add_argument("--defense", choices=["none","tool_filter","repeat_user_prompt"],
                   default="none")
    p.add_argument("--pairs-manifest", default="data/runs/workspace-pairs.json")
    p.add_argument("--output", default="data/runs/official-C1.jsonl")
    p.add_argument("--approve-over-200", action="store_true")
    args = p.parse_args()
    config = load_config()
    exp = yaml.safe_load(Path("config/experiment.yaml").read_text())
    lang = yaml.safe_load(Path("config/languages.yaml").read_text())
    valid_langs=[x["id"] for x in lang["languages"] if not x["id"].startswith("FILL_IN")]
    npair=exp["pairs"]
    ndef=len(exp["defenses"])
    lower=npair*ndef*len(valid_langs)
    budget={"condition":args.condition,"pairs":npair,"defenses":ndef,
            "configured_languages":valid_langs,"lower_bound_victim_calls_all_static":lower,
            "this_command_minimum_calls":npair,
            "warning":"AgentDojo may require many model turns per pair; retries, tool filtering "
                      "and translations are additional billable calls. Hard ledger caps are binding."}
    print(json.dumps(budget,indent=2))
    if args.mock or config["provider"]=="mock":
        response=Client(config={**config,"provider":"mock"}).chat(
            "victim",[{"role":"user","content":"mock-only dry run"}])
        print("MOCK DIAGNOSTIC; NO BENCHMARK ASR:",response["id"])
        return
    if args.split == "test" and not args.permit_heldout_test:
        raise SystemExit("Held-out test is locked; use --permit-heldout-test only after model, prompts and settings are frozen")
    if lower > 200 and not args.approve_over_200:
        raise SystemExit("Approval required: --approve-over-200")
    verify_defenses()
    if not Path(args.pairs_manifest).exists():
        raise SystemExit("Missing selected pair manifest: run scripts/select_pairs.py first")
    manifest=json.loads(Path(args.pairs_manifest).read_text(encoding="utf-8"))
    if manifest.get("suite")!="workspace":
        raise SystemExit("Only the workspace suite is preregistered")
    suite=load_workspace()
    client=Client(config)
    pipeline=build_pipeline(client,args.defense)
    completed=0
    from agentdojo.attacks.baseline_attacks import DirectAttack
    attack=DirectAttack(suite,pipeline)
    for pair in manifest["pairs"]:
        if pair.get("split") != args.split:
            continue
        record=run_english_static_pair(suite,pipeline,pair,attack=attack,
                   victim_model_id=client.models["victim"],
                   attacker_model_id=client.models["attacker"],
                   translator_model_id=client.models["translator"],
                   seed=exp["sample_seed"],defense_id=args.defense,
                   api_parameters=config["request"])
        completed+=int(append_trial(args.output,record))
    print(json.dumps({"new_trials":completed,"split":args.split,"output":args.output,
                      "ledger":client.usage(),"status":"official_checker_records_not_independently_audited"},indent=2))

if __name__=="__main__":
    main()
