"""把「文章类型: 期刊论文(未识别)」清零 —— 四级递降策略

用法:
    python resolve_types.py <untyped.json> [resolved_out.json]

输入 untyped.json: Zotero 原始条目数组（含 data.extra / data.tags / data.version）

策略（按顺序，命中即止）:
  1. 从 url / extra / archiveLocation 正则抠 PMID 或 PMC 号 → esummary 直查  ← 最有效
  2. PMC 号 → NCBI ID Converter 换 PMID
  3. 宽松标题检索（主标题去标点取前 9 词 + [Title]）
  4. Crossref query.bibliographic + 刊名交叉校验
"""
import json, re, sys, time, urllib.request, urllib.parse

UA = {"User-Agent": "ZoteroAnnotator/1.0 (mailto:researcher@example.org)"}

PUB_MAP = [                       # 顺序即优先级：systematic review 必须早于 review
    (r"meta-analysis", "Meta分析"),
    (r"systematic review", "系统综述"),
    (r"review", "综述"),
    (r"case reports", "病例报告"),
    (r"clinical trial", "临床试验"),
    (r"guideline", "指南"),
    (r"editorial", "社论"),
    (r"comment", "评论"),
    (r"letter", "通讯"),
    (r"retract", "撤稿声明"),
    (r"journal article", "论著"),
]
CR_MAP = {"journal-article": "论著", "posted-content": "预印本",
          "proceedings-article": "会议论文", "book-chapter": "图书章节",
          "reference-entry": "参考条目", "report": "报告", "monograph": "专著"}


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
    return re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower()).strip()


def loose(title):
    """PubMed 对长标题分词敏感，精确短语常 quotedphrasesnotfound"""
    main = re.split(r"[:\-–—]", title)[0]
    return " ".join(re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", main)[:9])


def map_pub(types):
    low = [str(t).lower() for t in (types or [])]
    for pat, cn in PUB_MAP:
        if any(re.search(pat, t) for t in low):
            return cn
    return ""


def find_ids(d):
    """Zotero 条目的 URL 里常直接躺着 PMID —— 零歧义，优先用"""
    blob = " ".join([d.get("url") or "", d.get("extra") or "",
                     d.get("archiveLocation") or "", d.get("accessionNumber") or ""])
    m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{6,9})", blob) or \
        re.search(r"PMID[:\s]*(\d{6,9})", blob, re.I)
    m2 = re.search(r"(PMC\d{6,9})", blob)
    return (m.group(1) if m else None), (m2.group(1) if m2 else None)


def pmc2pmid(pmcid):
    d = get_json("https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
                 f"?ids={pmcid}&format=json&tool=zoteroann&email=researcher@example.org")
    for rec in (d.get("records") or []):
        if rec.get("pmid"):
            return rec["pmid"], rec.get("doi", "")
    return None, ""


def by_pmid(pmid):
    s = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                 f"?db=pubmed&retmode=json&id={pmid}")
    r = (s.get("result") or {}).get(str(pmid)) or {}
    return map_pub(r.get("pubtype")), r.get("pubtype", [])


def via_pubmed_title(title):
    d = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                 f"?db=pubmed&retmode=json&retmax=3&term="
                 f"{urllib.parse.quote(loose(title) + '[Title]')}")
    for pid in ((d.get("esearchresult") or {}).get("idlist") or [])[:3]:
        s = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                     f"?db=pubmed&retmode=json&id={pid}")
        r = (s.get("result") or {}).get(str(pid)) or {}
        if norm(r.get("title"))[:55] == norm(title)[:55]:
            return map_pub(r.get("pubtype")), pid
    return "", None


def via_crossref(title, journal):
    d = get_json("https://api.crossref.org/works?rows=5&select=title,container-title,type,DOI"
                 f"&query.bibliographic={urllib.parse.quote(title)}")
    for x in (d.get("message") or {}).get("items", []):
        if norm((x.get("title") or [""])[0])[:55] != norm(title)[:55]:
            continue
        cj = (x.get("container-title") or [""])[0]
        if journal and cj and norm(journal)[:22] != norm(cj)[:22]:
            continue
        cn = CR_MAP.get(x.get("type", ""), "")
        if cn:
            return cn, x.get("DOI", "")
    return "", None


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/untyped.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "/tmp/untyped_resolved.json"
    un = json.load(open(src))
    out = []
    for it in un:
        k, d = it["key"], it["data"]
        t = (d.get("title") or "").strip()
        cn, src_label = "", ""
        if t:
            pmid, pmc = find_ids(d)                     # 1
            if not pmid and pmc:                        # 2
                pmid, _ = pmc2pmid(pmc)
                time.sleep(0.35)
            if pmid:
                cn, raw = by_pmid(pmid)
                src_label = f"PMID/{pmid}"
                time.sleep(0.35)
            if not cn:                                  # 3
                cn, pid = via_pubmed_title(t)
                src_label = f"PubMed/{pid}"
            if not cn:                                  # 4
                cn, doi = via_crossref(t, d.get("publicationTitle", ""))
                src_label = f"Crossref/{doi}"
            time.sleep(0.3)
        out.append({"key": k, "title": t, "cn": cn,
                    "src": src_label if cn else "", "raw": raw if cn else []})
        print(f"{'OK ' if cn else 'xx '} {(t or '(空标题)')[:56]}"
              + (f"\n      -> {cn}   ({src_label})" if cn else ""))
    json.dump(out, open(dst, "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for o in out if o["cn"])
    print(f"\n可确定类型: {ok}/{len(out)}  ->  {dst}")


if __name__ == "__main__":
    main()
