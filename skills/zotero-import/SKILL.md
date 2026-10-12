---
name: zotero-import
description: 'Imports PubMed papers into a local Zotero library via the Zotero HTTP API (localhost:23119). Creates a named collection (idempotent), tags the imported items (--tags), and PATCHes each item into that collection, working around the local-client pitfalls where POST /connector/import ignores the collections= parameter and drops the RIS AN (PMID) field, and where batch POST /items silently writes collections but drops tags/extra. Use this skill whenever the user wants papers added to Zotero by PMID or by .ris into a specific collection (e.g. 导进 zotero, 建个集合 XXX 把这些文献归进去, 打标签, import into Zotero).'
agent_created: true
---

# zotero-import

Add PubMed papers to a local Zotero library and land them in a **specific**
collection. The bundled `scripts/zotero_import.py` encodes the full validated
pipeline so the agent never re-derives the endpoint quirks.

## When to use

- User says "导进 zotero / 导入 Zotero", "建个集合 XXX 把这几篇归进去",
  "把这些文献导入并新建集合", or names a Zotero collection to file papers under.
- Inputs are PMIDs, DOIs (including **conference abstracts** not in PubMed), or an existing `.ris` file.
- Also use when the user wants a report/PPT's citations reverse-imported and tagged with
  page anchors (`PPT-P12`) so a specific slide's evidence can be queried later.
- **Also**: the user asks to **merge/dedupe duplicate records** in the library
  ("把 Zotero 里的重复记录合并一下") → jump to *Merging duplicate records* below,
  run `scripts/zotero_merge_duplicates.py`.

## How to use

Run the script with **any** Python 3 (standard library only — no pip needed):

```bash
# By PMIDs, into a named collection (created if absent)
python ~/.workbuddy/skills/zotero-import/scripts/zotero_import.py \
    --collection "CRT_心衰_心内血栓_脑梗" \
    --pmids 35344280,29670888,33716763

# From an existing RIS file
python ~/.workbuddy/skills/zotero-import/scripts/zotero_import.py \
    --collection "LAA_CFD_血栓风险" --ris papers.ris

# Also back up the built RIS
python ~/.workbuddy/skills/zotero-import/scripts/zotero_import.py \
    --collection "X" --pmids 1,2,3 --out dump.ris

# Tag every imported item (useful for grouping by source / by report page)
python ~/.workbuddy/skills/zotero-import/scripts/zotero_import.py \
    --collection "X" --pmids 1,2,3 --tags "汇报页内引用,PPT-P9"

# Build RIS + report WITHOUT importing (sanity check first)
python ~/.workbuddy/skills/zotero-import/scripts/zotero_import.py \
    --collection "X" --pmids 1,2,3 --dry-run
```

- `--collection` is required; the collection is created if it does not exist.
- `--pmids` (comma-separated) OR `--ris <file>` (mutually exclusive input modes).
- `--out <path>` optionally dumps the assembled RIS for archiving.
- `--tags <csv>` applies the same tag set to every imported item (needs no extra flag).
- `--dry-run` is the **only** safe trial flag. There is no `--dry`; an unknown flag is
  silently ignored by argparse-free call paths and the **full import still runs** — do not
  "test" with an invented flag.
- `--auth <path>` defaults to `~/.workbuddy/zotero_local_auth.json` (the
  pre-stored local Zotero credentials). Do **not** re-request authorization.

## Hard constraints (each one fails silently — read before writing)

0. **`find_or_create_collection` only scans TOP-LEVEL collections.** If the target name
   exists only as a **subcollection** (e.g. `02_基质定量与新型指标` nested under
   `左房电压梯度与异质性`), the script does not find it and **creates a duplicate
   top-level collection with the same name** — the import silently lands in the wrong
   place. Observed 2026-09-18: importing into `02_基质定量与新型指标` created a spurious
   top-level `IJYCHMLP`.
   **Workaround:** never point `--collection` at a nested name. Import into an existing
   **top-level** collection (or a throwaway one), then PATCH the item's `collections` to
   the nested key and delete the throwaway. Deleting a collection needs
   `If-Unmodified-Since-Version: <version>` — a bare `DELETE` returns
   `428 If-Unmodified-Since-Version not provided`.
   A ready-made helper for these read/write ops ships with this skill at
   `scripts/zotero_ops.py` (`patch_item`, `delete_collection`, `collection_items`,
   `list_collections`, `get_item`, `search`); a copy also lives at
   `la_analysis/literature/zotero_import/zotero_ops.py`.

0b. **Hand-rolled `PATCH /items/{key}` needs TWO header sets, or you get a misleading `428`.**
   Observed 2026-09-21: a bare `PATCH` with only `Content-Type` returned
   `428 If-Unmodified-Since-Version not provided` — but the real cause was **missing auth
   headers**, not the version. Sending `Zotero-Server-ID` + `Zotero-API-Key` **and**
   `If-Unmodified-Since-Version: <version>` returns **204** (header name is case-insensitive).
   Without the version header alone it is a genuine 428. ⇒ Do not conclude "the local API
   can't PATCH, must use POST" — `zotero_ops.patch_item` happens to use the POST-batch form,
   but a correctly-headed PATCH works fine. **Symptom to remember: 428 on the local API almost
   always means a missing header, not a missing precondition.**

