---
name: zotero-journal-metrics
description: 给 Zotero 文献库批量补全期刊指标（影响因子 / JCR 分区 / 中科院分区 / Top 期刊 / 文章类型 / 预警标记）。涵盖权威数据源获取与镜像、DOI→Crossref 反查权威刊名与 ISSN、多源合并匹配、以及用本地 API 安全写回 Zotero（追加合并、不覆盖原有 extra 与标签）。当用户说"给 Zotero 补影响因子/分区""标注文献指标""批量查分区"时使用。
agent_created: true
---

# Zotero 期刊指标批量补全

## 一、先确认三件事（决定成败）

- 1. **不要覆盖用户数据**。写入前必须先读一遍库，统计有多少条目已有 `extra`、已有 `tags`。
  实测一个 380 条的库：132 条已有 `extra`(PMID)、189 条已有项目标签。覆盖 = 不可逆的数据丢失。
2. **分区有多个互不相同的标准**，必须先问清：JCR 分区（Q1–Q4）、中科院分区（1–4 区）、新锐分区。
   国内评聘常用中科院分区，但它**不是** Clarivate 的产品。
3. **Zotero 本地 API 的 token 几分钟就过期**，批量脚本必须能自动续签。

## 一·补、⚠️ 最大的坑：模糊匹配会静默产生错误指标

**写错一个 IF 比留空危害大得多** —— 用户拿去做评聘材料就是学术事故。
实测一次 `子串包含 + 长度差<30` 的宽松匹配，把
`Journal of Cardiovascular Risk` 和 `Journal of Atrial Fibrillation` **同时**匹到
同一条记录并给出 `IF 4.3 / BIOCHEMISTRY & MOLECULAR BIOLOGY 119/328` —— 两条都是错的。

**安全匹配的唯一正解是走 ISSN**：

```
PubMed esummary  →  返回体里有 issn / essn 字段（很多人不知道）
        ↓
  去掉非 [0-9X] 字符、统一大写
        ↓
  与 JCR 表的 ISSN/EISSN 列、中科院表的 "issn1/issn2" 列做**精确**比对
```

- 为什么不能用刊名相似度：`Europace` 的 NLM 全称是
  `Europace : European pacing, arrhythmias, and cardiac electrophysiology : journal of the working
  groups on cardiac pacing, ... of the European Society of Cardiology`，
  与 JCR 表里的 `EUROPACE` 相似度只有 **0.39** —— 高分刊直接漏掉（实际 IF 10.2）。
- 如果一定要用相似度兜底：阈值 ≥0.94，**并且必须把命中的刊名打印出来人工核验**，
  不能只看命中数量。退回纯名称匹配时用 `difflib.SequenceMatcher`。
- 建 ISSN 索引时**必须跳过 CSV 表头行**，否则 `journal,ISSN,EISSN,...` 这行会让
  `issn_map["journal"] = ("ISSN","EISSN")`，之后任何含 "journal" 的刊名都会命中，
  把字面量 `ISSN` 写进报告。合法 ISSN 用 `^[0-9Xx\-]{4,}$` 过滤。

## 二、数据源（不要只依赖 LetPub）

⚠️ **LetPub 现状（2026）**：JCR 分区需注册登录才显示；**中科院分区已整站下架**，被其自研"新锐分区表"取代。
所以 LetPub 已不能作为中科院分区的来源。

**推荐：GitHub 公开数据集**（`hitfyd/ShowJCR`，**默认分支是 `master`**）：

```
https://raw.githubusercontent.com/hitfyd/ShowJCR/master/中科院分区表及JCR原始数据文件/<文件名>
```

| 文件 | 提供 |
|---|---|
| `JCR2025-UTF8.csv` | **IF 数值** + JCR 分区 + 学科 + 排名 |
| `FQBJCR2025-UTF8.csv` | **中科院分区**（大类/小类/Top）+ ISSN |
| `XR2026-UTF8.csv` | 新锐分区预警标记（如 `Under Review`） |
| `GJQKYJMD2024/2025.csv` | 国际期刊预警名单 |

