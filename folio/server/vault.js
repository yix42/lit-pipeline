/* =====================================================================
   ResearchVault 桥接层
   把 vault 的 L2 笔记与全文档案接进 Folio，供「引语闸门」审查使用。

   设计要点：
   - 判定逻辑**不在这里重新实现**，一律调 90_Meta/State/verify_note_quotes.py。
     那是权威基准（用户笔记里记录的闸门结果都出自它），归一化细节极多
     （HTML 实体 / NFKC / 弯引号 / C0 控制字符 / 连字符等价），
     在 JS 侧重写必然与它漂移 —— 两侧结果不一致比没有审查更糟。
   - 本模块只负责：定位 vault、定位解释器、调用、解析 JSON、缓存、换算。
   - 全程只读 vault（跑脚本用只读模式）；唯一写盘是给 --quotes-file 用的临时文件。
   ===================================================================== */
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

/* ---------------- vault 定位 ----------------
   换机可用：静态候选先认环境变量，再认家目录下的标准位置；
   坚果云那种「带版本号层级」的同步目录由 _dynCandidates() 现场扫出来，不写死用户名。 */
const VAULT_CANDIDATES = [
  process.env.FOLIO_VAULT_DIR,
  process.env.RESEARCH_VAULT,
  path.join(os.homedir(), "ResearchVault"),
  path.join(os.homedir(), "Nutstore", "1", "ResearchVault"),
  path.join(os.homedir(), "Nutstore Files", "1", "ResearchVault"),
  path.join(os.homedir(), "坚果云", "ResearchVault"),
  "C:\\Users\\xia\\Nutstore\\1\\ResearchVault",   // 原机（Windows）路径，保留作兜底
].filter(Boolean);

/* 家目录下形如 Nutstore* / 坚果云* 的同步目录，两种层级都试一遍 */
function _dynCandidates() {
  const out = [];
  try {
    const home = os.homedir();
    for (const d of fs.readdirSync(home)) {
      if (/nutstore|坚果云/i.test(d)) {
        out.push(path.join(home, d, "1", "ResearchVault"));
        out.push(path.join(home, d, "ResearchVault"));
      }
    }
  } catch (_) {}
  return out;
}

let _vaultCache;
function detectVault() {
  if (_vaultCache !== undefined) return _vaultCache;
  for (const c of VAULT_CANDIDATES.concat(_dynCandidates())) {
    try {
      if (fs.existsSync(path.join(c, "20_Notes"))) {
        _vaultCache = path.resolve(c);
        return _vaultCache;
      }
    } catch (_) {}
  }
  _vaultCache = null;
  return null;
}

function paths() {
  const vault = detectVault();
  if (!vault) return null;
  const stateDir = path.join(vault, "90_Meta", "State");
  return {
    vault,
    notes: path.join(vault, "20_Notes"),
    fulltext: path.join(vault, "40_Fulltext", "md"),
    script: process.env.FOLIO_VERIFY_SCRIPT ||
            path.join(stateDir, "verify_note_quotes.py"),
    // 引语修复脚本：与闸门同目录、共用同一套归一化引擎
    repairScript: process.env.FOLIO_REPAIR_SCRIPT ||
                  path.join(stateDir, "repair_note_quotes.py"),
    reportDir: process.env.FOLIO_REPORT_DIR ||
               path.join(stateDir, "_review"),
  };
}

/* ---------------- 解释器探测 ----------------
   顺序：FOLIO_PYTHON → python（PATH） → python3 → managed 绝对路径兜底。
   脚本只用标准库（html/json/os/re/sys/unicodedata），无需任何第三方包。 */
