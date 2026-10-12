#!/usr/bin/env python3
"""用户手供 PDF 入档后，幂等回写 L1 卡状态。

做三件事（都可重复运行）：
1. `fulltext_route` → `manual`，行尾注明入档日期与路径；
2. `read_scope: abstract` → `read_scope: fulltext`；
3. §6「决定」行改判为「进入 L2 精读」，并把原搁置记录**保留在下方**（不得删史）。

用法：python annotate_card_local_pdf_intake.py [key ...]
"""
import os
import re
import sys

VAULT = os.environ.get("RESEARCH_VAULT", os.path.expanduser("~/ResearchVault"))
CARDS = os.path.join(VAULT, "10_Triage/Cards")
DATE = "2026-09-19"
MARK = f"{DATE} 改判"          # 用于 frontmatter 注释
HIST = "【原行留痕】"            # 用于 §6 改判留痕（与 MARK 分开，否则前一步写入的 MARK 会把这一步判为「已完成」）
TARGETS = sys.argv[1:] or ["XPUKL6KE", "6Q8TMP9F", "C7EC9FUZ"]


def card_path(key):
    for f in os.listdir(CARDS):
        if f.startswith(key + "_") and f.endswith(".md"):
            return os.path.join(CARDS, f)
    return None


def main():
    for key in TARGETS:
        p = card_path(key)
        if not p:
            print(f"[skip] 无卡：{key}"); continue
        txt = open(p, encoding="utf-8").read()
        orig = txt

        # ① fulltext_route → manual（幂等：按「期望行」比对，不靠标记词）
        want = (f"fulltext_route: manual   # {DATE} 用户手供出版社 PDF 已入档"
                f"（`40_Fulltext/pdf/{key}.pdf` → `md/{key}.md`，多栏重排）；{MARK}")
        m = re.search(r"^fulltext_route:.*$", txt, re.M)
        if m and m.group(0).strip() != want.strip():
            txt = txt[:m.start()] + want + txt[m.end():]

        # ② read_scope → fulltext
        txt = re.sub(r"^read_scope:\s*abstract\s*$", "read_scope: fulltext", txt, count=1, flags=re.M)

        # ③ §6 决定行改判（保留原行作留痕）
        m = re.search(r"^- 决定：(.+)$", txt, re.M)
        if m and HIST not in txt:
            old = m.group(0)
            new = (f"- 决定：进入 L2 精读（**{MARK}**：用户手供出版社 PDF 已入档，"
                   f"原判「搁置」系**物理阻塞、非判定改变**）\n"
                   f"- {HIST}{old[2:]}")
            txt = txt[:m.start()] + new + txt[m.end():]
            # 全文通道行提示
            txt = re.sub(r"^- 全文通道：.*$",
                         f"- 全文通道：`manual`（**{DATE} 用户手供出版社 PDF**，"
                         f"已入档 `40_Fulltext/pdf/{key}.pdf` 与 `md/{key}.md`，多栏重排）",
                         txt, count=1, flags=re.M)

        if txt != orig:
            open(p, "w", encoding="utf-8").write(txt)
            print(f"[ok] {os.path.basename(p)}")
        else:
            print(f"[idem] {os.path.basename(p)} 无变化")


if __name__ == "__main__":
    main()
