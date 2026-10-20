# Cursor — fail-closed open-passage obstruction and doorway-threshold flags

**2026-10-20 • Shadow implementation of the approved slice of [PR #3455](https://github.com/BryceCurran86/PlanReader-3D/pull/3455).**

This is not a FIRM finish or ceiling issuance PR.

## Observed (repository)

- `pb_source_open_passage_connection_shadow._segment_intersects_passage` only treats collinear overlap as obstruction.
- `pb_source_floor_finish_occurrence_ownership_shadow.evaluate_source_floor_finish_ownership_shadow` sets `doorway_transition_authenticated` from `bool(doorway_transitions)` and hardcodes `terminates_at_internal_faces` / `under_wall_finish_excluded` True.

## Inference

Caller-created `SourcePassageWallEdge` / `SourceDoorwayThreshold` objects are not W4 wall or door authority. Sealed room-area m² is not a tiling quantity.

## Proposed (this PR)

- Detect interior crossing obstruction as well as collinear overlap. Jamb endpoint contact is not obstruction. Any obstructing wall candidate abstains.
- Doorway authentication requires polygon-edge alignment, matching page, a published room-face record id, two distinct jamb wall ids, and a source stroke id. Otherwise the flags stay False. Misaligned or foreign-page thresholds abstain.
- Keep `commercial_projection_allowed=False` and `takeoff_eligible=False`.

## Benchmark observations that must not influence implementation

Do not use Office 9.05352 m², Food Prep 13.270425 m², FT2/FT3 mark counts, IPF1 counts, frozen V2 scores, or title-block scale as algorithm inputs.
