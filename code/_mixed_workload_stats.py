# -*- coding: utf-8 -*-
"""Compute paired Wilcoxon signed-rank tests and bootstrap CIs for the mixed-workload
   scale-up (C1_mixed_workload_5000_detail.csv), per config, on per-query error and
   communication. Outputs a machine-readable CSV and a console table for §7.3.
"""
import csv, os, numpy as np
from scipy import stats
from collections import defaultdict

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs"
SRC = os.path.join(BASE, "C1_mixed_workload_5000_detail.csv")
OUT = os.path.join(BASE, "C1_mixed_workload_5000_stats.csv")

def bootstrap_ci(x, n=2000, seed=0, alpha=0.05):
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    if len(x) == 0:
        return (np.nan, np.nan)
    meds = []
    for _ in range(n):
        s = rng.choice(x, size=len(x), replace=True)
        meds.append(np.median(s))
    meds = np.sort(np.asarray(meds))
    lo = np.percentile(meds, 100*alpha/2)
    hi = np.percentile(meds, 100*(1-alpha/2))
    return (lo, hi)

rows = list(csv.reader(open(SRC, encoding="utf-8")))
header = rows[0]
data = rows[1:]
# config_id, J, grid, K, eps, seed, qid, workload, err_flat, err_hier, comm_flat, comm_hier, nQ, lb_bits
by_cfg = defaultdict(list)
for r in data:
    cid = r[0]
    by_cfg[cid].append({
        "err_flat": float(r[8]), "err_hier": float(r[9]),
        "comm_flat": float(r[10]), "comm_hier": float(r[11]),
        "workload": r[7],
    })

cfg_meta = {}
for r in data:
    cfg_meta[r[0]] = (r[1], r[2], r[3], r[4], r[5])

out_rows = [["config_id","J","grid","K","eps","n_queries",
             "med_err_hier","med_err_flat","better_rate",
             "wilcoxon_W","wilcoxon_p",
             "ci_med_err_hier_lo","ci_med_err_hier_hi",
             "ci_med_err_flat_lo","ci_med_err_flat_hi",
             "ci_better_lo","ci_better_hi",
             "med_comm_hier","med_comm_flat",
             "wilcoxon_comm_W","wilcoxon_comm_p"]]
print("%-4s %-4s %-4s %-5s %-4s %-5s | %-10s %-10s %-10s | %-12s %-12s" % (
    "cfg","J","K","eps","n","wload", "medH","medF","better", "W(p) err", "W(p) comm"))
for cid in sorted(by_cfg, key=int):
    recs = by_cfg[cid]
    J, grid, K, eps, seed = cfg_meta[cid]
    n = len(recs)
    ef = np.array([r["err_flat"] for r in recs])
    eh = np.array([r["err_hier"] for r in recs])
    cf = np.array([r["comm_flat"] for r in recs])
    ch = np.array([r["comm_hier"] for r in recs])
    medH, medF = float(np.median(eh)), float(np.median(ef))
    better = float(np.mean(eh < ef))
    # Wilcoxon signed-rank on paired (err_flat, err_hier) — exclude zero diffs
    d = ef - eh
    nz = d[d != 0]
    if len(nz) >= 10:
        W, p = stats.wilcoxon(eh, ef, zero_method="wilcox")
    else:
        W, p = np.nan, np.nan
    # comm
    dc = cf - ch
    nzc = dc[dc != 0]
    if len(nzc) >= 10:
        Wc, pc = stats.wilcoxon(ch, cf, zero_method="wilcox")
    else:
        Wc, pc = np.nan, np.nan
    # bootstrap
    c_medH = bootstrap_ci(eh)
    c_medF = bootstrap_ci(ef)
    c_better = bootstrap_ci(np.array([1.0 if a < b else 0.0 for a, b in zip(eh, ef)]))
    out_rows.append([cid,J,grid,K,eps,n,"%.4f"%medH,"%.4f"%medF,"%.4f"%better,
                     "%.1f"%W if W==W else "", "%.3g"%p if p==p else "",
                     "%.4f"%c_medH[0],"%.4f"%c_medH[1],
                     "%.4f"%c_medF[0],"%.4f"%c_medF[1],
                     "%.4f"%c_better[0],"%.4f"%c_better[1],
                     "%.1f"%float(np.median(ch)),"%.1f"%float(np.median(cf)),
                     "%.1f"%Wc if Wc==Wc else "", "%.3g"%pc if pc==pc else ""])
    print("%-4s %-4s %-4s %-5s %-4s %-5s | %-10s %-10s %-10s | W=%s p=%s | W=%s p=%s" % (
        cid, J, K, eps, n, grid, "%.4f"%medH, "%.4f"%medF, "%.3f"%better,
        "%.1f"%W if W==W else "n/a", "%.3g"%p if p==p else "n/a",
        "%.1f"%Wc if Wc==Wc else "n/a", "%.3g"%pc if pc==pc else "n/a"))

with open(OUT, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(out_rows)
print("\nStats CSV ->", OUT, os.path.getsize(OUT), "bytes")
