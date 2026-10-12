#!/usr/bin/env python3
"""按 PMCID / DOI 拉取全文，优先 Europe PMC 结构化 XML，PDF 兜底。

用法：
    python3 fetch_fulltext.py --pmcid PMC9911322 --out ./ft
    python3 fetch_fulltext.py --doi 10.3389/fphys.2024.1384695 --out ./ft
    python3 fetch_fulltext.py --keys-file pilot_keys.json --items /tmp/zot_items_now.json --out ./ft

设计要点：
  * XML 优先——出版商原生 XML，含 <sec>/<table-wrap>/<fig>，无需版面重建
  * 正文体量校验——<3000 字符要警惕，很可能是读者来信/勘误而非论著
  * 绝不伪造——拿不到就写 FULLTEXT_UNAVAILABLE 并记录原因，不拼凑
"""
import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "ZoteroFulltextFeasibility/1.0 (mailto:researcher@example.org)"}
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UNPAY = "https://api.unpaywall.org/v2"
EMAIL = "researcher@example.org"

MIN_BODY = 3000          # 正文纯文本低于此值 → 疑似非论著
ARTICLE_TYPES = {        # 非完整论著的文章类型，看到就提示
    "letter", "editorial", "comment", "erratum", "correction",
    "abstract", "reply", "correspondence",
}


def _get(url, timeout=35, tries=4, binary=False):
    """带退避重试。Europe PMC 会返回 503/429 限流，需较长退避。"""
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
                return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:          # noqa: PERF203
            last = e
            # 503/429 是限流，退避要长；4xx 其他错误不必重试
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2.5 * (2 ** a))
                continue
            raise
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(1.5 * (a + 1))
    raise last


def search_epmc(doi=None, pmid=None, pmcid=None):
    """按标识查 Europe PMC，返回 core 记录（含 pmcid / inEPMC / pubType）。"""
    if pmcid:
        q = f"PMCID:{pmcid}"
    elif doi:
        q = f'DOI:"{doi}"'
    elif pmid:
        q = f"EXT_ID:{pmid}"
    else:
        return {}
    try:
        d = json.loads(_get(f"{EPMC}/search?query={urllib.parse.quote(q)}"
                            "&resultType=core&format=json&pageSize=1"))
    except Exception:
        return {}
    res = (d.get("resultList") or {}).get("result") or []
    return res[0] if res else {}


def fetch_xml(pmcid):
    """取 Europe PMC 全文 XML。返回 (xml, 说明)。"""
    try:
        x = _get(f"{EPMC}/{pmcid}/fullTextXML")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:                          # noqa: BLE001
        return None, f"{type(e).__name__}"
    if not x or len(x) < 3000:
        return None, f"XML 过短({len(x) if x else 0})"
    return x, "ok"


def xml_stats(x):
    body = "".join(re.findall(r"<body>(.*?)</body>", x, re.S))
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()
    return {
        "body_chars": len(txt),
        "sections": len(re.findall(r"<sec[ >]", x)),
        "tables": len(re.findall(r"<table-wrap", x)),
        "figures": len(re.findall(r"<fig[ >]", x)),
        "refs": len(re.findall(r"<ref[ >]", x)),
        "preview": txt[:180],
    }


def xml_to_markdown(x, meta):
    """把 JATS XML 粗转为 Markdown（保留章节层级）。只做结构映射，不改写内容。"""
    title = ""
    m = re.search(r"<article-title>(.*?)</article-title>", x, re.S)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    out = [
        "---",
        f'title: "{meta.get("title") or title}"',
        f'zotero_key: "{meta.get("key","")}"',
        f'doi: "{meta.get("doi") or ""}"',
        f'pmcid: "{meta.get("pmcid") or ""}"',
        "source_type: europepmc-xml",
        "---",
        "",
        f"# {meta.get('title') or title}",
        "",
    ]

    abstract = re.search(r"<abstract[^>]*>(.*?)</abstract>", x, re.S)
    if abstract:
        at = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", abstract.group(1))).strip()
        out += ["## Abstract", "", at, ""]

    body = "".join(re.findall(r"<body>(.*?)</body>", x, re.S))
    # 按 <sec> 顺序展开：取每个 sec 的标题与段落
    for sm in re.finditer(r"<sec\b[^>]*>(.*?)</sec>", body, re.S):
        chunk = sm.group(1)
        tm = re.search(r"<title>(.*?)</title>", chunk, re.S)
        head = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""
        if head:
            out += [f"## {head}", ""]
        for pm in re.finditer(r"<p\b[^>]*>(.*?)</p>", chunk, re.S):
            para = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pm.group(1))).strip()
            if para:
                out += [para, ""]
    return "\n".join(out)


def via_unpaywall(doi):
    try:
        d = json.loads(_get(f"{UNPAY}/{urllib.parse.quote(doi)}?email={EMAIL}"))
    except Exception:
        return None
    loc = d.get("best_oa_location") or {}
    return {
        "is_oa": bool(d.get("is_oa")),
        "status": d.get("oa_status"),
        "pdf_url": loc.get("url_for_pdf") or loc.get("url") or "",
        "host": loc.get("host_type") or "",
    }


