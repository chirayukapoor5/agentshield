"""Opt-in translator; requires real provider, network call budget and approved input."""
import argparse
import json
from pathlib import Path
from src.llm.client import Client
from src.translate.generate import translate_batch

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True,help="JSON list of {id,text} source records")
    parser.add_argument("--language",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--approve-over-200",action="store_true")
    args=parser.parse_args()
    rows=json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(rows,list) or any(not isinstance(row,dict) or not all(k in row for k in ("id","text")) for row in rows):
        raise SystemExit("input must be list of {id,text}")
    estimated=len(rows)*2
    print(json.dumps({"items":len(rows),"estimated_translation_and_backtranslation_calls":estimated,
                      "additional_retries_possible":True},indent=2))
    if estimated>200 and not args.approve_over_200:
        raise SystemExit("approval required for >200 requests")
    client=Client()
    count=translate_batch(client,rows,args.language,args.output)
    print("Saved unvalidated translations:",count,args.output)

if __name__=="__main__":
    main()
