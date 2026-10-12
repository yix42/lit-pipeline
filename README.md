# lit-pipeline — 文献管线工具包

把一条完整链路打包成可移植的 git 仓库：

```
PubMed + Consensus 检索  →  建 L1/L2 卡  →  入 Zotero 库  →  Obsidian(vault)  →  Folio 文献工作台
   (lit-fusion)            (batch-intake)   (zotero-*)       (research-vault)   (folio 接入口)
```

换机 clone 后，配好几个占位符即可复现整条流水线。所有本地密钥 / 数据 / 第三方库都已排除在版本控制之外。

---

## 一、仓库结构

```
lit-pipeline/
├─ skills/                          # 8 个链路 skill（检索→入库→建卡→指标→MCP 连接器）
│  ├─ lit-fusion/                   # ① PubMed eutils + Consensus REST 融合检索（Consensus 优先策略）
│  │  └─ scripts/fusion.py pubmed2ris.py
│  ├─ zotero-local/                # ② 本地 Zotero HTTP API（localhost:23119）
│  ├─ zotero-import/               # ③ RIS→Zotero 集合、去重、按集合查
│  ├─ zotero-fulltext-feasibility/ # ④ 全文 7 值通道判定 + OA/PMC 抓取 + pdf→md
│  ├─ zotero-journal-metrics/      # ⑤ 期刊指标（ISSN→Crossref→JCR/IF）三级匹配
│  ├─ zotero-mcp-connector/        # ⑥ zotero-mcp node 服务说明
│  ├─ research-vault-pipeline/     # ⑦ Obsidian vault 四层 L0–L4 手册 + 校验器口径 + 引语闸门
│  └─ literature-batch-intake/     # ⑧ 批量入库脚本 + verify_note_quotes 引语闸门（唯一真源）
│
├─ folio/                          # Folio 文献工作台「接入口」（不含 app 主体 / data / vendor）
│  ├─ server/                       # MCP + HTTP 服务层（mcp.js / http.js / store.js / tools.js / vault.js / locate.js）
│  ├─ tools/                        # 摄取脚本：_ingest_paper / _pdf2folio / _cards_pdf / _cards_l2 / _import_note
│  └─ README-MCP.md                 # 连法与数据源说明
│
├─ config/                          # 配置模板（占位符，无真实密钥）
│  ├─ .mcp.json.template            # 填好后 → ~/.workbuddy/mcp.json
│  ├─ consensus_auth.json.template  # → ~/.workbuddy/consensus_auth.json
│  └─ zotero_local_auth.json.template # → ~/.workbuddy/zotero_local_auth.json
│
├─ docs/
│  └─ PIPELINE.md                  # 分步操作手册（检索→入库→建卡→Folio）
│
└─ .gitignore                        # 排除真实密钥、folio.json 数据、vendor、pycache、zip
```

---

## 二、快速上手（换机 5 步）

1. **clone** 本仓库。
2. **配 3 个认证文件**（从 `config/` 模板复制，填真实值）：
   - `config/consensus_auth.json.template` → `~/.workbuddy/consensus_auth.json`
   - `config/zotero_local_auth.json.template` → `~/.workbuddy/zotero_local_auth.json`
   - `config/.mcp.json.template` → 合并进 `~/.workbuddy/mcp.json`
   - 每个模板里的 `${...}` 占位符和 `YOUR_...` 都替换成本机路径 / 密钥。
3. **装依赖**：
   - Python：`pypdf`、`pymupdf`（全文抓取 / 双栏 PDF 重排兜底）。
   - MinerU 4.x（可选，默认 PDF→md 引擎）：`pip install mineru`（受管 venv）。
   - Node：`node`（Zotero MCP + Folio 服务）。
4. **装 skill**：把 `skills/` 下各目录拷到 `~/.workbuddy/skills/`（或项目级 `<proj>/.workbuddy/skills/`）。
5. **跑一次检索验证**：
   ```bash
   python3 skills/lit-fusion/scripts/fusion.py "omnipolar voltage mapping atrial fibrillation" \
       --limit 15 --out ~/lit_report.md --ris ~/lit.ris
   ```
   能出 Markdown 报告 + RIS 即链路通。

详细分步（含各阶段产物、校验器、引语闸门）见 **[docs/PIPELINE.md](docs/PIPELINE.md)**。

---

## 三、五个阶段的命令速查

| 阶段 | 用什么 | 一句话 |
|---|---|---|
| ① 检索 | `lit-fusion` | `fusion.py <query>` → Consensus 优先，回填 PubMed，出报告 + 合并 RIS |
| ② 入 Zotero | `zotero-import` | `zotero_import.py --collection <集> --ris <文件>`（或 `--pmids`） |
| ③ 全文/可取性 | `zotero-fulltext-feasibility` | `fetch_fulltext.py` 判 7 值通道；能取就一路做到底 |
| ④ 建卡进 Obsidian | `research-vault-pipeline` + `literature-batch-intake` | 落 L1/L2，`verify_note_quotes.py --json` 引语闸门，`validate_vault.py` 校验 |
| ⑤ 指标 | `zotero-journal-metrics` | ISSN→刊名→Crossref 三级匹配回写 IF/JCR |
| ⑥ 进 Folio | `folio/`（MCP/HTTP） | `_ingest_paper.js` / `_pdf2folio.js` / `_cards_pdf.js` 喂给 `data/folio.json` |

---

## 四、版本控制边界（重要）

**入版本库**：脚本、skill 手册、配置模板、Folio 服务层与摄取脚本、文档。
**不入版本库**（`.gitignore` 已挡）：

- 真实密钥：`consensus_auth.json` / `zotero_local_auth.json`（只入 `.template` 占位符）。
- 用户数据：`folio/data/folio.json`（4.2M，个人文献）、任何 `*.zip`。
- 第三方库：`folio/vendor/`（1.4M，按需 `npm i` 重建）。
- 运行噪声：`__pycache__/`、`.DS_Store`、临时报告 `lit_fusion_*.md/.ris`、`_review/ _shots/ _snapshots/`。

> 首次在本机跑通后，如需把这些 skill 也用起来：直接拷进 `~/.workbuddy/skills/`。仓库里的副本是「可移植母本」。
