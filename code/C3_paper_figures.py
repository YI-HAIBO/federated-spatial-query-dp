#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C3: 论文级图表生成（matplotlib, Agg）
读取现有与新增实验 CSV，输出 figures/*.png 与 figures_index.md
"""
import os, csv, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案"
EXP = os.path.join(BASE, "experiment_outputs")
FIG = os.path.join(EXP, "figures")
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

def read_csv(name):
    path = os.path.join(EXP, name)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def to_f(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

figs = []

# Fig 1: RR calibration (S1 real + B1 multi-city + B2 enterprise)
s1 = read_csv("S1_real_rr.csv")
b1 = read_csv("B1_multi_city_rr.csv")
b2 = read_csv("B2_enterprise_rr.csv")
fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
# S1
if s1:
    q = [to_f(r["q_quasi_id"]) for r in s1]
    rh = [to_f(r["rr_hierarchical"]) for r in s1]
    rf = [to_f(r["rr_flat"]) for r in s1]
    tb = [to_f(r.get("theory_bound_e1", 0.7311)) for r in s1]
    axes[0].plot(q, rh, "o-", label="Hierarchical (district)", color="#1f77b4")
    axes[0].plot(q, rf, "s--", label="Flat (street)", color="#d62728")
    axes[0].plot(q, tb, ":", label="Theory bound", color="#555555")
    axes[0].set_title("S1: Shenzhen jobs (N=200)")
    axes[0].set_xlabel("Quasi-identifiers q")
    axes[0].set_ylabel("Re-identification rate")
    axes[0].set_xticks(q)
    axes[0].set_ylim(0, 1.0)
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
# B1
if b1:
    q = [to_f(r["q_quasi_id"]) for r in b1]
    rh = [to_f(r["rr_hierarchical"]) for r in b1]
    rf = [to_f(r["rr_flat"]) for r in b1]
    tb = [to_f(r.get("theory_bound_e1", 0.7311)) for r in b1]
    axes[1].plot(q, rh, "o-", label="Hierarchical (district)", color="#1f77b4")
    axes[1].plot(q, rf, "s--", label="Flat (street)", color="#d62728")
    axes[1].plot(q, tb, ":", label="Theory bound", color="#555555")
    axes[1].set_title("B1: Multi-city jobs (27 cities, N=647)")
    axes[1].set_xlabel("Quasi-identifiers q")
    axes[1].set_xticks(q)
    axes[1].set_ylim(0, 1.0)
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
# B2
if b2:
    labels = [r["qi"].replace("q","Q").replace(":","+").split("+",1)[0] if "+" not in r["qi"] else r["qi"] for r in b2]
    x = list(range(len(b2)))
    rh = [to_f(r["hier_rr"]) for r in b2]
    rf = [to_f(r["flat_rr"]) for r in b2]
    w = 0.35
    axes[2].bar([i-w/2 for i in x], rh, width=w, label="Hierarchical (province)", color="#1f77b4")
    axes[2].bar([i+w/2 for i in x], rf, width=w, label="Flat (city)", color="#d62728")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([r["qi"] for r in b2], rotation=20, ha="right")
    axes[2].set_title("B2: Enterprise entities (N=346)")
    axes[2].set_ylabel("Re-identification rate")
    axes[2].set_ylim(0, max(max(rh+rf)*1.25, 0.1))
    axes[2].grid(True, axis="y", alpha=0.3)
    axes[2].legend()
fig.suptitle("Fig. 1 Re-identification Risk Calibration: Hierarchical vs Flat Aggregation", y=1.02)
fig.tight_layout()
p = os.path.join(FIG, "fig1_rr_calibration.png")
fig.savefig(p); plt.close(fig)
figs.append(("Fig. 1", "fig1_rr_calibration.png", "Real-data RR calibration: S1 Shenzhen, B1 multi-city, B2 enterprise."))

# Fig 2: C1 summary (error and comm ratio)
c1 = read_csv("C1_mixed_workload_5000_summary.csv")
if c1:
    labels = [f"J{r['J']}/g{r['grid']}/ε{r['eps']}" for r in c1]
    x = list(range(len(c1)))
    ef = [to_f(r["med_err_flat"]) for r in c1]
    eh = [to_f(r["med_err_hier"]) for r in c1]
    ratio = [to_f(r["med_ratio_over_lb"]) for r in c1]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax1.plot(x, ef, "s--", label="Flat median error", color="#d62728")
    ax1.plot(x, eh, "o-", label="Hierarchical median error", color="#1f77b4")
    ax1.set_ylabel("Median relative error")
    ax1.set_title("C1 Mixed Workload Scale-up (~5000 queries): Error and Communication Efficiency")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax2.bar(x, ratio, color="#2ca02c", alpha=0.8)
    ax2.axhline(0.16, color="#555", linestyle=":", label="0.16× bound ref")
    ax2.set_ylabel("Median comm / lower bound")
    ax2.set_xlabel("Configuration (J / grid / ε)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha="right")
    ax2.grid(True, axis="y", alpha=0.3)
    ax2.legend()
    fig.tight_layout()
    p = os.path.join(FIG, "fig2_c1_scaleup.png")
    fig.savefig(p); plt.close(fig)
    figs.append(("Fig. 2", "fig2_c1_scaleup.png", "C1 mixed workload (5000 queries): error and communication/lower-bound ratio."))

# Fig 3: Tradeoff (S4 pareto + E3 selected)
s4p = read_csv("S4_pareto.csv")
e3 = read_csv("E3_tradeoff.csv")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
if s4p:
    for scheme, marker, color in [("local","o","#d62728"),("hier","s","#1f77b4")]:
        pts = [r for r in s4p if r.get("scheme")==scheme]
        if pts:
            comm = [to_f(r["comm"]) for r in pts]
            err = [to_f(r["err"]) for r in pts]
            epsv = [to_f(r["eps"]) for r in pts]
            ax1.scatter(comm, err, marker=marker, label=scheme, color=color)
            for c,e,ev in zip(comm,err,epsv):
                ax1.annotate(f"ε={ev:g}", (c,e), textcoords="offset points", xytext=(4,4), fontsize=7)
    ax1.set_xlabel("Communication (bits proxy)")
    ax1.set_ylabel("Error proxy")
    ax1.set_title("S4 Pareto scan (scheme points)")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
if e3:
    # pick alpha=0.1 series
    pts = [r for r in e3 if abs(to_f(r.get("alpha"))-0.1)<1e-9]
    if pts:
        epsv = [to_f(r["epsilon"]) for r in pts]
        ratio = [to_f(r["ratio"]) for r in pts]
        lb = [to_f(r["candidate_lb"]) for r in pts]
        ax2.plot(epsv, ratio, "o-", color="#9467bd", label="comm_central / candidate_lb")
        ax2.set_xlabel("ε (alpha=0.1)")
        ax2.set_ylabel("Ratio")
        ax2.set_title("E3 communication vs candidate lower-bound (α=0.1)")
        ax2.grid(True, alpha=0.3)
        ax2.legend()
fig.tight_layout()
p = os.path.join(FIG, "fig3_tradeoff_pareto.png")
fig.savefig(p); plt.close(fig)
figs.append(("Fig. 3", "fig3_tradeoff_pareto.png", "Privacy-communication-utility tradeoff: Pareto scan and E3 ratio."))

# Fig 4: Ablation
ab = read_csv("S4_ablation.csv")
if ab:
    names = [r["variant"] for r in ab]
    comm = [to_f(r["comm"]) for r in ab]
    err = [to_f(r["err"]) for r in ab]
    fig, ax1 = plt.subplots(figsize=(9,4))
    x = list(range(len(names)))
    bars = ax1.bar(x, comm, color=["#2ca02c" if n=="full_construction" else "#1f77b4" for n in names], alpha=0.8)
    ax1.set_ylabel("Communication (proxy)", color="#1f77b4")
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, rotation=20, ha="right")
    ax1.grid(True, axis="y", alpha=0.3)
    ax2 = ax1.twinx()
    ax2.plot(x, err, "D--", color="#d62728", label="Error")
    ax2.set_ylabel("Error", color="#d62728")
    ax1.set_title("S4 Ablation: Component Contributions")
    fig.tight_layout()
    p = os.path.join(FIG, "fig4_ablation.png")
    fig.savefig(p); plt.close(fig)
    figs.append(("Fig. 4", "fig4_ablation.png", "S4 ablation: communication and error per variant."))

# Fig 5: Scalability & latency
sc = read_csv("S4_scalability.csv")
c2m = read_csv("C2_latency_measured.csv")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11,4.2))
if sc:
    for Jval, color, marker in [(4,"#1f77b4","o"),(8,"#ff7f0e","s"),(16,"#2ca02c","^")]:
        pts = [r for r in sc if int(to_f(r["J"]))==Jval]
        if pts:
            K = [to_f(r["K"]) for r in pts]
            ct = [to_f(r["comm_total"]) for r in pts]
            ax1.plot(K, ct, marker+"-", label=f"J={Jval}", color=color)
    ax1.set_xlabel("K (cells)")
    ax1.set_ylabel("Total communication (proxy)")
    ax1.set_title("S4 Scalability (J × K)")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
if c2m:
    labels = [f"J{r['J']}/g{r['grid']}" for r in c2m]
    x = list(range(len(c2m)))
    p50 = [to_f(r["p50_us"])/1000.0 for r in c2m]
    p95 = [to_f(r["p95_us"])/1000.0 for r in c2m]
    p99 = [to_f(r["p99_us"])/1000.0 for r in c2m]
    ax2.plot(x, p50, "o-", label="p50")
    ax2.plot(x, p95, "s--", label="p95")
    ax2.plot(x, p99, "^:", label="p99")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=20, ha="right")
    ax2.set_ylabel("Latency (ms, in-process proxy)")
    ax2.set_title("C2 Measured processing latency")
    ax2.grid(True, alpha=0.3)
    ax2.legend()
fig.tight_layout()
p = os.path.join(FIG, "fig5_scalability_latency.png")
fig.savefig(p); plt.close(fig)
figs.append(("Fig. 5", "fig5_scalability_latency.png", "Scalability (J×K) and in-process latency profile (C2)."))

# Index markdown
idx = os.path.join(EXP, "C3_figures_index.md")
with open(idx, "w", encoding="utf-8") as f:
    f.write("# C3 论文级图表索引\n\n")
    f.write("生成脚本：`outputs/选题方案/C3_paper_figures.py`（matplotlib Agg，300 dpi）\n\n")
    f.write("| 图 | 文件 | 说明 |\n|---|---|---|\n")
    for name, fn, desc in figs:
        f.write(f"| {name} | `figures/{fn}` | {desc} |\n")
    f.write("\n> 说明：图表基于当前工作空间中的合成实验与已接入的真实/采集数据（S1 深圳、B1 多市招聘、B2 企业采集、C1 扩量、C2 单机延迟与网络建模）。容器/跨地域真实网络延迟未实测，C2 以建模表补充并在文中诚实声明。\n")

print("FIGURES:", len(figs))
for name, fn, _ in figs:
    print(" -", os.path.join(FIG, fn))
print("INDEX:", idx)
