/* =====================================================================
   定位逻辑 —— 必须与 js/app.js 的 locateQuote() 保持一致
   卡片锚点 {paraIdx, start, end} 靠它在原文里找到位置。
   前端和 Node 侧各有一份：前端用于即时 UI 反馈，
   Node 侧用于 AI 建卡时自动锚定，两边算出来的结果必须能对上。
   ===================================================================== */
"use strict";

const TYPES = ["KT", "KC", "KM", "KR", "KV", "KS", "NT"];

/* ---------------- 归一化（必须与闸门 verify_note_quotes.py 口径对齐） ----------------
   为什么需要：原文档案从 XML/HTML/PDF 三种通道转出，同一句话的差异几乎都在排版层 ——
     `&lt;` / `<` ｜ `’` / `'` ｜ `–` / `-` ｜ 软换行 ｜ 全角
   闸门脚本把这些差异全部归一掉后才比对，所以它能判定「命中」。
   而本函数原先只折叠空白，于是含 `&lt;50 ms` 的引语在闸门里命中、在 Folio 里却锚不上 ——
   两边口径不一致会让「闸门说没问题、页面却跳不过去」。

   与 python 端的差别：这里必须保留「归一化字符 → 原文索引」的映射，
   因为锚点 start/end 要落在**原文**坐标上，不能返回归一化文本里的偏移。 */
const PUNCT_MAP = {
  "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
  "\u201c": '"', "\u201d": '"', "\u201e": '"',
  "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-",
  "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u2005": " ",
};
const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0", mdash: "\u2014", ndash: "\u2013" };

function decodeEntity(tok) {
  const m = /^&(#x[0-9a-fA-F]+|#[0-9]+|[a-zA-Z]+);$/.exec(tok);
  if (!m) return null;
  const b = m[1];
  if (b[0] === "#") {
    const code = b[1] === "x" || b[1] === "X" ? parseInt(b.slice(2), 16) : parseInt(b.slice(1), 10);
    return Number.isFinite(code) ? String.fromCodePoint(code) : null;
  }
  return ENTITIES[b] !== undefined ? ENTITIES[b] : null;
}

/* 返回 {norm, map}：norm 为归一化文本，map[i] 为 norm[i] 在原文中的索引。
   归一化步骤：HTML 实体反转义 → 标点统一 → 丢弃全部空白。 */
function normalizeWithMap(text) {
  const s = String(text || "");
  const chars = [];
  const map = [];
  let i = 0;
  while (i < s.length) {
    if (s[i] === "&") {
      const semi = s.indexOf(";", i);
      if (semi > i && semi - i <= 10) {
        const dec = decodeEntity(s.slice(i, semi + 1));
        if (dec !== null) {
          // 一个实体可能展开成多个字符，全部映射回实体起点
          for (const ch of dec) {
            if (!/\s/.test(ch)) { chars.push(ch); map.push(i); }
          }
          i = semi + 1;
          continue;
        }
      }
    }
    let ch = s[i];
    if (PUNCT_MAP[ch] !== undefined) ch = PUNCT_MAP[ch];
    if (!/\s/.test(ch)) { chars.push(ch); map.push(i); }
    i++;
  }
  return { norm: chars.join(""), map };
}

function normalizeText(text) { return normalizeWithMap(text).norm; }

/* 在指定文献里定位一句话，返回 {paraIdx,start,end}；找不到返回 null
   句子超过 60 字符时回退用前 60 字符探测 —— 长句里若有 OCR/转出噪声，
   整句匹配容易失败，前 60 字符通常足够定位。 */
function locateQuoteIn(paper, q) {
  if (!paper || !Array.isArray(paper.paragraphs) || !q) return null;
  const needle = normalizeText(q);
  if (needle.length < 4) return null;

  const probes = [needle];
  if (needle.length > 60) probes.push(needle.slice(0, 60));

  for (let pi = 0; pi < paper.paragraphs.length; pi++) {
    const { norm, map } = normalizeWithMap((paper.paragraphs[pi] && paper.paragraphs[pi].text) || "");
    if (!norm) continue;
    for (const probe of probes) {
      const at = norm.indexOf(probe);
      if (at >= 0) {
        // 映射回原文坐标：末字符的原索引 +1 作为 end
        const s0 = map[at];
        const s1 = map[at + probe.length - 1];
        return { paraIdx: pi, start: s0, end: (s1 === undefined ? s0 : s1) + 1 };
      }
    }
  }
  return null;
}

/* 按 id / 标题 / DOI 找文献。支持模糊标题（包含即命中） */
function findPaper(papers, key) {
  if (!key) return null;
  const k = String(key).trim();
  const low = k.toLowerCase();
  let exact = papers.find((p) => p.id === k);
  if (exact) return exact;
  exact = papers.find((p) => (p.doi || "").toLowerCase() === low);
  if (exact) return exact;
  exact = papers.find((p) => (p.title || "").toLowerCase() === low);
  if (exact) return exact;
  const hits = papers.filter((p) => (p.title || "").toLowerCase().includes(low));
  return hits.length ? hits[0] : null;
}

/* 把纯文本切成段落。
   给 AI 用的降级入口：手搓 Markdown 或 .txt 内容时，
   空行分段、识别 # 标题、识别 [1] 参考文献。 */
function textToParagraphs(text, startPage) {
  const page0 = Number.isFinite(startPage) ? startPage : 1;
  const raw = String(text || "").replace(/\r\n/g, "\n");
  const blocks = raw.split(/\n\s*\n+/);
  const out = [];
  blocks.forEach((b) => {
    const t = b.trim();
    if (!t) return;
    const line = t.split("\n")[0].trim();
    let type = "body";
    if (/^#{1}\s+/.test(line)) type = "h1";
    else if (/^#{2}\s+/.test(line)) type = "h2";
    else if (/^#{3}\s+/.test(line)) type = "h3";
    else if (/^\s*\[\d+\]/.test(line)) type = "ref";
    const cleaned = t.replace(/^#{1,3}\s+/gm, "").replace(/\n/g, " ").replace(/\s+/g, " ").trim();
    if (!cleaned) return;
    out.push({ page: page0, type, text: cleaned });
  });
  return out;
}

/* 段落 → Markdown（与前端 vSrc 视图口径一致） */
function paragraphsToMD(paper, markPages) {
  const Head = { h1: "# ", h2: "## ", h3: "### " };
  const lines = [];
  let lastPage = null;
  (paper.paragraphs || []).forEach((p) => {
    if (markPages && p.page !== lastPage) {
      lines.push("", "<!-- page " + p.page + " -->", "");
      lastPage = p.page;
    }
    const prefix = Head[p.type] || "";
    lines.push(prefix + String(p.text || "").trim(), "");
  });
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

function cardBrief(c) {
  return {
    id: c.id,
    paperId: c.paperId,
    type: TYPES.includes(c.type) ? c.type : "NT",
    quote: c.quote,
    note: c.note,
    comment: c.comment,
    tags: c.tags || [],
    star: !!c.star,
    pinned: !!c.pinned,
    anchored: Number.isInteger(c.paraIdx),
    paraIdx: c.paraIdx,
    start: c.start,
    end: c.end,
    createdAt: c.createdAt,
  };
}

module.exports = { TYPES, locateQuoteIn, findPaper, textToParagraphs, paragraphsToMD, cardBrief };
