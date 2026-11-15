# -*- coding: utf-8 -*-
"""Additional weakness-resolution evidence from existing data:
   (1) per-workload breakdown of the mixed-workload scale-up (range/cascade/knn),
       with Wilcoxon test -> addresses kNN-depth / workload-coverage concern;
   (2) leave-one-dataset-out robustness for the risk ordering (RQ1) -> cross-validation;
   (3) pooled (inverse-variance) effect size across datasets -> small-sample / meta concern.
   Outputs C1_workload_breakdown.csv and S6_rr_robustness.csv.
"""
import csv, os, math, numpy as np
from scipy import stats
from collections import defaultdict

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs"

# ---------- 1. per-workload breakdown ----------
rows = list(csv.reader(open(os.path.join(BASE, "C1_mixed_workload_5000_detail.csv"), encoding="utf-8")))
data = rows[1:]
by_wl = defaultdict(list)
for r in data:
    by_wl[r[7]].append((float(r[8]), float(r[9]), float(r[10]), float(r[11])))  # err_flat, err_hier, comm_flat, comm_hier

def wilcox_p(a, b):
    d = np.array(a, dtype=float) - np.array(b, dtype=float)
    d = d[d != 0]
    if len(d) < 10:
        return float("nan")
    return float(stats.wilcoxon(a, b, zero_method="wilcox").pvalue)

out1 = [["workload","n_queries","med_err_hier","med_err_flat","better_rate","wilcoxon_p_err","med_comm_hier","med_comm_flat","wilcoxon_p_comm"]]
print("=== per-workload breakdown ===")
for wl in ["range", "cascade", "knn"]:
    recs = by_wl[wl]
    ef = [r[0] for r in recs]; eh = [r[1] for r in recs]
    cf = [r[2] for r in recs]; ch = [r[3] for r in recs]
    better = float(np.mean([a < b for a, b in zip(eh, ef)]))
    pe = wilcox_p(eh, ef); pc = wilcox_p(ch, cf)
    out1.append([wl, len(recs), "%.4f"%float(np.median(eh)), "%.4f"%float(np.median(ef)),
                 "%.4f"%better, "%.3g"%pe, "%.1f"%float(np.median(ch)), "%.1f"%float(np.median(cf)), "%.3g"%pc])
    print("  %-8s n=%4d  medH=%.4f medF=%.4f better=%.3f p_err=%.2g  medCommH=%.1f p_comm=%.2g" % (
        wl, len(recs), float(np.median(eh)), float(np.median(ef)), better, pe, float(np.median(ch)), pc))
with open(os.path.join(BASE, "C1_workload_breakdown.csv"), "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(out1)
print("-> C1_workload_breakdown.csv")

# ---------- 2 & 3. leave-one-out + pooled meta ----------
srows = list(csv.reader(open(os.path.join(BASE, "S6_rr_statistics.csv"), encoding="utf-8")))[1:]
# dataset, q, n, rr_hier, rr_flat, delta, mc_b, mc_c, mc_p, ci_hier_lo, ci_hier_hi, ci_flat_lo, ci_flat_hi
recs = []
for r in srows:
    recs.append(dict(ds=r[0], q=int(r[1]), n=int(r[2]),
                     h=float(r[3]), f=float(r[4]), d=float(r[5]),
                     b=int(r[6]), c=int(r[7]), p=float(r[8]),
                     hlo=float(r[9]), hhi=float(r[10]), flo=float(r[11]), fhi=float(r[12])))

print("\n=== leave-one-dataset-out robustness ===")
out2 = [["left_out","configs_remaining","sig_configs","sig_pct","all_hier_le_flat"]]
dss = sorted(set(r["ds"] for r in recs))
for lo in dss:
    rem = [r for r in recs if r["ds"] != lo]
    sig = sum(1 for r in rem if r["p"] <= 0.0002)
    le = sum(1 for r in rem if r["h"] <= r["f"])
    out2.append([lo, len(rem), sig, "%.1f%%"%(100*sig/len(rem)), "%d/%d"%(le, len(rem))])
    print("  leave-out %-8s : %d configs, %d significant (%.0f%%), hier<=flat %d/%d" % (
        lo, len(rem), sig, 100*sig/len(rem), le, len(rem)))
out2.append(["NONE(all)", len(recs), sum(1 for r in recs if r["p"]<=0.0002), "%.1f%%"%(100*sum(1 for r in recs if r["p"]<=0.0002)/len(recs)), "%d/%d"%(sum(1 for r in recs if r["h"]<=r["f"]), len(recs))])

# pooled inverse-variance weighted delta (meta-analytic, fixed effect)
print("\n=== pooled effect size (fixed-effect inverse-variance) ===")
out3 = [["group","k","pooled_delta","pooled_lo","pooled_hi","n_total"]]
def pooled(rs):
    # approximate SE of delta from the two bootstrap CIs (each ~ +-1.96*SE)
    wsum = 0.0; num = 0.0
    for r in rs:
        se = ((r["hhi"] - r["hlo"]) + (r["fhi"] - r["flo"])) / (2 * 1.96 * math.sqrt(2))
        if se <= 0: se = 1e-9
        w = 1.0 / (se * se)
        num += w * r["d"]; wsum += w
    d = num / wsum
    # variance of pooled = 1/wsum
    se_p = 1.0 / math.sqrt(wsum)
    return d, d - 1.96*se_p, d + 1.96*se_p
for grp, rs in [("all", recs), ("q0", [r for r in recs if r["q"]==0]),
                ("q1", [r for r in recs if r["q"]==1]), ("q2", [r for r in recs if r["q"]==2]),
                ("q3", [r for r in recs if r["q"]==3])]:
    d, lo, hi = pooled(rs)
    out3.append([grp, len(rs), "%.4f"%d, "%.4f"%lo, "%.4f"%hi, sum(r["n"] for r in rs)])
    print("  %-6s k=%2d  pooled delta=%.4f [%.4f, %.4f]  n=%d" % (grp, len(rs), d, lo, hi, sum(r["n"] for r in rs)))
with open(os.path.join(BASE, "S6_rr_robustness.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    for row in out2: w.writerow(row)
    w.writerow([])
    for row in out3: w.writerow(row)
print("\n-> S6_rr_robustness.csv")
