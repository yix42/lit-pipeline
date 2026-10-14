#!/usr/bin/env python3
"""引语转录修复：把「只因字形写法不同」的笔记引语还原为档案原样。

**这不做「反向生成引语」。** 准入条件（2026-10-07 全库实测后大幅收窄）：

原本的准入是「去掉非字母数字后能在档案里找到」——太宽，实测会做出**错的修复**。
现在只放行两类，其余一律交人工（见 `unsafe_change_reason`）：

  ① **引号字形还原**：两侧只差引号（`'flags'` → `"flags"`、句尾 `'` → `"`）；
  ② **补回真 ±**：不删任何非空白字符，新增的非空白字符只有 `±`，
     且每个 ± 都落在 `数 ± 数` 语境（如 `2,439 ± 1,452`）。

**为什么收得这么紧**（都是 2026-10-07 逐条看全库 156 条未命中后实测出来的）：

| 档案侧的现象 | 真相 | 照它改的后果 |
|---|---|---|
| `±5 seconds` / `P ± .05` / `(r ± 0.85)` / `Taiwan, ±Second Dept` | 一个 U+00B1 兼作 **≈ / < / 脚注 †** | 把笔记里正确的 `~` `=` `<` 改成 `±` |
| `per\u00adformed` / `nonvalvu\u00adlar` | 软连字符 **U+00AD**（行末断词残留） | 往干净笔记里插不可见字符 |
| `_h_` / `_observation_` | markdown 斜体记号 | 给引语塞排版标记 |
| 档案缺句末的 `.` `)` `'` | 档案切片/转出残缺 | 把笔记里正确的标点删掉 |

**判据一句话**：档案比笔记更脏的地方，不修；只有「笔记漏抄了档案确实有的字形」才修。
留下一条已知未命中，比把对的改成错的便宜得多。

典型成因（仍然成立的那一类）：出版社 PDF 把 ± 排成 Symbol 字体，
抽文本时字形丢失，写笔记时那个字符被静默丢弃。

用法：
    python repair_note_quotes.py [key ...]                  # 诊断（人读）
    python repair_note_quotes.py --json [key ...]           # 诊断（机器读，带稳定 id）
    python repair_note_quotes.py --apply-ids ids.json       # 只落笔点名的那几条
    python repair_note_quotes.py --apply [key ...]          # 批量落笔全部可修的（少用）

**落笔纪律**：「诊断 → 逐条确认 → 才落笔」。
默认只诊断；要改文件必须显式给 `--apply-ids`（点名 id）或 `--apply`（批量）。
每次落笔前把被改的笔记**整份快照到库外** `~/ResearchVault_backups/<日期>_quote_repair/`
（备份目录不许放库内——Obsidian 里会变成重复笔记、还会同步上云）。

`--json` 的 id 是 `sha1(key + "|" + 原文引语)[:12]`，稳定可复现；
调用方拿它做「逐条确认」，不要按序号确认（序号会随笔记改动漂移）。
落笔时会**重新诊断一遍**再改 —— 调用方传来的旧内容一律作废。
"""
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_note_quotes as V   # noqa: E402

VAULT = V.VAULT
NOTES = V.NOTES
FULLTEXT = V.FULLTEXT
LOG = os.path.join(VAULT, "90_Meta/State/_quote_repair_log.json")

# 备份必须落在库外（库内出现备份目录是校验器会报 WARN 的错）
BACKUP_ROOT = os.path.join(os.path.dirname(os.path.abspath(VAULT.rstrip("/"))), "ResearchVault_backups")

PUNCT = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
         "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " "}

MIN_LETTERS = 30      # 与闸门 verify_note_quotes 的 SEG_MIN_LETTERS 一致
MIN_RATIO = 0.85      # 相似度低于此值不自动改