function detectPython() {
  const candidates = [process.env.FOLIO_PYTHON, "python", "python3"].filter(Boolean);
  // managed 解释器兜底：Glob 出实际版本目录，避免写死版本号
  try {
    const base = path.join(os.homedir(), ".workbuddy", "binaries", "python", "versions");
    if (fs.existsSync(base)) {
      for (const v of fs.readdirSync(base).sort().reverse()) {
        const exe = path.join(base, v, process.platform === "win32" ? "python.exe" : "bin/python3");
        if (fs.existsSync(exe)) candidates.push(exe);
      }
    }
  } catch (_) {}

  for (const c of candidates) {
    try {
      const r = spawnSync(c, ["-c", "import sys;print(sys.version_info[0])"], {
        encoding: "utf8", timeout: 15000, windowsHide: true,
      });
      if (r.status === 0 && String(r.stdout).trim() === "3") return c;
    } catch (_) {}
  }
  return null;
}

/* ---------------- 状态 ---------------- */
function info() {
  const p = paths();
  if (!p) {
    return {
      ok: false,
      error: "vault-not-found",
      tried: VAULT_CANDIDATES.concat(_dynCandidates()),
      hint: "设置环境变量 FOLIO_VAULT_DIR（或 RESEARCH_VAULT）指向 vault 根目录（须含 20_Notes）",
    };
  }
  const has = (d) => { try { return fs.existsSync(d); } catch (_) { return false; } };
  const count = (d, re) => {
    try { return fs.readdirSync(d).filter((f) => (re ? re.test(f) : true)).length; }
    catch (_) { return 0; }
  };
  const py = detectPython();
  return {
    ok: true,
    vault: p.vault,
    notes: p.notes,
    notesCount: count(p.notes, /\.md$/),
    fulltextCount: count(p.fulltext, /\.md$/),
    script: p.script,
    scriptExists: has(p.script),
    repairScript: p.repairScript,
    repairScriptExists: has(p.repairScript),
    python: py,
    ready: !!(py && has(p.script) && has(p.notes) && has(p.fulltext)),
  };
}

/* ---------------- L2 笔记清单 ---------------- */
/* 文件名约定：{zotero_key}_{slug}_{year}.md */
function listNotes() {
  const p = paths();
  if (!p) return [];
  let files = [];
  try { files = fs.readdirSync(p.notes); } catch (_) { return []; }
  const out = [];
  for (const f of files) {
    if (!f.endsWith(".md") || f === "_Index.md") continue;
    const m = /^([A-Z0-9]{8})_/.exec(f);
    if (!m) continue;
    out.push({ key: m[1], file: f });
  }
  return out.sort((a, b) => a.key.localeCompare(b.key));
}

/* 目录签名：文件数 + mtime 之和。任何文件改动都会让签名变化，用于缓存失效 */
function dirSig(dir) {
  let n = 0, sum = 0;
  try {
    for (const f of fs.readdirSync(dir)) {
      try { sum += fs.statSync(path.join(dir, f)).mtimeMs; n++; } catch (_) {}
    }
  } catch (_) {}
  return n + ":" + Math.round(sum);
}
function vaultSig() {
  const p = paths();
  if (!p) return "none";
  return dirSig(p.notes) + "|" + dirSig(p.fulltext);
}

/* ---------------- 调用闸门脚本 ----------------
   opts.script 可换成 repair_note_quotes.py（同目录、共用归一化引擎）。 */
function runScript(args, opts) {
  opts = opts || {};
  const p = paths();
  if (!p) return { ok: false, error: "vault-not-found" };
  const py = detectPython();
  if (!py) return { ok: false, error: "python-not-found" };
  const script = opts.script || p.script;
  if (!fs.existsSync(script)) return { ok: false, error: "script-not-found", script };

  const env = Object.assign({}, process.env, { RESEARCH_VAULT: p.vault });
  const r = spawnSync(py, [script].concat(args), {
    encoding: "utf8",
    timeout: opts.timeout || 300000,
    maxBuffer: 64 * 1024 * 1024,
    windowsHide: true,
    cwd: path.dirname(script),   // 脚本按 script 位置探测 vault 时用得上
    env,
  });
  if (r.error) return { ok: false, error: "spawn-failed", message: r.error.message };
  if (r.status !== 0) {
    return {
      ok: false,
      error: "script-exit-" + r.status,
      stderr: String(r.stderr || "").trim().slice(0, 1200),
    };
  }
  return { ok: true, stdout: r.stdout, stderr: String(r.stderr || "") };
}

