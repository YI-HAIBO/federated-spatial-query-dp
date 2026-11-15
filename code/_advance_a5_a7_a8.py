# -*- coding: utf-8 -*-
"""Advance A5 / A7 / A8 with real-data empirical evidence (all existing data, no new collection).

A5  (adversary knows <= q quasi-identifiers): quantify how the hier-vs-flat risk gap and the
    e^eps/(c-1+e^eps) re-identification bound depend on data distinctness (equivalence-class size c).
A7  (small sample): entity-level pooled bootstrap CI on the pooled Delta + per-dataset/per-city counts.
A8  (single-city-dominated calibration): per-city entity share + leave-one-group-out + explicit
    leave-Shenzhen-out recalibration.
Output: experiment_outputs/A5_A7_A8_advancement.csv
"""
import sys, os, csv, math, random
from collections import Counter, defaultdict

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案"
OUT = os.path.join(BASE, "experiment_outputs")
sys.path.insert(0, BASE)
import S6_rr_statistics as S

EPS = 1.0  # epsilon used in the paper's main experiments

def load_multicity_fixed(srcdir):
    """Load multi-city but recover city/district/street when city parsing failed and the
    district field actually holds a 'city·district·street' concatenation."""
    ents = S.load_multicity(srcdir)
    fixed = 0
    for e in ents:
        if not e["city"] and "·" in e["district"]:
            parts = [x.strip() for x in e["district"].split("·") if x.strip()]
            if len(parts) >= 3:
                e["city"], e["district"], e["street"] = parts[0], parts[1], parts[2]
                fixed += 1
            elif len(parts) == 2:
                e["city"], e["district"] = parts[0], parts[1]
                fixed += 1
    return ents, fixed

def rr_and_classsize(ents, keyfn):
    """Return (rr, per-entity flat-class-size list)."""
    ks = [keyfn(e) for e in ents]
    cnt = Counter(ks)
    rr = sum(1 for k in ks if cnt[k] == 1) / len(ks) if ks else 0.0
    class_sizes = [cnt[k] for k in ks]
    return rr, class_sizes

def delta_of(ents, hier_fn, flat_fn):
    kh = [hier_fn(e) for e in ents]; kf = [flat_fn(e) for e in ents]
    ch = Counter(kh); cf = Counter(kf)
    rh = sum(1 for k in kh if ch[k] == 1) / len(ents) if ents else 0.0
    rf = sum(1 for k in kf if cf[k] == 1) / len(ents) if ents else 0.0
    return rh, rf, rh - rf

def bound_e_eps_c(c, eps=EPS):
    """e^eps/(c-1+e^eps): probability of correct identification of an entity in a class of size c."""
    e = math.exp(eps)
    return e / (c - 1 + e)