# ⚠️ 档案侧的「符号」不可信。实测 40_Fulltext/md/23FSRVL5.md 里的 U+00B1 同时代表：
#     真 ± （52±10 years / 8.1±2.5 Hz / 100±15 ms）
#     <    （P ± .05 / r ± 0.85 —— 相关系数不可能带 ±）
#     ≈    （±5 seconds / ±2 minutes）
#     脚注 †/‡（Taiwan, ±Second Department / Satoshi Higa, MD,±）
# 成因见该档案 frontmatter：「C0 控制字符字形还原（\x01/\x02→±，\x03 位置相关）」。
# ⇒ 凡是「照档案把笔记里的字符改成符号」或「把笔记里的符号删掉」的修复，一律不自动做：
#   把对的改成错的，比留一条已知未命中更糟。
SYMBOLIC = set("±≤≥≈∼~=<>×÷∓∝∞†‡")
# 档案侧还带 markdown 斜体记号（Europe PMC 的 <italic> 被转成 `_h_` / `_observation_`）。
# 那是**给笔记塞标记**，不是补回被吞掉的字形 —— 引语里出现 `_` 只会让下一个人再删一次。
MARKUP = set("_*`")
# ⚠️ 软连字符 U+00AD：档案里 `per formed` 其实是 `per\u00adformed`（行末断词残留）。
# `normalize` 不剥它，所以它会表现为「未命中」；但把它插进笔记只是把断词缺陷搬过去。
SOFT_HYPHEN = "\u00ad"
# 「会被删掉」的还有连字符：档案把 `long-term` 转成 `longterm`、把
# `Fibrillation` 转成 `Fibril- lation`（行末断词残留）两种方向都有。
# 笔记侧的连字符是**对的**，不允许被档案带跑。
NO_DELETE = SYMBOLIC | MARKUP | set("-–—−") | {SOFT_HYPHEN}
# 引号字形（弯/直、单/双）是唯一「有确凿证据属于字形还原」的类别。
QUOTE_CHARS = set("'\"‘’“”")


def _diff_chars(before, after):
    """按位置比对，返回 (新引入的 [(下标, 字符)], 被改掉的字符)。"""
    added, removed = [], []
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            added.extend((j, after[j]) for j in range(j1, j2))
        if tag in ("delete", "replace"):
            removed.extend(before[i] for i in range(i1, i2))
    return added, removed


_PM_RE = re.compile(r"\d\s*±\s*[\d(]")


def unsafe_change_reason(before, after):
    """整个候选改动是否安全。安全才返回 None，否则返回人读原因。

    ★ 允许自动改的只剩两类（其余一律交人工）：
      ① **引号字形还原**：两侧只差引号（`'flags'` → `"flags"`、`'` → `"`）；
      ② **补回真 ±**：不删任何非空白字符，新增的非空白字符全是 `±`，
         且每个 ± 都落在 `数 ± 数` 语境。
    为什么收得这么紧（2026-10-07 全库实测，逐条看过 37 个候选后定的）：
      · 档案侧 `±` 兼作 < / ≈ / 脚注 †（见上），照它改会把对的改成错的；
      · 档案侧带软连字符 `per\\u00adformed`、markdown 斜体 `_h_`，照它改是**引入缺陷**；
      · 「删掉笔记侧的字」永远是降级 —— 档案缺、笔记有，说明档案才是残的那个。
    """
    added, removed = _diff_chars(before, after)
    a_ns = [c for _, c in added if not c.isspace()]
    r_ns = [c for c in removed if not c.isspace()]

    if not a_ns and not r_ns:
        return None                                  # 纯空白差异（按设计不该走到这里）

    # ① 引号字形还原
    if a_ns and r_ns and set(a_ns) <= QUOTE_CHARS and set(r_ns) <= QUOTE_CHARS:
        return None

    # ② 补回真 ±
    if not r_ns and a_ns and set(a_ns) == {"±"}:
        spans = [(m.start(), m.end()) for m in _PM_RE.finditer(after)]
        if all(any(a <= p < b for a, b in spans) for p, c in added if not c.isspace()):
            return None

    # —— 以下是拒绝理由（按「最该让人看见的原因」排序）——
    if SOFT_HYPHEN in a_ns:
        return "档案侧是软连字符 U+00AD（行末断词残留，如 per\\u00adformed），照它改是引入缺陷"
    if any(c in MARKUP for c in a_ns):
        return "照档案新引入 markdown 记号「%s」——那是排版标记，不是被吞掉的字形" % \
               next(c for c in a_ns if c in MARKUP)
    if r_ns:
        return "会删掉笔记里的「%s」——档案缺而笔记有，说明残缺的是档案" % "".join(sorted(set(r_ns)))
    if any(c in SYMBOLIC for c in a_ns):
        return "照档案新引入符号「%s」——档案侧符号可能是被污染的归属（± 代 < / ≈ / †）" % \
               next(c for c in a_ns if c in SYMBOLIC)
    return "新增「%s」不属于可自动还原的字形类别（只放行引号与真 ±）" % "".join(sorted(set(a_ns)))


