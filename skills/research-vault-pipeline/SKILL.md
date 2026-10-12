---
name: research-vault-pipeline
description: 在 `~/ResearchVault/`（主库）或任何按本规范建的 vault（如 `~/CFD_Vault/`）里跑「L0 Consensus 检索入口 → Zotero → L1 摘要分诊 → L2 全文精读 → L3 冻结 schema 知识页」五层文献流水线（L4 = 40_Fulltext 原文档案层；L0 = 00_Consensus 检索入口层，把 Consensus query 级 AI 综合快照作为库内第一层）。当用户要**用检索结论开一个新的证据链入口**、批量分诊文献、写精读笔记、建主题/概念/方法/关系/争议/综合页、回扫知识页、校验 vault 合规性，或**按「引文网络是否共享」判据新建一个库**时使用。含 schema v1.0 冻结条款、L1 分诊卡五字段、木桶证据分级、合成成熟度闸门、同队列重复报告计数口径、两个校验器（含 L0 段）与建新库的完整动作；**并含「引语闸门」`verify_note_quotes.py` 的完整口径与五模式 CLI 契约**（`--json`/`--quotes-file`/`--corpus-dir`/`--coverage-file`/`--report-dir`）与扩展纪律——核验 L2 笔记引语是否逐字取自原文、跑「引语是否命中」「笔记覆盖度」「入库即出质检报告」、或改动/调用该脚本时必读（归一化引擎是唯一真源，外部程序不得重写）；**并含引语修复 `repair_note_quotes.py` 的三段式（诊断→逐条确认→才落笔）与「档案侧字形不可信」准入闸门、以及 L3 硬闸 `gate_l3.py`（五态判定 + exit 1 阻断，未过闸门不得进 L3）**——要修引语、判「某篇/L3 页能不能过闸门」、或发现 L3 的 sources 引语对不上时必读。
agent_created: true
---

# ResearchVault 文献流水线

## 何时用

- **用一次检索（Consensus query）开一个新的证据链入口** → 建一张 L0 检索入口卡（先于单篇分诊，给整条 query 拍快照 + 导航到库内已有 L1/L4）
- 给 Zotero 某个集合做批量分诊（读摘要 → 决定去留）
- 把一篇论文写成 L2 精读笔记
- 从多篇笔记合成知识页（六类之一）
- 校验 vault 是否符合冻结 schema

## 库位置与结构（固定，勿改）

```
~/ResearchVault/
├── .obsidian/                Obsidian 库配置（打开过才会生成；空目录=从没被 Obsidian 认领）
├── 00_Consensus/             L0 检索入口层：Consensus query 级 AI 综合卡（{query-slug}.md）
│   └── {query-slug}.md      type=consensus_synth；恒 evidence_grade=interpretation；不可直接引用
├── 00_Inbox/                 新条目落地区
├── 10_Triage/                L1 摘要级分诊卡
│   ├── _Index.md             分诊总表
│   └── Cards/{zotero_key}_{短标题}_{年份}.md
├── 20_Notes/                 L2 全文级精读笔记
│   ├── _Index.md             精读总表
│   └── {zotero_key}_{slug}_{年份}.md
├── 30_Knowledge/             L3 知识页（六子目录）
│   ├── Themes/ Concepts/ Methods/ Relations/ Controversies/ Syntheses/
├── 40_Fulltext/{xml,pdf,md}/ 原文档案（逐字保留）；md/{zotero_key}.md 是全库双链的落点之一
│                              ← 这就是「L4」：有必填 frontmatter，见下文专节
├── README.md                 给用户看的入口
└── 90_Meta/
    ├── Schema/知识层冻结Schema.md   ← 权威定义，先读它
    ├── Schema/validate_schema.py    ← 校验器 A：L3 + 模板（冻结合规）
    ├── Schema/validate_vault.py     ← 校验器 B：L0 + L1 + L2 + L3 快检 + **L4** + 双链（Obsidian 解析规则）
    ├── State/                      批次数据 / 变更记录（不许留 /tmp）
    └── Templates/                   L0 检索入口卡 + L1 分诊卡 + L2 精读笔记 + 六类知识页模板
```

L1 卡名用**短标题**而非第一作者——真实理由是**便于按主题扫读**（库内同姓氏作者大量重复，按作者命名无法辨识）。
> ⚠️ **一条被纠正的错误记载（2026-09-17）**：README 与本文件曾写「Europe PMC 常不返回可用的第一作者名，用作者会得到一堆 `{unknown}`」——
> **该理由不成立。** Europe PMC `core` 一直返回 `authorString`（全作者名）与
> `authorList.author[].authorAffiliationDetailsList`（逐作者单位）。真相是**生成 L1 卡时只取了作者人数**
> （`authors: 12`），把名字与单位都丢了。赵医生指出「zotero 里文章是不缺作者和单位的」后已实测确认并回填。
> **教训：写进文档的「工具限制」要先验证一次——它很容易变成掩盖自己漏掉字段的借口。**

**权威优先级**：`90_Meta/Schema/知识层冻结Schema.md` > 本文件。本文件只是操作摘要，两者冲突时以 schema 文档为准。

## 已定决策（2026-09-17，勿重新讨论）

| 编号 | 决策 |
|---|---|
| D1 | 独立库 `~/ResearchVault/`（**不用** `~/Documents/Obsidian Vault/`，那是另一处） |
| D3 | 转换引擎（**2026-09-27 更新**）：**新件默认 MinerU 4.x**（装受管 venv `envs/mineru`，doclib server 走 UDS；`flash` 档零模型可直转，`basic/standard/advanced` 需拉数 GB 模型）；pymupdf 链路（`reflow_two_column_pdf.py`）降为**兜底**（MinerU server 故障/无网络时用）。入口脚本 `90_Meta/State/convert_pdf_mineru.py`（既有 md 不回退重写，只服务新入档 PDF）。⚠️ 桌面版 MinerU.app（0.13.0）是独立 GUI、无可脚本调的本地端口，**不入链路** |
| D5 | 使用 Obsidian |
| D6 | L3 知识层 **schema 冻结 v1.0** |
| D4 | 试点范围 = `01_方法学` + `02_基质定量` + `03_临床结局`，**15 篇，已执行完毕** |

全文获取通道（**7 值：`none` / `epmc_xml` / `pmc_html` / `oa_pdf` / `pdf_local` / `subscription` / `manual`**）与转换细节见技能 `zotero-fulltext-feasibility`，不在此重复。
⚠️ 这 7 个值同时用于 **L1 卡的 `fulltext_route`** 与 **L4 档案的 `source_type`**——两处必须是同一套枚举，不放描述性文字（来源说明写进 `source_note`）。

> ⚠️ **援引冻结条款前先定位字面依据。** §7 冻结条款的作用域**只覆盖 L3 知识层六类页**，全文无 L1 分诊卡字段的字样。
> 我曾把 L1 的 `fulltext_route` 枚举也当成「已冻结」而不敢改——那是对 L3 条款的**越界援引**。
> 改 L1 的字段/枚举**不需要**版本递增、不需要迁移；改 L3 的枚举才需要（大版本递增 + 批量迁移 + 用户显式批准）。

## 多库：什么时候另建一个 vault

**判据：按「引文网络是否共享」分，不按「有关 / 无关」分**（后者主观且会漂移，前者是非此即彼的事实）。
三条**全否**才另建：

1. 两条线会不会互相引用？
2. 会不会进同一个 L3 知识页？
3. 能不能共用同一套 L2 模板字段？

**Zotero 不拆**——保持一个库 + 多集合（指标回写、类型闸门、查重这些基础设施是共用的，
拆两库等于把同一套运维做两遍）。拆的是 vault，不是 Zotero。

**建新库的完整动作**（`~/CFD_Vault/` 是 2026-09-17 的实例）：

```bash
V=~/NEW_Vault
mkdir -p "$V"/{00_Consensus,00_Inbox,10_Triage/Cards,20_Notes,30_Knowledge/{Themes,Concepts,Methods,Relations,Controversies,Syntheses},40_Fulltext/{xml,pdf,md},90_Meta/{Schema,Templates/Knowledge,Sources,State,Refs}}
S=~/ResearchVault
cp "$S/90_Meta/Schema/知识层冻结Schema.md" "$S/90_Meta/Schema/validate_schema.py" "$S/90_Meta/Schema/validate_vault.py" "$V/90_Meta/Schema/"
cp "$S/90_Meta/Templates/Knowledge/"*.md "$V/90_Meta/Templates/Knowledge/"
cp "$S/90_Meta/Templates/L1_分诊卡.md" "$S/90_Meta/Templates/L0_检索入口卡.md" "$V/90_Meta/Templates/"
# 再写：README.md、四个 _Index.md（10_Triage/20_Notes/30_Knowledge/40_Fulltext）、90_Meta/State/变更记录.md
# 以及该领域自己的 L2 模板
```

⚠️ **两个校验器必须「按自身位置推导库根」**（`os.path.dirname(os.path.dirname(os.path.dirname(__file__)))`），
**不能硬编码 `~/ResearchVault`**——否则新库的校验器一跑就检查错库（这是建 CFD_Vault 时改的）。
配套改动：`check_links()` 的 `os.walk` 起点也要跟着走。

