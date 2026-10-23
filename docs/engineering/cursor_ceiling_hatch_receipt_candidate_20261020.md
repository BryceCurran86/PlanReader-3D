# Architecture: ceiling-hatch compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_hatch_receipt` sets `CORROBORATED` whenever `len(hatches) > 0`. Records are caller-supplied hatch boxes. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved ceiling-hatch ownership. Default 600 mm hatch size is a separate fail-open and is not changed here.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty.

## Benchmark observations that must not influence implementation

Expected hatch counts and project names are not inputs.
