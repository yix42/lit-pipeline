---
name: zotero-fulltext-feasibility
description: 探测一个 Zotero 文献库的「全文可得率」，并为 PDF→Markdown 转换选型提供实测依据。当需要判断某个文献库能不能做精读流水线、该走哪条全文获取通道（Europe PMC XML / PMC 文章页 / OA PDF / 机构订阅）、先用 `pubTypeList` 补文章类型闸门、或用哪个转换引擎（PyMuPDF / pymupdf-layout / pymupdf4llm / MinerU）时使用。含十篇真实文献的逐通道实测、MinerU 4.0 服务端架构变更与三个安装坑的复现解法。产出是带数字的可行性判断，不是空泛建议。
agent_created: true
---

# Zotero 全文可得性探测与转换选型

## 何时用

- 准备给某个 Zotero 分类做精读/知识库，**先确认全文拿不拿得到**（否则整条流水线会卡在第一关）
- 要决定用不用 MinerU，需要知道"不用会损失什么"
- 需要给用户一份"哪些文献能自动处理、哪些必须人工"的清单

## 核心结论（2026-09 在真实论文库上的实测，可直接引用）

1. **全文可得率强烈依赖年代**，不是均匀的。某医学库实测：2015 前 26% · 2016–2020 56% · 2021–2023 76% · 2024 后 68%，全库 61%。
   → **按年代分流**：近 5 年自动化，2015 年前直接转人工，别在自动链路上浪费。
2. **Europe PMC 全文 XML 质量高于 PDF**。它是出版商原生 XML，含 `<sec>`/`<table-wrap>`/`<fig>` 结构元素，**完全不需要版面重建**。但覆盖率有限（某 15 篇试点仅 6 篇可用）。
3. **轻量 PDF 提取：正文可用，表格不可靠，公式不可用**。PyMuPDF 在 10 份真实 PDF 上平均断行率 0.53%、0.2–0.9 秒/篇（MinerU 为分钟级）。
4. **⚠️ 不要用坐标重排文本**——详见下方"最大的坑"。
5. **要表格就装 `pymupdf-layout`，不要装 MinerU**（2026-09 新增实测）：CFD 论文上表格检出 0 → 3 张，含网格分辨率/时间步长/雷诺数等核心数值表。成本仅 +7 个包 / 约 120 MB / **零模型下载 / 零 API key / 全本地**。见下方"转换引擎选型（实测版）"。
6. **MinerU 4.0 已改为客户端+服务端架构**：pip 装完 112 个包 / 666 MB 后，本机**仍然没有可用的解析引擎**（`parse_server.local.mode = disabled`）。`--tier flash` 只能给纯文本档。详见下方"MinerU 4.0 的真实状态"。
7. **分诊前必须先补文章类型**（2026-09-17 新增，**强烈建议**）：`oa_probe.py` 产出的 `type` 字段是空的，必须用 Europe PMC 的 `pubTypeList` 补齐，否则会把**会议摘要 / 编辑部评论当论著**分诊。某 15 篇试点实测拦下 **4 篇**（3 篇 Europace `Suppl` 会议摘要 + 1 篇 `letter`）——其中会议摘要根本没有全文，整条链路会在取全文关卡白跑。脚本：`scripts/enrich_article_types.py`。
8. **Europe PMC 的 `fullTextXML` 会稳定返回 HTTP 500**（不是限流，重试无效），此时**回落 PMC 文章页 HTML 是有效通道**。但必须用 `curl` + 浏览器 UA——`urllib` 会被拦成约 20 KB 的统一挑战页（多篇文件大小完全相同即为特征）。脚本：`scripts/pmc_html_to_md.py`。

## ⚠️ 两个判重陷阱（2026-09-17 实测发现）

投给会议的摘要与后续正式论著**常同题**，若不判重会被当成两条独立证据、人为放大证据强度。某库 15 篇试点里就命中 **2 组**：

| 组 | 会议摘要 | 正式论著 |
|---|---|---|
| 1 | Europace 2025;27(Suppl 1) | Clinical Cardiology 2026;49(9) |
| 2 | Europace 2024;26(Suppl 1) `euae102.015` | J Cardiovasc Electrophysiol 2024;35(6) |

