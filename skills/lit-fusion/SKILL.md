---
name: lit-fusion
description: 融合文献检索 skill。默认采用「Consensus 优先 → 用其结果扩充 PubMed」策略：先跑 Consensus（语义检索 + citation_count + 盲区信号），再拿其命中结果按 DOI/标题回填 PubMed（取 PMID 与权威元数据）并叠加一次基础 PubMed 受控检索，最后按 DOI/标题归一化去重合并，自动分成「两库共有(交叉印证)/仅 PubMed(临床索引)/仅 Consensus(盲区补漏)」三类并输出统一 Markdown 报告。Consensus 额外提供 citation_count 质量信号。可选生成合并 RIS 并一键导入指定 Zotero 集合。当用户说「检索一下、两个库一起查、融合检索、找盲区、pubmed+consensus、交叉验证证据」时触发。
agent_created: true
---

# Lit Fusion — 融合文献检索

## Overview

本 skill 把两套互补的检索能力合并为一次调用：

- **PubMed (eutils)**：精确、同行评议、带 PMID，适合锁定具体文献与临床证据。
- **Consensus (REST API)**：覆盖 2.2 亿篇（含 Scopus / arXiv / preprint），带 AI 综合与 `citation_count` 引用数质量信号，适合快速摸清证据全貌、补足 PubMed 未收录的盲区。

核心价值：**默认采用「Consensus 优先 → 用其结果扩充 PubMed」策略**——先跑 Consensus（拿语义命中与盲区信号 + citation_count），再用其命中结果按 DOI/标题回填 PubMed（拿到 PMID 与权威元数据），并叠加一次基础 PubMed 受控检索，最后跨库去重 → 三类分层报告（交叉印证 / 临床索引 / 盲区补漏）+ 可选 Zotero 入库。适用于立题证据链构建、假设论证、盲区扫描、跨库交叉验证。

> 策略说明：相比旧版「两库并行、各自按原 query 检索」，新版让 PubMed 侧**由 Consensus 的命中驱动**，能针对 Consensus 实际找到的文献精准回填权威 PMID，减少「宽 OR 查询淹没 / 盲区虚高」的旧问题（见下方集成要点）。

## When to Use

- 用户要求「检索 XX 主题」「两个库一起查」「融合检索」「找 PubMed 没覆盖到的盲区」「交叉验证一下证据」。
- 立题阶段需要同时看「同行评议临床证据」与「跨库综合/ preprint 信号」。
- 想把检索结果直接归档进 Zotero 指定集合。

## Dependencies

- **Consensus API key**：存于 `~/.workbuddy/consensus_auth.json`，结构 `{"api_key": "..."}`。免费档 30 次/月，注意预算。
- **zotero-import skill**：`~/.workbuddy/skills/zotero-import/scripts/zotero_import.py`。仅在 `--import-to` 时调用，用于把合并 RIS 导入指定 Zotero 集合（已封装本地 API 端点踩坑）。
- 仅依赖 Python 标准库（urllib / json / xml），无需 pip 安装。

## Quick Start

```bash
# 基础融合检索（默认每库上限 15，输出报告到 ~/lit_fusion_report.md）
# 默认策略：Consensus 优先 → 用其命中结果扩充 PubMed（回填 PMID + 基础受控检索）→ 去重分三类
python3 ~/.workbuddy/skills/lit-fusion/scripts/fusion.py "cardiac resynchronization therapy stroke risk"

# PMID -> RIS（Consensus 盲区文献回填权威 DOI 后归档）
python3 ~/.workbuddy/skills/lit-fusion/scripts/pubmed2ris.py 30216113,20176989 -o out.ris

# 限定年份 + 仅人体研究 + 控制规模
python3 ~/.workbuddy/skills/lit-fusion/scripts/fusion.py "intraventricular flow stasis thrombosis" --year-min 2018 --human --limit 10

# 检索并直接归档进 Zotero 集合（自动建集合 + 批量移动）
python3 ~/.workbuddy/skills/lit-fusion/scripts/fusion.py "left ventricular thrombus heart failure" --import-to "CRT_心衰_心内血栓_脑梗"

# 只看某一库（节省另一库配额）
python3 ~/.workbuddy/skills/lit-fusion/scripts/fusion.py "xxx" --pubmed-only
python3 ~/.workbuddy/skills/lit-fusion/scripts/fusion.py "xxx" --consensus-only
```

