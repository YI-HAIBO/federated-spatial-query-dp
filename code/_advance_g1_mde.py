# -*- coding: utf-8 -*-
"""Advance G1 (MDE quantification): convert the 'small effect |delta|<=0.05 needs a larger
   sample' limitation into an exact, quantified detection-limit statement.

   The v7 G1 evidence (_advance_g1_power.py) answered the forward question:
       'given an effect delta, what n is needed for 80%/90% power?'
   Task #80 answers the inverse question, which is what the paper's Limitations actually
   asks:
       'given the CURRENT pooled sample (n=1193, per-group n_per~=596), what is the
        smallest effect |delta| that this study can detect at 80%/90% power?'
   That is the Minimum Detectable Effect (MDE).  We solve it exactly by bisection on the
   two-proportion z-test power equation (alpha=0.05, two-sided, equal per-group n),
   using IDENTICAL pooled baselines to _advance_g1_power.py (q=1, p_hier=0.1903,
   p_flat=0.3328, delta_obs=-0.1425).

   Standard library + S6 only.  Output: G1_mde.json
"""
import os, sys, math, json
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)

OUT = HERE
N_ENTITIES = 1193          # pooled n from G1_power_analysis.json
P_HIER = 0.1903            # pooled hier risk (q=1)
P_FLAT = 0.3328            # pooled flat risk (q=1)
DELTA_OBS = P_HIER - P_FLAT  # -0.1425
ALPHA = 0.05

def z(level):
    return NormalDist().inv_cdf(level)

def power_at(p1, p2, n_per, alpha=ALPHA):
    """Two-sided two-proportion z-test achieved power, equal per-group n."""
    za = z(1 - alpha / 2)
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n_per)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n_per)
    z_ = abs(p1 - p2) / se1
    # power = P(reject H0 | H1); approximate via normal: Phi((z_*se1 - za*se0)/se1)+...
    return NormalDist().cdf((abs(p1 - p2) - za * se0) / se1) + \
           NormalDist().cdf((-abs(p1 - p2) - za * se0) / se1)

def mde(p_baseline, n_per, power_target=0.80, alpha=ALPHA, sign=-1):
    """Smallest |delta| (delta = p_hier - p_flat, same sign as sign) achieving power_target.
       p_baseline = p_flat (reference proportion).  Bisect on |delta|."""
    lo, hi = 1e-6, 0.999
    for _ in range(60):
        mid = (lo + hi) / 2
        p2 = p_baseline + sign * mid
        p2 = max(1e-6, min(0.999999, p2))
        pw = power_at(p_baseline, p2, n_per, alpha)
        if pw >= power_target:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2

def cohens_h(p1, p2):
    arc = lambda x: 2 * math.asin(math.sqrt(max(0.0, min(1.0, x))))
    return arc(p1) - arc(p2)

def main():
    n_per_current = N_ENTITIES / 2.0   # 596.5
    # MDE at the CURRENT sample, 80% and 90% power
    m80 = mde(P_FLAT, n_per_current, 0.80)
    m90 = mde(P_FLAT, n_per_current, 0.90)
    m80_alt = mde(P_HIER, n_per_current, 0.80, sign=+1)  # symmetric check (baseline=p_hier)
    m90_alt = mde(P_HIER, n_per_current, 0.90, sign=+1)

    # MDE table vs per-group n
    table = []
    for n_per in [50, 100, 148, 150, 198, 200, 300, 400, 596, 800, 1200, 2000]:
        table.append({
            "n_per": n_per,
            "mde_80": round(mde(P_FLAT, n_per, 0.80), 4),
            "mde_90": round(mde(P_FLAT, n_per, 0.90), 4),
        })

    # Sensitivity of MDE to the reference baseline p_flat (how MDE depends on risk level)
    base_sens = []
    for p0 in [0.10, 0.20, 0.3328, 0.45, 0.60]:
        base_sens.append({
            "p_flat": round(p0, 4),
            "mde_80": round(mde(p0, n_per_current, 0.80), 4),
            "mde_90": round(mde(p0, n_per_current, 0.90), 4),
        })

    # Interpret: how many times the observed effect exceeds the detection limit
    ratio80 = abs(DELTA_OBS) / m80
    ratio90 = abs(DELTA_OBS) / m90

    # Cohen's h of the MDE (small-effect convention: h<0.2 small, 0.2-0.5 medium)
    h_mde80 = abs(cohens_h(P_FLAT, P_FLAT - m80))
    h_mde90 = abs(cohens_h(P_FLAT, P_FLAT - m90))
    h_obs = abs(cohens_h(P_FLAT, P_HIER))

    out = {
        "limitation_addressed": "G1: small effect |delta|<=0.05 requires larger sample",
        "approach": ("Inverse power analysis: Minimum Detectable Effect (MDE) at the CURRENT "
                     "pooled sample (n=1193, per-group n_per=596.5), two-proportion z-test, "
                     "alpha=0.05 two-sided, equal per-group n.  Replaces the 'needs larger "
                     "sample' statement with an exact detection-limit number."),
        "baseline": {"p_hier": P_HIER, "p_flat": P_FLAT, "delta_obs": DELTA_OBS,
                     "n_entities": N_ENTITIES, "n_per_current": round(n_per_current, 1)},
        "mde_current_n": {
            "mde_80": round(m80, 4), "mde_90": round(m90, 4),
            "mde_80_alt_baseline": round(m80_alt, 4), "mde_90_alt_baseline": round(m90_alt, 4),
        },
        "observed_vs_mde": {
            "ratio_over_mde80": round(ratio80, 2), "ratio_over_mde90": round(ratio90, 2),
            "cohens_h_observed": round(h_obs, 3),
            "cohens_h_mde80": round(h_mde80, 3), "cohens_h_mde90": round(h_mde90, 3),
        },
        "mde_table": table,
        "baseline_sensitivity": base_sens,
        "conclusion": (
            "With the current n=1193 (n_per=596.5), the smallest effect the study can detect "
            "is |delta| = %.4f (80%% power) / %.4f (90%% power), corresponding to Cohen's h = "
            "%.3f / %.3f.  The OBSERVED effect (|delta|=%.4f, h=%.3f) is %.1fx above the 80%% "
            "detection limit and %.1fx above the 90%% limit.  Hence the '|delta|<=0.05 needs a "
            "larger sample' limitation is not binding here: the study is NOT under-powered for "
            "the effect it actually reports; it would only be under-powered for effects below "
            "the MDE (a |delta| of %.4f or smaller), which is a detection-limit boundary, not "
            "a failure to detect the reported effect."
        ) % (m80, m90, h_mde80, h_mde90, abs(DELTA_OBS), h_obs, ratio80, ratio90, m80),
    }
    p = os.path.join(OUT, "G1_mde.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("G1 MDE at current n (n_per=%.1f):" % n_per_current)
    print("  MDE_80 = %.4f  (h=%.3f)" % (m80, h_mde80))
    print("  MDE_90 = %.4f  (h=%.3f)" % (m90, h_mde90))
    print("  observed |delta|=%.4f (h=%.3f)  ->  %.1fx above MDE_80, %.1fx above MDE_90"
          % (abs(DELTA_OBS), h_obs, ratio80, ratio90))
    print("  MDE table (80/90%):")
    for r in table:
        print("    n_per=%-5d  MDE80=%.4f  MDE90=%.4f" % (r["n_per"], r["mde_80"], r["mde_90"]))
    print("  WROTE", p)

if __name__ == "__main__":
    main()
