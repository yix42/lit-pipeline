#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zotero_merge_duplicates.py — 把 Zotero 库内**同 DOI/PMID** 的重复记录合并到主记录。

合并动作（对齐 Zotero GUI「Merge Items」的语义，但显式可审）：
    1. 把被并记录的**子项（附件/笔记）转挂**到主记录（除非显式豁免）
    2. 主记录取**合集**：collections ∪、tags ∪
    3. 主记录缺失的字段用被并记录补齐（pages/url/volume/issue/abstractNote…）
    4. `extra` 做**行级并集**（保住各自的【期刊指标】块），并追加一行合并留痕
    5. 被并记录置 deleted=1（**进回收站，不永久删**）

主记录的选择规则（按优先级）：
    a. vault 里按 key 命名的 L1/L2 卡所指的那一条（ResearchVault / CRT_Vault）
    b. 唯一带附件的那一条
    c. 字段更全的那一条
    d. 更早 dateAdded 的那一条

用法：
    python3 zotero_merge_duplicates.py           # dry-run，只打印计划
    python3 zotero_merge_duplicates.py --apply   # 执行
"""
import argparse
import collections
import json
import os
import sys
import time

import zotero_ops as Z

UID = Z.user_id()

FILL = ("pages", "url", "publicationTitle", "volume", "issue", "date",
        "abstractNote", "language", "journalAbbreviation", "ISSN", "DOI")

# (主记录, [被并记录...], {豁免转挂的子项 key: 理由})
PLAN = [
    ("AAQLSLP5", ["D9732C9R", "GPDAEQND"], {}),
    ("9HKQQLKB", ["C5U9MYXE"], {"SN477WG2": "与主记录附件同为已发表版 PDF（12 vs 13 页），保留主记录那份"}),
    ("C7EC9FUZ", ["A4Y8ZXX5"], {}),
    ("ZX245LJK", ["PNPKJTY2"], {}),
    ("2QKPGBGZ", ["87X23K99"], {}),
    ("5WRZCNBC", ["5H8PF2T2"], {}),
    ("MMZ4PEIH", ["J5MWUXDK"], {}),
    ("CYU939QY", ["W66RXVC6"], {}),
    ("Q726RPTA", ["FIVRKX2L", "67489646"], {}),
    ("NQ8T9NN3", ["853Y8F3G", "DFIADIUP"], {}),
    ("2Y2L4LXW", ["62AZD32U"], {}),
    ("RMAZZ4V5", ["994UTF8F"], {}),
]

LOG = []


def A(s=""):
    LOG.append(s)
    print(s, flush=True)


def children(key):
    st, ch = Z._req("GET", f"/api/users/{UID}/items/{key}/children?limit=100&format=json")
    return ch if isinstance(ch, list) else []


def fill_missing(md, dd):
    got = []
    for f in FILL:
        if not (md.get(f) or "").strip() if isinstance(md.get(f), str) else not md.get(f):
            if (dd.get(f) or "").strip() if isinstance(dd.get(f), str) else dd.get(f):
                md[f] = dd[f]
                got.append(f)
    if not md.get("creators") and dd.get("creators"):
        md["creators"] = dd["creators"]
        got.append("creators")
    return got


def union_extra(master_extra, dup_extra):
    m = master_extra or ""
    have = {l.strip() for l in m.split("\n") if l.strip()}
    add = []
    for l in (dup_extra or "").split("\n"):
        s = l.strip()
        if s and s not in have:
            add.append(l.rstrip())
            have.add(s)
    return m.rstrip(), add


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    A("★ Zotero 重复记录合并   %s" % ("【执行】" if a.apply else "【dry-run】"))
    A("")
    n_del = 0
    for master, dups, exempt in PLAN:
        md_full = Z.get_item(master)
        md = md_full["data"]
        A("=" * 104)
        A("主记录 %s   %s" % (master, (md.get("title") or "")[:88]))
        mcols = set(md.get("collections", []))
        mtags = [t["tag"] for t in md.get("tags", [])]
        mextra = md.get("extra") or ""
        moved, filled_all = [], []

        for dup in dups:
            d_full = Z.get_item(dup)
            dd = d_full["data"]
            A("  ← 并入 %s  v=%s" % (dup, d_full["version"]))
            # 1) 子项转挂
            for ch in children(dup):
                ck = ch["key"]
                ctype = ch["data"].get("itemType")
                if ck in exempt:
                    A("      · 子项 %s (%s) **不转挂** —— %s" % (ck, ctype, exempt[ck]))
                    continue
                if a.apply:
                    st, res = Z._req("POST", f"/api/users/{UID}/items",
                                     [{"key": ck, "version": ch["version"], "parentItem": master}])
                    A("      · 子项 %s (%s) 转挂 → %s   [%s]" % (ck, ctype, master, st))
                else:
                    A("      · 子项 %s (%s) 转挂 → %s" % (ck, ctype, master))
                moved.append(ck)
            # 2/3) 合集 + 补齐字段
            mcols |= set(dd.get("collections", []))
            for t in dd.get("tags", []):
                if t["tag"] not in mtags:
                    mtags.append(t["tag"])
            got = fill_missing(md, dd)
            filled_all += got
            # 4) extra 行级并集
            mextra, add = union_extra(mextra, dd.get("extra"))
            if add:
                mextra = mextra + "\n" + "\n".join(add)
            A("      · 集合并入 %s ｜补字段 %s ｜extra 新增 %d 行"
              % (dd.get("collections"), got or "无", len(add)))
            # 5) 回收站
            if a.apply:
                st, res = Z._req("POST", f"/api/users/{UID}/items",
                                 [{"key": dup, "version": d_full["version"], "deleted": 1}])
                A("      · 置 deleted=1  [%s] %s" % (st, "" if st == 200 else res))
            else:
                A("      · 置 deleted=1")
            n_del += 1

        note = ("【库务】2026-09-19 合并重复记录 %s（同 DOI / 同 PMID）；"
                "引用与取文一律以本 key 为准。" % "、".join(dups))
        if "【库务】" not in mextra:
            mextra = mextra.rstrip() + "\n\n" + note

        body = {"collections": sorted(mcols), "tags": mtags, "extra": mextra}
        A("  ⇒ 主记录合并后：集合 %s ｜标签 %d 个" % (sorted(mcols), len(mtags)))
        if a.apply:
            md_full = Z.get_item(master)
            st, res = Z.patch_item(master, body)
            A("     PATCH [%s]" % st)
            time.sleep(0.3)
            st2, _ = Z.patch_item(master, {"extra": mextra})   # extra 需两遍写
            A("     PATCH extra 第二遍 [%s]" % st2)
        A("")

    A("=" * 104)
    A("合计：%d 组，%d 条记录进回收站" % (len(PLAN), n_del))
    log_path = os.environ.get("MERGE_LOG", os.path.join(os.getcwd(), "_zotero_merge.log"))
    open(log_path, "w", encoding="utf-8").write("\n".join(LOG) + "\n")
    print("\n-> %s" % log_path)


if __name__ == "__main__":
    main()
