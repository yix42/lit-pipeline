/* =====================================================================
   MCP 工具实现 —— 读写全开，禁止删除
   删除类操作刻意不提供：AI 误删阅读积累的代价远高于收益。
   ===================================================================== */
"use strict";
const crypto = require("crypto");
const store = require("./store");
const loc = require("./locate");

const CARD_TYPES = loc.TYPES;

function txt(o) {
  return { content: [{ type: "text", text: typeof o === "string" ? o : JSON.stringify(o, null, 2) }] };
}
function err(msg) {
  return { isError: true, content: [{ type: "text", text: "错误：" + msg }] };
}
function ok(msg) {
  return { content: [{ type: "text", text: msg }] };
}
function needPaper(st, req) {
  const p = req.paperId
    ? st.papers.find((x) => x.id === req.paperId)
    : loc.findPaper(st.papers, req.paper);
  return p || null;
}
function pickPaperHint(st, p) {
  if (p) return p;
  if (st.curPaperId) return st.papers.find((x) => x.id === st.curPaperId) || null;
  return st.papers.length ? st.papers[0] : null;
}
function plusDays(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const p2 = (v) => (v < 10 ? "0" + v : "" + v);
  return d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate());
}

/* ---------------- 工具清单 ---------------- */
const TOOLS = [
  {
    name: "folio_status",
    description: "查看文献工作台的连接状态与数据概况。排查「AI 读不到数据」时先跑这个。",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "folio_list_papers",
    description: "列出全部文献的摘要信息（不含正文）。返回 id、标题、作者、期刊、年份、DOI、状态、到期日、段落数、卡片数。",
    inputSchema: {
      type: "object",
      properties: {
        keyword: { type: "string", description: "按标题/作者/DOI/标签模糊过滤，留空返回全部" },
        status: { type: "string", description: "按状态过滤：待读 / 在读 / 已读", enum: ["待读", "在读", "已读"] },
      },
    },
  },
  {
    name: "folio_get_paper",
    description: "取一篇文献的元信息和正文段落。正文可能很长，用 offset/limit 分段取。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string", description: "文献 id（推荐，来自 folio_list_papers）" },
        paper: { type: "string", description: "文献标题或 DOI，用于按名字查找" },
        includeText: { type: "boolean", description: "是否返回正文段落，默认 false" },
        offset: { type: "integer", description: "段落起始索引，默认 0" },
        limit: { type: "integer", description: "最多返回多少段，默认 40" },
      },
    },
  },
  {
    name: "folio_get_text",
    description: "只取正文原文（按段落范围），用于精读某一节。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string" },
        paper: { type: "string" },
        offset: { type: "integer", description: "默认 0" },
        limit: { type: "integer", description: "默认 30" },
      },
    },
  },
  {
    name: "folio_export_markdown",
    description: "把一篇文献导出为 Markdown（保留 # / ## / ### 标题层级和 <!-- page N --> 页码注释）。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string" },
        paper: { type: "string" },
        markPages: { type: "boolean", description: "是否插入页码注释，默认 true" },
      },
    },
  },
  {
    name: "folio_search",
    description: "跨文献全文搜索关键词。返回命中的文献、段落索引、页码和上下文片段，可直接拿ТЕ去建卡锚点。",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "搜索关键词" },
        paperId: { type: "string", description: "限定在某篇文献内搜索，留空则全局" },
        limit: { type: "integer", description: "最多返回多少条命中，默认 20" },
        context: { type: "integer", description: "命中位置前后各取多少字符做上下文，默认 90" },
      },
      required: ["query"],
    },
  },
  {
    name: "folio_list_cards",
    description: "列出卡片。可按文献、类型、星标过滤。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string" },
        paper: { type: "string" },
        type: { type: "string", enum: CARD_TYPES },
        starOnly: { type: "boolean", description: "只要星标卡" },
        hasNote: { type: "boolean", description: "只要写了笔记的卡" },
      },
    },
  },
  {
    name: "folio_get_card",
    description: "取单张卡片的完整内容（笔记、批注、标签、锚点位置）。",
    inputSchema: {
      type: "object",
      properties: { cardId: { type: "string", description: "卡片 id" } },
      required: ["cardId"],
    },
  },
  {
    name: "folio_add_card",
    description: "新建一张阅读卡。给 quote（原文里的真实句子）会自动在原文中定位并建立锚点，卡片的「定位原文」按钮随后可用。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string" },
        paper: { type: "string", description: "文献标题或 DOI；都不给则落到当前文献" },
        type: { type: "string", enum: CARD_TYPES, description: "KT知识主题/KC核心概念/KM方法要点/KR关键结果/KV证据数据/KS可证伪问题/NT随手批注" },
        quote: { type: "string", description: "原文引句。必须是原文里真实存在的连续文本，建议 30–200 字符" },
        note: { type: "string", description: "笔记正文" },
        comment: { type: "string", description: "批注/待办" },
        tags: { type: "array", items: { type: "string" } },
        star: { type: "boolean" },
        pinned: { type: "boolean" },
      },
      required: ["type"],
    },
  },
  {
    name: "folio_import_cards",
    description: "批量导入阅读卡。给 AI 生成一批卡时用它，一次调用写完，返回每张卡的锚定结果。quote 未命中的卡会照样建卡但无锚点，需要留意。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string" },
        paper: { type: "string", description: "文献标题或 DOI；都不给则落到当前文献" },
        cards: {
          type: "array",
          items: {
            type: "object",
            properties: {
              type: { type: "string", enum: CARD_TYPES },
              quote: { type: "string" },
              note: { type: "string" },
              comment: { type: "string" },
              tags: { type: "array", items: { type: "string" } },
              star: { type: "boolean" },
              pinned: { type: "boolean" },
            },
            required: ["type"],
          },
        },
        dryRun: { type: "boolean", description: "只试算不落盘，用于先确认 quote 能命中多少" },
      },
      required: ["cards"],
    },
  },
  {
    name: "folio_update_card",
    description: "修改已有卡片的笔记、批注、类型、标签、星标、置顶。不给的字段保持原样。",
    inputSchema: {
      type: "object",
      properties: {
        cardId: { type: "string" },
        type: { type: "string", enum: CARD_TYPES },
        quote: { type: "string", description: "改引句会重新定位锚点" },
        note: { type: "string" },
        comment: { type: "string" },
        tags: { type: "array", items: { type: "string" } },
        star: { type: "boolean" },
        pinned: { type: "boolean" },
      },
      required: ["cardId"],
    },
  },
  {
    name: "folio_add_paper",
    description: "新建一条文献条目。可以只给元数据（之后再灌正文），也可以同时给纯文本/Markdown 让它自动切段。",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string" },
        authors: { type: "string" },
        journal: { type: "string" },
        year: { type: "string" },
        doi: { type: "string" },
        tags: { type: "array", items: { type: "string" } },
        status: { type: "string", enum: ["待读", "在读", "已读"] },
        mtype: { type: "string", description: "阅读 focus 类型标记，默认 KC" },
        due: { type: "string", description: "到期日 YYYY-MM-DD" },
        dueInDays: { type: "integer", description: "相对今天的到期天数，与 due 二选一" },
        text: { type: "string", description: "正文纯文本或 Markdown，会自动切段" },
      },
      required: ["title"],
    },
  },
  {
    name: "folio_update_paper",
    description: "修改文献元信息：标题、作者、状态、到期日、标签等。不给的字段保持原样。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string" },
        paper: { type: "string" },
        title: { type: "string" },
        authors: { type: "string" },
        journal: { type: "string" },
        year: { type: "string" },
        doi: { type: "string" },
        tags: { type: "array", items: { type: "string" } },
        status: { type: "string", enum: ["待读", "在读", "已读"] },
        mtype: { type: "string" },
        due: { type: "string" },
        dueInDays: { type: "integer" },
      },
    },
  },
  {
    name: "folio_today",
    description: "查「今天要处理」：逾期文献（标红项）、今日到期、临近到期、还没写笔记的卡片。",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "folio_vault_status",
    description: "查看 ResearchVault 连接状态：vault 路径、L2 笔记数、全文档案数、闸门脚本与 Python 解释器是否就绪。审查功能出问题时先跑它。",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "folio_review_notes",
    description:
      "对 vault 的 L2 精读笔记跑「引语闸门」审查：把笔记里的英文引语逐条拿到 40_Fulltext 全文档案里定位，分三级——" +
      "严格命中 / 仅连字符差异（PDF 转出缺陷）/ 未命中（真问题）。未命中意味着要么笔记改写了原文（AI 反向生成引语的典型症状），" +
      "要么档案转出残缺。判定由 vault 自带的 verify_note_quotes.py 执行，不重写逻辑。",
    inputSchema: {
      type: "object",
      properties: {
        keys: {
          type: "array", items: { type: "string" },
          description: "只查指定的 zotero_key（8 位）。留空则查全库",
        },
        onlyMiss: { type: "boolean", description: "只返回有未命中的篇目明细，默认 true" },
        missPreviewChars: { type: "integer", description: "每条未命中引语的预览长度，默认 160" },
      },
    },
  },
  {
    name: "folio_review_cards",
    description:
      "对 Folio 库里的卡片跑同一条闸门：把卡片的 quote 交给同一个判定引擎（脚本 --quotes-file），" +
      "判定结果与 L2 笔记路径口径完全一致。用于检查 AI 建的卡是否锚得住真实原文。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string", description: "只看某篇文献的卡；留空则全部" },
        onlyMiss: { type: "boolean", description: "只返回未命中项，默认 true" },
      },
    },
  },
  {
    name: "folio_coverage",
    description:
      "覆盖度审查：比对「vault 笔记里应有的引语」与「已收进 Folio 的引语」，报出差集。" +
      "用于回答「是不是还有引语没进 Folio、因而从未被核实」——这是导入面窄时最容易出的问题" +
      "（早期只导入「主要发现」块，技术细节/统计方法等节的引语全部没进去）。" +
      "**归属按 key 收窄**（卡片 sourceKey / 文献标签），并另给一份全库口径作对照：" +
      "两者不一致即说明有卡片没写 sourceKey 或存在跨篇引用。" +
      "归一化由闸门脚本执行，与引语核验同口径。",
    inputSchema: {
      type: "object",
      properties: {
        paperId: { type: "string", description: "文献 id；给了就只比对这篇的卡片" },
        key: { type: "string", description: "vault 的 zotero_key（8 位）。省略时从卡片 sourceKey 或文献标签推断" },
        scope: {
          type: "string", enum: ["key", "all"],
          description: "默认 key＝只算归属这篇的卡片；all＝整个 Folio 库的卡片（对照口径，会高估覆盖）",
        },
        limit: { type: "integer", description: "最多返回多少条未覆盖引语，默认 50" },
        missingPreviewChars: { type: "integer", description: "每条未覆盖引语的预览长度，默认 140" },
      },
    },
  },
  {
    name: "folio_repair_quotes",
    description:
      "引语转录修复：诊断「未命中引语里哪些是笔记漏抄了字形」，并**按 id 逐条**落笔。" +
      "默认只诊断、不改任何文件；只有显式传 apply（要落笔的 id 数组）才会写笔记，" +
      "且落笔前会自动把笔记快照到库外的 ResearchVault_backups/。" +
      "准入极窄：只放行「引号字形还原」与「补回良构 ±」两类；" +
      "档案侧软连字符 / markdown 记号 / 符号污染（± 兼作 < ≈ †）、以及任何会删掉笔记侧字符的改动，一律拒改并给出原因。" +
      "口径：不敢改的留着比改错便宜——留下一条已知未命中，好过把对的改成错的。",
    inputSchema: {
      type: "object",
      properties: {
        keys: {
          type: "array", items: { type: "string" },
          description: "只诊断指定的 zotero_key（8 位）。留空则全库",
        },
        apply: {
          type: "array", items: { type: "string" },
          description:
            "要落笔的 id（来自上一次诊断的 fixable[].id）。**省略即纯诊断，绝不改文件**。" +
            "落笔时会重新诊断一遍再改；id 已失效（笔记被改过）的原样报回 missing。",
        },
        previewChars: { type: "integer", description: "每条引语的预览长度，默认 150" },
        manualPerKey: { type: "integer", description: "诊断时最多列多少条「须人工」明细，默认 20" },
      },
    },
  },
];

