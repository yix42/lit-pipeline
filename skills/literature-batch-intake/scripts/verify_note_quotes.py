#!/usr/bin/env python3
"""L2 笔记英文引语的**可核验性**检查（硬规则 1 的自动闸门）。

对每篇笔记，抽出所有英文引语，到 `40_Fulltext/md/<key>.md` 里逐条定位，分三层：

- **严格命中**：归一化（HTML 实体 / Unicode 标点 / NFKC / 去全部空白）后逐字命中。
- **宽松命中**：再去掉连字符后命中 → 差异仅在连字符（PDF 转出常见缺陷），可核验但需留意。
- **未命中**：真问题 —— 要么笔记删改了原文，要么档案转出严重残缺。

归一化为什么这么重：档案来自 XML / HTML / PDF 三种通道，同一句话的差异全在**排版层**——
    `&gt;` / `>` ｜ `’` / `'` ｜ `–` / `-` ｜ `ﬁ` / `fi` ｜ 软换行 / 硬换行 ｜ 双栏交错插入的对侧文字
把这些差异全部归一掉之后，剩下的差异才是**内容**差异。

用法：
    python verify_note_quotes.py                      # 检查全部 L2 笔记
    python verify_note_quotes.py 3RQGFGFQ 2QKPGBGZ    # 只检查指定 key
"""
import html
import os
import re
import sys
import unicodedata

VAULT = os.environ.get("RESEARCH_VAULT", os.path.expanduser("~/ResearchVault"))
NOTES = os.path.join(VAULT, "20_Notes")
FULLTEXT = os.path.join(VAULT, "40_Fulltext/md")

PUNCT_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2010": "-", "\u2011": "-",
    "\u00a0": " ", "\u2009": " ", "\u202f": " ", "\u2005": " ",
}

# 引语的字母占比下限（排除中文行夹带的英文片段）。**原为 0.5**——那会把数字密集的
# 真实引语整条跳过（6Q8TMP9F 发现 4 的均值±SD 句只有 0.43）⇒ 「没报错」被误当「已核验」。
LATIN_MIN = float(os.environ.get("VERIFY_LATIN_MIN", "0.35"))


def normalize(s: str, drop_hyphen: bool = False) -> str:
    s = re.sub(r"<!--.*?-->", " ", s)         # 分页标记 / 分节标记
    s = re.sub(r"\[p\d+\]\s*", "", s)          # 页眉页脚附录的行标（我们自己加的，不是原文）
    s = html.unescape(s)                       # &gt; &lt; &amp; &#x27;
    s = unicodedata.normalize("NFKC", s)       # ﬁ→fi, 全角→半角
    for a, b in PUNCT_MAP.items():
        s = s.replace(a, b)
    # 出版社 PDF 的 C0 控制字符（Elsevier 把 ± / − 排成 Symbol 字体，抽出来是 \x01/\x02/\x03）。
    # 新档案已在 reflow 阶段还原为 ± / -，但**旧档案与未重排的档案仍带控制字符**，
    # 这里一律视作噪声剔除，避免成批误报（实测一篇 22 条）。
    s = "".join(ch for ch in s if ord(ch) >= 32 or ch in "\n\t")
    s = re.sub(r"\*\*|\*", "", s)              # markdown 强调
    s = re.sub(r"\s+", "", s)                  # 全部空白
    if drop_hyphen:
        s = s.replace("-", "")
    return s


def extract_quotes(note_text: str):
    """抓引用块 / 表格单元格里的英文引语。

    `LATIN_MIN` 是引语的**字母占比下限**，用来排除中文行里夹带的英文片段。
    ⚠️ 原设 0.5，**会把数字密集的真实引语整条跳过**（实测 6Q8TMP9F 发现 4 的
    `revealed more endomysial fibrosis in the RAA (RAA 1⁄4 7.07 ± 1.55 mm …)`
    字母占比仅 0.43 ⇒ 该引语从未被核验过）。已下调到 0.35，并在末尾报告被跳过的条数，
    避免「没报错」被误当成「已核验」。
    """
    quotes = []
    for ln in note_text.split("\n"):
        s = ln.strip()
        if not (s.startswith(">") or (s.startswith("|") and '"' in s)):
            continue
        for q in re.findall(r'"([^"]{25,})"', s):
            q = q.strip()
            if CJK_RE.search(q):            # 含中文 ⇒ 不是英文引语（中文行/表格行里夹带的英文不算）
                SKIPPED.append((q, "CJK"))
                continue
            latin = len(re.findall(r"[a-zA-Z]", q)) / max(len(q), 1)
            if latin > LATIN_MIN:
                quotes.append(q)
            else:
                SKIPPED.append((q, round(latin, 2)))
    return quotes


