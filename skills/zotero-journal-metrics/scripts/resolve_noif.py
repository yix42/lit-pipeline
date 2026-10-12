"""给「有 JCR 分区但无 IF」或「完全没有 IF」的条目回查指标。

**必须走 ISSN 精确匹配** —— 刊名相似度会产生静默误配（见 SKILL.md 第「一·补」节）。

用法:
    python resolve_noif.py <items.json> [out.json]

items.json = Zotero 原始条目数组。脚本对每个缺 IF 的 journalArticle：
  1. 从 url/extra 抠 PMID；没有就用宽松标题检索 PubMed 拿 PMID
  2. esummary → issn / essn + fulljournalname / source
  3. ISSN 精确匹配 JCR 表与中科院表（名称仅作低置信兜底）
  4. **打印命中的刊名**，供人工核验；不自动写库

依赖 /tmp/jcrdata/{JCR2025-UTF8,FQBJCR2025-UTF8,JCR_2025}.csv
"""
import json, re, csv, sys, time, urllib.request, urllib.parse

UA = {"User-Agent": "ZoteroAnnotator/1.0 (mailto:researcher@example.org)"}
JCR_DIR = "/tmp/jcrdata"


def get_json(url, tries=3, timeout=25):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1.2 * (a + 1))
    return {}


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def ck(i):
    """ISSN 归一：只留 0-9X 并大写"""
    return re.sub(r"[^0-9Xx]", "", str(i or "")).upper()


def load_indexes():
    jcr_issn, cas_issn, jcr_name = {}, {}, {}
    with open(f"{JCR_DIR}/JCR2025-UTF8.csv", encoding="utf-8-sig") as f:
        for r in csv.reader(f):
            # 跳过表头：ISSN 列必须是合法形态
            if len(r) < 8 or not r[0] or not re.match(r"^[0-9Xx\-]{4,}$", r[1] or ""):
                continue
            rec = {"name": r[0], "if": r[4], "cat": r[5], "q": r[6], "rank": r[7]}
            jcr_name[norm(r[0])] = rec
            for i in (r[1], r[2]):
                if ck(i):
                    jcr_issn[ck(i)] = rec
    with open(f"{JCR_DIR}/FQBJCR2025-UTF8.csv", encoding="utf-8-sig") as f:
        for r in csv.reader(f):
            if len(r) < 10 or not r[0]:
                continue
            rec = {"name": r[0], "major": r[8], "q": r[9]}
            for i in re.split(r"[/,]", r[2]):
                if ck(i):
                    cas_issn[ck(i)] = rec
    # 仅 Quartile 的补充源：用于确认"该刊确实无 IF"
    qonly = {norm(r[0]) for r in
             csv.reader(open(f"{JCR_DIR}/JCR_2025.csv", encoding="utf-8-sig"))
             if r and r[0] and r[0].lower() != "journal"}
    return jcr_issn, cas_issn, jcr_name, qonly


def pmid_of(d):
    blob = " ".join([d.get("url") or "", d.get("extra") or "",
                     d.get("archiveLocation") or ""])
    m = (re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{6,9})", blob)
         or re.search(r"PMID[:\s]*(\d{6,9})", blob, re.I))
    return m.group(1) if m else None


def esummary(pmid):
    s = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                 f"?db=pubmed&retmode=json&id={pmid}")
    return (s.get("result") or {}).get(str(pmid)) or {}


def search_pmid(title):
    main = re.split(r"[:\-–—]", title)[0]
    q = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", main)[:9])
    if not q:
        return None
    d = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                 f"?db=pubmed&retmode=json&retmax=3&term={urllib.parse.quote(q + '[Title]')}")
    for pid in ((d.get("esearchresult") or {}).get("idlist") or [])[:2]:
        if norm(esummary(pid).get("title"))[:55] == norm(title)[:55]:
            return pid
    return None


def crossref_issn(doi):
    m = (get_json("https://api.crossref.org/works/" +
                  urllib.parse.quote(doi)).get("message") or {})
    return (m.get("container-title") or [""])[0], m.get("ISSN") or []


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/zot_items_now.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "/tmp/noif_resolved.json"
    items = json.load(open(src))
    docs = [i for i in items if i["data"].get("itemType") != "attachment"]
    todo = [i for i in docs
            if i["data"].get("itemType") == "journalArticle"
            and not re.search(r"^影响因子", i["data"].get("extra") or "", re.M)]

    jcr_issn, cas_issn, jcr_name, qonly = load_indexes()
    print(f"待查 {len(todo)} 条（ISSN 精确匹配优先，命中会打印刊名供核验）\n")
    out = []
    for i in todo:
        d = i["data"]
        title = (d.get("title") or "").strip()
        pub = (d.get("publicationTitle") or "").strip().lstrip("-").strip()
        pmid = pmid_of(d) or (search_pmid(title) if title else None)
        if not pmid and d.get("DOI"):
            time.sleep(0.3)
        r = esummary(pmid) if pmid else {}
        issns = [x for x in (ck(r.get("issn")), ck(r.get("essn"))) if x]
        label = r.get("fulljournalname") or r.get("source") or pub or "(无刊名)"

        doi_issns, doi_name = [], ""
        if not issns and d.get("DOI"):          # 无 PMID 时用 DOI
            doi_name, doi_issns = crossref_issn(d["DOI"])
            issns = [x for x in (ck(x) for x in doi_issns) if x]
            label = doi_name or label
            time.sleep(0.3)

        jc = next((jcr_issn[x] for x in issns if x in jcr_issn), None)
        cc = next((cas_issn[x] for x in issns if x in cas_issn), None)
        if not jc:                               # 名称兜底（仅精确）
            jc = jcr_name.get(norm(label))

        print(f"{i['key']:<9} {label[:62]}")
        print(f"          ISSN={','.join(issns) or '—':<20} PMID={pmid or '—'}")
        if jc:
            print(f"          ✅ JCR「{jc['name']}」IF={jc['if']} Q={jc['q']} {jc['cat']} {jc['rank']}")
        else:
            tag = "  ← Q-only 源有记录，该刊确实无 IF" if norm(label) in qonly else ""
            print(f"          ❌ JCR 未命中{tag}")
        print(f"          {'✅ 中科院「'+cc['name']+'」'+cc['major']+' '+cc['q'] if cc else '❌ 中科院未命中'}")
        out.append({"key": i["key"], "journal": label, "issn": ",".join(issns),
                    "pmid": pmid, "jcr_name": jc["name"] if jc else "",
                    "if": jc["if"] if jc else "", "q": jc["q"] if jc else "",
                    "cat": jc["cat"] if jc else "", "rank": jc["rank"] if jc else "",
                    "cas": f"{cc['major']} {cc['q']}" if cc else ""})
        time.sleep(0.3)

    json.dump(out, open(dst, "w"), ensure_ascii=False, indent=1)
    hit = [r for r in out if r["if"]]
    print(f"\n查到 IF: {len(hit)} 条  →  {dst}")
    for r in hit:
        print(f"   {r['key']}  {r['journal'][:50]} → IF {r['if']}  {r['cat']} {r['rank']}")


if __name__ == "__main__":
    main()
