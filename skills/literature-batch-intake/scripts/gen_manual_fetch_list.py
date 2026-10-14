#!/usr/bin/env python3
"""生成「待人工取件清单（含完整标题）」——给用户去下载用。

规则（用户 2026-09-19 指示）：**找不到全文时，要列出文章的完整标题，不只给 key。**
来源：L1 卡 frontmatter（title/doi/journal/year/priority）；标题被卡片截断的用 Crossref 补全。
用法：python gen_manual_fetch_list.py [--date YYYYMMDD]
"""
import argparse
import json
import os
import re
import time
import urllib.request

VAULT = os.environ.get("RESEARCH_VAULT", os.path.expanduser("~/ResearchVault"))
CARDS = os.path.join(VAULT, "10_Triage/Cards")
NOTES = os.path.join(VAULT, "20_Notes")
OUTDIR = os.path.join(VAULT, "90_Meta/Sources")


def fm(path):
    t = open(path, encoding="utf-8").read()
    if not t.startswith("---"):
        return {}
    body = t.split("---", 2)[1]
    d = {}
    for ln in body.split("\n"):
        m = re.match(r"^([a-z_]+):\s*(.*?)\s*$", ln)
        if m:
            d[m.group(1)] = m.group(2).strip().strip('"')
    return d


def crossref_title(doi):
    if not doi:
        return None
    try:
        req = urllib.request.Request(
            "https://api.crossref.org/works/" + urllib.parse.quote(doi),
            headers={"User-Agent": "research-vault/1.0 (mailto:zhao@example.com)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            m = json.load(r)["message"]
        return (m.get("title") or [""])[0] or None
    except Exception:
        return None


def looks_truncated(t):
    """卡上标题常被截到 ~90 字符且无句末标点 ⇒ 判为截断。"""
    return len(t.rstrip()) >= 85 and not t.rstrip().endswith((".", "?", "!", ")"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=time.strftime("%Y%m%d"))
    a = ap.parse_args()

    have_note = {f.split("_")[0] for f in os.listdir(NOTES)
                 if f.endswith(".md") and not f.startswith("_")}
    rows = []
    for f in sorted(os.listdir(CARDS)):
        if not f.endswith(".md"):
            continue
        p = os.path.join(CARDS, f)
        body = open(p, encoding="utf-8").read()
        d = fm(p)
        key = d.get("zotero_key", "")
        if not key or key in have_note:
            continue
        # ★ 已判「排除」的卡不进取件清单（会议摘要一类永远取不到，取了也没用）
        dec = re.findall(r"^-\s*决定：\s*(\S+)", body, re.M)
        if dec and dec[-1].startswith("排除"):
            continue
        route = (d.get("fulltext_route", "") or "").split("#")[0].strip()
        if route not in ("none", "manual"):
            continue                       # oa_pdf / epmc_xml 等自动通道的仍在处理中
        # manual 通道但 PDF 已落 40_Fulltext/pdf 的 = 已取到，不列入取件清单
        if route == "manual" and os.path.exists(os.path.join(VAULT, "40_Fulltext/pdf", key + ".pdf")):
            continue
        title = d.get("title", "")
        full = title
        if looks_truncated(title) or len(title) < 60:
            got = crossref_title(d.get("doi", ""))
            if got and len(got) > len(title):
                full = got
                time.sleep(0.4)
        rows.append(dict(key=key, pri=d.get("priority", ""), year=d.get("year", ""),
                         journal=d.get("journal", ""), doi=d.get("doi", ""),
                         title=full, card_title=title,
                         truncated=(full != title),
                         link=("https://doi.org/" + d["doi"]) if d.get("doi") else ""))
    rows.sort(key=lambda r: (r["pri"], r["key"]))

    out = [f"# 待人工取件清单（含完整标题）· {a.date}", "",
           "> 用途：自动通道已穷尽、需要**人工下载 PDF** 的文献。**给的是完整标题**（卡片标题截断的已用 Crossref 补全，"
           "并在「来源」列标注 `Crossref 补全`）。",
           "> 取到后把 PDF 丢过来即可，会走 `manual` 通道入档并建 L2（`ingest_local_pdf.py`）。",
           "> 生成：`90_Meta/State/gen_manual_fetch_list.py`（**脚本生成，勿手改**）", "",
           f"共 **{len(rows)}** 篇（P0 {sum(1 for r in rows if r['pri']=='P0')} · "
           f"P1 {sum(1 for r in rows if r['pri']=='P1')} · "
           f"P2 {sum(1 for r in rows if r['pri']=='P2')}）", "",
           "| # | key | 优先 | 年 | 刊 | 完整标题 | DOI | 标题来源 |",
           "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        out.append("| %d | `%s` | **%s** | %s | %s | %s | %s | %s |" % (
            i, r["key"], r["pri"], r["year"], r["journal"].replace("|", "/"),
            r["title"].replace("|", "/"), r["link"],
            "Crossref 补全" if r["truncated"] else "L1 卡"))
    out += ["", "---", "", "## 纯标题（便于逐条复制去搜）", ""]
    for i, r in enumerate(rows, 1):
        out.append("%d. **%s**  \n   %s  \n   `%s`｜%s %s｜%s" % (
            i, r["title"], r["journal"], r["key"], r["year"], r["pri"] or "-", r["link"]))
    p = os.path.join(OUTDIR, f"待人工取件清单_{a.date}.md")
    open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("写出", p, "｜", len(rows), "篇")
    for r in rows:
        print(f"  [{r['pri']}] {r['key']}  {r['title'][:95]}{' …' if r['truncated'] else ''}")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    main()
