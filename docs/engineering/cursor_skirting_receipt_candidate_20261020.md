# Architecture: skirting compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_skirting_receipt` sets `CORROBORATED` whenever `len(records) > 0`. Records are caller-supplied perimeters. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved skirting ownership.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected skirting lengths and project names are not inputs.
