# Architecture: fire-compartment compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_fire_compartment_receipt` sets `CORROBORATED` whenever `len(walls) > 0`. Records are caller-supplied wall boxes. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved fire-compartment ownership. Default 90-minute damper rating is a separate fail-open.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected fire-wall areas and project names are not inputs.
