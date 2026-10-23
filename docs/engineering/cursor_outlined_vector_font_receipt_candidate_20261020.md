# Architecture: outlined-vector-font recovery stays CANDIDATE

## Observed repository behavior

`SourceOutlinedVectorFontProducer.authority` mints `CORROBORATED` whenever classified glyph runs are non-empty. Individual records are already CANDIDATE.

## Inference

A non-empty classified run list is not independently re-resolved native-text ownership.

## Proposed change

Keep `CANDIDATE` when runs exist. Empty-run and unregistered paths stay unchanged.

## Benchmark observations that must not influence implementation

Q5446 expected text and project names are not inputs.
