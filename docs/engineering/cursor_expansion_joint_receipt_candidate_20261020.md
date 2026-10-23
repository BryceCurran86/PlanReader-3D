# Architecture: expansion-joint compile-receipt stays CANDIDATE

## Observed repository behavior

Compile-receipt sets `CORROBORATED` whenever joint records are non-empty.

## Inference

A non-empty caller list is not independently re-resolved joint ownership.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected joint lengths and project names are not inputs.
