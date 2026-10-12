/* =====================================================================
   HTTP 服务 —— 给浏览器页面用的 REST 通道
   同时静态托管整个工作台目录，这样从 http://localhost:PORT 打开
   页面时不存在跨域问题；从 file:// 双击打开时靠 CORS 头放行。
   ===================================================================== */
"use strict";
const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");
const store = require("./store");
const tools = require("./tools");

const ROOT = path.join(__dirname, "..");
/* 新名 FOLIO_PORT 优先，旧名 LITDESK_PORT 仍然认 —— 不让改名搞挂已有配置 */
const PORT = Number(process.env.FOLIO_PORT || process.env.LITDESK_PORT || 8787);
const HOST = process.env.FOLIO_HOST || process.env.LITDESK_HOST || "127.0.0.1";

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".pdf": "application/pdf",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".md": "text/markdown; charset=utf-8",
};

function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
  });
  res.end(body);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let b = "";
    req.on("data", (c) => {
      b += c;
      if (b.length > 40 * 1024 * 1024) { reject(new Error("请求体过大")); req.destroy(); }
    });
    req.on("end", () => {
      if (!b) return resolve({});
      try { resolve(JSON.parse(b)); } catch (e) { reject(new Error("JSON 解析失败: " + e.message)); }
    });
    req.on("error", reject);
  });
}

/* 静态文件托管。注意防目录穿越 */
function serveStatic(req, res, pathname) {
  let rel = decodeURIComponent(pathname);
  if (rel === "/" || rel === "") rel = "/app.html";
  const abs = path.normalize(path.join(ROOT, rel));
  if (!abs.startsWith(ROOT)) { res.writeHead(403); return res.end("forbidden"); }
  // 数据备份目录不对外暴露
  if (abs.includes(path.sep + "data" + path.sep)) { res.writeHead(403); return res.end("forbidden"); }
  fs.stat(abs, (e, st) => {
    if (e || !st.isFile()) { res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" }); return res.end("404"); }
    const ext = path.extname(abs).toLowerCase();
    res.writeHead(200, {
      "Content-Type": MIME[ext] || "application/octet-stream",
      "Content-Length": st.size,
      "Cache-Control": ext === ".html" ? "no-store" : "public, max-age=300",
      "Access-Control-Allow-Origin": "*",
    });
    fs.createReadStream(abs).pipe(res);
  });
}

async function handleAPI(req, res, pathname) {
  try {
    if (pathname === "/api/ping") {
      return json(res, 200, { ok: true, service: "folio", port: PORT, now: store.nowStr() });
    }
    if (pathname === "/api/state") {
      if (req.method === "GET") {
        const st = store.readState();
        return json(res, 200, { ok: true, state: st });
      }
      if (req.method === "PUT" || req.method === "POST") {
        const body = await readBody(req);
        if (!body || !body.state) return json(res, 400, { ok: false, error: "缺少 state 字段" });
        const saved = store.writeState(body.state);
        return json(res, 200, { ok: true, updatedAt: saved.updatedAt });
      }
      return json(res, 405, { ok: false, error: "不支持的方法" });
    }
    /* MCP over HTTP：给调试用，也方便将来挂别的客户端 */
    if (pathname === "/api/tools") {
      return json(res, 200, { ok: true, tools: tools.TOOLS.map((t) => t.name) });
    }
    if (pathname === "/api/call") {
      if (req.method !== "POST") return json(res, 405, { ok: false, error: "请用 POST" });
      const body = await readBody(req);
      const out = await tools.callTool(body.name, body.args || {});
      return json(res, 200, { ok: true, result: out });
    }
    return json(res, 404, { ok: false, error: "未知接口 " + pathname });
  } catch (e) {
    return json(res, 500, { ok: false, error: e.message });
  }
}

function createServer() {
  return http.createServer((req, res) => {
    const pathname = url.parse(req.url).pathname;
    if (req.method === "OPTIONS") {
      res.writeHead(204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      });
      return res.end();
    }
    if (pathname.startsWith("/api/")) return void handleAPI(req, res, pathname);
    serveStatic(req, res, pathname);
  });
}

/* 端口占用检测：MCP 进程启动时若发现已有服务在跑，就复用它而不是报错退出 */
function probePort(port) {
  return new Promise((resolve) => {
    const req = http.request(
      { host: HOST, port, path: "/api/ping", method: "GET", timeout: 800 },
      (res) => {
        let b = "";
        res.on("data", (c) => (b += c));
        res.on("end", () => resolve(b.includes('"folio"')));
      }
    );
    req.on("timeout", () => { req.destroy(); resolve(false); });
    req.on("error", () => resolve(false));
    req.end();
  });
}

function listen(port) {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.once("error", reject);
    srv.listen(port, HOST, () => resolve(srv));
  });
}

module.exports = { createServer, listen, probePort, PORT, HOST };

/* 直接运行时，当常驻服务启动 */
if (require.main === module) {
  store.ensureDirs();
  listen(PORT)
    .then((srv) => {
      console.log("文献工作台服务已启动");
      console.log("  数据文件：" + store.DATA_FILE);
      console.log("  页面地址：http://" + HOST + ":" + PORT + "/");
      console.log("  按 Ctrl+C 停止");
      const stop = () => { try { srv.close(); } catch (_) {} process.exit(0); };
      process.on("SIGINT", stop);
      process.on("SIGTERM", stop);
    })
    .catch((e) => {
      if (e.code === "EADDRINUSE") {
        console.error("端口 " + PORT + " 已被占用 —— 服务应该已经在运行了。");
        console.error("直接打开 http://" + HOST + ":" + PORT + "/ 即可。");
        process.exit(0);
      }
      console.error("启动失败：" + e.message);
      process.exit(1);
    });
}
