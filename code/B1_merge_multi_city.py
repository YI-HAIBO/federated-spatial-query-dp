# -*- coding: utf-8 -*-
"""
B1 多市招聘数据合并 + 多管辖区 RR 校准
========================================
扫描「智联招聘鸿蒙岗位抽样_*.csv」多市文件，用灵活列检测统一解析不同 schema，
从 城市/区/区域 字段提取三级空间（市·区·街道），构建多管辖区实体层，
跑 层级(行政区) vs 平坦(街道) 重识别 RR 校准。
全部标准库。输出 experiment_outputs/B1_multi_city_*.csv。
"""
import io, os, csv, math, glob
from collections import Counter, defaultdict

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_outputs")
os.makedirs(OUT, exist_ok=True)

SRC_DIR = r"C:\Users\Yi\WorkBuddy\2026-08-08-09-53-24"
# 只看各市岗位抽样（排除 _merged/glossary/企业采集/regression 等）
INCLUDE_PAT = "*智联招聘鸿蒙岗位抽样_*.csv"

def pick_col(candidate_cols, keys):
    """按中文关键词从候选列名匹配：返回匹配列名或 None"""
    for c in candidate_cols:
        cc = c.strip()
        for k in keys:
            if k in cc:
                return c
    return None

def parse_city_loc(city_str, district_str):
    """从 城市/区 字段提取 (city, district, street) 三级。
    城市字段常为『北京·海淀·中关村』，或城市+区各单独字段。"""
    city = district = street = ""
    # 尝试从 city 字段拆分（· / 空格 分隔）
    for sep in ["·", "·", "/", " "]:
        if sep and sep in city_str:
            parts = [x for x in city_str.split(sep) if x]
            if len(parts) >= 3:
                city, district, street = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                city, district = parts[0], parts[1]
            else:
                city = parts[0]
            break
    else:
        city = city_str
    # 若 district 字段单独给出且更具体，优先用之
    if district_str and (not district or district_str not in city_str):
        district = district_str
    # 清理
    return (city.strip(), district.strip(), street.strip())

def load_all():
    files = sorted(glob.glob(os.path.join(SRC_DIR, INCLUDE_PAT)))
    entities = []
    per_file = {}
    for p in files:
        fname = os.path.basename(p)
        try:
            ents = len(entities)
            with io.open(p, "r", encoding="utf-8-sig") as f:
                rd = csv.reader(f)
                header = next(rd, None)
                if not header:
                    continue
                # 建立 列名→索引
                idx = {h.strip(): i for i, h in enumerate(header)}
                fields = list(idx.keys())
                c_city = pick_col(fields, ["城市", "城市片区", "工作地点", "城市·区"])
                c_dist = pick_col(fields, ["区", "行政区", "区域", "城市片区"])
                c_street = pick_col(fields, ["街道", "街道区域"])
                c_edu = pick_col(fields, ["学历"])
                c_exp = pick_col(fields, ["经验", "工作经验"])
                c_title = pick_col(fields, ["岗位名称", "岗位名", "岗位", "职位"])
                c_comp = pick_col(fields, ["公司", "企业名称"])
                # 若城市字段缺失但有个别"城市·区"合并含区，降级
                for row in rd:
                    def g(col):
                        return row[idx[col]].strip() if col in idx else ""
                    city_raw = g(c_city) if c_city else ""
                    dist_raw = g(c_dist) if c_dist else ""
                    street_raw = g(c_street) if c_street else ""
                    city, district, street = parse_city_loc(city_raw, dist_raw)
                    if not street and street_raw:
                        street = street_raw
                    edu = g(c_edu) if c_edu else ""
                    exp = g(c_exp) if c_exp else ""
                    title = g(c_title) if c_title else ""
                    comp = g(c_comp) if c_comp else ""
                    if not (city or district or street):
                        continue
                    entities.append({
                        "src": fname, "city": city, "district": district, "street": street,
                        "edu": edu or "学历不限", "exp": exp or "经验不限",
                        "title": title or "", "company": comp or "",
                    })
            per_file[fname] = len(entities) - ents
        except Exception as e:
            per_file[fname] = -1
    return entities, per_file

def rdf(entities, region_fn, qi):
    """重识别率：按区域+准标识符(q个属性)分组，统计唯一可链接比例"""
    groups = defaultdict(list)
    for e in entities:
        key = (region_fn(e),)
        if qi >= 1:
            key += (e["edu"],)
        if qi >= 2:
            key += (e["exp"],)
        if qi >= 3:
            key += (e["title"],)
        groups[key].append(id(e))
    total = len(entities)
    unique = sum(1 for v in groups.values() if len(v) == 1)
    return unique / total if total else 0.0

def main():
    entities, per_file = load_all()
    n = len(entities)
    print("总实体(岗位记录)数:", n)
    print("文件数:", len(per_file), "| 每文件条数:", per_file)

    # 多管辖区统计
    city_cnt = Counter(e["city"] for e in entities if e["city"])
    dist_cnt = Counter((e["city"], e["district"]) for e in entities if e["district"])
    print("城市数:", len(city_cnt), "TOP:", city_cnt.most_common(12))
    print("(城市,行政区)组合数:", len(dist_cnt))

    # RR 校准：层级(行政区) vs 平坦(街道)，q 准标识符
    hier = lambda e: ("d", e["city"], e["district"])
    flat = lambda e: ("s", e["city"], e["district"], e["street"])
    eps = 1.0
    pi = math.exp(eps) / (1.0 + math.exp(eps))
    rows = []
    for q in [0, 1, 2, 3]:
        rr_hier = rdf(entities, hier, q)
        rr_flat = rdf(entities, flat, q)
        rows.append({"n_entities": n, "q_quasi_id": q,
                     "rr_hierarchical": round(rr_hier, 4),
                     "rr_flat": round(rr_flat, 4),
                     "theory_bound_e1": round(pi, 4),
                     "hier_le_bound": rr_hier <= pi})
        print("  q=%d 层级RR=%.3f 平坦RR=%.3f (界=%.3f) 层级≤界:%s"
              % (q, rr_hier, rr_flat, pi, rr_hier <= pi))

    path = os.path.join(OUT, "B1_multi_city_rr.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # 每文件计数
    pstat_path = os.path.join(OUT, "B1_multi_city_files.csv")
    with open(pstat_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["file", "entities"])
        for k, v in sorted(per_file.items()):
            w.writerow([k, v])

    print("WRITTEN:", path, pstat_path)
    return rows

if __name__ == "__main__":
    main()