**陷阱**：Semantic Scholar 会把**会议摘要的 PMCID** 报成论著的 `PubMedCentral` 字段。拿它去取全文，取回的是摘要记录（`article-type="abstract"`，正文 0 字），而**不是**论著全文。必须核对取回内容与目标论著是否一致。

## ⚠️ 已有类型字段不可盲信（2026-09-17 新增，第二个类型陷阱）

若库里**已经**有文章类型字段（如上一轮 journal-metrics 批次写的 `文章类型-*` 标签与 extra 的「文章类型:」行），**不要**默认它是对的。实测（某心内科库，**实时** 380 条）：`9N95AJD9` 是**读者来信**却被标成「论著」，`JC7U4YT8` 是 **2021 ESC 起搏指南**却被标成「论著」，`TAN5DY7D` 是**评论**、`7CYSNY8J` 是**综述**，同样都被标成「论著」。**4 条全是「该是别的、却写成论著」这一个错法。**

**为什么会错**：PubMed 给读者来信、编辑部评论同时打 `Journal Article` 标签（实测 `['letter','Journal Article']`、`['Comment','Journal Article']`）。任何「pubTypes 含 journal article 就算论著」的判据都会漏掉它们。

→ **判据修正**：识别非论著时**不得**把通用的 `Journal Article` / `research-article` 当作研究性标志，只认**具体的研究设计/文献体裁**标记（RCT、multicenter study、case reports、meta-analysis…）。

→ **顺带一提**：指南/共识在 PubMed 里常只标 `review-article`，单看 pubTypes 会判成「综述」。须**再看标题**——含 `guideline` / `consensus` / `recommendation` 时提级为「指南」。

### 回写口径：只补缺口，不覆盖细粒度值

Europe PMC 只给**粗粒度四分类**（论著/综述/非论著/未标类型），而库里的现有值往往**更细**（临床试验 / Meta分析 / 病例报告 / 指南 / 社论）。用粗分类全量覆盖会把细粒度值**降级**——而正是这些细分在分诊时最有区分度。

| 情形 | 动作 |
|---|---|
| 现为「未识别」/空 | Europe PMC 有类型则**补上**（且用细粒度映射，不直接用它的粗分类） |
| 现为细粒度值 | **一律保留**，粗分类不得覆盖 |
| 现为「论著」而 pubTypes 明确指向非研究性文献 | 列为**修正候选**，人工过目后再改 |

实测某库（**实时** 380 条）：真正可动作的只有 **4 条**、且**全部是「论著→非论著」的修正**，补充候选为 0；另有 49 条 Europe PMC 也无匹配（多为非生物医学条目，需另走 PubMed/Crossref）。**「几千条待回写」往往是伪问题——先跑只读比对再决定。**

脚本：`scripts/diff_types.py`（只读，产出 md + json 供人工过目，不碰 Zotero）。

**写回时的坑**：`merge_tags()` 只做并集、**不做删除**。若直接追加新的 `文章类型-*` 标签，会出现 `文章类型-临床试验` 与 `文章类型-综述` 并存。必须先 `[t for t in old if not t.startswith("文章类型-")]` 剔除旧的再加新值。

### ⚠️ 基准必须取实时，不得复用批处理中间产物（2026-09-17 踩坑，虚报 4 条）

journal-metrics 运行**中途**产出的 `zotero_types_YYYYMMDD.json` 只含**已解析的那部分**条目。
拿它当「现有值」基准，会把「**当时尚未解析**」误报成「**未识别**」，从而虚增补充候选——
实测虚增 4 条、**全部为伪报**（实时核实这 4 条早已有正确的类型标签：3 条「论著」+1 条「综述」）。
更隐蔽的是：**误报看起来完全合理**（现有值「未识别」+ Europe PMC 有 pubTypes = 一条像模像样的补充候选），
不查实时状态根本发现不了。

**正确做法：从实时 Zotero API 重建基准**（标签优先，回落 extra）：

