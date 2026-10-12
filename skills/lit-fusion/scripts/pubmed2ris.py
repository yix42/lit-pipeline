#!/usr/bin/env python3
"""PMID(s) -> RIS, via NCBI efetch.

Useful when a paper shows up only in a Consensus (or other non-PubMed) hit
list and you need an authoritative DOI / full metadata before archiving.

Usage:
    python3 pubmed2ris.py 30216113,20176989 -o out.ris
"""
import argparse
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _text(node):
    return "".join(node.itertext()).strip() if node is not None else ""


def fetch(pmids):
    data = urllib.parse.urlencode({
        "db": "pubmed", "retmode": "xml", "id": ",".join(pmids)
    }).encode()
    with urllib.request.urlopen(EUTILS, data=data, timeout=60) as r:
        return ET.fromstring(r.read())


def to_ris(root):
    blocks = []
    for art in root.iter("PubmedArticle"):
        L = []
        add = L.append

        atype = "JOUR"
        for pub in art.findall(".//PublicationType"):
            if pub.text in ("Review",):
                atype = "JOUR"
        add("TY  - " + atype)

        for a in art.findall(".//Author"):
            ln, fn = _text(a.find("LastName")), _text(a.find("ForeName"))
            if ln:
                add(f"AU  - {ln}, {fn}" if fn else f"AU  - {ln}")
            elif _text(a.find("CollectiveName")):
                add(f"AU  - {_text(a.find('CollectiveName'))}")

        title = _text(art.find(".//ArticleTitle"))
        # PubMed title already ends with '.' for translated articles; keep as-is
        add(f"TI  - {title}")
        add(f"JO  - {_text(art.find('.//Journal/Title'))}")
        add(f"JA  - {_text(art.find('.//Journal/ISOAbbreviation'))}")

        y = (_text(art.find(".//JournalIssue/PubDate/Year"))
             or _text(art.find(".//PubMedPubDate/Year")))
        add(f"PY  - {y}")
        add(f"VL  - {_text(art.find('.//JournalIssue/Volume'))}")
        add(f"IS  - {_text(art.find('.//JournalIssue/Issue'))}")
        add(f"SP  - {_text(art.find('.//Pagination/MedlinePgn')).split('-')[0]}")
        pg = _text(art.find(".//Pagination/MedlinePgn"))
        if pg:
            add(f"PG  - {pg}")

        pmid = art.findtext(".//PMID")
        doi = ""
        for i in art.findall(".//ArticleId"):
            if i.get("IdType") == "doi":
                doi = i.text
        if doi:
            add(f"DO  - {doi}")
        if pmid:
            add(f"AN  - {pmid}")
            add(f"UR  - https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

        ab = " ".join(_text(x) for x in art.findall(".//Abstract/AbstractText")).strip()
        if ab:
            add(f"AB  - {ab}")

        kw = [_text(k) for k in art.findall(".//Keyword")][:15]
        for k in kw:
            if k:
                add(f"KW  - {k}")

        add("ER  - ")
        blocks.append("\n".join(L) + "\n\n")

    if not blocks:
        raise SystemExit("no PubMed records returned for the given PMID(s)")
    return "".join(blocks)


def main():
    p = argparse.ArgumentParser(description="Convert PubMed PMIDs to RIS")
    p.add_argument("pmids", help="comma-separated PMIDs")
    p.add_argument("-o", "--out", required=True, help="output .ris path")
    a = p.parse_args()

    pmids = [x.strip() for x in a.pmids.split(",") if x.strip()]
    ris = to_ris(fetch(pmids))

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(ris)

    # echo a compact confirmation of what was written
    root = fetch(pmids)
    for art in root.iter("PubmedArticle"):
        doi = next((i.text for i in art.findall(".//ArticleId")
                    if i.get("IdType") == "doi"), "")
        print(f"PMID {art.findtext('.//PMID')} | DOI {doi} | "
              f"{_text(art.find('.//ArticleTitle'))[:70]}")
    print(f"\n-> wrote {a.out}")


if __name__ == "__main__":
    sys.exit(main())
