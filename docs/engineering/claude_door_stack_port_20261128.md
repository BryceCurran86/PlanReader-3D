# Port of the missing door tag and row compiler functions (#4764 7236084226, 2026-11-28)

Donor: draft #4665, head `d6d6aa0fa8` (`claude/door-integration-candidate-20261124`), which consolidated #4638 (GPT1's
two-wall contact contract), #4654, #4655 and #4649.

Ported, unchanged: `pb_opening_two_wall_contact_tags`, `pb_source_door_wall_end_sections`,
`pb_source_internal_door_two_wall_tags`, `pb_door_row_evidence_compiler_shadow`, `pb_door_base_level_scope_shadow`, their
synthetic tests and the three design notes (307 tests pass here).

Overlap audit: no function or class is defined twice except the local input types `TextWord` (also in
`pb_plan_opening_detection_v171`) and `RoomRegion` (also in `pb_structural_room_region_shadow`), which are separate
private shapes, not shared evidence vocabulary. No job names. Nothing imports the ported modules from a live path.

Deliberately not ported (separate decisions): the ring-builder wiring that computes tags inside
`pb_layered_wall_doorway_room_ring_shadow` (it changes a module the preview calls), the AGENTS.md all-pages rule text and
its owner-rule document (an engineering-contract change), the ring differential test with its goldens, and the test
that needs the original at its repository path.