```python
import json, urllib.request
BASE = 'http://localhost:23119/api/users/<userID>'
out, start = {}, 0
while True:
    req = urllib.request.Request(f'{BASE}/items?limit=100&start={start}',
                                 headers={'Zotero-API-Version': '3'})
    with urllib.request.urlopen(req, timeout=30) as r:
        batch = json.load(r)
    if not batch:
        break
    for it in batch:
        d = it['data']
        tags = [t['tag'] for t in (d.get('tags') or []) if t['tag'].startswith('文章类型-')]
        et = ''
        for line in (d.get('extra') or '').splitlines():
            if line.startswith('文章类型:'):
                et = line.split(':', 1)[1].strip(); break
        out[d['key']] = {'type_cn': tags[0].replace('文章类型-', '') if tags else et,
                         'raw': [], 'source': 'live'}
    start += len(batch)
    if len(batch) < 100:
        break
json.dump(out, open('zotero_types_live.json', 'w'), ensure_ascii=False, indent=1)
```

**同源教训**：**中间产物缺值 ≠ 源头缺值**。凡用于「差异比对」的基准都必须取自权威源（实时 API），
不能取自上一轮批处理的中间文件。这与「先跑只读比对再决定」是同一条原则的两端——
一端防「拿旧结论当现状」，另一端防「拿半成品当现状」。
**顺带**：库的条数也要现查。实测「331 条」是某次抓取的口径，实时是 **380 条**——差 49 条会直接影响分母与缺口判断。

### ⚠️ 全文档案 frontmatter：`zotero_key` ≠ `pmcid`

`scripts/pmc_html_to_md.py` 早期版本把第一参数（PMCID，如 `PMC9214588`）直接写进了 frontmatter 的
`zotero_key`。而 `zotero_key` 在 vault 里是**全库唯一主键（Zotero 8 位 key）**，L2 笔记靠它反查 `fulltext_path`——
写错会让笔记指向一个不存在的键。**已修**：`extract()` 新增 `zkey` 形参，frontmatter 分别输出
`zotero_key`（真 key）与 `pmcid`（PMCID）。**转换后务必 grep 一遍 frontmatter 自检。**

**⚠️ 这条坑会「第二次复发」——因为修脚本只堵住了脚本路径。**
实测 `VBX4SZCD.md`（欧洲起搏杂志 WAVE-MAP AF，PMC10410193）的 `zotero_key` 仍被写成 `PMC10410193`，
原因是**该篇未走脚本**：脚本已修好后，遇到「自动通道失败 → 人工/改用 `fetch_fulltext.py` 单篇取回」的场景，
frontmatter 就由人工或另一条代码路径生成，旧 bug 原样重现。**且该篇 `doi` 字段当时为空。**

→ **判据不是「脚本修了没有」，而是「这篇的 frontmatter 是怎么生成的」**。
只要不是走已修的 `pmc_html_to_md.py`，就必须手工核三项：`zotero_key` 是 8 位 ASCII 大写字母+数字、
`pmcid` 以 `PMC` 开头、`doi` 非空。
→ `ResearchVault` 侧已把此项纳入 `validate_vault.py`（`zotero_key` 必须 `fullmatch(r"[A-Z0-9]{8}")`），
**取完全文立即跑一次即可，不必靠记性。**

## 全文通道优先级（10 篇真实文献、3 处阻塞的实测结果）

按此顺序尝试，前一档失败再降级：

| 优先级 | 通道 | 实测 | 说明 |
|---|---|---|---|
| 1 | `epmc_xml` | ✅ 5/7 成功 | 首选，结构化最佳（`<sec>/<table-wrap>/<fig>`） |
| 2 | `pmc_html` | ✅ 2/2 成功 | XML 返回 500 时的有效替代；须 `curl` + 浏览器 UA |
| 3 | `oa_pdf`（出版商直链） | ❌ 0/3 | **Elsevier / Wiley / JAMA 三家全部拒绝**：Elsevier 按 IP 返回 Reference number 拒绝页，Wiley 用 Cloudflare 拦 headless（真实 Chromium 也不通过） |
| 4 | 机构仓库 | ❌ | 站点可达性不稳定（实测 QMRO 返回 `ERR_EMPTY_RESPONSE`） |
| 5 | `oa.fcgi`（NCBI OA API） | ❌ | **端点已废弃**，返回 404，不要再试 |
| 6 | `subscription` / `manual` | — | 兜底。非 OA 或反爬拦截时，如实记录并交人工，**不要伪造或拼凑** |

