/* 从 PDF 提取逐页文本 —— 用 Folio 页面内置的 pdf.js（与「PDF → Markdown」同一引擎）。
   跑法：node tools/_pdftext.js <pdf路径> [输出json]

   ⚠️ 论文 PDF 有两类必须处理的版式问题（否则正文句子会被拼坏、建卡挑不到完整引语）：
   ① **双栏**：单纯按 y 分桶会把左栏某行与右栏同高度那行拼成一行
      （实测本 PDF 第 1 页下半：`INTRODUCTION peak (TTP), is a promising...`）。
      做法：先用 x 直方图找「栏间空白」，再把双栏区域整段按「先左栏读完、再右栏」重排。
   ② **ligature**：`fi`/`fl` 被拆成独立 token（`strati fi cation`、`fl uctuates`、`signi fi cant`）。
      高置信度还原（前一个字符是字母时才合并）。 */
"use strict";
const fs = require("fs");
const path = require("path");
const os = require("os");
const puppeteer = require("C:/Users/xia/WorkBuddy/2026-10-04-19-51-30/.runtest/node_modules/puppeteer-core");

const ROOT = path.join(__dirname, "..");
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PDF = process.argv[2];
const OUT = process.argv[3] || path.join(os.tmpdir(), "folio-pdftext.json");

if (!PDF || !fs.existsSync(PDF)) { console.error("用法: node tools/_pdftext.js <pdf路径> [输出json]"); process.exit(1); }

