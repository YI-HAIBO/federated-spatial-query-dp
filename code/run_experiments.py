# -*- coding: utf-8 -*-
"""
选题方案07 实验脚本 E0-E5（可运行，无真实数据时用合成数据兜底）
用途：演示/验证实验协议 7.7 的可执行性；产出 CSV 到 experiment_outputs/。
依赖：仅标准库（random, math, csv, statistics, os）。
真实数据接入：见 README.md（用 dr5hn 仓库 JSON + 企查查/招聘实体层替换 e0 的合成部分）。
"""
import os, csv, math, random, statistics, sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_outputs")
SEEDS = [0, 1, 2, 3, 4]

def rng(seed):
    return random.Random(seed)

def lap(b, r):
    u = r.random() - 0.5
    if abs(u) < 1e-12:
        return 0.0
    return -b * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u))

# ---------------- E0: 合成层级树 + 实体层 + 管辖区 ----------------
def e0(seed=0, countries=3, states_per=3, cities_per=10, entities_per_city=6, J=4):
    r = rng(seed)
    tree = []          # (level, cid, sid, city_id, name, lat, lon, timezone, currency)
    entities = []      # (entity_id, city_id, industry, size_bucket, timezone)
    eid = 0
    for c in range(countries):
        tz = "UTC+%d" % (c % 5)
        cur = "CUR%d" % c
        for s in range(states_per):
            for ci in range(cities_per):
                cid = (c, s, ci)
                lat = r.uniform(-60, 70)
                lon = r.uniform(-180, 180)
                tree.append((0, c, s, ci, "country%d" % c, lat, lon, tz, cur))
                tree.append((1, c, s, ci, "state%d_%d" % (c, s), lat, lon, tz, cur))
                tree.append((2, c, s, ci, "city%d_%d_%d" % (c, s, ci), lat, lon, tz, cur))
                for _ in range(entities_per_city):
                    industry = r.choice(["IT", "MFG", "RET", "FIN", "EDU"])
                    size = r.choice(["S", "M", "L"])
                    entities.append((eid, cid, industry, size, tz))
                    eid += 1
    # 按国家划分为 J 个管辖区（合成：按国家取模）
    parts = {j: [] for j in range(J)}
    for c in range(countries):
        parts[c % J].append(c)
    # 统计
    n_city = countries * states_per * cities_per
    stats = {
        "countries": countries, "states": countries * states_per, "cities": n_city,
        "entities": len(entities), "J": J,
        "entities_per_city": entities_per_city,
        "jurisdiction_countries": {str(j): len(v) for j, v in parts.items()},
        "industry_dist": {ind: sum(1 for e in entities if e[2] == ind) for ind in ["IT", "MFG", "RET", "FIN", "EDU"]},
        "same_name_city_ratio": 0.0,
        "missing_coord_ratio": 0.0,
    }
    return tree, entities, parts, stats

# ---------------- E1: 重识别实证校准（层级 vs 平坦） ----------------
def _rr(entities, region_fn):
    """region_fn(e)->区域码；唯一可链接比例"""
    from collections import defaultdict
    groups = defaultdict(list)
    for e in entities:
        key = (region_fn(e), e[2], e[3], e[4])   # 区域+行业+规模+时区 准标识符
        groups[key].append(e[0])
    total = len(entities)
    unique = sum(1 for k, v in groups.items() if len(v) == 1)
    return unique / total