字段示例：
- JCR：`Journal,ISSN,EISSN,Web of Science,IF(2025),Category_1,IF Quartile(2025)_1,IF Rank(2025)_1,...`
- 中科院：`Journal,年份,ISSN/EISSN,Review,Open Access,Web of Science,标注,大类,大类分区,Top,小类1,小类1分区,...`

**兜底源** `ManSold/JCR-CAS-2025-table` 的 `JCR_2025.csv`（仅 `期刊名,Quartile`）：
覆盖比 ShowJCR 版更广，但**没有 IF 数值**。两套互补，**必须合并**——实测
`Computers in Biology and Medicine`、`Heliyon` 在 ShowJCR 版缺失、在 ManSold 版有。

> raw.githubusercontent.com 在国内常超时（HTTP 000）。备用镜像：
> `https://cdn.jsdelivr.net/gh/<user>/<repo>@<branch>/<路径>`

## 三、拿到权威刊名与 ISSN（关键一步）

Zotero 里的 `publicationTitle` 多是 NLM 缩写且**大量条目没有 ISSN**（实测 158 个刊名里仅 32 个带 ISSN）。
不要硬猜缩写，用 DOI 反查 Crossref：

```
GET https://api.crossref.org/works/{doi}
User-Agent: YourApp/1.0 (mailto:you@example.org)   ← 带上 mailto 才是 polite pool
→ message.container-title / message.short-container-title / message.ISSN / message.type
```

- 每条加 ~0.12s 间隔，失败重试 3 次；支持断点续跑（结果落盘缓存）。
- 291 个 DOI 约 3–4 分钟，能拿到 288 条权威刊名。

## 四、匹配策略

```
ISSN（Crossref 给的） → 精确匹配 JCR / 中科院 的 ISSN 或 EISSN
   ↓ 未命中
归一化刊名匹配：大写 → 去前导 THE → 去标点 → 折叠空格
   ↓ 未命中
手工 NLM 缩写别名表（J AM COLL CARDIOL → JOURNAL OF THE AMERICAN COLLEGE OF CARDIOLOGY 等）
```

未命中的通常就是：会议论文、bioRxiv 预印本、已停刊期刊、无 DOI 的笔记条目 —— 属正常，如实标注"未收录"即可。

### ⚠️ 2026-09-17 实测：**别信 ISSN，它可能大面积缺失**

一次「重做」暴露了三个叠加问题，覆盖率从 36 → **334**（分母 355 篇 journalArticle）：

| # | 问题 | 实测数字 | 处置 |
|---|---|---|---|
| 1 | **Zotero 的 `ISSN` 字段大面积为空** | 355 篇里只有 **43 篇有 ISSN（12%）** | 加「归一化刊名」与「DOI→Crossref」两级，不要指望 ISSN |
| 2 | **刊名不是同一个字符串** | Zotero 常带副标题（`Europace : European pacing, arrhythmias, …`）而 JCR 用 `Europace` | 归一化：剥 ` : ` 之后的部分 / 剥括注 / 去前导 THE / 去标点 |
| 3 | **跑的是过期快照** | 上一轮用的 items 快照 `dateAdded` 最晚只到前一天，**不含当天新导入的批次** | 见下「先对表，再看覆盖率」 |

分级命中数（实测）：`T1 ISSN 39 · T2 归一化刊名 209 · T3 DOI→Crossref 82 · 未匹配 25`。
**只按 ISSN 是 36；加上归一化刊名就到 222。** 所以 ISSN 缺失不是「查不到」的理由。

**前缀/后缀匹配可以加，但必须要求候选唯一。**
JCR 里 `PACE-PACING AND CLINICAL ELECTROPHYSIOLOGY` 带前缀、`JOURNAL OF PHYSIOLOGY-LONDON` 带后缀，
精确匹配对不上。但**不能用「任意包含」**——实测它会把 `The Journal of Physiology`
匹到 `AMERICAN JOURNAL OF PHYSIOLOGY-CELL PHYSIOLOGY`（**完全不同的刊**）。
规则：`n.startswith(q) or n.endswith(q) or q.startswith(n) or q.endswith(n)`，
且 `词数≥3 且长度≥18`，且**候选去重后必须只剩 1 个**，否则不匹配。

