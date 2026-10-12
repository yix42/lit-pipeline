#!/usr/bin/env python3
"""幂等回写 L1 卡里的「L2 已建」状态。

在 §6「分诊决定」块末尾追加一行 L2 状态，并在 frontmatter 的 `fulltext_route` 行尾加注释。
重复运行不会重复追加（幂等）。

用法：python annotate_card_l2_state.py
"""
import os
import re

VAULT = os.environ.get("RESEARCH_VAULT", os.path.expanduser("~/ResearchVault"))
CARDS = os.path.join(VAULT, "10_Triage/Cards")
NOTES = os.path.join(VAULT, "20_Notes")

TARGETS = {
    "2QKPGBGZ": "2QKPGBGZ_SUPPRESS-AF-RCT_2025",
    "6W9Z9MMN": "6W9Z9MMN_VOLCANO-RCT_2020",
    "BMPXNTHI": "BMPXNTHI_CAPLA-RCT_2023",
    "3RQGFGFQ": "3RQGFGFQ_VOLCANO-Extended_2022",
}
DATE = "2026-09-19"
MARK = "L2 精读笔记：已建"


def card_path(key):
    for f in os.listdir(CARDS):
        if f.startswith(key + "_") and f.endswith(".md"):
            return os.path.join(CARDS, f)
    return None


def note_exists(base):
    return os.path.exists(os.path.join(NOTES, base + ".md"))


def main():
    changed = []
    for key, base in TARGETS.items():
        p = card_path(key)
        if not p:
            print(f"[skip] 找不到卡：{key}")
            continue
        if not note_exists(base):
            print(f"[skip] L2 笔记不存在：{base}")
            continue
        txt = open(p, encoding="utf-8").read()
        orig = txt

        # ① frontmatter：fulltext_route 行尾注明 L2 已建
        def fix_route(m):
            line = m.group(0)
            if MARK in line:
                return line
            line = re.sub(r"\s*#.*$", "", line)
            return f"{line.rstrip()}   # {DATE} {MARK}"

        txt = re.sub(r"^fulltext_route:.*$", fix_route, txt, count=1, flags=re.M)

        # ② §6 末尾追加 L2 状态行（幂等；判据用 [[]] 而非 MARK——
        #    因为 ① 已在 frontmatter 注释里写过 "L2 精读笔记：已建"，用 MARK 判会误跳过）
        if f"[[{base}]]" not in txt:
            entry = f"- **{MARK}**（{DATE}）→ [[{base}]]（`20_Notes/{base}.md`）"
            m = re.search(r"(##\s*6\.\s*分诊决定\n)(.*?)(\n---\n|\n###\s|\Z)", txt, re.S)
            if m:
                block = m.group(2).rstrip("\n")
                if "全文通道：" in block:
                    # 插在「全文通道」行之后，保持原有行序
                    lines = block.split("\n")
                    idx = max(i for i, l in enumerate(lines) if l.startswith("- 全文通道："))
                    lines.insert(idx + 1, entry)
                    block = "\n".join(lines)
                else:
                    block = block + "\n" + entry
                txt = txt[:m.start(2)] + block + "\n" + txt[m.end(2):]
            else:
                print(f"[warn] {key} 未找到 §6 区块，跳过状态行")

        if txt != orig:
            open(p, "w", encoding="utf-8").write(txt)
            changed.append(key)
    print("已更新卡：" + (", ".join(changed) if changed else "（无变化）"))


if __name__ == "__main__":
    main()