def main():
    rows = []

    # ---------- load + fix ----------
    s1 = S.load_shenzhen(S.S1_PATH) if os.path.exists(S.S1_PATH) else []
    b1, fixed = load_multicity_fixed(S.B1_DIR)
    b2 = S.load_enterprise(S.B2_PATH) if os.path.exists(S.B2_PATH) else []
    print("entities: S1=%d B1=%d (fixed-city +%d) B2=%d" % (len(s1), len(b1), fixed, len(b2)))

    # ---------- A5: sensitivity vs distinctness ----------
    # (a) per-dataset RR-q profile and flat-class-size at each q
    datasets = [
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
    profiles = {}
    for name, ents, hf, ff, qsteps in datasets:
        prof = []
        for q, qid in qsteps:
            hier_fn = lambda e, hf=hf, qid=qid: hf(e) + tuple(qid(e))
            flat_fn = lambda e, ff=ff, qid=qid: ff(e) + tuple(qid(e))
            rh, rf, d = delta_of(ents, hier_fn, flat_fn)
            _, css = rr_and_classsize(ents, flat_fn)
            mean_c = sum(css) / len(css) if css else 0.0
            prof.append({"q": q, "rr_hier": rh, "rr_flat": rf, "delta": d, "mean_c": mean_c})
        profiles[name] = prof
        for p in prof:
            rows.append({"block": "A5_profile", "dataset": name, "group": "", "q": p["q"],
                         "n": len(ents), "rr_hier": round(p["rr_hier"], 4),
                         "rr_flat": round(p["rr_flat"], 4), "delta": round(p["delta"], 4),
                         "mean_class_size": round(p["mean_c"], 3),
                         "risk_bound_e1_c": round(bound_e_eps_c(max(1, round(p["mean_c"]))), 4)})

    # (b) RR-q slope (sensitivity) vs baseline distinctness
    for name, prof in profiles.items():
        if len(prof) >= 2:
            slope = (prof[-1]["rr_hier"] - prof[0]["rr_hier"]) / (prof[-1]["q"] - prof[0]["q"])
            rows.append({"block": "A5_slope", "dataset": name, "group": "",
                         "q": prof[-1]["q"], "n": 0,
                         "rr_hier": round(slope, 4), "rr_flat": 0.0, "delta": 0.0,
                         "mean_class_size": round(prof[0]["mean_c"], 3),
                         "risk_bound_e1_c": round(bound_e_eps_c(max(1, round(prof[0]["mean_c"]))), 4)})

    # (c) class-size stratified delta on B1 (largest dataset)
    flat_key = lambda e: (e["city"], e["district"], e["street"])
    hier_key = lambda e: (e["city"], e["district"])
    cnt = Counter(flat_key(e) for e in b1)
    buckets = [(1, 1, "c==1"), (2, 3, "c=2-3"), (4, 9, "c=4-9"), (10, 49, "c=10-49"), (50, 10 ** 9, "c>=50")]
    for lo, hi, label in buckets:
        sub = [e for e in b1 if lo <= cnt[flat_key(e)] <= hi]
        if not sub:
            continue
        rh, rf, d = delta_of(sub, hier_key, flat_key)
        c_mid = (lo + hi) / 2 if lo < 10 ** 9 else 50
        rows.append({"block": "A5_strata", "dataset": "B1_多市", "group": label,
                     "q": -1, "n": len(sub), "rr_hier": round(rh, 4), "rr_flat": round(rf, 4),
                     "delta": round(d, 4), "mean_class_size": round(c_mid, 2),
                     "risk_bound_e1_c": round(bound_e_eps_c(round(c_mid)), 4)})

    # ---------- A7: pooled bootstrap CI on Delta (fixed: per-dataset Binomial resampling) ----------
    # For each dataset at q=2, compute hier/flat 0/1 unique flags, then per-dataset
    # proportion; pooled delta = weighted mean. Bootstrap draws ones ~ Binomial(n_j, p_j)
    # per dataset (the S6-documented fix: resampling flags as a proportion, NOT keys, so
    # singletons are never 'merged' by with-replacement key resampling).
    pool_meta = []
    for name, ents, hf, ff, qsteps in datasets:
        qid2 = qsteps[2][1]
        kh = [hf(e) + tuple(qid2(e)) for e in ents]
        kf = [ff(e) + tuple(qid2(e)) for e in ents]
        ch = Counter(kh); cf = Counter(kf)
        fh = [1 if ch[k] == 1 else 0 for k in kh]
        fl = [1 if cf[k] == 1 else 0 for k in kf]
        pool_meta.append((name, len(ents), sum(fh) / len(ents), sum(fl) / len(ents)))
    tot = sum(nj for _, nj, _, _ in pool_meta)
    wsum0 = sum(nj * (ph - pf) for _, nj, ph, pf in pool_meta)
    d0 = wsum0 / tot
    rng = random.Random(42)
    obs = []
    for _ in range(3000):
        dw = 0.0
        for name, nj, ph, pf in pool_meta:
            oh = random.binomialvariate(nj, ph) / nj
            of = random.binomialvariate(nj, pf) / nj
            dw += nj * (oh - of)
        obs.append(dw / tot)
    obs.sort()
    lo, hi = obs[int(0.025 * len(obs))], obs[int(0.975 * len(obs))]
    print("A7 pooled q=2: n=%d delta=%.4f boot95=[%.4f, %.4f]" % (tot, d0, lo, hi))
    for name, nj, ph, pf in pool_meta:
        rows.append({"block": "A7_pooled", "dataset": name, "group": "q=2",
                     "q": 2, "n": nj, "rr_hier": round(ph, 4), "rr_flat": round(pf, 4),
                     "delta": round(ph - pf, 4), "mean_class_size": 0.0,
                     "risk_bound_e1_c": round(ph - pf, 4)})
    rows.append({"block": "A7_pooled", "dataset": "S1+B1+B2", "group": "q=2",
                 "q": 2, "n": tot, "rr_hier": round(sum(nj * ph for _, nj, ph, _ in pool_meta) / tot, 4),
                 "rr_flat": round(sum(nj * pf for _, nj, _, pf in pool_meta) / tot, 4),
                 "delta": round(d0, 4), "mean_class_size": 0.0, "risk_bound_e1_c": round(d0, 4)})
    rows.append({"block": "A7_pooled_ci", "dataset": "S1+B1+B2", "group": "boot95_lo",
                 "q": 2, "n": tot, "rr_hier": 0.0, "rr_flat": 0.0, "delta": 0.0,
                 "mean_class_size": 0.0, "risk_bound_e1_c": round(lo, 4)})
    rows.append({"block": "A7_pooled_ci", "dataset": "S1+B1+B2", "group": "boot95_hi",
                 "q": 2, "n": tot, "rr_hier": 0.0, "rr_flat": 0.0, "delta": 0.0,
                 "mean_class_size": 0.0, "risk_bound_e1_c": round(hi, 4)})

    # per-dataset / per-city counts
    city_counts = Counter(e["city"] for e in b1)
    for c, cc in sorted(city_counts.items(), key=lambda kv: -kv[1]):
        rows.append({"block": "A8_city_count", "dataset": "B1_多市", "group": c,
                     "q": -1, "n": cc, "rr_hier": 0.0, "rr_flat": 0.0, "delta": 0.0,
                     "mean_class_size": 0.0, "risk_bound_e1_c": 0.0})

    # ---------- A8: leave-one-group-out at q=2 (complement of the excluded group) ----------
    qid2 = datasets[1][4][2][1]
    hf = datasets[1][2]; ff = datasets[1][3]
    hier_key = lambda e, qid=qid2: hf(e) + tuple(qid(e))
    flat_key = lambda e, qid=qid2: ff(e) + tuple(qid(e))
    groups = set(e["city"] for e in b1 if e["city"])
    if any(not e["city"] for e in b1):
        groups.add("__unparsed__")
    keep = 0; tot = 0
    for g in sorted(groups):
        if g == "__unparsed__":
            sub = [e for e in b1 if e["city"]]        # complement: drop unparsed-city records
        else:
            sub = [e for e in b1 if e["city"] != g]    # complement: drop this city
        rh, rf, d = delta_of(sub, hier_key, flat_key)
        tot += 1
        keep += 1 if d <= 0 else 0
        rows.append({"block": "A8_leave_one_out", "dataset": "B1_多市", "group": "excl_" + g,
                     "q": 2, "n": len(sub), "rr_hier": round(rh, 4), "rr_flat": round(rf, 4),
                     "delta": round(d, 4), "mean_class_size": 0.0, "risk_bound_e1_c": 0.0})
    print("A8 leave-one-group-out q=2: %d/%d complements keep hier<=flat" % (keep, tot))

    # leave-Shenzhen-out: exclude all records whose parsed city is Shenzhen or a Shenzhen district label
    sz = {"深圳", "龙岗坂田", "南山粤海", "南山西丽", "福田沙头", "龙华民治", "罗湖东晓",
          "南山招商", "龙岗坪山", "福田华强北", "宝安新安", "龙华", "福田街道", "龙华大浪",
          "龙岗", "罗湖南湖", "福田", "福田莲花", "龙岗龙岗街道", "龙岗民治", "龙岗南湾",
          "福田南园", "龙岗平湖"}
    nosz = [e for e in b1 if e["city"] not in sz]
    rh, rf, d = delta_of(nosz, hier_key, flat_key)
    rows.append({"block": "A8_leave_shenzhen", "dataset": "B1_多市", "group": "no-Shenzhen",
                 "q": 2, "n": len(nosz), "rr_hier": round(rh, 4), "rr_flat": round(rf, 4),
                 "delta": round(d, 4), "mean_class_size": 0.0, "risk_bound_e1_c": 0.0})
    print("A8 leave-Shenzhen-out q=2: n=%d delta=%.4f (hier=%.4f flat=%.4f)" % (len(nosz), d, rh, rf))

    # max single-city share
    top = city_counts.most_common(1)
    if top:
        share = top[0][1] / len(b1)
        print("A8 largest parsed-city group: %s (%d/%d = %.1f%%)" % (top[0][0], top[0][1], len(b1), share * 100))

    p = os.path.join(OUT, "A5_A7_A8_advancement.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WRITTEN:", p, "(%d rows)" % len(rows))

if __name__ == "__main__":
    main()
