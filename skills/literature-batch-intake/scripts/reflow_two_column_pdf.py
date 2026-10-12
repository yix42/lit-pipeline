#!/usr/bin/env python3
"""多栏 PDF → 单栏读序 markdown。

问题：PyMuPDF 默认按「视觉行」输出，同一 y 高度上的各栏文字会被拼进同一行，
导致正文句子被邻栏文字打断。后果是笔记里的英文引语**无法逐字定位**——
看起来有引语、实际核不了。

三种版面会制造这类污染，本脚本按顺序处理：

1. **两栏**（多数医学刊）：左栏读完再读右栏。
2. **三栏 / 两栏 + 侧栏**（JACC 系列的「ABBREVIATIONS AND ACRONYMS」窄条就属此类）：
   若只按「页宽中线」分左右，正文中栏与右侧窄条会被一起按 y 排序 ⇒
   缩写行插进正文句子中间（实测形如
   ``...STUDY POPULATION. Patients were screened AT = atrial tachycardia and recruited...``）。
   故改为**按 x 区间重叠聚类分栏**，栏数不写死。
3. **跨栏块**（标题、跨栏图注、宽表）：当作**水平分隔带**，带内再分栏。

表格块（``page.find_tables()``）与页眉页脚统一移出正文流——否则表头和刊名会插进句子中间。

用法：
    python reflow_two_column_pdf.py <in.pdf> <out.md> [--col-gap 0.15] [--full-ratio 0.55]
"""
import sys
import re
import os


CAPTION_RE = re.compile(r"^\s*(Figure|Table|Supplementary|Appendix)\s*\d", re.I)

# 图内文字的字号阈值（相对正文众数）。**实测标定**（JACC 版式）：
#   正文 7.7 pt，图注 7.7 pt，图轴刻度 7.0 pt，小字号注释 5–6 pt。
# ⚠️ 0.90 是**扫描后取定的值**，不要凭直觉放宽：0.90 ⇒ 门限 6.93 pt；
#    放宽到 0.94（门限 7.24 pt）虽能收进 7.0 pt 的轴刻度（`1.71mV/46ms` 一类），
#    但把正文/图注一并扫走 —— 实测四篇合计未命中 **6 → 19 条**（XPUKL6KE 5→12、6Q8TMP9F 1→5）。
#    即：轴刻度字号与正文只差 0.7 pt，靠字号**无法**与正文分开，这是版式固有代价。
# 需要复现扫描时用 REFLOW_SMALL_RATIO 覆盖。
SMALL_SIZE_RATIO = float(os.environ.get("REFLOW_SMALL_RATIO", "0.90"))


def _cluster_columns(items, full_ratio_w):
    """按 x 区间重叠把块聚成栏。返回 [x_lo, x_hi, blocks]，按 x_lo 升序。

    不写死栏数：两栏、三栏、两栏+窄侧栏都能自动分开。
    """
    body = [b for b in items if (b[2] - b[0]) < full_ratio_w]
    cols = []
    for b in sorted(body, key=lambda b: b[0]):
        cols.append([b[0], b[2], [b]])
        changed = True
        while changed:                       # 迭代到收敛，避免插入顺序造成「本属同一栏却被拆开」
            changed = False
            for i in range(len(cols)):
                for j in range(len(cols) - 1, i, -1):
                    ov = min(cols[i][1], cols[j][1]) - max(cols[i][0], cols[j][0])
                    if ov > 0.5 * min(cols[i][1] - cols[i][0], cols[j][1] - cols[j][0]):
                        cols[i][0] = min(cols[i][0], cols[j][0])
                        cols[i][1] = max(cols[i][1], cols[j][1])
                        cols[i][2].extend(cols[j][2])
                        cols.pop(j)
                        changed = True
    cols.sort(key=lambda c: c[0])
    return cols


SENT_END = (".", ":", ";", "!", "?", ")", "]", "%", "|")


