# Architecture: skylights must not invent Cv 0.65 discharge coefficients

## Observed repository behavior

`SkylightVentSpec` and `parse_callout` default `discharge_coefficient_cv` to 0.65 when no coefficient is owned.

## Inference

A typical ASHEV discharge coefficient is not owned evidence.

## Proposed change

Omitted Cv stays 0. Takeoff that owns 0.65 passes it explicitly.

## Benchmark observations that must not influence implementation

Expected aerodynamic areas and project names are not inputs.
