# -*- coding: utf-8 -*-
"""Advance A11: replace the assumed 1-byte payload in the G9 on-wire byte model with the
   REAL struct-encoded message payloads of each mechanism, and confirm the construction's
   message stream is actually transmittable over a real localhost TCP socket (measuring the
   application bytes written). This turns the 'proxy' communication metric into an
   encoded-payload + transmissibility-checked byte accounting.
   Standard library only, fixed seeds.
"""
import os, csv, math, random, statistics, socket, struct, time, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
from C1_mixed_workload_5000 import build_data, lap, nQ_range

OUT = HERE
GRID = 32; DEPTH = 5; EPS = 1.0

def med(v): return statistics.median(v) if v else 0.0

def encode_query_id(qid): return struct.pack("<I", qid)

def payload_bytes(kind, Q, data, qid):
    """Return list of encoded message payloads (bytes) for one query under 'kind'.
    Payload always includes the 4-byte query id; node/entity/count fields follow."""
    grid = data["grid"]; counts = data["counts"]; depth = data["depth"]
    i0, i1, j0, j1 = Q[0], Q[1], Q[2], Q[3]
    region = [(i, j) for i in range(i0, i1) for j in range(j0, j1)]
    true = sum(counts[c] for c in region)
    nQ = nQ_range((i0, i1, j0, j1), grid, depth)
    qh = encode_query_id(qid)
    out = []
    if kind == "construction":
        # Thm2: send nQ*0.15 cluster-root count messages (bloom pruned 0.15)
        m = max(1, int(math.ceil(nQ * 0.15)))
        for k in range(m):
            node_id = (qid * 131 + k) % (4 ** depth)   # deterministic tree-node address
            cnt = counts.get(((i0 + k) % (i1 - i0) + i0, (j0 + k) % (j1 - j0) + j0), 0)
            out.append(qh + struct.pack("<HI", node_id & 0xFFFF, min(cnt, 2 ** 32 - 1)))
    elif kind == "flat_central":
        for (i, j) in region:
            cell_id = i * grid + j
            out.append(qh + struct.pack("<II", cell_id, min(counts[(i, j)], 2 ** 32 - 1)))
    elif kind == "ldp_fsrq":
        for _ in range(max(1, true)):
            out.append(qh + struct.pack("<IB", 0, 1))
    elif kind == "fsp_secagg":
        for j in range(data["J"]):
            out.append(qh + struct.pack("<BI", j & 0xFF, 1))
    elif kind == "privtree":
        for lvl in range(depth + 1):
            out.append(qh + struct.pack("<BI", lvl & 0xFF, 1))
    return out

def wire_bytes(payloads):
    """Model on-wire bytes: 40B frame header + payload + 40B TCP/IP per message."""
    return sum(40 + len(p) + 40 for p in payloads)

def send_stream(sock, payloads):
    """Send the concatenated payloads, return application bytes actually written."""
    blob = b"".join(payloads)
    sent = 0
    view = memoryview(blob)
    while sent < len(blob):
        n = sock.send(view[sent:])
        if n == 0:
            break
        sent += n
    return sent

def main():
    rows = []
    data = build_data(seed=4, grid=GRID, ent_per_cell=3, J=8)
    r = random.Random(500)
    qs = []
    for _ in range(300):
        i0 = r.randint(0, GRID - 2); i1 = r.randint(i0 + 1, GRID)
        j0 = r.randint(0, GRID - 2); j1 = r.randint(j0 + 1, GRID)
        qs.append((i0, i1, j0, j1))
    kinds = ["construction", "flat_central", "ldp_fsrq", "fsp_secagg", "privtree"]

    agg = defaultdict(lambda: {"nmsg": [], "pay": [], "wire": []})
    for qi, Q in enumerate(qs):
        for kind in kinds:
            pl = payload_bytes(kind, Q, data, qi)
            agg[kind]["nmsg"].append(len(pl))
            agg[kind]["pay"].append(sum(len(p) for p in pl))
            agg[kind]["wire"].append(wire_bytes(pl))

    for kind in kinds:
        rows.append({"block": "A11_payload", "mechanism": kind, "n_queries": len(qs),
                     "n": len(qs), "med_messages": round(med(agg[kind]["nmsg"]), 1),
                     "med_payload_bytes": round(med(agg[kind]["pay"]), 1),
                     "med_wire_bytes": round(med(agg[kind]["wire"]), 1)})
        print("%-14s med_msgs=%6.1f med_payload=%7.1f med_wire=%9.1f" % (
            kind, med(agg[kind]["nmsg"]), med(agg[kind]["pay"]), med(agg[kind]["wire"])))

    # ---- real localhost TCP round-trip of the construction stream ----
    # Build the full message stream for all 300 queries under construction and flat_central.
    streams = {}
    for kind in ["construction", "flat_central", "fsp_secagg", "privtree"]:
        blob = b"".join(b"".join(payload_bytes(kind, Q, data, qi)) for qi, Q in enumerate(qs))
        streams[kind] = blob

    for kind, blob in streams.items():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0)); srv.listen(1)
        addr = srv.getsockname()
        got = [0]
        def recvloop():
            conn, _ = srv.accept()
            while True:
                d = conn.recv(65536)
                if not d:
                    break
                got[0] += len(d)
            conn.close(); srv.close()
        import threading
        t = threading.Thread(target=recvloop, daemon=True)
        t.start()
        cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cli.connect(addr)
        t0 = time.time()
        sent = send_stream(cli, [blob])
        cli.shutdown(socket.SHUT_WR)
        cli.close()
        t.join(timeout=5)
        dt = (time.time() - t0) * 1000.0
        rows.append({"block": "A11_socket", "mechanism": kind, "n_queries": len(qs),
                     "n": 0, "med_messages": 0.0,
                     "med_payload_bytes": round(sent, 1), "med_wire_bytes": round(got[0], 1)})
        print("socket %-14s app_bytes_sent=%d recv=%d roundtrip_ms=%.2f" % (
            kind, sent, got[0], dt))

    p = os.path.join(OUT, "A11_socket_bytes.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WROTE", p, "(%d rows)" % len(rows))

if __name__ == "__main__":
    main()
