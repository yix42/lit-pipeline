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
    python verify_note_quotes.py --diagnose <KEY>     # 对未命中逐点归因（只读）

机器可读模式（2026-10-07 新增，供 Folio 文献工作台 server/vault.js 调用；
判定引擎与上面完全同一套，只是换个出口）：
    python verify_note_quotes.py --json                  # 全库/指定 key → JSON
    python verify_note_quotes.py <KEY> --json            # 单篇 → JSON
    python verify_note_quotes.py --quotes-file F --json  # 任意引语列表（Folio 卡片）
    python verify_note_quotes.py --quotes-file F --corpus-dir D --json
                                                         # 以 D 为语料（Folio 自己的正文）
    python verify_note_quotes.py --coverage-file F --json
                                                         # 覆盖度：笔记应有引语 vs 已进 Folio
    python verify_note_quotes.py --report-dir D          # 核验并落一份可归档报告到 D
    python verify_note_quotes.py --json --report-dir D   # 同时出 JSON 与报告

所有 JSON 模式都 exit 0，失败写进 ok/error 字段（非零退出会被调用方读成「脚本崩了」）。
**写盘**只有一个入口：显式传 --report-dir 时写 `D/引语闸门_<日期>.md`；其余一律只读。
"""
import contextlib
import html
import io
import json
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


# 一个「待核验片段」的最小字母数。check_key / diagnose / 覆盖度 / Folio 卡片
# 四条路径共用此常量，避免各处写死 30 后悄悄漂移。
SEG_MIN_LETTERS = 30


def _iter_segments(note_text: str):
    """笔记正文 → 待核验的引语片段（**唯一实现**，check_key 与覆盖度都用它）。

    口径：先按 extract_quotes 抓引语块（含中英文混杂行会被它按字母占比挡掉），
    丢掉参考文献式片段，再按省略号切开——一段引语里的两个独立原句是两条，
    不切开会让「其中一句是编的」被另一句的命中掩盖掉。
    """
    for q in extract_quotes(note_text):
        if strip_refs(q):
            continue
        for seg in re.split(r"…|\.\.\.", q):
            seg = seg.strip().strip('"')
            if len(re.findall(r"[a-zA-Z]", seg)) < SEG_MIN_LETTERS:
                continue
            yield seg


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
    strict = loose = cross = miss = 0
    misses = []
    for seg in _iter_segments(open(note_path, encoding="utf-8").read()):
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


# =====================================================================
# 机器可读层（2026-10-07 新增；供 Folio 文献工作台 server/vault.js 调用）
#
#   归一化与判定引擎（normalize / extract_quotes / locate / strip_refs）
#   **一字未改**。本层只做两件事：解析参数、把已有判定结果序列化成 JSON。
#
#   --json                      全库 / 指定 key 的引语核验
#   --quotes-file <f> --json    任意引语列表的判定（Folio 卡片复用同一引擎）
#   --corpus-dir <d>            配 --quotes-file：以该目录为语料；不给则用 40_Fulltext
#   --coverage-file <f> --json  覆盖度：笔记应有引语 vs 已进 Folio 的引语
#
#   约定：所有 JSON 模式都 **exit 0** 并把失败写进 ok/error 字段——
#   非零退出会被调用方读成「脚本崩了」，而「某篇没有全文档案」是正常结论，不是崩溃。
#   人的可读输出（check_key 的 print）在 JSON 模式下被重定向丢弃，不进 stdout。
# =====================================================================

# 覆盖度：过短的 have 片段不参与「反向包含」判定，否则 note 里的短标题会命中一切
COVER_MIN_CHARS = 30


def _load_corpus_dir(d):
    """把目录里的 .md 读成语料，键＝文件名（不含扩展名）——与 vault 的 40_Fulltext 同构。"""
    cor = {}
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md"):
            continue
        raw = open(os.path.join(d, f), encoding="utf-8").read()
        cor[f[:-3]] = (normalize(raw), normalize(raw, drop_hyphen=True))
    return cor


def _locate_in(cor, seg):
    """在给定语料里定位（与 locate 同口径，但语料可换）。"""
    a, b = normalize(seg), normalize(seg, drop_hyphen=True)
    for k, (s, l) in cor.items():
        if a in s:
            return "strict", k
        if b in l:
            return "loose", k
    return "miss", None


def _json_review(keys=None):
    """全库 / 指定 key 核验 → JSON。

    「没有全文档案」与「引语未命中」是两回事，必须分开报：
    前者进 errors（这篇根本没被核验过），后者进 results.miss（核验了、没对上）。
    旧版只在文本里打一行 [MISS-FULLTEXT]，机器侧读不到 ⇒ 会被当成「0 未命中＝通过」。
    """
    if not keys:
        keys = sorted({f.split("_")[0] for f in os.listdir(NOTES)
                       if f.endswith(".md") and re.match(r"^[A-Z0-9]{8}_", f)})
    results, errors = [], []
    for k in keys:
        note_path = os.path.join(NOTES, _note_file(k))
        src_path = os.path.join(FULLTEXT, k + ".md")
        if not os.path.exists(note_path):
            errors.append({"key": k, "error": "no-note", "path": note_path})
            continue
        if not os.path.exists(src_path):
            errors.append({"key": k, "error": "no-fulltext", "path": src_path})
            continue
        r = check_key(k, verbose=False)
        if r:
            results.append(r)
    tot = {f: sum(x[f] for x in results) for f in ("total", "strict", "loose", "miss")}
    return {
        "ok": True,
        "vault": VAULT,
        "keys": len(results),           # 真正核验过的篇数
        "requested": len(keys),         # 请求的篇数
        "latin_min": LATIN_MIN,
        "totals": tot,
        "results": results,
        "bad": [x["key"] for x in results if x["miss"]],
        "errors": errors,               # 未被核验的（缺笔记 / 缺全文档案）
        "readErrors": errors,
        "skipped": {
            "count": len(SKIPPED),
            "note": "含中文或字母占比 ≤ latin_min 的候选 —— 0 未命中 ≠ 全部已核验",
            "sample": [{"quote": q[:120], "reason": str(r2)} for q, r2 in SKIPPED[:20]],
        },
    }


def _judge_quotes(items, corpus_dir=None):
    """任意引语列表的判定 → JSON（Folio 卡片走这条路）。

    items: [{id, quote, ...}]；id 会原样回传（调用方靠它对齐回卡片）。
    返回 items[].segments = [{seg, level, where}]，与笔记侧同一套阶段口径。
    一条引语里某个片段判不了（含中文 / 字母太少）⇒ 该片段不进 segments 也不计入
    totals（记为 skipped），**不会**被静默算成「命中」。
    """
    if not isinstance(items, list):
        items = []
    items = [x for x in items if isinstance(x, dict) and str(x.get("quote") or "").strip()]

    cor = None
    if corpus_dir:
        if not os.path.isdir(corpus_dir):
            return {"ok": False, "error": "corpus-dir-not-found", "corpusDir": corpus_dir}
        cor = _load_corpus_dir(corpus_dir)
        if not cor:
            return {"ok": False, "error": "empty-corpus-dir", "corpusDir": corpus_dir}

    out_items, skipped = [], []
    n_strict = n_loose = n_miss = 0
    for it in items:
        iid = it.get("id")
        q = str(it.get("quote") or "")
        segs = []
        for seg in re.split(r"…|\.\.\.", q):
            seg = seg.strip().strip('"')
            if not seg:
                continue
            if CJK_RE.search(seg):
                skipped.append({"id": iid, "quote": seg[:120], "reason": "CJK"})
                continue
            if len(re.findall(r"[a-zA-Z]", seg)) < SEG_MIN_LETTERS:
                skipped.append({"id": iid, "quote": seg[:120], "reason": "latin<%d" % SEG_MIN_LETTERS})
                continue
            level, where = locate(seg, None) if cor is None else _locate_in(cor, seg)
            if level == "strict":
                n_strict += 1
            elif level == "loose":
                n_loose += 1
            else:
                n_miss += 1
            segs.append({"seg": seg, "level": level, "where": where})
        if not segs:
            # 一条都判不了 ⇒ 不进 items（调用方会把缺席读成「未判定」，
            # 而给个空 segments 会被它的兜底逻辑读成「严格命中」——那就成了假绿灯）
            continue
        out_items.append({
            "id": iid,
            "quote": q,
            "level": ("miss" if any(s["level"] == "miss" for s in segs)
                      else "loose" if any(s["level"] == "loose" for s in segs) else "strict"),
            "segments": segs,
            "totals": {lv: sum(1 for s in segs if s["level"] == lv) for lv in ("strict", "loose", "miss")},
        })
    return {
        "ok": True,
        "quotes": len(items),
        "judged": len(out_items),
        "corpus": "vault-40_Fulltext" if cor is None else "corpus-dir",
        "totals": {"total": n_strict + n_loose + n_miss,
                   "strict": n_strict, "loose": n_loose, "miss": n_miss},
        "items": out_items,
        "skipped": {"count": len(skipped), "items": skipped[:50]},
    }


def _coverage(key, have):
    """覆盖度：笔记里**应有**的引语，有多少已进入 Folio（＝已被核实过）。

    判定口径与闸门一致：笔记按 _iter_segments 切片段；have（Folio 的 quote / note，
    note 里含截断的「其余引语」）归一化后取整块 + 逐行，双向包含即算覆盖
    （引语在 note 里被截断时靠「have 片段 ⊆ 笔记片段」这一向命中）。

    只读，不写任何文件。
    """
    key = str(key or "").strip().upper()
    note_name = _note_file(key)
    note_path = os.path.join(NOTES, note_name)
    if not os.path.exists(note_path):
        return {"ok": False, "error": "note-not-found", "key": key, "notePath": note_path}

    segs = list(_iter_segments(open(note_path, encoding="utf-8").read()))

    chunks = []
    for h in (have or []):
        t = str(h)
        n = normalize(t)
        if n:
            chunks.append(n)
        for ln in t.split("\n"):
            n2 = normalize(ln)
            if n2 and n2 != n:
                chunks.append(n2)

    missing, covered = [], 0
    for seg in segs:
        n = normalize(seg)
        hit = False
        for c in chunks:
            if n and n in c:
                hit = True
                break
            if len(c) >= COVER_MIN_CHARS and c in n:
                hit = True
                break
        if hit:
            covered += 1
        else:
            missing.append(seg)

    return {
        "ok": True,
        "key": key,
        "noteFile": note_name,
        "noteTotal": len(segs),          # 笔记里应有的引语数
        "covered": covered,              # 已进 Folio 的
        "missingCount": len(missing),
        "missing": missing,
        "haveChunks": len(chunks),
        "coverMinChars": COVER_MIN_CHARS,
    }


def _json_dump(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.write("\n")


def _write_report(report_dir, data):
    """把核验结果落成一份可归档的 Markdown 报告（唯一会写盘的地方）。

    为什么要有：此前「10/10 严格命中」是人手抄进 _Index.md 的，
    抄错/漏抄没人发现；而且「没报错」与「已核验」在文本输出里长得一样。
    报告里把三态分开写死：命中 / 未命中 / **未被核验**（缺档案），
    最后一项单独成节，标题就写「不算通过」。
    """
    import datetime
    os.makedirs(report_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    path = os.path.join(report_dir, "引语闸门_%s.md" % today)

    t = data["totals"]
    errs = data.get("errors") or []
    skipped = (data.get("skipped") or {}).get("count", 0)
    by_miss = sorted((x for x in data["results"] if x["miss"]), key=lambda x: -x["miss"])

    L = []
    L.append("# 引语闸门报告 · %s" % today)
    L.append("")
    L.append("- 生成时间：%s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    L.append("- vault：`%s`" % data.get("vault"))
    L.append("- 核验范围：%d 篇（请求 %d 篇）" % (data["keys"], data.get("requested", data["keys"])))
    L.append("- 判定引擎：`90_Meta/State/verify_note_quotes.py`（归一化口径的唯一真源）")
    L.append("")
    L.append("## 合计")
    L.append("")
    L.append("| 指标 | 数 |")
    L.append("|---|---|")
    L.append("| 引语总数 | %d |" % t["total"])
    L.append("| 严格命中 | %d |" % t["strict"])
    L.append("| 仅连字符差异 | %d |" % t["loose"])
    L.append("| **未命中** | **%d** |" % t["miss"])
    L.append("| 有未命中的篇目 | %d |" % len(by_miss))
    L.append("| **未被核验（缺笔记/缺全文档案）** | **%d** |" % len(errs))
    L.append("| 跳过候选（含中文或字母占比 ≤ %.2f） | %d |" % (data.get("latin_min", 0.35), skipped))
    L.append("")
    L.append("> ⚠️ 「0 未命中」≠「全部已核验」。跳过的候选与未被核验的篇目都不在"
             "「严格命中」里，但它们也**没有被证明是错的**——只是没被查过。")
    L.append("")

    if by_miss:
        L.append("## 未命中明细（按未命中数降序）")
        L.append("")
        for x in by_miss:
            L.append("### %s — %d/%d 未命中" % (x["key"], x["miss"], x["total"]))
            L.append("")
            for m in x["misses"]:
                L.append("- ✗ %s" % re.sub(r"\s+", " ", m)[:300])
            L.append("")
    else:
        L.append("## 未命中明细")
        L.append("")
        L.append("无。")
        L.append("")

    L.append("## 未被核验的篇目（**不算通过**）")
    L.append("")
    if errs:
        L.append("| key | 原因 | 路径 |")
        L.append("|---|---|---|")
        for e in errs:
            why = "缺全文档案" if e.get("error") == "no-fulltext" else \
                  "缺笔记" if e.get("error") == "no-note" else str(e.get("error"))
            L.append("| %s | %s | `%s` |" % (e.get("key"), why, e.get("path")))
    else:
        L.append("无——所有篇目的笔记与全文档案都在，全部进入了核验。")
    L.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


if __name__ == "__main__":
    argv = sys.argv[1:]

    def _optval(flag):
        """取 --flag 后面那个值。"""
        if flag in argv:
            i = argv.index(flag)
            if i + 1 < len(argv):
                return argv[i + 1]
        return None

    keys = [a for a in argv if not a.startswith("-")]
    for _f in ("--quotes-file", "--corpus-dir", "--coverage-file", "--report-dir"):
        _v = _optval(_f)
        if _v is not None and _v in keys:
            keys.remove(_v)

    # ---- 覆盖度模式 ----
    if "--coverage-file" in argv:
        try:
            req = json.load(open(_optval("--coverage-file"), encoding="utf-8"))
            with contextlib.redirect_stdout(io.StringIO()):
                out = _coverage(req.get("key"), req.get("have"))
        except Exception as e:
            out = {"ok": False, "error": "bad-input", "message": "%s: %s" % (type(e).__name__, e)}
        _json_dump(out)
        sys.exit(0)

    # ---- 任意引语列表模式（Folio 卡片） ----
    if "--quotes-file" in argv:
        try:
            items = json.load(open(_optval("--quotes-file"), encoding="utf-8"))
            with contextlib.redirect_stdout(io.StringIO()):
                out = _judge_quotes(items, _optval("--corpus-dir"))
        except Exception as e:
            out = {"ok": False, "error": "bad-input", "message": "%s: %s" % (type(e).__name__, e)}
        _json_dump(out)
        sys.exit(0)

    # ---- 全库 / 指定 key 的 JSON 模式（--report-dir 可与之并用，也可单用）----
    report_dir = _optval("--report-dir")
    if "--json" in argv or report_dir:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                out = _json_review(keys)
        except Exception as e:
            out = {"ok": False, "error": "internal", "message": "%s: %s" % (type(e).__name__, e)}
        if report_dir and out.get("ok"):
            try:
                out["report"] = _write_report(report_dir, out)
            except Exception as e:
                out["reportError"] = "%s: %s" % (type(e).__name__, e)
        if "--json" in argv:
            _json_dump(out)
        else:
            t = out.get("totals") or {}
            print("核验 %s 篇：引语 %s · 严格 %s · 仅连字符 %s · 未命中 %s · 未被核验 %s"
                  % (out.get("keys"), t.get("total"), t.get("strict"), t.get("loose"),
                     t.get("miss"), len(out.get("errors") or [])))
            if out.get("report"):
                print("报告：%s" % out["report"])
            if out.get("reportError"):
                print("报告写入失败：%s" % out["reportError"])
        sys.exit(0)

    # ---- 以下为原有文本模式，行为不变 ----
    if "--diagnose" in argv:
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
