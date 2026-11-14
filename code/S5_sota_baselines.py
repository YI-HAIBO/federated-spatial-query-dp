# -*- coding: utf-8 -*-
"""S5: SOTA 数值基线对比（解析式）
统一设定: 合成 2D 四叉树 K=256 叶(16x16), J=4 簇, eps=1, 范围查询覆盖 n(Q) 子树根。
对比本文构造(Thm2)与现有方法的误差+通信:
  central_plaintext / central_dp_uniform / local_dp(本地DP)
  ldp_fsrq (LDP-FSRQ, Feng et al. 2024, IJIS)  - 本地DP空间范围查询
  fsp_secagg (FSP, Zhang et al. 2024)          - DP+SecAgg联邦空间发布
  privtree (Zhang et al. 2016, SIGMOD)         - 层级分解,噪声与树高无关
  construction_thm2 (本文)                      - 实际值取自 E4_baselines.csv
误差/通信为"解析估计(order-of-magnitude)",依据各论文渐近结果;通信/下界比值用
定理1 计算下界 LB = J*log2(K) + n(Q)*log2(K)。
"""
import os, csv, math, io

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案"
OUT = os.path.join(BASE, "experiment_outputs")

K = 256; J = 4; eps = 1.0
h = int(round(math.log(K, 4)))
nQ = int(8.0 * (2 ** h - 1))          # 范围查询覆盖的子树根数 (四叉树)
LB = J * math.log2(K) + nQ * math.log2(K)   # 定理1 计算通信下界(主导项)

# (variant, label, err, comm, source)
rows = [
    ("central_plaintext", "Central, no privacy", 0.0, float(K), "Baseline: read all K cells"),
    ("central_dp_uniform", "Central DP (uniform noise)", 1.0, float(K),
     "Central model, O(1/eps) noise; read all K cells"),
    ("local_dp", "Local DP (per-cluster)", 2.0, float(J),
     "Local model, per-cluster noise ~O(1/eps); O(J) uploads"),
    ("ldp_fsrq", "LDP-FSRQ (Feng et al. 2024)", math.sqrt(nQ) / eps, float(nQ),
     "LDP spatial range query: error ~O(sqrt(n(Q))/eps), comm ~O(n(Q))"),
    ("fsp_secagg", "FSP + SecAgg (Zhang et al. 2024)", 1.0, J * math.log2(K),
     "DP + SecAgg: SecAgg cancels individual noise -> central-level error O(1/eps), comm ~O(J log K)"),
    ("privtree", "PrivTree (Zhang et al. 2016)", math.log2(K) / eps, float(K),
     "Hierarchical decomposition, noise independent of tree height ~O(log K/eps); centralized, comm ~O(K)"),
    ("construction_thm2", "This construction (Thm 2)", 2.0, 75.99923868132106,
     "Measured (E4_baselines.csv); consistent projection + R-tree routing + Bloom pruning + cost optimizer"),
]

rows_out = []
for variant, label, err, comm, src in rows:
    rows_out.append({
        "variant": variant, "label": label, "err": round(err, 4),
        "comm": round(comm, 2), "comm_over_LB": round(comm / LB, 4),
        "source": src,
    })

p = os.path.join(OUT, "S5_sota_baselines.csv")
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader(); w.writerows(rows_out)

# Markdown 表格(可直接并入正文 §6)
md = ["# S5 SOTA 数值基线对比（解析式，K=256, J=4, eps=1）\n",
      "统一设定：合成 2D 四叉树 $K=256$ 叶、$J=4$ 簇、$\\varepsilon=1$、范围查询覆盖 $n(Q)=%d$ 子树根。"
      "计算下界 $\\mathrm{LB}=J\\log_2 K + n(Q)\\log_2 K = %.0f$（定理 1 通信主导项）。\n" % (nQ, LB),
      "| 方法 | 误差(相对) | 通信 | 通信/下界 | 来源 |",
      "|:---|---:|---:|---:|:---|"]
for r in rows_out:
    md.append("| %s | %.3f | %.0f | %.3f | %s |" % (r["label"], r["err"], r["comm"], r["comm_over_LB"], r["source"]))
md.append("\n> 注：LDP-FSRQ/FSP/PrivTree 的误差与通信为**解析估计（order-of-magnitude）**，依据各论文渐近结果；"
          "本文构造（construction_thm2）为 E4_baselines.csv 实测值。该表用于说明通信主导性下的机制差异，不替代逐算法重现代码复现。")
with open(os.path.join(OUT, "S5_sota_baselines.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print("K=%d J=%d nQ=%d LB=%.0f" % (K, J, nQ, LB))
for r in rows_out:
    print("  %-22s err=%.3f comm=%.1f comm/LB=%.3f" % (r["label"], r["err"], r["comm"], r["comm_over_LB"]))
print("WRITTEN:", p, os.path.join(OUT, "S5_sota_baselines.md"))
