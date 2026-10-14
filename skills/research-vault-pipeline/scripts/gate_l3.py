#!/usr/bin/env python3
"""L3 硬闸：**未过闸门不得进 L3**。

判定单位是「L3 页 × 该页 `sources` 里的每个 key」。对每个 key 问一句：
**这篇 L2 笔记过引语闸门了吗？** 没过，它的结论就不许被合成进知识页。

五态（不是三态 —— 「档案缺」和「引语对不上」必须分开）：

| 状态 | 含义 | 处置 |
|---|---|---|
| `PASS` | 0 未命中 | 准进 L3 |
| `REPAIRABLE` | 有未命中，但**全部**是「引号字形 / 补回良构 ±」这类可安全自动修的 | 先跑 `repair_note_quotes.py`，修完复检再进 |
| `FAIL` | 有未命中且含实质差异 | **不准进** —— 回 L2 核：改笔记，还是修档案 |
| `NO-FULLTEXT` | 笔记在，但 `40_Fulltext/md/<KEY>.md` 缺 | **不准进** —— 这条引语从未被核验过 |
| `NO-NOTE` | 该 key 没有 L2 笔记 | **不准进** —— 没有可引用的层 |

⚠️ **本闸是独立脚本，不并进 `validate_vault.py`。** 理由：
`validate_vault.py` 的 WARN 计数是被当健康信号用的（存量全是大 PDF 那几条）；
把一项**天天红**的检查塞进去，会把那个信号淹掉，于是没人再看 WARN。
闸门的意义就是「单义」——红了就是不准进，不许和别的告警混在一张表里。

用法：
    python gate_l3.py                    # 全库体检：逐页逐来源列状态
    python gate_l3.py --key KHG52E5I     # 单篇：这篇现在能不能进 L3
    python gate_l3.py --json             # 机器读（供 Folio / 脚本调用）
    python gate_l3.py --quiet            # 只出汇总与退出码（拿它当 CI 门）

退出码：**0 = 全过；1 = 有来源未过闸门**（`--json` 也照这个规矩，不做例外 ——
这是个闸，不是查询接口，静默成功会让人以为「反正都过」）。

**工作流铁律**（写 L3 之前跑）：
    改 L3 前 → gate_l3.py 必须绿 → 才动 30_Knowledge/
    红了 → 先 folio_repair_quotes 修可修的 → 剩下的回 L2 逐条核 → 复检绿了再写页
"""
import argparse
import contextlib
import io
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATE = os.path.join(os.path.dirname(_HERE), "State")
sys.path.insert(0, _STATE)

import verify_note_quotes as V     # noqa: E402  归一化口径的唯一真源
import repair_note_quotes as R     # noqa: E402  可修性判定（复用它的诊断）

KNOW = os.path.join(V.VAULT, "30_Knowledge")

PASS = "PASS"
REPAIRABLE = "REPAIRABLE"
FAIL = "FAIL"
NO_FULLTEXT = "NO-FULLTEXT"
NO_NOTE = "NO-NOTE"
UNKNOWN = "UNKNOWN"

BLOCKING = (FAIL, NO_FULLTEXT, NO_NOTE, UNKNOWN, REPAIRABLE)   # REPAIRABLE 也算「未过」

WHY = {
    PASS: "0 未命中",
    REPAIRABLE: "未命中全是可安全自动修的字形差异 —— 先跑 repair_note_quotes.py",
    FAIL: "有实质差异 —— 回 L2 核是笔记错还是档案残",
    NO_FULLTEXT: "缺全文档案 —— 这条引语从未被核验过",
    NO_NOTE: "没有 L2 笔记 —— 没有可引用的层",
    UNKNOWN: "闸门里没有这个 key",
}


# ---------------- L3 页与 sources ----------------
def l3_pages():
    out = []
    for root, _dirs, files in os.walk(KNOW):
        for f in sorted(files):
            if f.endswith(".md") and not f.startswith("_"):
                out.append(os.path.join(root, f))
    return sorted(out)