0c. **Zotero 7 has a dedicated `PMID` field — `extra`'s `PMID: xxx` line gets absorbed.**
   After writing `extra = "PMID: 38215808\n【库务】…"`, reading back shows `extra` with the
   `PMID:` line **gone** — it was auto-mapped into the top-level `PMID` field
   (`data["PMID"] == "38215808"`). **This is success, not data loss.** Do not "repair" it by
   rewriting `extra` in a loop.
   ⚠️ Consequence for **downstream consumers**: any dedupe/gap script that parses `PMID:` out of
   `extra` (or from a pubmed URL) will **miss** items written this way. Read `data["PMID"]`
   first, and only fall back to `extra` parsing.
1. **`/connector/import` drops the RIS `AN  - ` field** → PMID never lands in `extra`.
   If you need to map imported items back to PMIDs, build your own DOI→PMID / title→PMID
   map (parse `DO  - ` and `AN  - ` from the very RIS you imported) and PATCH `extra`
   afterwards. The bundled script now does this automatically.
2. **Batch `POST /api/users/{id}/items` caps at 50 items** (`413` beyond that).
   Chunk with `range(0, n, 50)` in any delete/update loop.
3. **Batch POST writes `collections` but silently drops `tags` and `extra`**, and returns
   `{"successful":...}` (a dict, not a list) — so `isinstance(res, list)` checks skip it
   without logging. **Per-item `PATCH /api/users/{id}/items/{key}` (returns 204) is the
   only reliable way to write `collections` + `tags` + `extra` together.**
4. **`limit` on `/collections/{key}/items/top` effectively caps at 100.** Page with
   `start`, or your verification count will under-report and look like a failed import.
5. **De-duplicating? score before you delete.** If the tagging loop assigns
   `by_pmid[pmid] = item` (last-write-wins), the *later* copy is the tagged one — deleting
   `group[1:]` removes exactly the copies you want to keep. Rank each copy
   (has-source-tag → tag count) descending, keep the first, delete the rest.
6. **Do not PATCH `extra` right after the import.** The connector's follow-up write
   overwrites it minutes later (`tags` survive, `extra` does not) — you get "tags fine,
   every PMID missing". Observed on 25/25 items in one batch and 6/13 in another.
   **Use a two-pass write:** pass 1 = import + PATCH `collections`/`tags`; wait 1–2 min;
   pass 2 = a `--finalize` run that does **not** import, re-scans the collection, and
   re-PATCHes only `tags`/`extra`. Then re-read the collection to confirm — never trust the
   PATCH response. A working `--finalize` template lives in
   `la_analysis/literature/zotero_import/add_batch3.py`.
7. **Conference abstracts (HRS / EHRA supplements) are NOT in PubMed.** `esearch` on
   `"<doi>"[DOI]` returns an empty list and `efetch` yields nothing — yet these are often
   exactly what a report cites for new metrics/nomenclature. Fall back to
   `GET https://api.crossref.org/works/{doi}` (send `User-Agent: '<app> (mailto:<email>)'`),
   read `message.title[0]` / `author[]` / `volume` / `issue` / `page` / `published.date-parts`.
   Keep the abstract's `PO-xx-xxx` / `AB-xxxxxxx-x` number — it is the citation identifier.
   CrossRef **rate-limits with 429**: back off (`sleep(3*(k+1))`, 4–5 tries) and sleep ≥1s
   between calls. For these items write `extra` as
   `Meeting abstract (HRS/EHRA supplement) — not indexed in PubMed` — **never** `PMID:`,
   or downstream `PMID:`-prefix parsing will treat it as a real PMID.
8. **Tag conference abstracts explicitly (`会议摘要`).** The same study is often presented at
   several meetings in one year (HRS + EHRA, then again next year); DOIs differ so dedupe
   will not merge them. Without a distinguishing tag the library shows 4–5 near-identical
   records that are easy to miscite as separate studies. Add a group tag too
   (e.g. `汇报同源系列`) and state in the index doc which single record to cite.

Full behaviour notes and rationale: `references/pitfalls.md`.
End-to-end recipe for reverse-importing a report/PPT's citations with page anchors
(`PPT-P26`) — 7 steps, tag taxonomy, and the number-as-search-fingerprint trick:
`references/report-to-zotero.md`.

## What the script does (and why)

1. Loads local credentials (`user_id` / `server_id` / `api_key`).
2. Resolves papers: PMIDs are fetched from PubMed E-utilities `efetch` (authoritative
   title/authors/DOI/abstract); or parsed from the supplied `.ris`.
3. `find_or_create_collection`: list top collections, hit by name → reuse; else
   create then **re-list** to read the key (the create call returns an empty 201 body).
4. `POST /connector/import` (RIS). Local Zotero **ignores** `collections=`, so items
   land in the UI's current collection — expected. The script captures the returned
   item keys.
