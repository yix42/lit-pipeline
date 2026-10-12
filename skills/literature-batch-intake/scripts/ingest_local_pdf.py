#!/usr/bin/env python3
"""把**用户手供的本地 PDF** 入档为 `40_Fulltext/{pdf,md}/<key>.{pdf,md}`。

适用场景：自动通道（Europe PMC / PMC / Unpaywall / OpenAlex / 机构仓储）全部失败，
但用户在浏览器里点开并下载了出版社 PDF。这类件**只能人工取**，取到后走本脚本入档。

与 `fetch_gap_fulltext_*.py` 的区别：那些脚本走网络，本脚本只处理**已经在磁盘上**的 PDF。

用法：
    python ingest_local_pdf.py manifest.json

manifest.json 形如：
    [{"key": "XPUKL6KE",
      "pdf": "/Users/xxx/Downloads/1-s2.0-....pdf",
      "doi": "10.1016/j.jacep.2019.06.002",
      "pmid": "31753431",
      "citation": "JACC Clin Electrophysiol 2019;5(11):1265-1277",
      "title": "..."}]

硬规矩（与技能 §7f 一致）：
- **多栏 PDF 必须重排**：`reflow_two_column_pdf.py`。不重排的话笔记里的引语一条都核不了。
- 原档必须留在 `40_Fulltext/pdf/`，**逐字不改**（重排只改线性顺序）。
- 入档后核对**字母数字总数**，确认重排没丢正文（跑眉去重、表格搬位会造成小幅下降，属预期）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata

VAULT = os.environ.get("RESEARCH_VAULT", os.path.expanduser("~/ResearchVault"))
STATE = os.path.join(VAULT, "90_Meta/State")
REFLOW = os.path.join(STATE, "reflow_two_column_pdf.py")
PYTHON = sys.executable


def alnum(s):
    return re.sub(r"[^0-9A-Za-z]", "", s)


def reflow(pdf_path, out_md):
    subprocess.run([PYTHON, REFLOW, pdf_path, out_md], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def build_frontmatter(e, n_pages, extractor_note):
    q = lambda s: '"' + str(s).replace('"', "'") + '"'
    lines = ["---",
             f"title: {q(e['title'])}",
             f"zotero_key: {e['key']}",
             f"doi: {q(e.get('doi', ''))}",
             f"pmid: {q(e.get('pmid', ''))}",
             f"citation: {q(e.get('citation', ''))}",
             f"pages: {n_pages}",
             f"extractor: {q(extractor_note)}",
             'source_type: "manual"',
             f"source_note: {q(e.get('source_note', '用户手供出版社 PDF（出版版）；多栏重排后抽文本；非镜像、非接受稿'))}",
             f"reflow: {q('multi-column→single-column：① 按 block x 坐标聚类分栏（栏数不写死），页内先左栏后右栏；② 表格块移出正文流、页末集中输出（跨栏块不做水平分隔带）；③ 页眉页脚按纵向带摘出 + 段落延续保护（间距≤2.9×行高中位数者留回正文）；④ 图内文字按字号判据（<正文众数×0.90）摘出；⑤ 块内软换行合并 + 跨块仅同栏且正常行距者合并；⑥ C0 控制字符字形还原（\\\\x01/\\\\x02→±，\\\\x03 位置相关）。只改线性顺序与字形，未增删一字')}",
             "---", ""]
    return "\n".join(lines)


def main():
    man = json.load(open(sys.argv[1], encoding="utf-8"))
    os.makedirs(os.path.join(VAULT, "40_Fulltext/pdf"), exist_ok=True)
    os.makedirs(os.path.join(VAULT, "40_Fulltext/md"), exist_ok=True)
    log = []
    for e in man:
        key, src = e["key"], e["pdf"]
        if not os.path.exists(src):
            print(f"[MISS-PDF] {key}: {src}"); continue
        dst_pdf = os.path.join(VAULT, "40_Fulltext/pdf", key + ".pdf")
        dst_md = os.path.join(VAULT, "40_Fulltext/md", key + ".md")
        if os.path.abspath(src) != os.path.abspath(dst_pdf):
            shutil.copy2(src, dst_pdf)
        tmp_md = "/tmp/_ingest_" + key + ".md"
        reflow(dst_pdf, tmp_md)
        import pymupdf
        doc = pymupdf.open(dst_pdf)
        raw = "".join(p.get_text() for p in doc)
        body = open(tmp_md, encoding="utf-8").read()
        note = ("pymupdf " + getattr(pymupdf, "__version__", "")
                + " + reflow_two_column_pdf.py（多栏重排）")
        out = build_frontmatter(e, doc.page_count, note) + body
        open(dst_md, "w", encoding="utf-8").write(out)
        a, b = len(alnum(raw)), len(alnum(body))
        rec = dict(key=key, pdf=dst_pdf, md=dst_md, pages=doc.page_count,
                   md_chars=len(out), alnum_raw=a, alnum_md=b,
                   alnum_delta=a - b, pdf_bytes=os.path.getsize(dst_pdf))
        log.append(rec)
        print(f"[OK] {key}: {doc.page_count} 页 · md {len(out)} 字符 · "
              f"字母数字 {a}→{b}（差 {a-b}，{100*(a-b)/max(a,1):.1f}%）")
    return log


if __name__ == "__main__":
    rows = main()
    stamp = os.environ.get("INGEST_STAMP", "run")
    p = os.path.join(STATE, f"ingest_local_pdf_{stamp}.json")
    json.dump(rows, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("state →", p)
