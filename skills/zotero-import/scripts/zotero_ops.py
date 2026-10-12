#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small Zotero local-API helper (read + per-item write) for the VTH literature line.

Loads ~/.workbuddy/zotero_local_auth.json. Zotero desktop must be running with the
local API enabled.

Usage examples are in __main__ at the bottom; the functions are importable.
"""
import json
import urllib.request
import urllib.error
from pathlib import Path

AUTH = Path.home() / ".workbuddy" / "zotero_local_auth.json"


def _auth():
    return json.loads(AUTH.read_text(encoding="utf-8"))


def _req(method, path, body=None, raw=False):
    a = _auth()
    url = a["base_url"] + path
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Zotero-API-Version", "3")
    req.add_header("Zotero-Server-ID", a["server_id"])
    req.add_header("Zotero-API-Key", a["api_key"])
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = r.read()
            if raw:
                return r.status, payload
            return r.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def user_id():
    return _auth()["user_id"]


def get_item(key):
    st, d = _req("GET", f"/api/users/{user_id()}/items/{key}?format=json")
    return d


def patch_item(key, fields):
    """fields e.g. {'collections': [...], 'tags': [...]}  -> 204 on success."""
    d = get_item(key)
    if not isinstance(d, dict):
        return None, d
    version = d["version"]
    body = {"key": key, "version": version}
    body.update(fields)
    st, res = _req("POST", f"/api/users/{user_id()}/items", [body])
    return st, res


def delete_collection(key):
    st, res = _req("DELETE", f"/api/users/{user_id()}/collections/{key}")
    return st, res


def list_collections():
    st, d = _req("GET", f"/api/users/{user_id()}/collections?limit=100&format=json")
    return {c["key"]: (c["data"]["name"], c["data"].get("parentCollection") or None) for c in d}


def collection_items(key, limit=100):
    out, start = [], 0
    while True:
        st, d = _req(
            "GET",
            f"/api/users/{user_id()}/collections/{key}/items/top"
            f"?limit={limit}&start={start}&format=json",
        )
        if not isinstance(d, list) or not d:
            break
        out += d
        if len(d) < limit:
            break
        start += limit
    return out


def search(q, limit=20):
    st, d = _req(
        "GET",
        f"/api/users/{user_id()}/items?q={urllib.parse.quote(q)}&qmode=everything"
        f"&limit={limit}&format=json",
    )
    return d


def set_extra(key, extra_text):
    return patch_item(key, {"extra": extra_text})


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(list_collections())
    else:
        cmd = sys.argv[1]
        if cmd == "cols":
            for k, v in sorted(list_collections().items(), key=lambda x: str(x[1])):
                print(k, "|", v[0], "| parent=", v[1] or "-")
        elif cmd == "item":
            print(json.dumps(get_item(sys.argv[2]), ensure_ascii=False, indent=2)[:3000])
        elif cmd == "delcol":
            print(delete_collection(sys.argv[2]))