**通道枚举（写进 L1 分诊卡的 `fulltext_route` 字段）**：`none` / `epmc_xml` / `pmc_html` / `oa_pdf` / `pdf_local` / `subscription` / `manual`。
`pmc_html` 是 2026-09-17 新增的第 7 个值——它与 `epmc_xml` 是**不同服务端、独立失效模式**，并入会丢失「XML 已失败、已换道」这一事实。
⚠️ 注意作用域：文献库的**知识层** schema 冻结条款通常**只管知识页**，不覆盖分诊卡的字段枚举。援引「枚举已冻结」前先到权威 schema 文件里定位到字面依据——我曾在此越界援引过一次。

**Unpaywall 的 `url_for_pdf` 不总是 PDF**：实测有把图（`...-fx1_lrg.jpg`）标为 `url_for_pdf` 的情况。下载后必须校验 `%PDF-` magic 与体量（<20 KB 基本不是完整论文）。

**补充 PMCID 的渠道**：当 Unpaywall 未给 PMCID 时，Semantic Scholar 的 `externalIds.PubMedCentral` 可能给出——但**必须按上方的判重陷阱核对**它究竟指向摘要还是论著。

## 步骤 1：批量探测可得率

```bash
python3 scripts/oa_probe.py            # 读 /tmp/zot_items_now.json，输出 /tmp/oa_probe.json
```

对每条文献查 Unpaywall（`https://api.unpaywall.org/v2/{doi}?email=`）+ Europe PMC
（`https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:"..."&resultType=core`）。

判定"可获取"的口径：`unpaywall.is_oa == True` **或** `epmc.inEPMC == 'Y'`。

Zotero 条目里 DOI 可能藏在三处，都要找：`data.DOI`、`data.url`（正则 `10\.\d{4,9}/[^\s"<>]+`）、`data.extra`。
PMID/PMCID 同理常在 `extra` 或 `url` 里，用 `(?:pubmed[/\s:]*|PMID[:\s]*)(\d{6,9})` 与 `(PMC\d{5,9})` 提取。

## 步骤 2：分层统计（这一步才产生决策价值）

不要只报总数。必须交叉两层：

- **年代 × 可得率** —— 决定自动化边界
- **Zotero 分类 × 可得率** —— 决定试点选哪个集合

拉分类用本地 API：`/api/users/{lib}/collections/{key}/items/top?limit=200`。
按分类算可得率后，**优先选 ≥90% 且主题聚焦的小集合做试点**，而不是选最大的那个。

## 步骤 3：真实拉取验证（别只信"是否开放"）

"判定开放" ≠ "真能拿到可用全文"。对试点集合逐篇实拉：

```bash
python3 scripts/fetch_fulltext.py --pmcid PMC9911322 --out /tmp/ft/
```

- Europe PMC XML：`https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML`
- **必须检查正文长度**：<3,000 字符要警惕——很可能不是论著，而是**读者来信 / 勘误 / 摘要**
- 常见失败：有 PMCID 但 XML 返回 0 字（Europe PMC 未收录全文）、HTTP 500、需订阅

另外 **NCBI OA service（`/pmc/utils/oa/oa.fcgi`）已废弃**，实测返回 404 Diagnostic 页，不要作为通道。

## 步骤 4：转换选型（实测版，2026-09-16 更新）

对真实 PDF 跑 `scripts/pdf_quality_test.py`，**正文/表格/公式分开评**，不要给一个笼统结论。

### 四个方案在 2 篇真实 CFD 论文上的实测

| 方案 | 表格检出 | 标题层级 | LaTeX | 耗时 | 判语 |
|---|---|---|---|---|---|
| PyMuPDF `get_text()` | **0** | 0–1 | 0 | 0.2–0.3 s | 正文够用，表格全丢 |
| + `pymupdf-layout` | **3**（mesh 篇） | 1 | 0 | 3.0–3.7 s | ✅ **推荐** |
| + `pymupdf4llm` → Markdown | **17 行** | **23** | 0 | 5.4 s | ✅ 结构化最好 |
| MinerU 4.0 `--tier flash` | 0 真表 | 2 | 0 | — | 文字少 18%，双栏交错 |

**分层依据是"子领域"**：

