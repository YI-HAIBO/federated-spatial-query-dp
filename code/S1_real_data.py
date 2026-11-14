# -*- coding: utf-8 -*-
"""
S1 真实数据接入：智联招聘真实岗位 CSV → 实体层 + linkage attack 校准
======================================================================
把真实招聘数据（岗位记录 + 地理 + 行业 + 规模）接入本项目实体层，做层级 vs 平坦重识别校准。
数据源：`智能体招聘_智联_深圳_20260816/智能体招聘_智联_深圳_合并.csv`（200 条真实岗位）
准标识符：行政区域(层级) / 街道(平坦) + 学历 + 企业规模 + 行业  (F3:攻击者至多掌握 q 个准标识符)
输出 experiment_outputs/S1_real_*.csv；缺失数据时自动合成兜底。
"""
import io, os, csv, math
from collections import Counter, defaultdict

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_outputs")
os.makedirs(OUT, exist_ok=True)

# 真实数据源（优先探测存在的路径）
REAL_CANDIDATES = [
    r"C:\Users\Yi\WorkBuddy\2026-08-16-07-44-50\智能体招聘_智联_深圳_20260816\智能体招聘_智联_深圳_合并.csv",
    r"C:\Users\Yi\WorkBuddy\2026-08-16-07-44-50\智能体招聘_猎聘_20260816\智能体招聘_猎聘_合并.csv",
]
REAL_PATH = next((p for p in REAL_CANDIDATES if os.path.exists(p)), None)

def load_real(path):
    """读真实招聘 CSV，清洗后返回 entity 列表。
    entity = dict(type='job', eid, region_city, region_district, region_street,
                  edu, size, industry, job_title)"""
    entities = []
    with io.open(path, "r", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        eid = 0
        for row in rd:
            # 字段可能含空白/重复，用 get 并清洗
            city = (row.get("城市") or "").strip()
            district = (row.get("行政区域") or "").strip()
            street = (row.get("街道区域") or "").strip()
            edu = (row.get("学历") or "").strip()
            size = (row.get("企业人数规模") or "").strip()
            ind = (row.get("行业业务") or "").strip()
            title = (row.get("岗位名称") or "").strip()
            if not (city or district or street):
                continue
            # 规模字段清洗（可能含拼接多余信息，取第一段）
            size_clean = size.split()[0] if size else "未知"
            entities.append({
                "type": "job", "eid": eid,
                "city": city, "district": district, "street": street,
                "edu": edu if edu else "学历不限", "size": size_clean,
                "industry": ind if ind else "未知",
                "job_title": title or "未知岗位",
            })
            eid += 1
    return entities

def synth_fallback(n=200, seed=0):
    """无真实数据时合成兜底（结构同真实）"""
    import random
    r = random.Random(seed)
    districts = ["南山","宝安","福田","龙华","龙岗","光明","罗湖","坪山","盐田","大鹏"]
    streets = ["粤海","西乡","南山","西丽","福城","新安","香蜜湖","梅林","松岗","笋岗"]
    sizes = ["20-99人","100-299人","10000人以上","20人以下","500-999人"]
    inds = ["软件/IT服务","人力资源","半导体/芯片","消费电子/智能硬件","人工智能"]
    edus = ["学历不限","大专","本科"]
    out = []
    for i in range(n):
        d = r.choice(districts)
        out.append({
            "type":"job","eid":i,"city":"深圳","district":d,
            "street":r.choice(streets),"edu":r.choice(edus),
            "size":r.choice(sizes),"industry":r.choice(inds),
            "job_title":"岗位%d"%i,
        })
    return out

# ---------- RR 校准 ----------
def rdf(entities, region_fn, quasi_id_fn, q):
    """重识别率：攻击者掌握 q 个准标识符属性。region_fn(e)->区域码；quasi_id_fn(e)->(q个准标识符)"""
    groups = defaultdict(list)
    for e in entities:
        key = (region_fn(e),) + quasi_id_fn(e, q)
        groups[key].append(e["eid"])
    total = len(entities)
    unique = sum(1 for k, v in groups.items() if len(v) == 1)
    return unique / total if total else 0.0

def quasi_id(e, q):
    """按 q 选择准标识符：0=无(仅区域),1=+行业,2=+行业+规模,3=+行业+规模+学历"""
    fields = [("industry", e["industry"]), ("size", e["size"]), ("edu", e["edu"])]
    if q <= 0:
        return ()
    return tuple(v for _, v in fields[:q])

def main():
    if REAL_PATH:
        entities = load_real(REAL_PATH)
        src = "REAL:" + os.path.basename(os.path.dirname(REAL_PATH))
    else:
        entities = synth_fallback(200)
        src = "SYNTH(fallback)"

    n = len(entities)
    hier_region = lambda e: ("dst", e["district"])        # 层级：行政区(粗)
    flat_region = lambda e: ("st", e["district"], e["street"])  # 平坦：街道(细)

    # 理论后验界（ε=1 精确DP界）
    eps = 1.0
    pi = math.exp(eps) / (1.0 + math.exp(eps))

    print("数据源:", src, "| 实体数:", n)
    rows = []
    for q in [0, 1, 2, 3]:   # 攻击者掌握 QI 个数
        rr_hier = rdf(entities, hier_region, quasi_id, q)
        rr_flat = rdf(entities, flat_region, quasi_id, q)
        rows.append({"source": src, "q_quasi_id": q, "n_entities": n,
                     "rr_hierarchical": round(rr_hier, 4),
                     "rr_flat": round(rr_flat, 4),
                     "theory_bound_e1": round(pi, 4),
                     "hier_le_bound": rr_hier <= pi})
        print("  q=%d 层级RR=%.3f 平坦RR=%.3f (界=%.3f) 层级≤界:%s"
              % (q, rr_hier, rr_flat, pi, rr_hier <= pi))

    # 写 CSV
    path = os.path.join(OUT, "S1_real_rr.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # 实体层统计
    stats_path = os.path.join(OUT, "S1_real_stats.csv")
    with open(stats_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["source", src]); w.writerow(["entities", n])
        w.writerow(["districts", len({e["district"] for e in entities if e["district"]})])
        w.writerow(["streets", len({e["street"] for e in entities if e["street"]})])
        for k, v in Counter(e["industry"] for e in entities).most_common(8):
            w.writerow(["ind_" + k, v])
        for k, v in Counter(e["size"] for e in entities).most_common(8):
            w.writerow(["size_" + k, v])
        for k, v in Counter(e["edu"] for e in entities).most_common(8):
            w.writerow(["edu_" + k, v])

    print("WRITTEN:", path, stats_path)
    return {"src": src, "n": n, "rows": rows, "path": path}

if __name__ == "__main__":
    main()