def _join_adjacent(ordered, line_h):
    """把相邻块黏回句子 —— **必须带几何条件**，否则会黏错。

    ★ 2026-09-19 修：原先把 `clean_soft_breaks` 施加在**整页文本**上，
    于是「上一行不以句末标点结尾 ⇒ 合并」这条会跨 block 生效，把不同栏/不同结构的块黏成一句。
    实测 s5（Wiley）首页：
        `O R I G I N A L  A R T I C L E` + `Martin Seifert MD1,2` + `Abstract` + 右栏首行
        → 黏成一整行，正文读序被打乱。
    现改为：**块内**软换行照旧合并（同一 block 必属同一栏，安全）；
    **跨块**只有同时满足「同栏重叠 + 纵向间距属正常行距 + 上块不带句末标点 + 不是图注」才合并。
    """
    out = []                                    # [x0, x1, y_bottom, text]
    for b in ordered:
        x0, y0, x1, y1, raw = b[0], b[1], b[2], b[3], b[4]
        t = clean_soft_breaks(raw).strip()
        if not t:
            continue
        if out and not CAPTION_RE.match(t):
            px0, px1, py1, pt = out[-1]
            ov = min(x1, px1) - max(x0, px0)
            same_col = ov > 0.5 * min(x1 - x0, px1 - px0)
            gap = y0 - py1
            if same_col and -1.0 <= gap <= 1.7 * line_h and not pt.endswith(SENT_END):
                out[-1] = [px0, px1, y1, pt + " " + t]
                continue
        out.append([x0, x1, y1, t])
    return [o[3] for o in out]


