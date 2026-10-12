# lit-fusion 集成要点与踩坑

## 1. 两库定位差异（决定用法）

| 维度 | PubMed (eutils) | Consensus (REST) |
|---|---|---|
| 覆盖范围 | 同行评议 MEDLINE 索引 | 2.2 亿篇，含 Scopus / arXiv / preprint |
| 元数据完整性 | 完整（PMID/DOI/年/期刊/Mesh） | 标题/作者/摘要/URL/引用数可靠；**年/期刊字段常为空** |
| 质量信号 | 有（期刊/PMID 可追溯） | `citation_count` 引用数（PubMed 不直接给） |
| AI 综合 | 无 | 有（适合假设论证、扫盲） |
| 配额 | 无（注意 ≤3 req/s） | 免费档 30 次/月 |

## 2. 去重合并策略

- **主键**：DOI（小写归一化）。两库都带 DOI 时最可靠。
- **次键**：标题归一化 —— 小写、去换行/多余空格、去所有非 `[a-z0-9]` 字符后比较。
- **三类划分**：
  - `both`：Consensus 条目能在 PubMed 命中（DOI 或标题）→ 交叉印证。
  - `pm_only`：PubMed 有、Consensus 无 → 临床索引，但可能 Consensus 未覆盖（如很新的文章）。
  - `con_only`：Consensus 有、PubMed 无 → 盲区补漏（preprint/Scopus/工程/非英文），**最大增量**。
- 注意：Consensus 标题偶有换行或多余空格，先 `replace("\n"," ").strip()` 再归一化。

## 3. 配额与节流

- Consensus 免费档 **30 次/月**。每项 `fusion.py` 调用消耗 1 次（不论返回条数）。
- 省额度策略：`--pubmed-only` 做日常精确检索；仅在「假设论证/盲区扫描」关键节点用 Consensus。
- PubMed eutils：请求间 `sleep(0.34)` 避免超速；esearch 与 efetch 分开。

## 4. 与既有 skill 的协作闭环

```
fusion.py  --import-to <集合>  ──►  zotero-import (建集合 + 批量移动)
        │
        └─► 报告 .md ──► md-to-docx (转 Word 发出)
```

- `zotero-import` 脚本路径：`~/.workbuddy/skills/zotero-import/scripts/zotero_import.py`
  - 接收 `--ris` 直接导入；已封装「`/connector/import` 忽略 collections 参数 → 导入后批量 POST 移动」的本地 API 踩坑。
- `md-to-docx`：将报告转中文友好 Word（宋体 + 深蓝标题 + 表格）。

## 5. 已知限制

- Consensus 返回的年/期刊字段不可靠，报告如实呈现空白，不要自行填充。
- 去重基于标题/DOI 字符串匹配，极个别同名不同文（如评论/勘误）可能误合并；人工复核报告「两库共有」列表即可。
- 不自动判断相关性/质量，仅提供引用数排序与交叉印证标记，最终筛选交给用户（符合「先方法讨论、再行动」的工作流）。
