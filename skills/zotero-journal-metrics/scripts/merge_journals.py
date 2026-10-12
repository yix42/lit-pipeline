import json, csv, io, re, unicodedata

D = "/tmp/jcrdata/"

def norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).upper()
    s = re.sub(r"^THE\s+", "", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def load(f):
    return list(csv.DictReader(io.StringIO(open(D + f, encoding="utf-8-sig", errors="ignore").read())))

# ---------- JCR 主表：IF(2025) + 分区 + 学科 + 排名 ----------
jcr_by_issn, jcr_by_name = {}, {}
for r in load("JCR2025-UTF8.csv"):
    cats = []
    for i in range(1, 7):
        c = (r.get(f"Category_{i}") or "").strip()
        if c:
            cats.append({"cat": c,
                         "q": (r.get(f"IF Quartile(2025)_{i}") or "").strip(),
                         "rank": (r.get(f"IF Rank(2025)_{i}") or "").strip()})
    rec = {"if": (r.get("IF(2025)") or "").strip(), "cats": cats,
           "wos": (r.get("Web of Science") or "").strip(), "src": "JCR2025"}
    for k in ("ISSN", "EISSN"):
        v = (r.get(k) or "").strip()
        if v:
            jcr_by_issn.setdefault(v, rec)
    n = norm(r.get("Journal"))
    if n:
        jcr_by_name.setdefault(n, rec)

# ---------- JCR 兜底表：只有分区，但覆盖更广 ----------
n_fill = 0
for r in load("JCR_2025.csv"):
    name = (r.get("期刊名") or "").strip()
    q = (r.get("Quartile") or "").strip()
    if not name or not q:
        continue
    n = norm(name)
    if n in jcr_by_name:
        if not jcr_by_name[n]["cats"]:
            jcr_by_name[n]["cats"] = [{"cat": "", "q": q, "rank": ""}]
        continue
    jcr_by_name[n] = {"if": "", "cats": [{"cat": "", "q": q, "rank": ""}],
                      "wos": "", "src": "JCR2025_fallback"}
    n_fill += 1

# ---------- 中科院分区表 2025 ----------
cas_by_issn, cas_by_name = {}, {}
for r in load("FQBJCR2025-UTF8.csv"):
    sub = []
    for i in range(1, 7):
        s = (r.get(f"小类{i}") or "").strip()
        if s:
            sub.append({"name": s, "q": (r.get(f"小类{i}分区") or "").strip()})
    rec = {"major": (r.get("大类") or "").strip(),
           "major_q": (r.get("大类分区") or "").strip(),
           "top": (r.get("Top") or "").strip(),
           "review": (r.get("Review") or "").strip(),
           "oa": (r.get("Open Access") or "").strip(),
           "sub": sub}
    for v in re.split(r"[/,;]", (r.get("ISSN/EISSN") or "")):
        v = v.strip()
        if v:
            cas_by_issn.setdefault(v, rec)
    n = norm(r.get("Journal"))
    if n:
        cas_by_name.setdefault(n, rec)

# ---------- 新锐 2026 预警标记 ----------
xr = {}
for r in load("XR2026-UTF8.csv"):
    mark = (r.get("预警标记") or "").strip()
    for k in ("Journal", "刊名"):
        n = norm(r.get(k))
        if n and mark:
            xr[n] = mark

# ---------- 国际期刊预警名单 ----------
warn = {}
for f in ("GJQKYJMD2025.csv", "GJQKYJMD2024.csv"):
    try:
        for r in load(f):
            n = norm(r.get("Journal"))
            if n:
                warn.setdefault(n, (r.get("预警原因（2025）") or r.get("预警原因（2024）") or "预警").strip())
    except Exception:
        pass

# ---------- 汇总 ----------
cr = json.load(open("/tmp/crossref_journals.json"))
items = json.load(open("/tmp/zot_items.json"))

# ---------- 常见 NLM 缩写 → 全称（用于无 DOI 条目） ----------
ALIAS = {
    "J AM COLL CARDIOL": "JOURNAL OF THE AMERICAN COLLEGE OF CARDIOLOGY",
    "JACC": "JOURNAL OF THE AMERICAN COLLEGE OF CARDIOLOGY",
    "EUR HEART J": "EUROPEAN HEART JOURNAL",
    "NAT MED": "NATURE MEDICINE",
    "JAMA CARDIOL": "JAMA CARDIOLOGY",
    "CIRC ARRHYTHM ELECTROPHYSIOL": "CIRCULATION ARRHYTHMIA AND ELECTROPHYSIOLOGY",
    "J CARDIOVASC ELECTROPHYSIOL": "JOURNAL OF CARDIOVASCULAR ELECTROPHYSIOLOGY",
    "J INTERV CARD ELECTROPHYSIOL": "JOURNAL OF INTERVENTIONAL CARDIAC ELECTROPHYSIOLOGY",
    "PACING CLIN ELECTROPHYSIOL": "PACE PACING AND CLINICAL ELECTROPHYSIOLOGY",
    "INT J CARDIOL": "INTERNATIONAL JOURNAL OF CARDIOLOGY",
    "J AM SOC ECHOCARDIOGR": "JOURNAL OF THE AMERICAN SOCIETY OF ECHOCARDIOGRAPHY",
    "IEEE TRANS BIOMED ENG": "IEEE TRANSACTIONS ON BIOMEDICAL ENGINEERING",
    "COMPUT BIOL MED": "COMPUTERS IN BIOLOGY AND MEDICINE",
    "INT J MOL SCI": "INTERNATIONAL JOURNAL OF MOLECULAR SCIENCES",
    "SCI REP": "SCIENTIFIC REPORTS",
    "ESC HEART FAIL": "ESC HEART FAILURE",
    "J AM HEART ASSOC": "JOURNAL OF THE AMERICAN HEART ASSOCIATION",
    "ANN BIOMED ENG": "ANNALS OF BIOMEDICAL ENGINEERING",
    "BIOMED ENG ONLINE": "BIOMEDICAL ENGINEERING ONLINE",
}
def expand(*names):
    out = []
    for n in names:
        if not n:
            continue
        nn = norm(n)
        out.append(ALIAS.get(nn, n))
    return out

def pick(by_issn, by_name, issns, *names):
    for i in issns:
        if i in by_issn:
            return by_issn[i]
    for nm in expand(*names):
        if nm and norm(nm) in by_name:
            return by_name[norm(nm)]
    return None

rows, j_hit, c_hit = [], 0, 0
jidx = {}
for it in items:
    d = it.get("data", {})
    if d.get("itemType") != "journalArticle":
        continue
    doi = (d.get("DOI") or "").strip()
    meta = cr.get(doi, {})
    container = meta.get("container") or d.get("publicationTitle") or ""
    short = meta.get("short") or ""
    zname = d.get("publicationTitle") or ""
    issns = [x.strip() for x in (meta.get("issn") or []) if x.strip()]
    if not issns and d.get("ISSN"):
        issns = [x.strip() for x in re.split(r"[,;]", d["ISSN"]) if x.strip()]

    j = pick(jcr_by_issn, jcr_by_name, issns, container, short, zname)
    c = pick(cas_by_issn, cas_by_name, issns, container, short, zname)
    nm = norm(container or zname)
    x = xr.get(nm) or xr.get(norm(short)) or xr.get(norm(zname))
    w = warn.get(nm) or warn.get(norm(short)) or warn.get(norm(zname))
    if j: j_hit += 1
    if c: c_hit += 1

    key = issns[0] if issns else nm
    e = jidx.setdefault(key, {"container": container, "issns": issns, "jcr": j, "cas": c,
                              "xr": x, "warn": w, "names": set(), "n": 0})
    e["names"].add(zname)
    e["n"] += 1
    rows.append({"key": it["key"], "doi": doi, "container": container, "issns": issns,
                 "jcr": j, "cas": c, "xr": x, "warn": w})

print(f"journalArticle 条目        : {len(rows)}")
print(f"  命中 JCR(IF/分区)        : {j_hit}")
print(f"  命中中科院分区(2025)     : {c_hit}")
print(f"  两者皆无                 : {sum(1 for r in rows if not r['jcr'] and not r['cas'])}")
print(f"  JCR 兜底表补充期刊数     : {n_fill}")
print(f"  去重后期刊数             : {len(jidx)}")

miss = sorted({(r['container'] or '(无刊名)') for r in rows if not r['jcr'] and not r['cas']})
print(f"\n完全无分区数据的期刊({len(miss)}):")
for m in miss:
    print("   ", m[:70])

print("\n有 IF 数值的期刊数:", sum(1 for v in jidx.values() if v['jcr'] and v['jcr']['if']))
print("新锐预警标记命中:", sum(1 for v in jidx.values() if v['xr']))

json.dump(rows, open("/tmp/merged_items.json", "w"), ensure_ascii=False, indent=1)
json.dump({k: {**v, "names": sorted(v["names"])} for k, v in jidx.items()},
          open("/tmp/merged_journals.json", "w"), ensure_ascii=False, indent=1)
print("\n已写 /tmp/merged_items.json 与 /tmp/merged_journals.json")
