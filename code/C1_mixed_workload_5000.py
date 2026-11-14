#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C1: 多负载混合扩量实验（~5000 条查询）
负载：range / cascade / knn 混合，跨多组 (J, grid, eps, seed) 配置。
在 S3 原型逻辑基础上扩展：记录单查询处理耗时（进程内延迟代理），
输出逐查询明细与分配置汇总 CSV。
"""
import os, csv, math, random, statistics, time
from collections import defaultdict

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_outputs")
os.makedirs(OUT, exist_ok=True)

def lap(b, r):
    u = r.random() - 0.5
    if abs(u) < 1e-12:
        return 0.0
    return -b * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u))

def build_data(seed=0, grid=16, ent_per_cell=3, J=4):
    r = random.Random(seed)
    cells = [(i, j) for i in range(grid) for j in range(grid)]
    K = len(cells)
    counts = {}
    for (i, j) in cells:
        counts[(i, j)] = ent_per_cell
    depth = int(math.log2(grid)) if grid > 0 else 1
    return {"grid": grid, "K": K, "depth": depth, "counts": counts, "J": J, "r": r}

def nQ_range(Q, grid, depth):
    base = int(8 * (2 ** (depth / 2))) if depth > 0 else 8
    area = max(1, (Q[1] - Q[0]) * (Q[3] - Q[2]))
    total = grid * grid
    frac = max(0.05, min(1.0, area / total))
    return max(1, int(base * math.sqrt(frac)))

def nQ_cascade():
    return 3

def nQ_knn(k):
    return max(1, k)

def hdp_mechanism(data, eps_total, mode="hier"):
    r = data["r"]
    counts = data["counts"]
    depth = max(1, data["depth"])
    if mode == "flat":
        eps = max(1e-6, eps_total / depth)
        return {k: max(0.0, v + lap(1.0 / eps, r)) for k, v in counts.items()}
    eps = max(1e-6, eps_total)
    return {k: max(0.0, v + lap(1.0 / eps, r)) for k, v in counts.items()}

def run_query(data, Q, mode, eps_total, use_bloom=True):
    grid = data["grid"]; depth = data["depth"]
    counts = data["counts"]
    noisy = hdp_mechanism(data, eps_total, mode)
    if Q[4] == "range":
        true = sum(counts[(i, j)] for i in range(Q[0], Q[1]) for j in range(Q[2], Q[3]))
        est = sum(noisy[(i, j)] for i in range(Q[0], Q[1]) for j in range(Q[2], Q[3]))
        nQ = nQ_range((Q[0], Q[1], Q[2], Q[3]), grid, depth)
        area = (Q[1]-Q[0]) * (Q[3]-Q[2])
        comm = area * 8 if mode == "flat" else nQ * 8
        if use_bloom and mode == "hier":
            comm = max(1, int(comm * 0.15))
    elif Q[4] == "cascade":
        i, j = Q[0], Q[2]
        true = counts[(i, j)]
        est = noisy[(i, j)]
        nQ = nQ_cascade()
        comm = nQ * 8 if mode == "hier" else grid * grid * 8
        if use_bloom and mode == "hier":
            comm = max(1, int(comm * 0.15))
    else:  # knn
        k = Q[5]
        k = min(k, grid)
        true = sum(counts[(i, j)] for i in range(k) for j in range(k))
        est = sum(noisy[(i, j)] for i in range(k) for j in range(k))
        nQ = nQ_knn(k)
        comm = nQ * 8 if mode == "hier" else grid * grid * 8
        if use_bloom and mode == "hier":
            comm = max(1, int(comm * 0.15))
    err = abs(est - true) / max(1.0, float(true))
    return err, comm, nQ

def queries(data, n_q, seed):
    r = random.Random(seed)
    grid = data["grid"]
    qs = []
    kinds = ["range", "cascade", "knn"]
    for idx in range(n_q):
        kind = kinds[idx % len(kinds)]
        if kind == "range":
            i0 = r.randint(0, grid-2); i1 = r.randint(i0+1, grid)
            j0 = r.randint(0, grid-2); j1 = r.randint(j0+1, grid)
            qs.append((i0, i1, j0, j1, "range", 0))
        elif kind == "cascade":
            qs.append((r.randint(0, grid-1), 0, r.randint(0, grid-1), 0, "cascade", 0))
        else:
            k = r.randint(1, max(1, int(math.sqrt(grid))))
            qs.append((0, k, 0, k, "knn", k))
    return qs

def lower_bound_bits(data, Q, nQ, eps_total):
    grid = data["grid"]
    J = data["J"]
    eps = max(1e-6, eps_total)
    return J * math.log2(max(2, grid)) + nQ * math.log2(max(2, grid)) + nQ / eps

def pct(vals, p):
    if not vals:
        return 0.0
    vs = sorted(vals)
    k = (len(vs)-1) * p / 100.0
    f = math.floor(k); c = math.ceil(k)
    if f == c:
        return vs[int(k)]
    return vs[f] * (c-k) + vs[c] * (k-f)

def main():
    configs = [
        {"J":4,  "grid":16, "eps":0.5, "seed":0, "n":400},
        {"J":4,  "grid":16, "eps":1.0, "seed":1, "n":400},
        {"J":4,  "grid":16, "eps":2.0, "seed":2, "n":400},
        {"J":8,  "grid":16, "eps":1.0, "seed":3, "n":400},
        {"J":8,  "grid":32, "eps":1.0, "seed":4, "n":500},
        {"J":8,  "grid":32, "eps":2.0, "seed":5, "n":500},
        {"J":16, "grid":32, "eps":1.0, "seed":6, "n":600},
        {"J":16, "grid":32, "eps":2.0, "seed":7, "n":600},
        {"J":16, "grid":64, "eps":1.0, "seed":8, "n":600},
        {"J":16, "grid":64, "eps":2.0, "seed":9, "n":600},
    ]
    detail_path = os.path.join(OUT, "C1_mixed_workload_5000_detail.csv")
    summary_path = os.path.join(OUT, "C1_mixed_workload_5000_summary.csv")

    detail_fields = [
        "config_id","J","grid","K","eps","seed","qid","workload",
        "err_flat","err_hier","comm_flat","comm_hier","nQ","lb_bits",
        "ratio_comm_over_lb","latency_us","mode"
    ]
    summary_rows = []
    total = 0
    with io_open(detail_path, "w") as fdet:
        wdet = csv.DictWriter(fdet, fieldnames=detail_fields)
        wdet.writeheader()
        for ci, cfg in enumerate(configs):
            data = build_data(seed=cfg["seed"], grid=cfg["grid"], ent_per_cell=3, J=cfg["J"])
            qs = queries(data, n_q=cfg["n"], seed=100+cfg["seed"])
            latencies = []
            errs_flat=[]; errs_hier=[]; comms_flat=[]; comms_hier=[]; ratios=[]
            by_kind = defaultdict(lambda: {"n":0,"err_h":[], "err_f":[], "ratio":[]})
            for qid, Q in enumerate(qs):
                t0 = time.perf_counter()
                err_f, comm_f, nQ_f = run_query(data, Q, "flat", cfg["eps"], use_bloom=False)
                err_h, comm_h, nQ_h = run_query(data, Q, "hier", cfg["eps"], use_bloom=True)
                t1 = time.perf_counter()
                lat_us = (t1 - t0) * 1e6
                lb = lower_bound_bits(data, Q, nQ_h, cfg["eps"])
                ratio = comm_h / max(1e-9, lb)
                kind = Q[4]
                wdet.writerow({
                    "config_id": ci, "J": cfg["J"], "grid": cfg["grid"], "K": data["K"],
                    "eps": cfg["eps"], "seed": cfg["seed"], "qid": qid, "workload": kind,
                    "err_flat": round(err_f,6), "err_hier": round(err_h,6),
                    "comm_flat": comm_f, "comm_hier": comm_h, "nQ": nQ_h,
                    "lb_bits": round(lb,4), "ratio_comm_over_lb": round(ratio,6),
                    "latency_us": round(lat_us,3), "mode": "single_process_proxy"
                })
                latencies.append(lat_us)
                errs_flat.append(err_f); errs_hier.append(err_h)
                comms_flat.append(comm_f); comms_hier.append(comm_h); ratios.append(ratio)
                by_kind[kind]["n"] += 1
                by_kind[kind]["err_h"].append(err_h); by_kind[kind]["err_f"].append(err_f)
                by_kind[kind]["ratio"].append(ratio)
                total += 1
            summary_rows.append({
                "config_id": ci, "J": cfg["J"], "grid": cfg["grid"], "K": data["K"],
                "eps": cfg["eps"], "n_queries": len(qs),
                "med_err_flat": round(statistics.median(errs_flat),6),
                "med_err_hier": round(statistics.median(errs_hier),6),
                "med_comm_flat": round(statistics.median(comms_flat),3),
                "med_comm_hier": round(statistics.median(comms_hier),3),
                "med_ratio_over_lb": round(statistics.median(ratios),6),
                "p95_ratio_over_lb": round(pct(ratios,95),6),
                "lat_p50_us": round(pct(latencies,50),3),
                "lat_p95_us": round(pct(latencies,95),3),
                "lat_p99_us": round(pct(latencies,99),3),
                "hier_better_err_rate": round(sum(1 for a,b in zip(errs_hier,errs_flat) if a<=b)/len(errs_hier),6),
            })
            print(f"config {ci} J={cfg['J']} grid={cfg['grid']} eps={cfg['eps']} n={len(qs)} done")

    with io_open(summary_path, "w") as fsum:
        wsum = csv.DictWriter(fsum, fieldnames=list(summary_rows[0].keys()))
        wsum.writeheader()
        wsum.writerows(summary_rows)

    # per-workload overall summary
    # re-read detail not necessary; compute quick overall from summary? better write overall
    overall_path = os.path.join(OUT, "C1_mixed_workload_5000_overall.md")
    with io_open(overall_path, "w") as f:
        f.write("# C1 多负载混合扩量（~5000 查询）\n\n")
        f.write(f"- 总查询数：{total}\n")
        f.write(f"- 配置数：{len(configs)}（J∈{{4,8,16}}，grid∈{{16,32,64}}，ε∈{{0.5,1,2}}）\n")
        f.write(f"- 负载：range / cascade / knn 按轮转混合\n")
        f.write(f"- 延迟：单进程 `time.perf_counter()` 代理（非容器/网络真实延迟，见 C2 说明）\n\n")
        f.write("## 分配置汇总\n\n")
        f.write("| J | grid | ε | n | med_err_flat | med_err_hier | med_comm_flat | med_comm_hier | med_ratio/lb | p95_ratio/lb | lat_p50(us) | lat_p95(us) |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for r in summary_rows:
            f.write(f"| {r['J']} | {r['grid']} | {r['eps']} | {r['n_queries']} | {r['med_err_flat']:.4f} | {r['med_err_hier']:.4f} | {r['med_comm_flat']:.0f} | {r['med_comm_hier']:.0f} | {r['med_ratio_over_lb']:.4f} | {r['p95_ratio_over_lb']:.4f} | {r['lat_p50_us']:.2f} | {r['lat_p95_us']:.2f} |\n")
        f.write("\n## 产出文件\n- `C1_mixed_workload_5000_detail.csv`：逐查询明细\n- `C1_mixed_workload_5000_summary.csv`：分配置汇总\n")
    print(f"TOTAL_QUERIES={total}")
    print(f"WROTE {detail_path}")
    print(f"WROTE {summary_path}")
    print(f"WROTE {overall_path}")

def io_open(path, mode):
    return open(path, mode, newline="", encoding="utf-8-sig")

if __name__ == "__main__":
    main()
