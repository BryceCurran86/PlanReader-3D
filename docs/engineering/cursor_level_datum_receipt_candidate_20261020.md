# Architecture: level-datum compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_level_stack` returns `CORROBORATED` whenever `raw_levels` is non-empty. Elevations, finish thickness, and ceiling offset may be caller-supplied or defaulted. Commercial flags are already False.

## Inference

A non-empty caller list is not independently re-resolved FFL/storey-datum ownership. Default heights are a separate fail-open and are not changed here.

## Proposed change

Keep `CANDIDATE` when levels exist; keep `ABSTAINED` when empty. Sorting and delta arithmetic stay unchanged.

## Benchmark observations that must not influence implementation

Expected storey heights and project names are not inputs.