/* 解析脚本的 JSON 出口。所有 JSON 模式都 exit 0，失败写进 ok/error。 */
function _parse(r) {
  if (!r.ok) return r;
  try {
    return JSON.parse(r.stdout);
  } catch (e) {
    return { ok: false, error: "bad-json", message: e.message, head: String(r.stdout).slice(0, 400) };
  }
}

function _keysOf(keys) {
  return Array.isArray(keys) && keys.length
    ? keys.map((k) => String(k).trim().toUpperCase()).filter(Boolean)
    : [];
}

/* 全库（或指定 key）跑引语闸门。
   opts.noReport=true 时不落归档报告、也不读缓存 —— 用于「落笔后复测」这种一次性调用，
   否则会拿单篇结果覆盖掉 _review/ 里那份全库报告。 */
let _gateCache = { sig: "", keys: "", data: null };
function reviewNotes(keys, opts) {
  const noReport = !!(opts && opts.noReport);
  const p = paths();
  if (!p) return { ok: false, error: "vault-not-found" };

  const keyList = _keysOf(keys);
  const keySig = keyList.length ? keyList.join(",") : "*";
  const sig = vaultSig();

  if (!noReport && _gateCache.data && _gateCache.sig === sig && _gateCache.keys === keySig) {
    return Object.assign({ cached: true }, _gateCache.data);
  }

  /* 顺手把可归档报告落到 reportDir（_review/引语闸门_<日期>.md）。
     只写那一个目录、只在这一条路径上写——报告是核验的凭据，
     此前它是人手抄进 _Index.md 的，抄错没人发现。 */
  const args = keyList.concat(["--json"]);
  if (!noReport) args.push("--report-dir", p.reportDir);
  const r = runScript(args, { timeout: 600000 });
  const data = _parse(r);
  if (!data.ok) return data;

  data.byMiss = (data.results || [])
    .filter((x) => x.miss > 0)
    .sort((a, b) => b.miss - a.miss)
    .map((x) => ({ key: x.key, miss: x.miss, total: x.total, misses: x.misses }));

  // 只有「带归档报告」的调用才进缓存 —— 否则复测结果会把 report 字段漏给后续调用
  if (!noReport) _gateCache = { sig, keys: keySig, data };
  return Object.assign({ cached: false }, data);
}

/* 对任意引语列表做判定（Folio 卡片复用同一引擎）
   写一个临时 JSON 交给脚本 --quotes-file，跑完即删。

   corpusFiles 给定时以它为语料（{名称: 正文}），否则用 vault 的 40_Fulltext。
   —— Folio 卡片的原文在 Folio 自己的 paragraphs 里、不在 vault 档案中，
   不传语料会把整批卡片误判成未命中。 */
function reviewQuotes(items, corpusFiles) {
  const p = paths();
  if (!p) return { ok: false, error: "vault-not-found" };
  const list = (Array.isArray(items) ? items : []).filter((x) => x && String(x.quote || "").trim());
  if (!list.length) return { ok: true, quotes: 0, totals: { total: 0, strict: 0, loose: 0, miss: 0 }, items: [] };

  const tag = "folio-q-" + process.pid + "-" + Date.now();
  const tmp = path.join(os.tmpdir(), tag + ".json");
  let corpusDir = null;
  try {
    fs.writeFileSync(tmp, JSON.stringify(list), "utf8");
    const args = ["--quotes-file", tmp, "--json"];

    if (corpusFiles && Object.keys(corpusFiles).length) {
      corpusDir = fs.mkdtempSync(path.join(os.tmpdir(), tag + "-"));
      for (const [name, body] of Object.entries(corpusFiles)) {
        // 文件名会原样成为脚本里的语料 key，故只保留安全字符
        const safe = String(name).replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 80) || "doc";
        fs.writeFileSync(path.join(corpusDir, safe + ".md"), String(body || ""), "utf8");
      }
      args.push("--corpus-dir", corpusDir);
    }

    const r = runScript(args, { timeout: 300000 });
    if (!r.ok) return r;
    try {
      return Object.assign({ ok: true }, JSON.parse(r.stdout));
    } catch (e) {
      return { ok: false, error: "bad-json", message: e.message, head: String(r.stdout).slice(0, 400) };
    }
  } finally {
    try { fs.unlinkSync(tmp); } catch (_) {}
    if (corpusDir) { try { fs.rmSync(corpusDir, { recursive: true, force: true }); } catch (_) {} }
  }
}

