/* =====================================================================
   数据层：读写 data/folio.json
   - 原子写入（临时文件 + rename），避免写坏
   - 写前自动留存一份带时间戳的快照，最多保留 MAX_BACKUP 份
   - 旧文件名 litdesk.json 会在首次启动时自动迁过来，已有数据不丢
   ===================================================================== */
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = path.join(__dirname, "..");
/* 允许多开互不干扰，也让测试跑在沙箱里而不弄脏真实数据：
   设 FOLIO_DATA_DIR（或旧名 LITDESK_DATA_DIR）即可把整棵 data 目录迁走。 */
const ENV_DIR = process.env.FOLIO_DATA_DIR || process.env.LITDESK_DATA_DIR
  ? path.resolve(process.env.FOLIO_DATA_DIR || process.env.LITDESK_DATA_DIR)
  : null;
const DATA_DIR = ENV_DIR || path.join(ROOT, "data");
const BACKUP_DIR = path.join(DATA_DIR, "backups");
const DATA_FILE = path.join(DATA_DIR, "folio.json");
const LEGACY_FILE = path.join(DATA_DIR, "litdesk.json");
const MAX_BACKUP = 20;
const SCHEMA_VERSION = 1;

/* 兼容旧版：若存在 litdesk.json 而没有 folio.json，直接改名为新版文件名。
   只做一次，且只在没有新文件时做 —— 绝不覆盖已有的新数据。 */
function migrateLegacy() {
  try {
    if (fs.existsSync(DATA_FILE) || !fs.existsSync(LEGACY_FILE)) return;
    fs.renameSync(LEGACY_FILE, DATA_FILE);
    try { process.stderr.write("[folio] 已把旧数据文件 litdesk.json 迁移为 folio.json\n"); } catch (_) {}
  } catch (e) {
    try { process.stderr.write("[folio] 旧数据文件迁移失败：" + e.message + "\n"); } catch (_) {}
  }
}

/* ---------------- 基础读写 ---------------- */
function ensureDirs() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.mkdirSync(BACKUP_DIR, { recursive: true });
  migrateLegacy();
}

function emptyState() {
  return { version: SCHEMA_VERSION, papers: [], cards: [], curPaperId: null, updatedAt: "" };
}

function nowStr() {
  const d = new Date();
  const p2 = (n) => (n < 10 ? "0" + n : "" + n);
  return (
    d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate()) +
    " " + p2(d.getHours()) + ":" + p2(d.getMinutes()) + ":" + p2(d.getSeconds())
  );
}

function todayStr() {
  const d = new Date();
  const p2 = (n) => (n < 10 ? "0" + n : "" + n);
  return d.getFullYear() + "-" + p2(d.getMonth() + 1) + "-" + p2(d.getDate());
}

/* 归一化：保证字段齐全、类型正确。缺字段补默认值，脏数据不让它崩流程 */
function normalize(raw) {
  const st = emptyState();
  if (!raw || typeof raw !== "object") return st;

  st.version = SCHEMA_VERSION;
  st.curPaperId = typeof raw.curPaperId === "string" ? raw.curPaperId : null;
  st.updatedAt = typeof raw.updatedAt === "string" ? raw.updatedAt : "";

  const seenPaper = new Set();
  st.papers = (Array.isArray(raw.papers) ? raw.papers : []).map((p) => {
    if (!p || typeof p !== "object") return null;
    const id = typeof p.id === "string" && p.id ? p.id : "p-" + crypto.randomUUID();
    if (seenPaper.has(id)) return null;
    seenPaper.add(id);
    return {
      id,
      title: String(p.title || "").trim(),
      authors: String(p.authors || "").trim(),
      journal: String(p.journal || "").trim(),
      year: String(p.year || "").trim(),
      doi: String(p.doi || "").trim(),
      tags: Array.isArray(p.tags) ? p.tags.map((t) => String(t)) : [],
      status: ["待读", "在读", "已读"].includes(p.status) ? p.status : "待读",
      mtype: typeof p.mtype === "string" ? p.mtype : "KC",
      due: typeof p.due === "string" ? p.due : "",
      createdAt: typeof p.createdAt === "string" ? p.createdAt : "",
      source: typeof p.source === "string" ? p.source : "",
      paragraphs: (Array.isArray(p.paragraphs) ? p.paragraphs : []).map((q) => ({
        page: Number.isFinite(q && q.page) ? q.page : 1,
        type: ["h1", "h2", "h3", "body", "ref"].includes(q && q.type) ? q.type : "body",
        text: String((q && q.text) || ""),
      })),
    };
  }).filter(Boolean);

  st.cards = (Array.isArray(raw.cards) ? raw.cards : []).map((c) => {
    if (!c || typeof c !== "object") return null;
    const pid = typeof c.paperId === "string" ? c.paperId : "";
    if (!seenPaper.has(pid)) return null; // 孤儿卡片直接丢弃，与前端一致
    return {
      id: typeof c.id === "string" && c.id ? c.id : "c-" + crypto.randomUUID(),
      paperId: pid,
      type: typeof c.type === "string" ? c.type : "NT",
      quote: String(c.quote || ""),
      note: String(c.note || ""),
      comment: String(c.comment || ""),
      tags: Array.isArray(c.tags) ? c.tags.map((t) => String(t)) : [],
      star: !!c.star,
      pinned: !!c.pinned,
      paraIdx: Number.isInteger(c.paraIdx) ? c.paraIdx : null,
      start: Number.isInteger(c.start) ? c.start : null,
      end: Number.isInteger(c.end) ? c.end : null,
      createdAt: typeof c.createdAt === "string" ? c.createdAt : "",
      /* 来源 vault 的 zotero_key（从 L2 笔记导入时写入）。
         ⚠️ normalize() 是白名单构造 —— 新字段不在这里登记会被静默丢弃，
         现象还像「同步失败」。加字段务必同步加在这里。 */
      sourceKey: typeof c.sourceKey === "string" ? c.sourceKey : "",
    };
  }).filter(Boolean);

  if (!st.curPaperId || !st.papers.some((p) => p.id === st.curPaperId)) {
    st.curPaperId = st.papers.length ? st.papers[0].id : null;
  }
  return st;
}

