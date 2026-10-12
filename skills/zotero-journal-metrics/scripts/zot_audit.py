"""Zotero 库指标注解 —— 全库审计（写完必跑）

用法:
    python zot_audit.py <server_id> <library_id> [items_out.json]

输出 4 项必查指标 + 文章类型分布 + 期刊聚合摘要。
"""
import json, re, sys, time, collections, urllib.request

SID = sys.argv[1] if len(sys.argv) > 1 else ""
LIB = sys.argv[2] if len(sys.argv) > 2 else ""
OUT = sys.argv[3] if len(sys.argv) > 3 else "/tmp/zot_items_now.json"
BASE = f"http://localhost:23119/api/users/{LIB}/items/top"


def authorize():
    r = urllib.request.Request(
        "http://localhost:23119/api/local/authorize",
        data=json.dumps({"libraryID": int(LIB), "libraryType": "user",
                         "appName": "WorkBuddy"}).encode(), method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("Zotero-Server-ID", SID)
    with urllib.request.urlopen(r, timeout=20) as resp:
        return json.loads(resp.read().decode()).get("key")   # 注意字段名是 key


def fetch(token):
    out, start = [], 0
    while True:
        r = urllib.request.Request(f"{BASE}?limit=100&start={start}",
                                   headers={"Zotero-API-Key": token, "Zotero-Server-ID": SID})
        with urllib.request.urlopen(r, timeout=40) as resp:
            batch = json.loads(resp.read().decode())
        out.extend(batch)
        if len(batch) < 100:
            return out
        start += 100
        time.sleep(0.2)


def main():
    items = fetch(authorize())
    json.dump(items, open(OUT, "w"), ensure_ascii=False)

    # 附件不算文献条目
    docs = [i for i in items if i["data"].get("itemType") != "attachment"]
    n = len(docs)
    print(f"顶层条目 {len(items)} = 文献 {n} + 附件 {len(items)-n}")

    types, unrec, notype, if_gap, noblock = collections.Counter(), [], [], [], []
    for i in docs:
        d, e = i["data"], (i["data"].get("extra") or "")
        m = re.search(r"文章类型[:：]\s*(.+)", e, re.M)
        types[m.group(1).strip() if m else "(无)"] += 1
        if not m:
            notype.append(i["key"])
        elif "未识别" in m.group(1):
            unrec.append(i["key"])
        if "【期刊指标】" not in e and "【文献信息】" not in e:
            noblock.append(i["key"])
        # 有 JCR 分区却无 IF = 匹配漏网，必查
        if re.search(r"^JCR分区", e, re.M) and not re.search(r"^影响因子", e, re.M):
            if_gap.append(i["key"])

    cov = lambda p: sum(1 for i in docs if re.search(p, i["data"].get("extra") or "", re.M))
    print(f"\n影响因子   {cov(r'^影响因子'):>4} / {n}")
    print(f"JCR分区    {cov(r'^JCR分区'):>4} / {n}")
    print(f"中科院分区 {cov(r'^中科院分区'):>4} / {n}")
    print(f"文章类型   {n-len(notype):>4} / {n}")
    print("\n【必查】")
    for label, lst in (("仍含'未识别'", unrec), ("无文章类型", notype),
                       ("有JCR分区但无IF", if_gap), ("无任何指标块", noblock)):
        flag = "OK" if not lst else "!! 需处理"
        print(f"  {label:<16} {len(lst):>3}  {flag}  {lst[:8]}")
    print("\n文章类型分布:")
    for k, v in types.most_common():
        print(f"  {k:<12} {v}")


if __name__ == "__main__":
    main()
