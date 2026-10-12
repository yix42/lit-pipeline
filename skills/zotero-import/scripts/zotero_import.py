#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zotero_import.py — Import PubMed papers into a local Zotero library.

Workflow (validated against Zotero 8 local HTTP API):
  1. Load local credentials from ~/.workbuddy/zotero_local_auth.json
     (fields: user_id, server_id, api_key).
  2. Resolve papers: by PMID (fetch authoritative metadata from PubMed E-utilities
     efetch) OR from an existing .ris file.
  3. Create (idempotent) or find the target collection by name.
  4. Import via POST /connector/import (RIS). NOTE: local Zotero IGNORES the
     `collections=` query param — items land in the UI's currently-selected
     collection. So we import first, then move.
  5. Bulk-move imported items into the target collection via
     POST /api/users/{uid}/items (requires each item's version for optimistic lock).
  6. Verify the collection count.

Usage:
  # by PMIDs, into a named collection (created if absent)
  python zotero_import.py --collection "CRT_心衰_心内血栓_脑梗" \
      --pmids 35344280,29670888,33716763

  # from an existing RIS file
  python zotero_import.py --collection "LAA_CFD_血栓风险" --ris papers.ris

  # also dump the built RIS for backup
  python zotero_import.py --collection "X" --pmids 1,2,3 --out dump.ris

  # apply a tag to every imported item (PATCH per item — the batch POST silently drops tags)
  python zotero_import.py --collection "X" --pmids 1,2,3 --tags "VTH,核心"

No extra Python deps beyond the standard library (urllib, json, xml).
"""
import json
import os
import re
import sys
import uuid
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET


DEFAULT_AUTH = os.path.expanduser('~/.workbuddy/zotero_local_auth.json')
BASE = 'http://127.0.0.1:23119'


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
class Zotero:
    def __init__(self, auth_path=DEFAULT_AUTH):
        with open(auth_path, 'r', encoding='utf-8') as f:
            a = json.load(f)
        self.uid = a['user_id']
        self.sid = a['server_id']
        self.key = a['api_key']
        self.H = {'Zotero-Server-ID': self.sid,
                  'Zotero-API-Key': self.key,
                  'User-Agent': 'WorkBuddy'}

    def _headers(self, ctype='application/json'):
        h = dict(self.H)
        h['Content-Type'] = ctype
        return h

    def req(self, path, method='GET', data=None, ctype='application/json'):
        url = f'{BASE}{path}'
        body = None
        if data is not None:
            body = data.encode('utf-8') if isinstance(data, str) \
                else json.dumps(data).encode('utf-8')
        r = urllib.request.Request(url, data=body,
                                   headers=self._headers(ctype), method=method)
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                raw = resp.read()
                ct = resp.headers.get('Content-Type', '')
                if not raw:
                    return None
                return json.loads(raw) if 'json' in ct \
                    else raw.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:400]
            print(f'  [HTTPError {e.code}] {msg}', file=sys.stderr)
            return None

    # --- collections ----------------------------------------------------- #
    def find_or_create_collection(self, name):
        cols = self.req(f'/api/users/{self.uid}/collections/top?format=json&limit=200')
        if isinstance(cols, list):
            for c in cols:
                if c.get('data', {}).get('name') == name:
                    return c['key'], True
        # create (body MUST be an array; 201 returns empty body -> re-list)
        self.req(f'/api/users/{self.uid}/collections', method='POST',
                 data=[{'name': name, 'parentCollection': False}])
        cols = self.req(f'/api/users/{self.uid}/collections/top?format=json&limit=200')
        if isinstance(cols, list):
            for c in cols:
                if c.get('data', {}).get('name') == name:
                    return c['key'], False
        raise RuntimeError('collection create/list failed')

    # --- import ----------------------------------------------------------- #
    def import_ris(self, ris_text):
        url = (f'{BASE}/connector/import?session={uuid.uuid4()}'
               f'&collections=&tags=&items=')
        r = urllib.request.Request(url, data=ris_text.encode('utf-8'),
                                   headers=self._headers('text/plain'), method='POST')
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                raw = resp.read()
                txt = raw.decode('utf-8', 'replace')
                try:
                    imported = json.loads(txt)
                    if isinstance(imported, list):
                        return [x.get('key') for x in imported if x.get('key')]
                except Exception:
                    pass
                return []
        except urllib.error.HTTPError as e:
            print(f'  [import HTTPError {e.code}]', file=sys.stderr)
            return []

    # --- move ------------------------------------------------------------- #
    def move_to_collection(self, item_keys, collection_key, tags=None, extra_map=None):
        """逐条 PATCH 写入 collections / tags / extra。

        为什么不用批量 POST /items：本地 Zotero 上该批量接口会出现
        「collections 生效、tags 与 extra 静默不生效」的偏态写入，且返回体是
        {"successful":...} 字典而非数组，容易连日志都不打。逐条 PATCH 返回 204，三者都落地。
        """
        tags = tags or []
        extra_map = extra_map or {}
        ok = fail = 0
        for k in item_keys:
            d = self.req(f'/api/users/{self.uid}/items/{k}?format=json')
            if not d:
                fail += 1
                continue
            body = {'version': d['version'], 'collections': [collection_key]}
            if tags:
                body['tags'] = [{'tag': t} for t in tags]
            if k in extra_map:
                body['extra'] = extra_map[k]
            r = self.req(f'/api/users/{self.uid}/items/{k}', method='PATCH', data=body)
            # 204 时 req() 返回 None（空 body），视为成功
            if r is None or isinstance(r, dict):
                ok += 1
            else:
                fail += 1
            time.sleep(0.05)
        print(f'  patch: {ok} ok, {fail} failed')
        return ok, fail

    def collection_items(self, collection_key):
        """按 start 分页拉全量：/items/top 的 limit 最大生效 100。"""
        out, start = [], 0
        while True:
            items = self.req(
                f'/api/users/{self.uid}/collections/{collection_key}/items/top'
                f'?format=json&limit=100&start={start}')
            if not isinstance(items, list) or not items:
                break
            out += items
            start += 100
            if len(items) < 100:
                break
        return out


# --------------------------------------------------------------------------- #
# Paper resolution
# --------------------------------------------------------------------------- #
def clean(t):
    return (t or '').replace('\n', ' ').strip()


def fetch_by_pmids(pmids):
    ids = ','.join(pmids)
    url = (f'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
           f'?db=pubmed&id={ids}&rettype=pubmed&retmode=xml')
    with urllib.request.urlopen(url, timeout=60) as r:
        xml_text = r.read()
    root = ET.fromstring(xml_text)
    out = {}
    for art in root.findall('.//PubmedArticle'):
        pmid = clean(art.findtext('.//PMID'))
        if pmid not in pmids:
            continue
        authors = []
        for au in art.findall('.//AuthorList/Author'):
            ln = clean(au.findtext('LastName'))
            fn = clean(au.findtext('ForeName') or au.findtext('Initials'))
            if ln:
                authors.append(f'{ln} {fn}')
        out[pmid] = {
            'title': clean(art.findtext('.//ArticleTitle')),
            'jtitle': clean(art.findtext('.//Journal/Title')),
            'iso': clean(art.findtext('.//Journal/ISOAbbreviation')),
            'vol': clean(art.findtext('.//JournalIssue/Volume')),
            'issue': clean(art.findtext('.//JournalIssue/Issue')),
            'year': clean(art.findtext('.//JournalIssue/PubDate/Year')),
            'pages': clean(art.findtext('.//Pagination/MedlinePgn')),
            'doi': clean(art.findtext('.//ELocationID[@EIdType="doi"]')),
            'abstract': clean(''.join((a.text or '')
                            for a in art.findall('.//Abstract/AbstractText'))),
            'authors': authors,
        }
    missing = [p for p in pmids if p not in out]
    if missing:
        print(f'  [warn] PMIDs not found: {missing}', file=sys.stderr)
    return list(out.values())


def parse_ris(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    papers = []
    cur = None
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith('TY'):
            cur = {'authors': []}
        elif line.startswith('ER'):
            if cur and cur.get('title'):
                papers.append(cur)
            cur = None
        elif cur is not None:
            tag = line[:2]
            val = line[3:].strip() if len(line) > 3 else ''
            if not val:
                continue
            if tag == 'AU':
                cur['authors'].append(val)
            elif tag == 'TI':
                cur['title'] = val
            elif tag == 'JO':
                cur['jtitle'] = val
            elif tag == 'VL':
                cur['vol'] = val
            elif tag == 'IS':
                cur['issue'] = val
            elif tag == 'PY':
                cur['year'] = val
            elif tag == 'PG':
                cur['pages'] = val
            elif tag == 'DO':
                cur['doi'] = val
            elif tag == 'AB':
                cur['abstract'] = val
    return papers


def build_ris(papers):
    def au_ris(name):
        name = name.strip()
        if ' ' in name:
            idx = name.rfind(' ')
            return name[:idx] + ', ' + name[idx + 1:]
        return name

    blocks = []
    for p in papers:
        L = ['TY  - JOUR']
        for a in p.get('authors', []):
            if a.strip():
                L.append('AU  - ' + au_ris(a))
        L.append('TI  - ' + (p.get('title') or ''))
        L.append('JO  - ' + (p.get('jtitle') or p.get('iso') or ''))
        if p.get('vol'):
            L.append('VL  - ' + p['vol'])
        if p.get('issue'):
            L.append('IS  - ' + p['issue'])
        if p.get('year'):
            L.append('PY  - ' + p['year'])
        if p.get('pages'):
            L.append('PG  - ' + p['pages'])
        if p.get('doi'):
            L.append('DO  - ' + p['doi'])
        if p.get('abstract'):
            L.append('AB  - ' + p['abstract'])
        L.append('ER  - ')
        blocks.append('\n'.join(L))
    return '\n'.join(blocks)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description='Import papers into local Zotero')
    ap.add_argument('--collection', required=True,
                    help='target collection name (created if absent)')
    ap.add_argument('--pmids', help='comma-separated PubMed IDs')
    ap.add_argument('--ris', help='path to an existing .ris file')
    ap.add_argument('--out', help='optional path to dump the built RIS for backup')
    ap.add_argument('--auth', default=DEFAULT_AUTH, help='path to zotero_local_auth.json')
    ap.add_argument('--tags', help='comma-separated tags applied to every imported item')
    ap.add_argument('--dry-run', action='store_true',
                    help='build RIS + report, but do NOT import')
    args = ap.parse_args()

    if not args.pmids and not args.ris:
        ap.error('provide --pmids or --ris')

    if args.pmids:
        pmids = [p.strip() for p in args.pmids.split(',') if p.strip()]
        print(f'Resolving {len(pmids)} PMIDs from PubMed...')
        papers = fetch_by_pmids(pmids)
    else:
        print(f'Parsing RIS {args.ris}...')
        papers = parse_ris(args.ris)

    if not papers:
        print('No papers resolved. Abort.')
        return

    ris = build_ris(papers)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(ris)
        print(f'RIS dumped -> {args.out} ({ris.count("TY  - JOUR")} entries)')

    if args.dry_run:
        print(f'[dry-run] would import {len(papers)} papers into '
              f'"{args.collection}". No import performed.')
        return

    z = Zotero(args.auth)
    key, existed = z.find_or_create_collection(args.collection)
    print(f'Collection "{args.collection}" -> key={key} '
          f'({"existed" if existed else "created"})')

    imported_keys = z.import_ris(ris)
    print(f'Imported {len(imported_keys)} item(s): {imported_keys}')

    tags = [t.strip() for t in (args.tags or '').split(',') if t.strip()]

    # connector/import 会丢弃 RIS 的 `AN  - `（PMID），故自行按标题建立 key -> PMID 映射，
    # 写完用 extra 补回去，方便日后与 PubMed 对账。
    extra_map = {}
    if imported_keys:
        by_title = {re.sub(r'\W+', ' ', p['title'].lower()).strip()[:70]: p
                    for p in papers if p.get('title')}
        for k in imported_keys:
            d = z.req(f'/api/users/{z.uid}/items/{k}?format=json')
            if not d:
                continue
            norm = re.sub(r'\W+', ' ', (d['data'].get('title') or '').lower()).strip()[:70]
            p = by_title.get(norm)
            if p and p.get('pmid'):
                extra_map[k] = f"PMID: {p['pmid']}"

    if imported_keys:
        z.move_to_collection(imported_keys, key, tags=tags, extra_map=extra_map)

    items = z.collection_items(key)
    print(f'Final collection count = {len(items)}')
    for it in items[:50]:
        d = it.get('data', {})
        print(f'  - {d.get("date", "")[:4]} | {d.get("title", "")[:70]}')


if __name__ == '__main__':
    main()
