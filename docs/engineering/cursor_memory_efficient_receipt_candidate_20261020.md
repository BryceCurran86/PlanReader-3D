# Architecture: memory-efficient plan streaming stays CANDIDATE

## Observed repository behavior

`SourceMemoryEfficientPlanProcessingProducer.authority` mints `CORROBORATED` when no pages are quarantined. Quarantined plans are already CANDIDATE.

## Inference

Completing a bounded memory stream is operational health, not independently re-resolved source ownership.

## Proposed change

Keep `CANDIDATE` on the no-quarantine path. Reason codes stay diagnostic. Unregistered selectors stay unchanged.

## Benchmark observations that must not influence implementation

Expected page counts and project names are not inputs.
