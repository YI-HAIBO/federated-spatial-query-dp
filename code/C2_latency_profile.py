#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C2: 延迟剖析（可执行部分）+ 容器/网络真实延迟说明
- 在单机进程内对 C1 代表配置进行批量计时，输出 p50/p95/p99 延迟代理。
- 真实容器/网络延迟需 Docker Compose 多容器部署与网络注入，本脚本给出
  可复现的本地测量 + 建模估算表，并明确边界。
"""
import os, csv, math, random, statistics, time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "experiment_outputs")
os.makedirs(OUT, exist_ok=True)

def lap(b, r):
    u = r.random() - 0.5
    if abs(u) < 1e-12: return 0.0
    return -b * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u))

def build_data(seed=0, grid=16, J=4):
    r = random.Random(seed)
    counts = {(i,j):3 for i in range(grid) for j in range(grid)}
    depth = int(math.log2(grid))
    return {"grid":grid,"K":grid*grid,"depth":depth,"counts":counts,"J":J,"r":r}

def nQ_range(Q, grid, depth):
    base = int(8 * (2 ** (depth / 2))) if depth > 0 else 8
    area = max(1,(Q[1]-Q[0])*(Q[3]-Q[2]))
    frac = max(0.05, min(1.0, area/(grid*grid)))
    return max(1,int(base*math.sqrt(frac)))

def hdp(data, eps, mode):
    r=data["r"]; counts=data["counts"]; depth=max(1,data["depth"])
    if mode=="flat":
        e=max(1e-6, eps/depth)
        return {k:max(0.0,v+lap(1.0/e,r)) for k,v in counts.items()}
    e=max(1e-6,eps)
    return {k:max(0.0,v+lap(1.0/e,r)) for k,v in counts.items()}

def run_range(data,Q,mode,eps,use_bloom=True):
    grid=data["grid"]; depth=data["depth"]; counts=data["counts"]
    noisy=hdp(data,eps,mode)
    true=sum(counts[(i,j)] for i in range(Q[0],Q[1]) for j in range(Q[2],Q[3]))
    est=sum(noisy[(i,j)] for i in range(Q[0],Q[1]) for j in range(Q[2],Q[3]))
    nQ=nQ_range(Q,grid,depth)
    area=(Q[1]-Q[0])*(Q[3]-Q[2])
    comm = area*8 if mode=="flat" else nQ*8
    if use_bloom and mode=="hier": comm=max(1,int(comm*0.15))
    return abs(est-true)/max(1.0,true), comm, nQ

def pct(vals,p):
    vs=sorted(vals); k=(len(vs)-1)*p/100.0; f=int(math.floor(k)); c=int(math.ceil(k))
    if f==c: return vs[f]
    return vs[f]*(c-k)+vs[c]*(k-f)

def measure_config(J,grid,eps,n,seed):
    data=build_data(seed=seed,grid=grid,J=J)
    r=random.Random(seed+1000)
    lats=[]; comms=[]
    for _ in range(n):
        i0=r.randint(0,grid-2); i1=r.randint(i0+1,grid)
        j0=r.randint(0,grid-2); j1=r.randint(j0+1,grid)
        Q=(i0,i1,j0,j1)
        t0=time.perf_counter()
        _,comm,_=run_range(data,Q,"hier",eps,True)
        t1=time.perf_counter()
        lats.append((t1-t0)*1e6); comms.append(comm)
    return {
        "J":J,"grid":grid,"K":grid*grid,"eps":eps,"n":n,
        "p50_us":round(pct(lats,50),3),"p95_us":round(pct(lats,95),3),"p99_us":round(pct(lats,99),3),
        "mean_us":round(statistics.mean(lats),3),"med_comm_bits":round(statistics.median(comms),3),
        "env":"single_process_windows","note":"perf_counter进程内测量，非容器/网络RTT"
    }

def main():
    configs=[(4,16,1.0),(8,16,1.0),(8,32,1.0),(16,32,1.0),(16,64,1.0)]
    rows=[]
    for idx,(J,grid,eps) in enumerate(configs):
        row=measure_config(J,grid,eps,n=800,seed=idx)
        rows.append(row)
        print("measured", row)
    # 模型化网络开销估算（供论文讨论，不冒充实测）
    # 假设：LAN RTT 0.5ms, WAN RTT 30ms, 带宽 100Mbps；每消息开销=RTT + bytes*8/bw
    bw_bps=100e6
    model_rows=[]
    for r in rows:
        bytes_est=r["med_comm_bits"]/8.0
        for net, rtt_ms in [("LAN_0.5ms",0.5),("WAN_30ms",30.0),("CrossRegion_80ms",80.0)]:
            tx_ms = (bytes_est*8.0/bw_bps)*1000.0
            # 简化：一次查询约需 log2(K)+nQ 轮消息，近似 1-3 RTT
            est_p50_ms = r["p50_us"]/1000.0 + rtt_ms + tx_ms
            est_p95_ms = r["p95_us"]/1000.0 + 1.5*rtt_ms + tx_ms
            model_rows.append({
                "J":r["J"],"grid":r["grid"],"network":net,"rtt_ms":rtt_ms,
                "compute_p50_ms":round(r["p50_us"]/1000.0,4),
                "tx_ms_model":round(tx_ms,6),
                "est_total_p50_ms":round(est_p50_ms,4),
                "est_total_p95_ms":round(est_p95_ms,4),
                "note":"建模估算(非实测)"
            })
    with open(os.path.join(OUT,"C2_latency_measured.csv"),"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT,"C2_latency_network_model.csv"),"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(model_rows[0].keys())); w.writeheader(); w.writerows(model_rows)
    md=os.path.join(OUT,"C2_latency_profile.md")
    with open(md,"w",encoding="utf-8") as f:
        f.write("# C2 延迟剖析\n\n")
        f.write("## 1. 单机实测（进程内代理）\n\n")
        f.write("| J | grid | ε | n | p50(us) | p95(us) | p99(us) | mean(us) | 环境 |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for r in rows:
            f.write(f"| {r['J']} | {r['grid']} | {r['eps']} | {r['n']} | {r['p50_us']} | {r['p95_us']} | {r['p99_us']} | {r['mean_us']} | {r['env']} |\n")
        f.write("\n## 2. 网络延迟建模估算（非实测）\n\n")
        f.write("| J | grid | network | RTT(ms) | compute_p50(ms) | tx_model(ms) | est_total_p50(ms) | est_total_p95(ms) |\n")
        f.write("|---:|---:|---|---:|---:|---:|---:|---:|\n")
        for r in model_rows:
            f.write(f"| {r['J']} | {r['grid']} | {r['network']} | {r['rtt_ms']} | {r['compute_p50_ms']} | {r['tx_ms_model']} | {r['est_total_p50_ms']} | {r['est_total_p95_ms']} |\n")
        f.write("\n## 3. 边界与诚实声明\n")
        f.write("- **已完成**：单机进程内查询处理延迟（`time.perf_counter`）在 5 组 (J,grid) 配置×800 次测量，可复现。\n")
        f.write("- **未完成（需部署环境）**：Docker Compose 多容器、真实跨容器/跨地域网络 RTT、丢包与抖动下的 p50/p95/p99。这要求容器编排与网络注入环境，当前工作空间无法直接产出真实容器延迟。\n")
        f.write("- **建模表用途**：仅用于论文中讨论“计算开销 vs 通信 RTT 主导性”的量级，不替代实测；投稿前若审稿要求需在容器环境补充实测。\n")
    print("WROTE C2_latency_measured.csv, C2_latency_network_model.csv, C2_latency_profile.md")

if __name__=="__main__":
    main()
