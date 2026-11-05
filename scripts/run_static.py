"""Static preflight; never invent AgentDojo scores."""
import argparse
import json
from pathlib import Path
import yaml
from src.llm.client import Client, load_config
from src.eval.agentdojo_adapter import verify_defenses, AgentDojoUnavailable

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true")
    p.add_argument("--approve-over-200", action="store_true")
    args = p.parse_args()
    config = load_config()
    exp = yaml.safe_load(Path("config/experiment.yaml").read_text())
    lang = yaml.safe_load(Path("config/languages.yaml").read_text())
    valid_langs = [x["id"] for x in lang["languages"] if not x["id"].startswith("FILL_IN")]
    ndef = len(exp["defenses"])
    npair = exp["pairs"]
    nlang = len(valid_langs)
    # Conservative lower bound: per trial may require multiple model turns.
    lower = npair * ndef * nlang
    print(json.dumps({"mode":"mock" if args.mock else config["provider"],
                      "pairs":npair,"defenses":ndef,"languages":valid_langs,
                      "minimum_victim_calls":lower,
                      "note":"Actual AgentDojo agent loops can consume multiple victim calls; "
                             "translation, retry and attacker calls are additional."}, indent=2))
    if lower > 200 and not args.approve_over_200 and not args.mock:
        raise SystemExit("Run exceeds 200-request lower bound; use --approve-over-200 after explicit approval")
    if args.mock:
        response = Client(config={**config,"provider":"mock"}).chat("victim",[{"role":"user","content":"mock integration test"}])
        print("MOCK ONLY; no AgentDojo scores:",response["id"])
        return
    verify_defenses()
    raise SystemExit("Official task-pair discovery and execution not wired; no real run performed")

if __name__=="__main__":
    main()