/* ---------------- 路由 ---------------- */
async function callTool(name, argsRaw) {
  const a = argsRaw || {};
  const S = require("./store");

  switch (name) {
    /* ---- 状态 ---- */
    case "folio_status": {
      const st = await S.readState();
      const s = S.stats();
      return txt({
        ok: true,
        dataFile: s.file,
        sizeKB: +(s.bytes / 1024).toFixed(1),
        papers: st.papers.length,
        cards: st.cards.length,
        currentPaper: st.curPaperId,
        updatedAt: st.updatedAt,
        note: "数据已连通。页面若在浏览器打开，刷新即可看到 AI 的改动。",
      });
    }

    /* ---- 读：文献 ---- */
    case "folio_list_papers": {
      const st = await S.readState();
      const kw = (a.keyword || "").trim().toLowerCase();
      let list = st.papers;
      if (a.status) list = list.filter((p) => p.status === a.status);
      if (kw) {
        list = list.filter((p) =>
          [p.title, p.authors, p.doi, p.journal, (p.tags || []).join(" ")]
            .join(" ")
            .toLowerCase()
            .includes(kw)
        );
      }
      return txt({
        count: list.length,
        currentPaperId: st.curPaperId,
        papers: list.map((p) => ({
          id: p.id,
          title: p.title,
          authors: p.authors,
          journal: p.journal,
          year: p.year,
          doi: p.doi,
          status: p.status,
          due: p.due,
          tags: p.tags,
          paragraphs: p.paragraphs.length,
          cards: st.cards.filter((c) => c.paperId === p.id).length,
        })),
      });
    }

    case "folio_get_paper":
    case "folio_get_text": {
      const st = await S.readState();
      const p = pickPaperHint(st, needPaper(st, a));
      if (!p) return err("找不到该文献。用 folio_list_papers 看可用的 id。");
      const wantText = name === "folio_get_text" || a.includeText;
      if (!wantText) {
        return txt({
          id: p.id, title: p.title, authors: p.authors, journal: p.journal, year: p.year,
          doi: p.doi, status: p.status, mtype: p.mtype, due: p.due, tags: p.tags,
          source: p.source, totalParagraphs: p.paragraphs.length,
          hint: "要读正文请设 includeText=true，或用 folio_get_text / folio_export_markdown",
        });
      }
      const offset = Number.isInteger(a.offset) && a.offset >= 0 ? a.offset : 0;
      const limitRaw = Number.isInteger(a.limit) && a.limit > 0 ? a.limit : 40;
      const limit = Math.min(limitRaw, 200);
      const slice = p.paragraphs.slice(offset, offset + limit).map((q, i) => ({
        paraIdx: offset + i, page: q.page, type: q.type, text: q.text,
      }));
      return txt({
        id: p.id, title: p.title,
        total: p.paragraphs.length, offset, returned: slice.length,
        truncated: offset + slice.length < p.paragraphs.length,
        paragraphs: slice,
      });
    }

    case "folio_export_markdown": {
      const st = await S.readState();
      const p = pickPaperHint(st, needPaper(st, a));
      if (!p) return err("找不到该文献。");
      const md = loc.paragraphsToMD(p, a.markPages !== false);
      return txt({ id: p.id, title: p.title, chars: md.length, markdown: md });
    }

    /* ---- 读：搜索 ---- */
    case "folio_search": {
      const st = await S.readState();
      const q = String(a.query || "").trim();
      if (q.length < 2) return err("关键词至少 2 个字符。");
      const low = q.toLowerCase();
      const limit = Number.isInteger(a.limit) && a.limit > 0 ? Math.min(a.limit, 60) : 20;
      const ctx = Number.isInteger(a.context) ? Math.min(Math.max(a.context, 0), 300) : 90;
      const norm = (s) => s.replace(/\s+/g, " ");
      const hits = [];
      const pool = a.paperId ? st.papers.filter((p) => p.id === a.paperId) : st.papers;
      for (const p of pool) {
        if (hits.length >= limit) break;
        for (let pi = 0; pi < p.paragraphs.length; pi++) {
          if (hits.length >= limit) break;
          const t = norm(p.paragraphs[pi].text || "");
          let at = t.toLowerCase().indexOf(low);
          while (at >= 0) {
            const from = Math.max(0, at - ctx);
            const to = Math.min(t.length, at + q.length + ctx);
            hits.push({
              paperId: p.id, paperTitle: p.title,
              paraIdx: pi, page: p.paragraphs[pi].page,
              start: at, end: at + q.length,
              context: (from > 0 ? "…" : "") + t.slice(from, to) + (to < t.length ? "…" : ""),
            });
            break; // 每段只取首个命中，避免长段刷屏
          }
        }
      }
      return txt({ query: q, count: hits.length, hits });
    }

    /* ---- 读：卡片 ---- */
    case "folio_list_cards": {
      const st = await S.readState();
      let pool = st.cards;
      const p = a.paperId || a.paper ? needPaper(st, a) : null;
      if (a.paperId || a.paper) {
        if (!p) return err("找不到该文献。");
        pool = pool.filter((c) => c.paperId === p.id);
      }
      if (a.type) pool = pool.filter((c) => c.type === a.type);
      if (a.starOnly) pool = pool.filter((c) => c.star);
      if (a.hasNote) pool = pool.filter((c) => String(c.note || "").trim());
      return txt({
        count: pool.length,
        cards: pool.map((c) => {
          const pp = st.papers.find((x) => x.id === c.paperId);
          return Object.assign(loc.cardBrief(c), { paperTitle: pp ? pp.title : "" });
        }),
      });
    }

    case "folio_get_card": {
      const st = await S.readState();
      const c = st.cards.find((x) => x.id === a.cardId);
      if (!c) return err("找不到该卡片。");
      const p = st.papers.find((x) => x.id === c.paperId);
      const res = Object.assign(loc.cardBrief(c), { paperTitle: p ? p.title : "" });
      if (p && Number.isInteger(c.paraIdx) && p.paragraphs[c.paraIdx]) {
        res.anchoredPage = p.paragraphs[c.paraIdx].page;
        res.anchoredText = p.paragraphs[c.paraIdx].text;
      }
      return txt(res);
    }

    /* ---- 写：卡片 ---- */
    case "folio_add_card": {
      if (!CARD_TYPES.includes(a.type)) return err("type 必须是 " + CARD_TYPES.join("/") + " 之一。");
      const r = await S.mutate((st) => {
        const p = pickPaperHint(st, needPaper(st, a));
        if (!p) return { __no: true, reason: "找不到目标文献，且工作台里目前没有任何文献。" };
        const anchor = loc.locateQuoteIn(p, a.quote);
        const card = {
          id: "c-" + crypto.randomUUID(),
          paperId: p.id,
          type: a.type,
          quote: String(a.quote || ""),
          note: String(a.note || ""),
          comment: String(a.comment || ""),
          tags: Array.isArray(a.tags) ? a.tags.map(String) : [],
          star: !!a.star,
          pinned: !!a.pinned,
          paraIdx: anchor ? anchor.paraIdx : null,
          start: anchor ? anchor.start : null,
          end: anchor ? anchor.end : null,
          createdAt: S.nowStr(),
        };
        st.cards.push(card);
        st.__report = {
          cardId: card.id, paperId: p.id, paperTitle: p.title,
          anchored: !!anchor,
          anchor: anchor ? { paraIdx: anchor.paraIdx, start: anchor.start, end: anchor.end } : null,
          page: anchor ? p.paragraphs[anchor.paraIdx].page : null,
        };
        return st;
      });
      const m = r.meta || {};
      if (m.aborted) return err(m.reason || "操作中止");
      return txt(m.report || { ok: true });
    }

    case "folio_import_cards": {
      const list = Array.isArray(a.cards) ? a.cards : [];
      if (!list.length) return err("cards 数组为空。");
      const badType = list.find((c) => !CARD_TYPES.includes(c.type));
      if (badType) return err("存在非法 type：" + badType.type + "。可用：" + CARD_TYPES.join("/"));

      const r = await S.mutate((st) => {
        const p = pickPaperHint(st, needPaper(st, a));
        if (!p) return { __no: true, reason: "找不到目标文献，且工作台里目前没有任何文献。" };
        const report = [];
        list.forEach((raw) => {
          const anchor = loc.locateQuoteIn(p, raw.quote);
          report.push({
            type: raw.type,
            quote: String(raw.quote || "").slice(0, 60),
            anchored: !!anchor,
            paraIdx: anchor ? anchor.paraIdx : null,
            page: anchor ? p.paragraphs[anchor.paraIdx].page : null,
          });
          if (a.dryRun) return;
          st.cards.push({
            id: "c-" + crypto.randomUUID(),
            paperId: p.id,
            type: raw.type,
            quote: String(raw.quote || ""),
            note: String(raw.note || ""),
            comment: String(raw.comment || ""),
            tags: Array.isArray(raw.tags) ? raw.tags.map(String) : [],
            star: !!raw.star,
            pinned: !!raw.pinned,
            paraIdx: anchor ? anchor.paraIdx : null,
            start: anchor ? anchor.start : null,
            end: anchor ? anchor.end : null,
            createdAt: S.nowStr(),
          });
        });
        st.__report = {
          paperId: p.id, paperTitle: p.title, dryRun: !!a.dryRun,
          requested: list.length,
          anchored: report.filter((x) => x.anchored).length,
          unanchored: report.filter((x) => !x.anchored).length,
          items: a.dryRun ? report : report.filter((x) => !x.anchored),
        };
        return st;
      });
      const m = r.meta || {};
      if (m.aborted) return err(m.reason || "操作中止");
      return txt(m.report || { ok: true });
    }

    case "folio_update_card": {
      const patch = {};
      ["type", "quote", "note", "comment", "tags", "star", "pinned"].forEach((k) => {
        if (a[k] !== undefined) patch[k] = a[k];
      });
      if (a.type !== undefined && !CARD_TYPES.includes(a.type)) {
        return err("type 必须是 " + CARD_TYPES.join("/") + " 之一。");
      }
      if (!Object.keys(patch).length) return err("没有要改的字段。");

      const r = await S.mutate((st) => {
        const c = st.cards.find((x) => x.id === a.cardId);
        if (!c) return { __no: true, reason: "找不到卡片 " + a.cardId };
        Object.keys(patch).forEach((k) => { c[k] = patch[k]; });
        if (a.type !== undefined) c.type = a.type;
        if (Array.isArray(a.tags)) c.tags = a.tags.map(String);
        if (a.quote !== undefined) {
          const p = st.papers.find((x) => x.id === c.paperId);
          const an = loc.locateQuoteIn(p, c.quote);
          c.paraIdx = an ? an.paraIdx : null;
          c.start = an ? an.start : null;
          c.end = an ? an.end : null;
        }
        st.__report = Object.assign(loc.cardBrief(c), { updated: true });
        return st;
      });
      const m = r.meta || {};
      if (m.aborted) return err(m.reason || "操作中止");
      return txt(m.report || { ok: true });
    }

    /* ---- 写：文献 ---- */
    case "folio_add_paper": {
      const title = String(a.title || "").trim();
      if (!title) return err("title 必填。");
      const r = await S.mutate((st) => {
        const existing = loc.findPaper(st.papers, a.doi) || null;
        if (existing && a.doi) return { __no: true, reason: "DOI 已存在：" + title };
        const p = {
          id: "p-" + crypto.randomUUID(),
          title,
          authors: String(a.authors || "").trim(),
          journal: String(a.journal || "").trim(),
          year: String(a.year || "").trim(),
          doi: String(a.doi || "").trim(),
          tags: Array.isArray(a.tags) ? a.tags.map(String) : [],
          status: ["待读", "在读", "已读"].includes(a.status) ? a.status : "待读",
          mtype: typeof a.mtype === "string" ? a.mtype : "KC",
          due: a.due ? String(a.due) : Number.isInteger(a.dueInDays) ? plusDays(a.dueInDays) : "",
          createdAt: S.nowStr(),
          source: "AI 导入",
          paragraphs: loc.textToParagraphs(a.text, 1),
        };
        st.papers.push(p);
        st.curPaperId = p.id;
        st.__report = { ok: true, paperId: p.id, title: p.title, paragraphs: p.paragraphs.length, isCurrent: true };
        return st;
      });
      const m = r.meta || {};
      if (m.aborted) return err(m.reason || "操作中止");
      return txt(m.report || { ok: true });
    }

    case "folio_update_paper": {
      const r = await S.mutate((st) => {
        const p = pickPaperHint(st, needPaper(st, a));
        if (!p) return { __no: true, reason: "找不到目标文献。" };
        ["title", "authors", "journal", "year", "doi", "status", "mtype"].forEach((k) => {
          if (a[k] !== undefined) p[k] = String(a[k]);
        });
        if (Array.isArray(a.tags)) p.tags = a.tags.map(String);
        if (a.due !== undefined) p.due = String(a.due);
        if (Number.isInteger(a.dueInDays)) p.due = plusDays(a.dueInDays);
        st.__report = {
          ok: true, paperId: p.id, title: p.title, status: p.status,
          due: p.due, tags: p.tags, markedRead: p.status === "已读",
        };
        return st;
      });
      const m = r.meta || {};
      if (m.aborted) return err(m.reason || "操作中止");
      return txt(m.report || { ok: true });
    }

    /* ---- 今天要处理 ---- */
    case "folio_today": {
      const st = await S.readState();
      const today = S.todayStr();
      const dayDiff = (a1, b1) =>
        Math.round((new Date(b1 + "T00:00:00") - new Date(a1 + "T00:00:00")) / 86400000);
      const items = [];
      st.papers.forEach((p) => {
        if (p.status === "已读" || !p.due) return;
        const d = dayDiff(today, p.due);
        if (d > 7) return;
        items.push({
          kind: "paper", id: p.id, title: p.title,
          overdue: d < 0, days: d,
          when: d < 0 ? "已逾期 " + -d + " 天" : d === 0 ? "今天到期" : d + " 天后到期",
          status: p.status, due: p.due,
        });
      });
      const noNote = st.cards.filter((c) => !String(c.note || "").trim());
      if (noNote.length) {
        const byPaper = {};
        noNote.forEach((c) => { byPaper[c.paperId] = (byPaper[c.paperId] || 0) + 1; });
        Object.keys(byPaper).forEach((pid) => {
          const p = st.papers.find((x) => x.id === pid);
          items.push({
            kind: "empty-note", id: pid, title: (p ? p.title : "(未知文献)") + "：还有 " + byPaper[pid] + " 张卡没写笔记",
            overdue: false, days: 99, when: "空笔记的卡片等于没读",
          });
        });
      }
      items.sort((x, y) => (x.overdue !== y.overdue ? (x.overdue ? -1 : 1) : x.days - y.days));
      return txt({ today, count: items.length, items });
    }

    /* ---- ResearchVault 引语闸门审查 ---- */
    case "folio_vault_status": {
      const v = require("./vault");
      const i = v.info();
      if (!i.ok) return err(i.hint || "vault 未找到");
      return txt({
        vault: i.vault,
        notesCount: i.notesCount,
        fulltextCount: i.fulltextCount,
        script: i.script,
        scriptExists: i.scriptExists,
        repairScript: i.repairScript,
        repairScriptExists: i.repairScriptExists,
        python: i.python,
        ready: i.ready,
        note: i.ready
          ? "闸门可用。跑 folio_review_notes 做审查。" +
            (i.repairScriptExists ? "跑 folio_repair_quotes 做引语字形修复的诊断。"
                                  : "（修复脚本不在：folio_repair_quotes 不可用）")
          : "闸门不可用 —— 检查 scriptExists / python 两项。",
      });
    }

    case "folio_review_notes": {
      const v = require("./vault");
      const st = v.info();
      if (!st.ok) return err(st.hint || "vault 未找到，请设 FOLIO_VAULT_DIR 环境变量");
      if (!st.ready) {
        return err(
          "闸门不可用：scriptExists=" + st.scriptExists + "，python=" + st.python +
          "。用 folio_vault_status 看详情。"
        );
      }
      const r = v.reviewNotes(a.keys);
      if (!r.ok) return err("审查失败：" + (r.message || r.error) + (r.stderr ? " | " + r.stderr : ""));

      const cut = Number.isInteger(a.missPreviewChars) ? a.missPreviewChars : 160;
      const preview = (s) => String(s || "").replace(/\s+/g, " ").slice(0, cut);
      const onlyMiss = a.onlyMiss !== false;

      const out = {
        vault: r.vault,
        cached: !!r.cached,
        notesChecked: r.keys,
        totals: r.totals,
        report: r.report || null,        // 已归档的报告（90_Meta/State/_review/引语闸门_<日期>.md）
        perNote: (r.results || []).length,
        notesWithMiss: (r.bad || []).length,
        skipNote:
          "另有 " + (r.skipped ? r.skipped.count : 0) +
          " 条候选未纳入核验（含中文或字母占比 ≤" + (r.latin_min || 0.35) +
          "）—— 这不等于「全部已核验」，别把 0 未命中读成全覆盖。",
      };
      if (r.errors && r.errors.length) out.readErrors = r.errors;

      out.byMiss = (r.byMiss || []).map((x) => ({
        key: x.key,
        miss: x.miss,
        total: x.total,
        misses: onlyMiss ? x.misses.map(preview) : undefined,
      }));
      if (!onlyMiss) {
        out.allNotes = (r.results || []).map((x) => ({
          key: x.key, total: x.total, strict: x.strict, loose: x.loose,
          cross: x.cross, miss: x.miss,
        }));
      }
      return txt(out);
    }

    case "folio_review_cards": {
      const v = require("./vault");
      const st = v.info();
      if (!st.ok) return err(st.hint || "vault 未找到，请设 FOLIO_VAULT_DIR 环境变量");
      if (!st.ready) return err("闸门不可用：scriptExists=" + st.scriptExists + "，python=" + st.python);

      const all = await S.readState();
      let pool = all.cards;
      if (a.paperId) {
        const p = all.papers.find((x) => x.id === a.paperId);
        if (!p) return err("找不到文献 " + a.paperId);
        pool = pool.filter((c) => c.paperId === p.id);
      }
      // 与笔记路径口径一致：只送英文引语（含中文或过短的由脚本自己判 skip）
      const items = pool
        .filter((c) => String(c.quote || "").trim())
        .map((c) => ({ id: c.id, quote: c.quote, label: c.type + " / " + (c.paperId || "").slice(0, 12) }));

      if (!items.length) {
        return txt({ ok: true, cardsChecked: 0, note: "没有带 quote 的卡片可供审查。" });
      }

      /* 第一轮：以 Folio 自己的正文为语料。
         卡片的原文在 Folio 的 paragraphs 里、不在 vault 档案中 ——
         若直接用 vault 语料判定，非 vault 来源的文献会被整批误判为未命中。 */
      const corpus = {};
      all.papers.forEach((pp) => {
        corpus[pp.id] = (pp.paragraphs || []).map((x) => x.text).join("\n\n");
      });
      const r1 = v.reviewQuotes(items, corpus);
      if (!r1.ok) return err("审查失败：" + (r1.message || r1.error) + (r1.stderr ? " | " + r1.stderr : ""));

      /* 第二轮：第一轮未命中的，再用 vault 全库档案复核一次
         —— 卡片引用 vault 里另一篇文献的原文是合法的（跨篇引用）。 */
      const missIds = new Set();
      (r1.items || []).forEach((it) => {
        if ((it.segments || []).some((s) => s.level === "miss")) missIds.add(it.id);
      });
      const r2map = {};
      if (missIds.size) {
        const rr = v.reviewQuotes(items.filter((x) => missIds.has(x.id)));
        if (rr.ok) (rr.items || []).forEach((it) => { r2map[it.id] = it; });
      }

      const byId = {};
      pool.forEach((c) => { byId[c.id] = c; });
      const onlyMiss = a.onlyMiss !== false;

      const rows = (r1.items || []).map((it) => {
        const c = byId[it.id] || {};
        const alt = r2map[it.id];
        // 两轮用同一套切分逻辑，故按索引对齐是安全的
        const segments = (it.segments || []).map((s, i) => {
          if (s.level !== "miss") return { level: s.level, where: s.where, text: s.seg, corpus: "folio" };
          const a2 = alt && (alt.segments || [])[i];
          if (a2 && a2.level !== "miss") {
            return { level: a2.level, where: a2.where, text: s.seg, corpus: "vault" };
          }
          return { level: "miss", where: null, text: s.seg, corpus: null };
        });
        const levels = segments.map((x) => x.level);
        const worst = levels.includes("miss") ? "miss"
          : levels.includes("loose") ? "loose"
          : levels.includes("strict") ? "strict" : "skip";
        return {
          cardId: it.id,
          type: c.type,
          paperId: c.paperId,
          anchored: Number.isInteger(c.paraIdx),
          level: worst,
          segments: segments.map((x) =>
            Object.assign({}, x, { text: String(x.text || "").slice(0, 140) })),
        };
      });

      // 合并后重新汇总（不能直接用第一轮的 totals）
      const tally = { total: 0, strict: 0, loose: 0, miss: 0 };
      rows.forEach((r) => r.segments.forEach((s) => { if (tally[s.level] !== undefined) tally[s.level]++; }));
      tally.total = tally.strict + tally.loose + tally.miss;

      const shown = onlyMiss ? rows.filter((x) => x.level === "miss" || x.level === "loose") : rows;
      return txt({
        cardsChecked: rows.length,
        corpus: "Folio 正文优先，未命中项再用 vault 档案复核",
        totals: tally,
        missCards: rows.filter((x) => x.level === "miss").length,
        looseCards: rows.filter((x) => x.level === "loose").length,
        detail: shown,
      });
    }

    /* ---- 覆盖度审查：笔记引语 vs Folio 卡片 ---- */
    case "folio_coverage": {
      const v = require("./vault");
      const st = v.info();
      if (!st.ok) return err(st.hint || "vault 未找到，请设 FOLIO_VAULT_DIR 环境变量");
      if (!st.ready) return err("闸门不可用：scriptExists=" + st.scriptExists + "，python=" + st.python);

      const all = await S.readState();
      let key = a.key ? String(a.key).trim().toUpperCase() : null;

      if (a.paperId) {
        const p = all.papers.find((x) => x.id === a.paperId);
        if (!p) return err("找不到文献 " + a.paperId);
        if (!key) {
          // 先看卡片上的 sourceKey（按 vault 方式导入时写入的）
          const c0 = all.cards.find((c) => c.paperId === p.id && c.sourceKey);
          if (c0) key = c0.sourceKey;
          else {
            // 退一步：文献标签里找 8 位 zotero_key（旧版导入会把它写进 tags）
            const t = (p.tags || []).find((x) => /^[A-Z0-9]{8}$/.test(String(x)));
            if (t) key = String(t);
          }
        }
      }
      if (!key) {
        return err("无法确定 vault key。请显式传 key，或先用 _import_note.js 方式导入该文献（会写入 sourceKey）。");
      }

      /* ★ 按 key 收窄（2026-10-07 修）。
         此前 pool = all.cards（**整个 Folio 库的卡片**），后果：
         「这篇笔记的引语进 Folio 了吗」被拿别的论文的卡片来回答 ——
         某篇的引语若合法地出现在**别篇**的卡里，会被**少报成缺失**（假阴性），
         反过来别篇卡里恰好有同句时，又会把「没进」误报成「进了」（假阳性）。
         归属判据两条并用：① 卡片自己的 sourceKey；② 该文献 tags 里带这个 key。
         scope:"all" 可退回全库口径（只作对照，不是主判据）。 */
      const isMine = (c) => {
        if (String(c.sourceKey || "").toUpperCase() === key) return true;
        const p = all.papers.find((x) => x.id === c.paperId);
        return !!(p && (p.tags || []).some((t) => String(t).toUpperCase() === key));
      };
      const wide = a.scope === "all";
      const pool = wide ? all.cards : all.cards.filter(isMine);

      /* have = 「已进入 Folio 的引语」。不能只取 card.quote ——
         一个要点单元可能含多条引语，首条用于锚定，其余逐条写在 note 里
         （且都过了闸门）。只取 quote 会把它们误报成「未覆盖」。
         把 note 一并纳入：判定是「归一化后互为子串」，note 里的引语是原文截断，
         仍能命中原引语。 */
      const harvest = (cards) => {
        const out = [];
        cards.forEach((c) => {
          if (String(c.quote || "").trim()) out.push(c.quote);
          if (String(c.note || "").trim()) out.push(c.note);
        });
        return out;
      };
      const r = v.coverage(key, harvest(pool));
      if (!r.ok) {
        return err("覆盖度检查失败：" + (r.message || r.error) + (r.stderr ? " | " + r.stderr : ""));
      }

      /* 同一条判据再跑一次「全库口径」，只作对照：
         两者不同时就说明有卡片归错了 key（或存在合法的跨篇引用），这是要紧的信号。 */
      let anywhere = null;
      if (!wide) {
        const r2 = v.coverage(key, harvest(all.cards));
        if (r2.ok) anywhere = { cards: all.cards.length, covered: r2.covered, missingCount: r2.missingCount };
      }

      const cut = Number.isInteger(a.missingPreviewChars) ? a.missingPreviewChars : 140;
      const lim = Number.isInteger(a.limit) ? a.limit : 50;
      const out = {
        vaultKey: r.key,
        scope: wide ? "全库卡片（对照口径）" : "按 key 收窄",
        noteTotal: r.noteTotal,          // 笔记里应有的引语数
        cards: pool.length,              // 属于这篇 key 的卡片数
        covered: r.covered,              // 已被覆盖的引语数
        missingCount: r.missingCount,
        verdict: r.missingCount === 0
          ? "笔记里的 " + r.noteTotal + " 条引语已全部进入 Folio 并被核实"
          : "还有 " + r.missingCount + " 条引语没进 Folio —— 这些从未被核实",
        missing: (r.missing || []).slice(0, lim)
          .map((x) => String(x).replace(/\s+/g, " ").slice(0, cut)),
      };
      if (anywhere) {
        out.anywhereInLibrary = anywhere;
        if (anywhere.covered !== r.covered) {
          out.scopeNote =
            "两种口径不一致（收窄 " + r.covered + " vs 全库 " + anywhere.covered + "）：" +
            "差额来自「引语出现在别篇的卡片里」。可能是合法的跨篇引用，也可能是卡片没写 sourceKey —— " +
            "前者无需处理，后者建议重导入该篇以补上 sourceKey。";
        }
      }
      if (!wide && pool.length === 0) {
        out.warn = "按 key「" + key + "」找不到任何归属卡片 —— 该篇可能还没导入 Folio（或导入时没写 sourceKey）。";
      }
      return txt(out);
    }

    /* ---- 引语修复：诊断 → 逐条确认 → 才落笔 ---- */
    case "folio_repair_quotes": {
      const v = require("./vault");
      const st = v.info();
      if (!st.ok) return err(st.hint || "vault 未找到，请设 FOLIO_VAULT_DIR 环境变量");
      if (!st.repairScriptExists) return err("修复脚本不在：" + st.repairScript);

      const cut = Number.isInteger(a.previewChars) ? a.previewChars : 150;
      const preview = (s) => String(s || "").replace(/\s+/g, " ").slice(0, cut);
      const ids = Array.isArray(a.apply) ? a.apply.map(String).filter(Boolean) : [];

      const d = v.repairDiagnose(a.keys);
      if (!d.ok) return err("诊断失败：" + (d.message || d.error) + (d.stderr ? " | " + d.stderr : ""));

      const out = {
        vault: d.vault,
        notesChecked: d.checked,
        summary: d.summary,                          // 归因分桶，一眼看清「是笔记在编还是档案残了」
        fixableCount: (d.fixable || []).length,
        manualCount: (d.manual || []).length,
        fixable: (d.fixable || []).map((x) => ({
          id: x.id, key: x.key, noteFile: x.noteFile, ratio: x.ratio,
          before: preview(x.before), after: preview(x.after),
        })),
      };

      if (!ids.length) {
        const cap = Number.isInteger(a.manualPerKey) ? a.manualPerKey : 20;
        out.applied = null;
        out.manual = (d.manual || []).slice(0, cap).map((x) => ({
          key: x.key, why: x.why, quote: preview(x.quote),
        }));
        if ((d.manual || []).length > cap) out.manualTruncated = (d.manual || []).length - cap;
        out.howToApply = out.fixableCount
          ? "确认无误后，用 folio_repair_quotes 传 apply: [上面某个 id, ...] 落笔 —— 只传你认可的那几条。"
          : "没有可自动修的条目。其余未命中已在 summary 里归因，须人工判（改笔记 或 修档案）。";
        return txt(out);
      }

      /* ---- 落笔：只改点名的 id；脚本会重新诊断一遍，过期 id 不会被误改 ---- */
      const r = v.repairApply(ids, a.keys);
      if (!r.ok) return err("落笔失败：" + (r.message || r.error) + (r.stderr ? " | " + r.stderr : ""));
      out.applied = (r.applied || []).map((x) => ({
        id: x.id, key: x.key, noteFile: x.noteFile,
        before: preview(x.before), after: preview(x.after),
      }));
      out.missingIds = r.missing || [];
      out.backup = r.backup || null;                 // 库外快照目录
      if (out.missingIds.length) {
        out.missingNote = "这些 id 已失效（多半是笔记被改过），未落笔 —— 重新诊断取新 id。";
      }

      /* 复测：改了之后到底好没好，用同一条闸门给证据（不落归档报告，免得覆盖全库报告） */
      const changed = Array.from(new Set((r.applied || []).map((x) => x.key)));
      if (changed.length) {
        const g = v.reviewNotes(changed, { noReport: true });
        if (g.ok) {
          out.recheck = (g.results || []).map((x) => ({
            key: x.key, total: x.total, strict: x.strict, loose: x.loose, miss: x.miss,
          }));
          out.recheckNote = "落笔后同一条闸门的复测结果；每次落笔都应让 miss 下降。";
        } else {
          out.recheckError = g.message || g.error;
        }
      }
      return txt(out);
    }

    default:
      return err("未知工具：" + name);
  }
}

module.exports = { TOOLS, callTool };