def _nonspace(s):
    return "".join(ch for ch in s if not ch.isspace())


def _patch(before, after):
    """**最小替换**：只把「非空白字形」的差异改成档案的写法，其余保留笔记原样。

    为什么不能整条替换（原实现的做法）：
      档案侧除了被吞掉的字形，还带一堆**版本更差**的版式缺陷 ——
      `was per formed`（软连字符变空格）、`Fibril- lation`（行末断词残留）。
      整条替换会把它们一起搬进本来干净的笔记。
    判据：`normalize` **忽略空白**，所以纯空白差异不可能是「未命中」的原因；
      这类差异一律保留笔记的写法。只有「去掉空白后两边不同」的差异才值得改。

    返回 (新串, 实质差异列表)。实质差异非空 ⇒ 该条本来就不该自动修。
    """
    out, skipped = [], []
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(before[i1:i2])
            continue
        b, a = before[i1:i2], after[j1:j2]
        if re.sub(r"[^0-9A-Za-z]", "", b) != re.sub(r"[^0-9A-Za-z]", "", a):
            skipped.append((b, a))          # 有增删词 ⇒ 不是字形差异
            out.append(b)
            continue
        if _nonspace(a) == _nonspace(b):
            out.append(b)                    # 纯空白差异 ⇒ 保留笔记（档案的空白更脏）
            continue
        out.append(a)
    return "".join(out), skipped


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


def make_id(key, before):
    """稳定 id：由 key + 原文引语决定，与顺序无关。"""
    return hashlib.sha1((key + "|" + before).encode("utf-8")).hexdigest()[:12]


def build_corpus():
    """全部档案：(保留空白的正文, 纯字母数字串, 其下标, 严格归一化正文, 去连字符归一化正文)。"""
    corpus = {}
    for f in os.listdir(FULLTEXT):
        if not f.endswith(".md"):
            continue
        raw = open(os.path.join(FULLTEXT, f), encoding="utf-8").read()
        s = light(raw)
        a, idx = alnum_index(s)
        # 第 4/5 项是「去全部空白」（严格 / 再去连字符）的版本，用于判断某条引语是否**已经命中**；
        # 前 3 项保留空白，用于把命中区段还原成可读原文。
        corpus[f[:-3]] = (s, a, idx, V.normalize(raw), V.normalize(raw, drop_hyphen=True))
    return corpus


def _note_file(key):
    for f in os.listdir(NOTES):
        if f.startswith(key + "_") and f.endswith(".md"):
            return f
    return None


def _all_keys():
    return sorted({f.split("_")[0] for f in os.listdir(NOTES)
                   if re.match(r"^[A-Z0-9]{8}_", f)})


