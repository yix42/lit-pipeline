#!/usr/bin/env python3
"""PMC 文章页 HTML → Markdown。

为什么需要这条路：
  Europe PMC 的 fullTextXML 端点对部分 PMCID 稳定返回 HTTP 500，
  但其对应的 PMC 文章页 HTML 是可获取的（需浏览器 UA + curl）。
  这是 XML 通道失效时的等效替代，产出仍为结构化 Markdown。

不做什么：
  * 不猜内容——只做标签到 Markdown 的结构映射
  * 不提取导航区（References / Associated Data / ACTIONS / Cite 等）
"""
import html
import json
import os
import re
import sys

OUTDIR = os.environ.get("RESEARCH_VAULT", os.path.expanduser("~/ResearchVault")) + "/40_Fulltext/md"

# 只保留这些顶层章节（PMC 页面的 h2），其余（导航、参考文献等）丢弃
KEEP_H2 = {"key points", "abstract", "introduction", "background", "methods",
           "materials and methods", "results", "discussion", "conclusion",
           "conclusions", "limitations", "statistical analysis", "study design"}
STOP_H2 = {"references", "associated data", "actions", "resources", "cite",
           "add to collections", "permalink", "supplementary materials",
           "acknowledgments", "acknowledgements", "funding", "author information",
           "article information", "comment in", "similar articles", "cited by",
           "publication types", "grant support", "figures", "tables"}


def clean(s):
    s = re.sub(r"<(script|style|nav|noscript)\b[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<sup[^>]*>", "^", s)
    s = re.sub(r"<sub[^>]*>", "_", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u2009", " ").replace("\u200a", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def table_to_md(tbl):
    rows = []
    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tbl, re.S | re.I):
        cells = [clean(c) for c in re.findall(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", tr, re.S | re.I)]
        if cells:
            rows.append(cells)
    if not rows:
        return []
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "---|" * w]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return out


DEGREE = re.compile(r"\b(MD|PhD|MSc|MPH|MBBS|DO|RN|NP|BSc|BA|BS|BSN|MS|MA|FRCP|FACC|MPH|MBBCh)\b")
PERSON = re.compile(r"^[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\.\-]+){1,3}$")
NAVWORDS = {"permalink", "actions", "resources", "cite", "add to collections"}


def is_author_head(txt):
    """PMC 用 h4 排版作者列表（'Nassir F Marrouche, MD'）。
    这类 h4 是噪音，须剔除；但要保留 Key Points 下的 'Question'/'Findings' 等单词标题。"""
    if DEGREE.search(txt):
        return True
    return bool(PERSON.match(txt))


def extract(path, key, title, meta_note, zkey=""):
    """key = PMCID（如 PMC9214588）；zkey = 真 Zotero 8 位 key（如 PATT7B2D）。

    ⚠️ 二者**不可混用**：本函数的第一参数一直是 PMCID，早期版本却把它写进了
    frontmatter 的 `zotero_key`，导致 L2 笔记按 zotero_key 反查全文时指向不存在的键。
    现分开：`zotero_key` 只填 zkey，PMCID 另立 `pmcid` 字段。
    """
    h = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"<main\b[^>]*>(.*?)</main>", h, re.S | re.I)
    if not m:
        m = re.search(r"<article\b[^>]*>(.*?)</article>", h, re.S | re.I)
    body = m.group(1) if m else h

    # 按出现顺序扫描块级元素
    blocks = []
    pat = re.compile(r"<h([1-4])\b[^>]*>(.*?)</h\1>|<p\b[^>]*>(.*?)</p>|<table\b[^>]*>(.*?)</table>",
                     re.S | re.I)
    stopped = False
    for mm in pat.finditer(body):
        if stopped:
            break
        if mm.group(1):                                   # 标题
            lvl, txt = int(mm.group(1)), clean(mm.group(2))
            if not txt:
                continue
            low = txt.lower().strip().rstrip(".")
            if is_author_head(txt) or low in NAVWORDS:
                continue
            if lvl == 2:
                if low in STOP_H2:
                    stopped = True
                    continue
                # 跳过与 frontmatter title 重复的首个标题
                if not blocks and title[:50].lower() in low:
                    continue
            blocks.append(("h", lvl, txt))
        elif mm.group(3):                                 # 段落
            txt = clean(mm.group(3))
            if len(txt) > 12:
                blocks.append(("p", 0, txt))
        elif mm.group(4):                                 # 表格
            md = table_to_md(mm.group(4))
            if md:
                blocks.append(("t", 0, "\n".join(md)))

    out = ["---",
           f'title: "{title}"',
           f'zotero_key: "{zkey}"',
           f'pmcid: "{key}"',
           f'source_type: {meta_note}',
           f'source_url: https://pmc.ncbi.nlm.nih.gov/articles/{key}/',
           "---", "", f"# {title}", ""]
    for kind, lvl, txt in blocks:
        if kind == "h":
            out += ["#" * (lvl + 1) + " " + txt, ""]
        elif kind == "p":
            out += [txt, ""]
        else:
            out += [txt, ""]
    return "\n".join(out), len(blocks)


JOBS = [
    ("/tmp/pmc.html", "PMC9214588", "PATT7B2D",
     "Effect of MRI-Guided Fibrosis Ablation vs Conventional Catheter Ablation on Atrial Arrhythmia Recurrence in Patients With Persistent Atrial Fibrillation: The DECAAF II Randomized Clinical Trial",
     "pmc-html (Europe PMC XML 端点返回 500，改用 PMC 文章页)"),
    ("/tmp/pmc_zx.html", "PMC11967559", "ZX245LJK",
     "Omnipolar Versus Bipolar Electrode Mapping in Patients With Atrial Fibrillation Undergoing Catheter Ablation",
     "pmc-html (Europe PMC XML 端点返回 500，改用 PMC 文章页)"),
]

os.makedirs(OUTDIR, exist_ok=True)
for path, pmcid, key, title, note in JOBS:
    if not os.path.exists(path):
        print(f"[skip] {key}: {path} 不存在")
        continue
    md, n = extract(path, pmcid, title, note, key)
    p = os.path.join(OUTDIR, f"{key}.md")
    open(p, "w", encoding="utf-8").write(md)
    print(f"[ok] {key}: {n} 个块 → {len(md)} 字符  -> {p}")