⚠️ **新库的 L2 模板**：**键名沿用通用集**（否则校验器不认），**语义按本领域重写并在模板里注明**。
例：CFD 版把「血栓模型 / 血流参数 / 壁面剪切力」顶上原「标测系统 / 电压阈值」的位置。
⚠️ 领域词表也要换：`tags` 前缀（`cfd` 而非 `cardiology`）等。

⚠️ 复刻前先跑一次 `validate_vault.py` 确认新库 **ERROR 0 · WARN 0**——空库也不该有断链。

## L0 检索入口层（Consensus query 级综合卡，2026-09-18 新增）

**是什么**：`00_Consensus/{query-slug}.md`，把**一次检索（Consensus query）的 AI 综合结论**固化成库内**第一层**入口。它回答「关于 X，现有证据的全貌 + 我该钻哪几篇」，先于单篇分诊给整条 query 拍快照。

**与 L1 的本质区别（为什么单独立一层，不塞进 L1）**：

| | L1 分诊卡 | L0 检索入口卡 |
|---|---|---|
| 组织单位 | 单篇论文（绑 8 位 `zotero_key`） | **一个 query**（一次检索） |
| 内容 | 摘要级事实 | **AI 综合正文** + 它命中/导航到的文献清单 |
| 是否文献 | 是 | **否**（无 zotero_key，无 PMID/DOI 身份） |
| `evidence_grade` | 按摘要/木桶 | **恒 `interpretation`**（AI 合成，不可直接引用） |
| 文件名 | `{zotero_key}_{标题}_{年}` | `{query 归一化 slug}`（小写、连字符，**非 8 位 key**） |

**铁律（写 L0 卡时必须守）**：
1. **本卡不可作为引用依据**——它是导航与快照。要引用其中任一结论，必须回 `notes_keys` 指向的 L2 精读笔记（`fulltext_verified`/`note_supported`）。
2. `evidence_grade` **恒 `interpretation`**，校验器 B 会强制拦其它值。
3. **双链可行性 = 该 key 是否有 L4 全文档案**（`40_Fulltext/md/{key}.md` 存在）。有 L4 才挂 `[[key]]`；只有 L1 无 L4 的 → 只写 key 文本、**不挂双链**（否则 `check_links` 报未解析断链）。校验器 B 的 `check_l0` 对 `notes_keys` 里每个 key 做这道自检。
4. **盲区清单是待办而非结论**：`unmapped` 里列的是「Consensus 命中但库内尚无 L1 卡」的工作，未建 L1 前不得据此下判断。

**五节正文**（模板 `90_Meta/Templates/L0_检索入口卡.md`）：① 综合结论（逐条标来源工作）② 机制与局限 ③ 已入库 vs 盲区映射 ④ 对本研究的钩子（只写落在因果链上的用途）⑤ 本层使用规则。

**与 lit-fusion 的衔接**：L0 卡就是 lit-fusion「Consensus 优先」策略的落盘形态——跑完一次 query 检索，把它的 AI 综合答案 + 命中的、已映射进库的 L1/L4 工作 + 盲区，固化成一张 L0 卡，作为该条证据链的入口。

**建新库时 L0 要一起带**：`mkdir` 加 `00_Consensus/`；`validate_vault.py` 的 `check_l0()` 段（`--l0`）随库根自动推导，无需改动；模板 `L0_检索入口卡.md` 一并拷走。

## L1 分诊层：五字段 + 五条硬规则

**字段**：① 方案（做了什么）② 结果（发现了什么）③ 结论（作者怎么说）④ **创新点（两层）** ⑤ **对我研究的用途**

**硬规则**（违反即失去分诊层意义）：

1. **只记录摘要中出现的信息。** 未提及 → 写「摘要未报」，禁止推算或从别处补。
2. **本卡不可作为引用依据。** 任何进正式文稿的结论必须回到 L2 全文笔记。
3. **「创新点」必须分两层**：「作者自述」与「我的真实增量判断（含与哪篇比）」。摘要的创新声称有系统性夸大。
4. **分诊卡只回答一个问题**：这篇值不值得花时间精读。不回答「这篇讲了什么」。
5. 摘要不足以分诊时（如只有背景没结果），升级 `read_scope` 或直接判 `P3`，**不要用推测填补**。

**优先级**：`P0` 直接相关必引 / `P1` 相关候补 / `P2` 边缘仅存卡 / `P3` 排除（含预警期刊、质量不可信）。

**作者与机构字段（2026-09-17 补，勿再丢）**：frontmatter 必须有
`first_author` / `authors`（**完整 authorString**）/ `author_count` / `affiliation`（一作首个单位）/ `affiliations`（去重机构数）。
数据源：Europe PMC `core` 的 `authorString` + `authorList.author[].authorAffiliationDetailsList`。
⚠️ **Zotero 条目本身没有作者单位**（`journalArticle` schema 不含该字段；实测 365 条 creators 带 `affiliation` 的 0 条）——
**别在 Zotero 里找单位，要去 Europe PMC 取**。
（历史错误：早期只存了 `authors: 12` 这个**人数**，名字与单位全丢，还在 README/技能里写下「Europe PMC 常不返回可用作者名」的借口。该理由不成立。）

**决策四态**：进入 L2 精读 / 暂存 / **搁置（全文不可得）** / 排除。

> **「搁置」与「暂存」必须区分**（2026-09-17 新增）：
> **暂存**＝分诊判定本身未定，需再评估；**搁置**＝判定为「应进 L2」，但全文获取**物理失败**。
> 二者混用会把一次真实的获取失败**掩盖成一次判定保守**，从而低估知识库缺口。
> 搁置须在卡片第 6 节写明：失败通道逐条、尝试日期、**恢复条件**（PDF 落点 `40_Fulltext/pdf/{zotero_key}.pdf`）。

**已知数据缺口**：Zotero 条目的文章类型（论著/综述/读者来信/勘误）需从 Europe PMC 的 `pubTypeList` 取。**不查会出事**——曾把一篇 2,569 字的读者来信当成论著分诊。
⚠️ 但**库内已有的类型字段也不可盲信**：实测有读者来信被标成「论著」、ESC 指南被标成「论著」。
判据与只读比对脚本见 `zotero-fulltext-feasibility`（`diff_types.py`），**回写口径为「只补缺口、不覆盖细粒度值」**。

> **✅ 错标已处理完毕（2026-09-17）**：实时比对全库 380 条 → 明确错标 4 条，**全部已写回 Zotero**
> （`7CYSNY8J`→综述 / `9N95AJD9`→通讯 / `JC7U4YT8`→指南 / `TAN5DY7D`→评论）。
> 报告 `90_Meta/State/type_diff_live_20260917.md`、脚本 `zot_type_writeback.py`、快照 `type_writeback_backup_20260917.json`。
> **建议扩充 0 条 · 未识别 49 条一律未动。**

> **⚠️ 处理 Zotero 元数据的操作铁律（用户 2026-09-17 明确）**
> **发现错了 → 报错并直接更正；没发现错 → 不动 Zotero。** 不需要逐条请示。
> 差异比对的三个桶就这么处理：**「明确错标」直接改，「建议扩充」与「未识别」不动**——
> 后者不是错误，动了就是把几百条没问题的条目一起搅了。
> 反过来，**机械细节（如标签替换、字段格式）不要拿去请示**，那是执行问题不是决策问题。
> 用户在意的是「别把简单事做复杂」，不是「多问」。

## L2 精读笔记

门槛：**L2 是全库唯一「可引用」的一层。**

模板：`90_Meta/Templates/L2_精读笔记.md`（与 `L1_分诊卡.md` 平级；**不放入 `Knowledge/`**——校验器只认该目录 + 六类白名单）。
心内科版含 `study_design` / `evidence_level` / `registration` / `sample_size` / `follow_up` / `primary_endpoint` 等专属字段。
文件名 `20_Notes/{zotero_key}_{slug}_{year}.md`（例：`PATT7B2D_DECAAF-II_2022.md`）；目录索引 `20_Notes/_Index.md`。
主要结果须配**效应量三件套**（点估计 + 95% CI + p）与**原文引用**。
发现有分歧 → 不要在笔记里裁断，标为「应交 L3 争议页处理」。
主观判断（作者未提的局限、机制推断、效能判断）一律行首标 `[推断]`，与原文陈述严格分开。

⚠️ **身份链陷阱**：笔记的 `zotero_key` 必须是 **Zotero 8 位 key**，**不是** PMCID。
转换脚本可能把 PMCID 误写进 `zotero_key`（`pmc_html_to_md.py` 早期版本即有此 bug，已修）——
**写笔记前先 `grep '^zotero_key:' 40_Fulltext/md/{key}.md` 核一遍**，否则笔记会指向一个不存在的键。

**当前状态（2026-09-17 批量入库后）**：**41 篇**。L1 判定「进入 L2 精读」的 41 张卡 ⟷ `20_Notes/` 41 篇 ⟷
`40_Fulltext/md/` 41 份，**三者相等，悬空项 0**。这个等式就是本层的体检指标，**不符即为悬空项**（见「踩过的坑」）。

