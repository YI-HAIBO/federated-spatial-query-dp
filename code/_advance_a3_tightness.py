# -*- coding: utf-8 -*-
"""Advance A3: dense numerical tightness scan of the Thm-1 lower bound vs the Thm-2 construction.
   Over a grid of (grid/depth, J, eps) and many range queries, report
   ratio = construction_comm_bits / lower_bound_bits, and whether the ratio is bounded
   (does not grow with K), supporting that the constant gap is a constant factor, not loose.
   Standard library, fixed seeds.
"""
import os, csv, math, random, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
from C1_mixed_workload_5000 import build_data, lower_bound_bits, nQ_range

OUT = HERE

def med(v): return statistics.median(v) if v else 0.0

def construction_comm_bits(data, Q, bloom=0.15, bits_per_count=8):
    nQ = nQ_range(Q, data["grid"], data["depth"])
    return max(1.0, nQ * bits_per_count * bloom)

def main():
    rows = []
    grid_J_eps = []
    for grid in [16, 32, 64]:
        for J in [4, 8, 16]:
            for eps in [0.5, 1.0, 2.0]:
                grid_J_eps.append((grid, J, eps))
    for grid, J, eps in grid_J_eps:
        data = build_data(seed=4, grid=grid, ent_per_cell=3, J=J)
        r = random.Random(1000 + grid * 7 + J)
        ratios = []
        for _ in range(120):
            i0 = r.randint(0, grid - 2); i1 = r.randint(i0 + 1, grid)
            j0 = r.randint(0, grid - 2); j1 = r.randint(j0 + 1, grid)
            Q = (i0, i1, j0, j1)
            nQ = nQ_range(Q, grid, data["depth"])
            comm = construction_comm_bits(data, Q)
            lb = lower_bound_bits(data, Q, nQ, eps)
            ratios.append(comm / max(1e-9, lb))
        rows.append({"grid": grid, "depth": data["depth"], "J": J, "eps": eps,
                     "n_queries": len(ratios),
                     "med_ratio": round(med(ratios), 4),
                     "min_ratio": round(min(ratios), 4),
                     "max_ratio": round(max(ratios), 4)})
        print("grid=%-3d depth=%d J=%-3d eps=%.1f  med_ratio=%.4f  range=[%.4f,%.4f]" % (
            grid, data["depth"], J, eps, med(ratios), min(ratios), max(ratios)))

    # summary: does med_ratio decrease with grid (K) at fixed (J, eps)?
    p = os.path.join(OUT, "A3_tightness_scan.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WROTE", p, "(%d rows)" % len(rows))

if __name__ == "__main__":
    main()
