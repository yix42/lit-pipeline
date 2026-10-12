#!/usr/bin/env python3
"""探测 Zotero 库内文献的开放获取全文可得率（不写任何库，纯只读探测）。
数据源：Unpaywall（DOI）+ Europe PMC（DOI/PMID）+ PMC ID Converter。
"""
import json, re, time, urllib.request, urllib.parse, sys
from collections import Counter

UA = {"User-Agent": "ResearchVault-Feasibility/1.0 (mailto:researcher@example.org)"}
EMAIL = "researcher@example.org"


def gj(url, timeout=25, tries=3):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if a == tries - 1:
                return {"_err": str(e)[:80]}
            time.sleep(1.0 * (a + 1))
    return {}


def doi_of(d):
    doi = (d.get("DOI") or "").strip()
    if doi:
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
        return doi or None
    url = d.get("url") or ""
    m = re.search(r"10\.\d{4,9}/[^\s\"<>]+", url)
    return m.group(0).rstrip(".") if m else None


def pmid_of(d):
    for blob in (d.get("extra") or "", d.get("url") or ""):
        m = re.search(r"(?:pubmed[/\s:]*|PMID[:\s]*)(\d{6,9})", blob, re.I)
        if m:
            return m.group(1)
    return None


def pmcid_of(d):
    for blob in (d.get("extra") or "", d.get("url") or ""):
        m = re.search(r"(PMC\d{5,9})", blob)
        if m:
            return m.group(1)
    return None


def probe_unpaywall(doi):
    d = gj(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={EMAIL}")
    if "_err" in d or "is_oa" not in d:
        return None
    loc = d.get("best_oa_location") or {}
    return {
        "is_oa": bool(d.get("is_oa")),
        "status": d.get("oa_status") or "?",
        "pdf": loc.get("url_for_pdf") or "",
        "host": loc.get("host_type") or "",
        "journal": d.get("journal_name") or "",
    }


def probe_epmc(doi=None, pmid=None):
    if doi:
        q = f'DOI:"{doi}"'
    elif pmid:
        q = f"EXT_ID:{pmid}"
    else:
        return None
    d = gj("https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
           + urllib.parse.quote(q) + "&resultType=core&format=json&pageSize=1")
    if "_err" in d:
        return None
    res = (d.get("resultList") or {}).get("result") or []
    if not res:
        return None
    r = res[0]
    return {
        "in_epmc": r.get("inEPMC") == "Y",
        "in_pmc": r.get("inPMC") == "Y",
        "is_oa": r.get("isOpenAccess") == "Y",
        "pmcid": r.get("pmcid") or "",
        "pmid": r.get("pmid") or "",
        "title": (r.get("title") or "")[:70],
        "journal": (r.get("journalInfo") or {}).get("journal", {}).get("title", "")[:46],
    }


def main():
    items = json.load(open("/tmp/zot_items_now.json"))
    docs = [i for i in items if i["data"].get("itemType") != "attachment"]
    print(f"文献条目 {len(docs)}", flush=True)

    rows = []
    for n, it in enumerate(docs, 1):
        d = it["data"]
        doi, pmid = doi_of(d), pmid_of(d)
        pmcid = pmcid_of(d)
        rec = {"key": it["key"], "title": (d.get("title") or "")[:70],
               "pub": (d.get("publicationTitle") or "")[:46],
               "doi": doi, "pmid": pmid, "pmcid": pmcid, "type": "",
               "oa": None, "route": "无标识"}
        if doi:
            u = probe_unpaywall(doi)
            if u:
                rec["oa"] = u
                rec["route"] = "Unpaywall"
            time.sleep(0.08)
        e = probe_epmc(doi=doi, pmid=pmid) or {}
        rec["epmc"] = e
        if not rec["oa"] and e:
            rec["route"] = "EPMC"
        time.sleep(0.08)
        rows.append(rec)
        if n % 25 == 0:
            print(f"  ...已查 {n}/{len(docs)}", flush=True)

    json.dump(rows, open("/tmp/oa_probe.json", "w"), ensure_ascii=False, indent=1)

    # ---- 汇总 ----
    n = len(rows)
    with_doi = sum(1 for r in rows if r["doi"])
    with_id = sum(1 for r in rows if r["doi"] or r["pmid"] or r["pmcid"])
    una_oa = sum(1 for r in rows if (r["oa"] or {}).get("is_oa"))
    una_any = sum(1 for r in rows if r["oa"])
    epmc_oa = sum(1 for r in rows if (r["epmc"] or {}).get("is_oa"))
    epmc_ft = sum(1 for r in rows if (r["epmc"] or {}).get("in_epmc"))
    epmc_pmc = sum(1 for r in rows if (r["epmc"] or {}).get("in_pmc"))

    print("\n" + "=" * 78)
    print(f"条目总数                 {n}")
    print(f"  有 DOI                 {with_doi}  ({with_doi/n*100:.1f}%)")
    print(f"  有任一标识(DOI/PMID/PMC) {with_id}  ({with_id/n*100:.1f}%)")
    print(f"  无任何标识             {n-with_id}")
    print()
    print(f"Unpaywall 有记录         {una_any}")
    print(f"Unpaywall 判定开放获取   {una_oa}  ({una_oa/n*100:.1f}%)")
    print(f"Europe PMC 开放获取      {epmc_oa}  ({epmc_oa/n*100:.1f}%)")
    print(f"Europe PMC 有全文(inEPMC){epmc_ft}  ({epmc_ft/n*100:.1f}%)")
    print(f"在 PMC 中(inPMC)         {epmc_pmc}  ({epmc_pmc/n*100:.1f}%)")

    # 合并口径：任一来源可拿到
    obtainable = [r for r in rows
                  if (r["oa"] or {}).get("is_oa") or (r["epmc"] or {}).get("in_epmc")]
    print(f"\n★ 至少一条途径可获取全文  {len(obtainable)}  ({len(obtainable)/n*100:.1f}%)")

    print("\nOA 状态分布 (Unpaywall):")
    for k, v in Counter((r["oa"] or {}).get("status", "无记录") for r in rows).most_common():
        print(f"  {k:<12} {v:>4}")

    print("\n托管类型 (host_type):")
    for k, v in Counter((r["oa"] or {}).get("host", "—") for r in rows
                        if (r["oa"] or {}).get("is_oa")).most_common():
        print(f"  {k:<12} {v:>4}")

    print("\n" + "-" * 78)
    print("无法自动获取全文的条目（需人工/机构订阅）：")
    hard = [r for r in rows if r not in obtainable]
    for r in hard[:40]:
        why = "无DOI" if not r["doi"] else ("有DOI但非OA" if r["doi"] else "?")
        print(f"  [{why:<10}] {(r['pub'] or '—')[:40]:<40} | {r['title'][:42]}")
    if len(hard) > 40:
        print(f"  ... 另有 {len(hard)-40} 条")

    json.dump({"obtainable_keys": [r["key"] for r in obtainable],
               "hard_keys": [r["key"] for r in hard]},
              open("/tmp/oa_split.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