分布：设计等级 1 级 1 · 2 级 9 · 3 级 8 · 4 级 18 · 5 级 3 · 不适用 2；
`evidence_grade` = `interpretation` 34 · `note_supported` 7（**无 `fulltext_verified`**——木桶取最低值，
笔记里几乎必然含有跨文献转述或已标 `[推断]` 的判断，所以整篇很少能停在最高级）。

**必填 frontmatter**：`zotero_key`（**置于首位**，全库主键，不得变动）/ `title` / `type: literature_note` /
`study_design` / `evidence_grade` / `fulltext_path`（固定 `40_Fulltext/md/{zotero_key}.md`，不手填）。

⚠️ **`evidence_level` 与 `evidence_grade` 不是一回事**：前者是**研究设计等级** 1–5（研究本身有多硬），
后者是**本笔记论断的可靠度**三级枚举（我这句话有多可靠）。两者都要填。
⚠️ L2 的 `evidence_grade` 同样取**本笔记最弱的一条**（木桶最低值）。

### 「与既有证据的关系」一节的出处核查（2026-09-17 新增）

该节与别处不同：**它写的是别人论文里的结论，而那条结论我们通常只有二手转述**。
所以必须把两件事分开标：

| 说法 | 含义 | 允许用吗 |
|---|---|---|
| **出处已定位** | 只做到了「找到 DOI/PMID」——**书目级定位** | ✅ 但要明写「内容未核验」 |
| 已核验 | 读过了原始文献、核对了那条结论 | ❌ **本层做不到，禁写** |

**硬约束（先探明再动手）**：全文档案里的参考文献表**曾经一份都没有**——实测 41 份档案 **0 份可用**
（24 份 `## References` 标题下为空、17 份连标题都没有）。**但这不是源头没有**：
档案多从 Europe PMC fullTextXML 转出，**XML 里 `<ref-list>` 一直在**（实测单篇 30–41 条），是**转换脚本丢的**。
→ **先跑 `restore_refs.py` 把表补回来**，再谈核查。补回后 **39/41 份 · 全库 1,358 条**。

**恢复表的两条注意**：
- **剥标签要用空格**：`<name><surname>Rolf</surname><given-names>Sascha</given-names></name>`
  直接删标签会拼成 `RolfSascha`；相邻 `<name>` 之间还要补 `, `。
- **XML 端点会稳定 500**（实测 PMC9214588 / PMC11967559）→ 走 Crossref `reference` 兜底。
  ⚠️ 但 **Crossref 的 `key` 编号不可信**（JAMA 那篇 40 条里有重复号）——
  **只有恰好构成 1..N 才采用其编号**，否则用顺序编号并在标题里写明「编号不等于原文编号」。

**两条核查路径（都做，互相验证）**：

| 路径 | 依据 | 强度 |
|---|---|---|
| `resolve_refs.py` | 本篇 PMID → `elink(pubmed_pubmed_refs)` → `esummary` → **按作者姓匹配** | 推断 |
| `verify_refs.py` | **本篇自己的参考文献表**（权威、带编号）按作者姓检索 | 直接 |

⚠️ **按姓匹配，不按 `[N]` 顺序对齐**——PubMed 的引文列表顺序不可靠。
⚠️ **L2 笔记 frontmatter 没有 `pmid` 字段**（只有 `zotero_key`/`pmcid`/`doi`）；PMID 在 L1 卡里，
连接必须走 `zotero_key`。这是个容易卡住的点，别在 L2 里找 PMID。

**实测结果**：✅ 唯一命中 52 · ⚠️ 同姓多重 11 · ❌ 未命中 1 · **两条路径互相矛盾 0 处**。
强度例证：U3RUIYYC 的 Vlachos/Ahmed-Jushuf/Strisciuglio 落在本篇 ref **2/27/15**，
与笔记当初记的 `[2]/[27]/[15]` **逐一吻合**。
**抓出的真错**：`VJG75RI8` 把 **Ozcan** 拼成 **Ozcab**（本篇 ref [13] 一作）——
**拼错一个字母，读者就永远找不到那篇**。这正是「链接核查原始出处」要抓的东西。

**四条防「自己制造假结论」的判据**（都是实测误报后才加的）：

1. **Crossref 兜底的参考文献表不含作者名**（只有题名/刊名/年）→ 按姓匹配必然全数未命中。
   若不排除，会写出「本篇参考文献表无此姓氏」——**把工具缺陷说成转述错误**。
   排除方法：恢复脚本在标题里写了来源字样（含 "Crossref"）→ 直接跳过该表。
2. **全大写缩写与试验名不是姓氏**（ALICIA / DECAAF / ERASE-AF / STABLE-SR-II / HDWS / LAA）：
   匹配前剔除，否则同样产生「无此姓氏」的假结论。
3. **同姓歧义一律不链**：本篇文献表里同姓 ≥2 条 → 只标「须回原文确认是哪一条」，**不许猜**。
4. **冲突检测要在「本名字之后、下一个名字之前」取 DOI**：
   一个表格行常同时写好几个作者（如某行内同时有 McManus 与 Dawson），
   取整行第一个 DOI 会**报出根本不存在的「不一致」**（已踩过）。

**写回标注**：`〔**出处已定位·经本篇参考文献表核对（本篇 ref N），内容未核验**〕`。
**口径不变：仍是书目级定位，不等于内容核验**；该节 `evidence_grade` **不因链上 DOI 而升级**。

### ⚠️ 写「会改文件」的脚本时：`--dry-run` 必须在代码里真的 gate 住

本库实测踩过一次：脚本的**写入块没有受 `--apply` 管束**，加上**检测正则 `References?\s*$`
匹配不上带尾注的标题**（`## References（本节由 …）`）→ 每次运行都走「追加」分支，
反复运行把 **18 个文件堆出多个 `## References` 段（最多 3 段）**。
**是靠「同一文件里出现 3 个 References」这个异常现象才发现的。**

> 两条通用做法：
> ① **写入前先判 `if args.apply:`**——写在文档里的「默认 dry-run」不算数，必须在代码里；
> ② **收尾多看一眼「有没有不该有的东西」**，不能只看「该有的东西在不在」。
> 换个说法：**脚本报「成功 N 份」是脚本自己说的；重复段是文件里的证据。**

#### ⚠️ 幂等性的唯一证据：**第二次运行必须「已写回 0 篇」**

同一天里本库连踩**三次**同一类缺陷，共同点都是**把「再写一次」当成「覆盖」**：

| 场景 | 症状 |
|---|---|
| 参考文献段恢复 | 检测正则匹配不上带尾注的标题 → 走「追加」分支 → 18 个文件堆出多个 `## References` |
| 脚本写入未 gate | `--apply` 只管了建目录，没管写入 → 不带参数运行也照写 |
| 核查标注写回 | 「替换第一条」+ 裸 `\*\*` 匹配到标注自身 → 标注越跑越多（52 条写出 101 处） |

**判据：凡是「会改文件」的脚本，收尾必须跑第二次并确认输出「已写回 0 篇」。**
这一条把上述三处全部暴露出来了——**第一次运行的成功输出不能证明任何东西。**

写回类脚本的四条硬做法：
1. **`if args.apply:` 真的 gate 住写入**（不是只 gate 住建目录）；
2. **按「出现位置」逐个处理**，不按名字/键去重后只处理第一处——同名可能出现在不同行，每行都该有自己的标注；
   从后往前改，前面的偏移才不被破坏；
3. **片段边界要同时受「下一个同类标记 / 换行 / 表格竖线」约束**，且找「下一个名字」用 `\*\*[A-Z]` 而非裸 `\*\*`
   （标注自身就是 `〔**…**〕`，裸匹配会匹配到它）；
4. **幂等靠「先清空该片段内所有标记、再插入唯一一条」**，并在收尾加一遍**同行同标记去重**，兜住历史遗留的位置漂移。



## L3 知识层：六类页（冻结枚举）
| code | 类型 | 最小来源数 | 关键专属字段 |
|---|---|---|---|
| `KT` | 主题页 | ≥ 3 篇 L2 笔记 | `scope` |
| `KC` | 概念页 | ≥ 2 | `term_en` / `domain` |
| `KM` | 方法页 | ≥ 2 | `modality` / `applicability` |
| `KR` | 关系页 | ≥ 2 | `from` / `to` / `direction` / `strength` |
| `KV` | 争议页 | ≥ 2，**须分属不同立场** | `sides` / `root_cause` / `resolution` |
| `KS` | 综合页 | ≥ 2 个 KT/KV | `question`（须为可证伪问句）/ `coverage_ledger` |

**通用 11 键**（全部必填）：`schema` `type` `id` `title` `status` `evidence_grade` `sources`
`source_count` `created` `updated` `tags`

**枚举**：
- `status` = `seed` / `growing` / `stable` / `frozen`
- `evidence_grade` = `fulltext_verified` / `note_supported` / `interpretation`
- `direction`（仅 KR）= `positive` / `negative` / `none` / `mixed` / `unknown`
- `resolution`（仅 KV）= `open` / `provisional` / `settled`
- `maturity`（仅 KS）= `draft` / `reviewed`

### ⚠️ 硬闸：未过引语闸门不得进 L3（2026-10-07 起）

上面的「最小来源数」只约束**数量**，不约束**这些来源本身可不可信**。所以另有一道硬闸：