def process(rec, outdir, meta):
    key = meta.get("key") or "unknown"
    result = {"key": key, "title": meta.get("title", ""), "route": None, "reason": ""}
    # PMCID 以显式传入者优先（search 可能查不到，但 XML 端点是直连的）
    pmcid = meta.get("pmcid") or rec.get("pmcid") or ""

    if pmcid:
        x, why = fetch_xml(pmcid)
        if x:
            st = xml_stats(x)
            result.update(route="europepmc-xml", **st)
            if st["body_chars"] == 0:
                # Europe PMC 收录了记录但没有全文 XML（常见的授权限制），需走 PDF
                result.update(route="xml-empty",
                              reason="Europe PMC 有记录但无全文 XML，需走 PDF 通道")
            elif st["body_chars"] < MIN_BODY:
                # 真的取回了正文，只是很短 —— 这才是疑似来信/勘误
                result.update(route="suspect-short",
                              reason=(f"正文仅 {st['body_chars']} 字符，"
                                      "疑似读者来信/勘误而非论著，请核实文章类型"))
            else:
                md = xml_to_markdown(x, meta)
                path = os.path.join(outdir, f"{key}.md")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(md)
                result["path"] = path
            return result
        result["reason"] = f"XML 不可用: {why}"

    doi = meta.get("doi") or rec.get("doi") or ""
    if doi:
        u = via_unpaywall(doi)
        if u and u["is_oa"] and u["pdf_url"]:
            result.update(route="oa-pdf", pdf_url=u["pdf_url"],
                          oa_status=u["status"], note="需 PDF→Markdown 转换")
            return result
        if u is not None:
            result.update(route="unavailable",
                          oa_status=u["status"],
                          reason=result["reason"] or "非开放获取，需机构订阅或人工")
            return result

    result.update(route="unavailable",
                  reason=result["reason"] or "无 DOI/PMCID，无法自动获取")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pmcid")
    ap.add_argument("--doi")
    ap.add_argument("--keys-file", help="JSON 数组，Zotero item key 列表")
    ap.add_argument("--items", default="/tmp/zot_items_now.json")
    ap.add_argument("--out", default="./ft")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    tasks = []
    if a.pmcid or a.doi:
        # 显式指定时：PMCID 直连，不必先 search；DOI 才需要 search 换 PMCID
        rec = {} if a.pmcid else search_epmc(doi=a.doi)
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", a.doi or "", flags=re.I)
        tasks.append((rec, {"key": a.pmcid or doi.replace("/", "_"),
                            "title": rec.get("title", ""),
                            "doi": rec.get("doi") or doi,
                            "pmcid": a.pmcid or rec.get("pmcid") or ""}))
    else:
        items = {i["key"]: i for i in json.load(open(a.items))}
        keys = json.load(open(a.keys_file))
        for k in keys:
            d = items[k]["data"]
            doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", (d.get("DOI") or ""), flags=re.I)
            if not doi:
                m = re.search(r"10\.\d{4,9}/[^\s\"<>]+", d.get("url") or "")
                doi = m.group(0).rstrip(".") if m else ""
            rec = search_epmc(doi=doi or None)
            pmcid = rec.get("pmcid") or ""
            if not pmcid:
                pm = re.search(r"(PMC\d{5,9})", (d.get("extra") or "") + (d.get("url") or ""))
                pmcid = pm.group(1) if pm else ""
            tasks.append(({"pmcid": pmcid, "doi": doi},
                          {"key": k, "title": (d.get("title") or ""), "doi": doi, "pmcid": pmcid}))
            time.sleep(0.25)

    results = []
    for rec, meta in tasks:
        r = process(rec, a.out, meta)
        results.append(r)
        icon = {"europepmc-xml": "OK ", "oa-pdf": "PDF", "suspect-short": "SH?",
                "xml-empty": "EPM", "unavailable": " --"}.get(r["route"], " ??")
        print(f"[{icon}] {r['key']:<10} {r.get('body_chars',''):>7} "
              f"{(meta.get('title') or '')[:52]} {r.get('reason','')}")
        time.sleep(0.2)

    json.dump(results, open(os.path.join(a.out, "_fetch_report.json"), "w"),
              ensure_ascii=False, indent=1)
    n = len(results)
    xml = sum(1 for r in results if r["route"] == "europepmc-xml")
    pdf = sum(1 for r in results if r["route"] == "oa-pdf")
    emp = sum(1 for r in results if r["route"] == "xml-empty")
    bad = sum(1 for r in results if r["route"] == "unavailable")
    sus = sum(1 for r in results if r["route"] == "suspect-short")
    print(f"\n合计 {n} 篇：XML 直取 {xml} · 需PDF转换 {pdf + emp}（其中 {emp} 篇因 Europe PMC 无全文 XML）"
          f" · 疑似非论著 {sus} · 不可得 {bad}")
    print(f"报告已写 {os.path.join(a.out, '_fetch_report.json')}")


if __name__ == "__main__":
    main()
