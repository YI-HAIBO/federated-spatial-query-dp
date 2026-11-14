# -*- coding: utf-8 -*-
"""C3b: 真实容器/网络延迟图（fig6）"""
import os, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXP = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs"
FIG = os.path.join(EXP, "figures")
os.makedirs(FIG, exist_ok=True)

def read(name):
    p = os.path.join(EXP, name)
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def f(v):
    try: return float(v)
    except: return 0.0

# 汇总每档配置
configs = [("baseline", 0), ("delay10", 10), ("delay30", 30), ("delay80", 80)]
rows = []
for mode, d in configs:
    data = read("C2_%s.csv" % mode)
    rtts = [f(r["p50_ms"]) for r in data if r["metric"] == "rtt_http"]
    q = [f(r["p50_ms"]) for r in data if r["metric"] == "federated_query"]
    q95 = [f(r["p95_ms"]) for r in data if r["metric"] == "federated_query"]
    rows.append({
        "delay": d, "rtt_p50": sum(rtts)/len(rtts) if rtts else 0,
        "q_p50": q[0] if q else 0, "q_p95": q95[0] if q95 else 0,
    })

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
x = [r["delay"] for r in rows]
rtt = [r["rtt_p50"] for r in rows]
ax1.plot(x, rtt, "o-", color="#1f77b4", label="Container RTT p50")
ax1.plot(x, [2*d for d in x], "--", color="#d62728", label="2× injected delay (ideal)")
ax1.set_xlabel("Injected one-way delay (ms, tc netem)")
ax1.set_ylabel("Container-to-container RTT (ms)")
ax1.set_title("Real container RTT vs injected delay")
ax1.grid(True, alpha=0.3); ax1.legend()

q = [r["q_p50"] for r in rows]
q95 = [r["q_p95"] for r in rows]
ax2.plot(x, q, "o-", label="Federated query p50", color="#2ca02c")
ax2.plot(x, q95, "s--", label="Federated query p95", color="#9467bd")
ax2.set_xlabel("Injected one-way delay (ms)")
ax2.set_ylabel("End-to-end query latency (ms)")
ax2.set_title("Federated query latency (4 nodes sequential)")
ax2.grid(True, alpha=0.3); ax2.legend()

fig.tight_layout()
p = os.path.join(FIG, "fig6_real_container_latency.png")
fig.savefig(p, dpi=300)   # IJGIS: figures must be >=300 dpi (was 100 dpi -> 1100x420)
print("WROTE", p, "(dpi=300)")

# update index (idempotent: avoid duplicate row on re-run)
idx = os.path.join(EXP, "C3_figures_index.md")
row = "\n| Fig. 6 | `figures/fig6_real_container_latency.png` | 真实容器间 RTT 与联邦查询端到端延迟（VM: 192.168.235.128，`tc netem` 10/30/80ms 注入） |\n"
if os.path.exists(idx):
    cur = open(idx, "r", encoding="utf-8").read()
    if "fig6_real_container_latency.png" in cur and "| Fig. 6 |" in cur:
        print("INDEX_SKIP (already present)")
    else:
        with open(idx, "a", encoding="utf-8") as fh:
            fh.write(row)
        print("INDEX_UPDATED")
else:
    with open(idx, "w", encoding="utf-8") as fh:
        fh.write("# C3 论文级图表索引\n" + row)
    print("INDEX_CREATED")
