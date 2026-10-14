---
name: literature-batch-intake
description: 把一批新主题文献从「检索」一路做到「L1 分诊卡 + L2 精读笔记」的批量入库流水线——跨库检索、Zotero 查重导入、PMID 回填、Europe PMC 文章类型闸门、全文通道探测（含 Unpaywall 兜底）、多通道抓全文（含第二遍穷尽式：J-STAGE 落地页挖链、OpenAlex/Unpaywall 全部 locations、仓储落地页抓 PDF、截断续传、退避重试）、**用户手供本地 PDF 入档（manual 通道；收到 PDF 先转 md 再读）**、**待人工取件清单（必须给完整标题、Crossref 补全）**、多栏 PDF 重排（分栏聚类／表格搬位／跑边+段落延续保护／字号摘图内文字／**块内+几何跨块的软换行合并**／C0 控制字符字形还原）；再用共享作业规范驱动多个子代理并行建卡，收口时跑英文引语可核验性闸门（跨全库档案核验，`--diagnose` 归因，分「档案排版交错／引表格内容／笔记真的删改原文」三类定性）并做窄前提的转录修复。当用户说「你补文献」「把这批文献入库」「检索 X 建页」「批量分诊/精读」「把需要取全文的取全文」「同步全文缺口」「这些引语核一下」「笔记里的原句能不能定位到」「这是取不到的几篇/我下载到了」「把这几份 PDF 入档建卡」「下次找不到的要我找的文章标题列出来」并已有 ~/ResearchVault/ 库时使用。库内操作与 L3/校验部分转 research-vault-pipeline。
agent_created: true
---

# 批量文献入库流水线（检索 → Zotero → 全文 → L1/L2）

## 何时用

- 用户说「**你补文献**」「把这批文献入库」「检索 X 并建页」
- 库内某一维是**真空**，需要针对性检索后补进 `~/ResearchVault/`
- 已有一批 Zotero 条目（某个集合），需要批量走完分诊 → 精读
- **用户丢来一批二手来源**（公众号精读文、综述文、朋友圈、PDF 解读稿、期刊新闻稿）说「导入一下」——
  走 §0b 的甄别流程，**先分清哪些是文献、哪些只是解读**，再入库

**不适用**：单篇论文写笔记、改 L3 页、跑校验 → 那些转 `research-vault-pipeline`。

---

## 0b ★ 二手来源（公众号/解读文）入库的鉴别流程（2026-09-29 实测新增 · 同日修正）

用户给的不是 PMID 清单而是**一批链接**（公众号、解读稿、媒体文）时，**第一件事不是抓全文，是判断「这是不是文献」**。

> ⚠️⚠️ **同日踩坑与修正（务必先读）**：本流程初版把「公众号文未列期刊/DOI」直接判成「原创中文综述、**不入库**」，
> 结果**漏掉了一篇真实已发表的 MDPI 论文**（*Hearts* 2026;7(1):10，DOI `10.3390/hearts7010010`）——
> 那篇公众号（燕赤霞 ECHO HEART）只是它的**中文精读**。用户随后给出 MDPI 原文地址才发现。
> ⇒ **「公众号没写期刊」≠「没有英文母本」。中文精读文极常见于有正式英文版的新刊综述。**

### ★ 判「是否原创中文」的唯一合法判据：**多路标题检索全落空**

公众号所述**主题明确但书目不全**时，**必须先做完这三路检索**才允许写「不入库」：

1. **Crossref 按标题检索**（`query.bibliographic=<英文主题词>`，rows=5）——最关键的一路，中文精读文给出的是英文标题，直接可查；
2. **PubMed / Europe PMC** 按主题词 + 作者；
3. **OpenAlex** 按主题词（可捞到未被 PubMed 收录的新刊，如本例的 MDPI *Hearts* —— **`hitCount=0` 于 Europe PMC，但 Crossref/OpenAlex 命中**）。

**三条全落空**才可写「疑似原创中文、不入库」，且**必须在卡/回复里写明「已检索哪些库、按什么检索式」**，
不得只写「无英文原文」这一句结论。**判错的代价是静默漏一篇真文献**——比多跑一次检索大得多。

| 二手来源形态 | 判据 | 处置 |
|---|---|---|
| **精读已发表英文文献**（给出完整书目/DOI） | 能用 DOI/标题在 PubMed·Crossref 命中 | ✅ **建卡**，回权威源核对全部字段 |
| **★ 主题明确、书目不全的中文精读** | **三路标题检索任一命中** | ✅ **按命中结果建卡**（本例即此类；MDPI 刊**常未被 PubMed 收录**，Europe PMC `hitCount=0` 不构成否定证据） |
| **原创中文叙述性综述** | **三路标题检索全部落空**（须写明检索式） | ❌ 不入库，只作背景，明确告诉用户「已检索 X/Y/Z 均无对应英文文献」 |
| **期刊新闻稿 / 会议报道 / 器械广告** | 无 DOI 或只有商品名 | ❌ 不入库；可提示「有对应原始文献，要不要我去检索？」 |
| **二手引用**（A 文里提到 B、C） | 只能拿到「作者+年份」 | ⚠️ 走正常 `lit-fusion` 检索补全，不建「转述卡」 |

**三条硬规矩**：

1. **★ 建卡前把元数据回权威源核对**（PubMed / Europe PMC / Crossref / OpenAlex）。
   二手来源的**书目可信度**与**内容可信度**是两个独立量：实测公众号文末书目与 Crossref **完全一致**，
   但正文里的一批数字（例数、百分比、频段、时间窗、器械型号）**在所有权威元数据源里一个都查不到**。
2. **★ 二手来源的一切数字一律不入卡**，只写进卡内「待核清单」，
   并在卡头写明「取到全文后第一件事＝回核这 N 项」。公众号的转述数字**永远不能当原文引**。
3. **★ 明确告诉用户哪些没入库、为什么**。不要默默跳过 2/3 —— 用户以为三篇都导了。
   **但「没入库」这个判断本身要有检索日志支撑**（见上方判据），否则就是漏检。

**库内写法**：卡内单开一条硬规则「二手转述数字一律不得入卡」，并列出逐条待核项。
- 反面教材：`10_Triage/Cards/PFAXNIRG_*.md`（把公众号那批数字全部列在头部警示里，一个没进正文）。
- **误判留痕**：`10_Triage/Cards/VACXPDE0_*.md` 第 6 节与硬规则 #7 写明了本次误判的完整链条与修正判据——
  **卡里保留误判痕迹是惯例，不是丑闻**（便于回溯同类情形别再犯）。

### ★ 顺带沉淀：MDPI（gold OA 刊）的两个取件要点（2026-09-29 实测）

| 事项 | 实测结论 |
|---|---|
| **DOI 构造** | MDPI 的 slug **带刊名复数/变体**：`Hearts` ⇒ `10.3390/hearts7010010`（**不是** `heart7010010`，猜错会 404）。**别猜，走 Crossref `query.bibliographic` 按标题检索。** |
| **PDF 直取路径** | `www.mdpi.com/<path>/pdf` **与网页端点对本机一律 403**（反爬）。可行路径＝**资源镜像**：`res.mdpi.com/d_attachment/<jslug>/<jslug>-<vol>-<artno>/article_deploy/<jslug>-<vol>-<artno>.pdf`（`mdpi-res.com` 同内容）。下载后**必校 `%PDF-` magic**。 |
| **PubMed 收录** | 新刊（如 *Hearts*）**常未被 PubMed/Europe PMC 收录**（本例 `hitCount=0`、无 PMID）⇒ **不可用「EPMC 未命中」判闭源**，须看 Unpaywall `is_oa`（本例 `gold`）。 |
| **许可** | gold OA 通常 **CC BY**；`source_note` 写明「gold OA, CC BY」以便复用。 |
| **⚠️ PDF 版 ≠ 网页版** | MDPI 网页可能多出「republished with a minor correction to the Data Availability Statement」而 **PDF 版无此声明**。按本库契约**以 PDF 版为准并原样保留**，但要在卡里写明这处差异（引数据可用性声明时会用到）。 |
| **★ 页侧竖排 DOI 水印会污染正文流** | MDPI PDF **每页页侧**都有一列竖排 `https://doi.org/10.3390/<slug>`。抽取器按「图内文字（按字号判据）」摘出后，**这些水印会落进正文流**，在**每页接缝处**把跨页句拦腰截断（实测 `VACXPDE0` 12 页里 **9 处**被截）。**后果**：引语闸门会出现「档案侧插入 DOI 串」的假未命中，看起来像笔记抄错，实际是档案坏了。**入库后必查**： |

  ```python
  # 扫全库：正文流里是否残留纯 DOI/水印串的图内文字块
  MARK = '<!-- 图内文字(按字号判据摘出,避免插入正文行间) -->'
  for m in re.finditer(re.escape(MARK) + r'\n((?:[^\n]*\n)*?)(?=\n?<!-- |\n\n|\Z)', s):
      lines = [l.strip() for l in m.group(1).strip().split('\n') if l.strip()]
      if lines and all(re.fullmatch(r'https?://(?:dx\.)?doi\.org/\S+|10\.\d{4,9}/\S+', l) for l in lines):
          print(f)   # ← 这些块应移出正文流，改记入文末「页眉页脚汇总」
  ```

  **处置**：只删**纯 DOI 块**；同批的「作者/编辑/收稿信息块」「Author Contributions 声明块」等**含真实内容的必须保留**。
  水印信息不丢——在文末页眉页脚汇总补一行 `[页侧竖排水印 · 每页重复 · 非正文] <DOI>`。
  **删完必校**：① 字母数字总数的减少量**恰等于**删掉的 DOI 串字母数字数（`VACXPDE0` 实测 34752→34512，−240 = 9×DOI 串，**字符集完全一致、无任何新字符**）；② 断词计数不增；③ 用 `verify_note_quotes.normalize()` 复查接缝句能命中（直接 `in` 判会因 `<!-- page N -->` 分页标记而假 MISS）。 |

---

## 与其它技能的分工（不要重复实现）

| 环节 | 归谁 |
|---|---|
| 跨库检索（PubMed + Consensus） | `lit-fusion`（`scripts/fusion.py`） |
| 导入 Zotero | `zotero-import`（`scripts/zotero_import.py`） |
| 全文通道判定 / 抓取 / 转换 | `zotero-fulltext-feasibility`（`scripts/fetch_fulltext.py`、`pmc_html_to_md.py`） |
| Zotero 元数据读写（含 428 坑、`merge_tags`） | `zotero-journal-metrics` / `zotero-local` |
| **前段批量编排（本技能）** | 检索→导入→闸门→探测→抓全文→合成中间格式→**子代理并行建 L1/L2** |
| 库内层规范、L3 六类页、校验器 | `research-vault-pipeline` |

