# Folio 连接器 —— WorkBuddy 直连文献工作台

**Folio** 的本义是「对开本 / 摊开的对页」。对它来说就是：把一页纸摊开成两面，左边是你的思考，右边是原文。

装好之后，在 WorkBuddy 对话里可以直接读写你的文献和阅读卡，不用手动导 JSON。

---

## 一、数据是怎么连的

```
┌──────────────┐         ┌──────────────────┐         ┌────────────────┐
│ WorkBuddy AI │  MCP    │ server/mcp.js    │         │ 浏览器里的页面 │
│              │◄───────►│ server/store.js  │  HTTP   │                │
└──────────────┘  stdio  └────────┬─────────┘◄───────►│  app.html      │
                                  │                    └────────────────┘
                            data/folio.json
                       （唯一的真实数据源 + 自动快照）
```

**两边读写同一份文件**，所以：
- AI 建的卡 → 浏览器刷新即可见，且已经锚定好原文位置
- 页面上的笔记改动 → AI 下一次调用立刻能读到

### 离线兜底

| 打开方式 | 行为 |
|---|---|
| `http://127.0.0.1:8787/` | 自动连接，指示器显示「已同步」 |
| 双击 `app.html`（file://） | 默认**不发任何网络请求**，指示器显示「离线 · 点此启用同步」；点一下才会连 |
| 服务没起 | 自动降级为 localStorage，原有功能完全不受影响 |

> file:// 下刻意默认不自动连：服务没起时硬连会让控制台刷一片 `ERR_CONNECTION_REFUSED` 红字。

---

## 二、已注册的配置

`~/.workbuddy/mcp.json` 里已写入：

```json
"folio": {
  "command": "C:\\Users\\xia\\.workbuddy\\binaries\\node\\versions\\22.22.2\\node.exe",
  "args": ["C:\\Users\\xia\\WorkBuddy\\2026-10-04-19-51-30\\文献工作台\\server\\mcp.js"],
  "env": { "FOLIO_PORT": "8787" },
  "disabled": false
}
```

**首次使用前需要在 WorkBuddy 里信任它**：连接器管理页面 → 找到 `folio` → 点「信任」。

> 之前若信任过旧名 `litdesk`，它是另一个条目，建议顺手删掉避免混淆。

MCP 进程由 WorkBuddy 拉起，同时它会在 8787 端口起 HTTP 服务给页面用。若你已经在跑 `start-server.bat`，MCP 会检测到端口占用并复用现有服务。

---

## 三、AI 能用的工具（18 个）

### 读

| 工具 | 用途 |
|---|---|
| `folio_status` | 连接状态与数据概况。**排查「AI 读不到数据」先跑它** |
| `folio_list_papers` | 文献清单（可按关键词/状态过滤） |
| `folio_get_paper` | 元信息 + 正文段落（支持 offset/limit 分段取） |
| `folio_get_text` | 只读正文，精读某一节 |
| `folio_export_markdown` | 导出 Markdown（保留标题层级 + 页码注释） |
| `folio_search` | 全文搜索，返回 paraIdx/start —— 可直接拿去建锚点卡 |
| `folio_list_cards` | 卡片列表（按文献/类型/星标过滤） |
| `folio_get_card` | 单卡完整内容 |
| `folio_today` | 今天要处理（逾期标红项） |

### 写

| 工具 | 用途 |
|---|---|
| `folio_add_card` | 建卡。`quote` 给原文真实句子 → 自动锚定到正文 |
| `folio_import_cards` | **批量建卡**，AI 生成一批卡的主力入口。支持 `dryRun` 先试算命中率 |
| `folio_update_card` | 改笔记/批注/类型/标签/星标 |
| `folio_add_paper` | 新建文献条目，可同时灌入文本自动切段 |
| `folio_update_paper` | 改标题/状态/到期日/标签等 |

### 审查 ResearchVault（引语闸门）

把 ResearchVault 的 L2 笔记与 Folio 卡片送进**同一个判定引擎**（`90_Meta/State/verify_note_quotes.py`）—— 两侧结果因此绝对一致。

| 工具 | 说明 |
|---|---|
| `folio_vault_status` | vault 定位、Python 与闸门脚本是否就绪、笔记/档案数量。**审查类问题先跑它** |
| `folio_review_notes` | 跑全库（或指定 key）引语核验，报「严格命中 / 仅连字符差异 / 未命中」 |
| `folio_review_cards` | 逐卡核验引语：先在该篇正文里定位，未命中再拿 vault 全库复核 |
| `folio_coverage` | **覆盖度审查** —— 笔记里有 N 条引语、Folio 已收 M 条、还差哪几条。防止「以为覆盖了、实际没进」 |