def e1(seed=0, tree=None, entities=None, eps_list=None):
    if tree is None:
        tree, entities, _, _ = e0(seed=seed)
    eps_list = eps_list or [0.1, 0.5, 1.0, 2.0, 4.0]
    # 层级：区域=省州（较粗）；平坦：区域=城市（较细）
    def hier_region(e):
        c, s, ci = e[1]
        return ("st", c, s)
    def flat_region(e):
        return ("ci", e[1])
    rr_hier = _rr(entities, hier_region)
    rr_flat = _rr(entities, flat_region)
    rows = []
    for eps in eps_list:
        pi = math.exp(eps) / (1.0 + math.exp(eps))   # 理论后验界
        rows.append((eps, rr_hier, rr_flat, pi))
    path = os.path.join(OUT, "E1_rr_curve.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["epsilon", "rr_hierarchical", "rr_flat", "theory_bound"])
        for row in rows:
            w.writerow(row)
    return {"path": path, "rr_hier": rr_hier, "rr_flat": rr_flat,
            "bound_ok_hier": rr_hier <= max(r[3] for r in rows)}

# ---------------- E2: 预算分配/分支因子/约束推断复现 ----------------
def _noisy_counts(leaf_counts, b, eps, allocation, use_ci, r):
    """按分支因子 b 建平衡树，层级加噪，可选约束推断；返回叶子相对误差"""
    # 简化：把城市(叶子)分成高度 h=log_b(叶子数) 层，每层分配 eps_l
    n = len(leaf_counts)
    levels = max(1, int(round(math.log(n, b))) if n > 1 else 1)
    if allocation == "uniform":
        eps_per = [eps / levels] * levels
    else:  # known-optimal ~ sqrt(f_l * Delta_l)，合成假设 f_l 均匀 => 各层相等但加权
        eps_per = [eps * (2 ** (l - levels)) / sum(2 ** (l - levels) for l in range(1, levels + 1)) for l in range(1, levels + 1)]
    # 顶层加噪（合成：叶子计数，父=子和）
    noisy = [max(0.0, v + lap(1.0 / eps_per[0], r)) for v in leaf_counts]
    if use_ci:
        # 简易均值一致：把每层噪声向"父均值"收缩一次（演示）
        m = sum(noisy) / len(noisy)
        noisy = [0.5 * v + 0.5 * m for v in noisy]
    true = leaf_counts
    err = [abs(noisy[i] - true[i]) / max(1, true[i]) for i in range(n)]
    return statistics.mean(err)

def e2(seed=0, tree=None, entities=None, eps=1.0):
    if tree is None:
        tree, entities, _, _ = e0(seed=seed)
    from collections import Counter
    cc = Counter(e[1] for e in entities)
    leaf_counts = [cc[c] for c in sorted(cc)]
    r = rng(seed)
    rows = []
    for alloc in ["uniform", "optimal"]:
        for b in [2, 4, 8]:
            for ci in [False, True]:
                rel = _noisy_counts(leaf_counts, b, eps, alloc, ci, r)
                rows.append((alloc, b, ci, round(rel, 5)))
    path = os.path.join(OUT, "E2_allocation.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["allocation", "branching", "constrained_inference", "relative_error"])
        w.writerows(rows)
    best = min(rows, key=lambda x: x[3])
    return {"path": path, "best": best}

# ---------------- E3: ε—通信—效用权衡 ----------------
def e3(seed=0, J=4, n=None, eps_list=None, alpha_list=None):
    if n is None:
        _, _, _, stats = e0(seed=seed)
        n = stats["entities"]
    eps_list = eps_list or [0.1, 0.5, 1.0, 2.0, 4.0]
    alpha_list = alpha_list or [0.05, 0.1, 0.2, 0.5]
    rows = []
    for eps in eps_list:
        # 极端1：本地DP（每辖区O(1)消息），误差 ~ sqrt(J)/eps
        err_local = math.sqrt(J) / eps
        # 极端2：汇总通信（近似中央），误差 ~ 1/eps，通信 ~ n 条
        comm_local = J
        comm_central = n
        for alpha in alpha_list:
            feasible_local = err_local <= alpha
            # 候选下界（量级示意）：Omega(J log N + k/B + min(n, J/(eps^2 alpha^2)))
            g = min(n, J / (eps * eps * alpha * alpha)) if not feasible_local else 0.0
            lb = J + g   # 忽略 logN/k/B 量级（合成）
            ratio = (comm_central / max(1, lb)) if not feasible_local else (comm_local / max(1, lb))
            rows.append((eps, alpha, err_local, feasible_local, comm_local, comm_central, round(lb, 3), round(ratio, 3)))
    path = os.path.join(OUT, "E3_tradeoff.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["epsilon", "alpha", "local_error", "local_feasible", "comm_local", "comm_central", "candidate_lb", "ratio"])
        w.writerows(rows)
    return {"path": path, "rows": len(rows)}

# ---------------- E4: 近最优构造 vs 基线（消融简版） ----------------
def e4(seed=0, J=4):
    tree, entities, parts, stats = e0(seed=seed)
    n = stats["entities"]
    eps = 1.0
    r = rng(seed)
    # 基线：集中式明文（误差0, 通信 n）
    # 集中式DP（均匀eps，中央）：误差 ~ 1/eps，通信 n
    # 本地DP：误差 ~ sqrt(J)/eps，通信 J
    # 构造（定理2）：本地加噪+一致性+R树路由+布隆，误差 ~ sqrt(J)/eps，通信 ~ J logN + k/B
    err_plain, comm_plain = 0.0, n
    err_central, comm_central = 1.0 / eps, n
    err_local, comm_local = math.sqrt(J) / eps, J
    N = stats["cities"]
    k = int(0.1 * n)
    err_constr, comm_constr = math.sqrt(J) / eps, J * (math.log(N) + 1) + k
    rows = [
        ("central_plaintext", err_plain, comm_plain),
        ("central_dp_uniform", err_central, comm_central),
        ("local_dp", err_local, comm_local),
        ("construction_thm2", err_constr, comm_constr),
    ]
    path = os.path.join(OUT, "E4_baselines.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["variant", "error", "communication"])
        w.writerows(rows)
    return {"path": path, "rows": rows}

# ---------------- E5: 可扩展性（J 与 N） ----------------
def e5(seed=0):
    rows = []
    for J in [4, 8, 16]:
        for C in [3, 6]:
            tree, entities, parts, stats = e0(seed=seed, countries=C, states_per=3, cities_per=10,
                                              entities_per_city=6, J=J)
            N = stats["cities"]
            comm = J * (math.log(N) + 1)
            rows.append((J, C, N, stats["entities"], round(comm, 2)))
    path = os.path.join(OUT, "E5_scaling.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["J", "countries", "cities", "entities", "comm_routing"])
        w.writerows(rows)
    return {"path": path, "rows": len(rows)}

# ---------------- main ----------------
def main():
    os.makedirs(OUT, exist_ok=True)
    print("== E0 ==")
    tree, entities, parts, stats = e0(seed=0)
    print("  tree nodes=%d entities=%d J=%d" % (len(tree), stats["entities"], stats["J"]))
    print("== E1 ==")
    r1 = e1(seed=0, tree=tree, entities=entities)
    print("  RR hier=%.4f flat=%.4f bound_ok=%s" % (r1["rr_hier"], r1["rr_flat"], r1["bound_ok_hier"]))
    print("== E2 ==")
    r2 = e2(seed=0, tree=tree, entities=entities)
    print("  best=%s" % (r2["best"],))
    print("== E3 ==")
    r3 = e3(seed=0)
    print("  rows=%d" % r3["rows"])
    print("== E4 ==")
    r4 = e4(seed=0)
    print("  variants=%d" % len(r4["rows"]))
    print("== E5 ==")
    r5 = e5(seed=0)
    print("  rows=%d" % r5["rows"])
    print("OUTPUTS DIR:", OUT)

if __name__ == "__main__":
    main()