```bash
cd <vault>/90_Meta/Schema && python gate_l3.py     # 0 = 全过；1 = 有来源未过
```

逐页逐 `sources` 判定 `PASS` / `REPAIRABLE` / `FAIL` / `NO-FULLTEXT` / `NO-NOTE`，**非 PASS 即阻断**。
详见本文末尾「L3 硬闸 `gate_l3.py`」一节。**先过闸门，再谈来源数够不够** ——
闸门红了不是「顺手把页改掉」的理由，是先回去把来源那一侧弄干净。

### 三条最容易违反的规则

1. **`evidence_grade` 取木桶最低值，不是最高值。** 一页里 9 条有全文支撑、1 条是猜的 → 整页 `interpretation`。
2. **争议不许在 KT/KC/KM/KR 页裁断**，只能另建 KV 页，原页用 `→ [[KV_xxx]]` 指向。
3. **每个论断行尾必须带 `— [[zotero_key]]`**；无来源标记的论断一律降级为 `interpretation` 并以 `[推断]` 开头。

### 合成成熟度闸门（防「看起来像结论的东西」）

建 KS 页需同时满足：① ≥2 个 KT/KV 上游；② `question` 是**可证伪的具体问句**
（「消融前标测能否独立预测复发」✅ / 「关于左房基质」❌）；③ 覆盖账本 `missing` 为空或已写明影响。
**三条不满足就只建 KT。** 未达门槛的页可以建但 `status` 必须为 `seed`，且不得被其他页引用。

### 写完新 L2 必须回扫 L3（硬规则）

L3 的**强度判断随来源数变化**，不是「建完就固定」。每落一篇新 L2 后，逐页过一遍上游 L3：

1. 该篇是否属于某页的 `sources` 范围？→ 是则加进 `sources` 与 `source_count`
2. 该篇是否**推翻或限定**了页内某条论断？→ 是则改论断正文（不是加一句附注了事）
3. 该篇是否引入新的阈值 / 定义 / 口径？→ 是则同步到 KC（概念）、KV（争议）、KM（方法）各页
4. 该篇是否改变了「证据强度」的措辞？→ 是则改 `strength` 段与独立证据线计数
5. 全部改完 → `updated` 字段更新 → 跑校验器 A

> 实测量级：一篇新 L2（`VBX4SZCD`）入库后同步了 **7 个 L3 页面**；批量入库 2 篇（`QMJHWD3P`、`TQPTC2N2`）
> 同步了 **5 个 L3 页面**（`KR-002` 17→19、`KV-001` 24→26、`KC-001` 7→9、`KM-001` 8→10、`KS-001` 9→12）。
> **只写 L2 不回扫 = 知识页停留在旧证据上，而且是静默的**（校验器不会报——数字自洽）。

### 同队列多次报告：`duplicate_of` 与「独立证据线」计数

两种不同情况，处置完全不同，**不要混**：

| 情况 | 判据 | 处置 |
|---|---|---|
| **同一篇论文的多条 Zotero 记录** | 同 DOI / 同 PMCID | 非主记录加 `duplicate_of: <主记录 key>`；`sources` 只列一次 |
| **同一队列的两次报告**（不同论文） | 同伦理批号 + 同入组窗口 + 同作者名单 | **`sources` 可以列两条**，但强度判断**必须合并为一条** |

> 实测例：`H23DR8JB` 与 `TQPTC2N2` 同伦理批号 `13/YH/0349`、同入组窗口 2014-09–2015-08、
> 同 12 位作者 ⇒ 是同一队列的两次报告。计来源可列 2 条，**但 `KR-002` 的独立队列数写 13 而不是 14**。
> ⚠️ **「14 篇」不等于「14 条独立证据线」**——把样本量重复计入会系统性高估证据强度。

L2 层另有自动查重：校验器 B 会按 `doi` / `pmcid` 扫重复并 WARN（已声明 `duplicate_of` 的跳过）。

## L4 全文档案

`40_Fulltext/md/{zotero_key}.md`，逐字保留原文。**必填**：`zotero_key` / `title` / `source_type`。

| 键 | 约束 |
|---|---|
| `zotero_key` | 8 位、**必须等于文件名去 `.md`**、**不得形如 `PMC\d+`**（校验器 B 会拦） |
| `source_type` | 必须落在 7 值通道枚举内 |
| `source_url` | 可选；实际抓取的 URL |
| `source_note` | `oa_pdf` / `pdf_local` / `subscription` / `manual` 四种通道**必填**，写明来源站点与稿件版本 |
| `pmcid` | **与 `zotero_key` 是两个字段**——早期脚本把 PMCID 写进 `zotero_key`（键与文件内容错配，L2 反查全指错）。见 L2 节的「身份链陷阱」 |

> ⚠️ **`source_note` 为什么对 PDF 通道是硬要求**：`oa_pdf` 抓到的可能是**作者接受稿**而非出版版
> （实测 `TQPTC2N2` 来自 Aalborg 机构仓储，是 submittedVersion）。不写明版本，
> 日后引用时无法判断「正文数字与出版版是否一致」。这一条不是形式主义——它直接决定该篇能不能当引用依据。

## 操作步骤

### 批量分诊

1. 从 Zotero 本地 API（`localhost:23119`）拉条目，DOI/PMID/PMCID 提取口径见 `zotero-fulltext-feasibility`
2. 用 Europe PMC `resultType=core` 批量取摘要 + `pubTypeList`（文章类型）
3. 按 L1 五字段逐篇生成卡片，落 `10_Triage/Cards/`
4. 更新 `10_Triage/_Index.md` 的统计与明细

### 写 L2 精读笔记

1. **先核身份**：`grep '^zotero_key:' 40_Fulltext/md/{key}.md`（见上文陷阱）
2. 通读全文档案，按模板填字段；主要结果配**效应量三件套**（点估计 + 95% CI + p）+ 原文引用
3. **建证据锚点段**：把该篇对已有知识页有影响的事实单列（切点、定义、样本、资助/COI、原文矛盾）
4. 主观判断行首标 `[推断]`；分歧标「应交 L3 争议页处理」
5. 落 `20_Notes/{zotero_key}_{slug}_{年份}.md`，更新 `20_Notes/_Index.md`
6. **回扫 L3**（见下）

### 建 L3 知识页

0. **★ 先跑硬闸**：`cd <vault>/90_Meta/Schema && python gate_l3.py` —— 退出码必须是 **0**。
   非 0 就别往下走：先 `folio_repair_quotes` 修可修的，剩下的回 L2 逐条核（笔记错还是档案残），
   复检绿了再建页。**闸门红了还建页 = 把未核验的引语合成进知识层。**
1. **先做纯提取，不做裁断**：把所有 L2 笔记的事实卡 + 跨篇对照表 + 争议候选 + 关系候选
   汇成一份 `90_Meta/State/extract_for_L3_{YYYYMMDD}.md`（实测 8 篇可产出 ~850 行）。
   提取与裁断分离，避免边读边下结论。
2. 按对照表定页：某主题 ≥3 源 → KT；某概念 ≥2 → KC；方法 ≥2 → KM；关系 ≥2 → KR。
3. **争议单独建 KV**，不在 KT/KC/KM/KR 里裁断，原页用 `→ [[KV_xxx]]` 指向。
4. 满足闸门（≥2 个 KT/KV + 可证伪问句 + 覆盖账本完整）才建 KS；否则只建 KT。
5. 每个论断行尾带 `— [[zotero_key]]`；页内最低一级证据决定整页 `evidence_grade`。
6. 跑两个校验器 **+ 硬闸复检**（`gate_l3.py` 仍须 0）。

### 端到端顺序（照这个跑）

```
Zotero 集合 → 取摘要+pubTypeList → L1 卡（含 article_type 闸门）
                                    ↓ 决定=进入 L2
                              取全文 → 40_Fulltext/{xml,md}/ → 补 L4 frontmatter（source_type/source_url/source_note）
                                    ↓ 核 zotero_key（防 PMCID 混入）
                              L2 笔记 → 落 20_Notes/
                                    ↓ 全部 L2 落地后（数量必须对齐）
                              extract_for_L3_*.md（纯提取）→ L3 各类页 → 争议另立 KV → KS（满足闸门）
                                    ↓
                              validate_schema.py + validate_vault.py（双退出码 0）
                                    ↓
                              回扫：新 L2 是否改写已有 L3 → 同步 sources/source_count/updated → 再跑 A
                                    ↓
                              收口 四个 _Index.md（L1/L2/L3/L4）+ README.md + 90_Meta/State/变更记录.md
```

**顺序是硬的**：L2 未落地不得建 L3（来源数是硬门槛）；L3 未回扫不得收口。
每一步的产物都是下一步的输入，跳步会得到 `seed` 页或悬空项。

**收口时四层数字要能互相推出**：

```
L1「进入 L2」张数 == L2 笔记篇数 == L4 档案份数
L1 总数 == 进 L2 + 搁置 + 暂存 + 排除
L4 各通道份数之和 == L4 总数
```

不满足就是悬空项或统计错。**索引里的明细表用脚本生成，不要手抄**——手抄必然出错，
且错了不会有任何东西报警。

