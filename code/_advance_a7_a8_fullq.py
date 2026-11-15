# -*- coding: utf-8 -*-
"""Advance A7/A8: pooled-sample bootstrap CI at every quasi-identifier level q=0..3, plus
   per-dataset delta table and leave-one-group-out across all q, to further strengthen the
   sample-robustness (A7) and single-city-dominance (A8) evidence.
   Standard library, fixed seeds, existing data only.

   v6.1: FIXED the q-step definitions. The earlier generic per-level lambda heuristic
   wrongly picked 'edu' for S1 at q=1 (paper S1 hierarchy is q=1=+industry), which tainted
   the pooled q=1 result. Now each dataset uses its own q-steps, identical to the v5
   _advance_a5_a7_a8.py definitions and to the main-text Table 1/2/3 hierarchies:
     S1: q0=(), q1=+industry, q2=+size, q3=+edu
     B1: q0=(), q1=+edu,     q2=+exp,  q3=+title
     B2: q0=(), q1=+etype,   q2=+eco,  q3=+track
"""
import sys, os, csv, math, random
from collections import Counter, defaultdict

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案"
OUT = os.path.join(BASE, "experiment_outputs")
sys.path.insert(0, BASE)
import S6_rr_statistics as S

def load_multicity_fixed(srcdir):
    ents = S.load_multicity(srcdir)
    for e in ents:
        if not e["city"] and "·" in e["district"]:
            parts = [x.strip() for x in e["district"].split("·") if x.strip()]
            if len(parts) >= 3:
                e["city"], e["district"], e["street"] = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                e["city"], e["district"] = parts[0], parts[1]
    return ents

def delta_of(ents, hier_fn, flat_fn):
    kh = [hier_fn(e) for e in ents]; kf = [flat_fn(e) for e in ents]
    ch = Counter(kh); cf = Counter(kf)
    rh = sum(1 for k in kh if ch[k] == 1) / len(ents) if ents else 0.0
    rf = sum(1 for k in kf if cf[k] == 1) / len(ents) if ents else 0.0
    return rh, rf, rh - rf

def pooled_bootstrap(datasets_meta, qstep, n_iter=3000, seed=42):
    """datasets_meta: list of (name, ents, hier_fn, flat_fn). qstep = (q, qid lambda).
       Pooled delta + per-dataset binomial bootstrap CI."""
    meta = []
    tot = 0
    qid = qstep[1]
    for name, ents, hf, ff in datasets_meta:
        kh = [hf(e) + tuple(qid(e)) for e in ents]
        kf = [ff(e) + tuple(qid(e)) for e in ents]
        ch = Counter(kh); cf = Counter(kf)
        fh = [1 if ch[k] == 1 else 0 for k in kh]
        fl = [1 if cf[k] == 1 else 0 for k in kf]
        ph = sum(fh) / len(fh); pf = sum(fl) / len(fl)
        meta.append((name, len(fh), ph, pf)); tot += len(fh)
    d0 = sum(nj * (ph - pf) for _, nj, ph, pf in meta) / tot
    rng = random.Random(seed); obs = []
    for _ in range(n_iter):
        dw = sum(nj * (random.binomialvariate(nj, ph) / nj - random.binomialvariate(nj, pf) / nj)
                 for _, nj, ph, pf in meta)
        obs.append(dw / tot)
    obs.sort()
    return meta, d0, obs[int(0.025 * n_iter)], obs[int(0.975 * n_iter)]

