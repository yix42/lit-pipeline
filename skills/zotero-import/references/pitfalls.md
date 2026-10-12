# Zotero 8 local HTTP API — 实测踩坑与正确用法

本参考固化「把文献导入本地 Zotero 指定集合」这条链路在 macOS + Zotero 8 上的真实行为。
脚本 `scripts/zotero_import.py` 已把这些坑都封装好，这里只记录「为什么」，便于维护与排错。

## 凭据（务必复用，不要重新授权）

- 凭据文件：`~/.workbuddy/zotero_local_auth.json`
  - 字段：`user_id`、`server_id`、`api_key`
- Zotero 其实**早就授权过 WorkBuddy**，key 存放在
  `~/Library/Application Support/Zotero/Profiles/<profile>/localAPIKeys.json`
  （字段 key/appName/remember/createdAt）。**直接读这个文件复用 key**，不要再去
  调 `POST /api/local/authorize` 傻等弹窗（会 15 分钟超时）。
- 每个 `/api/...` 写请求都要带请求头 `Zotero-Server-ID`（值即 `server_id`）与
  `Zotero-API-Key`（值即 `api_key`）。只带 Server-ID 不带 key → `401`；都不带 → `428`。

## 端点与行为（实测）

| 操作 | 端点 | 注意 |
|---|---|---|
| 列出顶层集合 | `GET /api/users/{id}/collections/top?format=json&limit=200` | 用 `.top`，上限可调 |
| 建集合 | `POST /api/users/{id}/collections`，**body 必须是数组** `[{name, parentCollection:false}]` | 传单对象会 `400`；返回 **201 空 body**，key 取不到 → 必须再 `GET` 集合列表按 name 取 key |
| 导入条目 | `POST /connector/import?session=<uuid>&collections=<key>&tags=&items=`，Content-Type `text/plain`，body=RIS | **忽略 `collections=` 参数**！条目落进 Zotero **当前 UI 选中集合**，不是目标集合 |
| 取单条版本 | `GET /api/users/{id}/items/{key}?format=json` | 返回 `version` 字段，移动时做乐观锁 |
| 批量改归属 | `POST /api/users/{id}/items`，body = `[{key, version, collections:[目标key]}, ...]` | 改集合归属只能走这里；`/connector/saveItems` 不支持更新已有条目 |
| 复核集合内容 | `GET /api/users/{id}/collections/{key}/items/top?format=json&limit=200` | 是 `items/top`，**不是** `items.top`（写错会 `404`） |

## 可靠导入流程（脚本已实现）

1. 解析文献（PMID → PubMed efetch 权威元数据；或解析已有 .ris）。
2. `find_or_create_collection(name)`：先列顶层集合按 name 命中则返回 key；否则建集合后**再列一次**取 key（不信任 201 空响应）。
3. `POST /connector/import` 导入（落当前选中集合，忽略 collections 参数）。解析返回 JSON 数组里的 `key` 列表作为导入条目。
4. `move_to_collection`：先逐条 `GET` 取 `version`，再批量 `POST /api/users/{id}/items` 把每条 `collections` 设为目标 key。
5. `GET .../items/top` 复核集合最终条数。

## 批量写入的三条硬约束（2026-09 实测补充）

这三条是在一次 72 篇导入中踩实后确认的，都会静默出错，必须照做。

### 1. `/connector/import` 丢弃 RIS 的 `AN  - ` 字段

RIS 里写 `AN  - 12345678`（PMID）**不会**落到条目的 Extra，`extra` 读回来是 `None`。
后果：导入后想「按 PMID 反查条目」会全部落空，标签/分组随之全错。

正确做法：**自己维护 DOI→PMID、标题→PMID 映射**（用导入时那份 RIS 自己解析，
DOI 在 `DO  - `、PMID 在 `AN  - `），按 DOI 匹配条目（缺 DOI 时回退规范化标题）。
写入后再用 PATCH 把 `extra` 补成 `PMID: xxxxxxxx` 方便日后对账。

### 2. 批量 `POST /api/users/{id}/items` **每批最多 50 条**

超过即 `413 Cannot add more than 50 items at a time`。删除/更新都要 `range(0, n, 50)` 切片。
批量移动通常条目少不会撞到，但**删除去重**时很容易一次几百条，必须分片。

### 3. 批量 POST 会「偏态写入」：`collections` 生效、`tags` 不生效

同一批里传 `{key, version, collections:[...], tags:[{tag:'x'}]}`，
结果 `collections` 写进去了，**`tags` 是空的**；且返回体是
`{"successful":{...},"failed":{...},"unchanged":{...}}`（**dict，不是 list**），
所以 `isinstance(res, list)` 判断会静默跳过、连日志都不打。
`extra` 同样不生效。

可靠做法：**逐条 `PATCH /api/users/{id}/items/{key}`**，body 只放要改的字段
（`version` / `collections` / `tags` / `extra`），成功返回 **204**。
逐条 PATCH 是唯一三字段都落地的写法。

### 4. 导入后不要立刻 PATCH `extra`（会被导入侧覆盖）

