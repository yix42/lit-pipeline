import json, re

ITEMS = {i["key"]: i for i in json.load(open("/tmp/zot_items.json"))}
MERGED = {r["key"]: r for r in json.load(open("/tmp/merged_items.json"))}
TYPES = json.load(open("/tmp/zot_types.json"))

MARK = "【期刊指标】"


def fmt_q(s):
    """'1 [338/5603]' -> '1区（338/5603）'"""
    s = (s or "").strip()
    m = re.match(r"(\d)\s*\[([^\]]+)\]", s)
    if m:
        return f"{m.group(1)}区（{m.group(2)}）"
    m = re.match(r"(\d)", s)
    return f"{m.group(1)}区" if m else s


def cn_sub(name):
    """'CARDIAC & CARDIOVASCULAR SYSTEMS 心脏和心血管系统' -> '心脏和心血管系统'"""
    name = (name or "").strip()
    parts = name.split()
    zh = [p for p in parts if any("\u4e00" <= ch <= "\u9fff" for ch in p)]
    return " ".join(zh) if zh else name


def build_extra(key, rec):
    d = ITEMS[key]["data"]
    old = (d.get("extra") or "").rstrip()
    j, c = rec.get("jcr"), rec.get("cas")
    t = TYPES.get(key, {})
    lines = [MARK]
    if j and j.get("if"):
        lines.append(f"影响因子: {j['if']}（JCR 2025）")
    cat = ""
    if j and j.get("cats"):
        first = j["cats"][0]
        cat = first.get("q", "")
        detail = first.get("cat", "")
        rk = first.get("rank", "")
        if cat:
            lines.append(f"JCR分区: {cat}" + (f" | {detail} {rk}" if detail else ""))
    if c and c.get("major_q"):
        tq = " | Top期刊" if c.get("top") == "是" else ""
        lines.append(f"中科院分区: {c.get('major','')} {fmt_q(c['major_q'])}{tq}")
        if c.get("sub"):
            s = c["sub"][0]
            lines.append(f"中科院小类: {cn_sub(s['name'])} {fmt_q(s['q'])}")
    if t.get("type_cn"):
        lines.append(f"文章类型: {t['type_cn']}")
    if rec.get("xr"):
        lines.append(f"新锐分区标记: {rec['xr']}")
    if rec.get("warn"):
        lines.append(f"国际期刊预警: {rec['warn']}")
    src = []
    if j:
        src.append("JCR 2025")
    if c:
        src.append("中科院分区表 2025")
    if t.get("source") and t["source"] != "none":
        src.append(t["source"])
    if src:
        lines.append("数据来源: " + " · ".join(src))
    if len(lines) == 1:
        return None
    block = "\n".join(lines)
    # 幂等：已存在则替换整块
    if MARK in old:
        old = old[:old.index(MARK)].rstrip()
    return (old + "\n\n" + block).strip() if old else block


def build_tags(key, rec):
    j, c = rec.get("jcr"), rec.get("cas")
    t = TYPES.get(key, {})
    add = []
    if j and j.get("cats"):
        q = j["cats"][0].get("q")
        if q:
            add.append(f"JCR-{q}")
    if j and j.get("if"):
        try:
            v = float(j["if"])
            add.append("IF≥10" if v >= 10 else ("IF≥5" if v >= 5 else "IF<5"))
        except Exception:
            pass
    if c and c.get("major_q"):
        m = re.match(r"(\d)", c["major_q"])
        if m:
            add.append(f"中科院{m.group(1)}区")
        if c.get("top") == "是":
            add.append("Top期刊")
    if t.get("type_cn"):
        add.append(f"文章类型-{t['type_cn']}")
    return add


def merge_tags(key, add):
    old = [x["tag"] for x in (ITEMS[key]["data"].get("tags") or [])]
    out = list(old)
    for t in add:
        if t not in out:
            out.append(t)
    return out


if __name__ == "__main__":
    n_extra = n_tag = 0
    samples = []
    for key, rec in MERGED.items():
        e = build_extra(key, rec)
        tg = build_tags(key, rec)
        if e:
            n_extra += 1
        if tg:
            n_tag += 1
        if len(samples) < 3 and e:
            samples.append((key, e, tg, merge_tags(key, tg), ITEMS[key]["data"]))
    print(f"将写入 extra 的条目: {n_extra} / {len(MERGED)}")
    print(f"将写入标签的条目: {n_tag}")
    print("=" * 74)
    for key, e, tg, allt, d in samples:
        print(f"\n### {key}  {d.get('title','')[:56]}")
        print(f"    原 extra: {repr(d.get('extra',''))}")
        print(f"    原 tags : {[x['tag'] for x in (d.get('tags') or [])]}")
        print("    ---- 新 extra ----")
        for ln in e.split("\n"):
            print("      " + ln)
        print(f"    ---- 新增 tags ---- {tg}")
        print(f"    ---- 合并后 tags ---- {allt}")