**Crossref 调用要重试。** 单次失败就缓存 `None` 会让一批条目静默漏配
（实测 `The Journal of Physiology` 的 ISSN 在 JCR 里明明存在，却因一次超时被判为未匹配）。重试 3 次 + 退避。

### ⚠️ 先对表，再看覆盖率——「没数据」和「没跑」是两件事

本轮的真主因不是匹配算法，是**时序**：指标跑完后用户又导入了一批文献，那批从未进过流水线。
**判据**：把 Zotero 当前全库的 key 集合与上一轮产物（`merged_*.json`）的 key 集合做差集——
差集里的条目就是「漏跑」，不是「无数据」。

> **写进笔记/报告时的用词必须区分**：
> - 「**该刊未被 JCR 2025 收录**（已按 ISSN → 刊名归一化 → DOI/Crossref 三级核对）」—— 是结论
> - 「**本库未收录该刊指标**」—— 只是描述了我们的数据缺口，**会让读者误以为是客观事实**
>
> 本轮实测有 **35 篇 L2 笔记**写着后者，其中 33 篇其实有数据。**「本库没有」永远不该直接写进交付物。**

### ⚠️ 聚合报告时的两个坑（实测踩过）

1. **同一本刊在库内有多种写法**。例如 `J Am Coll Cardiol` 与
   `Journal of the American College of Cardiology` 并存（5 条会被拆成 2 行）；
   `The journal of extra-corporeal technology` 与 `The Journal of ExtraCorporeal Technology` 同理。
   → 聚合前先建**别名表**（merged 数据的 `names` 字段 + 手工 CANON 覆盖），别只用 `lower()`。
   注意 `ALIAS.update(CANON)` 必须覆盖**全部**变体，只覆盖一个仍会分裂。
2. **同一刊不同条目的 JCR 行信息量不同**（有的只有 `Q1`，有的带 `Q1 | CATEGORY 4/237`）。
   按"先到先得"会丢掉学科排名 → **取字符串最长的一条**作为该刊的代表值。
3. **刊名显示值取「出现次数最多的写法」**，不是最长的。
   实测 `Europace` 组内 27 条里有 4 条写的是 NLM 全称（60+ 字），
   取最长会把整张表撑爆；取众数才是干净的 `Europace`。
4. 刊名首尾可能有 `- `、`·` 等杂字符（用户手工录入），聚合前要 strip。

### 反向体检：找出漏配的 IF

```
有「JCR分区:」但无「影响因子:」的行 = 匹配漏网，必查
```
2026 年实测漏配 10 条，两类原因：
- **缩写/全称不一致**（JACC：JCR 表里叫 `JACC-Journal of the American College of Cardiology`，
  按 `J Am Coll Cardiol` 归一化匹配不上 → 手工别名补上，IF 22.3）
- **该刊当年确实没有 IF**（见下节）

### ⚠️ 期刊被 On Hold / 除名 → 当年根本不发 IF

**不要当成"匹配失败"，更不要拿旧值冒充当年值。**
中科院表第 7 列会标 `SCIEOnHold`（全表仅 16 个刊有此标记，是强信号）。
此时应写「末次 IF + 说明」，并在 extra 里单开一行 `WoS 状态:`：

```
影响因子: 6.3（末次 2024 年；2025 年未发布）
JCR分区: Q1
...
WoS 状态: 2024-04 起 On Hold，2025-11-17 被 SCIE 除名（Editorial De-listing）
文章类型: 论著
```

2026-09 实测两例（务必用一手来源复核，勿凭印象）：
- **Computers in Biology and Medicine**：2024-04 起 On Hold，**2025-11-17 被 SCIE 除名**
  （Elsevier 在 Guide for Authors 页有官方公告）。末次 IF 6.3。中科院 2025 医学 2 区。
- **Heliyon**：2024-09 起 On Hold，2026-05 解除，但**当年（JCR 2026 周期）仍未获 IF**，
  预计 2027 年恢复。末次 IF 3.4（2023）。中科院 2025 综合性期刊 4 区。

标签可加 `WoS已除名` / `期刊曾OnHold`，比 `IF≥5` 这类档位标签更有信息量。