def diagnose(keys=None):
    """只读诊断。返回 {'ok','fixable':[...],'manual':[...],'checked':N}。

    fixable 每项：id / key / noteFile / before / after / archive / ratio
    manual  每项：key / noteFile / quote / why
    """
    corpus = build_corpus()
    keys = list(keys) if keys else _all_keys()
    fixable, manual = [], []
    for key in keys:
        nf = _note_file(key)
        if not nf:
            continue
        note = open(os.path.join(NOTES, nf), encoding="utf-8").read()
        for raw_q in V.extract_quotes(note):
            if V.strip_refs(raw_q):
                continue
            segs = [x.strip().strip('"') for x in re.split(r"…|\.\.\.", raw_q)]
            segs = [x for x in segs if len(re.findall(r"[a-zA-Z]", x)) >= MIN_LETTERS]
            if not segs:
                continue
            # 该引语是否**已经命中**。严格（去空白）与宽松（再去连字符）都算 ——
            # 宽松级是闸门自己的独立档位（「差异仅在连字符」），不是未命中；
            # 对它做「修复」只会把笔记里正确的连字符删掉（实测 3RQGFGFQ 的 long-term、
            # 6WR5489M 的 Fibrillation → 档案侧 Fibril- lation）。故一律跳过。
            if any(V.normalize(x) in corpus[k][3] or
                   V.normalize(x, drop_hyphen=True) in corpus[k][4]
                   for x in segs for k in corpus):
                continue
            if "…" in raw_q or "..." in raw_q:
                manual.append(dict(key=key, noteFile=nf, quote=raw_q,
                                   why="含省略号（多段拼接），不机械替换"))
                continue
            a = re.sub(r"[^0-9A-Za-z]", "", V.normalize(raw_q))
            found = None
            for k, (s, sa, idx, _, _) in corpus.items():
                j = sa.find(a)
                if j >= 0:
                    found = (k, s, idx, j)
                    break
            if not found:
                manual.append(dict(key=key, noteFile=nf, quote=raw_q,
                                   why="字母数字层也对不上 ⇒ 有实质差异，须人工"))
                continue
            k, s, idx, j = found
            sub = s[idx[j]:idx[j + len(a) - 1] + 1]
            sub = re.sub(r"\s+", " ", sub).strip()
            patched, substantive = _patch(raw_q, sub)
            if substantive:
                manual.append(dict(key=key, noteFile=nf, quote=raw_q,
                                   why="去掉空白后仍有增删词（%d 处），不是字形差异，须人工" % len(substantive)))
                continue
            if patched == raw_q:
                continue                      # 差异只在空白/归一化会抹平的字形上 ⇒ 无需改
            ratio = difflib.SequenceMatcher(None, V.normalize(raw_q), V.normalize(patched)).ratio()
            if ratio < MIN_RATIO:
                manual.append(dict(key=key, noteFile=nf, quote=raw_q,
                                   why="相似度仅 %.2f，不自动改" % ratio))
                continue
            why = unsafe_change_reason(raw_q, patched)
            if why:
                manual.append(dict(key=key, noteFile=nf, quote=raw_q, why=why,
                                   would_be=patched))
                continue
            fixable.append(dict(
                id=make_id(key, raw_q), key=key, noteFile=nf,
                before=raw_q, after=patched, archive=k, ratio=round(ratio, 3),
            ))
    return {"ok": True, "vault": VAULT, "checked": len(keys),
            "fixable": fixable, "manual": manual,
            "summary": _summarize(fixable, manual)}


# 归因分桶：把「不能自动修」的原因归成几类，好让人一眼看清
# 未命中到底是「笔记在编」还是「档案残了」。
BUCKETS = [
    ("实质差异（须人工判笔记还是档案错）", "字母数字层也对不上"),
    ("档案侧软连字符 U+00AD", "软连字符"),
    ("档案侧 markdown 记号", "markdown"),
    ("会删掉笔记侧标点（档案残缺）", "会删掉"),
    ("档案侧符号污染（± 代 < / ≈ / †）", "符号"),
    ("新增不属于可还原的字形类别", "不属于可自动还原"),
    ("省略号多段拼接", "省略号"),
    ("相似度不足", "相似度"),
]


def _summarize(fixable, manual):
    out = {"可自动修": len(fixable)}
    for it in manual:
        bucket = "其他"
        for name, pat in BUCKETS:
            if pat in it["why"]:
                bucket = name
                break
        out[bucket] = out.get(bucket, 0) + 1
    return out


