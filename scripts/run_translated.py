"""Run officially checked C2 injections, never auto-translate or score mock labels.

Only explicitly approved, validated translations can enter the held-out model.
No API call happens before all required translations have been checked.
Default split is dev; test split requires an explicit separate flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.eval.agentdojo_adapter import load_workspace, verify_defenses
from src.eval.build_pipeline import build_pipeline
from src.eval.translated_trials import (
    run_translated_pair, scenario_id, select_verified_translation,
)
from src.eval.trials import append_trial
from src.llm.client import Client, load_config
from src.translate.store import load_translations


def prepare_cases(pairs, translations, *, split, language, reference_payload):
    """Resolve all inputs before any target-model evaluation begins.

    reference_payload(pair) provides the exact C1 English injection; caller
    must freeze it and review the translation source hash. This method can
    call an attack-template generator, so count its costs separately.
    """
    if split not in {"dev", "tune", "test"}:
        raise ValueError("invalid split")
    if not isinstance(translations, dict) or "items" not in translations:
        raise ValueError("missing translation records")
    index = {}
    for item in translations["items"]:
        if not isinstance(item, dict):
            raise ValueError("translation must be object")
        key = (item.get("scenario_id"), item.get("lang"))
        if key in index:
            raise ValueError("duplicate translation for scenario and language")
        index[key] = item
    prepared = []
    for pair in pairs:
        if pair.get("split") != split:
            continue
        sid = scenario_id(pair)
        item = index.get((sid, language))
        if item is None:
            raise ValueError("missing translation: " + sid + "/" + language)
        source = reference_payload(pair)
        select_verified_translation(item, scenario=sid, language=language,
                                    english_payload=source)
        prepared.append((pair, source, item))
    if not prepared:
        raise ValueError("no scenario pairs for requested split")
    return prepared


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs-manifest", default="data/runs/workspace-pairs.json")
    p.add_argument("--translations", required=True)
    p.add_argument("--language", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--split", choices=("dev", "tune", "test"), default="dev")
    p.add_argument("--defense", choices=("none", "tool_filter", "repeat_user_prompt"),
                   default="none")
    p.add_argument("--output", default="data/runs/official-C2.jsonl")
    p.add_argument("--permit-heldout-test", action="store_true")
    p.add_argument("--i-understand-this-makes-real-calls", action="store_true")
    args = p.parse_args()
    if not args.i_understand_this_makes_real_calls:
        p.error("real model calls require an explicit opt-in")
    if args.split == "test" and not args.permit_heldout_test:
        p.error("held-out split is locked until protocol and choices are frozen")
    manifest = json.loads(Path(args.pairs_manifest).read_text(encoding="utf-8"))
    if manifest.get("suite") != "workspace" or not isinstance(manifest.get("pairs"), list):
        p.error("workspace scenario manifest required")
    translations = load_translations(args.translations)
    if args.language == "en":
        p.error("C2 requires a non-English language")
    config = load_config()
    if config.get("provider") == "mock":
        p.error("mock mode is not eligible for official C2 results")
    verify_defenses()
    suite = load_workspace()
    client = Client(config)
    pipeline = build_pipeline(client, args.defense)
    from agentdojo.attacks.baseline_attacks import DirectAttack
    attack = DirectAttack(suite, pipeline)

    def english_payload(pair):
        user = suite.get_user_task_by_id(pair["user_task_id"])
        injection = suite.get_injection_task_by_id(pair["injection_task_id"])
        payloads = attack.attack(user, injection)
        slot = pair["injection_slot"]
        if slot not in payloads or not isinstance(payloads[slot], str):
            raise ValueError("missing exact C1 reference payload")
        return payloads[slot]

    # Resolve *all* sources and human-validated translations before executing
    # any evaluated defender trial. This is critical for selection integrity.
    cases = prepare_cases(manifest["pairs"], translations, split=args.split,
                          language=args.language,
                          reference_payload=english_payload)
    completed = 0
    for pair, source, item in cases:
        trial = run_translated_pair(
            suite, pipeline, pair, english_payload=source, translation=item,
            language=args.language, script=args.script,
            victim_model_id=client.models["victim"],
            defense_id=args.defense, seed=manifest["seed"])
        completed += int(append_trial(args.output, trial))
    print(json.dumps({
        "condition": "C2", "language": args.language, "split": args.split,
        "selected": len(cases), "new_trials": completed, "output": args.output,
        "status": "official_checker_records_not_independently_audited",
        "ledger": client.usage(),
    }, indent=2))


if __name__ == "__main__":
    main()
