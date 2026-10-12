#!/usr/bin/env python3
"""lit-fusion: 融合 PubMed (eutils) + Consensus (REST) 文献检索。

功能:
  - 同时检索 PubMed 与 Consensus
  - 按 DOI / 标题归一化去重合并
  - 分三类: 两库共有(交叉印证) / 仅 PubMed / 仅 Consensus(盲区补漏)
  - 输出统一 Markdown 报告 (Consensus 提供 citation_count 质量信号)
  - 可选: 生成合并 RIS 并一键导入指定 Zotero 集合 (依赖 zotero-import skill)

仅依赖 Python 标准库, 无需 pip。
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# ---------- PubMed (eutils) ----------
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def pubmed_search(term, retmax, email, year_min=None, year_max=None):
    """esearch, with optional publication-date window.

    NOTE: year_min/year_max MUST be applied here — passing them only to
    Consensus silently returns pre-filter PubMed hits (e.g. 2001/2002 papers
    for a year_min=2008 query).
    """
    p = {"db": "pubmed", "term": term, "retmax": retmax,
         "retmode": "json", "sort": "relevance", "tool": "lit-fusion", "email": email}
    if year_min or year_max:
        p["datetype"] = "pdat"
        p["mindate"] = str(year_min) if year_min else "1800"
        p["maxdate"] = str(year_max) if year_max else "3000"
    url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())["esearchresult"]["idlist"]


def pubmed_fetch(ids, email):
    if not ids:
        return {}
    url = f"{EUTILS}/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "rettype": "pubmed", "retmode": "xml"})
    raw = urllib.request.urlopen(url, timeout=60).read()
    root = ET.fromstring(raw)
    out = {}
    for art in root.findall(".//PubmedArticle"):
        pmid = (art.findtext(".//PMID") or "").strip()
        if not pmid:
            continue
        title = (art.findtext(".//ArticleTitle") or "").replace("\n", " ").strip()
        jtitle = art.findtext(".//Journal/Title") or ""
        iso = art.findtext(".//Journal/ISOAbbreviation") or ""
        vol = art.findtext(".//JournalIssue/Volume") or ""
        issue = art.findtext(".//JournalIssue/Issue") or ""
        year = art.findtext(".//JournalIssue/PubDate/Year") or ""
        pages = art.findtext(".//Pagination/MedlinePgn") or ""
        doi = art.findtext('.//ELocationID[@EIdType="doi"]') or ""
        abstract = "".join((a.text or "") for a in art.findall(".//Abstract/AbstractText")).replace("\n", " ").strip()
        authors = []
        for au in art.findall(".//AuthorList/Author"):
            ln = au.findtext("LastName")
            fn = au.findtext("ForeName") or au.findtext("Initials")
            if ln:
                authors.append(f"{ln} {fn}".strip())
        mesh = [m.findtext("DescriptorName") for m in art.findall(".//MeshHeading")][:6]
        out[pmid] = {"pmid": pmid, "title": title, "jtitle": jtitle, "iso": iso,
                     "vol": vol, "issue": issue, "year": year, "pages": pages,
                     "doi": doi, "abstract": abstract, "authors": authors, "mesh": mesh}
        time.sleep(0.1)
    return out


def pubmed_id_by_doi(doi, email):
    """Backfill a PMID from a DOI via eutils (precise DOI match)."""
    if not doi:
        return None
    p = {"db": "pubmed", "term": f'"{doi}"[AID]', "retmax": 1,
         "retmode": "json", "tool": "lit-fusion", "email": email}
    try:
        url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(p)
        with urllib.request.urlopen(url, timeout=30) as r:
            ids = json.loads(r.read())["esearchresult"]["idlist"]
        time.sleep(0.35)
        return ids[0] if ids else None
    except Exception:
        return None


def pubmed_id_by_title(title, email, year_min=None, year_max=None):
    """Backfill a PMID from a (cleaned) title via a title-subset esearch.

    Uses the first 3 significant tokens wrapped in [tiab] OR, which is more
    forgiving than an exact phrase and catches title-normalization mismatches.
    """
    toks = [t for t in re.sub(r"[^A-Za-z0-9]+", " ", (title or "").lower()).split()
            if len(t) >= 3][:3]
    if len(toks) < 2:
        return None
    term = " AND ".join(f'"{t}"[tiab]' for t in toks)
    p = {"db": "pubmed", "term": term, "retmax": 3,
         "sort": "relevance", "retmode": "json", "tool": "lit-fusion", "email": email}
    if year_min or year_max:
        p["datetype"] = "pdat"
        p["mindate"] = str(year_min) if year_min else "1800"
        p["maxdate"] = str(year_max) if year_max else "3000"
    try:
        url = f"{EUTILS}/esearch.fcgi?" + urllib.parse.urlencode(p)
        with urllib.request.urlopen(url, timeout=30) as r:
            ids = json.loads(r.read())["esearchresult"]["idlist"]
        time.sleep(0.35)
        return ids[0] if ids else None
    except Exception:
        return None


def expand_pubmed_from_consensus(con_list, email, year_min=None, year_max=None):
    """New strategy (Consensus-first): backfill each Consensus hit with a PMID.

    DOI 优先回填，DOI 缺失/未命中时按标题 3-token 子串兜底。返回 {pmid: meta}，
    其中 meta 额外带 "via" 字段（"doi"/"title"）标注回填路径。
    """
    pmids = []
    seen = set()
    for c in con_list:
        pmid = pubmed_id_by_doi(c.get("doi"), email) or pubmed_id_by_title(
            c.get("title"), email, year_min=year_min, year_max=year_max)
        if pmid and pmid not in seen:
            seen.add(pmid)
            pmids.append(pmid)
    if not pmids:
        return {}
    meta = pubmed_fetch(pmids, email)
    # 标注回填来源
    for pmid, m in meta.items():
        m["via"] = "doi" if (m.get("doi") and any(
            c.get("doi") and c["doi"].lower() == m["doi"].lower() for c in con_list)) else "title"
    return meta


# ---------- Consensus (REST) ----------
def consensus_search(query, api_key, year_min, human, limit):
    p = {"query": query, "limit": limit}
    if year_min:
        p["year_min"] = year_min
    if human is not None:
        p["human"] = str(human).lower()
    url = "https://api.consensus.app/v1/search?" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"x-api-key": api_key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read())
    results = data.get("results", [])
    out = []
    for it in results:
        authors = it.get("authors") or []
        auths = []
        for a in authors[:10]:
            auths.append(a.get("name", "") if isinstance(a, dict) else str(a))
        out.append({
            "title": (it.get("title") or "").replace("\n", " ").strip(),
            "authors": [x for x in auths if x],
            "url": it.get("url", ""),
            "abstract": (it.get("abstract") or "").replace("\n", " ").strip(),
            "citation_count": it.get("citation_count") or it.get("citationCount") or 0,
            "doi": (it.get("doi") or "").strip(),
            "year": it.get("year") or it.get("publicationDate") or "",
            "journal": it.get("journal") or it.get("journalName") or "",
        })
    return out


# ---------- Consensus with retry (handles 429 rate-limit) ----------
def consensus_search_with_retry(query, api_key, year_min, human, limit, tries=3):
    last = None
    for i in range(tries):
        try:
            return consensus_search(query, api_key, year_min, human, limit)
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                wait = 5 * (i + 1)
                print(f"[Consensus] 429 rate-limit, retry {i+1} after {wait}s", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise last


# ---------- helpers ----------
def norm(t):
    t = (t or "").lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def au_ris(name):
    name = (name or "").strip()
    if " " in name:
        i = name.rfind(" ")
        return name[:i] + ", " + name[i + 1:]
    return name


# ---------- merge ----------
def merge(pm_dict, con_list):
    pm_by_doi = {}
    pm_by_norm = {}
    for pmid, p in pm_dict.items():
        if p["doi"]:
            pm_by_doi[p["doi"].lower()] = pmid
        pm_by_norm[norm(p["title"])] = pmid
    con_by_doi = {}
    con_by_norm = {}
    for c in con_list:
        if c["doi"]:
            con_by_doi[c["doi"].lower()] = c
        con_by_norm[norm(c["title"])] = c

    both = []
    con_only = []
    for c in con_list:
        pmid = None
        if c["doi"] and c["doi"].lower() in pm_by_doi:
            pmid = pm_by_doi[c["doi"].lower()]
        elif norm(c["title"]) in pm_by_norm:
            pmid = pm_by_norm[norm(c["title"])]
        if pmid:
            both.append((pm_dict[pmid], c))
        else:
            con_only.append(c)

    pm_only = [
        p for pmid, p in pm_dict.items()
        if not ((p["doi"] and p["doi"].lower() in con_by_doi) or norm(p["title"]) in con_by_norm)
    ]
    return both, pm_only, con_only


# ---------- report / RIS ----------
def build_ris_item(title, authors, journal, year, pages, doi, abstract, url=""):
    L = ["TY  - JOUR"]
    for a in authors:
        if a.strip():
            L.append("AU  - " + au_ris(a))
    L.append("TI  - " + title)
    L.append("JO  - " + (journal or ""))
    if year:
        L.append("PY  - " + str(year))
    if pages:
        L.append("PG  - " + pages)
    if doi:
        L.append("DO  - " + doi)
    if url:
        L.append("UR  - " + url)
    if abstract:
        L.append("AB  - " + abstract)
    L.append("ER  - ")
    return "\n".join(L)


def write_report(query, pm_dict, both, pm_only, con_only, out_path, year_min, human, limit):
    L = []
    L.append(f"# 融合检索报告：{query}\n")
    L.append(f"> 检索策略：**Consensus 优先 → 用其结果扩充 PubMed**（回填 + 基础检索）｜ year_min={year_min} ｜ human={human} ｜ 每库上限={limit}\n")
    L.append("## 总览\n")
    L.append(f"- **两库共有（交叉印证）**：{len(both)} 篇")
    L.append(f"- **仅 PubMed（临床索引/同行评议）**：{len(pm_only)} 篇")
    L.append(f"- **仅 Consensus（盲区补漏：preprint/Scopus/工程）**：{len(con_only)} 篇\n")
    L.append("## 一、两库共有（交叉印证，最优先采用）\n")
    if both:
        for p, c in both:
            L.append(f"- **{p['title']}**")
            L.append(f"  - PubMed: PMID {p['pmid']} ｜ {p['iso'] or p['jtitle']} {p['year']} ｜ DOI {p['doi']}")
            L.append(f"  - Consensus: 引用 {c['citation_count']} ｜ {c['url']}")
    else:
        L.append("（无）")
    L.append("\n## 二、仅 PubMed（临床索引，同行评议）\n")
    if pm_only:
        for p in pm_only:
            L.append(f"- **{p['title']}** (PMID {p['pmid']}) ｜ {p['iso'] or p['jtitle']} {p['year']} ｜ DOI {p['doi']}")
    else:
        L.append("（无）")
    L.append("\n## 三、仅 Consensus（盲区补漏，按引用数降序）\n")
    if con_only:
        def _cite(x):
            try:
                return -int(x["citation_count"])
            except Exception:
                return 0
        for c in sorted(con_only, key=_cite):
            yr = f" ({c['year']})" if c["year"] else ""
            jr = f" ｜ {c['journal']}" if c["journal"] else ""
            L.append(f"- **{c['title']}**{yr} ｜ 引用 {c['citation_count']}{jr}")
            L.append(f"  - {c['url']}")
    else:
        L.append("（无）")
    L.append("\n## 四、使用提示\n")
    L.append("- 检索策略：**Consensus 优先**（语义检索、覆盖 2.2 亿篇、盲区信号）→ 拿其命中结果**扩充 PubMed**（DOI/标题回填 PMID + 一次基础受控检索）→ 跨库去重分三类。")
    L.append("- 「两库共有」= 跨库交叉印证，证据强度最高，优先纳入。")
    L.append("- 「仅 Consensus」= PubMed 未收录的 preprint / Scopus / 工程类文献，用于补足盲区；其未经同行评议比例较高，引用前请核对原始出处。")
    L.append("- 「仅 PubMed」既含基础检索补到的同行评议文献，也含 Consensus 未覆盖但 PubMed 命中的临床索引。")
    L.append("- Consensus 免费档 30 次/月，注意预算；高频检索用 --pubmed-only 或降低 --limit。")
    open(out_path, "w").write("\n".join(L))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="Fuse PubMed + Consensus literature search")
    ap.add_argument("query", help="search query")
    ap.add_argument("--year-min", type=int, default=None)
    ap.add_argument("--year-max", type=int, default=None)
    ap.add_argument("--human", dest="human", action="store_true", default=None, help="Consensus: human studies only")
    ap.add_argument("--no-human", dest="human", action="store_false")
    ap.add_argument("--limit", type=int, default=15, help="per-source result cap")
    ap.add_argument("--email", default="lit-fusion@example.com")
    ap.add_argument("--out", default=None, help="report markdown path")
    ap.add_argument("--ris", default=None, help="combined RIS output path")
    ap.add_argument("--import-to", default=None, help="Zotero collection name to import into (uses zotero-import skill)")
    ap.add_argument("--pubmed-only", action="store_true")
    ap.add_argument("--consensus-only", action="store_true")
    ap.add_argument("--api-key-file", default=os.path.expanduser("~/.workbuddy/consensus_auth.json"))
    args = ap.parse_args()

    out_path = args.out or os.path.expanduser("~/lit_fusion_report.md")
    ris_path = args.ris or os.path.expanduser("~/lit_fusion_combined.ris")

    # ===== 新默认策略：Consensus 优先 → 用其结果扩充 PubMed =====
    # 1) 先 Consensus（拿命中与盲区）
    # 2) 用 Consensus 命中的 DOI/标题回填 PubMed（拿到 PMID + 权威元数据）
    # 3) 叠加一次基础 PubMed 受控检索
    # 最终 pm_dict = 回填结果 ∪ 基础结果（回填优先，去重）
    con_list = []
    pm_expanded = {}
    pm_base = {}

    if not args.pubmed_only:
        try:
            key = json.load(open(args.api_key_file)).get("api_key")
            time.sleep(1.0)  # gentle pacing before the Consensus call
            con_list = consensus_search_with_retry(args.query, key, args.year_min, args.human, args.limit)
            con_list = con_list[:args.limit]
            print(f"[Consensus] {len(con_list)} papers", file=sys.stderr)
        except Exception as e:
            print(f"[Consensus] ERROR: {e}", file=sys.stderr)

        if not args.consensus_only and con_list:
            pm_expanded = expand_pubmed_from_consensus(
                con_list, args.email, year_min=args.year_min, year_max=args.year_max)
            print(f"[PubMed:expanded-from-Consensus] {len(pm_expanded)} backfilled", file=sys.stderr)

    if not args.consensus_only:
        ids = pubmed_search(args.query, args.limit, args.email,
                            year_min=args.year_min, year_max=args.year_max)
        time.sleep(0.34)
        pm_base = pubmed_fetch(ids, args.email)
        print(f"[PubMed:base] {len(pm_base)} papers", file=sys.stderr)

    # 合并：回填优先（含权威元数据 + via 标注），基础补漏
    pm_dict = dict(pm_expanded)
    for k, v in pm_base.items():
        pm_dict.setdefault(k, v)

    if args.consensus_only:
        both, pm_only, con_only = [], [], con_list
    elif args.pubmed_only:
        both, pm_only, con_only = [], list(pm_dict.values()), []
    else:
        both, pm_only, con_only = merge(pm_dict, con_list)

    write_report(args.query, pm_dict, both, pm_only, con_only, out_path, args.year_min, args.human, args.limit)
    print(f"[report] -> {out_path}", file=sys.stderr)

    ris_items = []
    for p in pm_dict.values():
        ris_items.append(build_ris_item(p["title"], p["authors"], p["jtitle"] or p["iso"],
                                        p["year"], p["pages"], p["doi"], p["abstract"]))
    for c in con_only:
        ris_items.append(build_ris_item(c["title"], c["authors"], c["journal"],
                                        c["year"], "", c["doi"], c["abstract"], c["url"]))
    open(ris_path, "w").write("\n\n".join(ris_items) + "\n")
    print(f"[ris] -> {ris_path} ({len(ris_items)} entries)", file=sys.stderr)

    if args.import_to:
        script = os.path.expanduser("~/.workbuddy/skills/zotero-import/scripts/zotero_import.py")
        if os.path.exists(script):
            cmd = [sys.executable, script, "--collection", args.import_to, "--ris", ris_path]
            print(f"[zotero] importing into '{args.import_to}' ...", file=sys.stderr)
            try:
                subprocess.run(cmd, check=True)
            except Exception as e:
                print(f"[zotero] import failed: {e}", file=sys.stderr)
        else:
            print(f"[zotero] script not found: {script}", file=sys.stderr)


if __name__ == "__main__":
    main()
