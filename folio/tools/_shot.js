/* 打开 Folio 页面，切到目标文献，校验卡片与锚点并截图 */
const path = require("path");
const fs = require("fs");
const puppeteer = require(path.join(__dirname, "..", "..", ".runtest", "node_modules", "puppeteer-core"));
const CHROME = [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
].find((p) => fs.existsSync(p));
const OUT = path.join(__dirname, "..", "..", "shots");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await puppeteer.launch({
    executablePath: CHROME, headless: "new",
    args: ["--no-sandbox", "--force-device-scale-factor=1"],
  });
  const p = await b.newPage();
  await p.setViewport({ width: 1600, height: 1150 });
  const errs = [];
  p.on("pageerror", (e) => errs.push(e.message));

  await p.goto("http://127.0.0.1:8787/", { waitUntil: "networkidle0" });
  await sleep(2500);

  await p.evaluate(() => {
    const sel = document.getElementById("paperSel");
    // 按 id 匹配：同名文献可能有多份，标题无法区分
    const opt = Array.from(sel.options).find((o) => { const t = window.LD.state.papers.find((x) => x.id === o.value); return t && /Deep-learning-enabled brain/.test(t.title) && /^p-aa4b72f1/.test(t.id); });
    if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event("change", { bubbles: true })); }
  });
  await sleep(4000);

  // 渲染诊断：DOM 里到底有几张卡、容器状态如何
  const dom = await p.evaluate(() => {
    const box = document.querySelector("#cards");
    const nodes = document.querySelectorAll("#cards [data-cid]");
    return {
      cardDom: nodes.length,
      firstText: nodes.length ? (nodes[0].textContent || "").replace(/\s+/g, " ").slice(0, 70) : "(无)",
      boxH: box ? box.clientHeight : -1,
      boxScrollH: box ? box.scrollHeight : -1,
    };
  });
  console.log("DOM 卡片数 :", dom.cardDom, "| 容器高", dom.boxH, "滚动高", dom.boxScrollH);
  console.log("首卡内容   :", dom.firstText);

  const info = await p.evaluate(() => {
    const pid = window.LD.state.curPaperId;
    const cs = window.LD.state.cards.filter((c) => c.paperId === pid);
    const dist = {};
    cs.forEach((c) => { dist[c.type] = (dist[c.type] || 0) + 1; });
    let jump = 0;
    cs.forEach((c) => {
      const el = document.querySelector('#doc .p[data-pi="' + c.paraIdx + '"]');
      if (!el) return;
      for (const m of el.querySelectorAll("mark.hl")) {
        if (String(m.getAttribute("data-cards") || "").split(",").indexOf(c.id) >= 0) { jump++; break; }
      }
    });
    return {
      papers: window.LD.state.papers.length,
      allCards: window.LD.state.cards.length,
      curCards: cs.length,
      dist,
      anchored: cs.filter((c) => Number.isInteger(c.paraIdx)).length,
      jump,
      marks: document.querySelectorAll("#doc mark.hl").length,
      sync: document.getElementById("syncText").textContent,
    };
  });

  console.log("文献总数   :", info.papers, "| 卡片总数:", info.allCards);
  console.log("本文卡片   :", info.curCards, "| 已锚定:", info.anchored);
  console.log("类型分布   :", JSON.stringify(info.dist));
  console.log("原文高亮   :", info.marks, "处 | 可跳转:", info.jump + "/" + info.curCards);
  console.log("同步状态   :", info.sync);
  console.log("页面报错   :", errs.length ? errs.join(" | ") : "无");

  await p.screenshot({ path: path.join(OUT, "folio-dlbrain-24cards.png") });
  console.log("已截图 → shots/folio-dlbrain-24cards.png");
  await b.close();
})();
