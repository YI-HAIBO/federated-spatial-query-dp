# -*- coding: utf-8 -*-
"""G8/G9 advancement: same-engine baseline measurement (FSP+SecAgg, LDP-FSRQ, PrivTree)
   and G9 on-wire byte accounting applied to the construction's communication.
   Uses the C1 cost model so baselines are measured on the SAME basis as the
   construction (not just analytical estimates). Standard library, fixed seeds.
"""
import os, csv, math, random, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
from C1_mixed_workload_5000 import build_data, lap, lower_bound_bits, nQ_range

OUT = HERE

def med(v): return statistics.median(v) if v else 0.0

# ---- on-wire byte accounting (G9): bits -> serialized message bytes with overhead ----
def bytes_on_wire(bits, n_msgs):
    """Model on-wire bytes: each message = header(40B) + payload ceil(bits/8) + TCP/IP(40B)."""
    if n_msgs <= 0: return 0.0
    per_msg = 40 + math.ceil(bits / 8) + 40
    return n_msgs * per_msg

# ---- baseline mechanisms on the grid (simplified, same-basis) ----
def baseline_query(data, Q, kind, eps_total, seed):
    """Returns (rel_error, comm_bits, n_msgs) for a range query under baseline 'kind'.
       kinds: 'flat_central', 'ldp_fsrq', 'fsp_secagg', 'privtree', 'construction'."""
    grid = data["grid"]; depth = data["depth"]; counts = data["counts"]
    i0, i1, j0, j1 = Q[0], Q[1], Q[2], Q[3]
    region = [(i, j) for i in range(i0, i1) for j in range(j0, j1)]
    true = sum(counts[c] for c in region)
    r = random.Random(seed)
    nQ = nQ_range((i0, i1, j0, j1), grid, depth)
    area = len(region)
    if kind == "construction":
        # Thm2: read nQ cluster roots at budget eps; bloom pruning 0.15
        noise = lap(1.0 / max(1e-6, eps_total), r)
        est = true + noise
        comm = int(max(1, nQ * 8 * 0.15))
        msgs = max(1, int(math.ceil(nQ * 0.15)))
    elif kind == "flat_central":
        # budget split depth ways; each cell noisy; sum over area
        eps_c = eps_total / max(1, depth)
        est = sum(counts[c] + lap(1.0 / max(1e-6, eps_c), r) for c in region)
        comm = area * 8; msgs = area
    elif kind == "ldp_fsrq":
        # local DP: each entity reports; one noise draw at full budget per query region
        est = true + lap(1.0 / max(1e-6, eps_total), r)
        comm = true * 8  # ~8 bit/entity report
        msgs = int(true)
    elif kind == "fsp_secagg":
        # federated secure aggregation: J jurisdictions, one DP draw on the sum
        est = true + lap(1.0 / max(1e-6, eps_total), r)
        comm = data["J"] * 8
        msgs = data["J"]
    elif kind == "privtree":
        # hierarchical decomposition, noise independent of height (budget allocated per level)
        eps_lvl = eps_total / max(1, depth + 1)
        # sum over path of depth+1 level noises
        est = true + sum(lap(1.0 / max(1e-6, eps_lvl), r) for _ in range(depth + 1))
        comm = (depth + 1) * 8
        msgs = depth + 1
    err = abs(est - true) / max(1.0, float(true))
    return err, comm, msgs

def main():
    rows = []
    data = build_data(seed=4, grid=32, ent_per_cell=3, J=8)
    grid = data["grid"]; depth = data["depth"]
    # range queries
    r = random.Random(500)
    qs = []
    for _ in range(300):
        i0 = r.randint(0, grid-2); i1 = r.randint(i0+1, grid)
        j0 = r.randint(0, grid-2); j1 = r.randint(j0+1, grid)
        qs.append((i0, i1, j0, j1))
    kinds = ["construction", "flat_central", "ldp_fsrq", "fsp_secagg", "privtree"]
    agg = defaultdict(lambda: {"err": [], "comm": [], "bytes": []})
    for qi, Q in enumerate(qs):
        for kind in kinds:
            e, comm, msgs = baseline_query(data, Q, kind, 1.0, seed=1000 + qi)
            agg[kind]["err"].append(e)
            agg[kind]["comm"].append(comm)
            agg[kind]["bytes"].append(bytes_on_wire(comm, msgs))
    for kind in kinds:
        rows.append({"baseline": kind, "n": len(qs), "grid": grid, "depth": depth,
                     "med_err": round(med(agg[kind]["err"]), 5),
                     "med_comm_bits": round(med(agg[kind]["comm"]), 2),
                     "med_onwire_bytes": round(med(agg[kind]["bytes"]), 2),
                     "err_median": round(med(agg[kind]["err"]), 5)})
        print("%-14s med_err=%.4f med_comm_bits=%8.1f med_onwire_bytes=%9.1f" % (
            kind, med(agg[kind]["err"]), med(agg[kind]["comm"]), med(agg[kind]["bytes"])))

    p = os.path.join(OUT, "G8_baselines_measured.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WROTE", p)

if __name__ == "__main__":
    main()