def parse_sources(text):
    """两种写法都要认：行内 `sources: [A, B]` 与块状 `sources:\\n  - A`。

    （库内两种都有 —— KT/KM 用块状、KR/KV 用行内。只认一种会静默漏掉半库来源，
    而「漏掉」在这里等于**放行**，是最危险的失败方向。）
    """
    m = re.search(r"^sources:\s*\[(.*?)\]\s*$", text, re.M)
    if m:
        return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]
    m = re.search(r"^sources:\s*\n((?:[ \t]+-[ \t]*\S.*\n)+)", text, re.M)
    if m:
        return [ln.strip().lstrip("-").strip().strip("\"'")
                for ln in m.group(1).strip().split("\n") if ln.strip()]
    return []


# ---------------- 判定 ----------------
def verdicts(keys=None):
    """返回 (rev, verdict_fn, fix_by, man_by)。rev 是闸门的 JSON 结果。

    ⚠️ 必须用 `redirect_stdout` 包住这两次调用：`V._json_review()` 内部走
    `check_key(verbose=False)`，而它**仍会 print()**（`verify_note_quotes.py`
    只在 `__main__` 的 JSON 分支包了 stdout，import 进来直接调不会被隔离）。
    不包的话 `--json` 输出会被逐篇明细污染成一坨非 JSON 文本。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rev = V._json_review(keys)
        diag = R.diagnose(keys)
    miss = {r["key"]: r for r in rev["results"]}
    errs = {e["key"]: e["error"] for e in rev["errors"]}

    fix_by, man_by = {}, {}
    for x in diag["fixable"]:
        fix_by[x["key"]] = fix_by.get(x["key"], 0) + 1
    for x in diag["manual"]:
        man_by[x["key"]] = man_by.get(x["key"], 0) + 1

    def v(k):
        if k in errs:
            return NO_NOTE if errs[k] == "no-note" else NO_FULLTEXT
        if k not in miss:
            return UNKNOWN
        if miss[k]["miss"] == 0:
            return PASS
        if man_by.get(k, 0) == 0 and fix_by.get(k, 0) > 0:
            return REPAIRABLE
        return FAIL

    return rev, v, fix_by, man_by


def gate(only_key=None):
    rev, v, fix_by, man_by = verdicts([only_key] if only_key else None)

    rows = []
    pages = l3_pages()
    for p in pages:
        text = open(p, encoding="utf-8").read()
        src = parse_sources(text)
        items = []
        for k in src:
            st = v(k)
            items.append({
                "key": k, "status": st, "why": WHY[st],
                "miss": (rev["results"] and next(
                    (r["miss"] for r in rev["results"] if r["key"] == k), None)),
                "fixable": fix_by.get(k, 0), "manual": man_by.get(k, 0),
            })
        rows.append({
            "page": os.path.relpath(p, V.VAULT),
            "name": os.path.basename(p)[:-3],
            "sources": len(src),
            "blocked": sum(1 for x in items if x["status"] in BLOCKING),
            "items": items,
        })

    if only_key:
        cite = [r["name"] for r in rows if any(x["key"] == only_key for x in r["items"])]
        return {"ok": True, "mode": "single", "key": only_key, "status": v(only_key),
                "why": WHY[v(only_key)], "fixable": fix_by.get(only_key, 0),
                "manual": man_by.get(only_key, 0), "citedBy": cite,
                "gate": {"notes": rev["keys"], "totals": rev["totals"]}}

    summary = {s: 0 for s in (PASS, REPAIRABLE, FAIL, NO_FULLTEXT, NO_NOTE, UNKNOWN)}
    for r in rows:
        for x in r["items"]:
            summary[x["status"]] += 1
    return {
        "ok": True, "mode": "all", "vault": V.VAULT,
        "gate": {"notes": rev["keys"], "requested": rev["requested"], "totals": rev["totals"]},
        "pages": rows,
        "summary": summary,
        "citations": sum(r["sources"] for r in rows),
        "blockedPages": [r["name"] for r in rows if r["blocked"]],
    }


def render(g):
    L = []
    if g["mode"] == "single":
        k = g["key"]
        L.append("L3 硬闸 · 单篇判定")
        L.append("")
        L.append("  %s  →  %s" % (k, g["status"]))
        L.append("  %s" % g["why"])
        L.append("  可自动修 %d 条 · 须人工 %d 条" % (g["fixable"], g["manual"]))
        L.append("  当前被这些 L3 页引用：" + ("、".join(g["citedBy"]) if g["citedBy"] else "（无）"))
        L.append("")
        L.append("  ⇒ " + ("准进 L3。" if g["status"] == PASS else "**不准进 L3**（先处置上面那条）"))
        return "\n".join(L)

    gt = g["gate"]["totals"]
    L.append("L3 硬闸 · 全库体检")
    L.append("  闸门：%d 篇 / 引语 %d · 严格 %d / 仅连字符 %d / 未命中 %d"
             % (g["gate"]["notes"], gt["total"], gt["strict"], gt["loose"], gt["miss"]))
    L.append("")
    for r in g["pages"]:
        mark = "✗" if r["blocked"] else "✓"
        L.append("%s %s  —  %d 处来源，%d 未过闸门" % (mark, r["name"], r["sources"], r["blocked"]))
        for x in r["items"]:
            if x["status"] == PASS:
                continue
            extra = ""
            if x["status"] == FAIL:
                extra = "（未命中 %s：可修 %d / 须人工 %d）" % (x["miss"], x["fixable"], x["manual"])
            elif x["status"] == REPAIRABLE:
                extra = "（可自动修 %d 条）" % x["fixable"]
            L.append("     %-22s %-12s %s%s" % (x["key"], x["status"], x["why"], extra))
    L.append("")
    s = g["summary"]
    L.append("汇总：%d 页 / %d 处来源引用" % (len(g["pages"]), g["citations"]))
    L.append("  PASS %d · REPAIRABLE %d · FAIL %d · NO-FULLTEXT %d · NO-NOTE %d · UNKNOWN %d"
             % (s[PASS], s[REPAIRABLE], s[FAIL], s[NO_FULLTEXT], s[NO_NOTE], s[UNKNOWN]))
    if g["blockedPages"]:
        L.append("")
        L.append("⇒ **未过闸门，不得进 L3**（%d 页待处置）。退出码 1。" % len(g["blockedPages"]))
        L.append("   处置顺序：① 跑 repair_note_quotes.py 修可修的；")
        L.append("             ② 剩下的用 verify_note_quotes.py --diagnose <KEY> 逐条归因；")
        L.append("             ③ 笔记错就改笔记，档案残就修档案；④ 复检绿了再写 L3。")
    else:
        L.append("")
        L.append("⇒ 全部通过。退出码 0。")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(add_help=True, description="L3 硬闸：未过闸门不得进 L3")
    ap.add_argument("--key", help="只判这一篇（8 位 zotero_key）")
    ap.add_argument("--json", action="store_true", help="机器读输出")
    ap.add_argument("--quiet", action="store_true", help="只出汇总行")
    a = ap.parse_args()

    key = a.key.strip().upper() if a.key else None
    g = gate(key)

    if a.json:
        print(json.dumps(g, ensure_ascii=False, indent=1))
    elif a.quiet:
        if g["mode"] == "single":
            print("%s %s" % (g["key"], g["status"]))
        else:
            s = g["summary"]
            print("L3 硬闸：%d 页 / %d 处来源 · 未过 %d（FAIL %d · REPAIRABLE %d · 缺档案 %d · 缺笔记 %d）"
                  % (len(g["pages"]), g["citations"],
                     g["citations"] - s[PASS], s[FAIL], s[REPAIRABLE], s[NO_FULLTEXT], s[NO_NOTE]))
    else:
        print(render(g))

    if g["mode"] == "single":
        return 0 if g["status"] == PASS else 1
    return 0 if all(r["blocked"] == 0 for r in g["pages"]) else 1


if __name__ == "__main__":
    sys.exit(main())