**已确认的除名/On Hold 期刊（2026-09 核实，附一手来源）**：

| 期刊 | 时间线 | 末次 IF |
|---|---|---|
| Computers in Biology and Medicine | 2024-04 On Hold → **2025-11-17 除名**（Elsevier 官网公告） | 6.3 |
| Heliyon | 2024-09 On Hold → 2026-05 解除，当年仍无 IF | 3.4 (2023) |
| Journal of Personalized Medicine | 2024-12-10 除名（MDPI 官网公告，拟 2026-12 重申请） | 3.0 (2023) |
| Disease Markers | **2023-03-20 除名**（Hindawi 19 刊批量下架） | 3.464 (2021) |

## 四·补、⛔ 其他「查不到 IF」的情况必须显式标注，不能留空

留空与"没查到"在 Zotero 里长得一模一样，用户无法区分。**凡是确认无 IF 的，都要写一行**：

```
影响因子: 无（未收录于 JCR 2025 与中科院分区表 2025）
```
标签配 `未收录JCR`。实测一个 331 条的库，一次性把 15 条这类条目标注清楚后，
"无 IF"的条目从"疑似漏配"变成"确认无需补"，审计才能真正归零。

**不要给非期刊文献查 IF**（预印本 / 专著 / 图书章节 / 会议论文 / 研究报告）——
它们本来就不该有。这类条目用 `【文献信息】` 作小节标记。
⚠️ 注意：用户可能在两轮之间**自己把 itemType 改对**（journalArticle → preprint/book/…），
也可能某条标着 journalArticle 其实是 bioRxiv 预印本（DOI 前缀 `10.1101/` 即 bioRxiv，一眼可判）。

## 四·补二、预警期刊名单（⚠️ 只能用 ISSN 匹配，禁止模糊）

用户常自带一份《预警期刊列表》（科研处/微信流传的 xlsx，列形如
`序号 | 期刊名称 | issn | eissn | 来源依据`）。实测「来源依据」取值：
`Hindawi出版社` / `Frontiers系列期刊` / `中信所预警期刊` / `中信所预警-高危` /
`中科院预警-低|中|高`，还会有 `中科院预警-中、中信所预警-高危` 这类多源拼接。

写入格式（放在 `文章类型:` 之前）+ 标签：

```
国际期刊预警: Frontiers系列期刊
```
```
tags += 预警期刊
```

**硬规则：**

1. **ISSN 优先，绝不用刊名模糊匹配。** 实测 `AEROSPACE`（中科院预警-低，名单里还没 ISSN）
   与 `Europace` 的刊名相似度高达 **0.82** —— 模糊匹配会把 **22 篇 Europace 论文全部错标成
   预警期刊**。同类陷阱：`JOURNAL OF TROPICAL MEDICINE` ↔ `Journal of Translational
   Medicine`（0.82）、`INTERNATIONAL JOURNAL OF ENDOCRINOLOGY` ↔ `International Journal of
   Cardiology`（0.88）、`JOURNAL OF INTERVENTIONAL CARDIOLOGY` ↔ `Journal of Interventional
   Cardiac Electrophysiology`（0.83）。**都是不同刊。**
2. **名单本身常有脏数据**，归一化时要容错：
   - ISSN 中间夹空格：`0360- 1293`、`1816- 112X`、`2169- 1401`、`1878- 1705` → 先剥掉所有非字母数字
   - 位数错误：`1472-3:46`（实为 `1472-3346`）→ **记下来告知用户，别硬猜着补全**
   - 缺失写法五花八门：`N/A`、`-`、`/`、空串 → 一律当「无 ISSN」，退回刊名精确比对
3. **只标注命中项，不给未命中写「无」。** 预警是「有没有」型标记，写 300 行「无」只会淹没
   真正的命中；用户可用标签 `预警期刊` 反向筛选。（与第 4 节「影响因子: 无」的处理**相反**：
   那条是必要的，因为留空与查不到无法区分；这条不必要，因为标签本身就是筛选器。）