### 校验（每次改模板或加页后必跑）

**两个校验器分工，都要跑**，退出码均为 0 才算通过（ERROR → 退出码 1；WARN → 退出码 0）：

```bash
PY=~/.workbuddy/binaries/python/envs/default/bin/python
$PY ~/ResearchVault/90_Meta/Schema/validate_schema.py   # A：L3 + 模板
$PY ~/ResearchVault/90_Meta/Schema/validate_vault.py    # B：L0 + L1 + L2 + L3 快检 + L4 + 双链 + 库内残留
```

| 校验器 | 覆盖面 | 查什么 |
|---|---|---|
| `validate_schema.py` | `Templates/Knowledge/` + `30_Knowledge/` | 模板与冻结 schema 是否逐字一致、11 通用键、六组枚举、各类型最小来源数、`status` 是否越权（未达门槛必须 `seed`） |
| `validate_vault.py` | **整个 vault**（**L0 检索入口卡** / L1 卡 / L2 笔记 / L3 快检 / **L4 档案** / README / **库内残留**） | **L0 必填键、type/evidence_grade 枚举、文件名非 8 位 key、`notes_keys` 每个 key 必须有 L4 全文档案**；L1/L2/L4 必填键、`fulltext_route` 与 `source_type`（同 7 值枚举）、决策 4 值、L1 决定行的**可机读性**、L2 的 `fulltext_path` 是否存在、`zotero_key` 是否为 8 位 ASCII、**全库 `[[...]]` 双链按 Obsidian 规则能否解析**、**库内不该有的东西（`backup*` 目录 / `Sources` 外 ≥5 MB 大文件）** |

`validate_vault.py` 可用 `--l0` / `--l1` / `--l2` / `--l3` / `--l4` / `--links` 单跑一层（排查时比全跑快）。
**L0 段的自检要自证会响**：往某卡 `notes_keys` 塞一个无 L4 档案的假 key，`--l0` 应报 1 ERROR；还原后归零。

**两个脚本的判据不要互相引用**：A 的 `ENUMS`/`MIN_SOURCES` 以冻结 schema 为准，B 的 L1/L2 键清单
以 `README.md` 与本技能为准（L1/L2 **不受 §7 冻结条款约束**，见上文）。

#### ⚠️ 解析枚举字段前必须剥掉 YAML 行内注释

`scalar()` 取值前要先 `strip_comment()`。**这是真缺陷，不是洁癖**——库自带模板恰好在**枚举字段后面**写行内注释：

```yaml
fulltext_route: ""      # none/epmc_xml/pmc_html/oa_pdf/pdf_local/subscription/manual
```

不剥注释 → 把「值 + 一段中文说明」整体当成枚举值 → **照模板新建的卡一落盘就报「越界」**。
同类影响：`duplicate_of` 若带注释，解析出来是 `'ZX245LJK    # …'`，**任何按键比对的判重逻辑都会静默失效**。

规则与 YAML 一致：`#` 只有在「前面是空白」且「不在引号内」时才是注释起点。

> **碰到「校验器说越界、但看文件明明是对的」时，先怀疑校验器的解析口径，不要先改数据。**
> 这类错误会诱导你把正确的数据改成错的（本次若照报错改，就会把 7 张搁置卡的 route 改成一个更荒谬的值）。
> 反过来，**确认了是校验器缺陷，就修校验器并回归比对一遍全部解析结果**——
> 本次回归确认 15 处解析变化**全部是剥注释本身**，没有一处是意外的语义改变。

#### ⚠️ 双链校验必须按 Obsidian 的解析规则，不能用「key 前缀匹配」代替

**踩过的坑（2026-09-17）**：B 的链接检查曾对 8 位 key 用 `any(x.startswith(key))`
这种**前缀语义匹配**——只要 L2 里存在以该 key 开头的文件就算通过。后果是
**「校验器报 0 断链，而 Obsidian 里链接其实是灰的」**：语义存在 ≠ 点得开，两件事被混为一谈。

正确判据 = Obsidian 的实际规则：`[[X]]` 必须命中某 `.md` 的**基名**，或该文件 frontmatter
`aliases` 里的任一项。且**必须先剥掉 fenced code、行内代码、HTML 注释**里的 `[[...]]`
（Obsidian 不渲染这些位置）——否则文档与模板中的语法示例（如 `<!-- … [[zotero_key]] … -->`）
会被误报成断链，**那是检查器自己的假阳性**。

> **通用的教训**：写「引用是否有效」这类检查时，判据必须与**真实消费方**（这里是 Obsidian）一致，
> 不能自造一个更宽松的近似判据——近似判据会给出「一切正常」的假信号，比不检查更危险。

**已知解析落点（预期行为，不是断链）**：`[[PATT7B2D]]` → 命中基名，落到
`40_Fulltext/md/PATT7B2D.md`（原文档案）；`[[PATT7B2D_DECAAF-II_2022]]` → `20_Notes/…`（精读笔记）。
引用标记 `— [[key]]` 指向原始档案、完整文件名指向笔记，两者都可达，**不需要改链接**。

### 在 Obsidian 里打开这个库

库落在 `~/ResearchVault/`，**独立于** `~/Documents/Obsidian Vault/`。已注册进
`~/Library/Application Support/obsidian/obsidian.json`（备份 `obsidian.json.bak_*`）。

手工打开：Obsidian 左下角**库切换图标 → 打开其他库 → 打开文件夹作为本地库 → 选 `~/ResearchVault`**。

⚠️ **改 `obsidian.json` 必须先完全退出 Obsidian**——它运行时会把内存中的库列表写回该文件，
运行中写入的条目会被覆盖。本机 `osascript -e 'quit app "Obsidian"'` 会被 TCC 拦（-10004），
`osascript -e 'tell application "Obsidian" to quit'` 可用；
`open "obsidian://open?path=..."` **不会**注册新库，别指望它。
**库注册好之后 `~/ResearchVault/.obsidian/` 会自动生成 `app.json`/`workspace.json` 等——这是判断是否真的打开了的最硬证据。**

> 🚩 **操作纪律**：关软件这类小事**一次不成功就别再试第二种写法**，直接叫用户
> （把两个选项摆清楚：我来做 / 你来点）。用户明确要求过。
> 上面记的那几个失败写法是为了让你**第一次就用对**，不是让你在用户面前逐个试。

> 历史：2026-09-17 之前 B 不存在，L1/L2 **不合规不会被任何脚本拦下**，只能人工对照 `README.md`。
> 补齐后首次运行即抓出 **10 条真问题**（搁置卡决定行不可机读、L1 卡缺 `article_type`、
> 4 页 L3 正文引用未列入 `sources` 的键等）。**新写校验器是值得的——它抓出的全是人工审查漏掉的。**
> 同日稍后给 B **补上 L4 通道校验**（`--l4`），首次运行即抓出 2 份 `oa_pdf` 档案缺 `source_note`。
> **教训：每新起一层就要配一个关卡；L4 此前只被 L2 单向指过来，档案自身合不合规无人查。**

## 踩过的坑

- **`20_Notes/` 为空时不要建知识页。** 来源数是硬门槛，强行建只会得到一堆 `seed` 页，
  违反「宁可停在主题页」的初衷。
- **不要在 `10_Triage/` 下用 R。** R 会话会把 `.Rhistory` 写进当前工作目录，污染 vault
  （已发生过一次，文件已移出到 `/tmp/researchvault_stray/`）。
- **批次数据一律不许留在 `/tmp`。** `/tmp` 会被系统随时清理，而中间产物（类型补充数据、Zotero 原始条目等）
  常是跨会话复用的**唯一副本**。统一落 `90_Meta/State/`，命名带日期：`<用途>_<YYYYMMDD>.json`。
  曾差点因 `/tmp` 丢失而需要重跑全库网络请求。
- **不要把「判定可得率高」当成「能精读的篇数多」。** 原估全文可得率 93%，实际可精读率 **7/15 = 47%**。
  差异全部来自两处：① 未过 `article_type` 闸门（4 篇非论著撑大了分母）；② 通道实测失败（3 篇）。
  **分母要先洗过再做估算。**
- **先跑只读比对，再决定回写规模。** 「几千条待回写」往往是伪问题——实测全库 **380 条**里
  真正可动作的只有 **4 条**（且全部是「论著→非论著」修正）。直接开写会既慢又危险。
  ⚠️ 且**比对基准必须取自实时 API**，不得复用批处理中间产物
  （journal-metrics 运行**中途**的 `zotero_types_*.json` 只含已解析的条目，
  拿它当「现有值」会把「尚未解析」误报成「未识别」——实测虚报 4 条补充候选，全是伪的）。
- **不要用 `~/Documents/Obsidian Vault/`** ——那是另一个已存在的库，与本研究库无关。
- 模板文件一旦与 schema 不一致，冻结即失效。改 schema 必须同步改
  `90_Meta/Templates/Knowledge/` 六个模板，然后跑校验器。
- `evidence_grade` 木桶原则的意义：违背它就会复现「虚假掌握」——把整页可信度凭一条撑起来。

### 2026-09-17 全链贯通时新增的坑

