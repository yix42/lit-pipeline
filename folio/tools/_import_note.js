/* 把 vault 的一篇 L2 笔记导入 Folio：
     - 40_Fulltext/md/<key>.md          → Folio 的原文（paragraphs）
     - 20_Notes/<key>_*.md 的「要点单元」 → Folio 卡片（每单元一张，首条引语锚定）
     - 全部引语过一遍引语闸门             → 每条引语的核实状态写进卡片 note

   为什么按「要点单元」而不是「主要发现」：
     早期版本只认 `- **主要发现 N**`，而该标记只在「主要结果」节出现 ——
     技术细节 / 指标定义 / 统计方法 / 局限性等节的要点写成普通列表项或表格行，
     永远匹配不到。8VU28A3S 实测：55 条引语只进 5 条，方法学的 20 条一条没进。

   跑法：node tools/_import_note.js <KEY> [--dry]
*/
const fs = require("fs");
const path = require("path");
const { parseUnits, typeForUnit } = require("./note_units");
const vault = require("../server/vault");

/* vault 定位复用 server/vault 的探测（单一口径）；探测不到再退回家目录标准位置。
   原版把 C:\Users\xia\... 写死，换机就找不到库。 */
const VAULT = process.env.FOLIO_VAULT_DIR || process.env.RESEARCH_VAULT ||
  vault.detectVault() || path.join(require("os").homedir(), "ResearchVault");
const BASE = "http://127.0.0.1:8787";
const KEY = (process.argv[2] || "").trim().toUpperCase();
const DRY = process.argv.includes("--dry");
const NOTE_MAX = 2400;
if (!/^[A-Z0-9]{8}$/.test(KEY)) { console.error("用法: node _import_note.js <8位KEY> [--dry]"); process.exit(1); }

const BADGE = { strict: "严格命中", loose: "仅连字符差异", miss: "⚠ 未命中", "?": "未判定" };

async function call(name, args) {
  const r = await fetch(BASE + "/api/call", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, args }),
  });
  const j = await r.json();
  if (!j.result) throw new Error(JSON.stringify(j).slice(0, 300));
  if (j.result.isError) throw new Error(j.result.content[0].text);
  return JSON.parse(j.result.content[0].text);
}

/* ---------- 1. 定位文件 ---------- */
const noteDir = path.join(VAULT, "20_Notes");
const noteName = fs.readdirSync(noteDir).find((f) => f.startsWith(KEY + "_") && f.endsWith(".md"));
if (!noteName) { console.error("找不到笔记: " + KEY); process.exit(1); }
const notePath = path.join(noteDir, noteName);
const fullPath = path.join(VAULT, "40_Fulltext", "md", KEY + ".md");
if (!fs.existsSync(fullPath)) { console.error("找不到全文档案: " + fullPath); process.exit(1); }

