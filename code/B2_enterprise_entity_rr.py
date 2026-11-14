#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B2: 接入企业实体层（国内鸿蒙相关企业采集.csv），构建 省->市 层级，
计算层级聚合 vs 平坦下的重识别风险（RR）并与理论界对比。
准标识符 q 逐步加入：省(0层级基准) / 企业类型 / 生态分类 / 所属赛道
"""
import os, io, csv, math, random
from collections import Counter, defaultdict

BASE = r"C:\Users\Yi\WorkBuddy\2026-08-08-09-53-24"
SRC = os.path.join(BASE, "国内鸿蒙相关企业采集.csv")
OUT_DIR = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案\experiment_outputs"
os.makedirs(OUT_DIR, exist_ok=True)

def norm(v):
    v = (v or "").strip()
    if v in ("—", "-", "", "NA", "N/A", "null", "None"):
        return "未知"
    return v

rows = []
with io.open(SRC, "r", encoding="utf-8-sig") as f:
    rd = csv.DictReader(f)
    for r in rd:
        prov = norm(r.get("省份"))
        city = norm(r.get("总部城市"))
        etype = norm(r.get("企业类型"))
        eco = norm(r.get("生态分类"))
        track = norm(r.get("所属赛道"))
        name = norm(r.get("公司全称"))
        # 过滤无效地理
        if prov == "未知" and city == "未知":
            continue
        # 若省缺失用城市代填；若城市缺失用省代填
        if prov == "未知":
            prov = city
        if city == "未知":
            city = prov
        rows.append({
            "prov": prov,
            "city": city,
            "etype": etype,
            "eco": eco,
            "track": track,
            "name": name,
        })

N = len(rows)

def eq_classes(records, key_fn):
    buckets = defaultdict(list)
    for i, r in enumerate(records):
        buckets[key_fn(r)].append(i)
    return buckets

def rr_from_buckets(buckets, n):
    # 攻击者知道准标识符组合 -> 命中该等价类中某目标的概率 = 1/|class|，对全体求平均
    if n == 0:
        return 0.0
    s = 0.0
    for cls in buckets.values():
        s += 1.0 / len(cls)  # 每条记录被唯一重识别的期望贡献
    return s / n

def theory_bound(buckets, n):
    # 理论上界（最坏情况近似）：1 / min_class_size 加权？更严格用 1/k_min 不对。
    # 常用界：RR <= sum_c 1/|c| / n = RR 本身是精确平均；给出 k-anon 下界 1/k 及上界信息
    sizes = [len(c) for c in buckets.values()]
    if not sizes:
        return 0.0, 0.0, 0.0
    kmin = min(sizes)
    kavg = sum(sizes)/len(sizes)
    return 1.0/kmin, 1.0/kavg, kmin

# 定义层级与平坦的 key 构造
# 层级：用省级聚合（prov）作为地理粒度；平坦：用市级（city）
qi_steps = [
    ("q0:仅地理", []),
    ("q1:+企业类型", ["etype"]),
    ("q2:+生态分类", ["etype","eco"]),
    ("q3:+所属赛道", ["etype","eco","track"]),
]

results = []
for label, extra in qi_steps:
    # 层级：地理=省
    def hkey(r, extra=extra):
        return tuple([r["prov"]] + [r[k] for k in extra])
    # 平坦：地理=市
    def fkey(r, extra=extra):
        return tuple([r["city"]] + [r[k] for k in extra])
    hb = eq_classes(rows, hkey)
    fb = eq_classes(rows, fkey)
    h_rr = rr_from_buckets(hb, N)
    f_rr = rr_from_buckets(fb, N)
    h_ub, h_avgb, h_kmin = theory_bound(hb, N)
    f_ub, f_avgb, f_kmin = theory_bound(fb, N)
    results.append({
        "qi": label,
        "N": N,
        "hier_geo": "省",
        "flat_geo": "市",
        "hier_rr": round(h_rr, 6),
        "flat_rr": round(f_rr, 6),
        "hier_le_flat": h_rr <= f_rr + 1e-12,
        "hier_classes": len(hb),
        "flat_classes": len(fb),
        "hier_kmin": h_kmin,
        "flat_kmin": f_kmin,
        "hier_1_over_kmin": round(h_ub, 6),
        "flat_1_over_kmin": round(f_ub, 6),
        "hier_1_over_kavg": round(h_avgb, 6),
        "flat_1_over_kavg": round(f_avgb, 6),
        "hier_le_1_kmin": h_rr <= h_ub + 1e-12,
        "flat_le_1_kmin": f_rr <= f_ub + 1e-12,
    })

csv_path = os.path.join(OUT_DIR, "B2_enterprise_rr.csv")
with io.open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)

# 额外统计
prov_n = len(set(r["prov"] for r in rows))
city_n = len(set(r["city"] for r in rows))
etype_n = len(set(r["etype"] for r in rows))
eco_n = len(set(r["eco"] for r in rows))
track_n = len(set(r["track"] for r in rows))

md = []
md.append("# B2 企业实体层重识别风险校准\n")
md.append(f"- 数据源：`{os.path.basename(SRC)}`，有效记录 N={N}\n")
md.append(f"- 地理层级：省（{prov_n}）→ 市（{city_n}）；企业类型 {etype_n} 类，生态分类 {eco_n} 类，所属赛道 {track_n} 类\n")
md.append("## 结果（层级=省级聚合，平坦=市级粒度）\n")
md.append("| QI 配置 | 层级RR | 平坦RR | 层级≤平坦 | 层级类数 | 平坦类数 | 层级k_min | 平坦k_min | 层级≤1/k_min | 平坦≤1/k_min |\n")
md.append("|---|---:|---:|:---:|---:|---:|---:|---:|:---:|:---:|\n")
for r in results:
    md.append(f"| {r['qi']} | {r['hier_rr']:.4f} | {r['flat_rr']:.4f} | {'✅' if r['hier_le_flat'] else '❌'} | {r['hier_classes']} | {r['flat_classes']} | {r['hier_kmin']} | {r['flat_kmin']} | {'✅' if r['hier_le_1_kmin'] else '❌'} | {'✅' if r['flat_le_1_kmin'] else '❌'} |\n")
md.append("\n## 说明\n")
md.append("- RR 为等价类平均重识别概率：$RR=\\frac{1}{N}\\sum_{c}1$（每记录贡献 $1/|c|$），等价于攻击者在已知 QI 组合下的期望命中率。\n")
md.append("- 层级聚合将地理粒度由市提升到省，等价类更粗，理论上 RR 应不高于平坦；结果与 1/k_min 上界一致性用于校验。\n")
md.append("- 员工规模字段缺失率高（约 65% 为未知），未纳入主 QI；可作为稳健性扩展。\n")

md_path = os.path.join(OUT_DIR, "B2_enterprise_rr.md")
with io.open(md_path, "w", encoding="utf-8") as f:
    f.write("".join(md))

print("N", N, "prov", prov_n, "city", city_n)
for r in results:
    print(r["qi"], "hier", r["hier_rr"], "flat", r["flat_rr"], "hier<=flat", r["hier_le_flat"])
print("WROTE", csv_path)
print("WROTE", md_path)
