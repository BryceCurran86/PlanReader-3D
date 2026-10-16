# Four-job owner-machine run receipts, 2026-10-16 (code `47c8031a`)

**What this is.** Share-safe, hash-pinned receipts from one complete run of the v2 owner-side launcher
(`tools/four_job_windows_launcher.py`, PR #2844) on the owner's Windows machine, against the 10 original PDFs
held in the owner's private kit. It contains **derived producer artifacts only**: no source PDF, no frozen
benchmark file, no score. The owner's home path is replaced by `<HOME>`. Tracker: #2608; reconciler: GPT3 (#2004).

**What this is not.** It is not a four-project score and not a customer verification. Each project is a
single primary-PDF *diagnostic* handoff (`tools.run_source_closed_project_handoff --family-group all`); a
multi-document source package is not silently treated as complete. Official four-project accuracy stays
`null` / UNPUBLISHED.

## Run identity
- Code: `main` `47c8031a3a1bab9b4b679f51ec9034efbe948506` (dedicated shallow snapshot, detached checkout).
- Launcher: v2 at PR #2844 head `3dc770a3`, flags `--ref 47c8031a3a1bab9b4b679f51ec9034efbe948506 --timeout-min 120 --max-private-gb 10 --min-free-commit-gb 3`.
- Machine: Windows 11, 15.6 GB RAM, 6 logical CPUs, Python 3.13.15 in an isolated venv, PyMuPDF 1.28.0.
- Sources: 10/10 original PDFs verified by SHA-256 and byte size by the launcher; the four repository
  preflights (`tools.diag_gpt1_source_pdf_package_preflight`) verified every document's SHA-256, size and
  page count against the frozen source manifests (`*/source_package_preflight.json`), with roles:
  Lot16 architectural 13 pp + structural 11 pp; 3Laurel 18 pp; Maryborough 31 pp; Q5446 six documents
  (standard plans 10 pp, siting, standard inclusions, specification, colour boards, sales advice/estimate).
  All four manifests still say `status=INCOMPLETE`.

## Outcomes (source-first gate; none of these is "0 correct out of N")
| project | status | wall time | peak private / working set | first blocker |
|---|---|---:|---:|---|
| Lot16 (arch PDF, topology p3) | `COMPLETED`, sealed | 310 s | 1,404 / 1,195 MB | 8 `opening_area` quantities sealed; 13 of 21 physical openings unsigned (host, frame, kind, axes). Wall status `candidate`: composition partial, frame conflict, physical identity unresolved. **Customer-row verification NOT executed here** (`verified_customer_row_count` 0 is not a verification claim). |
| 3Laurel (topology p3) | `COMPLETED`, `no_sealable_quantities` | 538 s | 4,323 / 3,972 MB | `live_canonical_wall_frame_conflict`: 0 canonical walls, 139 openings, 292 rooms, 1,559 unresolved wall candidates; host chain ends at `ambiguous_physical_wall_equivalence_for_host` / `no_authenticated_host_wall_band`. `SOURCE_PRODUCTION_BLOCKED`. |
| Maryborough (31 pp, topology p7 + p30 + p31) | `MEMORY_LIMIT` (stopped by the launcher) | 481 s | **12,429** / 5,730 MB | Not a source finding: the complete handoff commits more than the 10 GB bound within 8 minutes. `production_summary.json` is the unsealed source-attempt record. `SOURCE_PRODUCTION_BLOCKED` (resource), `PRODUCTION_NOT_EXECUTED` to completion. |
| Q5446 (standard plans, 10 pp) | `COMPLETED`, `source_complexity_blocked` | 210 s | 4,913 / 4,723 MB | `physical_wall_candidate_scope_complexity_exceeded`: 9 of 10 pages exceed `MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS = 20,000` after the motif filter (p1 41,932 ... p9 20,129; p10 8,538). `SOURCE_PRODUCTION_BLOCKED`. The cap is unchanged. |

## Reproducibility
The same four projects were run earlier on the owner machine on snapshot `fc3aceee`. For Lot16, 3Laurel and
Q5446 the sealed/combined run file, the family sealed file, `production_summary.json` and
`source_attempt_preflight.json` are **byte-identical** between that run and this one (only the output-folder
paths inside Lot16's `production_summary.json` differ). The Lot16 eight quantity values (0.54, 0.9, 1.26,
1.8, 1.8, 2.16, 2.16, 10.08 m2) equal the archived signed set; the sealed-run fingerprint differs from the
archived signed replay because this is the complete-handoff entry, not GPT3's signed replay, so **this is not a
byte comparison with the signed originals**; retain the old eight V1 receipts unchanged.

## Resource model (observation, no cap changed)
Peak private memory is close to linear in the native drawing records of the primary PDF: 3Laurel 179,153
drawings -> 4.3 GB (about 24 KB each); Maryborough 509,644 drawings -> 12.4 GB when stopped (about 24 KB each);
Lot16 arch 6,971 drawings -> 1.4 GB; Q5446 101,225 drawings -> 4.9 GB. Maryborough's whole-document ingest
(31 pages, p7 alone 109,354 drawings) does not fit comfortably on a 15.6 GB machine that is also running a
desktop. An earlier instrumented run of the same handoff (not part of these receipts) reached 14.2 GB private
(4.3 GB working set) after 20 minutes with 2.9 GB of system commit headroom and was stopped by hand; its stack
dumps were inside `publish_derived_observations` (10 min) and `_native_dimension_cap_evidence`'s whole-document
word loop (20 min), which resolves every word of the document before filtering by page.
The launcher v1 30-minute Maryborough timeout (empty log) is consistent with this memory pressure (inference; v1 recorded nothing that could confirm it).

## Files
`RUN_RECEIPT.json` (identity, limits, per-project status, and for every file the SHA-256 of the private
original and of the share-safe copy), `SHA256SUMS` (share-safe copies; verify with `sha256sum -c SHA256SUMS`),
`<project>/source_package_preflight.json`, `<project>/outputs/*` (the producer's own artifacts),
`<project>/handoff.log`, `assemble_receipts.py` (how the share-safe copies were made).
`.gitattributes` keeps the bytes exact (`* -text`).

## Next dependency
GPT3 needs the Lot16 customer verification and V1 integrity check against these artifacts; GPT MAX/GPT1 own
the 13 unsigned Lot16 openings and the 3Laurel host equivalence; the Maryborough memory bound and the Q5446
outlined-glyph ink (84 % of segments on p1 are shorter than 3 pt) need design work that starts with an
architecture report, not a larger cap.
