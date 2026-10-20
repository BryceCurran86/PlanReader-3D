# Architecture: precast panels must not invent 175 mm thickness or 20/10/25 mm joint beads

## Observed repository behavior

`PrecastPanelSpec.thickness_mm` defaults to `175.0`. `PrecastJointSpec` defaults to a 20 mm gap, 10 mm bead depth, 25 mm backing rod, and `DOUBLE_BEAD`. `parse_joint_annotation` falls back to those figures plus a 2:1 width-to-depth ratio and 1.25 rod multiplier.

## Inference

Typical precast panel and control-joint sizes are not owned evidence.

## Proposed change

Omitted thickness, joint width, sealant depth, and rod diameter stay `0.0`. Omitted sealant config is `UNKNOWN` and contributes zero beads. Parse fallbacks match.

## Benchmark observations that must not influence implementation

Expected facade volumes and project names are not inputs.
