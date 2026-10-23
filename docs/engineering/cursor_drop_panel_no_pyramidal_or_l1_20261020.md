# Architecture: drop panels must not invent PYRAMIDAL capitals or L1 storeys

## Observed repository behavior

`ColumnCapitalSpec.shape` and `compute_capital_frustum_volume` default to `CapitalShape.PYRAMIDAL`, so omitted shape still gets a pyramidal frustum volume. `DropPanelSpec.level_id` and `ColumnCapitalSpec.level_id` default to `"L1"`.

## Inference

A typical capital shape and a first-storey level id are not owned evidence.

## Proposed change

Omitted shape is `UNKNOWN` and contributes zero capital volume. Omitted level id is empty.

## Benchmark observations that must not influence implementation

Expected drop-panel volumes and project names are not inputs.
