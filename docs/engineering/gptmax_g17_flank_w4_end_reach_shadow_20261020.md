# GPT MAX / Cursor assist — G17 flank → local W4 end-reach shadow (2026-10-20)

**Status:** Shadow diagnostic only. No host, frame, kind, metric, customer, or
benchmark authority. `99%` is an evaluation target, never a producer input.

## Compliance

Read: `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` §13, GPT MAX review
`GPTMAX_OPENING_AUTHORITY_RECOVERY_REVIEW_20261020.md` (#3342), and the
observed host path in `pb_opening_host_binding_authority._resolve_raster_source_band_host_from_records`.

## Observed

Production classifies each sealed solid flank as either
`raster_source_band_{side}_source_primitive_unmapped` or
`raster_source_band_{side}_local_wall_owner_unmapped` before any host band is
published. Remote W4 fragments that share a longer source primitive parent are
not local owners. Competing local owners conflict; nearest/first is never used.

## Inference

A nonpublishing ledger that re-observes those dispositions, retaining orphans
and multi-owners, lets GPT MAX hand exact first-gate receipts to GPT1/GPT3
without inventing geometry or relaxing tolerances.

## Proposed change (this PR)

Add `pb_g17_flank_w4_end_reach_shadow.build_g17_flank_w4_end_reach_ledger` plus
synthetic/look-alike/metamorphic tests. Default composition, signed Lot16
21/15/9/8 inventory, frozen truth, PDFs, 20k cap and 2.5 pt snap stay untouched.

## Benchmark observations excluded

Lot16 signed areas, STACKER 5.67 m², 8/27 recon, and any expected BOQ value
must not enter algorithms or thresholds.