---

## 全链 9 步

```
0 定这批文献的「角色」（竞争定位？补空白？反例？）
1 检索（lit-fusion，多档检索式比命中量）
2 候选查重 → 只导不在库的 → Zotero 导入
3 PMID 回填（新导入条目不带 PMID！）
4 元数据 + 摘要 + pubTypeList（Europe PMC core，带退避重试）
5 文章类型闸门 + 全文通道判定 + Unpaywall 兜底
6 合成中间格式 L1_batch_input_{YYYYMMDD}.json   ← 后续所有子代理的唯一输入
7 多通道抓全文 → 40_Fulltext/md/{zotero_key}.md    ← 全挂时转 manual 手供通道（§7g）
8 子代理并行建 L1 卡 → 并行建 L2 精读笔记
9 L3 建页 + 校验 + 索引收口   → 转 research-vault-pipeline
```

**所有批次数据一律落 `90_Meta/State/`，命名 `<用途>_<YYYYMMDD>.json`。不许留 `/tmp`（会被系统清理）。**

---

## 步骤 0 — 先定「角色」，再检索

用户的工作方式是**先有命题，再补文献**。开工前必须明确这批文献在论证里干什么：

- **竞争定位**（谁在做同类指标？我的卖点守不守得住？）
- **补空白**（库里某个维度 0 篇）
- **反例 / 效度基座**（有没有反对我假设的证据？）
- **新颖性边界**（哪些主张我**不能**提，因为别人做过了？）

角色决定**检索式**与**分诊时的用途字段怎么写**。跳过这步会检索出一堆不相关的论文。

---

## 步骤 1 — 检索（多档，比命中量）

```bash
PY=~/.workbuddy/binaries/python/envs/default/bin/python
$PY ~/.workbuddy/skills/lit-fusion/scripts/fusion.py \
  '<PubMed 检索式>' --pubmed-only --limit 40 2>&1 | tail -4
```

- **不要只跑一个检索式。** 同时跑 A/B/C/D/E 多档（宽 → 窄），逐档统计 `esearch.fcgi` 的 `count`，
  挑**精准**那档。实测：宽式混进大量小鼠机制研究，窄式才能捞出真候选。
- 无 Consensus key 时加 `--pubmed-only`。
- 报告复制一份到 `90_Meta/State/fusion_<主题>_<档>_{YYYYMMDD}.md`。

---

## 步骤 2 — 查重后导入（只导不在库的）

先拉全库建 PMID 索引，**再**决定导哪些：

```python
# 拉全库（分页，limit=100 循环到空）
GET http://localhost:23119/api/users/{LIB}/items/top?limit=100&start={N}
# 从每个 item 的 data.extra 里正则抠 PMID
re.finditer(r"PMID:\s*(\d+)", data["extra"] or "")
```

```bash
$PY ~/.workbuddy/skills/zotero-import/scripts/zotero_import.py \
  --collection "新集合名" --pmids 111,222,333 --tags "主题标签,YYYYMMDD检索"
```

候选清单先落盘（`<主题>_candidates_{date}.json`），记录 `core`(人工挑的核心候选) / `in_zotero` / `to_import` 三桶。

---

## 步骤 3 — ⚠️ PMID 回填（最容易漏的一步）

**`zotero_import.py` 走 RIS 导入，RIS 不带 PMID → 新条目 `extra` 里没有 `PMID:`。**
不回填的后果：后续所有按 PMID 做的映射全部失效，且**不会报错**，只会表现为「匹配不上」。

回填口径：**DOI 精确匹配优先，标题归一化（NFKD + 去非字母数字 + 小写）兜底**，
只补缺口（`re.search(r"PMID:\s*"+pmid, extra)` 已存在就跳过）。

PATCH 用 `req.add_header()`，**不要用 `headers={...}`**（见坑 4）。

---

## 步骤 4 — 元数据 + 摘要（Europe PMC）

```python
q = urlencode({"query": f"EXT_ID:{pmid} AND SRC:MED", "resultType": "core", "format": "json"})
GET https://www.ebi.ac.uk/europepmc/webservices/rest/search?{q}
```

取这些字段：`title` / `authorString` / `journalInfo.journal` / `yearOfPublication` / `volume` / `issue` /
`pageInfo` / `doi` / `pmcid` / **`pubTypeList.pubType`** / `citedByCount` / `inEPMC` / `isOpenAccess` /
`hasPDF` / `abstractText`。

**⚠️ 必带退避重试**（实测连续请求会被限流，表现为连接被断而不是 4xx）：

```python
for attempt in range(4):
    try: ... ; break
    except Exception:
        if attempt == 3: return None, "retry-exhausted"
        time.sleep(1.2 * (attempt + 1) + random.random())
time.sleep(0.7)   # 每次成功请求之间也歇
```

**分段可续跑**：把已完成的 PMID 写进 `_done` 列表存盘，下次跳过。一次跑不完就再跑一次，
不要用一个大超时硬扛（会被杀，前功尽弃）。

---

## 步骤 5 — 闸门 + 通道判定 + Unpaywall 兜底

**文章类型闸门**（`pubTypeList` → `article_type`）：
含 `review` → 综述；含 `research-article` / `journal article` / `clinical trial` / `comparative study` /
`multicenter` → 论著；否则 其他。
⚠️ 库内已有类型字段**也不可盲信**（PubMed 给 letter/comment 也打 `Journal Article`）。

**通道判定**：

| 条件 | `fulltext_route` |
|---|---|
| `inEPMC == "Y"` | `epmc_xml` |
| `hasPDF == "Y"` | `oa_pdf` |
| 否则 | `none` |

**⚠️ `none` 的必须再过一遍 Unpaywall**——实测 20 篇 `none` 里 **11 篇有 OA 版本可救**：

```python
GET https://api.unpaywall.org/v2/{doi}?email={email}
# is_oa == True → fulltext_route 改 "oa_pdf"，记 oa_url = best_oa_location.url_for_pdf or url
```

---

## 步骤 6 — 合成中间格式（子代理的唯一输入）

`90_Meta/State/L1_batch_input_{YYYYMMDD}.json`，**数组**，每元素 19 字段：

```
group  zotero_key  pmid  title  authors  journal  year  volume  issue  pages
doi  pmcid  pubTypes  article_type  cited_by  fulltext_route  priority  collection  abstract
```

- `priority`：`P0`（直接支撑命题）/ `P1`（背景）/ `P2`（边缘），按文献角色手定。
- **这份 JSON 是后续全部子代理的唯一数据源**——它们不再各自去拉 API。
  这既避免限流，也保证所有卡片的元数据**同源**。

---

## 步骤 7 — 多通道抓全文

输出统一落 `40_Fulltext/md/{zotero_key}.md`（**用 Zotero key 命名，不是 PMCID**）。

### 7a `epmc_xml`
```bash
$PY ~/.workbuddy/skills/zotero-fulltext-feasibility/scripts/fetch_fulltext.py \
  --pmcid PMCxxxxxxx --out /tmp/ft_stage
```
**⚠️⚠️ 脚本会把 PMCID 写进 frontmatter 的 `zotero_key`**（历史 bug 已修但**手工调用时仍会撞**）。
拿到产物后必须强制修正：

```python
head = re.sub(r"(?m)^zotero_key:.*$", f"zotero_key: {zkey}", head)
if not re.search(r"(?m)^pmcid:", head):
    head = head.rstrip() + f'\npmcid: "{pmcid}"\n'
```

### 7b `pmc_html`
抓 `https://pmc.ncbi.nlm.nih.gov/articles/{PMCID}/`，取 `id="bodymatter"` 那一段，正则去标签。
**长度 < 4000 字符判失败**（多半抓到导航壳）。

### 7c `oa_pdf`
下载 → 先校 `Content-Type` 或 `data[:5] == b"%PDF-"` → `pymupdf4llm.to_markdown(path)`。

