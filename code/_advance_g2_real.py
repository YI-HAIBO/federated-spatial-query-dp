# -*- coding: utf-8 -*-
"""Advance A6/G2 with REAL official data (7th National Population Census, 2020-11-01).
   Replaces the synthetic smoke-test evidence with a genuine third-party cross-check:
   our per-city entity counts (real B1 multi-city recruitment data) vs official per-city
   resident population (7th census, from provincial/city census bulletins), Spearman rank
   correlation. Shenzhen district-level entries are aggregated to prefecture level.
   USAGE: python3 _advance_g2_real.py
   Outputs G2_official_crosscheck.csv (real) + prints summary.
   Standard library only.
"""
import os, csv, math, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
import S6_rr_statistics as S

OUT = HERE
REAL_CSV = os.path.join(OUT, "g2_official_real_7th_census.csv")

SZ_PREFIX = ("龙岗", "南山", "福田", "罗湖", "宝安", "龙华", "盐田", "坪山", "光明", "大鹏")
SZ_BARE = ("龙岗", "龙华", "福田", "罗湖", "南山", "宝安")  # bare district-name city fields -> Shenzhen

def agg_shenzhen(ents):
    for e in ents:
        c = e["city"]
        if not c:
            continue
        if c.startswith(SZ_PREFIX) or c in SZ_BARE:
            e["city"] = "深圳"
    return ents

def load_multicity_fixed(srcdir):
    ents = S.load_multicity(srcdir)
    for e in ents:
        if not e["city"] and "·" in e["district"]:
            parts = [x.strip() for x in e["district"].split("·") if x.strip()]
            if len(parts) >= 3:
                e["city"], e["district"], e["street"] = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                e["city"], e["district"] = parts[0], parts[1]
    return agg_shenzhen(ents)

def spearman(xs, ys):
    def rank(v):
        idx = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[idx[j + 1]] == v[idx[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[idx[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx = sum(rx) / len(rx); my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den > 0 else 0.0

def main():
    ents = load_multicity_fixed(S.B1_DIR)
    our = defaultdict(int)
    for e in ents:
        if e["city"]:
            our[e["city"]] += 1

    official = {}
    with open(REAL_CSV, "r", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        for row in rd:
            city = (row.get("city") or "").strip()
            pop = float((row.get("population_2020_7th_census") or "0").replace(",", "") or 0)
            src = (row.get("source") or "").strip()
            official[city] = (pop, src)

    rows = []
    cities = sorted(set(our) & set(official))
    for c in cities:
        pop, src = official[c]
        rows.append({"city": c, "our_entities": our[c],
                     "official_population_2020": int(pop),
                     "penetration_per_10000": round(our[c] / pop * 10000, 4),
                     "source": src})
    x = [r["our_entities"] for r in rows]
    y = [r["official_population_2020"] for r in rows]
    rho = spearman(x, y) if len(cities) >= 3 else float("nan")

    print("=== G2 REAL official cross-check (7th census 2020 resident population) ===")
    print("aligned prefecture cities: %d | Spearman rho(our_entities, official_population) = %.3f"
          % (len(cities), rho))
    print("--- by city (rank check) ---")
    order = sorted(range(len(rows)), key=lambda i: -rows[i]["our_entities"])
    for i in order:
        r = rows[i]
        print("  %-4s our=%-4d pop=%-9d per10k=%.4f" % (r["city"], r["our_entities"],
                                                       r["official_population_2020"],
                                                       r["penetration_per_10000"]))
    # also report the largest rank inversion (where our count is much higher/lower than pop rank)
    px = [r["our_entities"] for r in rows]
    py = [r["official_population_2020"] for r in rows]
    print("--- notable deviations (our count vs pop rank) ---")
    sx = sorted(range(len(px)), key=lambda i: px[i])
    sy = sorted(range(len(py)), key=lambda i: py[i])
    rank_of = {c: i + 1 for i, c in enumerate(sorted(range(len(px)), key=lambda i: px[i]))}
    poprank_of = {c: i + 1 for i, c in enumerate(sorted(range(len(py)), key=lambda i: py[i]))}
    devs = []
    for i, r in enumerate(rows):
        dev = rank_of[i] - poprank_of[i]
        devs.append((abs(dev), r["city"], rank_of[i], poprank_of[i]))
    for d, c, a, b in sorted(devs, reverse=True)[:6]:
        print("  %-4s our_rank=%d pop_rank=%d (diff=%+d)" % (c, a, b, a - b))

    p = os.path.join(OUT, "G2_official_crosscheck.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([])
        w.writerow(["SUMMARY", "spearman_population", round(rho, 3), "aligned_cities", len(cities),
                    "metric", "7th_census_2020_resident_population", "real", "TRUE"])
    print("\nWROTE", p, "(%d aligned cities, REAL data)" % len(cities))

if __name__ == "__main__":
    main()
