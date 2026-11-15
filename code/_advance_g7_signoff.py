# -*- coding: utf-8 -*-
"""Advance A12/G7: assemble the external-theory signoff package.
   Verifies every theorem/proof artifact referenced for Thm 1 & Thm 2 exists, produces a
   manifest (G7_signoff_package.md) and a single handoff zip (G7_理论签核包.zip) ready to send
   to a theoretical collaborator. Standard library only.
"""
import os, zipfile, datetime

BASE = r"C:\Users\Yi\WorkBuddy\2026-11-09-19-01-07\outputs\选题方案"
OUT = os.path.join(BASE, "experiment_outputs")

# (display name, rel path, purpose)
FILES = [
    ("07_A1_复擀点签核请求.md", "07_A1_复擀点签核请求.md", "Thm1 Checkpoint A-D author self-verification log"),
    ("07_定理1_形式化证明.md", "07_定理1_形式化证明.md", "Thm1 formal lower-bound proof"),
    ("07_定理1_紧下界证明.md", "07_定理1_紧下界证明.md", "Thm1 tight lower-bound proof"),
    ("07_定理1_退化检查.md", "07_定理1_退化检查.md", "Thm1 degenerate-case check"),
    ("07_定理12_证明文档.md", "07_定理12_证明文档.md", "Thm1 & Thm2 construction / near-optimality"),
    ("07_G2_一致性压缩证明.md", "07_G2_一致性压缩证明.md", "Noise K -> n(Q) consistency compression"),
    ("07_G3_显式不等式比对.md", "07_G3_显式不等式比对.md", "Explicit inequality comparison vs Chen et al."),
    ("07_J_恶意共谋威胁模型_证明大纲.md", "experiment_outputs/07_J_恶意共谋威胁模型_证明大纲.md", "G5 malicious/collusion lemmas 1/2 COMPLETE proofs + Game 0-1-2 reduction"),
    ("G3_check.py", "G3_check.py", "Numerical inequality check (Thm1 constants)"),
    ("E34_tightness.py", "E34_tightness.py", "Tightness numerical scan (comm/lb ratio)"),
    ("G3_inequality_check.csv", "experiment_outputs/G3_inequality_check.csv", "Inequality-check data"),
    ("E34_tightness.csv", "experiment_outputs/E34_tightness.csv", "Tightness ratio data (K=16..1024)"),
    ("A3_tightness_scan.csv", "experiment_outputs/A3_tightness_scan.csv", "Dense tightness scan (grid/J/eps, 27 configs)"),
]

def main():
    missing = []
    entries = []
    for disp, rel, purpose in FILES:
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            missing.append(rel); continue
        entries.append((disp, rel, purpose, p, os.path.getsize(p)))

    lines = []
    lines.append("# G7 外部理论签核包（清单与完整性核验）")
    lines.append("")
    lines.append("> 配套：`07_H_IJGIS_短板不足漏洞局限审计.md`（v6）· 用于推进 A12（证明为作者自行推导）")
    lines.append("> 生成：%s" % datetime.date.today().isoformat())
    lines.append("")
    lines.append("**目的**：把定理 1/定理 2 的全部证明与数值验证证据整装为单一包，交理论合作者外部签核，")
    lines.append("以把「作者自行推导 + 数值验证」提升为「第三方签核」。")
    lines.append("")
    lines.append("## 一、完整性核验")
    lines.append("")
    lines.append("| 构件 | 用途 | 大小 | 存在 |")
    lines.append("|:---|:---|:---:|:---:|")
    for disp, rel, purpose, p, sz in entries:
        lines.append("| %s | %s | %d B | ✅ |" % (disp, purpose, sz))
    lines.append("")
    if missing:
        lines.append("**缺失（%d）**：%s" % (len(missing), ", ".join(missing)))
    else:
        lines.append("**全部 %d 个构件存在，无缺失。**" % len(entries))
    lines.append("")
    lines.append("## 二、签核请求要点")
    lines.append("")
    lines.append("请理论合作者重点核验：")
    lines.append("1. **定理 1 下界**：$\\Omega(J\\log K + n(Q)\\log K + n(Q)/\\varepsilon)$ 的几何论证、DP 噪声项、组合步、打包因子不变性（`07_A1` Checkpoint A–D）。")
    lines.append("2. **定理 2 近最优性**：构造达到下界量级，常数差为有界常数因子（`A3_tightness_scan.csv`：比值 ∈ [0.079, 0.185]，随 K 非增，构造 ≤5.4× 下界）。")
    lines.append("3. **G5 恶意/共谋扩展**：引理 1/2（下界在恶意/共谋下保持）**完整证明** + 构造安全归约 Game 0→1→2（`07_J` §2/§4，Pedersen/Bulletproofs/Shamir 实例化，开销 O(1)/O(J)）。")
    lines.append("4. **数值佐证**：`G3_inequality_check.csv`、`E34_tightness.csv`、`A3_tightness_scan.csv` 的固定种子可复现性。")
    lines.append("")
    lines.append("## 三、待签核结论格式")
    lines.append("")
    lines.append("- [ ] 定理 1 下界论证通过（Checkpoint A–D）")
    lines.append("- [ ] 定理 2 构造近最优性通过")
    lines.append("- [ ] 常数差为有界常数因子（≤ 已知上界）")
    lines.append("- [ ] G5 恶意/共谋引理 1/2 论证通过")
    lines.append("- [ ] 数值验证复现通过")
    lines.append("")
    lines.append("*生成：2026-11-15 · 配套 07_H v6 审计与 07_I 路线 · 待外部理论签核*")

    manifest = os.path.join(OUT, "G7_signoff_package.md")
    with open(manifest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("WROTE", manifest)

    # assemble handoff zip
    zp = os.path.join(OUT, "G7_理论签核包.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for disp, rel, purpose, p, sz in entries:
            z.write(p, os.path.basename(rel))
        z.write(manifest, os.path.basename(manifest))
    print("ZIP ->", zp, "(%d files, %d bytes)" % (len(entries) + 1, os.path.getsize(zp)))
    print("missing:", missing if missing else "none")

if __name__ == "__main__":
    main()
