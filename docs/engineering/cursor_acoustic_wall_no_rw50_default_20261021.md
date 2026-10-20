# Architecture: operable acoustic walls must not invent Rw50

## Observed repository behavior

`OperableWallSpec.acoustic_rating_rw_db` and `parse_callout` default to `50` when no Rw figure is owned.

Traced: `OperableWallSpec`, `SourceOperableAcousticWallShadowAuthority.parse_callout`.

## Inference

A typical Rw 50 rating is not owned evidence. Same class as the lining Rw50 fail-closed.

## Proposed change

Omitted `acoustic_rating_rw_db` is `0` on both the spec and the parser fallback. Explicit `RW 50` / `RW 45` / `RW 53` still parse. Status stays `CANDIDATE`; `takeoff_eligible` stays `False`.

## Authority boundaries

Shadow module only. No live extractor, W10, commercial rows, or `benchmarks/frozen_holdout/full_plan_v2/**`.

## Expected abstentions

Callout `"OPERABLE WALL"` and a bare `OperableWallSpec` keep `acoustic_rating_rw_db == 0`.

## Benchmark observations that must not influence implementation

Expected acoustic ratings and project names are not inputs.
