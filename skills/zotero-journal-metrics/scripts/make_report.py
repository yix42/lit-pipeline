import json, html

J = json.load(open("/tmp/merged_journals.json"))
M = json.load(open("/tmp/merged_items.json"))
T = json.load(open("/tmp/zot_types.json"))
ITEMS = {i["key"]: i["data"] for i in json.load(open("/tmp/zot_items.json"))}

def fq(s):
    import re
    s = (s or "").strip()
    m = re.match(r"(\d)\s*\[([^\]]+)\]", s)
    return f"{m.group(1)}区" if m else s

rows = []
for k, v in J.items():
    j, c = v.get("jcr"), v.get("cas")
    if not j and not c:
        continue
    ifv = j.get("if", "") if j else ""
    try:
        f = float(ifv)
    except Exception:
        f = -1
    q = (j["cats"][0]["q"] if (j and j.get("cats")) else "")
    rows.append({"name": v["container"] or (v["names"][0] if v["names"] else ""),
                 "issn": (v["issns"] or [""])[0], "if": ifv, "f": f, "q": q,
                 "cas": fq(c["major_q"]) if c else "", "major": c.get("major", "") if c else "",
                 "top": c.get("top", "") if c else "", "n": v["n"],
                 "xr": v.get("xr", "")})
rows.sort(key=lambda r: -r["f"])

n_items = len(M)
n_jcr = sum(1 for r in M if r["jcr"])
n_cas = sum(1 for r in M if r["cas"])
n_q1 = sum(1 for r in M if r["jcr"] and r["jcr"]["cats"] and r["jcr"]["cats"][0]["q"] == "Q1")
n_top = sum(1 for r in M if r["cas"] and r["cas"].get("top") == "是")

trs = []
for r in rows:
    ifc = "#c0392b" if r["f"] >= 10 else ("#d35400" if r["f"] >= 5 else "#555")
    trs.append(f"""<tr>
<td class="nm">{html.escape(r['name'][:62])}</td>
<td class="mono">{html.escape(r['issn'])}</td>
<td class="num" style="color:{ifc};font-weight:600">{html.escape(r['if']) or '—'}</td>
<td class="ctr">{html.escape(r['q']) or '—'}</td>
<td class="ctr">{html.escape((r['major']+' ' if r['major'] else '')+r['cas']) if r['cas'] else '—'}</td>
<td class="ctr">{'✔' if r['top']=='是' else ''}</td>
<td class="ctr">{r['n']}</td>
</tr>""")

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Zotero 期刊指标补全报告</title>
<style>
:root{{--bd:#e3e6ea;--mut:#6b7280;--ac:#185FA5}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC","Helvetica Neue",Arial,sans-serif;
margin:0;padding:32px 28px;color:#1f2328;background:#fff;font-size:13px;line-height:1.6}}
h1{{font-size:20px;font-weight:600;margin:0 0 4px}}
.sub{{color:var(--mut);margin-bottom:22px}}
.cards{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:26px}}
.card{{border:1px solid var(--bd);border-radius:10px;padding:14px 16px}}
.card .k{{color:var(--mut);font-size:12px;margin-bottom:6px}}
.card .v{{font-size:22px;font-weight:600;color:var(--ac)}}
.card .v small{{font-size:12px;font-weight:400;color:var(--mut)}}
h2{{font-size:15px;font-weight:600;margin:28px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--bd)}}
table{{border-collapse:collapse;width:100%;font-size:12.5px}}
th{{text-align:left;font-weight:600;color:var(--mut);border-bottom:1.5px solid #ccd2d9;
padding:8px 8px;position:sticky;top:0;background:#fff}}
td{{border-bottom:1px solid #f0f2f4;padding:7px 8px;vertical-align:top}}
td.num,td.ctr{{text-align:center;white-space:nowrap}}
td.mono{{font-family:ui-monospace,Menlo,monospace;color:var(--mut);font-size:11.5px}}
tr:hover td{{background:#f8fafc}}
.note{{background:#f7f9fb;border-left:3px solid var(--ac);padding:12px 16px;border-radius:0 8px 8px 0;
color:#374151;margin-top:22px;font-size:12.5px}}
.note b{{color:#111827}}
</style></head><body>
<h1>Zotero 期刊指标补全报告</h1>
<div class="sub">数据来源：JCR 2025 · 中科院文献情报中心分区表 2025 · PubMed / Crossref ｜ 写入方式：Extra 字段 + 标签（追加合并，未覆盖原有内容）</div>
<div class="cards">
<div class="card"><div class="k">已标注条目</div><div class="v">{n_items}<small> / 326</small></div></div>
<div class="card"><div class="k">涉及期刊</div><div class="v">{len(rows)}</div></div>
<div class="card"><div class="k">有 JCR 影响因子</div><div class="v">{n_jcr}</div></div>
<div class="card"><div class="k">有中科院分区</div><div class="v">{n_cas}</div></div>
<div class="card"><div class="k">Q1 论文 / Top 期刊论文</div><div class="v">{n_q1} <small>/ {n_top}</small></div></div>
</div>

<h2>期刊明细（按影响因子降序，共 {len(rows)} 种）</h2>
<table>
<thead><tr><th>期刊</th><th>ISSN</th><th style="text-align:center">影响因子</th>
<th style="text-align:center">JCR 分区</th><th style="text-align:center">中科院分区</th>
<th style="text-align:center">Top</th><th style="text-align:center">篇数</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table>

<div class="note">
<b>说明与局限</b><br>
1. 影响因子取自 JCR 2025 数据集，分区取自中科院分区表 2025 版（大类分区，括号内为学科排名）。<br>
2. 有 23 条记录未匹配到分区数据，均为会议论文、bioRxiv 预印本、已停刊期刊或无 DOI 的条目，属正常情况。<br>
3. 另有 23 条论文的文章类型未能自动识别（多为非 MEDLINE 收录期刊），标签显示为「文章类型-期刊论文(未识别)」。<br>
4. 写入采用追加合并：原有 extra 内容（如 PMID）与原标签（如「全极峰值频率标测」「PPT-P13」）均完整保留。<br>
5. 数据集为公开镜像版本，若用于正式评聘材料，建议以图书馆 JCR / 分区表官方系统复核。
</div>
</body></html>"""

open("/tmp/Zotero期刊指标补全报告.html", "w", encoding="utf-8").write(HTML)
print("已生成报告，期刊数:", len(rows))
print("Top 10:")
for r in rows[:10]:
    print(f"   IF={r['if']:<6} {r['q']:<3} {r['cas']:<4} {r['name'][:52]}")
