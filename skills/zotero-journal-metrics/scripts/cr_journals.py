import json, time, urllib.request, urllib.error, os, sys

UA = "ZoteroAnnotator/1.0 (mailto:researcher@example.org)"
OUT = "/tmp/crossref_journals.json"

items = json.load(open("/tmp/zot_items.json"))
dois = {}
for it in items:
    d = it.get("data", {})
    if d.get("itemType") == "attachment":
        continue
    doi = (d.get("DOI") or "").strip()
    if doi:
        dois[doi] = d.get("publicationTitle", "")
print(f"待查 DOI: {len(dois)}", flush=True)

cache = {}
if os.path.exists(OUT):
    cache = json.load(open(OUT))
    print(f"已有缓存: {len(cache)}", flush=True)

def fetch(doi, tries=3):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                m = json.loads(r.read().decode("utf-8"))["message"]
            return {
                "container": (m.get("container-title") or [""])[0],
                "short": (m.get("short-container-title") or [""])[0],
                "issn": m.get("ISSN", []),
                "type": m.get("type", ""),
                "year": (m.get("published", {}).get("date-parts", [[None]])[0] or [None])[0],
            }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"error": "404"}
            time.sleep(1.5 * (a + 1))
        except Exception:
            time.sleep(1.5 * (a + 1))
    return {"error": "failed"}

todo = [d for d in dois if d not in cache]
print(f"本次需查: {len(todo)}", flush=True)
for i, doi in enumerate(todo, 1):
    cache[doi] = fetch(doi)
    if i % 25 == 0 or i == len(todo):
        json.dump(cache, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(f"  进度 {i}/{len(todo)}", flush=True)
    time.sleep(0.12)

json.dump(cache, open(OUT, "w"), ensure_ascii=False, indent=1)

ok = sum(1 for v in cache.values() if v.get("container"))
print(f"\n完成：{ok}/{len(cache)} 拿到刊名", flush=True)

from collections import defaultdict, Counter
by_issn = {}
no_issn = []
for doi, v in cache.items():
    if not v.get("container"):
        no_issn.append((doi, dois.get(doi, "")))
        continue
    key = (v["issn"] or ["(无ISSN)"])[0]
    if key not in by_issn:
        by_issn[key] = {"container": v["container"], "short": v["short"],
                        "issn": v["issn"], "n": 0, "zotero_names": Counter()}
    by_issn[key]["n"] += 1
    by_issn[key]["zotero_names"][dois.get(doi, "")] += 1
print(f"归并出期刊数: {len(by_issn)}", flush=True)
json.dump(by_issn, open("/tmp/journals_by_issn.json", "w"), ensure_ascii=False, indent=1)
print("已写 /tmp/journals_by_issn.json", flush=True)