CJK_RE = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")


# 被字母占比门槛跳过的候选（多为中文行夹带的英文片段，用于事后复核而不是静默丢弃）
SKIPPED = []


def strip_refs(q: str) -> bool:
    """排除参考文献条目与短片段（不是论文原句，不适用引语纪律）。"""
    if re.match(r"^[A-Z][a-z]+ [A-Z]{1,3}(,| )", q):        # Masuda M, Asai M, ...
        return True
    if len(re.findall(r"[a-zA-Z]", q)) < 30:
        return True
    return False


def load_corpus(exclude=None):
    """加载全部全文档案（含引语常发生在跨篇对读表里——A 篇笔记引 B 篇原文是合法的）。

    返回 {key: (strict, loose)}。惰性、带缓存。
    """
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = {}
        for f in sorted(os.listdir(FULLTEXT)):
            if not f.endswith(".md"):
                continue
            k = f[:-3]
            if exclude and k == exclude:
                continue
            raw = open(os.path.join(FULLTEXT, f), encoding="utf-8").read()
            _CORPUS[k] = (normalize(raw), normalize(raw, drop_hyphen=True))
    return _CORPUS


_CORPUS = None


def locate(seg, own_key):
    """在全部档案里定位一条引语；返回 (层级, 命中档案 key)。层级：strict / loose / miss。"""
    a, b = normalize(seg), normalize(seg, drop_hyphen=True)
    own = load_corpus().get(own_key) if own_key in load_corpus() else None
    if own:
        if a in own[0]:
            return "strict", own_key
        if b in own[1]:
            return "loose", own_key
    for k, (s, l) in load_corpus(exclude=own_key).items():
        if a in s:
            return "strict", k
        if b in l:
            return "loose", k
    return "miss", None


def check_key(key: str, verbose: bool = True):
    note_path = os.path.join(NOTES, _note_file(key))
    src_path = os.path.join(FULLTEXT, key + ".md")
    if not os.path.exists(note_path):
        print(f"[MISS-NOTE] {key} → {note_path}")
        return None
    if not os.path.exists(src_path):
        print(f"[MISS-FULLTEXT] {key} → {src_path}")
        return None
    quotes = [q for q in extract_quotes(open(note_path, encoding="utf-8").read()) if not strip_refs(q)]
    strict = loose = cross = miss = 0
    misses = []
    for q in quotes:
        for seg in re.split(r"…|\.\.\.", q):
            seg = seg.strip().strip('"')
            if len(re.findall(r"[a-zA-Z]", seg)) < 30:
                continue
            level, where = locate(seg, key)
            if level == "strict":
                strict += 1
                if where != key:
                    cross += 1
            elif level == "loose":
                loose += 1
            else:
                miss += 1
                misses.append(seg)
    total = strict + loose + miss
    print(f"{key}: 引语 {total} 条 → 严格 {strict}（其中跨篇 {cross}）· 仅连字符差异 {loose} · 未命中 {miss}")
    if verbose:
        for m in misses:
            print("     ✗", re.sub(r"\s+", " ", m)[:120])
    return dict(key=key, total=total, strict=strict, loose=loose, cross=cross, miss=miss, misses=misses)


def _note_file(key):
    for f in os.listdir(NOTES):
        if f.startswith(key + "_") and f.endswith(".md"):
            return f
    return key + ".md"


def _norm_spaced(s: str) -> str:
    """归一化**但保留空白** —— 供人眼阅读与 difflib 对齐（normalize() 会把空白全删）。"""
    s = re.sub(r"<!--.*?-->", " ", s)
    s = re.sub(r"\[p\d+\]\s*", " ", s)
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    for a, b in PUNCT_MAP.items():
        s = s.replace(a, b)
    s = "".join(ch for ch in s if ord(ch) >= 32 or ch in "\n\t")
    s = re.sub(r"\*\*|\*", "", s)
    return re.sub(r"\s+", " ", s)


