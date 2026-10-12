#!/usr/bin/env python3
"""清洗 pymupdf-layout 抽出的表格单元格。

实测（8 份真实 PDF / 29 张表 / 1,120 个非空单元格）：改动 501 个（45%）；
粘连候选 254 个自动修复 195 个（77%），其余保守保留。

## 能修的（实测有效）
  1. 英文词间空格丢失      "Dynamicviscosity" → "Dynamic viscosity"
  2. 小数点被空格拆开      "0 .5 - 0 .75 mm"  → "0.5 - 0.75 mm"
  3. 中文单字逐行换行      "申\\n请\\n者\\n信\\n息"   → "申请者信息"
  4. CJK 字符间多余空格    "性 别"              → "性别"
  5. 连字丢字（见下）      "fnite" → "finite"

## 修不了的（重要，别抱期望）
  - **整段丢空格**："Wepresentanewnumericalsimulationframeworkforpredictionoffowpatterns…"（85 字符无空格）
    这类只能靠 Europe PMC XML 或人工，清洗器一律不动（拆开风险极高）。
  - **术语粘连**："Hypertrophiccardiomyopathy"、"Ironoverloadcardiomyopathy"
    需要医学术语感知才能拆，通用词典做不到。
  - **抽取顺序错乱**：如 '省自然科学基金委员会办\\n主管处室\\n公室'，字符都在但顺序乱了。
    清洗器保留断点线索（只合并"单字行"的换行），不假装修好。

## 连字（ligature）问题 —— 本技能最容易忽略的坑
同一篇 PDF，`page.get_text()` 里 'finite'/'defined'/'confirm' 全部正确，
但 `find_tables()` 抽出的摘要框里是 'fnite'/'defned'/'confrming'——**连字字形被整块丢掉**。
本模块的解法：用 `build_doc_vocab(doc)`（由 get_text() 建的**正确**词表）当拼写字典，
只接受"删掉一个字母即等于它"的**唯一**候选。等于拿文档自己的正确文本纠自己的错。

## 为什么必须传 doc_vocab
不传就只剩系统词典（web2）一条判据，误切率显著上升：
实测 'Reynoldsnumber' 会被切成 'Reynold|snum|ber'（web2 里真有 'snum'）。
传入本文词表后变为正确的 'Reynolds number'，而 DNA 序列 'CCGATGGGTTGTACCTTGTC'
仍被正确拒绝（它不会在正文里作为独立词出现）。

## 用法
库：
    from table_clean import clean_table, build_doc_vocab
    dv = build_doc_vocab(doc)                      # 每份文档建一次
    rows = clean_table(page.find_tables().tables[0].extract(), doc_vocab=dv)

自测（对真实 PDF 跑抽取+清洗并打印前后对比）：
    python3 table_clean.py /path/a.pdf /path/b.pdf
"""
import os
import re
import sys

# ---------------------------------------------------------------- CJK 处理

CJK = r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"
_CJK_CHAR = re.compile(f"[{CJK}]")
# 两个 CJK 字符之间的空白 → 删掉（"性 别" → "性别"）
_CJK_GAP = re.compile(f"(?<=[{CJK}])[ \\t\\u3000]+(?=[{CJK}])")


def _fix_cjk(s: str) -> str:
    """合并中文单字换行 + 字间空格。

    ⚠️ 换行**只在某一侧是"单字行"时才合并**。实测教训：无差别地把 CJK 换行全删，
    会把抽取顺序已经错乱的单元格糊成一团——例如
        '省自然科学基金委员会办\\n主管处室\\n：\\n公室'
    无差别合并 → '省自然科学基金委员会办主管处室：公室'（更难发现顺序错了）
    有条件合并 → '省自然科学基金委员会办 主管处室 ： 公室'（保留了断点线索）
    而对真正的逐字换行 '申\\n请\\n者\\n信\\n息' 两侧都是单字，仍能正确合成 '申请者信息'。
    """
    s = _CJK_GAP.sub("", s)
    lines = s.split("\n")
    if len(lines) < 2:
        return s
    out = [lines[0]]
    for ln in lines[1:]:
        prev, cur = out[-1].strip(), ln.strip()
        joined = (_CJK_CHAR.fullmatch(cur) is not None) or (_CJK_CHAR.fullmatch(prev) is not None)
        if joined and prev and cur and _CJK_CHAR.search(prev[-1]) and _CJK_CHAR.search(cur[0]):
            out[-1] = out[-1].rstrip() + cur
        else:
            out.append(ln)
    return "\n".join(out)


