# 文献管线操作手册（PIPELINE）

从「检索」到「Folio 工作台」的完整链路，六个阶段，每阶段给出口、产物、命令与判据。

```
query ──► ①检索(lit-fusion) ──► ②入Zotero(zotero-import)
        ──► ③全文可行性(zotero-fulltext-feasibility)
        ──► ④建卡进Obsidian(research-vault-pipeline + batch-intake)
        ──► ⑤期刊指标(zotero-journal-metrics)
        ──► ⑥进Folio(folio 接入口)
```

约定：
- `VAULT` = 你的 Obsidian vault 根（默认 `~/ResearchVault`，可用 `RESEARCH_VAULT` 环境变量覆盖）。
- `FOLIO_DIR` = Folio 工作台目录（默认 `~/Folio/文献工作台`）。
- 认证文件都放 `~/.workbuddy/`（见 `config/` 模板）。

---

## ① 检索 — lit-fusion

**策略**：Consensus 优先（语义检索 + `citation_count` + 盲区信号）→ 用其命中按 DOI/标题回填 PubMed（取 PMID 与权威元数据）→ 叠加一次基础 PubMed 受控检索 → 按 DOI/标题归一化去重合并 → 分三类：两库共有（交叉印证）/ 仅 PubMed（临床索引）/ 仅 Consensus（盲区补漏）→ 统一 Markdown 报告。

```bash
python3 skills/lit-fusion/scripts/fusion.py "omnipolar voltage mapping atrial fibrillation" \
    --limit 15 \
    --year-min 2015 \
    --out ~/lit_fusion_report.md \
    --ris ~/lit_fusion_combined.ris
```

常用开关：
- `--consensus-only` / `--pubmed-only`：单库。
- `--import-to <集合名>`：出报告的同时直接调 zotero-import 入指定 Zotero 集合。
- `--human` / `--no-human`：Consensus 是否只取人体研究。
- `--api-key-file`：默认读 `~/.workbuddy/consensus_auth.json`。

**产物**：`lit_fusion_report.md`（分类报告）+ `lit_fusion_combined.ris`（合并 RIS）。
**判据**：报告里「仅 Consensus」那一栏就是 PubMed 盲区，重点看。

---

## ② 入 Zotero — zotero-import

```bash
# 从 RIS 导入指定集合
python3 skills/zotero-import/scripts/zotero_import.py \
    --collection "心电_基质" --ris ~/lit_fusion_combined.ris --tags "litfusion"

# 或直接给 PMID
python3 skills/zotero-import/scripts/zotero_import.py \
    --collection "心电_基质" --pmids 34954276,41864305 --dry-run   # 先看
```

- 本地写入用 `zotero_local_auth.json`；`--dry-run` 先试。
- 去重 / 查集合 / 建集合走 `zotero_ops.py`；本地 API 读走 `zotero-local` skill 的 `zotero_api.py`。

**铁律**：L1 卡里的 `zotero_key` 必须是真实 8 位 key（来自 Zotero）。不在 Zotero 的按先例用合成 8 位 key（如 `VSCH2026`），并在 L4 档案标 `source_type: none`。

---

## ③ 全文可行性 — zotero-fulltext-feasibility

判定全文通道（7 值枚举）：`none / epmc_xml / pmc_html / oa_pdf / pdf_local / subscription / manual`。

```bash
# 单篇探可取性
python3 skills/zotero-fulltext-feasibility/scripts/fetch_fulltext.py <key_or_pmcid>

# 能取到的渠道（epmc_xml / pmc_html / oa_pdf）直接落到 40_Fulltext
```

**取全文的铁律**：取不到就一句话报「哪几个 key、卡在哪条通道」，取到了就一路做到底（落 L4 档案 → L1 卡状态回写 → L2 精读笔记 → 索引/校验器同步），不取到手就停手。

---

## ④ 建卡进 Obsidian — research-vault-pipeline + literature-batch-intake

五层：

```
00_Consensus(L0 检索入口) → Zotero → 10_Triage(L1 分诊) → 20_Notes(L2 精读)
        → 30_Knowledge(L3 六类知识页) → 40_Fulltext(L4 全文档案)
```