/* ---------- 2. 档案 → 原文（去 frontmatter） ---------- */
const rawFull = fs.readFileSync(fullPath, "utf8");
const fmMatch = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(rawFull);
const fm = {};
if (fmMatch) {
  fmMatch[1].split(/\r?\n/).forEach((ln) => {
    const m = /^([a-z_]+):\s*(.*)$/.exec(ln.trim());
    if (m) fm[m[1]] = m[2].replace(/^["']|["']$/g, "").trim();
  });
}
const fullBody = (fmMatch ? rawFull.slice(fmMatch[0].length) : rawFull).trim();

/* ---------- 3. 笔记 → 要点单元 ---------- */
const { units, allQuotes, stats } = parseUnits(fs.readFileSync(notePath, "utf8"));
console.log("笔记解析：单元 " + stats.units + " 个 / 引语 " + stats.quotesAll + " 条 / 未被覆盖 " + stats.quotesLost);
if (stats.quotesLost > 0) {
  console.log("  ⚠ 有 " + stats.quotesLost + " 条引语没落进任何单元 —— 覆盖度会报出来");
}

/* ---------- 4. 全部引语过闸门，拿每条核实状态 ---------- */
let statusByQuote = {};
let gateErr = "";
if (allQuotes.length) {
  const judged = vault.reviewQuotes(allQuotes.map((q, i) => ({ id: String(i), quote: q })));
  if (judged.ok) {
    (judged.items || []).forEach((it) => {
      const lv = (it.segments || []).map((s) => s.level);
      // 兜底必须是「未判定」而不是「严格命中」：闸门对含中文 / 字母太少的引语会整条
      // 判不了（不返回 segments），若兜到 strict 就等于给未核验的引语发绿灯。
      statusByQuote[allQuotes[Number(it.id)]] =
        lv.includes("miss") ? "miss" : lv.includes("loose") ? "loose"
          : lv.includes("strict") ? "strict" : "?";
    });
  } else {
    gateErr = judged.error || "闸门失败";
    console.log("  ⚠ 闸门未跑通（" + gateErr + "），核实状态留空");
  }
}
const tally = { strict: 0, loose: 0, miss: 0, "?": 0 };
allQuotes.forEach((q) => { tally[statusByQuote[q] || "?"]++; });

/* ---------- 5. 单元 → 卡片 ---------- */
const cards = [];
for (const u of units) {
  // 提示框里的孤立引语（> [!warning] 那一类）没有要点标题，归为批注更贴切
  const type = u.kind === "orphan" ? "NT" : typeForUnit(u.section, u.title);
  const head = "【" + (u.section || "未分节") + " / " + u.title + "】";
  const detail = (u.detail || []).filter(Boolean).slice(0, 12).join("\n");
  // 引语**完整保留**：覆盖度审查靠「归一化后互为子串」判定，
  // 一旦把引语截断（曾截到 180 字符），长引语就再也匹配不上 ——
  // 报告里会显示成「未进 Folio」，而它其实躺在 note 里。
  const others = u.quotes.slice(1)
    .map((q, i) => "  " + (i + 2) + '. "' + q + '"  [' + BADGE[statusByQuote[q] || "?"] + "]");
  const missInUnit = u.quotes.filter((q) => statusByQuote[q] === "miss").length;

  /* note 组织：**引语优先**。
     「其余引语」是核实信息，被挤掉就等于这些引语没进 Folio、从未被核实。
     所以超长时先丢说明文字，绝不丢引语。 */
  const tail = "\n\n—— 来源：vault L2 笔记 " + KEY + " / " + (u.section || "");
  const quoteBlock = others.length
    ? "\n\n其余引语（未锚定，共 " + others.length + " 条）：\n" + others.join("\n")
    : "";
  const core = head + quoteBlock;
  const full = core + (detail ? "\n\n" + detail : "") + tail;
  const note = full.length <= NOTE_MAX
    ? full
    : core.slice(0, Math.max(0, NOTE_MAX - tail.length)) + "…" + tail;

  cards.push({
    type,
    quote: u.quotes[0],
    note,
    comment: missInUnit ? "本要点有 " + missInUnit + " 条引语未命中原文，见 note 标注" : "",
    tags: [KEY, "vault导入", u.section].filter(Boolean).slice(0, 4),
    star: missInUnit > 0,
    sourceKey: KEY,
  });
}

const byType = {};
cards.forEach((c) => { byType[c.type] = (byType[c.type] || 0) + 1; });
console.log("卡片：" + cards.length + " 张 → " + JSON.stringify(byType));
console.log("引语核实：严格 " + tally.strict + " · 仅连字符 " + tally.loose +
  " · 未命中 " + tally.miss + " · 未判定 " + tally["?"]);
console.log("平均 note 长度：" + Math.round(cards.reduce((a, c) => a + c.note.length, 0) / cards.length) + " 字符");

if (DRY) {
  console.log("\n【--dry】以下为前 6 张卡预览，未写入任何数据：");
  cards.slice(0, 6).forEach((c, i) => {
    console.log("\n── [" + (i + 1) + "] " + c.type + (c.star ? " ★" : "") + " ──");
    console.log("  quote : " + c.quote.slice(0, 96));
    console.log("  note  : " + c.note.replace(/\n/g, "\n          ").slice(0, 420));
  });
  process.exit(0);
}

/* ---------- 6. 落库（复用已有文献 / 跳过重复卡） ---------- */
(async () => {
  const title = fm.title || KEY;
  const list = await call("folio_list_papers", {});
  const existing = (list.papers || []).find((x) =>
    (fm.doi && x.doi && x.doi === fm.doi) || String(x.title || "").trim() === title.trim());

  let paperId, paraCount;
  if (existing) {
    paperId = existing.id; paraCount = existing.paragraphs;
    console.log("\n复用已有文献: " + paperId + "（" + paraCount + " 段）");
  } else {
    const p = await call("folio_add_paper", {
      title, authors: "", journal: "", year: "2017", doi: fm.doi || "",
      tags: [KEY, "vault导入"], status: "在读", mtype: "KR", text: fullBody,
    });
    paperId = p.paperId; paraCount = p.paragraphs;
    console.log("\n原文入库: " + paperId + "（" + paraCount + " 段）");
  }

  const have = await call("folio_list_cards", { paperId });
  const seen = new Set((have.cards || []).map((c) => String(c.quote || "").trim()));
  const fresh = cards.filter((c) => !seen.has(String(c.quote).trim()));
  if (cards.length - fresh.length) console.log("跳过 " + (cards.length - fresh.length) + " 张已存在（quote 相同）");
  if (!fresh.length) { console.log("没有新卡需要写入。\n\nPAPER_ID=" + paperId); return; }

  const imp = await call("folio_import_cards", { paperId, cards: fresh });
  console.log("【已写入】请求 " + imp.requested + " · 锚定 " + imp.anchored + " · 未命中 " + imp.unanchored);
  if (imp.unanchored) {
    console.log("未锚定清单：");
    (imp.items || []).slice(0, 10).forEach((x) => console.log("  ✗ " + String(x.quote).slice(0, 88)));
  }
  console.log("\nPAPER_ID=" + paperId);
})().catch((e) => { console.error("失败：" + e.message); process.exit(1); });
