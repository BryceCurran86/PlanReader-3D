# Architecture: cold-room resolve must not mint CORROBORATED from presence

## Observed repository behavior

`SourceColdRoomInsulatedPanelAuthority.resolve` sets `CORROBORATED` whenever a record exists without a defect reason.

## Inference

A non-empty caller record without a defect flag is not corroboration. Detection is not measurement authority.

## Proposed change

Non-defect presence stays `CANDIDATE` with `SOURCE_COLD_ROOM_BOUNDARY_CANDIDATE`. Defects still abstain.

## Benchmark observations that must not influence implementation

Expected freezer areas, room names, and project names are not inputs.