def diagnose(key: str):
    """对未命中引语做「最佳对齐 + 逐点差异归因」——把未命中机械地分成三类。

    输出三类差异，直接对应纪律里要求的三分类：
      ＋档案侧插入（表格数值 / 图注 / 栏中另一栏文字夹进句子）⇒ 版式固有，笔记无需改
      ±替换 / －笔记多出 ⇒ 笔记侧改写或删字 ⇒ 必须改笔记
    只读，不改任何文件。
    """
    import difflib
    src = os.path.join(FULLTEXT, key + ".md")
    if not os.path.exists(src):
        print(f"[MISS-FULLTEXT] {key}")
        return
    A = _norm_spaced(open(src, encoding="utf-8").read())
    note = open(os.path.join(NOTES, _note_file(key)), encoding="utf-8").read()
    quotes = [q for q in extract_quotes(note) if not strip_refs(q)]
    n_diag = 0
    for q in quotes:
        for seg in re.split(r"…|\.\.\.", q):
            seg = seg.strip().strip('"')
            if len(re.findall(r"[a-zA-Z]", seg)) < 30:
                continue
            level, _ = locate(seg, key)
            if level != "miss":
                continue
            n_diag += 1
            n = _norm_spaced(seg).strip()
            sm = difflib.SequenceMatcher(None, n, A, autojunk=False)
            blk = sm.find_longest_match(0, len(n), 0, len(A))
            print("─" * 78)
            print(f"[{n_diag}] 笔记引语：{n}")
            if blk.size < 25:
                print(f"    ⚠ 最长连续锚点仅 {blk.size} 字符 → 口径差异过大，疑似**笔记侧改写**")
                continue
            pad = 160
            lo, hi = max(0, blk.b - pad), min(len(A), blk.b + blk.size + pad)
            W = A[lo:hi]
            b0 = blk.b - lo
            print(f"    档案窗口（【】＝最长连续锚点）："
                  f"{'…' if lo else ''}{W[:b0]}【{W[b0:b0+blk.size]}】{W[b0+blk.size:]}"
                  f"{'…' if hi < len(A) else ''}")
            sm2 = difflib.SequenceMatcher(None, n, W, autojunk=False)
            ops = sm2.get_opcodes()
            # 只保留夹在「首个有效 equal」与「末个有效 equal」之间的差异点（去掉窗口两侧的天然 padding）
            eqs = [i for i, (t, i1, i2, j1, j2) in enumerate(ops) if t == "equal" and (i2 - i1) >= 3]
            if not eqs:
                print("    ⚠ 窗口内无有效锚点")
                continue
            body = ops[eqs[0]:eqs[-1] + 1]
            ins = del_ = rep = 0
            for tag, i1, i2, j1, j2 in body:
                if tag == "insert":
                    ins += j2 - j1
                    print(f"    ＋档案侧插入（{j2-j1}字符）：{W[j1:j2]}")
                elif tag == "delete":
                    del_ += i2 - i1
                    print(f"    －笔记多出（{i2-i1}字符）：{n[i1:i2]}")
                elif tag == "replace":
                    rep += 1
                    print(f"    ±替换：笔记「{n[i1:i2]}」 → 档案「{W[j1:j2]}」")
            cover = blk.size / len(n)
            if del_ == 0 and rep == 0:
                verdict = "档案侧版式（笔记原文无误，无需改）"
            elif ins == 0:
                verdict = "笔记侧改写（必须改笔记）"
            else:
                verdict = "混合：档案侧插入 + 笔记侧差异"
            print(f"    → 覆盖 {cover:.0%}｜插入 {ins} 删字 {del_} 替换 {rep} ⇒ **{verdict}**")


if __name__ == "__main__":
    keys = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--diagnose" in sys.argv:
        for k in keys:
            diagnose(k)
        sys.exit(0)
    if not keys:
        keys = sorted({f.split("_")[0] for f in os.listdir(NOTES)
                       if f.endswith(".md") and re.match(r"^[A-Z0-9]{8}_", f)})
    tot = dict(total=0, strict=0, loose=0, miss=0)
    bad = []
    for k in keys:
        r = check_key(k, verbose=("-q" not in sys.argv))
        if r:
            for f in tot:
                tot[f] += r[f]
            if r["miss"]:
                bad.append(k)
    print(f"\n合计：引语 {tot['total']} · 严格 {tot['strict']} · 仅连字符 {tot['loose']} · 未命中 {tot['miss']}")
    if SKIPPED:
        print(f"另有 {len(SKIPPED)} 条候选未纳入核验（含中文 ⇒ 非英文引语；或字母占比 ≤ {LATIN_MIN}）：")
        for q, r in SKIPPED[:8]:
            print(f"    · ({r}) {re.sub(chr(92)+'s+', ' ', q)[:96]}")
    if bad:
        print("有未命中的 key：" + ", ".join(bad))