实测：刚 `POST /connector/import` 完就逐条 PATCH `extra`，PATCH 返回 204、
当场读回也正确，但**几分钟后 `extra` 又变回 null**——连接器侧的后续写入把它覆盖了。
同一批的 `tags` 却留住了。表现为「标签齐了、PMID 全缺」。

实测规模：第 2 批 25 条全丢、第 3 批 13 条里丢 6 条，无一幸免。

**正确解法：两趟写入（`--finalize` 模式）。**

1. 第一趟：导入 + 逐条 PATCH（`collections` + `tags`，`extra` 也写但**不指望它活下来**）。
2. 等 1–2 分钟让连接器侧写入落定。
3. 第二趟（`--finalize`）：**不导入**，回扫目标集合，按 DOI / 规范化标题找回本批条目，
   只补 `tags` + `extra`。这一步全部生效。

比「一次写完再重跑校验」更省事，也不会重复导入。脚本模板见
`la_analysis/literature/zotero_import/add_batch3.py` 的 `--finalize` 分支。

补完必须重新拉一次集合复核（全文条目 `extra` 以 `PMID:` 开头），不要相信 PATCH 的即时回读。

### 5. 去重时「保留哪一份」要想清楚

批量 PATCH 循环里若用 `by_pmid[pmid] = it` 这种「后者覆盖前者」的写法，
被打了标签的是**后出现的那一份**。此时若顺手删除 `group[1:]`，删掉的正是带标签的副本。
去重前先给每条打分（`是否含来源标签` → `标签数量`），按分数降序保留第一名，删除其余。

### 6. 会议摘要 PubMed 查不到，必须换 CrossRef

HRS / EHRA 年会的增刊摘要（`Heart Rhythm`、`EP Europace` 的 Supplement 期）
**完全不进 PubMed**：按 `"<doi>"[DOI]` 检索 `esearch` 返回空 idlist，
`efetch` 自然什么都取不到。而汇报/综述里引用的往往恰恰是这类摘要（尤其新指标、新命名）。

解决：改用 CrossRef 取权威元数据。

```
GET https://api.crossref.org/works/{urlencoded-doi}
    # 建议带 User-Agent: '<app> (mailto:<email>)'，进入 polite pool
```

- 标题在 `message.title[0]`（会议摘要常带 `PO-xx-xxx` / `AB-xxxxxxx-x` 编号前缀，
  **保留编号**——它本身就是该摘要的引用标识）。
- 作者 `message.author[]` 的 `family` / `given`；卷期 `volume` / `issue` / `page`。
- 年份取 `message.published.date-parts[0][0]`（次选 `issued`）。
- 摘要没有 `abstract` 字段，RIS 里不写 `AB  - ` 即可。
- **会 429 限流**：必须退避重试（`sleep(3*(k+1))`，最多 4–5 次），串行请求间隔 ≥1s。

入库后 `extra` 写 `Meeting abstract (HRS/EHRA supplement) — not indexed in PubMed`，
**不要写 `PMID:`**——否则后续按 `PMID:` 前缀解析会把它当成真 PMID，把统计弄脏。

### 7. 会议摘要最好显式打一个 `会议摘要` 标签

同一课题组的同一项研究常在同一年内投多场会议（HRS + EHRA + 次年再来一轮），
DOI 各不相同，去重机制**不会合并**它们。若不加区分，库里会出现 4–5 条几乎同名的记录，
引用时容易误当成多项独立研究。

做法：打 `会议摘要` 标签 + 一个 `汇报同源系列` 之类的分组标签，
并在索引文档里显式写明「这是同一研究的多场报告，正文引最新最全的那一条」。

## 其他坑

- 本地服务**不支持** `POST /collections/{key}/items`（405）。把条目加进集合必须走「导入后批量更新 `collections` 字段」。
- 按 DOI 的 `items?q=<doi>` 检索在本机不可靠（q 未必索引 DOI）；去重建议按标题匹配或导入后于 Zotero 内用 Duplicates 工具合并。
- `POST /api/users/{id}/items` 传 `{key, version, deleted: 1}` 即可把条目移入回收站；但实测该路径下
  回收站**读不回来**（`GET /items/trash` 返回空），等同硬删除 —— 去重前务必先确认「要删的确实是冗余副本」。
- 无 Better BibTeX(BBT) 时相关 bridge/`create_collection` 辅助不可用，本文档流程不依赖 BBT。
- `/connector/import` 默认落到 UI 当前选中集合；若导入前在 Zotero 里手动选中了目标集合，
  条目可能「恰好」落在目标集合（表现为批量移动返回 `unchanged`）——这不是 bug，复核以最终条数为准。
- `GET /collections/{key}/items/top` 的 `limit` 最大生效 100，超过按 100 返回；
  条目数可能大于 100 时**必须用 `start` 分页**，否则复核数偏小、误判为「导入不全」。
- **脚本没有 `--dry` 参数**：随手加一个未定义的 flag 不会报错也不会阻止执行，
  完整导入会真的跑一遍。要试跑请用 `--dry-run`，或先在小样本上验证。
