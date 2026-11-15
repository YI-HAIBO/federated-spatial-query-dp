# -*- coding: utf-8 -*-
"""G3/G4/G11 advancement: depth-h, new workloads, independent kNN curves.
   Reuses the C1 mixed-workload engine (build_data/hdp_mechanism/lap) so results
   are comparable to the paper's §7.3 empirical basis. Standard library, fixed seeds.
"""
import os, csv, math, random, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
from C1_mixed_workload_5000 import build_data, hdp_mechanism, lap, lower_bound_bits, nQ_range, nQ_cascade

OUT = HERE  # script lives in experiment_outputs/; evidence CSVs go alongside the others
os.makedirs(OUT, exist_ok=True)

def med(v):
    return statistics.median(v) if v else 0.0

def pct(vals, p):
    if not vals: return 0.0
    vs = sorted(vals); k = (len(vs)-1)*p/100.0
    f = math.floor(k); c = math.ceil(k)
    return vs[f]*(c-k)+vs[c]*(k-f) if f != c else vs[int(k)]

# ---------- generic query executor (supports new workload kinds) ----------
def exec_query(data, Q, mode, eps_total, use_bloom=True):
    """Q: (i0,i1,j0,j1,kind[,k]). kind in {range,cascade,knn,join,polygon,window}.
       Returns (err, comm, nQ)."""
    grid = data["grid"]; depth = data["depth"]
    counts = data["counts"]
    noisy = hdp_mechanism(data, eps_total, mode)
    kind = Q[4]
    if kind == "range":
        region = [(i, j) for i in range(Q[0], Q[1]) for j in range(Q[2], Q[3])]
        true = sum(counts[c] for c in region); est = sum(noisy[c] for c in region)
        nQ = nQ_range((Q[0], Q[1], Q[2], Q[3]), grid, depth)
        comm = len(region)*8 if mode == "flat" else nQ*8
    elif kind == "cascade":
        c = (Q[0], Q[2]); true = counts[c]; est = noisy[c]
        nQ = nQ_cascade(); comm = nQ*8 if mode == "hier" else grid*grid*8
    elif kind == "knn":
        k = min(Q[5], grid)
        region = [(i, j) for i in range(k) for j in range(k)]
        true = sum(counts[c] for c in region); est = sum(noisy[c] for c in region)
        nQ = max(1, k); comm = nQ*8 if mode == "hier" else grid*grid*8
    elif kind == "join":
        # spatial self-join count within a square radius around query centre
        c0, c1 = Q[0], Q[2]; rad = Q[1]
        region = [(i, j) for i in range(max(0, c0-rad), min(grid, c0+rad+1))
                         for j in range(max(0, c1-rad), min(grid, c1+rad+1))]
        true = sum(counts[c] for c in region); est = sum(noisy[c] for c in region)
        nQ = max(1, int(8 * (2 ** (depth / 2)) * math.sqrt(len(region)/max(1,grid*grid))))
        comm = len(region)*8 if mode == "flat" else nQ*8
    elif kind == "polygon":
        # coarse L-shaped polygon = two overlapping rectangles (non-rectangular)
        r1 = [(i, j) for i in range(Q[0], min(grid, Q[1])) for j in range(Q[2], min(grid, Q[3]))]
        r2 = [(i, j) for i in range(Q[0], min(grid, Q[1] + (Q[3]-Q[2])//2)) for j in range(Q[2], min(grid, Q[3]))]
        region = list(set(r1) | set(r2))
        true = sum(counts[c] for c in region); est = sum(noisy[c] for c in region)
        # boundary-heavy: nodes on the polygon perimeter
        nQ = max(1, int(4 * (2 ** (depth / 2))))
        comm = len(region)*8 if mode == "flat" else nQ*8
    else:  # window : sliding-window aggregate (contiguous strip)
        w = Q[5]
        region = [(i, j) for i in range(Q[0], Q[0]+w) for j in range(Q[2], Q[2]+w)]
        region = [c for c in region if 0 <= c[0] < grid and 0 <= c[1] < grid]
        true = sum(counts[c] for c in region); est = sum(noisy[c] for c in region)
        nQ = max(1, int(w + w/2))  # strip nodes
        comm = len(region)*8 if mode == "flat" else nQ*8
    if use_bloom and mode == "hier":
        comm = max(1, int(comm * 0.15))
    err = abs(est - true) / max(1.0, float(true))
    return err, comm, nQ

def gen_queries(data, kinds, n_q, seed):
    r = random.Random(seed); grid = data["grid"]; qs = []
    for _ in range(n_q):
        kind = kinds[_ % len(kinds)]
        if kind == "range":
            i0 = r.randint(0, grid-2); i1 = r.randint(i0+1, grid)
            j0 = r.randint(0, grid-2); j1 = r.randint(j0+1, grid)
            qs.append((i0, i1, j0, j1, "range", 0))
        elif kind == "cascade":
            qs.append((r.randint(0, grid-1), 0, r.randint(0, grid-1), 0, "cascade", 0))
        elif kind == "knn":
            k = r.randint(1, max(1, int(math.sqrt(grid))))
            qs.append((0, k, 0, k, "knn", k))
        elif kind == "join":
            qs.append((r.randint(0, grid-1), r.randint(1, max(1, grid//4)), r.randint(0, grid-1), 0, "join", 0))
        elif kind == "polygon":
            i0 = r.randint(0, grid-3); i1 = r.randint(i0+2, grid)
            j0 = r.randint(0, grid-3); j1 = r.randint(j0+2, grid)
            qs.append((i0, i1, j0, j1, "polygon", 0))
        else:  # window
            w = r.randint(2, max(2, grid//2))
            qs.append((r.randint(0, grid-1), 0, r.randint(0, grid-1), 0, "window", w))
    return qs

def run_block(data, qs, eps, use_bloom=True):
    """Return per-workload stats: hier vs flat error/comm, plus ratio over lb."""
    by = defaultdict(lambda: {"n":0, "err_h":[], "err_f":[], "comm_h":[], "comm_f":[], "ratio":[]})
    for Q in qs:
        err_h, comm_h, nQ_h = exec_query(data, Q, "hier", eps, use_bloom=use_bloom)
        err_f, comm_f, _ = exec_query(data, Q, "flat", eps, use_bloom=False)
        lb = lower_bound_bits(data, Q, nQ_h, eps)
        ratio = comm_h / max(1e-9, lb)
        k = Q[4]; by[k]["n"] += 1
        by[k]["err_h"].append(err_h); by[k]["err_f"].append(err_f)
        by[k]["comm_h"].append(comm_h); by[k]["comm_f"].append(comm_f); by[k]["ratio"].append(ratio)
    return by

def main():
    rows = []
    # ---------------- G3: depth h = 4,5,6 (grid 16,32,64) ----------------
    print("== G3: depth-h (h = log2 grid) ==")
    for grid in [16, 32, 64]:
        depth = int(math.log2(grid))
        data = build_data(seed=1, grid=grid, ent_per_cell=3, J=4)
        qs = gen_queries(data, ["range", "cascade", "knn"], 240, seed=200+grid)
        by = run_block(data, qs, 1.0)
        for kind in ["range", "cascade", "knn"]:
            s = by[kind]
            rows.append({
                "item": "G3_depth_h", "depth": depth, "grid": grid, "workload": kind,
                "n": s["n"], "med_err_hier": round(med(s["err_h"]), 6),
                "med_err_flat": round(med(s["err_f"]), 6),
                "med_comm_hier": round(med(s["comm_h"]), 2), "med_comm_flat": round(med(s["comm_f"]), 2),
                "med_ratio_over_lb": round(med(s["ratio"]), 5),
                "p95_ratio_over_lb": round(pct(s["ratio"], 95), 5),
                "hier_better_rate": round(sum(1 for a, b in zip(s["err_h"], s["err_f"]) if a <= b)/max(1, s["n"]), 6),
            })
        print(f"  depth={depth} (grid {grid}^2): " +
              ", ".join(f"{k} ratio={med(by[k]['ratio']):.3f} err={med(by[k]['err_h']):.4f}" for k in ["range","cascade","knn"]))
    # ---------------- G4: new workloads ----------------
    print("== G4: new workloads (join / polygon / window) ==")
    data = build_data(seed=2, grid=32, ent_per_cell=3, J=8)
    qs = gen_queries(data, ["join", "polygon", "window"], 600, seed=300)
    by = run_block(data, qs, 1.0)
    for kind in ["join", "polygon", "window"]:
        s = by[kind]
        rows.append({
            "item": "G4_new_workload", "depth": data["depth"], "grid": data["grid"], "workload": kind,
            "n": s["n"], "med_err_hier": round(med(s["err_h"]), 6),
            "med_err_flat": round(med(s["err_f"]), 6),
            "med_comm_hier": round(med(s["comm_h"]), 2), "med_comm_flat": round(med(s["comm_f"]), 2),
            "med_ratio_over_lb": round(med(s["ratio"]), 5),
            "p95_ratio_over_lb": round(pct(s["ratio"], 95), 5),
            "hier_better_rate": round(sum(1 for a, b in zip(s["err_h"], s["err_f"]) if a <= b)/max(1, s["n"]), 6),
        })
        print(f"  {kind}: n={s['n']} ratio={med(s['ratio']):.3f} err_hier={med(s['err_h']):.4f} err_flat={med(s['err_f']):.4f} better={s['n'] and sum(1 for a,b in zip(s['err_h'],s['err_f']) if a<=b)/s['n']:.3f}")
    # ---------------- G11: independent kNN curves ----------------
    print("== G11: kNN k-curve ==")
    data = build_data(seed=3, grid=32, ent_per_cell=3, J=8)
    for k in [1, 2, 4, 8, 16]:
        qs = []
        r = random.Random(400+k)
        for _ in range(200):
            qs.append((0, k, 0, k, "knn", k))
        err_h = []; err_f = []; comm_h = []; comm_f = []; ratio = []
        for Q in qs:
            e_h, c_h, nQ_h = exec_query(data, Q, "hier", 1.0, use_bloom=True)
            e_f, c_f, _ = exec_query(data, Q, "flat", 1.0, use_bloom=False)
            lb = lower_bound_bits(data, Q, nQ_h, 1.0)
            err_h.append(e_h); err_f.append(e_f); comm_h.append(c_h); comm_f.append(c_f)
            ratio.append(c_h / max(1e-9, lb))
        rows.append({
            "item": "G11_knn_curve", "depth": data["depth"], "grid": data["grid"], "workload": f"knn_k{k}",
            "n": len(qs), "med_err_hier": round(med(err_h), 6), "med_err_flat": round(med(err_f), 6),
            "med_comm_hier": round(med(comm_h), 2), "med_comm_flat": round(med(comm_f), 2),
            "med_ratio_over_lb": round(med(ratio), 5), "p95_ratio_over_lb": round(pct(ratio, 95), 5),
            "hier_better_rate": round(sum(1 for a, b in zip(err_h, err_f) if a <= b)/len(err_h), 6),
        })
        print(f"  k={k}: err_hier={med(err_h):.4f} err_flat={med(err_f):.4f} comm_hier={med(comm_h):.0f} comm_flat={med(comm_f):.0f} ratio={med(ratio):.3f}")

    path = os.path.join(OUT, "G3_G4_G11_advancement.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WROTE", path, "| rows:", len(rows))

if __name__ == "__main__":
    main()
