# 实验脚本 README（E0—E5 + S1/S3/S4 增补）

`run_experiments.py` 实现选题方案 07（v2.2）7.7 实验执行协议的 **E0—E5**；后续增补 **S1/S3/S4/E34/G3**（对应 S1 实体层、S3 原型、S4 完整评测、G3 数值比对、E34 紧性），**均仅依赖标准库**，无真实数据时用**合成数据**兜底，直接可跑。

## 运行全部脚本

```bash
python run_experiments.py   # E0—E5
python S1_entity_layer.py   # S1 实体层(合成兜底) + linkage attack（RR 校准）
python S1_real_data.py      # S1 真实数据接入：智联招聘真实岗位 CSV → RR 校准
python review_AD_check.py   # 复核点 A/D 数值验证（几何紧性 + 预算重分配）
python E34_tightness.py     # 紧性：几何 √K 优势 + 构造常数倍
python G3_check.py          # G3 数值：层级 vs 平化不等式
python S3_prototype.py      # S3 端到端原型：三类负载（范围/级联/kNN）
python S4_evaluation.py     # S4 完整评测：Pareto + 消融 + 可扩展
```

## 输出（`experiment_outputs/`）

| 文件 | 内容 | 对应 |
|:---|:---|:---|
| `E1_rr_curve.csv` | ε × 层级RR × 平坦RR × 理论界 | E1（RQ1） |
| `E2_allocation.csv` | 分配方案 × 分支因子 × 约束推断 × 相对误差 | E2（RQ2／引理2） |
| `E3_tradeoff.csv` | ε × α × 本地误差 × 可行 × 通信 × 候选下界 × 比值 | E3（RQ3／定理1） |
| `E4_baselines.csv` | 集中式明文／DP／本地DP／构造 × 误差 × 通信 | E4（RQ4／定理2） |
| `E5_scaling.csv` | J × 国家数 × 城市数 × 实体数 × 路由通信 | E5（可扩展性） |
| `S1_entity_layer.csv` | 层级 vs 平坦 RR（合成层，含辖区先验）＋理论后验界 | S1（实体层） |
| `S1_entity_stats.csv` | 实体层统计（合成层计数/行业/规模） | S1 |
| `S1_real_rr.csv` | **真实数据**（智联招聘深圳 200 岗位）层级 vs 平坦 RR × q 准标识符 | S1（真实接入） |
| `S1_real_stats.csv` | **真实数据**实体层统计（9 行政区/49 街道/50 行业/9 规模/8 学历） | S1（真实接入） |
| `E34_tightness.csv` | 各 K 下 σ_flat/σ_hier、通信节省、通信/下界比值 | E34（紧性） |
| `G3_inequality_check.csv` | 各 K 下 nQ_quad/kd、√K、通信节省 | G3（数值） |
| `S3_prototype.csv`＋`S3_prototype_summary.csv` | 三类负载 end-to-end：误差/通信/下界比值 | S3（原型） |
| `S4_pareto.csv` | 通信—效用—ε Pareto 扫描 | S4 |
| `S4_ablation.csv` | R树/布隆/一致/代价优化 逐组件贡献 | S4 |
| `S4_scalability.csv` | J×N 增倍通信/延迟代理 | S4 |

## 逻辑说明

- **层级几何**：2D 四叉/kd 树 `n(Q)=O(√K)`（Cormode et al. SIGMOD 2012 Lemma 2）；整树查询读根 `n(Q)=1`，平化读全部 K 叶 → **通信节省 K 倍**（`E34`、`G3`）。
- **紧性**：构造（一致性 HDP + R 树路由 + 布隆剪枝 + 代价优化）通信/下界 ≤ O(1)（`S3`：0.08—0.16；简化 `E34`：≤0.2）。
- **一致性**：父=子和投影使查询可读簇根而非叶子（**几何驱动**，非噪声平均——G2 修正版说明）。

## 接入真实数据（替换合成部分）

1. **行政层级**：`git clone --depth 1 https://github.com/dr5hn/countries-states-cities-database.git`，记录 commit；用 JSON 主格式。
2. **实体层**：企查查企业／招聘数据（或合成层按实测分布生成），每条绑定城市叶节点（按经纬度映射）。
3. **S1 合成接入**：`S1_entity_layer.load_real_entities(path)` 读 CSV；不可用则 `build_entities()` 合成兜底。
4. `e0()`／`run_query()` 的合成树／实体生成可替换，其余逻辑无需改动。