- **写完新 L2 笔记必须回扫 L3。** 一篇新笔记会改写已有知识页的论断（`VBX4SZCD` 入库后
  同步了 **7 个 L3 页面**：新增的「同批患者双节律建图、0.5 mV 切点窦律 >28% vs 房颤 >72%」
  直接改写了阈值争议页与关系页多处结论）。**只写 L2 不回扫 = 知识页停留在旧证据上。**
  回扫后要同步 `sources` / `source_count` / `updated`。
- **L3 正文引用的键必须同时列入 `sources`。** schema §4 要求来源在 `sources` 内；
  正文写了 `— [[HFPNBAYI]]` 却没把 `HFPNBAYI` 放进 `sources` 会被校验器 B 抓出。
- **校验器正则里 `\w` 包含中文。** 写「双链引用必须是 8 位 Zotero key」的判据时，
  `re.findall(r"\[\[(\w{8})\]\]", body)` 会把 `[[KC_过渡带定义]]`（恰好 8 个字符）误判成 key。
  正确写法：`re.findall(r"\[\[([A-Z0-9]{8})\]\](?![A-Za-z0-9_])", body)`
  ——Zotero key 恒为大写字母 + 数字的 ASCII。**写完校验器要用「已知合规的文件」反测一次**，
  否则校验器自己的假阳性会掩盖真问题。
- **L1 的决定行必须可机读。** 写成 `- 决定：**搁置（全文不可得）** —— 分诊判定本为…`
  会让解释与值混在一行，校验器无法取值。拆成 `- 决定：搁置` + `- 说明：…` 两行。
- **L1 判定与 L2 实况必须对齐（悬空项排查）。** 反向检查：`grep '- 决定：进入 L2' 10_Triage/Cards/*.md`
  的数量应等于 `20_Notes/*.md` 的数量。不符时逐条找——`VBX4SZCD` 就是 L1 早已判 `P0` 进 L2、
  但全文一直没取的**建库首卡**，它同时缺 `article_type` 且决定行写着「（样例 demo）」。
  **"流程没写通"往往不是一个抽象判断，而是库里有这么一张具体的卡。**
- **`zotero_key` ≠ `pmcid` 会第二次复发。** 脚本已修，但**手工取全文时不会走脚本**，
  仍会把 PMCID 写进 `zotero_key`（`VBX4SZCD.md` 曾被写成 `PMC10410193`）。
  取完全文**立即** `grep '^zotero_key:' 40_Fulltext/md/{key}.md` 核一遍，再看 DOI/PMCID 是否齐。
- **原文内部的数字矛盾要如实记录，不要替作者圆场。** `VBX4SZCD` 的窦律最优面积切点
  Results 写 >60%、Discussion 写 >69%（真值在未转出的补充 Figure S2）；亚组 N 由 195 骤降至 142 原文未解释。
  这类矛盾**写进 L2 笔记的证据锚点**，并在 L3 页里作为「三套窦律阳性定义不可混用」的成因 —— 
  **不裁断、不抹平**，这正是 KV 页存在的理由。
- **「文件都在」≠「用户在 Obsidian 里看得到」。** 用户说「我没找到」时，先查
  `~/ResearchVault/.obsidian/` 是否**空目录**、`obsidian.json` 里有没有这个库——
  **库没被 Obsidian 认领的话，磁盘上写满笔记用户也是看不到的**。
  打开过的库一定会在 `.obsidian/` 下生成 `app.json`/`workspace.json`，这是最硬的判据。
- **链接的「语义存在」不等于「点得开」。** 校验器自造的宽松判据（如 key 前缀匹配）
  会给出「0 断链」的假信号，而 Obsidian 里全是灰链接。判据必须与真实消费方一致，
  并剥掉代码块/行内代码/HTML 注释中的 `[[...]]`（Obsidian 不渲染这些位置）。

### 2026-09-17 批量入库 49 篇时新增的坑

- **批次统计的唯一权威口径是 `90_Meta/State/L1_batch_input_*.json`（或同类的批次输入清单），
  不是 `triage_date`。** 全库 65 张卡的 `triage_date` 可能全是同一天（本库即如此），
  按日期分组会把所有批次混成一个桶，算出来的「本批搁置数」是错的。
  本库曾把批次搁置数写成 15，按批次输入清单实数为 **16**（33 进 L2 + 16 搁置 = 49）。
- **修订说明时不要凭印象写中间数字。** 首版曾写「`oa_pdf` 失败 17 篇」，实为两轮抓取共留
  **11 条**失败记录（`fulltext_fetch_run*_*.json`）。**宁可只陈述可核实的事实，
  或把中间数写成对账本文件的指针**（「详见 `…json`」），也不要写一个记不起来的数。
- **同一枚举字段出现多种写法时，先归一化再写校验。** `source_type` 曾混用
  `europepmc-xml` / `epmc_xml` / `pmc-html (…)` / `pc_html` / `oa_repository_pdf` 五种写法
  ——描述性文字与枚举值挤在一个字段里，**任何按键比对都会失败**。
  归一化时把描述性文字**移入新建的 `source_note` 字段**，不要直接丢掉（那是溯源信息）。
- **字段值自相矛盾时改数据，不放宽校验。** 7 张搁置卡的 `fulltext_route` 写着 `oa_pdf`
  （意为「通道可用」），与「搁置＝全文不可得」直接冲突，而另 12 张搁置卡写的是 `none`。
  **放宽校验会让这类矛盾合法化**——正确的做法是统一到能自洽的值，并把失败经过写进卡内。
- **新建的校验分支要用「已知合规文件」反测。** L4 校验（`source_type ∈ ROUTES`）首次跑
  41 份档案，抓出 2 份缺 `source_note` 的真缺口；但同样要确认**没把合规的误报**——
  跑完看 WARN 数是否等于你预期能解释的条数。
- **`strip_comment()` 缺失会让「照模板新建的卡」一落盘就报错**（详见上文校验专节）。
  这类缺陷的特点是：**旧数据全对、新数据全错**——因为模板自己就带行内注释。
  遇到「只有新写的报错、旧的都过」，优先怀疑解析口径而不是数据。

### 2026-09-17 五问（IF/作者/出处）新增的坑

- **⛔ 备份目录不能放在库内。** L2 备份曾落 `90_Meta/State/backup_*`，后果三连：
  ① 别名歧义 WARN **97 条**（同一笔记的副本与原件 `aliases` 撞车）；
  ② Obsidian 里出现重复笔记；③ 白白同步上云。
  → 统一放 **`~/ResearchVault_backups/<日期>/`**（库外）。**判据：备份是「给机器回滚用的」，不是「给人读的知识」，两者不该混在一个库。**
  ⚠️ **当时的防线是错的**：`check_links()` 只是「静默跳过」`backup*` 目录——那是为了消 97 条别名歧义 WARN 而加的，
  结果把「库内不该有备份」这个**真问题也一起静音了**（后来又漏进去一份，2.2 MB，无人察觉）。
  → 已改为 **`check_stray()`**：库内出现 `backup*` 目录、或 `90_Meta/Sources` 之外出现 ≥5 MB 大文件，**一律 WARN**。
  **通用判据：只用于「避免噪音」的跳过逻辑，会顺手把真问题一起静音。「跳过」与「报警」必须同时做。**
  **且新加的检查必须自证会响**——本轮用「造 6 MB 测试文件 + backup 测试目录」跑出 WARN 2 再清理回 WARN 0。
  **不会响的检查等于没有。**
- **⛔ 「本库未收录 X」不能当结论写进交付物。** 这是**描述我们自己的数据缺口**，
  读者会误以为「X 客观不存在」。实测 35 篇 L2 笔记写着「本库未收录该刊 IF/分区 → 留空，不推测」，
  其中 33 篇其实有数据（只是上一轮没跑）。
  **正确写法**：「该刊未被 JCR 2025 收录（已按 ISSN → 刊名归一化 → DOI/Crossref 三级核对）」。
- **⚠️ 指标/元数据流水线跑完后又导入新文献 → 必须补跑。** 本轮的真主因就是这个（不是算法）。
  **收尾检查**：把当前全库 key 集合与上一轮产物 key 集合做差集，**差集不为空就是漏跑**。
  「没有数据」和「没有跑」在报告里长得一模一样，但处置完全相反。
- **⚠️ 写在文档里的「工具限制」要先验证一次。** 「Europe PMC 常不返回可用的第一作者名」白纸黑字写在 README 与技能里，
  而事实是 `authorString` 一直可用、是我只取了人数。
  **它很容易变成掩盖自己漏掉字段的借口**——凡是「某某拿不到」的表述，落笔前实测一遍。
- **⚠️ 抽查时别只查数量，要查内容。** 本轮「作者回填 62 张」在脚本里全成功，
  但真正验证的是打开一张卡看到 `first_author: "Nairn D"` + 单位字符串。
  **数量是脚本自己报的，内容才是证据。**
- **⚠️ 交付说明里的数字/条目，必须与脚本里实际写的**逐条对上**。** 本轮交付说明写「配好 6 条过滤规则」，
  而 `configure_nutstore_sync.py` 里 `NEW` **只有 2 条**——多出来的 4 条从未写入。
  **配置本身没错（另 4 条本就由插件自动排除），错的是说明与配置不一致。**
  **写交付说明时回去看一眼脚本常量，别凭记忆列条目。**

