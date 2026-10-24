# Architecture: movement joints must not invent a 6 mm sealant depth

## Observed repository behavior

`compute_movement_joint` sets `sealant_depth = max(0.17, gap_width_pt / 2.0)`, inventing ~6 mm whenever half-gap is smaller.

## Inference

A typical sealant-depth rule of thumb is not owned evidence. Depth follows the supplied gap only.

## Proposed change

`sealant_depth = gap_width_pt / 2.0` with no minimum. Zero gap stays zero volume.

## Benchmark observations that must not influence implementation

Expected joint volumes and project names are not inputs.
