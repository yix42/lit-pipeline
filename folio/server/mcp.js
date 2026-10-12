/* =====================================================================
   MCP server（stdio 传输）—— 给 WorkBuddy 调用
   协议版本 2024-11-05，自己实现 JSON-RPC 分帧，不引第三方依赖。

   关键设计：进程启动时会试着在同一端口拉起 HTTP 服务。
   - 端口空闲 → 自己起，页面与 AI 读写同一进程
   - 端口已占用 → 说明常驻服务已在跑，MCP 只读写同一份磁盘文件（store 层
     每次写入前都会重读，因此两个写者不会互相覆盖整份数据）
   无论哪种情况，AI 的改动刷新页面都能看到。
   ===================================================================== */
"use strict";
const httpAPI = require("./http");
const store = require("./store");
const tools = require("./tools");

const PROTOCOL = "2024-11-05";
const SERVER_INFO = { name: "folio", version: "1.0.0" };

/* ---------------- stdout 必须是干净的协议流，日志一律走 stderr ---------------- */
function log(...args) {
  try { process.stderr.write("[folio] " + args.join(" ") + "\n"); } catch (_) {}
}

function send(obj) {
  const s = JSON.stringify(obj);
  process.stdout.write(s + "\n");
}

let _idSeq = 0;
const _pending = new Map();

function onMessage(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch (e) {
    return; // 非 JSON 行直接忽略，不回错误，避免和 stdin 里的噪声互相刷屏
  }
  if (Array.isArray(msg)) return msg.forEach(handleOne);
  handleOne(msg);
}

async function handleOne(msg) {
  if (!msg || typeof msg !== "object") return;
  const { id, method, params } = msg;

  // 对方在回应我们发出的请求（将来扩展采样/引导时会用到）
  if (id !== undefined && _pending.has(id)) {
    const resolve = _pending.get(id);
    _pending.delete(id);
    return resolve(msg);
  }
  if (method && method.startsWith("notifications/")) return; // 通知无需回复

  try {
    let result;
    switch (method) {
      case "initialize":
        result = {
          protocolVersion: PROTOCOL,
          capabilities: { tools: { listChanged: false } },
          serverInfo: SERVER_INFO,
          instructions:
            "Folio 文献工作台连接器。建议先跑 folio_status 确认数据已连通，再用 folio_list_papers 找文献 id。\n" +
            "给 AI 批量生成阅读卡用 folio_import_cards，quote 字段必须是原文里真实存在的连续句子，否则无法锚定到正文。\n" +
            "本连接器不提供任何删除操作。",
        };
        break;

      case "tools/list":
        result = { tools: tools.TOOLS };
        break;

      case "tools/call": {
        const name = params && params.name;
        const args = (params && params.arguments) || {};
        if (!name) throw new Error("缺少工具名");
        const out = await tools.callTool(name, args);
        result = out;
        break;
      }

      case "resources/list":
        result = { resources: [] };
        break;
      case "prompts/list":
        result = { prompts: [] };
        break;
      case "ping":
        result = {};
        break;

      default:
        // 未知方法按 JSON-RPC 约定回 method not found
        if (id === undefined) return;
        return send({ jsonrpc: "2.0", id, error: { code: -32601, message: "不支持的方法: " + method } });
    }
    if (id !== undefined) send({ jsonrpc: "2.0", id, result });
  } catch (e) {
    log("处理 " + method + " 出错: " + (e && e.stack ? e.stack : e));
    if (id !== undefined) {
      send({ jsonrpc: "2.0", id, error: { code: -32603, message: String((e && e.message) || e) } });
    }
  }
}

/* ---------------- stdio 分帧：按行切 JSON ---------------- */
function bootStdio() {
  let buf = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) onMessage(line);
    }
  });
  process.stdin.on("close", () => {
    log("stdin 关闭，退出");
    process.exit(0);
  });
  process.stdin.on("error", (e) => log("stdin 错误: " + e.message));
}

async function main() {
  store.ensureDirs();
  bootStdio();

  try {
    const alive = await httpAPI.probePort(httpAPI.PORT);
    if (alive) {
      log("检测到已有服务在端口 " + httpAPI.PORT + "，复用它");
      log("数据文件：" + store.DATA_FILE);
    } else {
      const srv = await httpAPI.listen(httpAPI.PORT);
      log("HTTP 服务已启动 http://" + httpAPI.HOST + ":" + httpAPI.PORT + "/");
      log("数据文件：" + store.DATA_FILE);
      const stop = () => { try { srv.close(); } catch (_) {} process.exit(0); };
      process.on("SIGINT", stop);
      process.on("SIGTERM", stop);
    }
  } catch (e) {
    // HTTP 起不来不影响 MCP 本身 —— 工具直接读写数据文件仍然可用
    log("HTTP 服务未能启动（" + e.message + "），MCP 仍可直接读写数据文件");
  }
  log("MCP 就绪，等待请求");
}

process.on("uncaughtException", (e) => log("未捕获异常: " + (e && e.stack ? e.stack : e)));
process.on("unhandledRejection", (e) => log("未处理的 Promise 拒绝: " + (e && e.stack ? e.stack : e)));

main();
