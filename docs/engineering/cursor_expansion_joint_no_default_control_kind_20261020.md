# Architecture: movement joints must not invent CONTROL_JOINT kind

## Observed repository behavior

`compute_movement_joint` defaults `joint_kind=JointKind.CONTROL_JOINT`. Omitted-kind callers therefore publish a masonry control joint.

## Inference

Kind is identity, not a typical-construction default. Unknown kind must stay unknown.

## Proposed change

Add `JointKind.UNKNOWN` and default omitted kind to it.

## Benchmark observations that must not influence implementation

Expected joint schedules and project names are not inputs.
