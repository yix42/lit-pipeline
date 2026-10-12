#!/usr/bin/env python3
"""对真实 PDF 评「正文 / 表格 / 公式」三类内容的提取质量，为转换引擎选型提供依据。

用法：
    python3 pdf_quality_test.py a.pdf b.pdf          # 指定文件
    python3 pdf_quality_test.py --dir /path/to/pdfs  # 目录（自动跳过 ._ 开头的 macOS 资源叉）
    python3 pdf_quality_test.py --tables a.pdf       # 额外做表格结构抽样
    python3 pdf_quality_test.py --formulas a.pdf     # 额外做公式抽样

⚠️ 关键约束：默认使用 page.get_text()，**不要加坐标重排**。
   实测证明按 (y, x) 重排会把图注/坐标轴标签/面板标记(a/b)打碎成交错行——
   现代出版商 PDF 已嵌入正确文本流顺序，坐标重排会覆盖它。
"""
import argparse
import glob
import json
import os
import re
import sys
import time

try:
    import pymupdf as fitz          # PyMuPDF >= 1.24 推荐写法
except ImportError:                 # 兼容旧写法
    import fitz                     # type: ignore


def stats_for(path, do_tables=False, do_formulas=False):
    t0 = time.time()
    doc = fitz.open(path)
    pages = len(doc)
    texts, imgs = [], 0
    for pg in doc:
        texts.append(pg.get_text())          # 不做坐标重排
        imgs += len(pg.get_images(full=True))
    dt = time.time() - t0
    T = "\n".join(texts)

    hyph = len(re.findall(r"[a-z]-\s*\n\s*[a-z]", T)) / max(len(T.split()), 1)
    rec = {
        "file": os.path.basename(path),
        "pages": pages,
        "images": imgs,
        "chars": len(T),
        "seconds": round(dt, 2),
        "has_text_layer": len(T.strip()) > 800,
        "hyphen_break_rate": round(hyph, 4),
        "table_refs": len(re.findall(r"\bTable\s*\d", T)),
        "figure_refs": len(re.findall(r"\bFig(?:ure)?\.?\s*\d", T)),
        "formula_like": len(re.findall(r"(?:^|\n)\s*[A-Za-zα-ωΑ-Ω]\s*=\s*[^\n]{2,70}", T)),
    }

    if do_tables:
        found, samples = 0, []
        for i, pg in enumerate(doc):
            try:
                tabs = pg.find_tables()
            except Exception:                       # noqa: BLE001
                rec["table_note"] = "find_tables 不可用"
                break
            for t in tabs.tables:
                found += 1
                if len(samples) < 3:
                    try:
                        samples.append({"page": i + 1, "rows": t.row_count,
                                        "cols": t.col_count,
                                        "head": [[str(c or "")[:26] for c in r]
                                                 for r in (t.extract() or [])[:3]]})
                    except Exception:               # noqa: BLE001
                        pass
        rec["tables_detected"] = found
        rec["table_samples"] = samples
        # 表头是否被拆行：首两行有重复单元格内容即视为可疑
        rec["table_header_suspect"] = any(
            len({c for c in s["head"][0] if c}) < len([c for c in s["head"][0] if c])
            or (len(s["head"]) > 1 and bool(set(s["head"][0]) & set(s["head"][1])))
            for s in samples) if samples else False

    if do_formulas:
        hits = []
        for i, pg in enumerate(doc):
            for m in re.finditer(r"(?:^|\n)\s*([A-Za-zα-ωΑ-Ω]\s*=\s*[^\n]{2,70})", pg.get_text()):
                hits.append({"page": i + 1, "text": m.group(1).strip()[:90]})
            if len(hits) >= 6:
                break
        rec["formula_samples"] = hits
        rec["formula_fragmented"] = any(
            len(h["text"].split()) <= 3 or re.search(r"\d\s*\.\s*\d", h["text"]) for h in hits
        ) if hits else None

    doc.close()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--tables", action="store_true")
    ap.add_argument("--formulas", action="store_true")
    ap.add_argument("--json", default="/tmp/pdf_quality.json")
    a = ap.parse_args()

    files = list(a.paths)
    if a.dir:
        files += [p for p in glob.glob(os.path.join(a.dir, "**", "*.pdf"), recursive=True)
                  if not os.path.basename(p).startswith("._")]
    if not files:
        print("未指定 PDF。用法见 --help", file=sys.stderr)
        sys.exit(1)

    print(f"{'文件':<46}{'页':>4}{'图':>5}{'字符':>9}{'断行':>7}{'耗时':>8}  正文")
    print("-" * 92)
    rows = []
    for p in files:
        if not os.path.exists(p):
            print(f"  !! 不存在 {p}")
            continue
        try:
            r = stats_for(p, a.tables, a.formulas)
        except Exception as e:                      # noqa: BLE001
            print(f"{os.path.basename(p)[:44]:<46}  ERR {type(e).__name__}: {str(e)[:50]}")
            continue
        rows.append(r)
        v = "可提取" if r["has_text_layer"] else "疑似扫描件(需OCR)"
        print(f"{r['file'][:44]:<46}{r['pages']:>4}{r['images']:>5}{r['chars']:>9}"
              f"{r['hyphen_break_rate']*100:>6.2f}%{r['seconds']:>7.1f}s  {v}")

    if not rows:
        sys.exit(1)

    n = len(rows)
    scanned = sum(1 for r in rows if not r["has_text_layer"])
    print("-" * 92)
    print(f"样本 {n} · 有文字层 {n-scanned} · 疑似扫描件 {scanned} · "
          f"平均断行率 {sum(r['hyphen_break_rate'] for r in rows)/n*100:.2f}% · "
          f"平均 {sum(r['seconds'] for r in rows)/n:.2f}s/篇")

    if a.tables:
        print("\n表格质量：")
        for r in rows:
            if "tables_detected" not in r:
                continue
            flag = "表头疑似被拆行" if r.get("table_header_suspect") else "表头结构正常"
            print(f"  {r['file'][:40]:<42} 检出 {r['tables_detected']:>2} 张 · {flag}")
            for s in r.get("table_samples", [])[:1]:
                print(f"      p{s['page']} {s['rows']}行×{s['cols']}列 首行: "
                      f"{' | '.join(s['head'][0])[:78]}")

    if a.formulas:
        print("\n公式质量：")
        for r in rows:
            if r.get("formula_samples"):
                frag = r.get("formula_fragmented")
                print(f"  {r['file'][:40]:<42} 抽样 {len(r['formula_samples'])} 处 · "
                      f"{'⚠️ 碎片化' if frag else '尚可'}")
                for h in r["formula_samples"][:2]:
                    print(f"      p{h['page']}: {h['text']}")

    json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)
    print(f"\n明细已写 {a.json}")


if __name__ == "__main__":
    main()
