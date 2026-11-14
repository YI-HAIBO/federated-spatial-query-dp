# -*- coding: utf-8 -*-
"""
S1 实体层构建 + linkage attack 评估（可运行，合成兜底）
========================================================
对应方案 7.7 E0 增补 + S1 里程碑：
  1. 实体层构建（E0 扩展）：企业/岗位实体 + 准标识符（区域+时区+行业+规模+上级节点）
  2. 管辖区切分（J）
  3. linkage attack：用准标识符合并，统计唯一可链接比例 RDF（定义 3 的 RR）
  4. 层级 vs 平坦 校准（E1 复用），并与已知后验界 pi(y)<=e^eps/(1+e^eps) 对比
真实数据接入：用企查查/招聘 CSV 替换 build_entities 的合成部分（见 load_real_entities）。
输出 experiment_outputs/S1_entity_layer.csv 与 RR 结果。
"""
import os, csv, math, random, statistics
from collections import defaultdict

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_outputs")
os.makedirs(OUT, exist_ok=True)

def rng(seed):
    return random.Random(seed)

# ---------- 实体层构建（合成兜底） ----------
def build_entities(seed=0, countries=3, states_per=3, cities_per=10, ent_per_city=4):
    """返回 entity 列表: (eid, (country,state,city), industry, size_bucket, timezone, jid)"""
    r = rng(seed)
    entities = []
    eid = 0
    for c in range(countries):
        tz = "UTC+%d" % (c % 5)
        for s in range(states_per):
            for ci in range(cities_per):
                loc = (c, s, ci)
                for _ in range(ent_per_city):
                    industry = r.choice(["IT", "MFG", "RET", "FIN", "EDU"])
                    size = r.choice(["S", "M", "L"])
                    entities.append((eid, loc, industry, size, tz))
                    eid += 1
    return entities

def load_real_entities(path):
    """接入企查查/招聘 CSV（真实数据接口）。列：eid,country,state,city,industry,size,timezone。
    若不可用，返回 None，调用方用 build_entities 兜底。"""
    try:
        entities = []
        with open(path, "r", encoding="utf-8") as f:
            rd = csv.reader(f)
            next(rd, None)
            for row in rd:
                if len(row) < 7:
                    continue
                eid = int(row[0]); c = int(row[1]); s = int(row[2]); ci = int(row[3])
                ind = row[4]; size = row[5]; tz = row[6]
                entities.append((eid, (c, s, ci), ind, size, tz))
        return entities or None
    except Exception:
        return None

# ---------- 管辖区切分 ----------
def partition(entities, J):
    """按国家取模分 J 个管辖区；返回 entity→jid 映射（可为外部先验，模拟不同辖区持数据）。"""
    # 模拟：某实体的"所在辖区"由 auth 指定；这里按国家归属
    jid_map = {}
    for (eid, (c, s, ci), ind, size, tz) in entities:
        jid_map[eid] = c % J
    return jid_map

# ---------- linkage attack / RDF ----------
def rdf(entities, region_fn, jid_map=None, prior=False):
    """重识别率 RR：按准标识符（区域+行业+规模+时区）分组，统计唯一可链接比例。
    jid_map 若给，则加入"辖区"作外部先验（攻击者知道实体所在辖区）。"""
    groups = defaultdict(list)
    for (eid, (c, s, ci), ind, size, tz) in entities:
        key = (region_fn((c, s, ci)), ind, size, tz)
        if jid_map is not None:
            key = (jid_map[eid],) + key
        groups[key].append(eid)
    total = len(entities)
    unique = sum(1 for k, v in groups.items() if len(v) == 1)
    return unique / total if total else 0.0

def main():
    entities = build_entities(seed=0)
    n = len(entities)
    # 区域函数：层级（省州）vs 平坦（城市）
    hier = lambda loc: ("st", loc[0], loc[1])
    flat = lambda loc: ("ci", loc)
    # RR：无辖区先验
    rr_hier = rdf(entities, hier)
    rr_flat = rdf(entities, flat)
    # RR：有辖区先验（攻击者知道实体在哪个管辖区）
    jid = partition(entities, J=4)
    rr_hier_prior = rdf(entities, hier, jid)
    rr_flat_prior = rdf(entities, flat, jid)

    # 已知后验界对比（面向级联查询的 DP 后验界）
    eps = 1.0
    pi_bound = math.exp(eps) / (1.0 + math.exp(eps))

    rows = [
        {"region": "hierarchical(省州)", "prior": "none", "RR": round(rr_hier, 4), "theory_bound_e1": None},
        {"region": "flat(城市)", "prior": "none", "RR": round(rr_flat, 4), "theory_bound_e1": None},
        {"region": "hierarchical(省州)", "prior": "jurisdiction", "RR": round(rr_hier_prior, 4), "theory_bound_e1": pi_bound},
        {"region": "flat(城市)", "prior": "jurisdiction", "RR": round(rr_flat_prior, 4), "theory_bound_e1": pi_bound},
    ]
    path = os.path.join(OUT, "S1_entity_layer.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["region", "prior", "RR", "theory_bound_e1"])
        w.writeheader()
        w.writerows(rows)

    # 附带实体层统计
    stats_path = os.path.join(OUT, "S1_entity_stats.csv")
    ind_dist = defaultdict(int); size_dist = defaultdict(int)
    for (eid, loc, ind, size, tz) in entities:
        ind_dist[ind] += 1; size_dist[size] += 1
    with open(stats_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["entities", n])
        w.writerow(["cities", len({e[1] for e in entities})])
        for k in sorted(ind_dist):
            w.writerow(["ind_" + k, ind_dist[k]])
        for k in sorted(size_dist):
            w.writerow(["size_" + k, size_dist[k]])

    summary = {
        "entities": n,
        "rr_hier": rr_hier, "rr_flat": rr_flat,
        "rr_hier_prior": rr_hier_prior, "rr_flat_prior": rr_flat_prior,
        "bound_ok_hier_prior": rr_hier_prior <= pi_bound,
        "path": path, "stats_path": stats_path,
    }
    print(summary)
    return summary

if __name__ == "__main__":
    main()