/* 覆盖度：笔记里应有的引语 vs 已收进 Folio 的引语，报出差集。
   归一化与子串判定全部交给脚本（--coverage-file），本层只负责传参与解析。 */
function coverage(key, have) {
  const p = paths();
  if (!p) return { ok: false, error: "vault-not-found" };
  const tmp = path.join(os.tmpdir(), "folio-cov-" + process.pid + "-" + Date.now() + ".json");
  try {
    fs.writeFileSync(tmp, JSON.stringify({
      key: String(key || "").trim().toUpperCase(),
      have: Array.isArray(have) ? have : [],
    }), "utf8");
    const r = runScript(["--coverage-file", tmp, "--json"], { timeout: 300000 });
    if (!r.ok) return r;
    try {
      return JSON.parse(r.stdout);
    } catch (e) {
      return { ok: false, error: "bad-json", message: e.message, head: String(r.stdout).slice(0, 400) };
    }
  } finally {
    try { fs.unlinkSync(tmp); } catch (_) {}
  }
}

/* ---------------- 引语修复（诊断 → 逐条确认 → 才落笔） ----------------
   ⚠️ 这是本模块**唯一会写 vault 的路径**（写 20_Notes 里的笔记）。
   闸门脚本只诊断；修复脚本自己负责「落笔前把笔记快照到库外」。
   Folio 侧只做两件事：把诊断结果原样端出去、把点名的 id 原样递进去 ——
   绝不在这一层「顺手全修」，判定与准入全在脚本里（唯一真源）。 */
function repairDiagnose(keys) {
  const p = paths();
  if (!p) return { ok: false, error: "vault-not-found" };
  if (!fs.existsSync(p.repairScript)) {
    return { ok: false, error: "repair-script-not-found", script: p.repairScript };
  }
  const args = _keysOf(keys).concat(["--json"]);
  return _parse(runScript(args, { script: p.repairScript, timeout: 600000 }));
}

/* ids 非空才会走到这里；空数组直接拒绝，避免「不传参数 = 全修」这种默认。 */
function repairApply(ids, keys) {
  const p = paths();
  if (!p) return { ok: false, error: "vault-not-found" };
  const list = (Array.isArray(ids) ? ids : []).map((x) => String(x).trim()).filter(Boolean);
  if (!list.length) return { ok: false, error: "no-ids", message: "必须显式点名要落笔的 id" };
  if (!fs.existsSync(p.repairScript)) {
    return { ok: false, error: "repair-script-not-found", script: p.repairScript };
  }
  const tmp = path.join(os.tmpdir(), "folio-repair-" + process.pid + "-" + Date.now() + ".json");
  try {
    fs.writeFileSync(tmp, JSON.stringify({ ids: list }), "utf8");
    const args = ["--apply-ids", tmp, "--json"].concat(_keysOf(keys));
    const out = _parse(runScript(args, { script: p.repairScript, timeout: 600000 }));
    if (out && out.ok) clearCache();   // 笔记变了，闸门缓存必须作废
    return out;
  } finally {
    try { fs.unlinkSync(tmp); } catch (_) {}
  }
}

function clearCache() { _gateCache = { sig: "", keys: "", data: null }; }

module.exports = {
  detectVault, detectPython, paths, info,
  listNotes, reviewNotes, reviewQuotes, coverage,
  repairDiagnose, repairApply, clearCache, vaultSig,
};
