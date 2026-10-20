# Architecture: floor-waste compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_drainage_receipt` sets `CORROBORATED` whenever drain records are non-empty.

## Inference

A non-empty caller list is not independently re-resolved waste-drain ownership.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected drain counts and project names are not inputs.