> **本机无 pymupdf / pdfminer / pypdf / poppler 时的两条兜底**（2026-09-18 实测）：
> 1. **零安装、最快**：macOS 自带 JXA + PDFKit，直接离线抽全文——
>    `osascript -l JavaScript -e 'ObjC.import("Quartz"); var d=$.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath($(path))); d.string.js'`
>    对**数字版 PDF**（非扫描件）即得全文；扫描件返回空/极短，可据此判定是否需 OCR。
> 2. **要结构化/分页**：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pypdf`（默认 PyPI 在本机会长时间挂起；清华镜像 2 秒装完），
>    然后用 `PdfReader(p).pages[i].extract_text()` 逐页抽，实测 Wiley/Elsevier 数字版无空页、无乱码。
>    ⚠️ 不要手写 zlib+ToUnicode 的裸解析器——PDF 内容流上的正则回溯会把单文件拖到数分钟以上。
> 用户直接丢来的出版社 PDF（`fulltext_route: manual`）走同一条路：抽完存
> `40_Fulltext/md/{zotero_key}.md`（加 frontmatter：`source: publisher PDF (user-supplied)` + `extractor`），
> 原件存 `40_Fulltext/pdf/{zotero_key}.pdf`。

**抓完必须补 L4 frontmatter**（`source_url` + `source_note`），并保证 `source_type` 是 7 值枚举原文、
**不带任何描述性文字**（描述写进 `source_note`）：

```yaml
source_type: oa_pdf
source_url: https://lib.ossn.ru/jour/article/download/1144/798
source_note: "Unpaywall 指认 publisher/publishedVersion；Kardiologiia（俄文刊）出版版 PDF"
```

### 7d 两条「别急着判死」的通道（2026-09-17 实测新增）

**① Europe PMC 延迟收录 → 搁置前复检一次。**
期刊/文章可能**尚未进 Europe PMC**（`inEPMC=N`、XML 端点 404），但过一段时间就会收录。
本轮实测救回 1 篇：`QMJHWD3P` 首轮抓取时无 `doi`、`epmc_xml` 拿不到，**复检时已可解析**（新得 `PMC13576552`），
改走 `epmc_xml` 成功转入 L2。

> **口径**：`none` **不是终局判定**。判 `none` 与最终写入搁置卡之间应**隔一次复检**（至少在批次收尾时统一复检一次）。
> 这一步成本极低（一个 `EXT_ID` 查询），但能把「暂时不可得」和「真的不可得」分开——
> **后者才是应写进搁置记录的**。

**② 出版商 403 之后，转向机构仓储的作者接受稿。**
Elsevier / Wiley / AHA / OUP / Karger 的 `doi.org`、`pdfdirect` 链接普遍 **403**，
但同一篇文章往往有**机构仓储副本**（大学 repository）。本轮实测：
- `TQPTC2N2` → OUP 403 ⇒ 改走 **Aalborg University** 仓储取得（**submittedVersion，作者接受稿**）
- `ASB2VWC6` → **dadun.unav.edu**（University of Navarra）有副本

> ⚠️ **拿到接受稿必须写明版本。** `source_note` 里要写清「作者接受稿 / submittedVersion，非出版版式」——
> **接受稿与出版版的正文数字可能不同**，不写明日后的引用无法判断该篇能不能当依据。
> ⚠️ 机构仓储常见 **`SSL: CERTIFICATE_VERIFY_FAILED`**（本机对 `dadun.unav.edu` 即如此），
> 归人工通道，不要为绕过证书校验去关验证。

### 7e 第二遍「穷尽式」通道（2026-09-19 实测新增）

第一遍跑完仍未到手的，**不要直接判死**——第二遍换这六条，本轮 29 篇里净新增 2 篇：

| 通道 | 做法 | 命中场景 |
|---|---|---|
| `epmc_xml_retry` / `pmc_retry` | **退避重试 3 次**（3s/6s/9s） | EPMC 间歇 500、PMC 间歇 403。本轮 `BMPXNTHI` 的 EPMC XML 返 **500**，但 PMC 文章页可取 ⇒ 靠这条救回 |
| **直接下 PDF 时加续传重试** | 第二次带 `Range: bytes=0-` | `IncompleteRead(495888 bytes)` 这类**通道是通的、只是被截断**。本轮 `3RQGFGFQ` 靠这条拿到 1.78 MB PDF |
| `jstage` | 取 `doi.org` 落地页，正则 `/_?article/.../_pdf` | **J-STAGE（日本刊）**。PDF 链形状是 `…/advpub/0/advpub_<ID>/_pdf` 或 `…/<vol>/<issue>/<ID>/_pdf`，**必须从落地页挖**；Unpaywall 给的 curl 直下会 `IncompleteRead` |
| `OpenAlex 全部 locations` | `api.openalex.org/works/doi:{doi}` 里 `locations[]` 的 `pdf_url` + `landing_page_url` | 第一遍只用了 `best_oa_location`，会漏掉仓储副本 |
| `Unpaywall 全部 oa_locations` | `url_for_pdf` + `url_for_landing_page` + `url` | 同上；**`url_for_pdf` 为空时落地页仍可能有 PDF**（`pure.eur.nl`、`cris.*` 这类） |
| **仓储落地页抓 PDF 链** | 对 HTML 候选正则 `\.pdf` / `/files/<id>/*.pdf` | 如 `pure.eur.nl/en/publications/<uuid>` → `/files/<id>/<name>.pdf` |

> **另两条本轮实测在本机不可用（写下来省得重试）**：`api.fatcat.wiki`（scholar.archive.org）
> 与 `r.jina.ai` 被本机出口代理直接拦（`CONNECT tunnel failed, 502`）——脚本里应**探一次即永久短路**，
> 否则每篇白等三轮重试。

### ⚠️⚠️ 两个必须避开的判定陷阱（都造成过「其实能取却没试」）

**陷阱 1：`…/pdf` 结尾的直链被当成「落地页」。**
ScienceDirect（`…/pii/XXXX/pdf`）与 Wiley（`pdfdirect`）的 PDF 直链**不以 `.pdf` 结尾**。
若判据写成 `url.endswith(".pdf")`，这些 URL 会被送去「抓落地页」，而**真正的下载一次都没发生**
（本轮第一版即如此：22 篇全部 0 次下载尝试）。判据必须覆盖：

```python
p = url.lower().split("?")[0].rstrip("/")
is_pdf = p.endswith(".pdf") or p.endswith("/pdf") or "pdfdirect" in p or "/_pdf" in p or "/pdf/" in p
```

**陷阱 2：看到 `403` 就判「这篇是 OA、只是被反爬拦」。**
`403` 可能来自**落地页解析失败**（随手举：任何 `doi.org`/`jstage` 探测在本机都会 403），
与「该篇有没有 OA 版本」毫无关系。判据必须换成**权威字段 + 逐条 URL 的真实结果**：

- 先问 Unpaywall `is_oa` / `oa_status`（**唯一权威**）；
- 再看**真实尝试下载**的那几条 URL 的返回：`403/Forbidden` ⇒ 反爬拦；
  `非 PDF / 404 / 空壳` ⇒ **直链已失效**（不等于被拦）；两者都没有 ⇒ 闭源。
- 分类落三种，分别对应三种人工动作：**「OA 有直链、本机被反爬拦」**（浏览器点开即可）、
  **「OA 直链已失效」**（需人工确认）、**「闭源」**（订阅/向作者索取）。

> 本轮第一版按「消息里有没有 403」分类，把 **22 篇全判成「OA 被反爬拦」**——错得很整齐，也因此更危险。

**陷阱 3：机构仓储落地页写着「Open Access / Published version」，实际按钮是 `disabled`。**
2026-09-29 实测（`10.1161/CIRCEP.124.013102`）：OpenAlex 的 `locations[]` 里出现
`Ghent University Academic Bibliography`，落地页 `biblio.ugent.be/publication/01JHJ546Y5AJDZHM2PQGP293TE` 返回 200，
`#downloads` 区块明写 **"full text (Published version) / Open Access / PDF / 5.81 MB"** ——
**但同一个 `<a class="btn btn-default" disabled>Download</a>` 带 `glyphicon-lock` 图标，
且 `UGent only` 标签**。判据必须是**按钮的 `disabled` 属性与权限标签**，不是区块里的文字：

```python
seg = html[html.find('id="downloads"'):][:4000]
locked = ('disabled' in seg) or ('glyphicon-lock' in seg) or re.search(r'\b\w+ only\b', seg)
```

`locked == True` ⇒ **机构内网/订阅限定，本机不可得**，直接归人工通道，在卡上写明是哪所机构、需要什么权限。
⚠️ 这是**第四种**闭架形态（前三种：反爬 403 / 直链失效 / 真闭源），
特点是**「开放标记为真、访问权为假」**——只读 `is_oa` 或只 grep 页面文字都会误判成「可取」。

### 7f ⚠️ PDF → MD：**多栏必须先重排**（2026-09-19 实测新增，同日二次加固）

PyMuPDF 默认按**视觉行**输出：同一 y 高度上的左栏与右栏文字被拼进**同一行**，
正文句子被对侧栏文字打断，形如：

```
...ECG during an
Figure 1. Patient flow chart. Patients were followed up for 25 (23,31) months.
outpatient visit or (2) AF/AT of at least 30-s duration on ambulatory ECG...
```

**后果极隐蔽**：L2 笔记里确实贴了原句、看着完全合规，但**一条都核不了**（见 §8.6）。

```bash
python reflow_two_column_pdf.py <in.pdf> <out.md>
```

**四层判据（缺一层就有残留断点）**：

1. **分栏**：按 block 的 x 坐标**聚类**分栏（`_cluster_columns`，**栏数不写死**，容 1/2/3 栏或多栏）。
   页内**先左栏后右栏**；`len(cols) <= 1` 的页按 y 直排（否则单栏页的标题会被「跨栏 ⇒ 页末输出」搬到大作者名单之后，**页序错乱**）。
2. **表格块**：`page.find_tables()` 的矩形覆盖 >50% 面积的 block **移出正文流、页末集中输出**
   （否则表头、刊名插进句子中间）。
   ★ **跨栏块（横跨 `full_ratio=0.55` 页宽）同样不做「水平分隔带」**——只排序、页末输出；
   当分隔带用会把表注插进跨页句中间。
3. **跑边（页眉/页脚）**：主判据是**纵向位置**（`y1 < 8.5%H` / `y0 > 92.5%H`）。
   ★★ **必须配「段落延续保护」**——纵向带会把**正文段落的首/末行**一并卷走
   （实测每页 1–3 行，如 `these criteria were excluded.`、`mean ± SD …`），
   正文被割成两半 ⇒ 引语核验直接失败。机械补判据：与同 x 栏带内**非跑边块**的纵向间距
   `≤ 2.9 × 行高中位数`，且不宽于 `0.55W`、不匹配字间距报刊头 `(?:\b[\w&]\b\s+){5,}`、不是纯数字块
   ⇒ 判为**正文段落延续**，留回正文流；否则才算跑边。**实测分离度：真跑边 3.2–10.8，正文行 0.3–2.8**，阈值 2.9 处干净分开。
   跑边块去重（数字归一成 `#`）后，页末以 `[pN]` 前缀集中输出。
4. **图内文字（字号判据）**：图注/图轴/图例与正文**同栏同带，纯几何分不开**。
   取页面**字号众数**（要求众数占该页字符数 >40% 才启用），凡 block 中位字号
   `< 众数 × 0.90` 且非图注（`CAPTION_RE`）者判为图内文字，**不进正文流**，页末以注释标记集中输出。
   ⚠️ **0.90 是扫描标定值，不要凭直觉放宽**：正文 7.7 pt / 图轴刻度 7.0 pt，**只差 0.7 pt**；
     放宽到 0.94 虽收进轴刻度，却把正文/图注一并扫走 —— 实测四篇合计未命中 **6 → 19**。
     需复现扫描时用环境变量 `REFLOW_SMALL_RATIO` 覆盖。

**收尾**：合并软换行（行尾连字符断词一并合并；行尾无句末标点则空格合并）→ NFKC 归一化 →
**C0 控制字符字形还原**（见下）。

#### ★ 软换行合并的作用域：**块内 + 几何跨块**，绝不能对整页跑（2026-09-19 三次加固）

`clean_soft_breaks()` 若作用在**整页拼好的文本**上，会把**不同 block 的行**也黏成一句。
实测一篇（Georgi 2024）首页出现：

```
O R I G I N A L A R T I C L E Christian Georgi MD 1 | Marwin Bannehr MD 1 ... Abstract
```

即 **刊头 + 作者块 + `Abstract` + 右栏首行**被缝成一行，摘要首句被腰斩。**读序是对的，黏行是错的**，
且这种错在引语核验里表现为「档案里找不到这条句子」——**会被误判成笔记的错**。

正确做法：

1. **块内**无条件合并相邻行（行尾连字符断词一并合并；行尾无句末标点则空格合并）。
2. **跨块**只做**几何合并**，四条同时满足才并：
   ① 两块的 **x 区间有实质重叠**（同一栏）；
   ② 纵向间距 **≤ 1.7 × 行高中位数**；
   ③ **上块末尾不带句末标点**（`. ? ! :`）；
   ④ **上块不是图注/表题**（`CAPTION_RE`）。
3. `__main__` **不再**对整篇跑 `clean_soft_breaks`。

实测：修后 s5 首页恢复为 7 行独立结构行，正文读序正常。**跨块合并阈值宁紧勿松**——
多并一行是「句子被拼接」（不可核验），少并一行只是「句子被截断」（核验时取连续片段即可）。

#### ★ C0 控制字符字形还原（不做就是**静默改数**）

出版社 PDF 把 `±` 排成 Symbol 字体，抽文本得到 C0 控制字符。旧规则只认「`mean ` 之后的是 `±`」，
**把 `7.07 ± 1.55` 还原成了 `7.07 - 1.55`**——注意这不是乱码，是**改数**，且不会报错。

正确规则（`\x01`/`\x02` 一律 → `±`；`\x03` **位置相关**）：

```python
text = text.replace("\x01", "\u00b1").replace("\x02", "\u00b1")
text = re.sub(r"(?<=\bmean )\x03", "\u00b1", text)          # "mean \x030.5"
text = re.sub(r"(?<=\d)\s*\x03\s*(?=\d)", "\u00b1", text)   # 215.0 \x03 69.2 → 数字之间是 ±
text = text.replace("\x03", "-")                            # 紧贴数字之前（前一字符是 ( / 换行 / 空格）→ 负号
```

即：**数字之间 → `±`**；**紧贴数字之前 → 负号**（如 `(\x030.006 to 0.009)`）。
重排完必须 `grep -P '\x0[123]'` 确认**零残留**。

#### ★★ 另一类字形噪声：**按契约原样保留、绝不订正**（2026-09-20 裁定）

与上一条相反：**Elsevier / JACC 系** PDF 抽文本时会把排版用的数学符号整体映射错——

| PDF 里的真符号 | 抽出来变成 | 例（档案原样 → 真义） |
|---|---|---|
| `≥` | **`$`** | `$50 milliseconds over #10 millimeters` → `≥50 ms，≤10 mm` |
| `≤` | **`#`** | `($2 weeks for amiodarone)` → `≥2 周` |
| `=` | `1⁄4` | — |
| 上下标 | 丢失 | — |

**处置口径（勿再纠）：保留原样、不订正。** 理由有硬约束：

1. **引语闸门要求「笔记与档案逐字一致」**——改档案会同时让既有笔记的全部引语失配，闸门立刻红。
2. 库内已有成文惯例：`C7EC9FUZ` / `XPUKL6KE` / `6Q8TMP9F` / `BIJVFLXE` / `ANTEMDD3` 五篇均在笔记文末写「**按契约原样保留，未订正**」并列出映射表。新笔记照办即可。

**⚠️⚠️ 绝不可做库级批量替换。** 库内 12 份档案有同类字形（实测 `$`→≥ 25 处 / `#`→≤ 26 处），
但**多例是真符号**：`/$36.00`（定价）、`#555962`（货号）、`#22-083`（批号）、`Patients #3/#10`（患者编号）。

> **判据（只有同时满足才算 ≥/≤）**：`$`/`#` **紧随数字**，且处于**阈值语境**（后接 `mV` / `ms` / `mm` / `s` / `%` / `years` / `deflections`）。
> 抽查用：`re.finditer(r'[\$#](?=\d)', body)` 逐条 eyeball 上下文，**不要**写成自动替换脚本。

#### 纪律与验收

- 原档留 `40_Fulltext/pdf/<key>.pdf` **逐字不改**；旧 md 备份为 `40_Fulltext/md/*.bak_preRescue` 一类的旁支文件（收口时删）。
- frontmatter 加 **`reflow:`** 字段，写明本次具体做了哪几条（改了规则就更新该字段）。
- **核对字母数字总数**前后一致（只改线性顺序；跑眉去重与表格搬位会造成**小幅**下降，属预期；大幅下降即丢正文）。
- 实测收益：J-STAGE 双栏一篇未命中引语 **12 → 0**；本批三篇出版社 PDF 二次重排后再消一批断点。

**新取到 PDF 先重排，再交给子代理写笔记。**

### 7g 用户手供 PDF 入档（`manual` 通道，2026-09-19 实测新增）

自动通道（Europe PMC / PMC / Unpaywall / OpenAlex / 机构仓储）全挂时，
用户在浏览器里点开并下载了出版社 PDF —— **这类件只能人工取**，取到后走本通道。
（用户已明确规矩：**取不到就直接告诉他，取到就直接建完卡、不回头问**。）

入档脚本 `ingest_local_pdf.py`（随本技能分发）——**只处理已在磁盘上的 PDF**，不走网络：

```bash
# manifest.json 形如
# [{"key":"XPUKL6KE","pdf":"/Users/…/1-s2.0-…pdf","doi":"10.1016/j.…",
#   "pmid":"31753431","citation":"JACC Clin Electrophysiol 2019;5(11):1265-1277","title":"…"}]
python ingest_local_pdf.py manifest.json          # 自动调 reflow 重排
```

它做三件事：`pdf/` 落原档 → 调 `reflow_two_column_pdf.py` 重排 → 写 frontmatter（`source_type: "manual"`、
`source_note` 写清**出版版 / 非镜像 / 非接受稿**）+ 报告**字母数字总数前后差**。
状态落 `90_Meta/State/ingest_local_pdf_<stamp>.json`。

**入档后须回写的四处**（顺序别倒）：

1. **L1 卡**：`read_scope: fulltext`；`fulltext_route` 由原值改 `manual`，**行尾加注**（几日、谁手供、已入档、已改判）。
2. **§6 分诊决定**：追加「【原行留痕】决定：搁置 → 进入 L2」——**保留原判**再写改判，便于回溯。
3. **缺口清单**：重跑 `gen_fulltext_gap_list.py`（断链数应随之下降）。
4. **建 L2 笔记** → 收口（§8.7）。

⚠️ 这类入档常常**同时清掉两条悬空记录**：一条是「缺口（A 类『其实 OA 本机被拦』）」，一条是「断链（卡判进 L2 却从没抓过全文）」——
收口时**两条都要销**，别只销一条。

### 7g-2 重排之后：**版式适用边界** 与 **字典辅助去断词**（2026-09-20 实测新增）

`reflow_two_column_pdf.py` **不做行末连字符断词的合并**，而且**不是所有版式都适合重排**。
本轮 3 篇（Elsevier Heart Rhythm ×2 + JACC Clin EP ×1）实测出的三档边界：

| 版式 | 断词数（重排前→后） | 字母数字总数变化 | 结论 |
|---|---|---|---|
| **Elsevier / Heart Rhythm** | 106→1、116→2 | −3.7% / −5.7%（页眉页脚与图内文字被移出正文流，属预期） | **采用** |
| **JACC 系（JACC Clin EP）** | 114→99 | **−7.6%** | 勉强采用，但**必须补去断词** |
| **Wiley / JCE** | 反而更差（连字符写成 `num- ber`，句子仍被图注/表体插断） | — | **不采用**，改为定点修档 |

⇒ **两条量化判据，重排后必查**（别默认采用重排结果）：

```python
import re
def hy(s):    return len(re.findall(r"[a-z]-\s+[a-z]", s))          # 断词残留
def alnum(s): return len(re.sub(r"[^0-9A-Za-z]", "", s))            # 字母数字总数
```

- `hy()` 没降到个位数 ⇒ 重排没解决断词，要补下面这道工序；
- `alnum()` 掉 **>7%** ⇒ 先查是不是丢了正文（对照各节标题是否齐全），别直接入库。

**「字典辅助去断词」工序**（重排之后必做，本轮已用它把 JACC Clin EP 那篇从 99 处断词清到 0）：

⚠️ **断词有三种形态，正则各不相同（2026-09-29 补）**：

| 形态 | 实测样例 | 正则要点 |
|---|---|---|
| Elsevier / Heart Rhythm | 行末 `arrhyth-` + 换行 + `mias` | `([a-zA-Z]{2,})-[\s\n]+([a-z]{2,})` |
| **Springer（JICE 等）** | **`Sci\xad entific`——U+00AD 后还跟一个空格 0x20** | **`([A-Za-z]{2,})\u00ad\s?([a-z]{2,})`**；用 `([A-Za-z]+)\u00ad([A-Za-z]+)` 会**处理 0 处、字符数完全不变**（实测踩过），排查办法是打印码位 `repr()` |
| AHA / Circ AE | 抽出的是**无标记裸数字**引用上标（`13`、`32`），不是断词 | 见 §8.6，**不要当漏字** |

**字典收尾必须人工兜一道**：字典对 `uti|lized`（软连字符形态的 `utilized`）这类**不命中**，
跑完字典后把**残留软连字符逐处打印出来、用显式映射表收尾**——实测 Springer 那篇字典合并 125 处后仍残留 20 处，
人工核对后合并 19 处（`utilized`/`predictors`/`complemented`/`reconduction`…，含专名 `Musikantow`）才清零。
**校验仍是那两条**：`alnum()` 前后不变（只少了软连字符与空格）、`hy()` 计数不增。

```python
W = set(open("/usr/share/dict/words").read().lower().split())            # 235k，macOS 自带
W |= set(open("/tmp/words_alpha.txt").read().lower().split())            # 370k：curl -sL https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt
KEEP_PREFIX = {"non","high","low","long","ultra","multi","semi","anti",
               "post","pre","mid","sub","super","whole","cross"}         # 复合词前缀白名单
# 规则：整词命中且左半不在白名单 → 合并；否则 → 去掉空白、保留连字符
re.sub(r"([a-zA-Z]{2,})-[\s\n]+([a-z]{2,})",
       lambda m: (m.group(1)+m.group(2)) if (m.group(1)+m.group(2)).lower() in W
                 and m.group(1).lower() not in KEEP_PREFIX else m.group(1)+"-"+m.group(2), body)
```

- 整词命中 → 合并（`arrhyth- mias`→`arrhythmias`）；
- 两半都是独立词 → 保连字符去空白（`low- voltage`→`low-voltage`、`high- frequency`→`high-frequency`）；
- **白名单是必需的**：否则 `non-inducible` 会被并成 `noninducible`（本轮实测命中）。

**还要手工修「重排吃掉空格造成的串字」**：块内软换行合并时个别处会把空格一并吃掉，
搜 `\b[a-zA-Z]{17,}\b` 捞出长串逐个判（本轮 `B8YLGCJP` 有 3 处：
`delayedenhancement MRI`→`delayed enhancement MRI`、`recommendedtojointhem…`→拆回正常英文、`electrogramanalysis`→`electrogram analysis`）。

⚠️ **`ingest_local_pdf.py` 会用运行日志覆盖同名 manifest**：脚本按 `INGEST_STAMP` 写
`90_Meta/State/ingest_local_pdf_<stamp>.json` 作为**运行日志**——若 manifest 取同名就会被覆盖。
⇒ manifest 一律另存 `manual_intake_<date>.json`，运行日志留给脚本用。

> 补：PDF 文本层把 `=` 映射成 `5`、把 `±` 映射成 `6` 是 Elsevier 系的通病，档案里会出现
> `n 5 104`、`P 5 .48`、`1.75 6 0.10` 这类写法。**引语要按档案原样保留**（否则核验不通过），
> 但在笔记正文里引用时应还原为 `=`/`±`，并在自检节说明。

### 7g-3 Zotero 本地 API 的**写操作**要带 `Zotero-Server-ID`（2026-09-20 实测，Zotero 10.0.3）

`PATCH /api/users/{uid}/items/{key}` 与 `DELETE /api/users/{uid}/collections/{key}` 只带
`If-Unmodified-Since-Version` 会返回 **428**，body 是 `Zotero-Server-ID not provided`。

**正确做法**：先 `GET` 同一资源 → 从**响应头**取 `Zotero-Server-ID` → 写请求里同时带上两个头。

```python
def call(m, u, h=None):
    r = urllib.request.Request(f"{base}{u}", method=m); r.add_header("Zotero-API-Key", KEY)
    for k, v in (h or {}).items(): r.add_header(k, v)
    try:
        resp = urllib.request.urlopen(r); return resp.status, resp.headers.get("Zotero-Server-ID"), ""
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Zotero-Server-ID"), e.read().decode()

st, sid, _ = call("GET", f"/api/users/{uid}/collections/{ckey}")          # 拿 Server-ID
call("DELETE", f"/api/users/{uid}/collections/{ckey}",
     {"If-Unmodified-Since-Version": str(ver), "Zotero-Server-ID": sid})  # 带上才不 428
```

- `zotero_ops.py` 的 `patch_item()` 走 `POST /api/users/{uid}/items` **批量写**（body 里带 `key`+`version`），
  **不需要**这个头，可正常用；
- 但同文件的 `delete_collection()` **缺这个头**，会**固定失败** ⇒ 删集合一律自己走 raw API。

### 7g-4 「反序」取全文：`fetch_epmc_xml_batch.py`（2026-09-20 新增）

标准链是「先有 L1 卡 → 再取全文」，因为 `fetch_gap_fulltext_20260919.py` 的 `load_meta()` 是**从卡里**读元数据的。
但新批次常常是 **Zotero 已导入、卡还没建**（尤其自动通道能拿到全文时），此时用
`90_Meta/State/fetch_epmc_xml_batch.py` 按 `(zotero_key, pmcid)` 直接落成 L4：

```bash
python 90_Meta/State/fetch_epmc_xml_batch.py 90_Meta/State/<batch>.json
# JSON 每项：{"key","pmcid","doi","title","citation"}
```

- 只吃 PMCID，不依赖卡；JATS → Markdown 保留 `## Abstract` 与各节标题，表格按行文本化为 `| a | b |`；
- **会议摘要**（`article-type="abstract"`）正文在 `<abstract>` 里、`<body>` 为空——脚本已处理（取 abstract），
  产出仅 2k 字符属正常，**档案 `source_note` 务必标注「会议摘要，仅含摘要正文」**，否则后来者会以为取全了；
- 源为结构化 XML ⇒ **没有多栏版式问题，不需要重排、不需要去断词**（7g-2 那两道工序只针对 PDF）。

> 批次收口顺序（本批次实测可行）：Zotero 导入 → 移正集合 + 补 date → extra 回写 PMID/PMCID（**写两遍**）
> → 取全文 → 建 L1 卡 → 写 L2 笔记 → 引语闸门 → 索引重生 → `validate_vault.py`。

### 7h 待人工取件清单：**必须给完整标题**（2026-09-19 用户明示）

用户原话：**「下次找不到要我找的文章标题列出来」**。只给 `zotero_key` 或 DOI 是不够的——
他要拿标题去搜。脚本 `gen_manual_fetch_list.py`（随本技能分发）：

```bash
python gen_manual_fetch_list.py --date YYYYMMDD
# → 90_Meta/Sources/待人工取件清单_<date>.md
```

输出两段：**按优先级排的全表**（key · 年份 · 优先级 · 标题 · 刊名 · DOI 链接）+ **「纯标题」段**（逐条可直接复制去搜）。

三条硬规矩：

1. **标题必须是完整全称**。卡片标题被截断的（`…` 结尾）用 **Crossref** 按 DOI 补全，
   并在「标题来源」列注明是 `Crossref` 还是卡内——**不要把截断值当标题发出去**。
2. **已判「排除」的卡不计入**（会议摘要一类永远取不到的，S 类）。首版混进了 3 张 P3 会议摘要，已修。
3. 判据与缺口清单**同源**：`fulltext_route ∈ {none, manual}` **且** `20_Notes/` 无同 key 笔记。
   ——即「清单里出现的，就是卡上真没有全文的」。**已进 L2 的不再出现**（哪怕档是二手渠道来的）。

### 7i 读 PDF：**先转 md，再读**（2026-09-19 用户明示）

用户原话：**「pdf文章读之前先转md」**。收到用户丢来的 PDF 时：
**不要**用 PDF 阅读器（视觉读页）直接认文章、抄数字——**先跑 `reflow_two_column_pdf.py` 落 md，再从 md 认**。
理由：① 读序问题（多栏并块）在视觉读页时**看不见**，转 md 才会暴露（本轮 s5 首页就是这么抓到的）；
② 转出的 md 直接就是后续引语核验的**比对底本**；③ 认文章要走 DOI 正则（`10.\d{4,5}/…` 取最高频），
比看首页题名可靠（首页题名可能被读序打散）。

```bash
# 批量先落暂存区，再从 md 认 DOI → 映射到库内 key → 写 manifest
mkdir -p 90_Meta/State/_intake_staging
python reflow_two_column_pdf.py "<in.pdf>" 90_Meta/State/_intake_staging/sN.md
grep -o '10\.[0-9]\{4,5\}/[^ ,;)]*' 90_Meta/State/_intake_staging/sN.md | sort | uniq -c | sort -rn | head -3
```

暂存区 `_intake_staging/` **收口时整目录删掉**（中间产物不入库）。

#### 7i-1 「先转 md」的**真正判据**：认文章与抄数字的**输入**必须是 md，不是 PDF 页

⚠️ **本条 2026-09-29 补**：规则立了，但实践中仍会滑回「打开 PDF 看一眼首页对一下 DOI」——
本轮 `RFPARGXF` 卡上就写了「PDF 首页 DOI 自检」，属违规。**判据只看一件事：这一步读的是 md 还是 PDF。**

- ✅ 合规：`ingest_local_pdf.py` 一步到位落 `40_Fulltext/md/<key>.md`，**再从该 md 认 DOI / 抄数字 / 建卡**——
  这就是「先转 md 再读」的完整形态，**不需要中间暂存区**（暂存区只在「还不知道是哪篇、要先认」时才有意义）。
- ❌ 违规：用 PDF 阅读器打开、看着首页标题/版权行/DOI 栏做核对，**哪怕只是「自检一下」**。

**自检动作的标准写法**（全部在 md 上做）：

```bash
cd 40_Fulltext/md
grep -o '10\.[0-9]\{4,5\}/[^ ,;)"'"'"'<>]*' <KEY>.md | sed 's/[.,;]$//' | sort | uniq -c | sort -rn | head -4
grep -ic '<doi 尾部片段>' <KEY>.md        # 目标 DOI 命中次数
grep -o -m1 -E '<题名前 20 字符>[^.]{0,120}' <KEY>.md   # 题名锚点
```

实测两篇：`TOPO7U0D` DOI 命中 4 次、`RFPARGXF` 命中 2 次，**完整题名 + 刊期行 + 作者块都在 md 正文里**，
出版版 PDF 的题名/版权行本来就不缺——**先转 md 就够了，从头到尾不必打开 PDF**。

- **卡与笔记里凡写「PDF 首页/首页 DOI/读首页核对」这类措辞，一律视为待修项**：
  交付前用 `Grep 'PDF 首页|首页 DOI|读首页'` 扫本批全部卡与笔记，改成「入档 md 正文认 DOI（命中 N 次）」。
- 数字、结局、COI、引语**本来就只从 md 取**（引语闸门整条链跑在 md 上），这一层不会错；
  错的只是**认文章/自检那一步的输入**，改口径表述即可，**不需要重做入档或重算任何数字**。

### 探测结论要回写进卡（别只留在日志里）

写个**幂等**脚本，把结论追加到每张未取到全文的卡 `## 6. 分诊决定` 的「全文通道」行之后：

```
- **第二遍探测（YYYY-MM-DD）**：新增通道 `…`｜`…`；结论 = **<三分类之一>**（<Unpaywall oa_status + 代表卡点>）
```

**注意两个坑**：① 同一脚本重跑会把同名通道**累积多份**（去重再拼）；② 已有当日行要**原地替换**
而不是再插一行，否则口径修正后卡上会同时留着对的和错的。

### 实测失败模式（归人工通道）
- **403 Forbidden**：Elsevier / Wiley / AHA / OUP / Karger / NEJM 的 `doi.org` 与 `pdfdirect` 链接 → 先试机构仓储（见 7d）
  ⚠️ 但**先用 Unpaywall 分清「OA 被拦」与「真闭源」**（见上「陷阱 2」）——两者的升级路径完全不同。
- **SSL: CERTIFICATE_VERIFY_FAILED**：部分机构仓储
- **返回非 PDF**：`image/jpeg`（抓到了图）、`text/html`（抓到了落地页）
- **反爬并非无头才触发**：`agent-browser` 的**有头模式也过不去** Cloudflare（本轮在 ScienceDirect/AHA/Wiley 长等 4×8 秒仍停在验证页），
  不要为此反复试；这一步直接归人工。

这些**不要反复试**，标记后归 `manual` / `subscription`，在卡上写明失败通道逐条。

---

## 步骤 8 — 子代理并行建 L1 / L2（本技能的核心）

### 8.1 铁律：规则写**一份文件**，prompt 只引用它

**绝不要在 N 份子代理 prompt 里各写一遍通用规则。** 实测这样会**逐份漂移**，
而且改一次要改 N 处。做法：

1. 写 `/Users/macintosh/ResearchVault/90_Meta/State/L1_作业规范_{date}.md`（或 `L2_…`）
2. 每个子代理 prompt 开头只写：**「完整读 `<规范路径>`，那是你的唯一作业契约」**
3. prompt 正文只保留：**你负责的 key 列表（含输出文件名）+ 本组特殊要求（3–5 行）**

规范文件必须包含：
- 必读文件（模板 / 参考范例 / 元数据来源 L1 卡 / 全文档案路径）
- **项目背景**（决定「对我研究的启示」怎么写——没有它子代理会写空话）
- 输出命名表（**逐字给出文件名，不要让它自己起**）
- frontmatter 键清单与填写口径
- 正文要求 + **额外必查项**
- **硬规则**（证据纪律）+ 文末自检节模板 + 回报格式

### 8.2 证据纪律（硬规则的内核，不可省）

1. 每条「主要发现」配**逐字英文原句**，保留 however / only / not / 条件句——**严禁反向生成引语**；
   定位不到就写「未在当前全文中定位到可核验原句」
2. 每个数字**必须能在全文档案定位**；找不到写「原文未报告」，**不得推算**
3. `evidence_grade` 取**最弱一条**（木桶），并在自检节说明理由——**宁可低**
4. **争议只指出、不裁断**（裁断属 L3 的 KV 页）
5. 表体 / 图未随档案转出 → 必须明写「未随档案转出，本库内不可核验」
6. 元数据与正文不符 → 显式标注「未在本库全文层核验」

### 8.3 分组原则

- 按**主题**分组（电极/模态、空间统计、影像对照、循环标志物…），**不要按顺序切**。
  同组文献互为对照，子代理才能写出「与既有证据的关系」。
- **每组 3–6 篇**。
- **并发 4–7 个**。实测一次开 8 个会撞频率限制（429），整个批次被打断且**已建文件不会回滚**——
  恢复时先 `ls` 数一遍，只补缺的（本技能支持幂等续跑）。

### 8.4 交代清楚「哪几篇是特殊的」

综述（无原始数据）、方法学论文（无临床终点）必须**逐篇点名**并给出处理口径
（`study_design` 怎么写、`evidence_level` 怎么标、「主要结果」换成什么），
否则子代理会硬套临床结局模板。

### 8.5 ⚠️ 子代理的产出必须自己抽查

实测子代理会：① 在自检段**声称**某文件「已核验存在」但实际不存在；
② 把 `[[基名]]` 写成反引号键名；③ 越界改动没让它动的文件。
**交出后必须自己 `Read` 抽查若干篇 + 跑校验器 + 数文件数**，不要直接采信它的回报。

### 8.6 ★ 引语可核验性：**做完必跑**（2026-09-19 新增）

「每条发现配逐字原句」这条纪律，过去**没有任何自动闸门**，全靠自觉。
实测后果很隐蔽：**笔记里贴了英文原句、看起来完全符合规范，实际一条都核不了**：

- PDF 双栏交错 ⇒ 句子被对侧栏文字打断（见 §7f）
- 档案是 HTML / XML ⇒ `&gt;` 没还原、弯引号 `’` vs `'`、连字 `ﬁ` vs `fi`
- 子代理拼接或改写了原句 ⇒ 限定词消失（把「在 X 条件下成立」读成「普遍成立」）

跑法（`90_Meta/State/verify_note_quotes.py`，随本技能分发）：

```bash
python verify_note_quotes.py                     # 全库
python verify_note_quotes.py <key> ...           # 指定篇
python verify_note_quotes.py --diagnose <key>    # 逐条归因（定性用，见下）
```

**机器可读模式**（供 Folio 文献工作台 `server/vault.js` 调用；判定引擎与上面**完全同一套**，只是换个出口）：

```bash
python verify_note_quotes.py --json                                  # 全库 / 指定 key → JSON
python verify_note_quotes.py <key> --json                            # 单篇 → JSON
python verify_note_quotes.py --quotes-file F --json                  # 任意引语列表（Folio 卡片）
python verify_note_quotes.py --quotes-file F --corpus-dir D --json   # 以 D 为语料（Folio 自己的正文）
python verify_note_quotes.py --coverage-file F --json                # 覆盖度：笔记应有引语 vs 已进 Folio
python verify_note_quotes.py --report-dir D                          # 核验并落一份可归档报告到 D
python verify_note_quotes.py --json --report-dir D                   # 同时出 JSON 与报告
```

★ **所有 JSON 模式一律 `exit 0`**，失败写进 `{"ok": false, "error": ...}` —— 非零退出会被调用方读成「脚本崩了」。
★ **写盘只有一个入口**：显式传 `--report-dir` 时写 `D/引语闸门_<日期>.md`；**其余一律只读**。

三层判：**严格命中 / 仅连字符差异 / 未命中**。
归一化链：HTML 反实体 → NFKC（连字）→ 标点统一（`’`→`'`、`–—−`→`-`）→ 去全部空白 → 去 markdown 强调。
同时剔除作者自加的 **`[pN]` 行标**、`<!-- -->` 注释、markdown 强调符。

#### ⚠️ 抽取侧的两个门槛（错了会让报告「看起来没问题」）

- **字母占比下限 `LATIN_MIN`（默认 0.35，环境变量可覆盖）**：原为 0.5，会把**数字密集的真实引语整条跳过**——
  实测 `6Q8TMP9F` 的均值±SD 句字母占比只有 **0.43**，**从未被核验过，报告里也显示不出异常**。
  收紧的教训：**门槛太高 = 静默漏检，比误报危险**。
- **CJK 闸门**：含中文的候选（多为中文行夹带的英文片段）直接判**非英文引语**跳过。
  0.35 门槛落地时曾把含中文的表格行收进来，未命中一度虚涨到 85 —— 这个闸门是必需的。
- **被跳过的候选要在末尾列出来**（`SKIPPED`），不要静默丢弃。

#### 定性：`--diagnose` 三分类

未命中先做**最长连续锚点 + 逐点 INS/DEL/REP 归因**（`--diagnose` 直接给「📄 档案窗口（【】＝最长连续锚点）」）：

```python
if ins == 0:      verdict = "笔记侧改写（必须改笔记）"
elif del_ == 0 and rep == 0: verdict = "档案侧版式（笔记原文无误，无需改）"
else:             verdict = "混合：档案侧插入 + 笔记侧差异"
```

| 类 | 特征 | 处理 |
|---|---|---|
| ① 档案排版交错 | 前缀命中后断在 `Figure N.` / 表头 / 刊名页码处 | **修档案（§7f）**，或按契约标注 |
| ② 引的是表格内容 | 整段是阈值表 / 单元格文字 | 按契约明写「表体未随档案转出」——**允许** |
| ③ **笔记真的删改了原文** | 词被换 / 被删 / 被拼接 | **必须改笔记**（唯一必须动手的一类） |
| ④ **引的不是档案** | 覆盖率极低（实测 30%）且**档案里根本没有这句话**——引的是网页版声明 / 他文 / 公众号转述 | **改笔记**：改为说明性文字 + 注明来源与「不作为逐字引语登记」。**绝不要**为了让闸门通过而删掉这处差异记录 |
| ⑤ 尾随参考文献编号 | 档案句尾多出 `[15]` / `[18]` 等原文引用标记 | **档案侧版式，笔记不改**（`del_=0, rep_=0`），在「自检」节登记即可 |

⚠️ **⑤ 的两种形态别混**（2026-09-29 实测）：Elsevier/Springer 抽成 **带括号**的 ` [9, 13]`；
**AHA / Circ AE 抽成无标记的裸数字**——`…interpolation errors,13 underscore the value…`、
`…ventricular arrhythmia,32 but this warrants…`。两者诊断都表现为「**档案侧插入 2 字符**」，
**极易误判为笔记漏字**；判据是 `del_=0, rep_=0`（真漏字会同时有 `del_` 或 `rep_`）。

⚠️ **`--diagnose` 报「覆盖 100%、插入 0 删字 0 替换 0」却仍判未命中 ⇒ 句首大小写差异**。
`normalize()` **不做大小写折叠**，所以笔记引语开头把 `The mean follow-up` 写成 `the mean follow-up`
（或反过来）就是 miss，而诊断输出里三类计数全是 0、**只有回档案核首字母才看得出来**。
这类**必须改笔记**（按档案逐字），不能按「档案侧版式」放过。

⚠️ **④ 只有在「覆盖率很低 + 档案侧全文搜索确认无此句」两个条件同时成立时才能下**——
`VACXPDE0` 那条网页版声明覆盖率 30%，而 ① 类断点也会有低覆盖率，**必须全文 `find` 一次再定性**。

★★ **顺序铁律：「未命中 → 先重排档案 → 再复检 → 才定笔记的错」。**
**档案侧断档会掩盖笔记侧漏字**——本批三篇里 3 条真错（`C7EC9FUZ` 两处、`6Q8TMP9F` 一处）
全都被旧档案的断点掩盖着，先动笔记就会改错方向。

#### 转录修复（`repair_note_quotes.py`，随本技能分发）

**三段式铁律：诊断 → 逐条确认 → 才落笔。不许「一键全修」。**

```bash
python repair_note_quotes.py --json <key> ...       # ① 诊断（只读，绝不改文件）
# ② 逐条确认 fixable[].id
python repair_note_quotes.py --apply-ids ids.json   # ③ 落笔（ids.json = {"ids": [...]}，追加 _quote_repair_log.json）
```

**只放行两类**（`unsafe_change_reason()` 的准入闸门，其余一律归人工）：

1. **引号字形还原** —— `'flags'` → `"flags"`（非空白字符全是引号类，语义不动）；
2. **补回良构 ±** —— **不删**任何非空白字符，新增的非空白字符**全是 `±`**，
   且每个 `±` 都落在 `\d\s*±\s*[\d(]` 语境。

**确认环节看 `id`，不看序号**：`id = sha1(key + "|" + 原文引语)[:12]`，**与顺序无关**。
落笔时**重新诊断一遍**，过期 id 原样报 `missing`，不猜。

★★ **判据前提：档案侧字符不可信。** `40_Fulltext/md/` 里由 C0 字形还原生成的档案，
**一个 `±` 同时编码四种真值** —— 真 ±（`52±10 years`）、`<`（`P ± .05`、`r ± 0.85`）、
`≈`（`±5 seconds`）、脚注 `†`（`Taiwan, ±Second Department`）。
同类还有**软连字符 U+00AD**（`per\u00adformed`，`normalize()` **不剥它**）与 **markdown 记号**（`_h_`）。
⇒ **档案缺而笔记有的字符，说明残缺的是档案。** 照档案改就是**把对的改成错的**。

**落笔前把笔记整份快照到库外** `~/ResearchVault_backups/<日期>_quote_repair/`
（库内出现备份目录是校验器 WARN 的错，也会在 Obsidian 里变成重复笔记）。
**验完要两条证据**：威力（`miss` 下降）**和**幂等（第二次同 id → `applied 0`），缺一不可。

典型用途：把笔记里被吞掉字形的 `1.56 0.47 mV` 还原成 `1.56 ± 0.47 mV`（语义一字未改）。
**不满足两类的残余一律标「须人工」，不要连试。** 实测收敛：第一版诊断报「可自动修 113 条」，
逐条抽查后发现会把 `~` 改成 `±`、把 `per\u00adformed` 搬进干净笔记 —— 三轮收窄后 **113 → 1**。

⚠️ **诊断时不要用「手打重现的测试串」**——我曾据此误判笔记把 `additionally conducted` 改成 `performed`、
把 `Figure 4A` 写成 `Figure 5A`，两处都是我手打串的错，笔记本身是对的。
**必须取脚本从笔记里抽出的原串。**

### 8.7 收口清单（完整闭环，可照抄）

主代理在子代理回报后统一做（**不要分派给子代理**，它们只写自己那一篇）：

1. **机械校验**：frontmatter 22 键齐全（不删键、缺值留空串）、`fulltext_path` 指向真实文件、文件名与契约表逐字一致、`zotero_key` 8 位 ASCII
2. **引语核验**：跑 §8.6，未命中逐条定性
3. **三处一致性回写**（★ 2026-09-20 加，别只推一处）：**卡 / 索引 / 档案三者必须对齐**——
   `read_scope: fulltext`（全文已入档者）、`fulltext_route` **逐一对齐** L4 档案的 `source_type`、
   `20_Notes/_Index.md` 与 `40_Fulltext/_Index.md` 的计数与分布按 frontmatter **实测重算**（勿沿用旧数）。
   实测教训：一批只推「卡／索引／档案」之一是不合格的 —— 历史 49 张卡因此长期停在 `abstract`。
4. **L1 卡回写**：§6 追加「L2 精读笔记：已建（日期）→ `[[基名]]`」+ `fulltext_route` 行尾加注 —— **幂等脚本**，
   判据用 `[[基名]]` 而非任何中文关键词（踩坑：关键词会先被 frontmatter 注释引入，导致 §6 那步被误判「已存在」而跳过）
5. **索引**：`20_Notes/_Index.md`（**手写，须自己加行**——它常落后实况，顺手核对有无历史遗漏）；
   `10_Triage/_Index.md` 与缺口清单**重跑脚本**，勿手改
6. **双校验器**：`validate_vault.py` 退出码 0；悬空数应等于「L1 判进 L2 数 − L2 篇数」。
   ★★ **它同时是「重复入库」的唯一自动防线**（DOI 撞库）——必须看输出，不能只看退出码
7. **变更记录**：`90_Meta/State/变更记录.md` 追加一节（交付表 / 新工具 / 修正 / **悬空项明写**）
8. **待人工取件清单**：`gen_manual_fetch_list.py --date …` 重跑（§7h）——**账要主动递给用户**，
   不要等他来问「还有哪些没取到」。清单里每篇都要有**完整标题**。
9. **告知用户时可照抄的一句话**：本批清掉 N 条缺口 / M 条断链，剩余待取件 K 篇（已附完整标题清单）。

---

## 步骤 9 — L3 与收口

转 `research-vault-pipeline`：纯提取 → 定页 → 建页 → 回扫 → 双校验器 → 索引收口。
**顺序是硬的**：L2 未落地不得建 L3（来源数是硬门槛）。

---

## 踩过的坑（逐条都真撞过）

| # | 坑 | 症状 | 处理 |
|---|---|---|---|
| 1 | **新导入条目无 PMID** | 后续按 PMID 匹配全失效，**不报错** | 步骤 3 强制回填（DOI 优先、标题兜底） |
| 2 | **`zotero_key` 被写成 PMCID** | L2 的 `fulltext_path` 反查指向不存在的键 | 手工取全文时必须 `re.sub` 修正；写 L2 前 `grep '^zotero_key:'` 自检 |
| 3 | **Europe PMC 限流** | 连接被断（不是 4xx），看起来像网络问题 | 退避重试 + 请求间隔 + 分段续跑（`_done` 列表） |
| 4 | **`urllib` 的 `headers={}` 会 capitalize 头名** | `If-Unmodified-Since-Version` → `If-unmodified-since-version` → Zotero **428**，且报错文案与「缺 `Zotero-Server-ID`」**一模一样**，照字面查会一路查到授权上去 | 一律用 `req.add_header()` 逐个添加 |
| 5 | **子代理 prompt 各写一遍规则** | 规则逐份漂移，改一处要改 N 处 | 规则落一份规范文件，prompt 只引用 |
| 6 | **子代理自检不可信** | 自检段称「已核验存在」但文件不存在 | 自己 Read 抽查 + 跑校验器数数 |
| 7 | **宽检索式混入动物研究** | 候选里一半是小鼠机制 | 多档检索式比命中量，选窄式；候选人工过一遍 |
| 8 | **并发子代理过多** | 429，批次中断 | 4–7 个；中断后按文件数**幂等续跑** |
| 9 | **镜像站 / 非官方 PDF** | 内容与正式版不符 | OA 版本走 Unpaywall 的 `best_oa_location`；下载后校 `%PDF-` magic |
| 10 | **`none` 一次判死** | 把「Europe PMC 还没收录」当成「永远拿不到」，直接写进搁置 | 搁置前复检一次 `inEPMC`；实测 `QMJHWD3P` 复检即已收录 |
| 11 | **机构仓储接受稿当出版版** | 正文数字与出版版可能不同，事后无法判断 | `source_note` 写清版本（submittedVersion / 出版版）+ 来源站点 |
| 12 | **`source_type` 混写描述性文字** | 5 种写法并存（`europepmc-xml` / `pmc-html (…)` …），按键比对全失败 | 归一化到 7 值枚举；描述移入 `source_note` |
| 13 | **C0 控制字符一律当减号** | `7.07 ± 1.55` 被还原成 `7.07 - 1.55`——**静默改数**，不报错 | `\x01/\x02` → `±`；`\x03` **位置相关**（数字之间→`±`，紧贴数字前→负号），见 §7f |
| 14 | **跑边判据卷走正文段首/末行** | 正文被割成两半 ⇒ 引语核验失败；三篇跑边行数一度归 0 | 补**段落延续保护**（间距 ≤2.9×行高中位数 ⇒ 留回正文），见 §7f |
| 15 | **引语抽取字母占比门槛太高** | 数字密集的真实引语被整条跳过，**从未被核验过且报告显示不出异常** | `LATIN_MIN` 0.5 → 0.35 + CJK 闸门 + 末尾列被跳过项，见 §8.6 |
| 16 | **先动笔记、后看档案** | 档案侧断档掩盖了笔记侧漏字，改不到真错处 | 顺序铁律「**先重排档案 → 再复检 → 才定笔记的错**」，见 §8.6 |
| 17 | **`40_Fulltext/md/*.md` 计数混入摘要级占位档** | 验收闸门凭空多出假悬空（55 vs 真 53） | 数档案数时 `grep -L '^source_type:.*none'` 排除；判有无全文只看卡 `fulltext_route`，见验收清单 |
| 18 | **`clean_soft_breaks` 对整页跑** | 不同 block 的行被黏成一句（刊头+作者块+`Abstract`+右栏首行缝成一行），**读序其实是对的**，却让档案里找不到该句 ⇒ 会被误判成笔记的错 | 改成**块内合并 + 几何跨块合并**（同栏重叠 / 间距 ≤1.7×行高 / 上块无句末标点 / 非图注），`__main__` 不再整篇跑，见 §7f |
| 19 | **待取件清单只给 key/DOI** | 用户没法拿去搜（他要标题） | 必须出**完整标题**，卡内被截断的用 Crossref 补全并标注来源，见 §7h |
| 20 | **拿 PDF 直接视觉读页认文章** | 多栏并块的读序问题在视觉读页时看不见 | **先转 md 再读**，认文章走 DOI 正则，见 §7i |
| 21 | ★★ **手供 PDF 与库内已有条目同篇** | 用户重发了库里 **2026-09-19 已入档**的同一份出版社 PDF（同 DOI、同 1.67 MB）⇒ 建出重复 L1/L2/L4 三件，**肉眼看不出** | **建卡后必跑 `validate_vault.py`——它的 DOI 撞库是「重复入库」的唯一自动防线**；撞上就删新建那套（先 `grep -r <新key>` 确认无入链），**不要**改成 second-opinion 卡 |
| 22 | **`read_scope` / `fulltext_route` 从未回写** | 49 张卡全文入档后仍写 `abstract`；4 张卡 `fulltext_route` 与 L4 档案 `source_type` 打架（历史三批都把这件事列为「未做」） | 收口时按模板硬规则归一：**全文已入档 ⇒ `read_scope: fulltext`；`fulltext_route` 须与 `40_Fulltext/md/<key>.md` 的 `source_type` 逐一对齐**（「两处不可打架」） |
| 23 | **索引冻结在旧批** | `40_Fulltext/_Index.md` 停在 41 篇（实有 89）；`20_Notes/_Index.md` 的 `evidence_level` 分布合计只有 50 | 索引分两类：**脚本生成的**（`10_Triage/_Index.md`、缺口/取件清单）一律重跑；**手维护的**（`20_Notes/_Index.md`、`40_Fulltext/_Index.md`）由 frontmatter **实测重算**再写，勿沿用旧数 |
| 24 | **档案标题被截断** | `…Under Rapid Pac`、`…omnipolar tec` 之类断在词中，8 份 | 按 **Crossref** 用 DOI 取权威标题补全（判据：`^title:` 以非词边界结尾）；出版商自己的 Crossref 记录也截断的（`YVIS2UCJ`）如实留着 |
| 25 | ★★ **MDPI 页侧竖排 DOI 水印落进正文流** | 被「图内文字按字号判据」摘出后留在正文流，在**每页接缝**截断跨页句（`VACXPDE0` 12 页 **9 处**）⇒ 引语闸门出现「档案侧插入一串 DOI」的假未命中，**极易误判成笔记抄错** | 入档后按 §0c 的扫描代码全库查一遍；只删纯 DOI 块、保留含真实内容的图内文字块；水印改记入文末页眉页脚汇总；删完校「字母数字减少量 == DOI 串字母数字数」 |
| 26 | ★ **引语未命中只分了「档案错 / 笔记错」两类** | 漏了第三类：**引语引的根本不是档案**。`VACXPDE0` 那条 MDPI 网页版更正声明在 PDF 档案里**不存在**，无论怎么改笔记或档案都命中不了 | `--diagnose` 覆盖 30% 以下时先问一句「**这句话在档案里真的存在吗**」；确认不存在 ⇒ 改笔记为**说明性文字**并注明「出自网页版、PDF 版无此句，**不作为逐字引语登记**」，**不要**为了让闸门通过而删掉这句差异记录 |
| 27 | **把尾随参考文献编号当笔记漏字** | 档案原句是 `…maintained contractility [18].`，笔记引到句号为止 ⇒ 诊断显示「档案侧插入」但人容易当成引漏了 | `[N]` 是原文引用标记不是正文，`del_=0, rep_=0` 即判**档案侧版式**；按库内惯例在笔记「自检」节**逐条登记、笔记不改**（同 `NLT6QW6I` / `T2YLDY8T` / `ZYKCVR4V` 的处理） |
| 28 | ★★ **「先转 md 再读」只立了禁令、没给判据** | §7i 写了不许视觉读页，但**没给可机械检查的判据**，实践中照样打开 PDF 首页对一下 DOI（本轮 `RFPARGXF` 的卡与笔记都写了「PDF 首页 DOI 自检」）——理由是「看一眼自检」感觉像小事 | 按 **§7i-1**：判据只看**这一步的输入是 md 还是 PDF 页**。`ingest_local_pdf.py` 落 md 后直接从 md 认 DOI（出版版 PDF 首页的题名/刊期/DOI 在 md 里本来就有，**不多给信息**）；交付前 `Grep 'PDF 首页\|首页 DOI\|读首页'` 扫本批卡与笔记，看到就改成「入档 md 正文认 DOI（命中 N 次）」。**只改口径表述，数字与引语本来就取自 md，不必重做入档** |
| 29 | ★ **Springer 断词形态把正则打空** | 形态是 `Sci\xad entific`——**U+00AD 后跟一个空格 0x20**（不是 Elsevier 的行末 `num- ber`）；用 `([A-Za-z]+)\xad([A-Za-z]+)` **处理 0 处、字符数完全不变**，看起来像「这篇没有断词」 | 正则改 `([A-Za-z]{2,})\xad\s?([a-z]{2,})`；**排查办法是 `repr()` 打印码位**，别靠猜形态。另：**字典收尾必须人工兜一道**——字典合并 125 处后仍残留 20 处（`uti\xad lized` 这类不命中），要打印残留逐处用显式映射表合并（实测 Springer 那篇合并 19 处才清零）。见 §7g-2 三形态表 |
| 30 | **句首大小写差异：覆盖 100% 却仍判未命中** | 笔记引语开头把 `The mean follow-up` 写成小写 `the` ⇒ `--diagnose` 报「覆盖 100%、插入 0 删字 0 替换 0」，**三类计数全 0，看不出原因** | `normalize()` **不折叠大小写**。凡「覆盖 100% 却 miss」一律回档案核**首字母**；这是**必须改笔记**的一类，不能按「档案侧版式」放过 |
| 31 | **AHA/Circ AE 的引用上标是无标记裸数字** | 档案是 `…interpolation errors,13 underscore…`、`…ventricular arrhythmia,32 but this warrants…`（无括号），诊断同样显示「档案侧插入 2 字符」⇒ 极易误判为笔记漏字 | 与 Elsevier/Springer 的 ` [9, 13]` 带括号形态并列记入 §8.6 第 ⑤ 类；判据仍是 `del_=0, rep_=0`（真漏字会同时有 `del_` 或 `rep_`） |
| 28 | ★ **「先转 md 再读」只立了规则没卡住判据** | §7i 写了禁令，但**没给可机械检查的判据**，实践中照样打开 PDF 首页对 DOI（本轮 `RFPARGXF` 卡写「PDF 首页 DOI 自检」）。理由是「看一眼自检」感觉像小事 | §7i-1：**判据只看输入是 md 还是 PDF 页**。`ingest_local_pdf.py` 落 md 后**直接从 md 认 DOI**（`grep -o '10\.[0-9]\{4,5\}/…' \| sort \| uniq -c`），**出版版题名/刊期/作者块本来就在 md 里，全程不必打开 PDF**；交付前 `Grep 'PDF 首页\|首页 DOI\|读首页'` 扫本批卡与笔记，看到就改成「入档 md 正文认 DOI（命中 N 次）」。**只是口径表述要改，数字与引语本来就取自 md，不必重做入档** |

---

## 完批验收清单（跑完必查）

```bash
cd ~/ResearchVault
# 1 L1 卡数 == 批内条数？
ls -1 10_Triage/Cards/*.md | wc -l
# 2 L1 判「进入 L2」数 == L2 篇数 == L4 真档案数？（任一不等即有悬空项）
grep -l "决定：进入 L2" 10_Triage/Cards/*.md | wc -l
ls -1 20_Notes/*.md | grep -v _Index | wc -l
# ★ L4「真档案」数：必须排除 `source_type: none` 的**摘要级占位档**，
#   否则闸门会把只存了摘要的档也数进去（实测 55 vs 真 53，凭空多出「2 条悬空」）。
grep -L '^source_type:[[:space:]]*"*none' 40_Fulltext/md/*.md | wc -l
ls -1 40_Fulltext/md/*.md | wc -l        # 仅用于发现差异：多出来的就是占位档
# 3 每篇 L2 的 fulltext_path 都真实存在？
# 4 双校验器，退出码均 0
PY=~/.workbuddy/binaries/python/envs/default/bin/python
$PY 90_Meta/Schema/validate_schema.py
$PY 90_Meta/Schema/validate_vault.py
```

**L1 判「进 L2」的数量必须等于 `20_Notes/` 篇数、也等于 L4「真档案」份数**——三者不等即为悬空项
（实测抓到过一次：建库首张卡判了 P0 却一直没取全文，整条流程「看起来跑通」实则断在这）。

⚠️ **`40_Fulltext/md/` 里可能混有摘要级占位档**（`source_type: none`，只有摘要没有全文；
实测库里躺着 2 份，其中 1 份对应的卡还判着「进入 L2」——那是真悬空，另一份是「暂存」卡，本不该有档）。
判「是否已有全文」**一律看卡的 `fulltext_route`，不看 md 是否存在**（`gen_fulltext_gap_list.py` 就是这么做的，
所以占位档不会污染缺口清单）；但**数档案数时要排除它们**，否则凭空多出几条假的「悬空」。

**批次统计只认 `L1_batch_input_{date}.json`，不认 `triage_date`**——同一批卡的分诊日期可能全写同一天，
按日期分组会把多个批次混成一个桶。实测曾把批次搁置数写成 15，按批次输入清单实数为 **16**。

---

## 批次记录

- `90_Meta/State/变更记录.md` 追加条目：批内条数 / 各步产物路径 / 未覆盖面 / 待办。
- 结构性变更（改 schema、改枚举）才需要版本递增 + 用户批准；**批次数据不触发冻结流程**。

### 已跑过的批次（作为规模参照）

| 批次 | 日期 | 条数 | 进 L2 | 搁置 | 暂存 | 排除 |
|---|---|---|---|---|---|---|
| D4 试点（`01_方法学` + `02_基质定量` + `03_临床结局`） | 2026-09-17 | 15 | 7 | 3 | 1 | 4 |
| 批量入库（VTH 对照 + VTH 缺口 + 循环标志物，三集合并行） | 2026-09-17 | 49 | 33 | 16 | 0 | 0 |
| **用户手供 PDF 入档**（`XPUKL6KE` / `6Q8TMP9F` / `C7EC9FUZ`，全为自动通道已判死的 P0/P1） | 2026-09-19 | 3 | 3 | — | — | — |
| **用户手供 PDF 入档（第二批）**（`DFJP7DTH` IDEAL-AF / `T2YLDY8T` Kuo / `R7WL3RKR` Georgi / `VSCH2026` van Schie / `FM7MRQK6` Heinzmann） | 2026-09-19 | 5 | 5 | — | — | — |
| **合计**（+ 建库首卡 1 篇补完） | | **73** | **49** | **19** | **1** | **4** |

- 批量批次的搁置优先级：P0 8 · P1 7 · P2 1。**P0 搁置最值得优先人工取件。**
- 手供批次实测：入档 3 篇（13/15/10 页），**同时清掉 1 条断链 + 3 条悬空**；核验后三篇未命中 5/2/0，
  **8 条全为档案侧版式，笔记原文无误**，另修掉 3 条被旧档案掩盖的笔记侧真错 + 回补 4 处 `±`。
- 第二批手供 5 篇（126 KB 级的 IDEAL-AF 在内，3 个子代理并行）：**清掉 1 条断链（`DFJP7DTH`）+ 4 条缺口**；
  核验 312 条引语 → 未命中 10，**10 条全为档案侧版式**（页首抬高的图注/表题切断跨页句 7 条、页脚跑行 2 条、首页刊名残片 1 条）；
  收口时改掉 1 条「把档案残留当引语」的写法（`R7WL3RKR` 作者块，且用 Crossref 反证**卡与 Zotero 是对的**）。
- 批量批次实测耗时集中在「建 L2 笔记」与「L3 回扫」两段；抓全文反而是最快的一段。
- ⚠️ **并发子代理 429 会打断批次但已建文件不回滚**——中断后先数文件数再幂等补缺（见坑 8）。