## 引语闸门 `verify_note_quotes.py`：口径、CLI 契约与扩展纪律（2026-10-07）

**它是什么**：`90_Meta/State/verify_note_quotes.py`，核对「L2 笔记里的逐字引语是否真在 `40_Fulltext/md/<KEY>.md` 里」。
**它是归一化口径的唯一真源** —— 任何外部程序（Folio 工作台、未来的校验器）要判「引语是否命中」，
**必须调它**，不得在别处重写一遍归一化。**两侧漂移比没有审查更糟。**

### 可调用接口（2026-10-07 新增五个机器可读模式）

| 模式 | 用途 |
|---|---|
| `--json [KEY...]` | 结构化输出。`ok / vault / keys / requested / latin_min / totals{total,strict,loose,miss} / results[] / bad / errors / readErrors / skipped{count,note,sample}` |
| `--quotes-file <f>` | 对任意引语集逐条判级：`items[{id,quote,level,segments[{seg,level,where}]}]` |
| `--corpus-dir <d>` | 语料改为指定目录（键＝文件名去扩展名，与 `40_Fulltext/md` 同构） |
| `--coverage-file <f>` | 报「笔记里有 N 条引语 / 已收 M 条 / 差哪几条」 |
| `--report-dir <d>` | 写 `<d>/引语闸门_<YYYY-MM-DD>.md`（可单独用，不必带 `--json`） |

调用约定：`cwd = 脚本所在目录`（即 `90_Meta/State`），`env.RESEARCH_VAULT = <库根>`。
日常两条命令：

```bash
cd ~/ResearchVault/90_Meta/State
RESEARCH_VAULT=~/ResearchVault python3 verify_note_quotes.py --json          # 全库
RESEARCH_VAULT=~/ResearchVault python3 verify_note_quotes.py --json <KEY>    # 单篇
RESEARCH_VAULT=~/ResearchVault python3 verify_note_quotes.py --report-dir ~/ResearchVault/90_Meta/State/_review
```

### 五条硬纪律（改这个脚本、或接新调用方时必须守）

1. **★ 归一化引擎一个字都不能动**：`HTML unescape → NFKC → PUNCT_MAP → 去 C0 控制符 → 去 markdown 强调符 → 去全部空白 → 可选去连字符`。
   三态判定 `strict` / `loose`（仅连字符差异）/ `miss` 与 `LATIN_MIN = 0.35` 的口径都是契约。扩 CLI 只动**入口与输出层**。
2. **★「没报错」≠「已核验」**：判不了级的引语（含中文、或字母占比 ≤ `LATIN_MIN`）
   **整条不进结果**（`--quotes-file` 模式下 `skipped` 单列）；调用方的兜底分支**一律写 `"?"` 或 `"skip"`，绝不写 `"strict"`**。
   「缺全文档案」进 `errors`，**不静默计入 0 未命中**。
3. **写入只有一个入口**：显式传 `--report-dir` 时才写盘；其余路径**只读**（改完 grep 一遍写盘调用自证）。
4. **所有 JSON 模式一律 `exit 0`**，失败写进 `{"ok": false, "error": ...}`——调用方需要统一解析，
   不要用非零退出码表达业务失败。
5. **人读输出与 JSON 出口必须隔离**：用 `contextlib.redirect_stdout(io.StringIO())` 包住 JSON 分支，
   否则进度打印会混进 stdout 把 JSON 弄脏。

### 改它的标准动作（照这个顺序，别跳）

```bash
cd ~/ResearchVault/90_Meta/State
cp verify_note_quotes.py verify_note_quotes.py.bak-$(date +%Y%m%d)   # ① 先快照，记 md5
# ② 只改 CLI / 输出层
python3 verify_note_quotes.py > /tmp/new.txt                          # ③ 文本模式回归
diff <(python3 verify_note_quotes.py.bak-$(date +%Y%m%d)) /tmp/new.txt && echo 逐字节一致
python3 verify_note_quotes.py --json | python3 -m json.tool > /dev/null && echo JSON 可解析
```

> ⚠️ **回归以「文本模式逐字节一致」为准**——那是最能证明「没碰到引擎」的证据。
> 但**别拿全库总数当回归判据**：坚果云随时会同步进新笔记，总数会变。
> 正确做法：**按 key 集合做差集**，只比对两版都覆盖的那些篇目。
> 实测教训：一次回归中全库从 106 → 108 篇，我一度以为改坏了；查 mtime 才发现是同步落进来的新笔记。

### 报告口径（`--report-dir` 产出的 md）

分三节：**合计表**（含「**未被核验**」单列）、**未命中明细**、以及单列的
**「未被核验的篇目（**不算通过**）」**。开头固定一句：

> ⚠️ 「0 未命中」≠「全部已核验」。跳过的候选与未被核验的篇目都不在「严格命中」里，但它们也**没有被证明是错的**——只是没被查过。

**落点惯例**：`90_Meta/State/_review/引语闸门_<YYYY-MM-DD>.md`（可被程序重建，属派生产物）。

### 2026-10-07 的实测基线（可作回归参照）

- 全库文本模式：**274 行 / 31218 字节 / 106 篇**（当日的库规模）。
- `--json` 全库：`errors` 0、耗时 ~1.8 s、`skipped` 单列不混入未命中。
- 判级错例警戒：`--diagnose` 报「覆盖 100%、插入 0、删字 0、替换 0」却仍判未命中 ⇒ **句首大小写差异**（`normalize()` 不折叠大小写）。

### 引语修复 `repair_note_quotes.py`（2026-10-07 重写并接入 · 三段式）

**它做什么**：把闸门判为「未命中」的引语，在**能确认是安全字形差异**时修正笔记。

**三段式（不可压缩成一步）**：

| 段 | 命令 | 会不会改文件 |
|---|---|---|
| ① 诊断 | `folio_repair_quotes {keys:[...]}`（**省略 `apply`**）/ `python3 repair_note_quotes.py --json` | **绝不改** |
| ② 逐条确认 | 看 `fixable[].id` = `sha1(key + "\|" + 原文引语)[:12]`（**与顺序无关**，不按序号） | — |
| ③ 才落笔 | `--apply-ids ids.json --json`（**显式点名 id**） | 会改，先整份快照 |

**★ 只放行两类改动**：

1. **引号字形还原**：`'x'` → `"x"`
2. **补回良构 `±`** —— 三个条件同时满足：不删任何非空白字符 / 新增非空白字符全是 `±` /
   每个 `±` 都落在 `re.compile(r"\d\s*±\s*[\d(]")` 的语境里

其余一律归 `manual`，必须人去核。**这条闸门是本次最重要的教训，见下。**

#### ★★ 为什么必须这么紧：档案侧字符不可信（本次踩到的最大坑）

`40_Fulltext/md/` 里那些由 C0 字形还原生成的档案，**单个 U+00B1（±）同时编码四种真值**：

| 档案里的现象 | 真相 | 照档案改的后果 |
|---|---|---|
| `52±10 years`、`8.1±2.5 Hz` | 真 ± | — |
| `P ± .05`、`r ± 0.85` | 那个 `±` 是 **`<`**（相关系数不可能带 ±） | **把笔记里对的 `P < .05` 改成错的** |
| `±5 seconds`、`±2 minutes` | 还兼作 **`≈`** | 把 `~` 改成 `±` |
| `Taiwan, ±Second Department`、`Satoshi Higa, MD,±` | 还兼作**脚注 `†`** | 引入无关符号 |

档案自己的 frontmatter 已写明成因：「C0 控制字符字形还原（`\x01`/`\x02`→±，`\x03` 位置相关）」。
同类污染还有：**软连字符 U+00AD**（`per\u00adformed`，`normalize` 不剥它、表现为 `per formed`；照抄进笔记等于**注入不可见缺陷**）、
**markdown 记号**（`_h_`/`_observation_`，Europe PMC 的 `<italic>` 转出来的）。

> **判据一句话：档案缺而笔记有的字符，说明残缺的是档案，不是笔记。**

#### 收敛过程（「别急着信第一版诊断」的范本）

第一版诊断报「可自动修 113 条」，逐条抽查后发现两个致命问题（会把 `~` 改成 `±`；会把 `per\u00adformed` 搬进干净笔记）。三轮收窄：

| 动作 | 可自动修 | 须人工 |
|---|---|---|
| 初版（整条替换 `note.replace(raw_q, sub, 1)`） | 113 | 100 |
| 加符号闸门（`SYMBOLIC` 字符不许新增） | 106 | 107 |
| **把「仅连字符差异」也判为已命中** | 48 | 106 |
| 加 markdown 闸门 | 37 | 117 |
| `_patch()` **最小替换**（逐 opcode 只取非空白字形差） | 37 | 117 |
| **收窄成两类放行** | **1** | **153** |

> ⚠️ 「仅连字符差异也算命中」这条**别省**：否则会把笔记里正确的 `long-term`/`Fibrillation`
> 改成档案那边更脏的 `longterm`/`Fibril- lation` —— 档案的行末断词靠空格表达，整条替换会把那个空格搬过来。

