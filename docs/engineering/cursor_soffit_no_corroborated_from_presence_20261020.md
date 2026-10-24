# Architecture: soffit resolve must not mint CORROBORATED from resolved records

## Observed repository behavior

`SourceExternalSoffitAuthority.resolve` sets `CORROBORATED` when every filtered record carries `SOURCE_EXTERNAL_SOFFIT_RESOLVED`.

## Inference

A caller-supplied resolved flag is not corroboration. Shadow soffit stay candidate.

## Proposed change

The all-resolved path stays `CANDIDATE`. Conflicts still abstain.

## Benchmark observations that must not influence implementation

Expected eaves areas and project names are not inputs.
