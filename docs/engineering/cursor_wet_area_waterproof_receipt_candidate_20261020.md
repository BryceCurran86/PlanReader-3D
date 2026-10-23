# Architecture: wet-area waterproofing compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_waterproofing_receipt` sets `CORROBORATED` whenever `len(wet_areas) > 0`. Records are caller-supplied floor area, perimeter, and upstand heights. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved wet-area / membrane ownership. Default 150 mm / 2000 mm heights in the compute helper are a separate fail-open and are not changed here.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty. Arithmetic and seals stay unchanged.

## Benchmark observations that must not influence implementation

Frozen finish codes, expected BOQ membrane areas, and project names are not inputs.
