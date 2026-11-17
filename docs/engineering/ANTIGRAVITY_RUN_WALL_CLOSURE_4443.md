# AntiGravity executable handoff — wall/opening inversion and room closure (#4443)

**Owner correction, 17 November 2026.** The coloured owner-marked floor plan identifies two fabricated box-shaped excursions where there is one straight physical exterior wall. Around BED 5, WIR, BATH and LIVING, wall ink was classified as a doorway while actual openings were missed. Fix source classification **before** closing room polygons; do not manufacture a wall or partition based on an overlay.

## Claim and branch instructions

1. Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, current issue [#4443](https://github.com/BryceCurran86/PlanReader-3D/issues/4443) and PRs [#4445](https://github.com/BryceCurran86/PlanReader-3D/pull/4445), [#4423](https://github.com/BryceCurran86/PlanReader-3D/pull/4423), [#4436](https://github.com/BryceCurran86/PlanReader-3D/pull/4436), [#4437](https://github.com/BryceCurran86/PlanReader-3D/pull/4437). Claim the source-native exterior edge and wall/doorway functions on coordination issue #4135; don't overwrite an active agent's branch.
2. Work within the **original** PlanReader `pb_*` pipeline. The research `planreader_next` app must not be promoted to a second customer issuer.
3. Use an approved LOCAL environment with access to the real private PDF. No screenshot-only wall inference; verify the PDF's SHA. Never upload the PDF, private overlays or absolute source path to the public repo, issues, CI artifacts or PR logs. The connection formerly used by ChatGPT (Desktop Commander) is quota-blocked, but AntiGravity can execute these local commands with its own authorized source access.
4. Run the one-command harness below from the repository root. It runs focused tests, source-first exterior diagnostics, native edge ownership and room-boundary overlay; creates source-local JSON/PNG/manifest outside the Git checkout. It uses Python 3.13; dependency installation follows the repo's existing requirements and is not performed automatically by the harness.
5. Inspect `manifest.json`, `footprint/page_<N>_footprint_first.json/png`, `native_ownership/page_<N>_native_exterior_owners.json/png`, and `room_regions.json/png`. In the original screenshot's BED 5 / WIR / BATH / LIVING region, prove continuous native wall spans, actual hosted doorway/slider geometry, virtual closures and non-overlapping enclosed floor rings. A room-name label by itself is never a physical partition. LIVING/KITCHEN remain combined where open-plan; ALFRESCO remains distinct. Exclude the false two boxes only when original ink proves a straight exterior; genuine alcoves remain.
6. Add failing regression fixtures first, implement source-positive repairs, rerun focused tests and **exact-head full Python 3.13/3.14 CI**. Record before/after source SHA, exact native path IDs, unresolved gap coordinates and first failing authority gate. Unresolved cases remain ABSTAIN, not invented closed walls.
7. Push bounded PR(s) and merge when exact-head tests pass, original source overlay matches owner corrections, required customer-integrity checks hold and integration conflicts are resolved. Do not modify frozen 120-item denominator, sealed signed observations, 20,000 native-primitive cap or 2.5-point production snap. A temporary closure is not a wall-surface quantity; do not invent commercial quantities.

## Local command (PowerShell)

```powershell
# Example: set paths to YOUR existing private source and private output directory.
# This is a 0-based page index. Acacia original floor page p2 => PageIndex 1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_antigravity_wall_closure.ps1 `
  -Pdf "C:\PRIVATE\original_acacia.pdf" `
  -PageIndex 1 `
  -OutDir "C:\PRIVATE\antigravity_replays" `
  -ExpectedSha256 "435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a"
```

Do not use the example path literally. The SHA above comes from the existing Acacia original-source PR notes and must be compared with the actual privately held document; if it doesn't match, stop. Other drawings require their own measured SHA and page index.

The script deliberately disallows paths inside the public checkout. For other PDFs, `-PageIndex` remains zero-based in the harness. Its structural region CLI receives the corresponding one-based page number.

## Current limits and integration

PR #4445 provides a **shadow-only** source-wall continuity guard and shows accepted virtual chords (cyan) vs wall-overridden false gap candidates (orange). Its regression file is only run by the harness if it is present in the current checkout. For final validation use the latest #4445 head or a branch containing its merged code; a missing test file is not a pass.

The layered doorway producer is `pb_layered_wall_doorway_room_ring_shadow.py`; the footprint source owners are `pb_source_native_exterior_edge_path_ownership.py`. Existing entry points: `tools/run_original_footprint_first.py`, `tools/run_native_exterior_path_ownership.py`, `tools/diag_structural_room_region_overlay.py`.

**Exit evidence**: one true straight exterior in the owner-identified location; authentic wall versus opening classification; closed BED 5/WIR/BATH/LIVING polygons only when source walls and hosted doorway closure support them; positive finite non-overlapping room rings; source paths and closure IDs reported; full required CI green; customer/source lineage unchanged. Do not claim completion solely because the harness exits zero: it is a source evidence producer, not an acceptance oracle.
