#!/usr/bin/env python3
"""pymupdf-layout 对照评测：同一批 CFD PDF，比较激活 layout 前后的表格/结构提取能力。"""
import json, os, re, sys, time

import pymupdf
BASELINE_ONLY = os.environ.get("NO_LAYOUT") == "1"
if not BASELINE_ONLY:
    import pymupdf.layout     # 激活 ONNX 布局分析器

def run(path):
    t0 = time.time()
    doc = pymupdf.open(path)
    rec = {"file": os.path.basename(path), "pages": len(doc), "layout": not BASELINE_ONLY}
    texts, tables, n_tables = [], [], 0
    for i, pg in enumerate(doc):
        texts.append(pg.get_text())
        try:
            tf = pg.find_tables()
            for t in tf.tables:
                n_tables += 1
                if len(tables) < 5:
                    ex = t.extract() or []
                    tables.append({
                        "page": i + 1, "rows": t.row_count, "cols": t.col_count,
                        "head": [[str(c or "")[:22] for c in r] for r in ex[:3]],
                    })
        except Exception as e:
            rec.setdefault("table_errors", []).append(f"p{i+1}:{type(e).__name__}")
    T = "\n".join(texts)
    rec.update({
        "chars": len(T),
        "seconds": round(time.time() - t0, 2),
        "tables_detected": n_tables,
        "table_samples": tables,
        "has_latex": len(re.findall(r"\$[^$]{2,60}\$", T)),
        "eq_rows": len(re.findall(r"(?:^|\n)\s*[A-Za-zα-ωΑ-Ω]\s*=\s*[^\n]{2,70}", T)),
        "section_heads": len(re.findall(r"(?m)^\s*\d+(?:\.\d+)*\s+[A-Z][A-Za-z ]{4,60}\s*$", T)),
    })
    doc.close()
    return rec

files = sys.argv[1:]
out = [run(f) for f in files]
tag = "layout_off" if BASELINE_ONLY else "layout_on"
json.dump(out, open(f"/tmp/cfd_{tag}.json", "w"), ensure_ascii=False, indent=1)
print(f"{'文件':<28}{'页':>4}{'字符':>9}{'表格':>6}{'节标题':>7}{'LaTeX':>7}{'耗时':>8}")
print("-" * 72)
for r in out:
    print(f"{r['file'][:26]:<28}{r['pages']:>4}{r['chars']:>9}{r['tables_detected']:>6}"
          f"{r['section_heads']:>7}{r['has_latex']:>7}{r['seconds']:>7.1f}s")
print(f"\n[{tag}] 明细 -> /tmp/cfd_{tag}.json")
for r in out:
    for s in r["table_samples"][:2]:
        print(f"  {r['file'][:22]} p{s['page']} {s['rows']}x{s['cols']}: {' | '.join(s['head'][0])[:80]}")