## 输出物

1. **Markdown 报告**（默认 `~/lit_fusion_report.md`）：
   - 总览：三类计数。
   - 一、两库共有（交叉印证，最优先采用）—— 附 PMID + Consensus 引用数 + 链接。
   - 二、仅 PubMed（临床索引/同行评议）。
   - 三、仅 Consensus（盲区补漏，按引用数降序）—— 附链接。
   - 四、使用提示（含 Consensus 配额提醒）。
2. **合并 RIS**（默认 `~/lit_fusion_combined.ris`）：PubMed 全文元数据 + Consensus-only 最佳可得字段，供 Zotero 导入。

## Workflow

1. 解析查询与过滤参数（年份、是否人体、每库上限）。
2. **Consensus 优先**：调用 Consensus `v1/search`（带 `x-api-key`），取标题/作者/摘要/URL/引用数/DOI，作为检索主线。
3. **用 Consensus 结果扩充 PubMed**：`expand_pubmed_from_consensus()` 逐条拿 Consensus 命中，按 DOI（`[AID]`）精确回填 → 缺 DOI/未命中时按标题 3-token 子串 `[tiab]` 兜底，取回 PMID 与权威元数据（带 `via=doi/title` 标注）。
4. 叠加一次**基础 PubMed 受控检索**（`pubmed_search`，用原 query，仍推荐受控语法），补 Consensus 未覆盖的同行评议文献。
5. 合并（回填优先去重）后，按 `DOI`（优先）与标题归一化（小写、去非字母数字）分三类。
6. 写 Markdown 报告 + 合并 RIS。
7. 若 `--import-to` 给定，调用 `zotero-import` 把 RIS 导入该集合。

## 集成要点（详见 references/notes.md）

- **去重策略**：先按 DOI（小写）匹配，否则按标题归一化匹配。Consensus 标题需清理（去换行/多余空格）后与 PubMed 比对。
- **盲区定位**：「仅 Consensus」通常含 preprint / Scopus / 工程类文献，未经同行评议比例高，引用前须核对原始出处——这是该 skill 相对纯 PubMed 的最大增量。
- **配额管控**：Consensus 免费档仅 30 次/月；高频检索建议 `--pubmed-only` 或降低 `--limit`，保留 Consensus 给「假设论证/盲区扫描」关键节点。
- **年份过滤（已修 bug，勿退化）**：`--year-min/--year-max` 必须同时作用于两库。曾经只传给 Consensus，PubMed 侧静默返回 2001/2002 等越界文献。现在 `pubmed_search()` 用 esearch 的 `datetype=pdat&mindate&maxdate` 实现；Consensus 结果再按 `--limit` 截断（API 会多返回几行）。
- **「仅 Consensus」≠ 真的 PubMed 未收录**：Consensus 标题常带换行/大小写/标点差异（如 `LV` vs `Left Ventricular`、问号结尾），归一化匹配会失败，导致明明有 PMID 的论文被误分为「盲区」。回填流程：按标题/作者回 PubMed 搜 → 拿到 PMID/DOI → `pubmed2ris.py` 生成权威 RIS → `zotero-import` 归档。实测两篇「盲区」文献均可找回（PMID 30216113、20176989）。
- **宽查询的语义漂移**：`(LBBB OR "heart failure") AND (stroke OR thromboembolism)` 这类 OR-宽查询，PubMed 侧会被房颤文献淹没，Consensus 侧则退化成纯 LBBB 文献，两库重叠为 0。想要 LBBB→卒中的独立信号，应把 LBBB 拆成独立窄查询，而不是靠 OR 拼接。
- **PubMed 侧是「空格即 AND」——长自然语言查询会静默归零**（2026-09-15 实测）。`fusion.py` 把 `query` 原样作为 esearch 的 `term`，所以 `"low voltage zone atrial fibrillation catheter ablation substrate"` 会被解析成 **7 个词的 AND 交集**，实测只返回 0–8 条（甚至 0 条）；而 Consensus 侧是语义检索仍返回 20 条 → 报告里「仅 Consensus」虚高，看起来像 PubMed 盲区，实际是查询写法问题。**正确做法：PubMed 侧一律改用受控语法**：
  ```bash
  python3 fusion.py '("low-voltage zone"[tiab] OR "low-voltage area"[tiab]) AND ("atrial fibrillation"[tiab]) AND (ablation[tiab])' --pubmed-only --limit 30
  ```
  同一主题实测：自然语言查询 0 条 → 受控语法 30 条。
