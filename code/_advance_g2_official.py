# -*- coding: utf-8 -*-
"""Advance A6/G2: official-statistics cross-check, ready-to-run.
   Aligns our per-city entity counts (real B1 multi-city recruitment data) with an official
   statistics CSV (employment population / legal-entity unit count per city, from statistical
   yearbooks / statistical bulletins / 4th Economic Census), then reports Spearman rank
   correlation and the magnitude ratio (our_count / official_metric) as a third-party evidence
   layer for the commercial-list source.
   USAGE: python3 _advance_g2_official.py [official.csv]
     If no path given, a SYNTHETIC placeholder CSV is generated and used ONLY to smoke-test the
     pipeline (result is clearly labelled; NOT real evidence). Supply the real official CSV to
     obtain real evidence.
   Standard library only, fixed seeds.
"""
import os, csv, math, random, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
import S6_rr_statistics as S

OUT = HERE
SYNTHETIC = os.path.join(OUT, "_g2_official_synthetic.csv")

def load_multicity_fixed(srcdir):
    ents = S.load_multicity(srcdir)
    for e in ents:
        if not e["city"] and "·" in e["district"]:
            parts = [x.strip() for x in e["district"].split("·") if x.strip()]
            if len(parts) >= 3:
                e["city"], e["district"], e["street"] = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                e["city"], e["district"] = parts[0], parts[1]
    return ents

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

def make_synthetic(our_counts):
    """Generate a synthetic official CSV proportional to our counts + lognormal noise (smoke-test only)."""
    rng = random.Random(7)
    with open(SYNTHETIC, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["city", "employment_population", "legal_unit_count"])
        for city, n in sorted(our_counts.items()):
            emp = max(1000, int(n * 800 * math.exp(rng.gauss(0, 0.3))))
            unit = max(50, int(n * 20 * math.exp(rng.gauss(0, 0.3))))
            w.writerow([city, emp, unit])
    return SYNTHETIC

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SYNTHETIC
    if not os.path.exists(src):
        print("No official CSV found; generating SYNTHETIC placeholder:", SYNTHETIC)
    b1 = load_multicity_fixed(S.B1_DIR)
    our = defaultdict(int)
    for e in b1:
        if e["city"]:
            our[e["city"]] += 1
    if not os.path.exists(src):
        make_synthetic(our)
    synthetic = (os.path.basename(src) == os.path.basename(SYNTHETIC))

    official = {}
    with open(src, "r", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        c_city = "city"
        c_emp = next((c for c in cols if "就业" in c or "employ" in c.lower() or "population" in c.lower()), None)
        c_unit = next((c for c in cols if "单位" in c or "unit" in c.lower() or "法人" in c.lower()), None)
        for row in rd:
            city = (row.get(c_city) or "").strip()
            emp = float((row.get(c_emp) or 0).replace(",", "") or 0) if c_emp else 0.0
            unit = float((row.get(c_unit) or 0).replace(",", "") or 0) if c_unit else 0.0
            official[city] = (emp, unit)

    rows = []
    cities = sorted(set(our) & set(official))
    for c in cities:
        o = official[c]
        rows.append({"city": c, "our_entities": our[c],
                     "official_employment": o[0], "official_units": o[1],
                     "ratio_emp": round(our[c] / o[0], 5) if o[0] else 0.0,
                     "ratio_unit": round(our[c] / o[1], 5) if o[1] else 0.0})
    if len(cities) >= 3:
        x = [r["our_entities"] for r in rows]
        y1 = [r["official_employment"] for r in rows]
        y2 = [r["official_units"] for r in rows]
        rho_emp = spearman(x, y1); rho_unit = spearman(x, y2)
    else:
        rho_emp = rho_unit = float("nan")
    print("=== G2 official cross-check (source: %s) ===" % src)
    print("aligned cities: %d | Spearman rho(our, employment)=%.3f | rho(our, units)=%.3f"
          % (len(cities), rho_emp, rho_unit))
    for r in rows:
        print("  %-8s our=%-4d emp=%-10.0f unit=%-8.0f ratio_emp=%.5f ratio_unit=%.5f"
              % (r["city"], r["our_entities"], r["official_employment"], r["official_units"],
                 r["ratio_emp"], r["ratio_unit"]))

    p = os.path.join(OUT, "G2_official_crosscheck.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    # append summary row
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([""])
        w.writerow(["SUMMARY", "spearman_emp", round(rho_emp, 3), "spearman_units", round(rho_unit, 3),
                    "synthetic" if synthetic else "real", len(cities), "", ""])
    print("WROTE", p, "(%d aligned cities)" % len(cities))
    if synthetic:
        print("*** NOTE: SYNTHETIC official data (placeholder) - rerun with real yearbook/econ-census CSV for real evidence. ***")

if __name__ == "__main__":
    main()
