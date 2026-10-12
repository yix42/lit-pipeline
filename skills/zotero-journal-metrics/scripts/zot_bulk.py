import json, sys, time, urllib.request, urllib.error
sys.path.insert(0, "/tmp")
from zot_annotate import build_extra, build_tags, merge_tags, ITEMS, MERGED

SID = "TEhMTnZWyw91"
LIB = "21540183"
BASE = f"http://localhost:23119/api/users/{LIB}/items"
STATE = {"token": None}


def authorize():
    r = urllib.request.Request(
        "http://localhost:23119/api/local/authorize",
        data=json.dumps({"libraryID": int(LIB), "libraryType": "user",
                         "appName": "WorkBuddy"}).encode(),
        method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("Zotero-Server-ID", SID)
    with urllib.request.urlopen(r, timeout=20) as resp:
        d = json.loads(resp.read().decode())
    STATE["token"] = d.get("key") or d.get("token")
    return STATE["token"]


def call(method, key, body=None, version=None):
    r = urllib.request.Request(f"{BASE}/{key}",
                               data=json.dumps(body).encode() if body else None,
                               method=method)
    r.add_header("Zotero-API-Key", STATE["token"])
    r.add_header("Zotero-Server-ID", SID)
    r.add_header("Content-Type", "application/json")
    if version is not None:
        r.add_header("If-Unmodified-Since-Version", str(version))
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def get_version(key):
    r = urllib.request.Request(f"{BASE}/{key}",
                               headers={"Zotero-API-Key": STATE["token"], "Zotero-Server-ID": SID})
    with urllib.request.urlopen(r, timeout=25) as resp:
        return json.loads(resp.read().decode()).get("version")


authorize()
print("已授权，token 长度:", len(STATE["token"] or ""), flush=True)

keys = list(MERGED)
ok = fail = 0
errors = []
start = time.time()
for i, key in enumerate(keys, 1):
    e = build_extra(key, MERGED[key])
    if not e:
        continue
    body = {"extra": e,
            "tags": [{"tag": t} for t in merge_tags(key, build_tags(key, MERGED[key]))]}
    st, msg = call("PATCH", key, body, version=ITEMS[key]["version"])
    if st == 401:                      # token 过期 → 续签重试
        authorize()
        st, msg = call("PATCH", key, body, version=ITEMS[key]["version"])
    if st == 412:                      # 版本冲突 → 取最新版本重试
        try:
            st, msg = call("PATCH", key, body, version=get_version(key))
        except Exception as ex:
            st, msg = 0, str(ex)
    if st in (204, 200):
        ok += 1
    else:
        fail += 1
        errors.append((key, st, msg))
    if i % 50 == 0 or i == len(keys):
        print(f"  进度 {i}/{len(keys)}  成功={ok} 失败={fail}  用时{time.time()-start:.0f}s", flush=True)
    time.sleep(0.05)

print(f"\n完成：成功 {ok}，失败 {fail}", flush=True)
if errors:
    print("失败明细：")
    for k, s, m in errors[:20]:
        print(f"   {k}  HTTP {s}  {m[:120]}")
json.dump({"ok": ok, "fail": fail, "errors": errors},
          open("/tmp/zot_write_log.json", "w"), ensure_ascii=False, indent=1)
print("已写 /tmp/zot_write_log.json")
