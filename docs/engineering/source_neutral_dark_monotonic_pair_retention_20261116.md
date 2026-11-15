# Monotonic source-native wall-pair retention — 16 Nov 2026

This diagnostic-only change is a child of draft PR #4347. It does not issue customer quantities, infer wall areas, construct a raster hull, or change the frozen 120-item score.

## Verified root cause

Acacia source page 2 has 42 original strict-black paired-stroke candidates. Expanding the wall ink pool with 1,458 genuinely source-owned near-black strokes introduces rival face clusters, causing the existing one-pool stroke-pair detector to return only 29 pairs. An older original-source witness is therefore lost by a weaker supplemental source candidate.

## Fix

- Capture the original black-ink source mask BEFORE adding neutral dark strokes, preserving native PDF path IDs.
- Run the original strict pair pass and expanded pair pass separately; original pairs go first and are never lost.
- Exact original path-ID tuple plus original PDF-point geometry deduplicates only identical pairs; no fuzzy gap snap.
- Wire the monotonic set to the exterior-first wall preflight, the new native room-ring tracer, and the actual annotated PlanMapper preview.
- Skip the extra baseline pass on pages without any neutral-dark additions. Keep the existing per-viewport 20,000 primitive cap, original source digest, and manual/commercial authority rules.

## Genuine original-source receipts

Acacia, source page 2: 42 strict wall-pair candidates, 29 expanded-alone candidates, 66 monotonic candidates. **Zero strict pairs lost; 24 new candidates.** Source-neutral dark paths recovered: 1,458. Full new app preview: 76 wall-strip candidates, zero confirmed rooms, physical exterior ABSTAINED, zero customer quantities.

3Laurel, original plan page 3: unchanged from existing trace. 404 candidate strips, 48 temporary doorway closures, 16 candidate enclosed regions, exterior ABSTAINED, no billable quantities. No neutral-dark rows added.

Q5446 ground original plan: unchanged from existing heavy-stroke trace. 77 source candidates, one candidate region, exterior ABSTAINED, no billable quantities.

Source original PDFs, diagnostic JSON and overlays are retained exclusively on the owner's Windows PC under private_packets. None are committed.

## Tests and limitations

Python 3.13 focused/related original-regression set: **138 passed / 4 skipped**, compilation and Ruff F821/F823 clean. Synthetic tests verify strict candidate preservation, original native-path identity and rejection when baseline source paths are replaced or renumbered.

Still unresolved: authenticated physical exterior wall loops, source-owned opening-gap witnesses, Lot16 raster wall graph, all customer wall/floor/ceiling issuers and protected final four-job benchmark. Keep draft until independently verified.
Q5446 upper original plan: unchanged, 66 candidate source strips and 2 candidate regions; exterior ABSTAINED, zero quantities. The per-pair strict and expanded diagnostic counters are null when the neutral-dark supplement is not executed, not a false zero wall count.
