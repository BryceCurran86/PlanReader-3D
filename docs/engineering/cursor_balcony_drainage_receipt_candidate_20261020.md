# Architecture: balcony-drainage compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_balcony_receipt` sets `CORROBORATED` whenever `len(balconies) > 0`. Records are caller-supplied areas and fall distances. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved balcony ownership. Default 1:100 fall and 50 mm threshold are a separate fail-open.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected balcony areas and project names are not inputs.
