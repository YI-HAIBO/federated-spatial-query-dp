import urllib.request, json, time, sys, statistics, socket

NODES = ["node1", "node2", "node3", "node4"]
PORT = 8000
N = 150

def get(url, timeout=10):
    t0 = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as r:
        r.read()
    return (time.perf_counter() - t0) * 1000.0  # ms

def pctl(vals, p):
    v = sorted(vals)
    k = max(0, min(len(v) - 1, int(round(p / 100.0 * (len(v) - 1)))))
    return v[k]

def measure_node(name):
    lat = []
    for _ in range(N):
        try:
            lat.append(get("http://%s:%d/" % (name, PORT)))
        except Exception as e:
            lat.append(9999.0)
    return lat

def measure_query():
    # 模拟联邦空间查询：client 顺序访问全部 J 节点，各节点做 qms 计算
    qms = 2.0
    lat = []
    for _ in range(N):
        t0 = time.perf_counter()
        for name in NODES:
            try:
                get("http://%s:%d/query?qms=%.1f" % (name, PORT, qms), timeout=15)
            except Exception as e:
                pass
        lat.append((time.perf_counter() - t0) * 1000.0)
    return lat

def main():
    mode = "baseline"
    out = "/app/result.csv"
    for i, a in enumerate(sys.argv[1:]):
        if a == "--mode" and i + 2 <= len(sys.argv):
            mode = sys.argv[i + 2]
        if a == "--out" and i + 2 <= len(sys.argv):
            out = sys.argv[i + 2]

    rows = []
    # 逐节点 RTT
    for name in NODES:
        lat = measure_node(name)
        rows.append({
            "mode": mode, "metric": "rtt_http", "target": name,
            "p50_ms": round(pctl(lat, 50), 4), "p95_ms": round(pctl(lat, 95), 4),
            "p99_ms": round(pctl(lat, 99), 4), "mean_ms": round(statistics.mean(lat), 4),
            "max_ms": round(max(lat), 4),
        })
    # 联邦查询端到端
    q = measure_query()
    rows.append({
        "mode": mode, "metric": "federated_query", "target": "all",
        "p50_ms": round(pctl(q, 50), 4), "p95_ms": round(pctl(q, 95), 4),
        "p99_ms": round(pctl(q, 99), 4), "mean_ms": round(statistics.mean(q), 4),
        "max_ms": round(max(q), 4),
    })

    import csv, io
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("MEASURE_DONE mode=%s rows=%d out=%s" % (mode, len(rows), out))

if __name__ == "__main__":
    main()
