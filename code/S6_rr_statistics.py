# -*- coding: utf-8 -*-
"""S6: RR 校准的统计检验
对 S1(深圳200)/B1(多市647)/B2(企业346) 统一用"唯一识别实体占比"(0/1 可配对)定义，
做：层级 vs 平坦 的 McNemar 配对比例检验(精确二项) + Bootstrap 95% CI。
注: S1/B1 原 RR 即为唯一识别占比; B2 原 RR 为期望 1/|class| 定义,此处用唯一识别占比
统一重算以支持配对检验(正文保留各自原 RR,统计段落统一用本定义并注明)。
"""
import io, os, csv, math, random, glob
from collections import defaultdict, Counter

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案"
OUT = os.path.join(BASE, "experiment_outputs")

S1_PATH = r"C:\Users\Yi\WorkBuddy\2026-08-16-07-44-50\智能体招聘_智联_深圳_20260816\智能体招聘_智联_深圳_合并.csv"
B1_DIR = r"C:\Users\Yi\WorkBuddy\2026-08-08-09-53-24"
B2_PATH = os.path.join(B1_DIR, "国内鸿蒙相关企业采集.csv")

# ---------- 加载 ----------
def load_shenzhen(path):
    ents = []
    with io.open(path, "r", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f)):
            city = (row.get("城市") or "").strip()
            district = (row.get("行政区域") or "").strip()
            street = (row.get("街道区域") or "").strip()
            if not (city or district or street):
                continue
            ents.append({
                "city": city, "district": district, "street": street,
                "industry": (row.get("行业业务") or "").strip() or "未知",
                "size": ((row.get("企业人数规模") or "").strip().split()[0] if (row.get("企业人数规模") or "").strip() else "未知"),
                "edu": (row.get("学历") or "").strip() or "学历不限",
            })
    return ents

def load_multicity(srcdir):
    ents = []
    for p in sorted(glob.glob(os.path.join(srcdir, "*智联招聘鸿蒙岗位抽样_*.csv"))):
        with io.open(p, "r", encoding="utf-8-sig") as f:
            rd = csv.reader(f)
            header = next(rd, None)
            if not header:
                continue
            idx = {h.strip(): i for i, h in enumerate(header)}
            def pick(cols):
                for c in idx:
                    for k in cols:
                        if k in c:
                            return c
                return None
            c_city = pick(["城市", "城市片区", "工作地点", "城市·区"])
            c_dist = pick(["区", "行政区", "区域", "城市片区"])
            c_street = pick(["街道", "街道区域"])
            c_edu = pick(["学历"]); c_exp = pick(["经验", "工作经验"]); c_title = pick(["岗位名称", "岗位名", "岗位", "职位"])
            for row in rd:
                def g(c): return row[idx[c]].strip() if c and c in idx else ""
                city = district = street = ""
                cstr = g(c_city); dstr = g(c_dist)
                for sep in ["·", "·", "/", " "]:
                    if sep and sep in cstr:
                        parts = [x for x in cstr.split(sep) if x]
                        if len(parts) >= 3: city, district, street = parts[0], parts[1], parts[2]
                        elif len(parts) == 2: city, district = parts[0], parts[1]
                        else: city = parts[0]
                        break
                else:
                    city = cstr
                if dstr and (not district or dstr not in cstr):
                    district = dstr
                if not street and g(c_street):
                    street = g(c_street)
                if not (city or district or street):
                    continue
                ents.append({"city": city.strip(), "district": district.strip(), "street": street.strip(),
                             "edu": g(c_edu) or "学历不限", "exp": g(c_exp) or "经验不限", "title": g(c_title) or ""})
    return ents

def load_enterprise(path):
    ents = []
    def norm(v):
        v = (v or "").strip()
        return "未知" if v in ("—", "-", "", "NA", "N/A", "null", "None") else v
    with io.open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            prov = norm(row.get("省份")); city = norm(row.get("总部城市"))
            if prov == "未知" and city == "未知":
                continue
            if prov == "未知": prov = city
            if city == "未知": city = prov
            ents.append({"prov": prov, "city": city,
                         "etype": norm(row.get("企业类型")), "eco": norm(row.get("生态分类")),
                         "track": norm(row.get("所属赛道"))})
    return ents

# ---------- 唯一识别占比 + 配对检验 ----------
def keys_of(ents, region_fn, qid_fn):
    return [tuple(region_fn(e)) + tuple(qid_fn(e)) for e in ents]

def rr_from_keys(ks):
    if not ks: return 0.0
    cnt = Counter(ks)
    return sum(1 for k in ks if cnt[k] == 1) / len(ks)

def flags_from_keys(ks):
    cnt = Counter(ks)
    return [1 if cnt[k] == 1 else 0 for k in ks]

