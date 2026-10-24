# Architecture: hybrid mixed-format recovery stays CANDIDATE

## Observed repository behavior

`SourceHybridMixedFormatRecoveryProducer.authority` mints `CORROBORATED` for every registered page, including from caller-supplied vector/raster segment lists.

## Inference

Registered caller primitives are not independently re-resolved mixed-format ownership.

## Proposed change

Mint `CANDIDATE` on the registered-page path. Unregistered selectors still `ABSTAIN`. Reconciliation arithmetic is unchanged.

## Benchmark observations that must not influence implementation

Expected primitive counts and project names are not inputs.