function readState() {
  ensureDirs();
  if (!fs.existsSync(DATA_FILE)) return emptyState();
  let txt;
  try {
    txt = fs.readFileSync(DATA_FILE, "utf8");
  } catch (e) {
    throw new Error("数据文件读取失败: " + e.message);
  }
  if (!txt.trim()) return emptyState();
  try {
    return normalize(JSON.parse(txt));
  } catch (e) {
    // 文件损坏时不静默清空：先救护一份，再用空状态跑起来
    const rescue = path.join(BACKUP_DIR, "corrupt-" + Date.now() + ".json");
    try { fs.copyFileSync(DATA_FILE, rescue); } catch (_) {}
    throw new Error(
      "数据文件 JSON 解析失败，已把原文件隔离到 " + rescue + "。错误：" + e.message
    );
  }
}

function rotateBackup() {
  try {
    if (!fs.existsSync(DATA_FILE)) return;
    const files = fs.readdirSync(BACKUP_DIR)
      .filter((f) => /^(folio|litdesk)-\d{8}-\d{6}\.json$/.test(f))
      .sort();
    while (files.length >= MAX_BACKUP) {
      fs.unlinkSync(path.join(BACKUP_DIR, files.shift()));
    }
    const d = new Date();
    const p2 = (n) => (n < 10 ? "0" + n : "" + n);
    const stamp =
      d.getFullYear() + p2(d.getMonth() + 1) + p2(d.getDate()) + "-" +
      p2(d.getHours()) + p2(d.getMinutes()) + p2(d.getSeconds());
    // 只在内容真的变了时才留快照，避免每次刷新都堆一堆无意义备份
    const snap = path.join(BACKUP_DIR, "folio-" + stamp + ".json");
    fs.copyFileSync(DATA_FILE, snap);
  } catch (_) {
    // 备份失败不该阻断主流程
  }
}

function writeState(st) {
  ensureDirs();
  rotateBackup();
  const payload = Object.assign({}, normalize(st), { updatedAt: nowStr() });
  const tmp = DATA_FILE + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(payload, null, 2), "utf8");
  fs.renameSync(tmp, DATA_FILE);
  return payload;
}

/* ---------------- 写入串行化 ----------------
   页面与 MCP 可能同时到达，用一条 Promise 链把所有写操作排队，
   保证 read-modify-write 不会互相覆盖。 */
let _queue = Promise.resolve();
/* 回调除了返回补丁后的 state，还可以挂 __report（要回传给调用方的结构化结果）
   或 __no（中止写入并说明原因）。这两个字段不属于 state，写入前会被摘掉，
   再经 meta 带出来 —— 因为 writeState 内部会做 normalize，直接放 state 里会被丢掉。 */
function mutate(fn) {
  const run = async () => {
    const latest = readState(); // 每次写入前重读磁盘，拿到别的写者的最新结果
    const next = fn(latest);
    if (next === false) return { ok: false, skipped: true, state: latest, meta: null };
    const patched = next || latest;
    const meta = {
      report: patched.__report || null,
      aborted: !!patched.__no,
      reason: patched.__no ? patched.__no.reason || "" : "",
    };
    delete patched.__report;
    delete patched.__no;
    const saved = writeState(patched);
    return { ok: true, state: saved, meta };
  };
  const p = _queue.then(run, run);
  _queue = p.catch(() => {});
  return p;
}

function stats() {
  let bytes = 0;
  try { bytes = fs.statSync(DATA_FILE).size; } catch (_) {}
  return { bytes, file: DATA_FILE, backupsDir: BACKUP_DIR };
}

module.exports = {
  readState, writeState, mutate, normalize, emptyState,
  nowStr, todayStr, stats, ensureDirs,
  DATA_FILE, DATA_DIR, BACKUP_DIR,
};
