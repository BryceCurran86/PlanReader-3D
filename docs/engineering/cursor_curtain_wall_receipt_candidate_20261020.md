# Architecture: curtain-wall compile-receipt stays CANDIDATE

## Observed repository behavior

Compile-receipt sets `CORROBORATED` whenever bay records are non-empty.

## Inference

A non-empty caller list is not independently re-resolved curtain-wall ownership.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected glazing areas and project names are not inputs.
