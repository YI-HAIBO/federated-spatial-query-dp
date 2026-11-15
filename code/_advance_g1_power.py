# -*- coding: utf-8 -*-
"""Advance G1: power / sensitivity analysis converting the small-sample limitation into a
   quantified conclusion.  Uses the OBSERVED effect (hierarchical vs flat re-identification
   risk difference) from the A7 pooled sample, using IDENTICAL key definitions to the A7
   evidence (_advance_a7_a8_fullq.py + main Table 1/2/3).  Computes Cohen's h, required n for
   80%/90% power (two-proportion z-test, alpha=0.05), achieved power at the current pooled n,
   and a sensitivity table + power curve.
   Standard library + S6 only.
"""
import os, sys, math, json
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
import S6_rr_statistics as S

OUT = HERE

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

def datasets():
    """Identical hier/flat keys and q-steps to _advance_a7_a8_fullq.py + main Table 1/2/3."""
    s1 = S.load_shenzhen(S.S1_PATH) if os.path.exists(S.S1_PATH) else []
    b1 = load_multicity_fixed(S.B1_DIR)
    b2 = S.load_enterprise(S.B2_PATH) if os.path.exists(S.B2_PATH) else []
    return [
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

def risk_pair(ents, hf, ff, qid):
    """Entity-level re-identification risk (unique-fraction) under hier/flat keys."""
    kh = [hf(e) + tuple(qid(e)) for e in ents]
    kf = [ff(e) + tuple(qid(e)) for e in ents]
    ch = Counter(kh); cf = Counter(kf)
    ph = sum(1 for k in kh if ch[k] == 1) / len(ents) if ents else 0.0
    pf = sum(1 for k in kf if cf[k] == 1) / len(ents) if ents else 0.0
    return ph, pf

def cohens_h(p1, p2):
    def arc(x): return 2 * math.asin(math.sqrt(max(0.0, min(1.0, x))))
    return arc(p1) - arc(p2)

def required_n(p1, p2, power=0.80, alpha=0.05):
    from statistics import NormalDist
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_beta = NormalDist().inv_cdf(power)
    pbar = (p1 + p2) / 2; qbar = 1 - pbar
    num = z_alpha * math.sqrt(2 * pbar * qbar) + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    den = (p1 - p2)
    return (num / den) ** 2 if den != 0 else float("inf")

def achieved_power(p1, p2, n, alpha=0.05):
    from statistics import NormalDist
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    pbar = (p1 + p2) / 2; qbar = 1 - pbar
    se = math.sqrt(2 * pbar * qbar / n)
    z = abs(p1 - p2) / se
    return NormalDist().cdf(z - z_alpha) + NormalDist().cdf(-z - z_alpha)

def main():
    ds = datasets()
    # Per-dataset risk at each q, and pooled proportions at the strongest q (q=1).
    per_ds = []
    print("per-dataset entity-level risk (hier/flat) and delta at each q:")
    for name, ents, hf, ff, qsteps in ds:
        line = "%s n=%d" % (name, len(ents))
        vals = []
        for q in range(4):
            ph, pf = risk_pair(ents, hf, ff, qsteps[q][1])
            vals.append((q, ph, pf, ph - pf))
        for q, ph, pf, d in vals:
            line += " | q%d: %.4f/%.4f (%.4f)" % (q, ph, pf, d)
        print("  " + line)
        per_ds.append((name, len(ents), vals))

    # Pooled proportions at q=1 (strongest effect, matches A7 pooled delta=-0.1425)
    q_of_interest = 1
    tot = sum(len(e) for _, e, _, _, _ in ds)
    num_hier = 0.0; num_flat = 0.0
    for (name, ents, hf, ff, qsteps), (nm, n, vals) in zip(ds, per_ds):
        ph, pf = risk_pair(ents, hf, ff, qsteps[q_of_interest][1])
        num_hier += ph * len(ents); num_flat += pf * len(ents)
    p_hier = num_hier / tot; p_flat = num_flat / tot
    n_entities = tot
    delta = p_hier - p_flat
    print("\nPOOLED (q=%d): p_hier=%.4f p_flat=%.4f n=%d delta=%.4f" % (q_of_interest, p_hier, p_flat, n_entities, delta))

    h = cohens_h(p_flat, p_hier)
    print("Cohen's h = %.4f (effect size)" % h)

    n80 = required_n(p_flat, p_hier, 0.80)
    n90 = required_n(p_flat, p_hier, 0.90)
    print("\nRequired sample size for observed effect (two-proportion z-test):")
    print("  power=80%%: n_per=%.0f (total=%.0f)" % (n80, 2 * n80))
    print("  power=90%%: n_per=%.0f (total=%.0f)" % (n90, 2 * n90))
    n_per_current = n_entities / 2
    ap = achieved_power(p_flat, p_hier, n_per_current)
    print("  achieved power at current pooled n (per group=%.0f): %.3f" % (n_per_current, ap))

    print("\n--- sensitivity: required n_per (80% power) vs effect size (holding p_flat) ---")
    sens = []
    for delta_v in [-0.03, -0.05, -0.08, -0.10, -0.1257, -0.1425, -0.18, -0.25, -0.37]:
        p2 = max(0.01, min(0.99, p_flat + delta_v))
        n80d = required_n(p_flat, p2, 0.80)
        sens.append((delta_v, n80d))
        print("  delta=%.4f -> n_per(80%%)=%.0f (total=%.0f)" % (delta_v, n80d, 2 * n80d))

    print("\n--- power curve (observed effect q=%d) ---" % q_of_interest)
    curve = []
    for n_per in [100, 150, 200, 300, 400, 596, 800, 1200]:
        pw = achieved_power(p_flat, p_hier, n_per)
        curve.append((n_per, pw))
        print("  n_per=%-5d power=%.3f" % (n_per, pw))

    out = {
        "q_of_interest": q_of_interest,
        "pooled_p_hier": round(p_hier, 4), "pooled_p_flat": round(p_flat, 4),
        "n_entities": n_entities, "delta": round(delta, 4),
        "cohens_h": round(h, 4),
        "n80_per_group": round(n80, 1), "n90_per_group": round(n90, 1),
        "achieved_power_current": round(ap, 3),
        "sensitivity": [{"delta": d, "n_per_80": round(n, 1)} for d, n in sens],
        "power_curve": [{"n_per": n, "power": round(p, 3)} for n, p in curve],
        "per_dataset": [
            {"name": nm, "n": n,
             "q_vals": [{"q": q, "rr_hier": round(ph, 4), "rr_flat": round(pf, 4), "delta": round(d, 4)}
                        for q, ph, pf, d in vals]} for nm, n, vals in per_ds],
    }
    p = os.path.join(OUT, "G1_power_analysis.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nWROTE", p)

if __name__ == "__main__":
    main()
