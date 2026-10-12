/* =====================================================================
   连接器冒烟测试：直接起 MCP stdio 进程，走完整 MCP 握手 + 工具调用
   用法：node tools/conntest.js
   ===================================================================== */
const path = require("path");
const os = require("os");
const fs = require("fs");
const { spawn } = require("child_process");
const ROOT = path.join(__dirname, "..");

/* 用「正在跑本脚本的那个 node」去起 MCP 子进程 —— 换机不会失效
   （原版写死 C:\Users\xia\...\node.exe） */
const NODE = process.execPath;
const MCP = path.join(ROOT, "server", "mcp.js");
/* 测试跑在独立数据目录里，不碰真实数据，也不受上次运行的残留影响 */
const TMP = path.join(os.tmpdir(), "folio-conntest-" + Date.now());
fs.mkdirSync(TMP, { recursive: true });

let pass = 0, fail = 0, seq = 0;
const pending = new Map();

function ok(m) { console.log("  PASS  " + m); pass++; }
function bad(m) { console.log("  FAIL  " + m); fail++; }
function head(m) { console.log("\n=== " + m + " ===\n"); }

const child = spawn(NODE, [MCP], {
  stdio: ["pipe", "pipe", "pipe"], windowsHide: true,
  env: Object.assign({}, process.env, { FOLIO_DATA_DIR: TMP }),
});
let buf = "";
let stderrLog = "";

child.stderr.on("data", (c) => { stderrLog += c.toString(); });
child.stdout.on("data", (chunk) => {
  buf += chunk.toString();
  let nl;
  while ((nl = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let msg;
    try { msg = JSON.parse(line); } catch (_) { continue; }
    if (msg.id !== undefined && pending.has(msg.id)) {
      const { resolve } = pending.get(msg.id);
      pending.delete(msg.id);
      resolve(msg);
    }
  }
});

function request(method, params) {
  const id = ++seq;
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => { pending.delete(id); reject(new Error("超时: " + method)); }, 20000);
    pending.set(id, { resolve: (m) => { clearTimeout(t); resolve(m); } });
    child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  });
}
function notify(method, params) {
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
}
function parseTool(msg) {
  const c = msg.result && msg.result.content;
  if (!c || !c[0]) return null;
  try { return JSON.parse(c[0].text); }
  catch (_) { return { __raw: c[0].text }; }
}

