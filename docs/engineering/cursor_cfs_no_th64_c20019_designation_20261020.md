# Architecture: CFS members must not invent TH64 or C20019 designations

## Observed repository behavior

`parse_callout` assigns `TH64` for TOP HAT text and `C20019` for CHANNEL or C-PURLIN text when no section designation is owned.

## Inference

Typical top-hat and C-purlin catalogue sizes are not owned evidence.

## Proposed change

Omitted designation stays empty and linear mass stays 0.

## Benchmark observations that must not influence implementation

Expected CFS mass and project names are not inputs.
