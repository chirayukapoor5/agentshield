"""Rate intervals and pair-level contrasts. No synthetic numeric results."""
import math
import random

def wilson(k, n, z=1.959963984540054):
    if not isinstance(k, int) or not isinstance(n, int) or n < 0 or not 0 <= k <= n:
        raise ValueError("require integers 0 <= successes <= n")
    if n == 0:
        return None
    p, zz = k / n, z*z
    d = 1 + zz/n
    ctr = (p + zz/(2*n))/d
    rad = z*math.sqrt(p*(1-p)/n + zz/(4*n*n))/d
    return max(0, ctr-rad), min(1, ctr+rad)

def rate(values):
    values = list(values)
    if any(type(x) is not bool for x in values):
        raise ValueError("rates require scored booleans only")
    k = sum(values)
    return {"successes": k, "n": len(values), "rate": k / len(values) if values else None, "ci95": wilson(k,len(values))}

def paired_bootstrap(rows, samples=2000, seed=20261105):
    """Rows: (scenario_family, english_success, multilingual_success).
    Resample scenario families (including all their repeated seeds) as clusters.
    """
    groups = {}
    for family, a, b in rows:
        if type(a) is not bool or type(b) is not bool:
            raise ValueError("scored boolean pairs required")
        groups.setdefault(family, []).append(int(b)-int(a))
    if not groups:
        return None
    keys = sorted(groups)
    estimate = sum(sum(v) for v in groups.values()) / sum(map(len,groups.values()))
    rng = random.Random(seed)
    diffs = []
    for _ in range(samples):
        chosen = [groups[rng.choice(keys)] for _ in keys]
        diffs.append(sum(map(sum, chosen))/sum(map(len,chosen)))
    diffs.sort()
    return {"difference_c4_minus_c3": estimate, "n_families":len(keys),
            "n_pairs":sum(map(len,groups.values())),
            "ci95": (diffs[int(.025*(samples-1))],diffs[int(.975*(samples-1))])}
