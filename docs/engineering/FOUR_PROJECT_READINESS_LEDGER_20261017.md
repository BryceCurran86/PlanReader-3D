# Four-project readiness ledger, 2026-10-17

Share-safe: statuses, counts, times and reason codes only. No source PDF, render, page content or private path.
Official four-project accuracy stays **`null` / UNPUBLISHED** (the frozen manifests are still `INCOMPLETE`, the runs below are
single-primary-PDF diagnostic handoffs, and nothing here is a score). Tracker: #2608.

## Run identity

- Owner machine: Windows 11, 15.6 GB RAM, 6 logical CPUs, Python 3.13, PyMuPDF 1.28.0, isolated venv.
- Launcher: `tools/four_job_windows_launcher.py` (v2), `--max-private-gb 10 --min-free-commit-gb 3 --timeout-min 120`, run from the
  owner kit folder (10/10 original PDFs verified by SHA-256 and size before anything starts).
- Code under test: **main `c0f9c2f8`** (session A). The unmerged memory work in #2929 was measured separately on
  throwaway vehicle commits (sessions B and C); that table is evidence for review, not a property of main.

Reproduce (from the kit folder, with the PDFs in `sources/<project>/`):

```bash
python <repo>/tools/four_job_windows_launcher.py --ref <40-hex commit> --timeout-min 120 --max-private-gb 10 --min-free-commit-gb 3
# one project: add  --only au_qld_maryborough_service_station
```

## A. Main alone (`c0f9c2f8`)

| project | status | wall time | peak private | first blocking authority (from `production_summary.json`) |
|---|---|---:|---:|---|
| Lot16 (arch PDF, topology p3) | `COMPLETED`, sealed | 497 s | 1,387 MB | 8 `opening_area` quantities sealed; the other 13 of 21 physical openings are unsigned (host, frame, kind, axes) |
| 3Laurel (topology p3) | `COMPLETED`, `no_sealable_quantities` | 615 s | 4,297 MB | 1,445 canonical walls now exist (`candidate`; was 0 on 2026-10-16 `47c8031a` with `live_canonical_wall_frame_conflict`), 139 openings, 292 rooms; claim `abstained`: `live_physical_net_wall_integration_unavailable`, `opening_two_face_wall_lineage_ambiguous`, `complete_authenticated_host_wall_universe_required`, `host_binding_record_unavailable`; 1,559 unresolved wall candidates |
| Maryborough (31 pp, topology p7 + p30 + p31) | `SYSTEM_MEMORY_GUARD` | 331 s | 8,017 MB | not a source finding: the handoff commits more than the machine's free commit allows (on 2026-10-16 it hit the 10 GB bound at 12.4 GB) |
| Q5446 (standard plans, 10 pp) | `COMPLETED`, `source_complexity_blocked` | 255 s | 4,920 MB | `physical_wall_candidate_scope_complexity_exceeded`: 9 of 10 pages exceed `MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS = 20,000`; 0 canonical objects |

Changes since the 2026-10-16 receipts (`docs/engineering/four_job_runs/20261016_47c8031a`): Lot16's sealed run and family run and Q5446's summary are identical to
those receipts (summaries compared after normalising the session folder name); 3Laurel's canonical walls went from 0 to 1,445 (retaining colliding candidates locally, #2680); Maryborough still cannot complete on this machine.

## B. Frozen evaluator on what exists (unchanged evaluator)

- `benchmarks.frozen_holdout.full_plan_v2.run_development_scoreboard` with no produced items: `PARTIAL_OR_BLOCKED`, 120 source-closed
  truth items, 4 projects configured, 0 executed, accuracy `None`.
- Lot16, `run_exact_project_reconciliation` on the archived signed run and its identity map: denominator 27, **8 matched within tolerance**,
  19 missed, 0 outside tolerance, coverage 0.296; regenerating the report gives the archived `exact_project_report.json` (equal after Windows newline
  normalisation: the evaluator writes CRLF on Windows, the archive is LF).
- The eight Lot16 values in session A are 0.54, 0.9, 1.26, 1.8, 1.8, 2.16, 2.16, 10.08 m2 (equal to the archived signed set; the complete-handoff
  fingerprint differs from the signed replay because it is a different entry point).
- Maryborough (session B, below): the one sealed FIRM `floor_area` quantity (a single physical room) has no benchmark binding, so exact reconciliation against the
  frozen 24 gives **0 matched, `unsupported_extra` 1** with the earlier identity map. A produced quantity is not a match until the physical identity is bound.

## C. Unmerged evidence: #2929 (memory), same machine, vehicle = main + PR head

| project | main alone (A) | + #2929 `5556da63` | + #2929 `668b0f85` |
|---|---|---|---|
| Lot16 | 497 s, 1,387 MB | 258 s, 1,254 MB, sealed outputs byte-identical to A | 240 s, 1,182 MB, **sealed outputs differ** (see below) |
| 3Laurel | 615 s, 4,297 MB | 323 s, 2,484 MB, summary byte-identical | 296 s, 2,278 MB, summary byte-identical |
| Q5446 | 255 s, 4,920 MB | 152 s, 3,043 MB, summary byte-identical | 123 s, 2,145 MB, summary byte-identical |
| Maryborough | `SYSTEM_MEMORY_GUARD`, 331 s, 8,017 MB | **`COMPLETED` / sealed**, 1,632 s, 7,130 MB | **`COMPLETED` / sealed**, 1,245 s, 5,264 MB |

Maryborough with #2929: 3,843 canonical walls (`candidate`), 683 floors/rooms, 180 openings, 3,909 unresolved wall candidates, one sealed `floor_area` quantity.
**Blocker found on `668b0f85`:** Lot16's eight quantities keep their semantic keys, values and statuses, but every `opening_host_binding_v3_<hash>` in the evidence
IDs changes, so each quantity fingerprint and the run fingerprint change (signed-output immutability, item 6a of the levers guide). A vehicle through `4270a218`
reproduces the Lot16 sealed run byte for byte; the change appears with `668b0f85`. Posted on #2929.

## D. What would move the score (not done here)

| project | next dependency | suggested lane (inference) |
|---|---|---|
| Lot16 | 13 of 21 physical openings need host/frame/kind/axes; door heights need the owner decision in the levers guide | GPT MAX / GPT1 |
| 3Laurel | host wall band and whole-wall identity so openings and wall area can be signed; the 1,445 canonical walls are `candidate` only | GPT MAX / Cursor |
| Maryborough | #2929 (memory) with Lot16 identity preserved, then physical-identity binding of the produced floor area and the room/finish families | Cursor, GPT1, GPT3 |
| Q5446 | outlined-text ink above the 20,000-segment cap needs a reviewed design (the cap itself must not change) | architecture report #2847 |
| all | CI cannot run the original-source jobs until the originals are provisioned (`docs/engineering/ORIGINAL_SOURCE_PROVISIONING.md`) | owner + Claude |