(async () => {
  try {
    head("A. MCP 握手");
    const init = await request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "conntest", version: "1.0" },
    });
    if (init.result && init.result.serverInfo && init.result.serverInfo.name === "folio")
      ok("initialize 返回 serverInfo.name=folio");
    else bad("initialize 响应异常：" + JSON.stringify(init.result).slice(0, 160));
    if (init.result && init.result.protocolVersion === "2024-11-05")
      ok("协议版本 2024-11-05 协商一致");
    else bad("协议版本不一致");

    notify("notifications/initialized", {});

    const list = await request("tools/list", {});
    const names = ((list.result && list.result.tools) || []).map((t) => t.name);
    ok("tools/list 返回 " + names.length + " 个工具");
    ["folio_status", "folio_list_papers", "folio_search", "folio_add_card", "folio_import_cards",
     "folio_update_card", "folio_add_paper", "folio_export_markdown", "folio_today",
     // vault 引语闸门相关
     "folio_vault_status", "folio_review_notes", "folio_review_cards", "folio_coverage"
    ].forEach((n) => {
      if (names.includes(n)) ok("提供工具 " + n);
      else bad("缺少工具 " + n);
    });
    // 铁律：不得提供任何删除能力
    const del = names.filter((n) => /delete|remove|clear|purge|drop/i.test(n));
    if (del.length === 0) ok("未暴露任何删除类工具（符合权限约定）");
    else bad("存在删除类工具：" + del.join(", "));
    const noSchema = ((list.result && list.result.tools) || []).filter((t) => !t.inputSchema);
    if (noSchema.length === 0) ok("全部工具都带 inputSchema");
    else bad("以下工具缺 inputSchema：" + noSchema.map((t) => t.name).join(", "));

    head("A2. 准备测试数据");
    // 首次运行数据文件是空的，先造一篇带正文的文献 + 一条逾期项，后面的读写才有对象
    const has = parseTool(await request("tools/call", { name: "folio_status", arguments: {} }));
    if (!has || has.papers === 0) {
      const mk = await request("tools/call", {
        name: "folio_add_paper",
        arguments: {
          title: "Serum proteomic signatures before and after atrial fibrillation ablation",
          authors: "Zhao L, Chen H, Wang J, et al.", journal: "Scientific Reports", year: "2026",
          doi: "10.1038/s41598-026-00000-0", tags: ["蛋白组学", "消融"], status: "在读", dueInDays: -2,
          text: [
            "# Serum proteomic signatures before and after atrial fibrillation ablation",
            "",
            "## Abstract",
            "",
            "Background. Atrial fibrillation is the most common sustained arrhythmia, and catheter ablation has become the first-line rhythm control strategy.",
            "",
            "We profiled 1066 serum proteins across 514 ablation patients and characterised pre- versus post-ablation remodelling in 75 paired samples.",
            "",
            "## 2. Methods",
            "",
            "### 2.3 Proteomic profiling",
            "",
            "Differential abundance was assessed with limma, using empirical Bayes moderation. Low-abundance filtering retained proteins detectable in at least 70 percent of samples.",
            "",
            "## 3. Results",
            "",
            "Among 658 tested proteins, 41 passed the adjusted significance threshold. The largest absolute log fold changes were observed in complement component C3.",
            "",
            "Discrimination was moderate rather than strong. The area under the ROC curve for the combined panel was 0.71, which is not sufficient to support clinical use.",
            "",
            "## 4. Discussion",
            "",
            "We therefore state the falsifiable prediction: in a cohort of at least 200 patients followed for 18 months, the four-protein panel should improve area under the ROC curve above 0.75.",
            "",
            "## References",
            "",
            "[1] Van Gelder IC, et al. Lenient versus strict blood pressure control. N Engl J Med. 2010;362(15):1363-1373.",
          ].join("\n"),
        },
      });
      const mkc = parseTool(mk);
      if (mkc && mkc.paperId) ok("已创建测试文献（" + mkc.paragraphs + " 段，含逾期标记）");
      else bad("测试数据准备失败：" + JSON.stringify(mkc));
    } else {
      ok("数据文件已有 " + has.papers + " 篇文献，跳过准备");
    }

    head("B. 读：文献与正文");
    const st = parseTool(await request("tools/call", { name: "folio_status", arguments: {} }));
    if (st && typeof st.papers === "number") ok("folio_status 连通，文献 " + st.papers + " 篇 / 卡片 " + st.cards + " 张");
    else bad("folio_status 返回异常");

    const lp = parseTool(await request("tools/call", { name: "folio_list_papers", arguments: {} }));
    if (lp && Array.isArray(lp.papers) && lp.papers.length) {
      ok("folio_list_papers 返回 " + lp.papers.length + " 篇");
      const p0 = lp.papers[0];
      ["id", "title", "authors", "status", "paragraphs", "cards"].forEach((k) => {
        if (p0[k] !== undefined) ok("文献摘要含字段 " + k);
        else bad("文献摘要缺字段 " + k);
      });
    } else bad("folio_list_papers 未返回文献");

    const target = lp && lp.papers && lp.papers[0] ? lp.papers[0].id : null;
    const gp = parseTool(await request("tools/call", {
      name: "folio_get_paper", arguments: { paperId: target, includeText: true, limit: 5 },
    }));
    if (gp && Array.isArray(gp.paragraphs) && gp.paragraphs.length === 5) {
      ok("folio_get_paper 取回 5 段，total=" + gp.total);
      if (gp.paragraphs[0].paraIdx === 0) ok("段落带 paraIdx，可直接用作锚点");
      else bad("paraIdx 未正确标注");
    } else bad("folio_get_paper 返回异常");

    const md = parseTool(await request("tools/call", {
      name: "folio_export_markdown", arguments: { paperId: target },
    }));
    if (md && md.markdown && md.markdown.includes("# ")) ok("folio_export_markdown 产出 Markdown（" + md.chars + " 字符）");
    else bad("Markdown 导出失败");
    if (md && md.markdown && md.markdown.includes("<!-- page ")) ok("页码注释已保留");
    else bad("缺少页码注释");

    head("C. 搜索");
    const sr = parseTool(await request("tools/call", {
      name: "folio_search", arguments: { query: "area under the ROC", limit: 5 },
    }));
    if (sr && sr.count > 0) {
      ok("folio_search 命中 " + sr.count + " 条");
      const h = sr.hits[0];
      if (h.context.includes("ROC")) ok("命中上下文含关键词");
      else bad("上下文片段异常");
      if (Number.isInteger(h.paraIdx) && Number.isInteger(h.start)) ok("命中位置带 paraIdx/start，可直接建锚点卡");
      else bad("命中缺少锚点坐标");
    } else bad("folio_search 未命中");

    head("D. 写：建卡与锚定");
    const add = parseTool(await request("tools/call", {
      name: "folio_add_card",
      arguments: {
        paperId: target, type: "KR",
        quote: "Discrimination was moderate rather than strong. The area under the ROC curve for the combined panel was 0.71",
        note: "连接器写入的测试卡", tags: ["冒烟测试"], star: true,
      },
    }));
    if (add && add.anchored) ok("folio_add_card 已建卡并自动锚定（paraIdx=" + add.paraIdx + ", page=" + add.page + "）");
    else bad("folio_add_card 未能锚定：" + JSON.stringify(add));
    const newCardId = add && add.cardId;

    const add2 = parseTool(await request("tools/call", {
      name: "folio_add_card",
      arguments: { paperId: target, type: "NT", quote: "这句话在原文里根本不存在，用来验证未命中时的行为", note: "无锚点卡" },
    }));
    if (add2 && add2.anchored === false) ok("引句未命中时明确标记 anchored=false，不假装成功");
    else bad("未命中场景处理异常");

    const imp = parseTool(await request("tools/call", {
      name: "folio_import_cards",
      arguments: {
        paperId: target,
        cards: [
          { type: "KV", quote: "Among 658 tested proteins, 41 passed the adjusted significance threshold", note: "批量1" },
          { type: "KS", quote: " bats and whales share no common ancestor in this manuscript", note: "批量2-故意不命中" },
        ],
      },
    }));
    if (imp && imp.requested === 2 && imp.anchored === 1) ok("folio_import_cards 批量导入：2 张，锚定 1 张，未锚定 " + imp.unanchored + " 张");
    else bad("批量导入统计异常：" + JSON.stringify(imp));

    head("E. 写：更新");
    const upd = parseTool(await request("tools/call", {
      name: "folio_update_card", arguments: { cardId: newCardId, note: "笔记已改", star: false },
    }));
    if (upd && upd.updated && upd.note === "笔记已改") ok("folio_update_card 改笔记生效，且未破坏锚点");
    else bad("更新失败：" + JSON.stringify(upd));
    if (upd && upd.anchored) ok("更新后锚点仍在（paraIdx=" + upd.paraIdx + "）");
    else bad("更新后锚点丢失");

    head("F. 写：新建文献");
    const np = parseTool(await request("tools/call", {
      name: "folio_add_paper",
      arguments: {
        title: "连接器创建的测试文献", authors: "WB AI", year: "2026",
        tags: ["冒烟"], dueInDays: 3,
        text: "# 标题一\n\n这是第一段正文内容。\n\n## 2. 方法\n\n这是第二段正文。\n\n[1] 一条参考文献。",
      },
    }));
    if (np && np.paperId) ok("folio_add_paper 建文献成功，id=" + np.paperId.slice(0, 12) + "…");
    else bad("新建文献失败");
    if (np && np.paragraphs === 5) ok("纯文本自动切成 5 段（含 h1/h2/body/ref 分类）");
    else bad("段落切分数异常：" + (np && np.paragraphs));

    const today = parseTool(await request("tools/call", { name: "folio_today", arguments: {} }));
    if (today && Array.isArray(today.items)) {
      ok("folio_today 返回 " + today.items.length + " 项待办");
      if (today.items.some((i) => i.overdue)) ok("逾期项已标记 overdue（页面标红的依据）");
      else bad("未见逾期项，示例数据里应当有一条");
    } else bad("folio_today 返回异常");

    head("G. 错误处理");
    const badTool = await request("tools/call", { name: "folio_delete_card", arguments: { cardId: "x" } });
    if (badTool.result && badTool.result.isError) ok("调用不存在的删除工具返回 isError");
    else bad("错误处理失效");

    const badId = await request("tools/call", { name: "folio_get_card", arguments: { cardId: "nope" } });
    if (badId.result && badId.result.isError) ok("查不存在的卡片返回明确错误而非崩溃");
    else bad("错误处理失效");

    const noPaper = await request("tools/call", { name: "folio_add_card", arguments: { type: "KT", note: "无目标" } });
    if (!noPaper.error) ok("未指定文献时回落到当前文献，不报错");
    else bad("未指定文献时抛错");
  } catch (e) {
    bad("异常：" + e.message);
  } finally {
    try { child.kill(); } catch (_) {}
    try { fs.rmSync(TMP, { recursive: true, force: true }); } catch (_) {}
    console.log("\n" + "=".repeat(52));
    console.log("（测试数据目录已清理：" + TMP + "）");
    if (fail) console.log("连接器测试未通过：" + fail + " 项 FAIL / " + pass + " 项 PASS");
    else console.log("连接器测试全部通过（" + pass + " 项）");
    if (stderrLog.trim()) {
      console.log("\n--- 服务端日志 ---");
      console.log(stderrLog.trim().split("\n").slice(0, 12).join("\n"));
    }
    console.log("=".repeat(52));
    process.exit(fail ? 1 : 0);
  }
})();
