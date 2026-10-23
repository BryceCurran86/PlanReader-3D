# Architecture: wall acoustic-insulation compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_insulation_receipt` sets `CORROBORATED` whenever `len(records) > 0`. Records are caller-supplied wall boxes and optional rating fields. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved batt-infill ownership. Default 90 mm cavity, R2.5, and Rw50 are a separate fail-open and are not changed here.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected insulation areas and project names are not inputs.