| 子领域 | 引擎 | 理由 |
|---|---|---|
| 临床/流行病学类 | Europe PMC XML → PyMuPDF 原版 | 结论以文字与生存分析为主；XML 的 `<table-wrap>` 直取表格，质量高于任何 PDF 重建 |
| **CFD / 仿真 / 公式密集类** | **PyMuPDF + `pymupdf-layout` + `pymupdf4llm`** | 唯一能在本机零成本拿到数值参数表的方案 |
| 需要 LaTeX 公式 | ⚠️ **四个方案都不行** | 无方案产出 LaTeX：pymupdf4llm 静默丢弃展示公式，MinerU flash 碎片化保留。现实路径是人工抄录（CFD 论文核心控制方程通常 <10 个） |

### `pymupdf-layout` 正确用法

它是 `pymupdf` 的**就地扩展**（文件装进 `site-packages/pymupdf/layout/`），不是独立工具。
**ONNX 模型随 wheel 打包**（~49 MB，`resources/onnx/`），无需下载。

```bash
pip install pymupdf-layout pymupdf4llm      # +7 个包，约 120 MB
```

```python
import pymupdf.layout          # ← 必须先 import，它会 monkey-patch pymupdf._get_layout
import pymupdf4llm
md = pymupdf4llm.to_markdown("paper.pdf")   # 结构化 Markdown，含表格
# 或直接用 page.find_tables() —— 激活 layout 后才会真正生效
```

⚠️ 不要写 `import pymupdf_layout`，**没有这个模块名**（`ModuleNotFoundError`）。

### 中文 PDF 与表格清洗（2026-09-16 补测，8 份真实 PDF / 29 张表）

**中文排版同样有效，且提升更大**：中文学位论文（94 页）3 → 9 张、中文基金申请书 4 → 6 张。
全库 8 份 PDF 合计 **17 → 29 张（+71%）**。

唯一一个"反向"案例（某英文论著 1 → 0）经核查是 layout **纠正了误报**——关掉时检出的
`2×2` 表单元格全空、只剩页脚 `www.nature.com/...`。

清洗用 `scripts/table_clean.py`（改动 45% 的单元格、粘连修复率 77%）：

```python
from table_clean import clean_table, build_doc_vocab
dv = build_doc_vocab(doc)          # ← 必须传，否则误切率飙升
rows = clean_table(page.find_tables().tables[0].extract(), doc_vocab=dv)
```

**能修的**：英文词间粘连 `Dynamicviscosity`→`Dynamic viscosity`、小数点被拆 `0 .5`→`0.5`、
中文逐字换行 `申\n请\n者\n信\n息`→`申请者信息`、CJK 字间空格 `性 别`→`性别`、
**连字丢字** `fnite`→`finite`。

**修不了的（别抱期望，须走 XML 或人工）**：
- 整段丢空格 —— `Wepresentanewnumericalsimulationframeworkforpredictionoffowpatterns…`（85 字符无空格）
- 医学术语粘连 —— `Hypertrophiccardiomyopathy`（需术语感知）
- 抽取顺序错乱 —— 字符都在但位置乱，清洗器只保留断点线索，不假装修好

### ⚠️ 连字（ligature）坑 —— 最容易忽略
同一篇 PDF，`page.get_text()` 里 `finite`/`defined`/`confirm` **全部正确**，
但 `find_tables()` 抽出的摘要框里是 `fnite`/`defned`/`confrming`——**连字字形被整块丢掉**。
解法：用 `build_doc_vocab()`（来自正确的 `get_text()`）当拼写字典，
只接受"删掉一个字母即等于它"的**唯一**候选。即拿文档自己的正确文本纠自己的错。

### 拆词判据（踩过的坑）
用系统词典（web2）单判据会把 `Reynoldsnumber` 切成 `Reynold|snum|ber`——web2 里真有 `snum`。
→ 判据必须是 **`系统词典 OR 本文词表` 的并集**；只用系统词典会漏掉 `functions`、`simulations`
这类屈折形式（web2 缺），导致 `Radialbasisfunctions` 拆不开。
并集判据下 `Reynoldsnumber`→`Reynolds number` 正确，而 DNA 引物序列
`CCGATGGGTTGTACCTTGTC` 仍被正确拒绝。

**宁缺勿滥**：拆分失败的 token 一律原样保留。剩余未修复项里绝大多数是 DNA 引物序列——
它们本来就不该被拆。

### MinerU 4.0 的真实状态（重要，与旧版本完全不同）

