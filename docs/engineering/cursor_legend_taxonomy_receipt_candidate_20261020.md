# Architecture: legend-symbol taxonomy compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_taxonomy_receipt` sets `CORROBORATED` whenever `len(viewports) > 0`. Viewports are caller-supplied boxes and symbol tuples. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved legend ownership.

## Proposed change

Keep `CANDIDATE` when `total_boxes > 0`; keep `ABSTAINED` when empty. Quarantine arithmetic is unchanged.

## Benchmark observations that must not influence implementation

Expected symbol counts and project names are not inputs.
