---
name: zotero-mcp-connector
description: Connect a Zotero research library to WorkBuddy as an MCP connector using drxaibi/zotero-mcp. Covers local (read-only, offline) and Web API (read/write, citations) modes, building the native module, resolving the numeric User ID from the API key, and an MCP stdio smoke test. Use when the user says "connect Zotero", "接 Zotero", "Zotero MCP", or wants AI to read/search their Zotero library or generate citations.
---

# Zotero MCP Connector (drxaibi/zotero-mcp)

Connect a Zotero library to WorkBuddy. Two backends:

- **Web API mode** (recommended for active users): Zotero can stay open; `get_bibliography` (citation generation) works. Needs a Zotero API key + numeric User ID.
- **Local mode** (offline, no key): reads `~/Zotero/zotero.sqlite` directly. Requires Zotero to be **closed** during queries (SQLite/WAL lock). `get_bibliography` is DISABLED in local mode.

## Steps

### 1. Clone + build (native module needs Xcode CLT)
```bash
mkdir -p ~/.workbuddy/mcp-servers
git clone https://github.com/drxaibi/zotero-mcp.git ~/.workbuddy/mcp-servers/zotero-mcp
cd ~/.workbuddy/mcp-servers/zotero-mcp
export PATH=/Users/macintosh/.workbuddy/binaries/node/versions/22.22.2-2/bin:$PATH
npm install && npm run build   # better-sqlite3 compiles natively; needs `xcode-select --install`
ls dist/index.js               # entry point
```
Entry: `~/.workbuddy/mcp-servers/zotero-mcp/dist/index.js`. Use the managed node binary as `command`.

### 2. Get credentials (Web mode)
- Go to https://www.zotero.org/settings/keys → "Create new private key".
- Permissions: ✅ library access, ✅ notes access; ❌ write.
- The key shows ONLY ONCE. Copy it fully (watch 0/O, 1/l/I, no trailing spaces).
- The page TOP shows the numeric **User ID** (e.g. "Your user ID is 21540183"). A Zotero *username* will NOT work in the API path — it must be the numeric ID.

### 3. Resolve numeric User ID from the key (no need to read the page)
```bash
curl -s "https://api.zotero.org/keys/<API_KEY>"
# → {"key":"...","userID":21540183,"username":"...","access":{...}}
```
If this returns "not found" / "Invalid key", the key is mistyped or was never saved → recreate it.

### 4. Write `~/.workbuddy/mcp.json` (merge into existing `mcpServers`)
```json
{
  "mcpServers": {
    "zotero": {
      "command": "/Users/macintosh/.workbuddy/binaries/node/versions/22.22.2-2/bin/node",
      "args": ["/Users/macintosh/.workbuddy/mcp-servers/zotero-mcp/dist/index.js"],
      "env": {
        "ZOTERO_MODE": "web",
        "ZOTERO_USER_ID": "<numeric-id>",
        "ZOTERO_API_KEY": "<api-key>"
      },
      "disabled": false
    },
    "zotero-local": {
      "command": "/Users/macintosh/.workbuddy/binaries/node/versions/22.22.2-2/bin/node",
      "args": ["/Users/macintosh/.workbuddy/mcp-servers/zotero-mcp/dist/index.js"],
      "env": { "ZOTERO_MODE": "local", "ZOTERO_DATA_DIR": "/Users/macintosh/Zotero" },
      "disabled": false
    }
  }
}
```
Keep both entries so the user can pick. Then the user must open the connector management page (top-right custom connectors) and click **Trust** for the server to activate.

### 5. Smoke test (MCP stdio, no client needed)
Pipe JSON-RPC lines: `initialize` → `notifications/initialized` → tool calls.
```bash
printf '%s\n%s\n%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}' \
'{"jsonrpc":"2.0","method":"notifications/initialized"}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_recent_items","arguments":{"days":30,"limit":3}}}' \
| ZOTERO_MODE=web ZOTERO_USER_ID=<id> ZOTERO_API_KEY=<key> \
  /Users/macintosh/.workbuddy/binaries/node/versions/22.22.2-2/bin/node \
  /Users/macintosh/.workbuddy/mcp-servers/zotero-mcp/dist/index.js
```
macOS has no `timeout`; `printf` closing stdin makes the server exit. Local mode will return `database is locked` if Zotero is open — that is expected, not a bug.

## Tools available (12)
search_library, search_fulltext, get_item, get_item_fulltext, get_item_notes, get_item_annotations, list_collections, get_collection_items, list_tags, get_bibliography (web only), get_related_items, get_recent_items.

## Gotchas
- Numeric User ID, not username, in the API path (`users/<numeric>`).
- Key shown only once → if lost, delete & recreate.
- Local mode: close Zotero first; no citation generation.
- Never leave the API key in /tmp test scripts — delete them after verifying.