- **L0**（`type: consensus_synth`）：query 级 AI 综合快照，恒 `evidence_grade: interpretation`，不可直接进文稿；`notes_keys` 里每个 8 位 key 必须有 L4 全文档案才能挂 `[[双链]]`。
- **L1 分诊卡**五字段：方案 / 结果 / 结论 / 创新点（「作者自述」+「我的增量判断」两层）/ 对我研究的用途。
- **L2 精读**：引语必须逐字取自原文；`verify_note_quotes.py` 是唯一真源（归一化引擎不得被外部重写）。
- **L3 六类页**：KT/KC/KM/KR/KV/KS，`KS` 需可证伪问句；争议只进 KV。
- 批次统计只认 `L1_batch_input_*.json`，不认 `triage_date`。

**入库即质检 + 校验**：

```bash
cd $VAULT/90_Meta/State
RESEARCH_VAULT=$VAULT python3 verify_note_quotes.py --json          # 全库引语闸门
RESEARCH_VAULT=$VAULT python3 verify_note_quotes.py --json <KEY>    # 单篇
python3 $VAULT/90_Meta/Schema/validate_schema.py   # L3 + 模板
python3 $VAULT/90_Meta/Schema/validate_vault.py    # L0+L1+L2+L3+L4+双链+残留
```

**L1 索引用脚本生成，不手抄**：`gen_l1_index.py`。
**索引表 / 引语闸门 / L3 硬闸（`gate_l3.py`）未过不得进 L3。**

---

## ⑤ 期刊指标 — zotero-journal-metrics

三级匹配：`ISSN` → `归一化刊名` → `DOI→Crossref`。回写 IF / JCR 分区。

```bash
# 详见 skills/zotero-journal-metrics/SKILL.md（脚本：zot_audit / zot_bulk / resolve_noif / make_report）
```

**判据**：全库仅约 12% 有 ISSN，命中前缀/后缀必须候选唯一；`evidence_grade` 不因链上 DOI 升级。

---

## ⑥ 进 Folio — folio 接入口

Folio 数据源 = `FOLIO_DIR/data/folio.json`（唯一真实数据源 + 自动快照）。两条喂法：

1. **MCP（WorkBuddy 对话直连）**：`folio/server/mcp.js`（stdio），配进 `~/.workbuddy/mcp.json`（模板见 `config/`）。AI 建的卡 → 浏览器刷新即可见，已锚定原文位置。
2. **HTTP（8787）**：`folio/server/http.js`，起 `FOLIO_DIR` 下 `启动.command` / `node server/mcp.js`。

**摄取脚本**（`folio/tools/`）：

| 脚本 | 用途 |
|---|---|
| `_ingest_paper.js` | 单篇 PDF → 建 Folio 卡（含原文锚定） |
| `_pdf2folio.js` | 批量 PDF → Folio |
| `_cards_pdf.js` | 把 vault 的 L1/L2 卡导出成 PDF 卡 |
| `_cards_l2.js` | L2 精读卡 → Folio |
| `_import_note.js` | 导入已有笔记 |
| `make_sample_pdf.py` | 造样例 PDF 测链路 |

**离线兜底**：`file://` 打开 `app.html` 默认不发网络请求，降级 localStorage；`http://127.0.0.1:8787/` 自动连，指示器「已同步」。

---

## 附：环境依赖

| 依赖 | 用途 | 安装 |
|---|---|---|
| Python 3.9+ | 全部 `scripts/*.py` | 系统即可 |
| `pypdf` `pymupdf` | 全文抓取、双栏 PDF 重排兜底 | `pip install pypdf pymupdf` |
| `mineru` 4.x（可选） | 默认 PDF→md 引擎 | 受管 venv `pip install mineru`（UDS socket，非 TCP） |
| `node` | Zotero MCP + Folio 服务 | 系统 / 受管 |
| Zotero 桌面 | 本地 API `:23119` | 已装 |
| MinerU 桌面版 app | **不入链路**（独立 GUI 走云端） | 仅作对照 |

> 密钥与个人数据不入版本库。首次跑通后，把 `skills/` 各目录拷进 `~/.workbuddy/skills/` 即完成本机安装。
