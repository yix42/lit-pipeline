#!/usr/bin/env python3
"""用 Europe PMC 的 resultType=core 给 Zotero 条目补：文章类型 / 摘要 / 作者数 / 卷期页 / 被引数。

为什么必须补 type：
  上一轮踩过坑——PMC9998453 看着像论著，实为 2,569 字读者来信。
  /tmp/oa_probe.json 里 331 条的 type 字段全空，不补会把信件和勘误当论著分诊。

限流策略：Europe PMC 建议 <3 req/s。批量 20 条一次查询，失败指数退避。
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
BATCH = 20
OUT = "/tmp/oa_enriched.json"


def _get(url, timeout=45, tries=5):
    last = None
    for a in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(3.0 * (2 ** a))
                continue
            raise
        except Exception as e:                                    # noqa: BLE001
            last = e
            time.sleep(2.0 * (a + 1))
    raise last


def norm_doi(d):
    d = (d or "").strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    return d


def norm_pmid(v):
    v = str(v or "").strip()
    m = re.search(r"(\d{6,9})", v)
    return m.group(1) if m else ""


def norm_pmcid(v):
    v = str(v or "").strip().upper()
    m = re.search(r"(PMC\d+)", v)
    return m.group(1) if m else ""


def query_for(rec):
    """优先 PMCID（唯一），其次 DOI，最后 PMID。"""
    pmcid = norm_pmcid(rec.get("pmcid") or (rec.get("epmc") or {}).get("pmcid"))
    if pmcid:
        return f"PMCID:{pmcid}"
    doi = norm_doi(rec.get("doi"))
    if doi:
        return f'DOI:"{doi}"'
    pmid = norm_pmid(rec.get("pmid") or (rec.get("epmc") or {}).get("pmid"))
    if pmid:
        return f"EXT_ID:{pmid}"
    return None


def extract(res):
    """从 core 结果里取我们要的字段。"""
    pt = res.get("pubTypeList", {}).get("pubType", []) or []
    ptl = [str(x) for x in pt]
    low = " ".join(ptl).lower()
    # 归一化成一个主类型，便于分诊层做闸门
    if any(k in low for k in ("retract", "correction", "erratum", "comment", "editorial",
                              "letter", "reply", "published erratum")):
        main = "非论著"
    elif "review" in low:
        main = "综述"
    elif any(k in low for k in ("journal article", "research-article", "article")):
        main = "论著"
    else:
        main = "未标类型"
    authors = res.get("authorList", {}).get("author", []) or []
    ji = res.get("journalInfo", {}) or {}
    return {
        "pubTypes": ptl,
        "pubType_main": main,
        "abstract": res.get("abstractText") or "",
        "n_authors": len(authors),
        "pubYear": res.get("pubYear") or "",
        "volume": ji.get("volume") or "",
        "issue": ji.get("issue") or "",
        "pages": res.get("pageInfo") or "",
        "citedBy": res.get("citedByCount"),
        "isReview": bool(res.get("isReview")),
        "hasAbstract": bool(res.get("hasAbstract")),
        "epmc_inEPMC": res.get("inEPMC") == "Y",
        "epmc_pmcid": res.get("pmcid") or "",
        "epmc_pmid": res.get("pmid") or "",
        "epmc_title": res.get("title") or "",
    }


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/oa_probe.json"
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    recs = json.load(open(src))
    if only:
        recs = [r for r in recs if r["key"] in only]

    todo = [(r, query_for(r)) for r in recs]
    have = [(r, q) for r, q in todo if q]
    miss = [r for r, q in todo if not q]
    print(f"待补 {len(recs)} 条 | 可查 {len(have)} 条 | 无标识符 {len(miss)} 条", flush=True)

    found, empty = {}, []
    t0 = time.time()
    for i in range(0, len(have), BATCH):
        chunk = have[i:i + BATCH]
        q = " OR ".join(f"({x[1]})" for x in chunk)
        url = (f"{EPMC}?query={urllib.parse.quote(q)}"
               f"&resultType=core&format=json&pageSize={len(chunk) * 2}")
        try:
            d = _get(url)
            res = d.get("resultList", {}).get("result", []) or []
        except Exception as e:                                    # noqa: BLE001
            print(f"  [{i//BATCH+1}] 查询失败 {type(e).__name__}: {str(e)[:60]}", flush=True)
            res = []

        # 结果按 DOI/PMCID/PMID 回连
        idx = {}
        for r in res:
            for k in (norm_pmcid(r.get("pmcid")), norm_doi(r.get("doi")),
                      norm_pmid(r.get("pmid"))):
                if k:
                    idx[k] = r
        for rec, q in chunk:
            hit = None
            for cand in (norm_pmcid(rec.get("pmcid") or (rec.get("epmc") or {}).get("pmcid")),
                         norm_doi(rec.get("doi")),
                         norm_pmid(rec.get("pmid") or (rec.get("epmc") or {}).get("pmid"))):
                if cand and cand in idx:
                    hit = idx[cand]
                    break
            if hit:
                found[rec["key"]] = extract(hit)
            else:
                empty.append(rec["key"])
        done = min(i + BATCH, len(have))
        print(f"  [{done:>3}/{len(have)}] 已匹配 {len(found):>3}  用时 {time.time()-t0:5.1f}s", flush=True)
        time.sleep(0.4)

    # 回写
    for r in recs:
        e = found.get(r["key"])
        if e:
            r["type"] = e["pubType_main"]
            r["pubTypes"] = e["pubTypes"]
            r["abstract"] = e["abstract"]
            r["n_authors"] = e["n_authors"]
            r["pubYear"] = e["pubYear"]
            r["volume"] = e["volume"]
            r["issue"] = e["issue"]
            r["pages"] = e["pages"]
            r["citedBy"] = e["citedBy"]
            r["hasAbstract"] = e["hasAbstract"]
            if e["epmc_pmcid"]:
                r.setdefault("epmc", {})
                r["epmc"]["pmcid"] = e["epmc_pmcid"]
                r["epmc"]["pmid"] = e["epmc_pmid"]
                r["epmc"]["in_epmc"] = e["epmc_inEPMC"]
    json.dump(recs, open(OUT, "w"), ensure_ascii=False, indent=1)

    # 统计
    from collections import Counter
    print(f"\n=== 完成：{len(found)}/{len(recs)} 补到字段，用时 {time.time()-t0:.1f}s ===")
    print("文章类型分布:", dict(Counter(r.get("type") or "(未补)" for r in recs)))
    print("有摘要:", sum(1 for r in recs if r.get("abstract")), "/", len(recs))
    if empty:
        print(f"未匹配 {len(empty)} 条: {', '.join(empty[:15])}")
    print(f"输出 -> {OUT}")


if __name__ == "__main__":
    main()
