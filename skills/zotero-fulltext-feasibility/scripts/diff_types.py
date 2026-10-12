#!/usr/bin/env python3
"""文章类型差异比对（只读）—— Europe PMC 补充数据 vs Zotero 现有值

用法:
    python3 diff_types.py \
        --epmc  ~/ResearchVault/90_Meta/State/epmc_enrich_20260917.json \
        --types ~/ResearchVault/90_Meta/State/zotero_types_20260916.json \
        --out   ~/ResearchVault/90_Meta/State/type_diff_20260917

设计要点（口径来源：与用户确认的「只补缺口、不覆盖细粒度值」）：

  核心事实 —— Zotero 库里 331 条**早已带** `文章类型-*` 标签与 extra 的「文章类型:」行
  （journal-metrics 批次所写，粒度**细于** Europe PMC 的粗分类）。
  因此本脚本**不是**做「292 条覆盖」，而是做三分：

    A 补充候选  existing 为空 / 「期刊论文(未识别)」 → 用 pubTypes 推出的细粒度值补上
    B 修正候选  existing 为「论著」，但 pubTypes **明确**含 review/editorial/letter/comment/erratum
                且**不含** journal article / research-article → 实质错标，建议改为对应类型
    C 保留     其余全部不动。其中「论著」条目若 pubTypes 提示更细类型（如 RCT），
                仅作**信息统计**，不列入本轮写回（属扩充而非补缺，超出本轮范围）

  对 pubTypes 的映射不复用 Europe PMC 给的粗 `type` 字段，而是自建优先级表
  （与 zotero-journal-metrics/scripts/resolve_types.py 的 PUB_MAP 同源），
  以免把「临床试验」压成「论著」这类降级。

只读：本脚本不连 Zotero、不写库。产出 md + json 供人工过目。
"""
import argparse
import collections
import json
import os
import re

# ---- 细粒度映射：顺序即优先级 ----------------------------------------------
# 前置规则（先于本表）：若同时含 review 与 systematic review，后者更细，必须排在前面
PUB_MAP = [
    (r"meta-analysis", "Meta分析"),
    (r"systematic review", "系统综述"),
    (r"review", "综述"),
    (r"case reports", "病例报告"),
    (r"randomized controlled trial", "临床试验"),
    (r"clinical trial", "临床试验"),
    (r"guideline", "指南"),
    (r"editorial", "社论"),
    (r"comment", "评论"),
    (r"letter", "通讯"),
    (r"retract", "撤稿声明"),
    (r"journal article", "论著"),
    (r"research-article", "论著"),
]

# 判定「明确非论著」用的模式（用于 B 桶）
NON_RESEARCH = [
    (r"published erratum|erratum", "勘误"),
    (r"retract", "撤稿声明"),
    (r"editorial", "社论"),
    (r"comment", "评论"),
    (r"letter", "通讯"),
    (r"review", "综述"),
]
# 明确是研究性文献的标志（出现任一项则**不**进 B 桶）
#
# ⚠️ 关键：**不得**把通用的 "Journal Article" / "research-article" 当成研究性标志。
#    PubMed 会给读者来信/编辑部评论同时打上 "Journal Article"
#    （实测 `9N95AJD9` = ['letter','Journal Article']，实为读者来信；`TAN5DY7D` = ['Comment','Journal Article']）。
#    若把它们计入研究标志，B 桶会永远为 0 —— 那是**判据失效**，不是「库里干净」。
#    故此处只认**具体的研究设计/文献体裁**标记。
IS_RESEARCH = re.compile(
    r"clinical trial|randomized controlled trial|multicenter study|"
    r"comparative study|observational study|validation study|evaluation study|"
    r"case reports|meta-analysis|systematic review",
    re.I,
)

# 现有值里属于「细粒度、不得被粗分类覆盖」的
FINE_GRAINED = {"临床试验", "Meta分析", "病例报告", "指南", "社论", "会议论文", "系统综述", "通讯", "评论", "撤稿声明"}
UNRESOLVED = {"", "期刊论文(未识别)"}


# 标题级修正：pubTypes 只给 review 时，指南/共识类文献应在标题上再判一次
GUIDELINE_TITLE = re.compile(r"guidelines?\b|consensus\b|recommendations?\b", re.I)