`folio_coverage` 的设计意图：Folio 只收「要点单元」，每个单元一张卡、首条引语用于锚定、其余引语写进 note。所以查询口径是「笔记全部引语 vs 卡片 quote + note 里列出的引语」，判定用脚本的归一化（弯引号 / HTML 实体 / 连字符等价），不做裸字符串比对。

### 删除

**刻意不提供任何删除工具。** 你选的是「读写全开、禁止删除」—— AI 误删阅读积累的代价太高。

---

## 四、典型用法

跟 AI 说：

> 帮我给《XXX》这篇文献生成 8 张阅读卡，按 KT/KM/KR/KV/KS 分类，`quote` 必须是原文里真实存在的句子。

AI 会：
1. `folio_search` / `folio_get_paper` 读正文
2. 生成卡片，每句 quote 都取自原文
3. `folio_import_cards` 一次性写入
4. 返回的 `anchored` 数量告诉你有几张成功锚定 —— **没锚定的说明 quote 是编的或改过，要警惕**

### 让 AI 建卡时最重要的一句话

**`quote` 必须是原文里逐字存在的连续文本。** 这套机制靠 `indexOf` 定位，改一个词就锚不上。AI 若凭印象复述，卡照样建，但 `anchored=false`，页面的「定位原文」按钮不会出现。

推荐做法：先让 AI 用 `folio_search` 或 `folio_get_text` 读到真实原文，再让它生成 quote。

---

## 五、关于改名

产品从 `litdesk` 改名为 `folio` 时，以下几处刻意**保留旧名以免丢数据**：

| 位置 | 现状 | 为什么不改 |
|---|---|---|
| localStorage 键 | `wb_litdesk_*` | 改了浏览器里已有数据会全部读不出来 |
| 环境变量 | `LITDESK_PORT` 仍被识别 | `FOLIO_PORT` 优先，旧名继续兼容 |
| 数据目录变量 | `LITDESK_DATA_DIR` 仍被识别 | 同上 |

数据文件名 `data/litdesk.json` 会在服务首次启动时**自动迁移**为 `data/folio.json`（仅当新文件不存在时执行，绝不覆盖）。

---

## 六、数据安全

**自动快照**：每次写入前留存一份到 `data/backups/`，最多留 20 份，轮转清理。
**原子写入**：先写 `.tmp` 再 rename，不会因为中断写出半截文件。
**损坏隔离**：JSON 解析失败时把坏文件挪到 `data/backups/corrupt-<时间戳>.json`，不会静默清空。
**测试隔离**：设 `FOLIO_DATA_DIR` 可把整个数据目录迁走，测试脚本都用它，不碰你的真实数据。

手动备份仍然是菜单里的「备份 → 导出 JSON」（文件名 `folio-backup_<日期>.json`）。

---

## 七、改端口

默认 8787。要改的话：
- MCP：`mcp.json` 里改 `FOLIO_PORT`
- 常驻服务：设环境变量后再跑 `start-server.bat`
- file:// 打开的页面：地址后面加 `?port=8899`

三者要一致才能连上。

---

## 八、自测

```bash
node tools/selfcheck.js    # 静态约束（render* 调用关系、$('id') 必须在页面存在）
node tools/pdftest.js      # PDF → Markdown：22 项
node tools/runtest.js      # 浏览器运行时：36 项
node tools/conntest.js     # MCP 握手 + 18 工具全调用：46 项
node tools/synctest.js     # 页面 ↔ AI 双向链路：13 项
node tools/importtest.js   # vault 笔记 → Folio 卡片：31 项
```

前五套跑在临时目录里、跑完自动清理。`importtest.js` 只读 vault，测两条硬不变量：

1. **单元切分绝不丢引语** —— 全库逐篇断言 `quotesLost === 0`。这条曾经真实失守过（祖先合并时把子项引语静默丢弃），丢掉的引语既不在任何单元里、也不报错，等于从未被核实。
2. **JS 与 Python 引语口径逐篇一致** —— 两套抽取实现必须抽出同样的条数。口径一旦漂移，Folio 会抽出一批闸门不认（或漏掉闸门认的）引语，两侧结果不一致比没有审查更糟。

A/B/C 组是内置合成样本，**不依赖 vault 是否存在**，所以离开这台机器也能跑，用来锁住已修过的回归（`The LA…` 被误判成参考文献、短引语被字母阈值丢弃等）。
