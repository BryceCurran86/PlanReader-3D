# Architecture: sheet-registration compile-receipt stays CANDIDATE

## Observed repository behavior

`compile_alignment_receipt` sets `CORROBORATED` whenever `len(transforms) > 0`. Transforms are computed from caller-supplied control points. Commercial flags are already False.

## Inference

A non-empty caller transform list is not independently re-resolved sheet-identity or GPCS ownership. Two rival registrations must not be resolved by nearest, first, or smallest; this PR does not add a winner. GPT2 still owns original p7↔p11 correspondence.

## Proposed change

Keep `CANDIDATE` when `total > 0`; keep `ABSTAINED` when empty. Similarity arithmetic is unchanged.

## Benchmark observations that must not influence implementation

Maryborough page-11/page-7 expected offsets and frozen BOQ values are not inputs.