4. 收尾必做**反向体检**：拿名单全部刊名 × 库内全部刊名跑相似度 ≥0.80，逐对人工确认是否同一刊。
   不跑就无法排除「名单 ISSN 写错 → 漏配」。实测 236×160 会冒出约 38 对，**全部是不同刊**，
   属预期；关键是确认没有真命中被漏掉。

## 五、文章类型

按 DOI 从 **PubMed eutils** → **Crossref**（`type` 字段）依次取，映射为中文：
`journal-article→论著`、`review→综述`、`clinical trial→临床试验`、`meta-analysis→Meta分析`、
`case reports→病例报告`、`editorial→社论`、`guideline→指南`。
PubMed 覆盖不到的非 MEDLINE 期刊会落到"未识别"，按下节补。

### 5.1 把"未识别"清零：四级递降策略（实测 23/23 可清零）

| 级 | 手段 | 命中率 |
|---|---|---|
| 1 | **从 `url` / `extra` / `archiveLocation` 正则抠 PMID 或 PMC 号 → esummary 直查** | 最高，务必放第一位 |
| 2 | PMC 号 → **ID Converter** 换 PMID | `https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids=PMC5135163&format=json` |
| 3 | 宽松标题检索：`re.split(r"[:\-–—]", title)[0]` 取主标题 → 去标点 → 取前 9 个词 → `[Title]` | 约 1/4 |
| 4 | Crossref `query.bibliographic` + 刊名交叉校验 → `type` | 兜底 |

**关键教训**：
- ❌ 直接用完整标题 `[Title]` 检索会大量 `quotedphrasesnotfound`
  —— PubMed 对长标题分词敏感，精确短语反而查不到。
- **第 1 级常被忽略但最有效**：Zotero 条目的 URL 里往往就躺着
  `pubmed.ncbi.nlm.nih.gov/38266130`，extract 出来直查即可，零歧义。
  实测 7 条漏网里有 6 条靠这一招解决。
- 人工录入的"占位标题"（如 `CCN5 reverses established cardiac fibrosis (Jeong 2016)`）
  检索必然失败 → 用关键作者 + 关键词检索 PubMed 再人工确认
  （此例定为 JACC 2016;67(13):1556-1568, PMID 27150688）。
- PubMed 的 `pubtype` 是**数组**，映射要按优先级排序匹配
  （`systematic review` 必须排在 `review` 之前，否则全被吞成"综述"）。

### 5.2 非期刊文献（Zotero itemType 不是 journalArticle）

**不要给它们查 IF/分区** —— 客观上不存在。只在 extra 里写类型，
并且**用 `【文献信息】` 而不是 `【期刊指标】` 作小节标记**，避免一本专著顶着"期刊指标"标题。

| itemType | 中文 | 核验要点 |
|---|---|---|
| `report` | 研究报告 | 机构报告编号，如 RAND `RR-A4180-1` |
| `preprint` | 预印本 | `10.48550/arXiv.*` 前缀即 arXiv；DataCite 可验 `types.resourceTypeGeneral = Preprint` |
| `conferencePaper` | 会议论文 | ACM/IEEE 会议录 |
| `bookSection` | 图书章节 | Crossref 的 `type = book-chapter` 可一次定位（含所属书名） |
| `book` | 专著 | OpenLibrary / 图书馆编目（"Type of document: Book"）核 ISBN |

### 5.3 文章类型标签的自洽校验

审计时要区分「**没有**类型标签」和「有标签但值是**未识别**」——
只查 `tags` 里有没有 `文章类型-` 前缀会把后者漏掉。正确写法：

```python
m = re.search(r"文章类型[:：]\s*(.+)", extra, re.M)
if not m:              → 完全没有
elif "未识别" in m.group(1): → 有但没解决
```

## 六、写回 Zotero（安全第一）

### 需要的两个头
```
Zotero-API-Key: <token>        ← 注意：curl/urllib 都要显式加
Zotero-Server-ID: <server_id>  ← 缺这个会报 428 "Zotero-Server-ID not provided"
```