- **回填时必须校验标题匹配，否则静默误配**（2026-09-15 实测，47 条中 2 条误配）。按标题回查 PubMed 时，短语检索可能命中**完全不相干**的论文（「Nademanee 2004 CFAE 原始定义」→ 命中 Reddy 2019 PFA；「峰值频率表征重构」→ 命中左房/左室容积比）。务必用归一化标题做双向包含判断，**不要取 `idlist[0]` 盲信第一条**；摘要为空或题名不符的条目一律人工复核。
- **会议摘要回填不到是正常的**。DOI 形如 `10.1093/europace/euad122.757`（Europace 增刊）或 `euae102.213` 的条目属 EHRA 大会摘要，PubMed 通常不收录 → 属**真盲区**而非误配，报告里应显式标注「会议摘要，无全文，不可作为独立论据」。
- **与既有 skill 协作**：检索报告如需发出，可再调用 `md-to-docx` 转 Word；需精确导入时由 `zotero-import` 承接。三者形成「检索→转化→归档」闭环。
- **⛔ 导入 Zotero 后必须扫一遍「前导 `- `」污染**（2026-09-18 实测）。`/connector/import` 导入 RIS 后，
  title/期刊/年份/作者/摘要会**全员**被加上 `- `（translator 取值起点偏移一个字符）。
  判据：`title.startswith('- ')`。**本 skill 生成的 RIS 走这条路同样中招**——不是本 skill 的 bug，
  但本 skill 的下游就是 Zotero，所以要在流程里补这一道检查。
  修复脚本见 `~/TeachingAI_Vault/90_Meta/State/fix_zotero_dash.py`（可直接复制到别处用）。
- **⚠️ Consensus 的 `AU` 字段格式不统一**（2026-09-18 实测）：既有 "Yizhou, Fan"（名, 姓）也有 "Wu, Rong"（姓, 名）。
  Zotero 一律按「姓, 名」解析 → 前者的 lastName/firstName 被颠倒。
  **不要盲目交换**，用 Europe PMC 的 `first_author` 做锚判定（见 `research-vault-pipeline` 技能同名条目）。
  另：Consensus 常缺 `PY`（年份）与 `JO`（刊名），写报告与 RIS 时会显示「年份缺/刊缺」，属**预期行为**，不是抓取失败。
- **教育/社科主题上 Consensus 的增量价值远高于医学主题。** 2026-09-18 实测：教学 × AI 主题下
  Consensus 补漏命中的 AJPE 2026《Wielding Magic Without Mastery: The Illusion of Competence in the Age of AI》
  正中课题核心，而 PubMed 侧没有——**教育学刊被 PubMed 收录的比例低**，这类主题务必跑 Consensus。
- **多查询融合时要自己写去重。** 本 skill 一次只接一个 `query`；跑 N 个窄查询后
  用 `~/TeachingAI_Vault/90_Meta/State/merge_search.py` 按 DOI/标题归一化合并（可直接复制改 `QUERIES` 常量）。
  **窄查询优于宽 OR 查询**（见上文「宽查询的语义漂移」）。
