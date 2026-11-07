"""Versioned translation records; unvalidated examples stay visibly marked."""
import json
import random
from pathlib import Path

REQUIRED = {"id", "lang", "text", "provenance", "back_translation",
            "back_translation_similarity", "needs_native_check", "validated_by_me"}

def load_translations(path):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or "version" not in obj or not isinstance(obj.get("items"), list):
        raise ValueError("expected versioned JSON object with items list")
    seen = set()
    for item in obj["items"]:
        if not isinstance(item, dict) or not REQUIRED.issubset(item):
            raise ValueError("translation missing required fields")
        if item["id"] in seen:
            raise ValueError("duplicate translation id")
        seen.add(item["id"])
        if item["provenance"] not in ("machine", "human"):
            raise ValueError("invalid provenance")
        if type(item["validated_by_me"]) is not bool or type(item["needs_native_check"]) is not bool:
            raise ValueError("validation flags must be booleans")
        score = item["back_translation_similarity"]
        if score is not None and (type(score) not in (int, float) or not 0 <= score <= 1):
            raise ValueError("similarity must be null or within [0, 1]")
    return obj

def write_translations(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)

def spotcheck(data, number=20, seed=20261105):
    rng = random.Random(seed)
    return rng.sample(data["items"], min(number, len(data["items"])))