**架构已从"批处理 CLI"改为"客户端 + 解析服务端"**（自述：*personal document center, built for agents*）。`mineru parse` 默认报：

```
Error: No basic, standard, or advanced engine available. You can start a local
parse-server, use --remote, or explicitly pass --tier flash for text-only preview.
```

```
$ mineru config show
parse_server.local.mode       disabled                    ← 本地引擎默认关闭
parse_server.remote.url       https://mineru.net/api      ← 云端
```

三条路，各有代价：

| 路径 | 代价 | 适用性 |
|---|---|---|
| `--tier flash` | 纯文本档，无版面、无真表格 | 聊胜于无 |
| 自建 parse-server | Docker + 模型权重，另一套部署工程 | 未实测 |
| `--remote`（mineru.net） | 需 API key，**PDF 要上传第三方** | ❌ **未发表稿件禁止** |

**结论：本阶段不推荐为任何子领域安装 MinerU。**

### 安装 MinerU 会踩的三个坑（已全部解决，供复现）

1. **`cryptography` 源码编译失败**（`openssl-sys` / Cargo）
   根因**不是**缺 openssl，而是 `modelscope-hub` 声明了无上界的 `cryptography>=41`，pip 选了最新的 **50.0.1——而 50 在 macOS x86_64 上只发 sdist**（48.0.1 有 `macosx_10_9_universal2` wheel）。
   → 加约束：`pip install -c <(echo "cryptography<49") "mineru[core]"`
2. **被安全删除守卫拦截，整笔事务回滚**（`os.unlink` → `_check_bulk_delete_guard` → `SystemExit: 1`）
   往已有环境装时 pip 需覆盖已存在文件才会触发。
   → **改建全新空 venv**（无文件需覆盖，不走该路径）
3. **pip 字节码编译阶段段错误**（exit 139，前 5 个包落盘后中断；单独装任一包却正常 → 与事务规模相关）
   → 加 `--no-compile`，一次通过

另注：**zsh 不对未加引号的变量做分词**，`IDX="-i url --trusted-host h"; pip $IDX` 会把整个串当单个参数，
报 `Could not find a version that satisfies the requirement`。用数组 `typeset -a IDX; IDX=(...)`。

## 最大的坑：不要用坐标重排文本

我按常规思路写过"双栏感知"提取器（按页宽中点切左右栏 + 各自按 y 排序），结果**反而把内容打碎**：

```
按坐标重排后 →  a / b / Freedom from AF after one procedure, /
                Freedom from AF after one procedure, / all patients, mITT population
```

原因：**现代出版商的 PDF 已嵌入正确的文本流顺序**，坐标重排会覆盖它；图注、坐标轴标签、面板标记（a/b）
这类短文本块恰好落在同一水平带，重排后就交错。

→ **默认用 `page.get_text()`，不做坐标重排。** 需要版面分析就直接装 `pymupdf-layout`（官方 ONNX 模型），
不要自己造坐标启发式——那是最差的中间态，实测比不重排还差。

## 其他实操要点

- **PyPI 直连在国内会挂死**（实测卡 11 分钟无输出）。装包用清华镜像：
  `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 30 pymupdf`
- 装到隔离环境，别污染系统 Python：`python3 -m venv <managed>/envs/default`

### 环境落点（2026-09-17 定版，勿重复搭建）

| 环境 | 内容 | 状态 |
|---|---|---|
| `<managed>/envs/default` | pymupdf + **pymupdf-layout** + **pymupdf4llm** | ✅ **实际使用的转换链路，保留** |
| `<managed>/envs/mineru` | MinerU 4.0 全量（112 包 / 666 MB） | ❌ **已删除**（用户裁定不采用） |
| `~/.mineru` | MinerU parse-server 自建 doclib 库 + 日志 | ❌ **已删除** |

`<managed>` = `~/.workbuddy/binaries/python/envs`。**不要再为 MinerU 建环境**——它在本机拿不到可用解析引擎（见上文），
且删除时占 666 MB。若将来确需公式/版面，优先评估 `pymupdf-layout` 的新版本，而非回到 MinerU。
`mineru-llama-cpp` 只在 x86_64 macOS 上启用（arm64 才走 `mineru[torch]`），故本机安装体积不含 torch。
- PyMuPDF 1.28+ 的 `page.find_tables()` **必须先 `import pymupdf.layout` 才有实效**——不激活时对
  带边框的数值表也是 0 检出；激活后同一文件能出 3 张。这是最容易漏的一步。
