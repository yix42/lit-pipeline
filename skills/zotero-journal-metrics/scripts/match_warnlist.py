#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把《预警期刊列表》匹配到 Zotero 全库条目。只匹配 + 报告，不写库。

⚠️ 核心原则：ISSN 精确匹配优先，刊名兜底。**绝不使用模糊相似度匹配** ——
实测 AEROSPACE 与 Europace 相似度 0.82，模糊匹配会把 22 篇 Europace 论文错标成预警期刊。

用法：
  python3 match_warnlist.py <warnlist.csv> [zot_items.json] [out_prefix]

  warnlist.csv 需含表头，列序：序号,期刊名称,issn,eissn,来源依据
  （从用户 xlsx 导出即可，直接 sheet_get_cell_data(return_csv=True) 拿到的就是这格式）
  zot_items.json 默认 /tmp/zot_items_now.json（zot_audit.py / 拉取脚本的产物）

产出：
  <out_prefix>_hits.json    key -> {warn_src, warn_name, warn_no, matched_by, journal, title}
  <out_prefix>_miss.json    未命中条目（含全部非期刊文献，属正常）
  stdout 打印：脏数据提示 / 命中明细 / 反向体检结果
"""
import csv
import difflib
import json
import re
import sys
from collections import Counter, defaultdict

WARN_CSV = sys.argv[1] if len(sys.argv) > 1 else "/tmp/warn_journals.csv"
ITEMS = sys.argv[2] if len(sys.argv) > 2 else "/tmp/zot_items_now.json"
PREFIX = sys.argv[3] if len(sys.argv) > 3 else "/tmp/warn"


def nissn(s):
    """ISSN 归一化：去掉所有非字母数字并大写。N/A、-、/ 等一律视为空。"""
    s = re.sub(r"[^0-9Xx]", "", str(s or ""))
    return s.upper() if len(s) == 8 else ""


def nname(s):
    """刊名归一化：大写、& → AND、去标点、去 THE、压空格。"""
    s = str(s or "").upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"\bTHE\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def nloose(s):
    return nname(s).replace(" ", "")


# ---------- 读预警表 ----------
rows = list(csv.reader(open(WARN_CSV, encoding="utf-8-sig")))
if not rows:
    sys.exit("预警名单为空")
if "期刊" not in "".join(rows[0][:2]):
    sys.exit(f"表头不像预警名单，实际为：{rows[0][:5]}")
warn = []
for r in rows[1:]:
    if len(r) < 5 or not r[1].strip():
        continue
    w = {"no": r[0].strip(), "name": r[1].strip(), "issn": r[2].strip(),
         "eissn": r[3].strip(), "src": r[4].strip()}
    w["issns"] = sorted({x for x in (nissn(w["issn"]), nissn(w["eissn"])) if x})
    warn.append(w)

by_issn, by_name, by_loose = {}, {}, {}
for w in warn:
    for i in w["issns"]:
        by_issn.setdefault(i, []).append(w)
    by_name.setdefault(nname(w["name"]), []).append(w)
    by_loose.setdefault(nloose(w["name"]), []).append(w)

print(f"预警表：{len(warn)} 条 · 可归一 ISSN {len(by_issn)} 个 · 刊名 {len(by_name)} 个\n")

# ---- 脏数据提示（必须回报给用户，不要静默处理）----
noiss = [w for w in warn if not w["issns"]]
if noiss:
    print(f"⚠️ 无可用 ISSN 的条目 {len(noiss)} 条（只能靠刊名精确匹配）：")
    for w in noiss:
        print(f"     {w['name']}   issn={w['issn']!r} eissn={w['eissn']!r}")
dirty = []
for w in warn:
    for raw, clean in ((w["issn"], nissn(w["issn"])), (w["eissn"], nissn(w["eissn"]))):
        if clean and re.search(r"\s|:|;", raw):   # 能清洗出 8 位，但原文夹了空格/冒号
            dirty.append((w, raw, clean))
            break
if dirty:
    print(f"⚠️ 原始 ISSN 夹了空格/冒号 {len(dirty)} 条（已自动清洗，建议反馈给用户核对）：")
    for w, raw, clean in dirty:
        print(f"     {w['name'][:46]:<46} {raw!r} → {clean}")

# 位数不对的（典型：少打一位 / 多打一位）——最容易静默漏配，必须单列出来
odd = []
for w in warn:
    for raw in (w["issn"], w["eissn"]):
        digits = re.sub(r"[^0-9Xx]", "", raw)
        if digits and len(digits) != 8 and re.search(r"\d{3}", raw):
            odd.append((w, raw, digits))
            break
if odd:
    print(f"⚠️ ISSN 位数不对 {len(odd)} 条（**无法自动匹配**，需人工确认正确 ISSN 后再补）：")
    for w, raw, digits in odd:
        print(f"     {w['name'][:46]:<46} {raw!r} → 洗净后仅 {len(digits)} 位 {digits}")
print()

# ---------- 读库 ----------
I = json.load(open(ITEMS))
docs = [i for i in I if i["data"].get("itemType") != "attachment"]
mi_path = "/tmp/merged_items.json"
name2issn = defaultdict(set)
try:                                     # merged_items / journals_by_issn 有则用（DOI→ISSN 更准）
    for m in json.load(open(mi_path)):
        for x in (m.get("issns") or []):
            if nissn(x):
                name2issn[nname(m.get("container") or "")].add(nissn(x))
    J = json.load(open("/tmp/journals_by_issn.json"))
    for issn, rec in J.items():
        for zn in (rec.get("zotero_names") or {}):
            name2issn[nname(zn)].add(issn)
except Exception as e:                   # noqa: BLE001
    print(f"（提示：未能载入辅助 ISSN 索引 {e}，仅用刊名匹配）\n")

MI = {}
try:
    MI = {m["key"]: m for m in json.load(open(mi_path))}
except Exception:                        # noqa: BLE001
    pass


def doc_issns(d):
    out = set()
    m = MI.get(d["key"])
    if m:
        out |= {nissn(x) for x in (m.get("issns") or []) if nissn(x)}
    pub = (d.get("publicationTitle") or "").strip()
    if pub:
        out |= name2issn.get(nname(pub), set())
    return out


# ---------- 匹配 ----------
hits, miss = {}, []
for i in docs:
    d = i["data"]
    pub = (d.get("publicationTitle") or "").strip()
    iss = doc_issns(d)
    hit, how = None, ""

    for x in sorted(iss):
        if by_issn.get(x):
            hit, how = by_issn[x][0], f"ISSN {x}"
            break
    if not hit:
        for key, tag, pool in ((nname(pub), "刊名", by_name),
                               (nloose(pub), "刊名(连写)", by_loose)):
            if key and key in pool:
                hit, how = pool[key][0], tag
                break

    if hit:
        hits[d["key"]] = {"warn_src": hit["src"], "warn_name": hit["name"],
                          "warn_no": hit["no"], "matched_by": how,
                          "journal": pub or hit["name"],
                          "title": (d.get("title") or "")[:70]}
    else:
        miss.append({"key": d["key"], "pub": pub,
                     "title": (d.get("title") or "")[:60]})

json.dump(hits, open(f"{PREFIX}_hits.json", "w"), ensure_ascii=False, indent=1)
json.dump(miss, open(f"{PREFIX}_miss.json", "w"), ensure_ascii=False, indent=1)

print(f"=== 命中 {len(hits)} / {len(docs)} 条文献 ===")
for k, v in Counter(v["warn_src"] for v in hits.values()).most_common():
    print(f"   {k:<30} {v:>3}")
print()
for k, v in sorted(hits.items(), key=lambda kv: (kv[1]["warn_src"], kv[1]["journal"])):
    print(f"  {k:<9} [{v['matched_by']:<12}] {v['journal'][:36]:<36} | {v['warn_src']}")
print(f"\n（未命中 {len(miss)} 条，含全部非期刊文献，属正常；明细见 {PREFIX}_miss.json）")

# ---------- 反向体检：相似度 ≥0.80 的刊名对，逐对人工确认是否同一刊 ----------
lib = Counter()
for i in docs:
    p = (i["data"].get("publicationTitle") or "").strip()
    if p:
        lib[p] += 1
flagged = {nname(v["warn_name"]) for v in hits.values()}
print("\n=== 反向体检：名单刊名 × 库内刊名，相似度 ≥0.80 ===")
print("    （逐对确认是否同一刊；全是不同刊即为预期。用来排除「名单 ISSN 写错→漏配」）")
pairs = 0
for w in warn:
    for lp, ln in lib.items():
        if not nname(lp):
            continue
        r = difflib.SequenceMatcher(None, nname(w["name"]), nname(lp)).ratio()
        if r >= 0.80:
            pairs += 1
            mark = "已标注" if nname(w["name"]) in flagged else "⚠️ 未标注——请人工确认"
            print(f"  {r:.2f} {mark}  「{w['name'][:38]}」 ↔ 「{lp[:38]}」({ln}条)")
if not pairs:
    print("  （无）")
print(f"\n共 {pairs} 对。**不要用这些相似度直接建匹配**——"
      f"这正是必须靠 ISSN 的原因。")