最终全库归因：可自动修 **1**（`PLPVPJ2C`/`3553ccea7c47`，引号 `'`→`"`，ratio 0.992）；
须人工 **153** = 实质差异 95 · 软连字符 23 · 会删掉笔记侧标点 20 · markdown 11 · 省略号 4。

#### 落笔纪律与验证

- **备份必须落库外**：`~/ResearchVault_backups/<YYYYMMDD>_quote_repair/`。库内出现备份目录会被
  `validate_vault.py` 的 `check_stray()` 报 WARN，且会在 Obsidian 里**变成重复笔记**。
- 落笔时**重新诊断一遍**，过期 id 原样报 `missing`，不猜。
- 追加 `90_Meta/State/_quote_repair_log.json`（每条带日期）。
- **验证必须在沙盒里做**（真实 `20_Notes` 副本 + 软链 `40_Fulltext/md` + 脚本副本 + `BACKUP_ROOT` 落 `/tmp`，真库不碰）：
  **威力证据** = 闸门 `strict 52→53 / miss 6→5`；**幂等证据** = 第二次同 id 必须 `applied 0 / missing [id]`。
  **两条都要，缺一不可** —— 只验「改了有变化」会放过重复落笔。

### L3 硬闸 `gate_l3.py`（2026-10-07 新建）

**「未过引语闸门，不得进 L3」的强制执行点。** 判定单位 = 「L3 页 × 该页 `sources` 里的每个 key」。

**五态**（不是三态 —— 「档案缺」与「引语对不上」是两回事）：

| 状态 | 含义 | 处置 |
|---|---|---|
| `PASS` | 0 未命中 | 准进 L3 |
| `REPAIRABLE` | 未命中**全部**是可安全自动修的字形差异 | 先跑修复，复检再进 |
| `FAIL` | 有实质差异 | **不准进** —— 回 L2 核是笔记错还是档案残 |
| `NO-FULLTEXT` | 笔记在，`40_Fulltext/md/<KEY>.md` 缺 | **不准进** —— 引语从未被核验过 |
| `NO-NOTE` | 没有 L2 笔记 | **不准进** —— 没有可引用的层 |

`BLOCKING` **含 `REPAIRABLE`** —— 闸门的意义是单义，「可能可修」也是「现在还没过」。

```bash
cd <vault>/90_Meta/Schema
python gate_l3.py                 # 全库体检 · 有未过则 exit 1
python gate_l3.py --key KHG52E5I  # 单篇：能不能进 + 被哪些 L3 页引用（citedBy）
python gate_l3.py --json          # 机器读 · exit 1 不变
python gate_l3.py --quiet         # 只出汇总（当 CI 门）
```

**退出码是硬语义**：`0 = 全过；1 = 有来源未过`。**`--json` 也不破例** ——
这是个闸，不是查询接口，静默成功会让人以为「反正都过」。

#### ⚠️ 两条实现陷阱（都踩过）

1. **`parse_sources()` 必须同时认两种写法**：行内 `sources: [A, B]`（KR/KV 用）与块状 `sources:` + `  - A`（KT/KM 用）。
   只认一种会**静默漏掉半库来源** —— 而在这个位置上「漏掉」等于**放行**，是最危险的失败方向。
   > 自检法：逐页比对 `source_count` 字段与解析数，必须**零不一致**。
2. **`import` 进来的 `verify_note_quotes` 不受 `redirect_stdout` 保护**：
   `check_key(verbose=False)` **仍会 `print()`**（`verify_note_quotes.py` 只在 `__main__` 的 JSON 分支包了 stdout）。
   调 `V._json_review()` 时必须自己包一层 `contextlib.redirect_stdout(io.StringIO())`，
   否则 `--json` 输出被逐篇明细污染成一坨非 JSON 文本。

#### ⚠️ 为什么**不**并进 `validate_vault.py`

后者的 WARN 计数是被当健康信号用的（存量全是大 PDF 那几条）；把一项**天天红**的检查塞进去，
会把那个信号淹掉，于是没人再看 WARN。**闸门必须单义 —— 独立脚本，红了就是不准进。**

**首次体检结果（2026-10-07）**：9 个 L3 页**全部不合格** · 103 处来源引用 · PASS 50 / FAIL 53。
集中度：`TQPTC2N2` miss=14（被 6 页引用）；`KHG52E5I`/`UXPJC8VD`/`LB7FP38A`/`ZX245LJK` 各 miss=1（各被 7–8 页引用）。

#### 工作流铁律

```
改 30_Knowledge/ 前 → gate_l3.py 必须绿 → 才动页
红了 → 先 folio_repair_quotes 修可修的 → 剩下的回 L2 逐条核 → 复检绿了再写
```

> 闸门红了**不是**「顺手把 L3 页改掉」的理由 —— 红了就是**不准改**，先回去把来源那一侧弄干净。

### 跨端同步（坚果云官方插件 `nutstore-sync`，2026-09-17 实测）

| 事实 | 结论 |
|---|---|
| 自带 glob 实现（不是 micromatch） | `**`→`.*`（跨 `/`）；`*`→`[^/]*`（**不跨** `/`）；**逐级祖先目录**依次测试、**最后命中者生效** |
| `configDirSyncMode` 默认 `none` | **`.obsidian` 整目录自动排除**（`O6()` 会追加该规则），还会硬编码排掉 `workspace`/`workspace.json`/`plugins/**/node_modules`/`plugins/nutstore-sync/{cache,data.local.json}` |
| 只在加载时读一次 `data.json` | **手改配置后必须重启 Obsidian 才生效**；重启前打开设置面板会用旧配置覆盖回去 |
| `syncPolicy` 存 `data.local.json`（设备级、不同步） | 默认 `two-way`。**含「覆盖 / 还原」的策略会删另一端文件，别选** |
| 插件自身文件夹不同步 | 换机**不能直接可用**：要重装插件 + 重登录（SSO）+ 重设 `remoteDir` + 重加规则 |

**排除规则的正确粒度**——**别整目录排 `90_Meta/State`**：
它同时装着**账本（`变更记录.md`）**、方案文档与全部流水线脚本（`.py`），
这些恰恰是换机后最需要的。**只排 `.json`，留下 `.md` 与 `.py`**（代价仅 0.5 MB）。

```
90_Meta/Sources          # 第三方源 CSV，重下即可
90_Meta/State/*.json     # 批次中间数据，每跑一次就变 → 同步只会制造冲突副本
.agents                  # 插件自带 AI 的会话状态，本机性质
```

**⚠️ 排查体积时先看「单个大文件」，别只看目录总量。** 本轮「`90_Meta/State` 有 19 MB 批次数据」
这个说法**一直是错的**：真正元凶是一张 **14.7 MB 的临时截图**（占 78%），批次 JSON 只有 3.6 MB。
**一个从没被质疑过的数字，掩盖了一个占 78% 的垃圾文件。**

### 2026-09-18 建 `~/TeachingAI_Vault/`（教学 × AI）时新增的坑

- **⛔ RIS 导入 Zotero 会全员带上「前导 `- `」。** `/connector/import` 导入后
  title/期刊/年份/作者/摘要**全部**被加了 `- `（translator 取值起点偏移一个字符）。
  实测全库 623 条里 **172 条**中招，**其中 22 条是此前批次留下的历史遗留**——
  说明这个缺陷一直在，只是没人扫过全库。**导入后必须扫一遍 `title.startswith('- ')`。**
  修复脚本：`~/TeachingAI_Vault/90_Meta/State/fix_zotero_dash.py`（默认 dry-run，`--apply` 才写，重跑须「待修 0 条」）。
- **⛔ Consensus 的作者名格式不统一，不能盲目交换姓/名。** 既有 "Yizhou, Fan"（名, 姓）
  也有 "Wu, Rong"（姓, 名），一律按「姓, 名」解析会**把本来就正确的改错**。
  判据：拿 Europe PMC 的 `first_author` 的姓做锚——Zotero 一作 `lastName` 以该姓开头即正确（不动），
  `firstName` 等于该姓即颠倒（整条交换），两者都不匹配则**不判定**（输出待核清单，别猜）。
  脚本 `fix_author_order.py`；实测 112 条不动 / 19 条交换 / 19 条无 EPMC 记录留待人工。
- **⚠️ 主题词表要防「跨领域同形词」。** 教学 × AI 的分层第一版把 `metacogniti` / `miscalibration` /
  `overconfidence` 当「认知机制词」，结果**机器学习模型校准**文献（影像分割、网络架构）大量混入，
  A 类虚高到 89 篇。修法：同形词下放到弱词表并要求教育场景，另加「必须与 AI 相关」的一票否决前提。
  **通用判据：选主题词前先问「这个词在别的领域是不是也高频」。**
- **⚠️ 给子代理的 brief 里枚举值必须抄模板原文。** 本次 brief 写「进入 L2」而模板/校验器是
  **「进入 L2 精读」** → 12 张卡被判 ERROR。**错在数据侧就改数据，不要放宽校验器。**
- **⚠️ 生成索引表时 `_file` 必须在 `sort()` 之前绑定。** 首版在排序后才 `zip(files, rows)` 补文件名，
  导致明细表**数据与文件名整体错位**（某张卡显示另一篇的元数据）——**数量统计完全看不出来，
  只能靠抽查内容发现。**