def apply_ids(ids, keys=None):
    """只落笔点名的那几条 id。**重新诊断一遍**再改 —— 绝不用调用方传来的旧内容。

    返回 {'ok','applied':[...],'missing':[...],'skipped':[...],'backup':路径或None,'log':日志路径}
    missing：id 现在已不可修（多半是笔记已被改过）；
    skipped：before 在笔记里已找不到（内容变了，宁可不动）。
    """
    want = set(str(x) for x in (ids or []))
    if not want:
        return {"ok": False, "error": "no-ids"}
    d = diagnose(keys)
    log_before = _read_log()
    backup_dir = None
    touched = {}          # noteFile -> 改后的正文
    applied, used = [], set()

    for it in d["fixable"]:
        if it["id"] not in want:
            continue
        nf = it["noteFile"]
        body = touched.get(nf)
        if body is None:
            body = open(os.path.join(NOTES, nf), encoding="utf-8").read()
        if it["before"] not in body:
            continue
        body = body.replace(it["before"], it["after"], 1)
        touched[nf] = body
        applied.append(it)
        used.add(it["id"])

    if not touched:
        return {"ok": True, "applied": [], "missing": sorted(want),
                "skipped": [], "backup": None, "log": None,
                "note": "没有可落笔的条目（id 可能已失效——笔记被改过就会这样）"}

    # 落笔前整份快照到库外
    import datetime
    stamp = datetime.datetime.now().strftime("%Y%m%d")
    backup_dir = os.path.join(BACKUP_ROOT, stamp + "_quote_repair")
    os.makedirs(backup_dir, exist_ok=True)
    for nf in touched:
        shutil.copy2(os.path.join(NOTES, nf), os.path.join(backup_dir, nf))

    for nf, body in touched.items():
        with open(os.path.join(NOTES, nf), "w", encoding="utf-8") as fh:
            fh.write(body)

    log = log_before + [dict(date=stamp, **it) for it in applied]
    with open(LOG, "w", encoding="utf-8") as fh:
        json.dump(log, fh, ensure_ascii=False, indent=1)

    return {"ok": True, "applied": applied, "missing": sorted(want - used),
            "skipped": [], "backup": backup_dir, "log": LOG}


def _read_log():
    try:
        return json.load(open(LOG, encoding="utf-8"))
    except Exception:
        return []


def _human(d, apply_note=""):
    print("=== 归因 ===")
    for k, v in sorted(d["summary"].items(), key=lambda kv: -kv[1]):
        print("  %4d  %s" % (v, k))
    print("\n=== 可自动修（引号字形还原 / 补回良构 ±）===")
    for it in d["fixable"]:
        print("  [%s] id=%s  ratio %.3f" % (it["key"], it["id"], it["ratio"]))
        print("      - %s" % re.sub(r"\s+", " ", it["before"])[:150])
        print("      + %s" % re.sub(r"\s+", " ", it["after"])[:150])
    if not d["fixable"]:
        print("  （无）")
    print("  合计 %d 条%s" % (len(d["fixable"]), apply_note))
    print("\n=== 须人工处理（%d 条）===" % len(d["manual"]))
    for it in d["manual"]:
        print("  [%s] %s\n      %s" % (it["key"], it["why"],
                                       re.sub(r"\s+", " ", it["quote"])[:150]))


def main():
    argv = sys.argv[1:]
    as_json = "--json" in argv
    apply = "--apply" in argv
    ids_file = None
    for i, a in enumerate(argv):
        if a == "--apply-ids" and i + 1 < len(argv):
            ids_file = argv[i + 1]
    flags_with_val = {"--apply-ids"}
    keys = []
    skip_next = False
    for i, a in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if a in flags_with_val:
            skip_next = True
            continue
        if not a.startswith("--"):
            keys.append(a)
    keys = keys or None

    if ids_file:
        try:
            raw = json.load(open(ids_file, encoding="utf-8"))
        except Exception as e:
            out = {"ok": False, "error": "bad-ids-file", "message": str(e)}
            print(json.dumps(out, ensure_ascii=False, indent=1) if as_json else "错误：" + str(e))
            return 0
        ids = raw if isinstance(raw, list) else (raw.get("ids") or [])
        r = apply_ids(ids, keys)
        if as_json:
            print(json.dumps(r, ensure_ascii=False, indent=1))
        else:
            print("已落笔 %d 条" % len(r.get("applied") or []))
            for it in (r.get("applied") or []):
                print("  [%s] %s" % (it["key"], it["id"]))
            if r.get("missing"):
                print("未生效的 id：", ", ".join(r["missing"]))
            if r.get("backup"):
                print("快照 →", r["backup"])
        return 0

    d = diagnose(keys)
    if apply:
        r = apply_ids([it["id"] for it in d["fixable"]], keys)
        note = "（已落盘）" if r.get("applied") else "（无可落笔项）"
        _human(d, note)
        if r.get("backup"):
            print("快照 →", r["backup"])
        print("日志 →", r.get("log") or LOG)
        return 0

    if as_json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        _human(d, "（未落盘：逐条确认走 --apply-ids，批量走 --apply）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
