"""Opt-in ONLY. Never run from setup/test/dry-run.

Real provider check: query /models then make 20 minimal chat calls, log 429s,
time and request consumption; cannot infer true hard provider limit from 20 calls.
"""
import argparse
import json
import os
import time
import urllib.request
from src.llm.client import Client, load_config

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--i-understand-this-makes-real-calls",action="store_true")
    args=parser.parse_args()
    if not args.i_understand_this_makes_real_calls:
        raise SystemExit("Refusing API smoke test without explicit CLI opt-in")
    cfg=load_config()
    if cfg["provider"]=="mock":
        raise SystemExit("Set a real provider and hard caps before smoke test")
    client=Client(cfg)
    key=os.environ[cfg.get("api_key_env","API_KEY")]
    req=urllib.request.Request(cfg["base_url"].rstrip("/")+"/models",
                               headers={"Authorization":"Bearer "+key})
    with urllib.request.urlopen(req,timeout=cfg["request"].get("timeout_s",60)) as r:
        models=json.loads(r.read())
    print("Accessible model IDs:",[x.get("id") for x in models.get("data",[])])
    start=time.monotonic()
    succeeded=0
    errors=[]
    for i in range(20):
        try:
            client.chat("victim",[{"role":"user","content":"Reply OK. Test "+str(i)}],
                        max_tokens=8)
            succeeded+=1
        except Exception as exc:
            errors.append({"iteration":i,"error_type":type(exc).__name__,
                           "status":getattr(exc,"code",None)})
    print(json.dumps({"successful":succeeded,"failures":errors,
         "elapsed_s":time.monotonic()-start,"ledger":client.usage(),
         "recommendation":"Choose conservative caps below observed successful pace; "
                          "20 calls cannot establish provider-wide RPM/TPM ceilings."},indent=2))

if __name__=="__main__":
    main()
