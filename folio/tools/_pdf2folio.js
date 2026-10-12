/* 把 _pdftext.js 的输出（逐页段落）入库到 Folio。
   跑法：node tools/_pdf2folio.js <段落json> [--dry]

   只做「原文入库」，不建卡 —— 卡片要精读后按 quote 逐条定义（见 _cards_pdf.js）。 */
"use strict";
const fs = require("fs");

const BASE = "http://127.0.0.1:8787";
const JSON_PATH = process.argv[2];
const DRY = process.argv.includes("--dry");
if (!JSON_PATH || !fs.existsSync(JSON_PATH)) {
  console.error("用法: node tools/_pdf2folio.js <段落json> [--dry]");
  process.exit(1);
}

const META = {
  title: "Deep-learning-enabled brain hemodynamic mapping using resting-state fMRI",
  authors: "Xirui Hou, Pengfei Guo, Puyang Wang, Peiying Liu, Doris D. M. Lin, Hongli Fan, Yang Li, " +
    "Zhiliang Wei, Zixuan Lin, Dengrong Jiang, Jin Jin, Catherine Kelly, Jay J. Pillai, Judy Huang, " +
    "Marco C. Pinho, Binu P. Thomas, Babu G. Welch, Denise C. Park, Vishal M. Patel, Argye E. Hillis, Hanzhang Lu",
  journal: "npj Digital Medicine",
  year: "2023",
  doi: "10.1038/s41746-023-00859-y",
  tags: ["PDF导入", "rs-fMRI", "CVR", "BAT", "深度学习", "脑血管", "脑血流动力学"],
  status: "在读",
};

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

const doc = JSON.parse(fs.readFileSync(JSON_PATH, "utf8"));
const paras = [];
doc.pages.forEach((pg) => pg.paragraphs.forEach((p) => paras.push(p)));
console.log("段落数：" + paras.length);

/* 组装提交文本：段间空行分隔（textToParagraphs 按空行切段）。
   节标题用 `# `（h1）、小标题用 `## `（h2）—— 全大写短行判为节标题。 */
const lines = paras.map((p) => {
  const isSec = p.head && /^[A-Z][A-Z\s\d:,;'\-]*$/.test(p.text) && p.text.length < 60;
  if (isSec) return "# " + p.text;
  if (p.head) return "## " + p.text;
  return p.text;
});
const text = lines.join("\n\n");

console.log("正文字符数：" + text.length);
if (DRY) {
  console.log("\n【--dry】前 600 字符：\n" + text.slice(0, 600));
  process.exit(0);
}

(async () => {
  const r = await call("folio_add_paper", Object.assign({ text }, META));
  console.log("\n已入库：paperId=" + r.paperId + "  段落=" + r.paragraphs +
    (r.isCurrent ? "（已设为当前）" : ""));
  console.log("PAPER_ID=" + r.paperId);
  process.exit(0);
})().catch((e) => { console.error("失败：" + e.message); process.exit(1); });
