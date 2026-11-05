"""Refuse plots without attempt-level official data instead of drawing fake curves."""
from pathlib import Path

def main():
    if not Path("data/runs/official-attempts.jsonl").exists():
        raise SystemExit("No official attempt-level checker traces: cannot generate ASR-vs-budget plots")
    raise SystemExit("Plot integration pending official checked attempt-level schema; no plot produced")

if __name__=="__main__":
    main()