# ---------------------------------------------------------------- 数字

# "0 .5" / "0. 5" / "1, 000" 之类的错误断字
_DEC_SPACE = re.compile(r"(?<=\d)\s*\.\s*(?=\d)")


def _fix_numbers(s: str) -> str:
    """'0 .5 - 0 .75 mm' → '0.5 - 0.75 mm'。只贴合小数点，不动单位前的空格。"""
    return _DEC_SPACE.sub(".", s)


# ---------------------------------------------------------------- 英文粘连

_words = None


def _load_vocab():
    """加载系统词典。macOS: /usr/share/dict/words（web2）。加载失败则退化为不拆分。"""
    global _words
    if _words is not None:
        return _words
    _words = set()
    for p in ("/usr/share/dict/words", "/usr/dict/words"):
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    _words = {w.strip().lower() for w in f if w.strip()}
                break
            except OSError:
                pass
    return _words


def build_doc_vocab(doc) -> set:
    """收集一份文档里"独立出现过"的小写英文词，作为拆词的第二道判据。

    ⚠️ 为什么需要它：单靠系统词典（web2）会把 'Reynoldsnumber' 切成
       'Reynold|snum|ber'（web2 里确实有 'snum' 这种词条）——实测踩过。
       要求"每一部分都在本文正文里独立出现过"能把这类误切挡掉，因为 'snum'
       不会作为独立词出现在一篇流体力学论文里。
    """
    txt = []
    for pg in doc:
        txt.append(pg.get_text())
    return {w.lower() for w in re.findall(r"[A-Za-z]{2,}", "\n".join(txt))}


def _segment(tok: str, vocab: set, doc_vocab=None, min_part=4, max_parts=3):
    """把粘连 token 切成全词典词。切不开 / 不够可信就返回 None（宁缺勿滥）。"""
    low = tok.lower()
    n = len(low)
    if n < 9 or low in vocab:
        return None

    INF = 10 ** 6
    best = [INF] * (n + 1)
    cut = [None] * (n + 1)
    best[n] = 0
    for i in range(n - 1, -1, -1):
        for j in range(i + min_part, min(n, i + 18) + 1):
            part = low[i:j]
            # 判据取"系统词典 OR 本文词表"的并集。
            # ⚠️ 只用系统词典会漏：web2 缺大量屈折形式，'functions'、'simulations'
            #    都不在表里，导致 'Radialbasisfunctions' 拆不开。而本文词表是从
            #    正文 get_text() 建的，反而更全、更贴身。
            if part not in vocab and (doc_vocab is None or part not in doc_vocab):
                continue
            if best[j] + 1 < best[i]:
                best[i] = best[j] + 1
                cut[i] = j
    if best[0] == INF or best[0] > max_parts:
        return None

    out, i = [], 0
    while i < n:
        j = cut[i]
        out.append(tok[i:j])
        i = j
    # 最后一道自检：所有部分长度达标，否则放弃
    if any(len(p) < min_part for p in out):
        return None
    return out


# ⚠️ 不能加 ^...$ 锚点：单元格常含多个 token（'Heartfrequency Strokevolume'），
#    带锚点会导致整个单元格一个都匹配不到，run-on 修复静默失效。实测踩过这个坑。
_TOKEN = re.compile(r"[A-Za-z][A-Za-z\-]{7,}")
_ALPHA_TOKEN = re.compile(r"[A-Za-z]{4,}")


def _repair_ligature(s: str, doc_vocab) -> str:
    """修复 layout 路径丢连字字形（ﬁ/ﬂ/ﬀ）导致的缺字。

    实测：同一篇 CFD 论文，get_text() 里 'finite'/'defined'/'confirm' 全部正确，
    但 find_tables() 抽出的摘要框里是 'fnite'/'defned'/'confrming'——连字字形被整块丢掉。

    做法：**返回文档自身的词表**（由 get_text() 建，是正确的）当拼写字典。
    若某 token 不在任何词典里，但在正文词表中存在"删掉一个字母即等于它"的唯一候选，
    就认定是丢字并还原。用文档自己的正确文本纠自己的错，不引入外部假设。

    只接受唯一匹配；多个候选一律不动（宁缺勿滥）。
    """
    if not doc_vocab:
        return s
    by_len = {}
    for w in doc_vocab:
        by_len.setdefault(len(w), []).append(w)

    def repl(m):
        tok = m.group(0)
        low = tok.lower()
        if low in doc_vocab:
            return tok
        cands = {w for w in by_len.get(len(low) + 1, ())
                 if any(w[:i] + w[i + 1:] == low for i in range(len(w)))}
        if len(cands) == 1:
            fixed = next(iter(cands))
            return fixed.capitalize() if tok[0].isupper() else fixed
        return tok

    return _ALPHA_TOKEN.sub(repl, s)