(async () => {
  const b64 = fs.readFileSync(PDF).toString("base64");
  const b = await puppeteer.launch({
    executablePath: CHROME, headless: "new",
    args: ["--no-sandbox", "--allow-file-access-from-files"],
  });
  const p = await b.newPage();
  const errs = [];
  p.on("pageerror", (e) => errs.push(String(e).slice(0, 160)));

  await p.goto("file:///" + path.join(ROOT, "app.html").replace(/\\/g, "/"), { waitUntil: "domcontentloaded" });
  await p.waitForFunction(() => typeof pdfjsLib !== "undefined", { timeout: 30000 });

  const res = await p.evaluate(async (b64) => {
    const raw = atob(b64);
    const arr = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    const doc = await pdfjsLib.getDocument({ data: arr }).promise;

    // ligature 还原：`strati fi cation` / `CO 2 fl uctuations` —— ligature 前不一定是字母，
    // 故按「行首或空白 + fi/fl/ff… + 空格 + 字母」匹配
    const fixLig = (s) => {
      let prev, t = s.replace(/^\d{10}\(\):,[;\s]*/, "").replace(/\bCO 2\b/g, "CO2");
      do {
        prev = t;
        t = t.replace(/([A-Za-z]) (ffi|ffl|ff|fi|fl) ([A-Za-z])/g, "$1$2$3");  // 词中：strati fi cation
        t = t.replace(/(^|\s)(ffi|ffl|ff|fi|fl) ([A-Za-z])/g, "$1$2$3");       // 空白后：CO2 fl uctuations
      } while (t !== prev);
      return t
        .replace(/([“”‘’])\s+/g, "$1").replace(/\s+([“”‘’])/g, "$1")
        .replace(/\s+([,.;:%)])/g, "$1").replace(/\s+/g, " ").trim();
    };
    /* 上标引用编号会独立成行（`1,2 3 4 5`、`2 7 8 2,9`）—— 纯数字/逗号/符号的短行丢弃 */
    const isSupLine = (t) => t.length <= 20 && /^[\d\s,\-–—✉*†‡§.]+$/.test(t);

    const pages = [];
    for (let pi = 1; pi <= doc.numPages; pi++) {
      const pg = await doc.getPage(pi);
      const vp = pg.getViewport({ scale: 1 });
      const tc = await pg.getTextContent();
      const items = tc.items
        .map((it) => ({ s: it.str, x: it.transform[4], y: it.transform[5], w: it.width || 0, h: it.height || 0 }))
        .filter((z) => z.s && z.s.trim());

      /* ---- ① 按 y 分桶成行带 ---- */
      const rows = [];
      items.forEach((z) => {
        let r = rows.find((q) => Math.abs(q.y - z.y) < 3);
        if (!r) { r = { y: z.y, items: [] }; rows.push(r); }
        r.items.push(z);
      });
      rows.sort((a, b) => b.y - a.y);
      rows.forEach((r) => r.items.sort((a, b) => a.x - b.x));

      /* ---- ② 判定双栏并求「栏间空白」位置 ----
         不能只看全页 x 直方图：混合布局页（上半单栏 + 下半双栏，如本 PDF 第 1 页）
         的单栏行会横跨整页，把直方图填满、抹平栏间空白。
         改为**逐行找行内间隙**：双栏行被 y 分桶合并后，行内会留下一个 ~20pt 的
         空档（左栏末 item 的右边界 → 右栏首 item 的左边界）。取这些空档的中位数
         作为栏界；要求空档落在页中线附近，避免把段落缩进/图表间隙误当栏界。 */
      const W = vp.width;
      const cands = [];
      rows.forEach((r) => {
        const its = r.items;
        for (let i = 0; i < its.length - 1; i++) {
          const gap = its[i + 1].x - (its[i].x + its[i].w);
          if (gap >= 14) cands.push((its[i].x + its[i].w + its[i + 1].x) / 2);
        }
      });
      let gapCenter = null;
      const nearMid = cands.filter((c) => c > W * 0.3 && c < W * 0.7).sort((a, b) => a - b);
      if (nearMid.length >= 2) {
        gapCenter = nearMid[Math.floor(nearMid.length / 2)];
      } else {
        // 退回全页直方图（纯双栏页通常是这种情形）
        let bestGap = 0;
        const binW = 4, hit = {};
        items.forEach((z) => { const k = Math.floor(z.x / binW); hit[k] = (hit[k] || 0) + 1; });
        const keys = Object.keys(hit).map(Number).sort((a, b) => a - b);
        for (let k = 0; k < keys.length - 1; k++) {
          if (keys[k + 1] - keys[k] > 1) {
            const span = (keys[k + 1] - keys[k] - 1) * binW;
            if (span > bestGap) { bestGap = span; gapCenter = ((keys[k] + 1 + keys[k + 1]) / 2) * binW; }
          }
        }
        if (bestGap < 8) gapCenter = null;
      }
      const twoCol = gapCenter !== null;

      /* ---- ③ 重排：跨栏行直接输出；双栏行带先攒左、再攒右 ---- */
      const lines = [];
      let bufL = [], bufR = [];
      const flush = () => {
        bufL.forEach((o) => { if (o.t) lines.push(o); });
        bufR.forEach((o) => { if (o.t) lines.push(o); });
        bufL = []; bufR = [];
      };
      const mk = (r, items, col) => ({
        t: fixLig(items.map((z) => z.s).join(" ")),
        x0: items.length ? Math.round(items[0].x) : 0,
        h: items.length ? Math.round(items.reduce((a, z) => a + (z.h || 0), 0) / items.length * 10) / 10 : 0,
        col,
      });

      rows.forEach((r) => {
        if (!twoCol) { lines.push(mk(r, r.items, "S")); return; }
        const spans = r.items.some((z) => z.x < gapCenter && z.x + z.w > gapCenter);
        if (spans) {
          flush();
          lines.push(mk(r, r.items, "S"));
        } else {
          bufL.push(mk(r, r.items.filter((z) => z.x < gapCenter), "L"));
          bufR.push(mk(r, r.items.filter((z) => z.x >= gapCenter), "R"));
        }
      });
      flush();

      const clean = lines.filter((o) => o.t && !isSupLine(o.t));
      pages.push({
        page: pi, width: Math.round(vp.width), height: Math.round(vp.height),
        twoCol, gapCenter: gapCenter === null ? null : Math.round(gapCenter),
        lineCount: clean.length, lines: clean,
      });
    }
    return { numPages: doc.numPages, pages };
  }, b64);

  /* ---- ④ 跨页重复行 ⇒ 页眉/页脚（期刊名、running head）----
     这类行每页都出现、位置在版心之外，靠单页判断不出来；跨页计数最可靠。
     实测本 PDF 的 `X. Hou et al.` 会与正文首行合并成段。 */
  const freq = {};
  res.pages.forEach((pg) => {
    const seen = new Set();
    pg.lines.forEach((l) => { if (!seen.has(l.t)) { seen.add(l.t); freq[l.t] = (freq[l.t] || 0) + 1; } });
  });
  res.pages.forEach((pg) => {
    pg.lines = pg.lines.filter((l) => !(freq[l.t] >= 3 && l.t.length < 100));
    // 期刊页眉标志（跨页计数抓不到的短标记），以及 `www.` 开头的网址行
    pg.lines = pg.lines.filter((l) => !/^(ARTICLE OPEN|www\.)/.test(l.t));
    // 字号过滤：正文字号 9pt，图内标签/坐标轴刻度 7pt。实测 P5/P7/P8 的
    // `DL GR DL GR DL GR`、`Cross-correlation` 这类图内文字会整段混进正文。
    pg.lines = pg.lines.filter((l) => !(l.h > 0 && l.h <= 7.5));
    pg.lineCount = pg.lines.length;
  });

  /* ---- ⑤ 行 → 段落 ----
     段落首行在 PDF 里带缩进（比栏左边界大 ~6pt）—— 用这个判定新段落开始。
     段内续接：行尾是连字符时**直接拼接**（`athero-`+`sclerosis`、`resting-`+`state`），
     否则补一个空格。断词处的连字符保留（无法可靠区分「词内断词」与「真连字符」，
     保留至多多一个连字符，删掉则会把 `resting-state` 变成 `restingstate`）。 */
  const colBase = (lines, col) => {
    const xs = lines.filter((l) => l.col === col).map((l) => l.x0).sort((a, b) => a - b);
    return xs.length ? xs[Math.floor(xs.length * 0.1)] : 0;
  };
  res.pages.forEach((pg) => {
    const base = { L: colBase(pg.lines, "L"), R: colBase(pg.lines, "R"), S: 0 };
    const paras = [];
    let cur = null, curCol = null;
    pg.lines.forEach((l) => {
      const ind = l.col !== "S" && l.x0 > base[l.col] + 6;
      // 图注须是 `Figure 1.` / `Fig. 1 |`（带编号 + 分隔符）；`Figure 1 shows the structure…`
      // 是正文引用，不能当图注，否则会被独立成段
      const isFig = /^(Fig\.|Figure|Table|Extended Data)\s*\d+\s*[.|:]/.test(l.t);
      const isHead = isFig || (/^[A-Z][A-Z\s\d:,;'\-]{5,}$/.test(l.t) && l.t.length < 60);
      // cur.head：标题段之后的正文首行往往不缩进，必须靠「上一段是标题」强制断开
      if (!cur || curCol !== l.col || ind || isHead || cur.head) {
        cur = { text: l.t, head: isHead, col: l.col };
        paras.push(cur);
        curCol = l.col;
      } else {
        cur.text += /-$/.test(cur.text) ? l.t : " " + l.t;
      }
    });
    // 小标题：独立成段、很短、不带句末标点（如 `Network architecture`）
    pg.paragraphs = paras.map((x) => {
      const short = x.text.length < 50 && !/[.;:!?]$/.test(x.text) && x.text.split(/\s+/).length <= 6;
      return { text: x.text, head: !!(x.head || short) };
    });
  });

  fs.writeFileSync(OUT, JSON.stringify(res, null, 1), "utf8");
  console.log("页数: " + res.numPages + "  行 " +
    res.pages.reduce((a, x) => a + x.lineCount, 0) + "  段落 " +
    res.pages.reduce((a, x) => a + x.paragraphs.length, 0));
  res.pages.forEach((x) => {
    console.log("  P" + x.page + "  " + x.lineCount + " 行  " + (x.twoCol ? "双栏(gap=" + x.gapCenter + ")" : "单栏"));
  });
  console.log("输出: " + OUT);
  if (errs.length) console.log("页面错误: " + errs.slice(0, 3).join(" | "));
  await b.close();
})().catch((e) => { console.error("失败: " + e.message); process.exit(1); });