> ⚠️ **428 有第二个成因：`urllib` 的 `headers=` 字典会把头名做 `.capitalize()`。**
> `Request(url, headers={"If-Unmodified-Since-Version": "935"})` 实际发出的是
> `If-unmodified-since-version`，Zotero 认不出，同样回 **428 Precondition Required**——
> 报错信息与「缺 Zotero-Server-ID」完全相同，极易误判成没授权而白查半天。
> **必须改用 `req.add_header("If-Unmodified-Since-Version", str(version))` 逐个添加**
> （`add_header` 不做大小写改写）。这一点 `zot_bulk.py` 是对的，照抄它。
> 另：`Zotero-API-Key` / `Zotero-Server-ID` 两个头也必须走 `add_header`。

### 授权（token 很短命）
```bash
POST http://localhost:23119/api/local/authorize
Headers: Content-Type: application/json, Zotero-Server-ID: <server_id>
Body:    {"libraryID":21540183,"libraryType":"user","appName":"<AppName>"}
```
- **缺 `appName` 会报 "appName is required"**；缺 `Zotero-Server-ID` 报 428。
- **返回体里字段名是 `key`，不是 `token`**：`{"key":"...","remember":false}`
- 批量时必须在收到 **401** 时重新授权并重试该条。
- ⚠️ **authorize 端点本身会限流 / 偶发超时**（一次运行里连调两次就可能
  `TimeoutError`，Zotero 侧可能在等确认）。对策：**把 token 缓存到本地文件复用**，
  只在 401 时才重新授权；且授权函数要带 3–4 次退避重试。实测这样跑 24 条写入零失败。
- 💡 写回脚本用「**先 GET 该条 → 基于最新 extra 组装 → 再用该条 version PATCH**」，
  比复用整库快照更稳（快照可能已过期导致 412）。条数不多时优先这么做。

### 写入
用 **PATCH** 只改 `extra` 和 `tags`，带 `If-Unmodified-Since-Version: <version>`；
收到 **412** 说明版本冲突 → 重新 GET 取 version 再重试一次。

```json
{"extra": "...", "tags": [{"tag": "JCR-Q1"}]}
```

- **`tags` 是整体替换**：必须传「原有标签 + 新增标签」的并集。
- **但「并集」对互斥标签是错的**：`文章类型-*` 是**互斥**的（一条不可能既是综述又是论著）。
  `merge_tags()` 只并集不删除，直接追加会得到 `文章类型-论著` 与 `文章类型-综述` **并存**。
  → 正确做法：**先剔除全部 `文章类型-*` 旧值，再追加新值**，然后整体 PATCH。
  → 写前先打印「旧 文章类型 / 新 tag / tag 总数变化」，写后**回读复核**只应剩一个。
  （2026-09-17 实测 4 条：全部是「论著 → 非论著」的替换，tag 总数不变。）
- **`extra` 用幂等标记块**：写一个 `【期刊指标】` 标记，重跑时把标记之后的内容整体替换，
  标记之前的原有内容（PMID 等）原样保留。
- **只改确有错的，不要顺手「补全」**：差异比对分桶（明确错标 / 建议扩充 / 未识别）时，
  只有「明确错标」才动库。建议扩充（如「论著」→「临床试验」，现值并不错）与未识别条目
  **一律不动**——没发现错就不动库，否则一次写回会污染几百条。
- **写前必备份**：把目标条的 `version` / `tags` / `extra` 原文存一份 JSON 快照再动手。

### 建议的注解格式
```
PMID: 39581432            ← 原有内容，保留

【期刊指标】
影响因子: 7（JCR 2025）
JCR分区: Q1 | CARDIAC & CARDIOVASCULAR SYSTEMS 34/237
中科院分区: 医学 1区（338/5603） | Top期刊
中科院小类: 心脏和心血管系统 2区（30/223）
国际期刊预警: Frontiers系列期刊      ← 仅命中预警名单时才有此行，放在「文章类型」之前
文章类型: 论著
数据来源: JCR 2025 · 中科院分区表 2025 · PubMed
```
标签建议：`JCR-Q1` / `中科院1区` / `Top期刊` / `IF≥10`(或 ≥5、<5) / `文章类型-论著` / `预警期刊`

> 插入新行时**不要重排已有行**：定位 `^文章类型[:：]` 在其前插入即可，
> 这样用户原有的 `PMID:`、`Edition:` 等行完全不受影响。脚本要幂等
> （先 `re.sub` 掉旧的同名行再插入），否则重复跑会叠行。

