# Architecture: CFS members must not invent ROOF_PURLIN when role is omitted

## Observed repository behavior

`parse_callout` and evaluate string fallbacks assign `CFSRole.ROOF_PURLIN` when no GIRT, EAVES, or FASCIA keyword is present.

## Inference

A typical roof purlin role is not owned evidence.

## Proposed change

Omitted role stays `UNKNOWN`. Explicit ROOF or PURLIN text still parses as `ROOF_PURLIN`.

## Benchmark observations that must not influence implementation

Expected purlin meters and project names are not inputs.
