# Architecture: structural wall resolve must not mint CORROBORATED from presence

## Observed repository behavior

`SourceStructuralWallSystemShadowAuthority.resolve` sets `EvidenceResolutionStatus.CORROBORATED` whenever records exist and no defect reason is present. The module docstring already requires shadow `CANDIDATE`.

## Inference

A non-empty caller list without a defect flag is not corroboration. Detection is not measurement authority.

## Proposed change

Non-defect presence stays `CANDIDATE` with `SOURCE_STRUCTURAL_WALL_SYSTEM_CANDIDATE`. Defects still abstain. No commercial or FIRM change.

## Benchmark observations that must not influence implementation

Expected wall lengths and project names are not inputs.