- 表格质量现状：结构（行列）正确，但**词间空格粘连、小数被拆**，引用前需清洗
- 探测全部为只读；**不要在探测阶段写入 Zotero 或创建 Vault**
- 装包一律加 `--no-compile`：既绕过字节码编译阶段的段错误，也更快

## 脚本清单

| 脚本 | 作用 |
|---|---|
| `scripts/oa_probe.py` | 全库 OA 可得率探测 + 年代/分类交叉统计 |
| `scripts/enrich_article_types.py` | **用 Europe PMC `resultType=core` 补文章类型 / 摘要 / 作者数 / 卷期页 / 被引数**（分诊前的必经步骤） |
| `scripts/fetch_fulltext.py` | 按 PMCID/DOI 拉取全文（XML 优先，含正文体量校验） |
| `scripts/pmc_html_to_md.py` | **PMC 文章页 HTML → Markdown**（Europe PMC XML 返回 500 时的回落通道，自动剔除作者 h4 与导航区） |
| `scripts/pdf_quality_test.py` | 对真实 PDF 评正文/表格/公式提取质量（**未激活 layout**） |
| `scripts/layout_vs_baseline.py` | 同一批 PDF 上「激活 layout」vs「不激活」的对照评测（表格/标题/公式/耗时） |
| `scripts/table_clean.py` | 清洗抽出的表格单元格（粘连/小数点/中文换行/连字丢字/拆词） |
| `scripts/diff_types.py` | **Europe PMC 类型 vs Zotero 现有类型 的只读差异比对**（四分桶：补充候选 / 修正候选 / 保留 / 仍未能识别），产出 md + json。**写库前必跑**。`--types` 必须是**实时拉取**的快照 |

```bash
# 补文章类型（分诊前必做）。第二个参数可给逗号分隔的 key 子集，不给则全库
python3 scripts/enrich_article_types.py /tmp/oa_probe.json
python3 scripts/enrich_article_types.py /tmp/oa_probe.json "KEY1,KEY2,KEY3"

# 类型差异比对（只读，写库前必跑）。
# 三个输入都应是**持久化**副本（不要 /tmp）；--types **必须是从实时 API 拉的全库快照**，
# 不得复用 journal-metrics 的中间产物 —— 那会把「当时尚未解析」误报成「未识别」，虚增补充候选。
python3 scripts/diff_types.py \
  --epmc  ~/ResearchVault/90_Meta/State/epmc_enrich_20260917.json \
  --types ~/ResearchVault/90_Meta/State/zotero_types_live_YYYYMMDD.json \
  --out   ~/ResearchVault/90_Meta/State/type_diff_live_YYYYMMDD

# XML 返回 500 时走 PMC 文章页。先抓页面（必须 curl，不能用 urllib）
curl -sL --compressed -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0" \
  -o /tmp/pmc.html "https://pmc.ncbi.nlm.nih.gov/articles/PMC9214588/"
python3 scripts/pmc_html_to_md.py      # 路径与任务列表在脚本底部的 JOBS 变量中配置
```

```bash
# 表格清洗自测：对真实 PDF 跑抽取+清洗并打印逐格前后对比
python3 scripts/table_clean.py a.pdf b.pdf
```

```bash
# 对照测法：同一批文件跑两遍，第二遍用 NO_LAYOUT=1 关闭 layout
python3 scripts/layout_vs_baseline.py a.pdf b.pdf
NO_LAYOUT=1 python3 scripts/layout_vs_baseline.py a.pdf b.pdf
```

脚本依赖：`pymupdf`；`layout_vs_baseline.py` 另需 `pymupdf-layout`（对照跑时可不装）。
输入默认读 `/tmp/zot_items_now.json`（由 zotero-journal-metrics 技能的 zot_fetch_now.py 生成）。

---

## 全文缺口清单：三档分诊法（2026-09-19 新增，实测 78 卡库）

**何时用**：用户问「哪些文献需要全文但没取到」，或要在动手取文前先排一次优先级。