## 七、验收

写完后**必须回读全库审计**，不要只信写入返回码：
拉取全部条目，统计含标记块的条数，检查 `journalArticle` 数量是否 100% 覆盖，
并抽样确认原有 `extra` 行与原有标签仍在。

四条必查指标（写成一个脚本一次跑完）：

```python
docs = [i for i in ITEMS if i["data"]["itemType"] != "attachment"]  # 附件不计入
"仍含'未识别'"        → 必须为 0
"无文章类型"          → 必须为 0
"有 JCR分区 但无 IF"  → 必须为 0（或已显式标注 On Hold）
"无任何指标块"        → 应为 0
```

⚠️ 两点：
- **附件（`attachment`）不算文献条目**，分母要用过滤后的数
  （实测 336 个顶层条目 = 331 文献 + 5 附件）。
- 用户可能在两次运行之间**自己在 Zotero 里改了 itemType**（把 journalArticle 改成
  book/report/preprint）。**每次都重新拉取**，不要复用上一次的快照做判断。

## 八、可选：用 WOS 补缺

若机构有 WOS 权限（可用 `session-cookie-bridge` 技能把浏览器会话桥接过来）：

- 高级检索页用 `eval` 设 query textarea 的值并触发 `input`，再找文本为 `Search` 的按钮 `.click()`。
  **直接点 ref 常被底部 cookie 同意横幅挡住**，先关横幅。
- 支持多条 DOI 合并：`DO=("a" OR "b" OR ...)`；结果页导出**单次上限 1000 条**。
- 结果页能读 **Document Types**（补文章类型）与 Web of Science Categories。
- ⚠️ WOS 结果页**没有** IF 字段；JCR 需单独订阅且只开放个人邮箱登录，机构 SSO 通常进不去。
- ⚠️ `agent-browser download` 会把守护进程挂住（`os error 35`），导出改用别的方式。

## 九、脚本清单（`scripts/`）

| 脚本 | 用途 |
|---|---|
| `cr_journals.py` | DOI → Crossref 权威刊名 / ISSN（带缓存与重试） |
| `merge_journals.py` | 多套 JCR / 中科院数据合并成期刊主表 |
| `zot_annotate.py` | 生成 extra 文本块与标签（含幂等 `【期刊指标】` 标记） |
| `zot_bulk.py` | 批量 PATCH 写回（401 自动续签、412 自动重取 version） |
| `make_report.py` | 生成指标报告 HTML |
| **`zot_audit.py`** | **全库审计**：拉最新条目 + 4 项必查指标 + 类型分布 |
| **`resolve_types.py`** | **把「未识别」清零**：PMID/PMC 直查 → ID 转换 → 宽松标题 → Crossref |
| **`resolve_noif.py`** | **给缺 IF 的条目回查**：PMID/DOI → ISSN 精确匹配 JCR/中科院，命中会打印刊名供核验 |
| **`match_warnlist.py`** | **预警名单匹配**：名单 csv + 库内条目 → hits/miss JSON；ISSN 优先、刊名兜底，附名单脏数据排查与相似度反向体检 |

> **定点改类型标签的单条/少数条写回**：不必动用 `zot_bulk.py` 的整库快照。
> 参考实现见 `~/ResearchVault/90_Meta/State/zot_type_writeback.py`（`--dry-run` / `--apply` 双档，
> 自动存写前快照、校验「extra 除该行外逐字未变」、写后回读复核）。

> `zot_audit.py <server_id> <library_id>` 是收尾必备：四项指标全 OK 才算完成。
> `resolve_types.py <untyped.json>` 的输入就是审计里「仍含未识别」的条目子集。
> `resolve_noif.py <items.json>` 的输入就是审计里的全量条目；它**只报告不写库**，
> 结果必须人工看过命中的刊名再决定是否写回。
> `match_warnlist.py <warnlist.csv> [items.json] [out_prefix]` 输出的 `_hits.json`
> 既可直接喂给写回脚本，也是给用户看的「命中明细」；**只标注命中项**。
