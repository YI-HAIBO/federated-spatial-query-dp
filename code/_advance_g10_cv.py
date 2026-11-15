# -*- coding: utf-8 -*-
"""G10: leave-one-city (B1) and leave-one-province (B2) cross-validation.
   Reuses S6 RR/McNemar functions on the raw per-entity records. For each exclusion,
   recompute hierarchical vs flat re-identification risk and check the ordering holds.
"""
import os, csv, sys, io, math, random
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
from S6_rr_statistics import load_multicity, load_enterprise, rr_from_keys, flags_from_keys, mc_nemar_exact, keys_of, B1_DIR, B2_PATH

OUT = HERE  # evidence CSV alongside the others

def run_cv(ents, group_key, hier_region, flat_region, qid_steps, label, min_group=8):
    """Leave-one-group-out CV. Returns rows."""
    groups = defaultdict(list)
    for e in ents:
        groups[group_key(e)].append(e)
    groups = {g: v for g, v in groups.items() if len(v) >= min_group}
    rows = []
    # full (no exclusion) baseline
    def summarize(sub_ents):
        out = []
        for q, qid_fn in qid_steps:
            kh = keys_of(sub_ents, hier_region, qid_fn)
            kf = keys_of(sub_ents, flat_region, qid_fn)
            rh = rr_from_keys(kh); rf = rr_from_keys(kf)
            fh = flags_from_keys(kh); ff = flags_from_keys(kf)
            b, c, p = mc_nemar_exact(fh, ff)
            out.append({"q": q, "rh": rh, "rf": rf, "delta": rh - rf, "p": p})
        return out
    # full
    full = summarize(ents)
    for frow in full:
        rows.append({"scope": label, "excluded": "NONE", "q": frow["q"], "n": len(ents),
                     "rr_hier": round(frow["rh"], 4), "rr_flat": round(frow["rf"], 4),
                     "delta": round(frow["delta"], 4), "mc_p": round(frow["p"], 4),
                     "hier_le_flat": frow["delta"] <= 0, "sig": frow["p"] < 0.05})
    for g, sub in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        remain = [e for e in ents if group_key(e) != g]
        for frow in summarize(remain):
            rows.append({"scope": label, "excluded": g, "q": frow["q"], "n": len(remain),
                         "rr_hier": round(frow["rh"], 4), "rr_flat": round(frow["rf"], 4),
                         "delta": round(frow["delta"], 4), "mc_p": round(frow["p"], 4),
                         "hier_le_flat": frow["delta"] <= 0, "sig": frow["p"] < 0.05})
    return rows

def main():
    rows = []
    # ---------- B1: leave-one-city ----------
    b1 = load_multicity(B1_DIR)
    print("B1 entities:", len(b1))
    r1 = run_cv(b1,
        lambda e: e["city"],
        lambda e: ("h", e["city"], e["district"]),
        lambda e: ("f", e["city"], e["district"], e["street"]),
        [(0, lambda e: ()),
         (1, lambda e: (e["edu"],)),
         (2, lambda e: (e["edu"], e["exp"])),
         (3, lambda e: (e["edu"], e["exp"], e["title"]))],
        "B1_多市_留一城市", min_group=8)
    rows += r1
    print("  B1 CV rows:", len(r1))
    # ---------- B2: leave-one-province ----------
    if os.path.exists(B2_PATH):
        b2 = load_enterprise(B2_PATH)
        print("B2 entities:", len(b2))
        r2 = run_cv(b2,
            lambda e: e["prov"],
            lambda e: ("h", e["prov"]),
            lambda e: ("f", e["city"]),
            [(0, lambda e: ()),
             (1, lambda e: (e["etype"],)),
             (2, lambda e: (e["etype"], e["eco"])),
             (3, lambda e: (e["etype"], e["eco"], e["track"]))],
            "B2_企业_留一省", min_group=6)
        rows += r2
        print("  B2 CV rows:", len(r2))

    p = os.path.join(OUT, "G10_cross_validation.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WROTE", p, "| rows:", len(rows))

if __name__ == "__main__":
    main()