## 真实数据接入（S1/B1/B2 已跑通）

- **S1 深圳岗位**：`S1_real_data.py` 接入 `智能体招聘_智联_深圳_合并.csv`（200 条，utf-8-sig），输出 `S1_real_rr.csv`。各档 q 层级 RR 均 < 平坦 RR 且 ≤ 理论后验界（q=0: 1.0% vs 7.5%；q=1: 33.5% vs 60.0%；q=2: 53.5% vs 67.5%；q=3: 63.5% vs 73.0%）。
- **B1 多市招聘合并**：`B1_merge_multi_city.py` 合并 27 市鸿蒙岗位抽样（647 条），输出 `B1_multi_city_rr.csv`、`B1_multi_city_files.csv`。q≤2 时层级 RR < 平坦 RR 且 ≤ 界；q=3(+岗位名) 达 93.0% vs 93.7%（高区分度 QI 边界，需诚实讨论）。
- **B2 企业实体层**：`B2_enterprise_entity_rr.py` 接入 `国内鸿蒙相关企业采集.csv`（346 条，20 省/48 市），输出 `B2_enterprise_rr.csv`、`B2_enterprise_rr.md`。省级层级聚合在 q0-q3 各配置下 RR 均低于市级平坦。

## C1—C3 扩量与图表（2026-11-10）

| 脚本 | 内容 | 主要产出 |
|:---|:---|:---|
| `C1_mixed_workload_5000.py` | 5000 查询混合扩量（10 配置：J∈{4,8,16}, grid∈{16,32,64}, ε∈{0.5,1,2}；range/cascade/knn） | `C1_mixed_workload_5000_detail.csv`, `C1_mixed_workload_5000_summary.csv`, `C1_mixed_workload_5000_overall.md` |
| `C2_latency_profile.py` | 单机进程内延迟实测（5 配置×800 次）+ 网络 RTT 建模估算 | `C2_latency_measured.csv`, `C2_latency_network_model.csv`, `C2_latency_profile.md` |
| `_c2_vm_driver.py`（VM） | **真实容器/网络延迟实测**：Docker Compose 4 节点+客户端，`tc netem` 注入 10/30/80ms | `C2_baseline.csv`, `C2_delay10.csv`, `C2_delay30.csv`, `C2_delay80.csv`, `C2_real_container_latency.md` |
| `C3_paper_figures.py` | 论文级图表（matplotlib, 300 dpi） | `figures/fig1_rr_calibration.png` ~ `fig5_scalability_latency.png`, `C3_figures_index.md` |

> C1 结果：各配置层级中位误差显著低于平坦，通信/下界中位比值约 0.03–0.10（p95 ≤ 0.20）。C2 已补齐**真实容器/网络延迟实测**：容器间基线 RTT p50≈0.9ms；`tc netem` 注入 10/30/80ms → RTT≈21.6/61.6/161.2ms，联邦查询端到端 p50 14.1→95.5→255.8→653.6ms（见 `C2_real_container_latency.md`）。

## 成稿合规（D1—D9 进度）

- 详见 `07_D_成稿合规推进清单.md`：D4 数据集引用、D5 行政区域/ISO 表述、D9 E0—E6 指标对照已整理；D1/D2/D3/D6/D7/D8 待正式稿或外部条件。
- 投稿包进度见 `07_投稿包_IJGIS.md` 第七节。

## 注意（诚实声明）

- **合成数据仅用于验证流程可执行**，数值**不代表**真实结果；已接入真实/采集数据（S1/B1/B2）支撑 RR 结论，但仍需在论文中区分数据来源与证据强度。
- C2 已含**真实容器/网络延迟实测**（Docker Compose + `tc netem` 注入）；物理跨主机/真实跨地域链路仍建议部署环境复核。
- 理论主张依据 `07_定理1_形式化证明.md` 的复核点 A—D（**作者自我核验通过**，见 `07_A1_复擀点签核请求.md`；无外部理论合作者，不声称外部签核）；本套装脚本仅供验证其数值/机制层面。
- E3 的「候选下界」是**量级示意**（见定理 1 证明文档），**非已证明下界**；真实实验须在 S2 定稿下界后再对比。
- E2 的约束推断为**简化版**（单次均值收缩），真实实验应实现加权最小二乘投影（Qardaji 等 PVLDB 2013）。
- E4 的构造误差按 $\sqrt{J}/\varepsilon$ 量级示意，真实实验须按序贯组合精确计算。