def reflow(pdf_path, col_gap=0.15, full_ratio=0.55):
    import pymupdf

    doc = pymupdf.open(pdf_path)
    out = []
    marginalia = []
    for pno, page in enumerate(doc, 1):
        H = page.rect.height
        W = page.rect.width
        tab_rects = []
        try:
            for t in page.find_tables():
                tab_rects.append(pymupdf.Rect(t.bbox))
        except Exception:
            pass

        def in_table(b):
            br = pymupdf.Rect(b[:4])
            area = max(br.get_area(), 1e-6)
            for tr in tab_rects:
                if (br & tr).get_area() / area > 0.5:
                    return True
            return False

        blocks = [b for b in page.get_text("blocks") if b[4].strip()]
        tables = sorted([b for b in blocks if in_table(b)], key=lambda b: (b[1], b[0]))
        rest = [b for b in blocks if not in_table(b)]

        # 字号判据：图注/图轴/小字号注释常与正文同栏同带，纯几何分不开；
        # 但它们的字号明显小于正文（实测 JACC：正文 9.5 pt，图轴 5–7 pt）。
        # 不摘出去的话，它们会插进正文行之间，把句子切断 ⇒ 引语无法逐字定位。
        sizes, modal = {}, {}
        for db in page.get_text("dict")["blocks"]:
            if db.get("type") != 0:
                continue
            sz, tx = [], ""
            for ln in db["lines"]:
                for sp in ln["spans"]:
                    if sp["text"].strip():
                        sz.append(sp["size"]); tx += sp["text"]
            if not tx.strip():
                continue
            key = tuple(round(v, 1) for v in db["bbox"])
            sizes[key] = sorted(sz)[len(sz) // 2]
            modal[round(sizes[key], 1)] = modal.get(round(sizes[key], 1), 0) + len(tx.strip())
        modal_size = None
        if modal:
            top, cnt = max(modal.items(), key=lambda kv: kv[1])
            if cnt / max(sum(modal.values()), 1) > 0.40:      # 只有当众数确实占主导才启用
                modal_size = top

        def blk_size(b):
            return sizes.get(tuple(round(v, 1) for v in b[:4]))

        # ★ 跑边判据（纵向带）+ **段落延续保护**（2026-09-19 增补）
        # 主判据仍是纵向位置（y1 < 8.5%H / y0 > 92.5%H）——「页首短行」「是否落在栏内」
        # 这类启发式实测都更差，不再启用。但纵向带会把**正文段落的首/末行**一并卷走
        # （实测 JACC 实测：每页 1–3 行，如 `these criteria were excluded.`、`mean ± SD …`），
        # 这些行进入附录桶后正文被割成两半，引语核验直接失败。
        # 故补一道**机械**判据：与同 x 栏带内**非跑边块**的纵向间距若属正常行距（≤2.9×行高中位数），
        # 即判该块是正文段落的延续，留回正文流。
        # 实测分离度：真跑边（刊名/卷期/页码/收稿行）比值 3.2–10.8，正文行 0.3–2.8，阈值 2.9 处干净分开。
        band, normal = [], []
        for b in rest:
            if b[3] < 0.085 * H or b[1] > 0.925 * H:
                band.append(b)
            else:
                normal.append(b)
        hs = [b[3] - b[1] for b in normal if b[3] > b[1]]
        line_h = sorted(hs)[len(hs) // 2] if hs else 10.0
        LETTERSPACED = re.compile(r"(?:\b[\w&]\b\s+){5,}")   # `J A C C : C L I N I C A L …` 字间距报刊头
        for b in band:
            x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
            w = x1 - x0
            nearest = 1e9
            for c in normal:
                ov = min(x1, c[2]) - max(x0, c[0])
                if ov <= 0.5 * min(w, c[2] - c[0]):
                    continue
                nearest = min(nearest, abs(y0 - c[3]), abs(c[1] - y1))
            keep_body = (nearest / line_h <= 2.9
                         and w < full_ratio * W
                         and not LETTERSPACED.search(txt)
                         and not re.fullmatch(r"[\d\s]+", txt.strip()))
            if keep_body:
                normal.append(b)                     # 正文段落延续 → 留回正文流
            else:
                marginalia.append((pno, y0, txt))    # 页眉页脚：跑边内容

        captions, flows, other, small, body_blocks = [], [], [], [], []
        for b in normal:
            x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
            if (modal_size and blk_size(b) and blk_size(b) < modal_size * SMALL_SIZE_RATIO
                    and not CAPTION_RE.match(txt)):
                small.append(b)                        # 图内文字（轴标/图例/小字号注释）
                continue                               # 不进正文流，页末统一输出
            body_blocks.append(b)
            if CAPTION_RE.match(txt):
                captions.append(b)                     # 图注 / 表注
            elif (x1 - x0) >= full_ratio * W:
                other.append(b)                        # 跨栏块：多栏页里页末统一输出
                                                       # （**不可**当分隔带，否则表注会插进跨页句中间）
            else:
                flows.append(b)
        captions.sort(key=lambda b: (b[1], b[0]))
        other.sort(key=lambda b: (b[1], b[0]))
        small.sort(key=lambda b: (b[1], b[0]))
        cols = _cluster_columns(flows, full_ratio * W)

        # 单栏页（摘要页、通信、单栏表格页）：栏概念不存在，按 y 直排即可——
        # 否则「跨栏块 ⇒ 页末输出」这条规则会把标题搬到大作者名单之后（实测页序错乱）。
        if len(cols) <= 1:
            ordered = sorted(body_blocks, key=lambda b: (b[1], b[0]))
        else:
            ordered = list(captions)
            for c in cols:
                ordered += sorted(c[2], key=lambda b: (b[1], b[0]))
            ordered += other
        lines = _join_adjacent(ordered, line_h)
        if small:
            lines.append("<!-- 图内文字（按字号判据摘出，避免插入正文行间） -->")
            lines += [clean_soft_breaks(b[4]).strip() for b in small]
        lines += [clean_soft_breaks(b[4]).strip() for b in tables]
        body = "\n".join(x for x in lines if x)
        out.append(f"<!-- page {pno} -->\n{body}")
    if marginalia:
        seen, keep = set(), []
        for pno, y, t in sorted(marginalia):
            key = re.sub(r"\d+", "#", t.strip())
            if key in seen:                     # 每页重复的跑眉只留一次
                continue
            seen.add(key)
            keep.append(f"[p{pno}] {t.strip()}")
        out.append("<!-- 页眉页脚汇总（已从正文流移出，避免插入跨页句子） -->\n" + "\n".join(keep))
    return "\n\n".join(out)


def clean_soft_breaks(text):
    """合并 PDF 硬换行：行尾连字符断词 → 合并；行尾无句末标点 → 空格合并。

    PDF 的 block 内部换行只是排版换行，不是语义换行。不合并的话，
    笔记里的英文引语（一句跨了 3 行）就无法在档案里逐字定位。
    """
    lines = text.split("\n")
    res = []
    for ln in lines:
        s = ln.rstrip()
        if res:
            prev = res[-1]
            # ⚠️ 不可跨「结构标记」合并：页眉页脚附录的行以 `[pN]` 开头、
            # 分页/分节标记以 `<!--` 开头。不挡住的话，正文最后一行会与附录首行黏成一句
            # （实测把 COI 段与 `[p1] received research and fellowship support…` 拼在一起）。
            if s.startswith("<!--") or s.startswith("[p"):
                res.append(s)
                continue
            if prev.startswith("<!--") or prev.startswith("[p"):
                res.append(s)
                continue
            if prev.endswith("-") and len(prev) > 1 and prev[-2].isalpha() and re.match(r"^[a-z]", s):
                res[-1] = prev[:-1] + s.lstrip()
                continue
            if prev and not prev.endswith((".", ":", ";", "!", "?", ")", "]", "%", "|")):
                res[-1] = prev + " " + s.lstrip()
                continue
        res.append(s)
    return "\n".join(res)


def unicode_normalize(text):
    """NFKC 归一化 + 出版社 PDF 的两类常见错位修复。

    ① **连字/引号/连字符**：``Scientiﬁc``（U+FB01）、``patients’``（U+2019）、
       ``Figure 5``（U+2005 窄空格）—— 不归一化，笔记里手打的 ASCII 版本就匹配不上。
    ② ★ **控制字符字形错位**：Elsevier 的 PDF 会把数学符号排成 Symbol 字体，
       抽出来是 C0 控制字符。实测（四篇 JACC 稿件逐字符统计）：
         ``\\x01`` / ``\\x02`` → ``±``
         ``\\x03`` → **位置相关**，且可按上下文机械区分：
           · 前后都是数字（`215.0 \\x03 69.2`、`7.07 \\x03 1.55`）→ ``±``（均值±SD）
           · **紧贴**数字之前、前一字符是 ``(``/换行/空格（`(\\x030.006 to 0.009)`、`\\x030.003`）
             → **负号**（XPUKL6KE 表 5 的 36 处全属此类）
       **不修的话，档案里的 ``1.04 \\x01 0.43 mV`` 无法与笔记里的 ``1.04 ± 0.43 mV`` 对上**，
       引语核验会成批误报（实测一篇 22 条）；**而把 ``±`` 误还原成 ``-`` 更糟——那是静默改数**。
    """
    import unicodedata

    text = unicodedata.normalize("NFKC", text)
    for a, b in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2013", "-"), ("\u2014", "-"), ("\u2212", "-"), ("\u00a0", " ")):
        text = text.replace(a, b)
    text = text.replace("\x01", "\u00b1").replace("\x02", "\u00b1")
    # \x03 位置相关：数字之间的是 ±（均值±SD）；紧贴数字之前的是负号
    text = re.sub(r"(?<=\bmean )\x03", "\u00b1", text)
    text = re.sub(r"(?<=\d)\s*\x03\s*(?=\d)", "\u00b1", text)
    text = text.replace("\x03", "-")
    # 其余 C0 控制字符一律去掉（不可见、不可引用）
    text = "".join(ch for ch in text
                   if ord(ch) >= 32 or ch in "\n\t")
    return text


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    gap, fr = 0.15, 0.55
    for a in sys.argv[1:]:
        if a.startswith("--col-gap"):
            gap = float(a.split("=", 1)[1]) if "=" in a else 0.15
        if a.startswith("--full-ratio"):
            fr = float(a.split("=", 1)[1]) if "=" in a else 0.55
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    txt = reflow(args[0], gap, fr)
    # ⚠️ 不要在这里再对**整篇**跑 clean_soft_breaks：软换行合并在 reflow() 内
    #    已按「块内 + 几何跨块」处理（见 _join_adjacent）。全局跑会跨 block 黏行，
    #    把页首的结构行（刊头/作者/Abstract）与正文黏成一句，读序被打乱。
    txt = unicode_normalize(txt)
    with open(args[1], "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"wrote {args[1]}  {len(txt)} chars")
