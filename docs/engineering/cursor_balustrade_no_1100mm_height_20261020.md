# Architecture: balustrades must not invent 1100 mm or 1000 mm heights

## Observed repository behavior

`BalustradeRunSpec.height_mm` defaults to `1100.0`. `parse_balustrade_annotation` invents 1100 mm for balconies and 1000 mm for stairs/ramps/voids. Omitted height still counted as non-compliant against those typical code minima.

## Inference

Typical NCC barrier heights are not owned evidence.

## Proposed change

Omitted height stays `0.0` on both the spec and the parser. Face area is 0 and the non-compliant flag is not raised when height is omitted.

## Benchmark observations that must not influence implementation

Expected barrier areas and project names are not inputs.