def _fix_runon(s: str, doc_vocab=None) -> str:
    """对长全字母 token 逐个尝试按词典切词，保留原有分隔符。"""
    vocab = _load_vocab()
    if not vocab:
        return s

    def repl(m):
        tok = m.group(0)
        parts = _segment(tok, vocab, doc_vocab)
        return " ".join(parts) if parts else tok

    return _TOKEN.sub(repl, s)


# ---------------------------------------------------------------- 主入口

_PUNCT_SPACE = re.compile(r"\s+([,;:)\]}%])")
_OPEN_SPACE = re.compile(r"([(\[{])\s+")


def clean_cell(v, do_runon=True, doc_vocab=None) -> str:
    """清洗单个单元格。

    doc_vocab: 由 build_doc_vocab(doc) 得到的本文词汇表。**强烈建议传入**——
               它是英文粘连拆词可信度的主要保障，不传会显著提高误切风险。
    """
    if v is None:
        return ""
    s = str(v).replace("\u00ad", "").replace("\xa0", " ")
    s = _fix_cjk(s)                       # 先合并中文换行（避免被后续换行替换打断）
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)  # 剩余换行 → 空格
    s = _fix_numbers(s)
    if do_runon:
        s = _repair_ligature(s, doc_vocab)   # 先补丢字，再拆粘连
        s = _fix_runon(s, doc_vocab)
    s = re.sub(r"\s{2,}", " ", s)
    s = _PUNCT_SPACE.sub(r"\1", s)
    s = _OPEN_SPACE.sub(r"\1", s)
    return s.strip()


def clean_table(rows, doc_vocab=None):
    """清洗整张表（list[list[str]]）。"""
    if not rows:
        return rows
    return [[clean_cell(c, doc_vocab=doc_vocab) for c in row] for row in rows]


def _row_density(rows):
    """非空单元格占比，用来判断抽取质量。"""
    cells = [c for r in rows for c in r]
    if not cells:
        return 0.0
    return sum(1 for c in cells if c.strip()) / len(cells)


# ---------------------------------------------------------------- 自测

def _selftest(paths):
    import pymupdf
    import pymupdf.layout  # noqa: F401  激活 layout

    tot_raw = tot_clean = 0
    shown = 0
    for p in paths:
        doc = pymupdf.open(p)
        dv = build_doc_vocab(doc)        # 本文词汇表，用于拆词可信度校验
        for i, pg in enumerate(doc):
            try:
                tabs = pg.find_tables().tables
            except Exception:                       # noqa: BLE001
                continue
            for t in tabs:
                raw = t.extract() or []
                cln = clean_table(raw, doc_vocab=dv)
                # 统计"被改动的单元格数"
                ch = sum(1 for r1, r2 in zip(raw, cln) for a, b in zip(r1, r2)
                         if str(a or "").strip() != b)
                tot_raw += sum(1 for r in raw for c in r if str(c or "").strip())
                tot_clean += sum(1 for r in cln for c in r if c.strip())
                if ch and shown < 6:
                    shown += 1
                    print(f"\n--- {os.path.basename(p)} p{i+1}  {t.row_count}x{t.col_count}"
                          f"  改动 {ch} 个单元格 ---")
                    for r1, r2 in list(zip(raw, cln))[:4]:
                        for a, b in zip(r1, r2):
                            a, b = str(a or "").strip(), b
                            if a != b and (a or b):
                                print(f"    前: {a[:70]!r}")
                                print(f"    后: {b[:70]!r}")
        doc.close()
    print(f"\n合计非空单元格  原始 {tot_raw} → 清洗后 {tot_clean}"
          f"（{'(无丢失)' if tot_clean >= tot_raw else '(有丢失!)'}）")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    _selftest(args)
