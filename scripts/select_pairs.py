"""Generate a real AgentDojo pair manifest without model/API calls."""
import argparse
import json
from src.eval.sample import sample_pairs,write_manifest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--count",type=int,default=30)
    parser.add_argument("--seed",type=int,default=20261105)
    parser.add_argument("--output",default="data/runs/workspace-pairs.json")
    args=parser.parse_args()
    manifest=sample_pairs(count=args.count,seed=args.seed)
    digest=write_manifest(args.output,manifest)
    print(json.dumps({"path":args.output,"sha256":digest,"selected":len(manifest["pairs"]),
                      "excluded":len(manifest["excluded_noninjectable_user_tasks"])},indent=2))

if __name__=="__main__":
    main()