**判据**：卡上 `fulltext_route ∈ {none, manual}`，**且** `20_Notes/` 下无同名 L2 笔记。
⚠️ **两个条件缺一不可** —— 实测 28 条命中里有 **2 条已有 L2**（卡字段未回写），只按 route 筛会虚报缺口。

### 三档判法（不是「开放/不开放」二分）

| 档 | 判据 | 通道 | 说明 |
|---|---|---|---|
| **A** | EPMC `inEPMC=Y` 且有 `PMCID`，且 **逐条实测 `fullTextXML` 端点返回 200** | `epmc_xml` | ⚠️ **必看 `pubTypeList`** —— 实测 4 条里 **3 条是增刊会议摘要**，「可取全文」≠「有全文」 |
| **B** | Unpaywall `is_oa=true` 但无 PMCID | 出版社页 / 机构仓储 | hybrid 者**可能被 Cloudflare 拦**（无头浏览器会撞 Turnstile 质询） |
| **C** | Unpaywall `is_oa=false` / `oa_status=closed` 且 `inEPMC=N` | 机构订阅 或 作者索取 | 自动通道已穷尽，别再试 |

探测三段（无状态、幂等）：
```bash
# 1) Unpaywall：is_oa / oa_status / oa_locations
curl -s "https://api.unpaywall.org/v2/<DOI>?email=<you>@example.org"
# 2) Europe PMC：inEPMC / pmcid / pubTypeList
curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%22<DOI>%22&resultType=core&format=json"
# 3) 端点实测（A 档才做；只读前 400 字节即可确认不是挑战页/图片）
curl -sI "https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML"
```

### ⚠️ 五个必须知道的坑（本轮实测）

1. **★★ 出版社 PDF 里的表格常是图片，文本层取不到。** 实测 Frontiers 12 页 PDF（45 MB）抽出的文本**完全不含 Table 1 / Table 2**。
   ⇒ **要逐例数值只能走 `epmc_xml` 或 **PMC 文章页 HTML**，PDF 不是可用来源**。若某技能/流程声称「从 PDF 取到了表格」，先验证。
2. **`url_for_pdf` 可能是图片 CDN 或 DOI 解析页。** Unpaywall 对 Elsevier hybrid 文常返回 `ars.els-cdn.com/...-fx1_lrg`（一张图）或 `https://doi.org/...`。**必须验 `Content-Type`**，别把它当正文直链写进清单。
3. **hybrid OA 被 Cloudflare 拦 ≠ 付费墙。** 实测三源一致 `is_oa=true / HYBRID / CCBY`，但 `curl` 403、无头浏览器撞 Turnstile ⇒ **无需机构订阅、也无需作者索取**，缺的只是"过了验证的浏览器会话"。
   ⇒ **字段纪律：`route: none` 必须附「试过哪几条通道、各失败在什么环节」。「自动取不到」≠「不存在」。** 曾因把前者记成后者，差点白跑一轮订阅/索取。
4. **会议摘要会混进 A 档。** 增刊摘要（Europace `Suppl` 等）有 PMCID、能取到 XML，但 `article-type="abstract"`。**这类不该做 L2**，只在卡上把 `read_scope` 标 `abstract`、证据等级标最低、`fulltext_route` 标 `epmc_xml(abstract-only)`，避免以后被当成"已取全文"。
5. **同 DOI/同 PMID 的重复卡会把缺口数算大。** 实测一对（`CUJE7AKF` / `SDLLEQSG`）同 DOI 同 PMID 同作者同题，分属两个主题集合、`zotero_key` 却不同 ⇒ **Zotero 库内疑有两条记录**。修法是**标 `duplicate_of` 而不要删卡**（删了会丢集合归属），并提示用户去 Zotero 合并。

### 产出形状

一份 markdown 清单（落 `90_Meta/Sources/全文缺口清单_<date>.md`），**用脚本生成不要手抄**：
概览表（卡片总数 / route 命中 / 已有 L2 / 真实缺口）→ 按 P0–P3 与集合分布 → A/B/C 三档各一表（附通道、直链、注入坑标记）→ 库务问题 → 建议动作顺序（带成本）。
**优先取什么由「与当前课题主线的关系」决定，不由优先级字段决定** —— 实测 C 档 13 篇里只有 4 篇真正需要动手。
