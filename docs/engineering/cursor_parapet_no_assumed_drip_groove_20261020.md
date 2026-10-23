# Architecture: parapets must not assume a drip groove exists

## Observed repository behavior

`ParapetSegmentSpec.has_drip_groove` defaults to `True`.

## Inference

Typical capping drip grooves are not owned evidence. Existence stays fail-closed.

## Proposed change

Default `has_drip_groove=False`. Explicit True remains valid.

## Benchmark observations that must not influence implementation

Expected flashing counts and project names are not inputs.