def main():
    s1 = S.load_shenzhen(S.S1_PATH) if os.path.exists(S.S1_PATH) else []
    b1 = load_multicity_fixed(S.B1_DIR)
    b2 = S.load_enterprise(S.B2_PATH) if os.path.exists(S.B2_PATH) else []
    # Per-dataset hier/flat keys and q-steps (identical to v5 script + main Table 1/2/3).
    ds = [
        ("S1_深圳", s1,
         lambda e: ("h", e["district"]), lambda e: ("f", e["district"], e["street"]),
         [(0, lambda e: ()), (1, lambda e: (e["industry"],)),
          (2, lambda e: (e["industry"], e["size"])), (3, lambda e: (e["industry"], e["size"], e["edu"]))]),
        ("B1_多市", b1,
         lambda e: ("h", e["city"], e["district"]), lambda e: ("f", e["city"], e["district"], e["street"]),
         [(0, lambda e: ()), (1, lambda e: (e["edu"],)),
          (2, lambda e: (e["edu"], e["exp"])), (3, lambda e: (e["edu"], e["exp"], e["title"]))]),
        ("B2_企业", b2,
         lambda e: ("h", e["prov"]), lambda e: ("f", e["city"]),
         [(0, lambda e: ()), (1, lambda e: (e["etype"],)),
          (2, lambda e: (e["etype"], e["eco"])), (3, lambda e: (e["etype"], e["eco"], e["track"]))]),
    ]
    rows = []
    for q in range(4):
        # Apply each dataset's OWN q-step (ds[i][4][q]) — matches v5 script + main Table 1/2/3.
        meta = []; tot = 0
        for name, ents, hf, ff, qsteps in ds:
            qid = qsteps[q][1]
            kh = [hf(e) + tuple(qid(e)) for e in ents]
            kf = [ff(e) + tuple(qid(e)) for e in ents]
            ch = Counter(kh); cf = Counter(kf)
            fh = [1 if ch[k] == 1 else 0 for k in kh]
            fl = [1 if cf[k] == 1 else 0 for k in kf]
            ph = sum(fh) / len(fh); pf = sum(fl) / len(fl)
            meta.append((name, len(fh), ph, pf)); tot += len(fh)
        d0 = sum(nj * (ph - pf) for _, nj, ph, pf in meta) / tot
        rng = random.Random(42); obs = []
        for _ in range(3000):
            dw = sum(nj * (random.binomialvariate(nj, ph) / nj - random.binomialvariate(nj, pf) / nj)
                     for _, nj, ph, pf in meta)
            obs.append(dw / tot)
        obs.sort()
        lo, hi = obs[int(0.025 * 3000)], obs[int(0.975 * 3000)]
        for name, nj, ph, pf in meta:
            rows.append({"q": q, "dataset": name, "n": nj, "rr_hier": round(ph, 4),
                         "rr_flat": round(pf, 4), "delta": round(ph - pf, 4),
                         "ci_lo": "", "ci_hi": ""})
        rows.append({"q": q, "dataset": "POOLED", "n": tot,
                     "rr_hier": round(sum(nj * ph for _, nj, ph, _ in meta) / tot, 4),
                     "rr_flat": round(sum(nj * pf for _, nj, _, pf in meta) / tot, 4),
                     "delta": round(d0, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})
        print("q=%d pooled delta=%.4f boot95=[%.4f, %.4f]" % (q, d0, lo, hi))

    # A8: leave-one-group-out at every q on B1 (complement), count order-kept
    b1q = ds[1][4]
    for q in range(4):
        qid = b1q[q][1]
        hf = ds[1][2]; ff = ds[1][3]
        hier_fn = lambda e, qid=qid: hf(e) + tuple(qid(e))
        flat_fn = lambda e, qid=qid: ff(e) + tuple(qid(e))
        groups = set(e["city"] for e in b1 if e["city"])
        if any(not e["city"] for e in b1):
            groups.add("__unparsed__")
        keep = 0; tot = 0
        for g in sorted(groups):
            if g == "__unparsed__":
                sub = [e for e in b1 if e["city"]]
            else:
                sub = [e for e in b1 if e["city"] != g]
            rh, rf, d = delta_of(sub, hier_fn, flat_fn)
            tot += 1; keep += 1 if d <= 0 else 0
        rows.append({"q": q, "dataset": "A8_leave_one_group", "n": tot,
                     "rr_hier": round(keep / tot, 4), "rr_flat": 0.0, "delta": 0.0,
                     "ci_lo": "", "ci_hi": "", "note": "keep%%=%d/%d" % (keep, tot)})
        print("A8 q=%d leave-one-group: %d/%d keep hier<=flat" % (q, keep, tot))

    p = os.path.join(OUT, "A7_A8_fullq.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["q", "dataset", "n", "rr_hier", "rr_flat", "delta", "ci_lo", "ci_hi", "note"])
        w.writeheader(); w.writerows(rows)
    print("WROTE", p, "(%d rows)" % len(rows))

if __name__ == "__main__":
    main()
