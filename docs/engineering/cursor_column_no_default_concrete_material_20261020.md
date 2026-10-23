# Architecture: columns must not invent CONCRETE material

## Observed repository behavior

`create_circular_column` and `create_polygonal_column` default `material="CONCRETE"`.

## Inference

A typical column material is not owned evidence.

## Proposed change

Omitted material is empty. Callers that pass an explicit material stay unchanged.

## Benchmark observations that must not influence implementation

Expected column volumes and project names are not inputs.
