# Architecture: acoustic walls must not invent Rw50

## Observed repository behavior

`AcousticWallSpec.target_rw` defaults to `50`. `parse_acoustic_wall_tag` falls back to `50` when the tag has no Rw figure.

## Inference

A typical acoustic rating is not owned evidence. This is the same class as the prior Rw50 fail-closed.

## Proposed change

Omitted `target_rw` is `0` on both the spec and the parser fallback.

## Benchmark observations that must not influence implementation

Expected acoustic ratings and project names are not inputs.
