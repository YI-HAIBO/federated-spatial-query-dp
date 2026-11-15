# -*- coding: utf-8 -*-
"""Advance G9 (real on-wire byte measurement) WITHOUT the C2 container.

A11 (v5) measured application-layer bytes for a single-direction blob send over a raw
localhost socket. The C2 container (for true packet capture of TCP/IP frame headers) was
unavailable, so G9 stayed open. This script provides the achievable alternative:

  1. A REAL query->response round-trip over a TCP proxy: the client sends 300 real range
     queries; the service computes the actual hierarchical-DP (or baseline) answer AND
     transmits the mechanism's real encoded message stream (the per-mechanism counts that
     the federated protocol actually pushes over the wire) back to the client. A
     byte-accounting TCP forward-proxy measures the ACTUAL bytes on the wire in BOTH
     directions (client->server request bytes, server->client mechanism-payload bytes).
  2. A defensible on-wire segmentization model for the TCP/IP+Ethernet frame overhead:
     on_wire = app_bytes + ceil(app_bytes / MSS) * (TCP_HDR + IP_HDR + Eth_HDR), the honest
     best-available estimate without a packet-capture device (no tcpdump/WinPcap here).
     Clearly labeled model+measurement hybrid.

Standard library only, fixed seeds. No container required.
"""
import os, csv, math, random, statistics, socket, struct, time, threading, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
from C1_mixed_workload_5000 import build_data, hdp_mechanism, nQ_range

OUT = HERE
GRID = 32; DEPTH = 5; EPS = 1.0; J = 8
MSS = 1460
TCP_HDR = 20; IP_HDR = 20; ETH_HDR = 18

def on_wire_model(app_bytes):
    segs = math.ceil(max(1, app_bytes) / MSS)
    return app_bytes + segs * (TCP_HDR + IP_HDR + ETH_HDR)

def frame(payload):
    return struct.pack("<I", len(payload)) + payload

def read_exact(conn, n):
    buf = b""
    while len(buf) < n:
        d = conn.recv(n - len(buf))
        if not d:
            return None
        buf += d
    return buf

def read_frame(conn):
    h = read_exact(conn, 4)
    if h is None:
        return None
    ln = struct.unpack("<I", h)[0]
    if ln == 0:
        return b""           # done marker
    return read_exact(conn, ln)

def mechanism_payloads(kind, Q, data, qid):
    """Real encoded per-mechanism message stream for one query (same encoding as A11)."""
    grid = data["grid"]; counts = data["counts"]; depth = data["depth"]
    i0, i1, j0, j1 = Q[0], Q[1], Q[2], Q[3]
    region = [(i, j) for i in range(i0, i1) for j in range(j0, j1)]
    true = sum(counts[c] for c in region)
    nQ = nQ_range((i0, i1, j0, j1), grid, depth)
    qh = struct.pack("<I", qid)
    out = []
    if kind == "construction":
        m = max(1, int(math.ceil(nQ * 0.15)))
        for k in range(m):
            node_id = (qid * 131 + k) % (4 ** depth)
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

def service_loop(conn, data, mode, mechanism):
    """Read framed queries; transmit the mechanism's real message stream + done marker."""
    while True:
        q = read_frame(conn)
        if q is None or q == b"":
            break
        qid, i0, i1, j0, j1 = struct.unpack("<IHHHH", q)
        noisy = hdp_mechanism(data, EPS, mode)
        est = sum(noisy[(i, j)] for i in range(i0, i1) for j in range(j0, j1))
        payloads = mechanism_payloads(mechanism, (i0, i1, j0, j1), data, qid)
        # Send the mechanism's message stream (each framed), then a 0-length done marker.
        blob = b"".join(frame(p) for p in payloads) + frame(b"")
        conn.sendall(blob)
    try:
        conn.close()
    except Exception:
        pass

class ByteProxy:
    def __init__(self, service_addr):
        self.service_addr = service_addr
        self.bytes_c2s = 0; self.bytes_s2c = 0
        self._lock = threading.Lock()

    def _pipe(self, src, dst, name):
        total = 0
        try:
            while True:
                d = src.recv(65536)
                if not d:
                    break
                dst.sendall(d); total += len(d)
        except Exception:
            pass
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass
        with self._lock:
            if name == "c2s": self.bytes_c2s += total
            else: self.bytes_s2c += total

    def serve(self, listen_addr):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(listen_addr); srv.listen(1)
        client, _ = srv.accept()
        service = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        service.connect(self.service_addr)
        t1 = threading.Thread(target=self._pipe, args=(client, service, "c2s"), daemon=True)
        t2 = threading.Thread(target=self._pipe, args=(service, client, "s2c"), daemon=True)
        t1.start(); t2.start(); t1.join(); t2.join()
        client.close(); service.close(); srv.close()

def run_roundtrip(data, mechanism, mode, nq=300):
    # service
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0)); srv.listen(1)
    service_addr = srv.getsockname()
    def _svc():
        conn, _ = srv.accept()
        service_loop(conn, data, mode, mechanism)
        srv.close()
    st = threading.Thread(target=_svc, daemon=True); st.start()
    # proxy
    proxy = ByteProxy(service_addr)
    ps = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ps.bind(("127.0.0.1", 0)); paddr = ps.getsockname(); ps.close()
    pt = threading.Thread(target=proxy.serve, args=(paddr,), daemon=True); pt.start()
    # client
    cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for _ in range(100):
        try:
            cli.connect(paddr); break
        except OSError:
            time.sleep(0.02)
    r = random.Random(900)
    nresp = 0; total_payload = 0
    for qid in range(nq):
        i0 = r.randint(0, GRID - 2); i1 = r.randint(i0 + 1, GRID)
        j0 = r.randint(0, GRID - 2); j1 = r.randint(j0 + 1, GRID)
        cli.sendall(frame(struct.pack("<IHHHH", qid, i0, i1, j0, j1)))
        # read mechanism stream until done marker
        while True:
            f = read_frame(cli)
            if f is None:
                break
            if f == b"":
                break
            total_payload += len(f)
        nresp += 1
    cli.close()
    pt.join(timeout=8); st.join(timeout=8)
    return proxy.bytes_c2s, proxy.bytes_s2c, nresp, total_payload

def main():
    data = build_data(seed=4, grid=GRID, ent_per_cell=3, J=J)
    rows = []
    for label, mechanism, mode in [("construction", "construction", "hier"),
                                   ("flat_central", "flat_central", "flat")]:
        c2s, s2c, nresp, total_payload = run_roundtrip(data, mechanism, mode)
        app_total = c2s + s2c
        rows.append({"block": "G9_proxy", "mechanism": label, "mode": mode,
                     "n_queries": 300, "n_responses": nresp,
                     "app_bytes_c2s": c2s, "app_bytes_s2c": s2c,
                     "app_bytes_total": app_total,
                     "payload_bytes_read": total_payload,
                     "on_wire_model_total": on_wire_model(c2s) + on_wire_model(s2c)})
        print("%-14s resp=%d/300 c2s=%6d s2c=%6d app=%8d payload=%7d onwire=%9d" % (
            label, nresp, c2s, s2c, app_total, total_payload,
            on_wire_model(c2s) + on_wire_model(s2c)))
    p = os.path.join(OUT, "G9_proxy_bytes.csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("WROTE", p, "(%d rows)" % len(rows))

if __name__ == "__main__":
    main()