def map_pubtypes(types, title=""):
    """pubTypes(英文 list) -> 细粒度中文值。命中即止，按 PUB_MAP 优先级。

    标题感知修正：ESC/AHA 指南在 PubMed 里常只标 `review-article`，
    单看 pubTypes 会得出「综述」，弱于实际体裁。若标题含 guideline/consensus/
    recommendation，且 pubTypes 指向 review 系，则提级为「指南」。
    （实测例：`JC7U4YT8` = 2021 ESC Guidelines on cardiac pacing，pubTypes 仅 `review-article`）
    """
    low = [str(t).lower() for t in (types or [])]
    if not low:
        return ""
    for pat, cn in PUB_MAP:
        if any(re.search(pat, t) for t in low):
            if cn in ("综述", "系统综述") and title and GUIDELINE_TITLE.search(title):
                return "指南"
            return cn
    return ""


def classify_non_research(types):
    """若 pubTypes 里出现明确非论著标志，返回该中文值；否则 None。"""
    low = " | ".join(str(t).lower() for t in (types or []))
    if not low:
        return None
    for pat, cn in NON_RESEARCH:
        if re.search(pat, low):
            return cn
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epmc", required=True)
    ap.add_argument("--types", required=True)
    ap.add_argument("--out", required=True, help="输出前缀（不带扩展名）")
    a = ap.parse_args()

    epmc = {r["key"]: r for r in json.load(open(a.epmc))}
    cur = json.load(open(a.types))

    bucket = {"A": [], "B": [], "C": []}
    stats = collections.Counter()

    for key, rec in cur.items():
        existing = (rec.get("type_cn") or "").strip()
        e = epmc.get(key) or {}
        pubtypes = e.get("pubTypes") or []
        full_title = e.get("title") or ""
        proposed = map_pubtypes(pubtypes, full_title)
        title = full_title[:70]

        row = {"key": key, "title": title, "existing": existing,
               "proposed": proposed, "pubTypes": pubtypes,
               "old_source": rec.get("source", ""), "doi": rec.get("doi", "")}

        if existing in UNRESOLVED:
            if proposed:
                row["action"] = f"{existing or '(空)'} → {proposed}"
                bucket["A"].append(row)
                stats["A"] += 1
            else:
                stats["A_无解"] += 1
                bucket.setdefault("U", []).append(row)
            continue

        if existing in FINE_GRAINED:
            stats["C_细粒度保留"] += 1
            continue

        if existing == "论著":
            nr = classify_non_research(pubtypes)
            # 只有当 pubTypes 明确指向非研究性文献、且不含任何研究性标志时才建议改
            if nr and not IS_RESEARCH.search(" | ".join(pubtypes)):
                row["action"] = f"论著 → {nr}"
                bucket["B"].append(row)
                stats["B"] += 1
            elif proposed and proposed != "论著":
                # 可细分（如 RCT / Meta 分析），但属扩充不属补缺 → 仅统计
                stats[f"C_可细分_{proposed}"] += 1
            else:
                stats["C_论著保留"] += 1
            continue

        stats[f"C_其他_{existing}"] += 1

    # ---- 落盘 json ----
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump({"generated": "2026-09-17", "buckets": bucket, "stats": dict(stats)},
              open(a.out + ".json", "w"), ensure_ascii=False, indent=1)

    # ---- 落盘 md ----
    L = []
    L.append("# 文章类型差异比对（只读 · 未写库）\n")
    L.append("> 口径：**只补缺口、不覆盖细粒度值**（用户 2026-09-17 确认）。")
    L.append(f"> 现有值来自 `{os.path.basename(a.types)}`；")
    L.append("> 候选值由 Europe PMC `pubTypes` 经**细粒度映射**推出（不直接采用其粗分类 `type`）。\n")
    L.append("> ⚠️ **基准必须是实时快照。** journal-metrics 运行过程中的中间产物（如 `zotero_types_20260916.json`）")
    L.append("> 只含**部分**已解析条目，拿它当「现有值」会把「当时尚未解析」误报成「未识别」，")
    L.append("> 从而虚增 A 桶。重新拉基准的正确做法见本技能 SKILL.md 的实时拉取片段。\n")

    L.append("## 汇总\n")
    L.append("| 桶 | 含义 | 条数 |")
    L.append("|---|---|---|")
    L.append(f"| **A 补充候选** | 现为未识别，可用 pubTypes 补上 | **{len(bucket['A'])}** |")
    L.append(f"| **B 修正候选** | 现标论著，pubTypes 明确指向非研究性文献 | **{len(bucket['B'])}** |")
    L.append(f"| C 保留 | 不动（细粒度已足够 / 论著维持 / 其他） | {sum(v for k, v in stats.items() if k.startswith('C_'))} |")
    L.append(f"| — 其中无法补齐 | 未识别且 pubTypes 也推不出 | {stats.get('A_无解', 0)} |")
    L.append("")

    L.append("### C 桶明细统计\n")
    L.append("| 情形 | 条数 |")
    L.append("|---|---|")
    for k, v in sorted(stats.items()):
        if k.startswith("C_"):
            L.append(f"| {k[2:]} | {v} |")
    L.append("")
    L.append("> ⚠️ `可细分_*` 一项属**扩充**而非补缺：现有「论著」条目中，pubTypes 提示了更细的类型")
    L.append("> （如 RCT → 临床试验），但现有值并没错。**按约定本轮不动**，仅作信息备查。\n")

    for code, name in (("A", "A 桶 · 补充候选（建议执行）"), ("B", "B 桶 · 修正候选（建议执行）")):
        rows = bucket[code]
        L.append(f"## {name} —— {len(rows)} 条\n")
        if not rows:
            L.append("（无）\n")
            continue
        L.append("| # | zotero_key | 现有 | → 建议 | pubTypes（Europe PMC 原文） | 标题 |")
        L.append("|---|---|---|---|---|---|")
        for i, r in enumerate(sorted(rows, key=lambda x: x["key"]), 1):
            pt = ", ".join(r["pubTypes"][:6]) or "（空）"
            L.append(f"| {i} | `{r['key']}` | {r['existing'] or '(空)'} | **{r['proposed']}** | {pt} | {r['title']} |")
        L.append("")
        L.append("> 逐条核对上方 `pubTypes` 原文后再决定是否执行；本报告**不代表已修改**。\n")

    unres = bucket.get("U", [])
    L.append(f"## D 桶 · 仍未能识别（Europe PMC 无匹配） —— {len(unres)} 条\n")
    L.append("> 这些条目现有值为「期刊论文(未识别)」，且 Europe PMC 也没给出 `pubTypes`，")
    L.append("> **本轮无法补齐**。需另走通道（PubMed esummary 按 PMID / Crossref 按 DOI），或人工判定。\n")
    if unres:
        L.append("| # | zotero_key | 标题 |")
        L.append("|---|---|---|")
        for i, r in enumerate(sorted(unres, key=lambda x: x["key"]), 1):
            L.append(f"| {i} | `{r['key']}` | {r['title']} |")
        L.append("")

    L.append("## 残余风险（本报告不能证明的事）\n")
    L.append("- B 桶为空**不等于**「库里没有错标」。它只说明：没有一条能用 Europe PMC 的 `pubTypes` **明确**判定为错标。")
    L.append("  仅凭元数据无法识别的错标（如系列文章中的单篇评论被标为论著）本报告查不出。")
    L.append("- 反过来，B 桶判据仍可能**误报**：某篇真正的论著若恰好同时被打了 `Comment`（如配发的编者按与原文共用记录），会被误列。故 B 桶一律**人工过目**后再执行。")
    L.append("- 现有值为「细粒度」的 30 条**一律未比对**（按约定保留），因此不排除其中也有错标。\n")

    L.append("## 写回前必读（技术注意）\n")
    L.append("1. **`merge_tags()` 只做并集、不做删除。** 写回前必须先剔除旧的 `文章类型-*` 标签，")
    L.append("   否则会出现 `文章类型-临床试验` 与 `文章类型-综述` 并存。")
    L.append("2. extra 里的「文章类型:」行走 `build_extra()` 的 `【期刊指标】` 标记块整块重建；")
    L.append("   标记**之前**的原有内容会原样保留。")
    L.append("3. 逐条 `PATCH`（批量端点返回 400）；Zotero 须处于运行状态。\n")

    open(a.out + ".md", "w").write("\n".join(L))
    print(f"A 补充候选 {len(bucket['A'])} · B 修正候选 {len(bucket['B'])}")
    print(f"→ {a.out}.md / {a.out}.json")


if __name__ == "__main__":
    main()
