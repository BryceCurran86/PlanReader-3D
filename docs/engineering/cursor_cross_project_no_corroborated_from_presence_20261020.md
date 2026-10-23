# Architecture: cross-project validation must not mint CORROBORATED from presence

## Observed repository behavior

`SourceCrossProjectDrawingTypeValidationAuthority.resolve` sets `CORROBORATED` when records exist without bias or violation flags.

## Inference

A non-empty caller list without a veto is not corroboration.

## Proposed change

Non-defect presence stays `CANDIDATE` with `SOURCE_CROSS_PROJECT_VALIDATION_CANDIDATE`. Bias/violations still abstain.

## Benchmark observations that must not influence implementation

Drawing-type labels and project names are not prediction inputs.
