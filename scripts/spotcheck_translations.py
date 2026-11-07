"""Interactive translation audit; native checks are intentionally user-supplied."""
import argparse
from pathlib import Path
from src.translate.store import load_translations, spotcheck, write_translations

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("path",nargs="?",default="data/translations/example.v1.json")
    parser.add_argument("--seed",type=int,default=20261105)
    parser.add_argument("--count",type=int,default=20)
    args=parser.parse_args()
    data=load_translations(args.path)
    for item in spotcheck(data,args.count,args.seed):
        print("\nID:",item["id"],"LANG:",item["lang"])
        print("TRANSLATION:",item["text"])
        print("BACK:",item["back_translation"])
        verdict=input("Validated by you? [y/n/skip] ").strip().lower()
        if verdict=="y":
            item["validated_by_me"]=True
            item["needs_native_check"]=False
        elif verdict=="n":
            item["validated_by_me"]=False
            item["needs_native_check"]=True
        write_translations(args.path,data)
    print("Saved",args.path)

if __name__=="__main__":
    main()