5. `move_to_collection`: **per-item `PATCH`** each item's `version`, then set
   `collections:[targetKey]` plus any `--tags` and the `PMID` extra (batch POST is
   unreliable for tags/extra — see Hard constraints).
6. Verify final count via `/api/users/{id}/collections/{key}/items/top`, **paged with `start`**.
7. Re-run with `--finalize` after 1–2 minutes to re-apply `tags`/`extra` (nothing is
   imported in this mode) — this repairs the extras the connector clobbered.

All endpoint quirks and failure modes are documented in
`references/pitfalls.md` — read it before patching the script.

## Merging duplicate records (full-library sweep)

**Script**: `scripts/zotero_merge_duplicates.py` — **dry-run by default**, `--apply` executes.
Edit its `PLAN` list (`(master, [dups], exempt_children)`) after running the sweep below.
Reference run (2026-09-19): 542 top-level items → 13 groups → **16 records to trash**, 0 remaining.

**Step 1 — sweep.** Page `/api/users/{id}/items/top?limit=100&start=N` and group by
normalized `DOI`, `PMID` (parse `PMID:` out of `extra`, or the pubmed URL), and normalized
`title` (>25 chars). Do **not** skip the title key — it catches items whose DOI field is empty.
`items/top` **excludes trashed items** and its `Total-Results` header gives the live count
(use it to reconcile "before/after" numbers; `items` = top + children).

**Step 2 — classify.** Same DOI **or** same PMID ⇒ real duplicate, merge. Otherwise **stop and look**:

| Pattern | Verdict |
|---|---|
| Same title, different DOI, both `xx(Suppl_y)` and no PMID | **Two separately published conference abstracts** of one study (e.g. Europace `euac053.103` ESC-2022 vs `euad122.757` EHRA-2023, author lists differ). **Do NOT merge** — merging loses a citable item. |
| Same title, different DOI, one is `10.1101/*` / `medRxiv` | Preprint ↔ published. Check whether any vault has **a card per version** before merging; if it does, leave both. |

**Step 3 — pick the master** (order matters):
**a.** the record that a vault's card is *named after* (`10_Triage/Cards/<KEY>_*.md` in
`~/ResearchVault`, `~/CRT_Vault`, `~/CFD_Vault`, …) → **b.** the only one with an attachment →
**c.** more complete fields → **d.** earlier `dateAdded`.
⚠️ Always grep **every** vault for the keys first — the vault card name is the tie-breaker
and it is not visible from Zotero.

**Step 4 — merge** (Zotero GUI "Merge Items" semantics, but explicit and logged):
1. **Move children** of each dup to the master: `POST /items` with
   `[{"key": <child>, "version": <v>, "parentItem": <master>}]`.
   Imports **nothing** and works for `attachment` **and** `note`. Exempt a child only when you
   have verified it is redundant (compare size/md5 under `~/Zotero/storage/<attachKey>/`;
   read page count + first text via `osascript -l JavaScript` + PDFKit when the filenames match).
2. Master `collections` = **union**; master `tags` = **union** (send the **full** array — PATCH replaces it).
3. Fill master's **empty** fields from the dup (`pages`/`url`/`volume`/`issue`/`abstractNote`/…).
4. `extra` = **line-level union** (dedupe stripped lines, keep master's order, append the rest).
   This is what preserves each record's `【期刊指标】` block. Append a provenance line:
   `【库务】<date> 合并重复记录 <KEY>；引用与取文一律以本 key 为准。`
5. Trash the dup: **`POST /items` with `[{"key": <dup>, "version": <v>, "deleted": 1}]`**.
   ⚠️ **`DELETE /items/{key}` returns `428 If-Unmodified-Since-Version not provided`** on the local
   API and there is no way to pass that header through the helper — use the POST form above.
   Trash (not permanent delete) ⇒ fully reversible from the Zotero UI.
6. `extra` needs the **two-pass write** (repeat the PATCH once) — the connector clobbers the first one.

**Step 5 — verify.** Re-run the sweep: expect **0 remaining same-DOI/PMID groups**. Then
spot-check that each master still has its children and that `deleted == True` for every dup.

**Step 6 — sync downstream.** A deleted key may still be referenced by a vault card,
a fulltext archive, or an L3 page. Grep **all** vaults for the trashed keys and update:
the card's `duplicate_of` comment, the card/index decision column, and any "搁置"/"missing"
list. If a dup key holds the *better* fulltext archive (e.g. `PNPKJTY2` has 1,459 lines vs the
master's 311), keep the archive and say explicitly "新增引用用主 key，旧 key 只作全文档案 key"。

## Notes

- Zotero desktop must be running and local API enabled for the import to work.
- Deduplication is not automatic. After any import, run the sweep in
  *Merging duplicate records* above (same DOI/PMID ⇒ merge; same title with different
  DOI ⇒ inspect first, it is often two legitimate publications).
- This skill targets a **local** Zotero library. The read-only Web API (cloud) mode
  cannot write — do not confuse the two.