def mc_nemar_exact(h, f):
    """McNemar 配对: b=hier&~flat, c=~hier&flat; 精确二项 p=2*min(P(X<=m),P(X>=m)), X~Bin(n,0.5)"""
    b = sum(1 for x, y in zip(h, f) if x == 1 and y == 0)
    c = sum(1 for x, y in zip(h, f) if x == 0 and y == 1)
    n = b + c
    if n == 0:
        return b, c, 1.0
    from math import comb
    k = min(b, c)
    cdf = sum(comb(n, i) * 0.5 ** n for i in range(k + 1))
    p = min(1.0, 2 * cdf)
    return b, c, p

def bootstrap_ci(flags, n_iter=1000, seed=0):
    """非参数 bootstrap 95% CI（对 0/1 唯一识别指示量占比，比例口径）。
    NOTE(2026-11-12 V4-M1 修复)：原实现对"键"有放回重采样并在每个重采样内重算唯一性，
    有放回抽样会把单例"合并"，使分布系统性偏低、区间落在点估计下（21/24 行失效）。
    正确做法：对逐实体 0/1 指示量（比例）重采样，重采样内 1 的个数 ~ Binomial(N, p)，
    区间以点估计为中心，点估计必落在区间内。"""
    r = random.Random(seed); N = len(flags)
    p = sum(flags) / N
    vals = []
    for _ in range(n_iter):
        ones = random.binomialvariate(N, p)   # 精确二项抽样，O(1)
        vals.append(ones / N)
    vals.sort()
    return vals[int(0.025 * n_iter)], vals[int(0.975 * n_iter)]

def run_dataset(name, ents, hier_region, flat_region, qid_steps):
    rows = []
    for q, qid_fn in qid_steps:
        kh = keys_of(ents, hier_region, qid_fn)
        kf = keys_of(ents, flat_region, qid_fn)
        rh = rr_from_keys(kh); rf = rr_from_keys(kf)
        fh = flags_from_keys(kh); ff = flags_from_keys(kf)
        b, c, p = mc_nemar_exact(fh, ff)
        ch_lo, ch_hi = bootstrap_ci(fh)
        cf_lo, cf_hi = bootstrap_ci(ff)
        rows.append({"dataset": name, "q": q, "n": len(ents),
                     "rr_hier": round(rh, 4), "rr_flat": round(rf, 4),
                     "delta": round(rh - rf, 4),
                     "mc_b": b, "mc_c": c, "mc_p": round(p, 4),
                     "ci_hier_lo": round(ch_lo, 4), "ci_hier_hi": round(ch_hi, 4),
                     "ci_flat_lo": round(cf_lo, 4), "ci_flat_hi": round(cf_hi, 4)})
        print("  [%s] q=%d hier=%.4f flat=%.4f Δ=%.4f McNemar p=%.4f (b=%d,c=%d)" % (
            name, q, rh, rf, rh - rf, p, b, c))
    return rows

def main():
    print("== S6 RR 统计检验 ==")
    allrows = []
    # S1 深圳
    if os.path.exists(S1_PATH):
        s1 = load_shenzhen(S1_PATH)
        print("S1 entities:", len(s1))
        allrows += run_dataset("S1_深圳", s1,
            lambda e: ("h", e["district"]),
            lambda e: ("f", e["district"], e["street"]),
            [(0, lambda e: ()),
             (1, lambda e: (e["industry"],)),
             (2, lambda e: (e["industry"], e["size"])),
             (3, lambda e: (e["industry"], e["size"], e["edu"]))])
    # B1 多市
    b1 = load_multicity(B1_DIR)
    print("B1 entities:", len(b1))
    allrows += run_dataset("B1_多市", b1,
        lambda e: ("h", e["city"], e["district"]),
        lambda e: ("f", e["city"], e["district"], e["street"]),
        [(0, lambda e: ()),
         (1, lambda e: (e["edu"],)),
         (2, lambda e: (e["edu"], e["exp"])),
         (3, lambda e: (e["edu"], e["exp"], e["title"]))])
    # B2 企业
    if os.path.exists(B2_PATH):
        b2 = load_enterprise(B2_PATH)
        print("B2 entities:", len(b2))
        allrows += run_dataset("B2_企业", b2,
            lambda e: ("h", e["prov"]),
            lambda e: ("f", e["city"]),
            [(0, lambda e: ()),
             (1, lambda e: (e["etype"],)),
             (2, lambda e: (e["etype"], e["eco"])),
             (3, lambda e: (e["etype"], e["eco"], e["track"]))])
    # 写 CSV
    p = os.path.join(OUT, "S6_rr_statistics.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
        w.writeheader(); w.writerows(allrows)
    print("WRITTEN:", p)

if __name__ == "__main__":
    main()
