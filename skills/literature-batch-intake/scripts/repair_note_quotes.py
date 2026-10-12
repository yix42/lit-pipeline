#!/usr/bin/env python3
"""引语转录修复：把「只因非字母数字字符而不同」的笔记引语还原为档案原样。

**这不做「反向生成引语」。** 适用的前提极窄，三条同时满足才动手：
  1. 该引语在核验里是「未命中」；
  2. 把两侧都压成**只含字母数字**的串后，笔记串**能在档案里逐字找到**
     —— 也就是说差异**只在** ± − – ／ 空格 标点 这类字符上，**没有增删任何一个词**；
  3. 引语里**不含省略号**（`…` / `...`）——省略号引语是多段拼接，不能机械替换。

满足三条时，笔记里的 `1.56 0.47 mV` 会被还原成档案原样的 `1.56 ± 0.47 mV`。
**语义一字未改，只补回被吞掉的字形。**

典型成因：出版社 PDF 把 ± 排成 Symbol 字体，抽文本得到 C0 控制字符；
写笔记时那个字符被静默丢弃（实测一批 10 条）。

用法：
    python repair_note_quotes.py [--apply] [key ...]
不加 `--apply` 只报告不落盘。
"""
import os
import re
import sys
import unicodedata
import difflib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_note_quotes as V   # noqa: E402

VAULT = V.VAULT
NOTES = V.NOTES
FULLTEXT = V.FULLTEXT
LOG = os.path.join(VAULT, "90_Meta/State/_quote_repair_log.json")

PUNCT = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
         "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " "}


def light(s):
    """轻归一化：**保留空白**（要拿回可读的档案原文），只统一字形、去掉控制字符。"""
    s = re.sub(r"<!--.*?-->", " ", s)
    s = re.sub(r"\[p\d+\]\s*", "", s)   # 页眉页脚附录的行标（我们自己加的）
    s = unicodedata.normalize("NFKC", s)
    for a, b in PUNCT.items():
        s = s.replace(a, b)
    s = s.replace("\x01", "\u00b1").replace("\x02", "\u00b1")
    s = s.replace("\x03", "\u00b1")
    return "".join(ch for ch in s if ord(ch) >= 32 or ch in "\n\t")


def alnum_index(s):
    """返回 (纯字母数字串, 每个字符在 s 中的下标)。"""
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch.isalnum():
            out.append(ch)
            idx.append(i)
    return "".join(out), idx


def main():
    apply = "--apply" in sys.argv
    keys = [a for a in sys.argv[1:] if not a.startswith("--")]

    corpus = {}
    for f in os.listdir(FULLTEXT):
        if f.endswith(".md"):
            raw = open(os.path.join(FULLTEXT, f), encoding="utf-8").read()
            s = light(raw)
            a, idx = alnum_index(s)
            # 第 4 项是「去全部空白」的版本，用于判断某条引语**是否已经命中**；
            # 前 3 项保留空白，用于把命中区段还原成可读原文。
            corpus[f[:-3]] = (s, a, idx, V.normalize(raw))

    if not keys:
        keys = sorted({f.split("_")[0] for f in os.listdir(NOTES)
                       if re.match(r"^[A-Z0-9]{8}_", f)})

    log, repaired, manual = [], [], []
    for key in keys:
        nf = None
        for f in os.listdir(NOTES):
            if f.startswith(key + "_") and f.endswith(".md"):
                nf = f
        if not nf:
            continue
        p = os.path.join(NOTES, nf)
        note = open(p, encoding="utf-8").read()
        hits = 0
        for raw_q in V.extract_quotes(note):
            if V.strip_refs(raw_q):
                continue
            segs = [x.strip().strip('"') for x in re.split(r"…|\.\.\.", raw_q)]
            segs = [x for x in segs if len(re.findall(r"[a-zA-Z]", x)) >= 30]
            if not segs:
                continue
            # 该引语是否**已经命中**（去空白口径，与核验脚本一致）
            if any(V.normalize(x) in corpus[k][3] for x in segs for k in corpus):
                continue
            if "…" in raw_q or "..." in raw_q:
                manual.append((key, raw_q, "含省略号（多段拼接），不机械替换")); continue
            a = re.sub(r"[^0-9A-Za-z]", "", V.normalize(raw_q))
            found = None
            for k, (s, sa, idx, _) in corpus.items():
                j = sa.find(a)
                if j >= 0:
                    found = (k, s, idx, j); break
            if not found:
                manual.append((key, raw_q, "字母数字层也对不上 ⇒ 有实质差异，须人工")); continue
            k, s, idx, j = found
            sub = s[idx[j]:idx[j + len(a) - 1] + 1]
            sub = re.sub(r"\s+", " ", sub).strip()
            ratio = difflib.SequenceMatcher(None, V.normalize(raw_q), V.normalize(sub)).ratio()
            if ratio < 0.85:
                manual.append((key, raw_q, f"相似度仅 {ratio:.2f}，不自动改")); continue
            note = note.replace(raw_q, sub, 1)
            hits += 1
            log.append(dict(key=key, note=nf, before=raw_q, after=sub,
                            archive=k, ratio=round(ratio, 3)))
        if hits:
            repaired.append((key, hits))
            if apply:
                open(p, "w", encoding="utf-8").write(note)

    print("=== 可修复（差异仅在非字母数字字符）===")
    for k, n in repaired:
        print(f"  {k}: {n} 条")
    print(f"  合计 {sum(n for _, n in repaired)} 条" + ("（已落盘）" if apply else "（未落盘，加 --apply）"))
    print("\n=== 须人工处理 ===")
    for k, q, why in manual:
        print(f"  [{k}] {why}\n      {re.sub(chr(92)+'s+', ' ', q)[:150]}")
    if apply and log:
        import json
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n修复日志 →", LOG)


if __name__ == "__main__":
    main()
