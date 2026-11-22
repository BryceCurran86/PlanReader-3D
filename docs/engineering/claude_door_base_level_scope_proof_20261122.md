# Door base-level proof (level scope): both adjoining floors on the finished-floor slab

Date: 2026-11-22 (Brisbane). Branch `claude/interior-door-two-wall-tags-20261121` (stacked on GPT1's contract branch, base main `73d710872`). Shadow only: nothing here is wired, issued, sealed or scored.

## 1. Decision and scope

The owner's rule (21 Nov) scores one row per physical door only after the drawings verify the base level separately from the head level. After the compile on the 3Laurel original showed the base was the only axis stopping 12 of 14 doors (width, head level and wall connections verified), the owner approved building the proof from the slab plan and room membership ("Yes, build it", 22 Nov chat). This note records what was built, the rule, what it cannot prove, and the measured result. The rule itself still goes to the authority-promotion review; nothing in this change moves commercial output.

## 2. Observed (drawing and repository, not benchmark)

- A joinery head note ("... AFL U.N.O.") is a level ABOVE the finished floor, so it becomes an opening height only once the base of the door is proven (`pb_document_joinery_head_height_authority`: "must prove the opening base/vertical placement separately").
- Existing base authorities: a schedule row with an explicit rough-opening sill (`pb_opening_vertical_placement_authority`) and an elevation outline whose base sits on FFL (`pb_elevation_door_vertical_witness_shadow`). Interior doors in the measured plan have neither.
- The 3Laurel set carries a slab plan (page 6) with the statement "SERVICE SLAB STEPPED DOWN 100mm FROM FFL" and four "100 STEP" marks, and the floor plan (page 3) carries four "100 STEP DOWN" marks. All four floor-plan marks lie outside every enclosed room ring (alfresco and porch areas); the slab plan shows the same four stepped areas next to the alfresco boxes, the porches and the external service pads, plus 50 mm shower rebates inside wet areas.
- The layered room ring, with the native doorway closures switched on, gives each hinged door a closure that bounds two room rings (6 of the 8 hinged doors on the earlier probe); the cavity sliders get their own closure kind.

## 3. Inference

A statement that level changes are annotated relative to the finished floor makes the ABSENCE of a mark in a room evidence that the room is on the finished-floor slab, provided (a) the marks on the plan and on the level sheet agree in number, (b) the text that says so is corroborated, and (c) no unreadable word sits in the room where a mark could hide. Without a statement the absence means nothing, so the proof abstains.

## 4. Built (new files only)

`pb_door_base_level_scope_shadow.py` and `tests/test_door_base_level_scope_shadow_v1.py` (65 tests). Pure: it takes the doors, the doorway closures, the room regions and the text blocks as plain data. A door's base is proven only when all five links hold; each has its own named gate:

| Link | Gate when it fails |
|---|---|
| The door belongs to exactly ONE closure (by shared native path, never nearest) | `door_has_no_topology_closure`, `door_matches_competing_closures` |
| That closure bounds exactly TWO distinct rooms (so neither side is open space or the outside) | `closure_not_bounded_by_two_distinct_rooms` |
| The document states how level changes are annotated: a block that pairs a level-change word with a floor datum word (policy vocabulary, tested with look-alikes) | `no_level_statement_in_the_document` |
| Every sheet that marks level changes agrees with the plan on how many marks exist | `level_change_marks_do_not_reconcile_across_sheets` |
| No mark on the plan lies inside either adjoining room (a mark on a room's edge counts as inside) | `room_carries_level_change_annotation` |
| The statement and every mark are text-integrity corroborated and no unreadable word lies inside either room | `level_text_not_corroborated` |

A verified door yields the compiler's `BaseWitness` (base 0 above the finished floor, source `level_scope_proof`); any other door yields none, so the base is never assumed. The proof carries every authority flag False.

## 5. Limits (kept explicit)

- The rule is only as complete as the drawing's own annotation: a level change that no sheet marks is invisible to it. The reconciliation against the level sheet narrows that, it does not remove it.
- The word list is policy. It is deliberately broad (a false match only adds an abstention) and it deliberately does not include "RECESSED": in the measured plan "RECESSED TRACK" is a sliding-door track, not a floor level.
- Unreadable text on a level sheet cannot be counted: the reconciliation uses corroborated text only.
- A room's holes are not known to the caller; a mark inside a hole counts as inside the room, which can only add an abstention.
- One plan page per call; doors that open to the outside or to open space are not interior doors and abstain.
- A door with a base that is NOT the finished floor (a stepped room, a raised sill) is not handled: it abstains rather than being given a measured base.

## 6. Benchmark observations that must not influence the implementation

None were used. The reference census and every expected quantity stay out of the rule, the vocabulary and the thresholds; the only numbers in the module are the contract tolerance-free geometry (point in polygon) and counts.

## 7. Measured result (3Laurel Rev3, SHA prefix `014e9f68`, page 3; counts only)

Inputs: the layered room ring with the native doorway closures switched on (the canonical preview path, no repository edit): 27 rings (22 candidate, 5 abstained by the topology itself, so only the 22 are rooms) and 82 closures (8 swing doorways, 6 cavity-slider closures, 3 sliding-leaf, 1 panel-lift, 64 stroke closures). Text of pages 3 and 6 under the opt-in glyph-ledger text trust (2,010 text observations, 1,756 corroborated, 254 abstained). The head note comes from the earlier full compile (corroborated, 2,100 AFL). The numbers were reproduced offline from the persisted topology and text, not from a single end-to-end run.

What the level words look like: 4 level-change marks on the plan, every one outside every room ring (alfresco and porch areas); 4 on the slab sheet (they reconcile 4 to 4); 2 statement blocks on the slab sheet.

| Door outcome (14 interior door marks) | Count |
|---|---|
| Base proven: both adjoining floors on the finished-floor slab (2 hinged, 1 cavity slider) | 3 |
| `closure_not_bounded_by_two_distinct_rooms`: the topology encloses one side only; the other side leaks into open space through an unresolved gap | 8 |
| `door_matches_competing_closures`: the two hinged marks whose jamb records the existing detector shares | 2 |
| `level_text_not_corroborated`: one unverified glyph (a single `+` character, `text_glyph_mapping_unverified`) lies inside one of the door's rooms | 1 |

Compile of the four checks: wall connections 12 of 14, width 14 of 14, head level 14 of 14, base level 3 of 14, so 3 of 14 doors have all four verified and are READY for the existing issuer's review (candidate areas come from the verified axes; nothing is issued). The three rows are the doors whose two adjoining rooms are both enclosed candidate rings in the topology.

Lesson recorded from the first end-to-end run: with a block-level trust rule the proof verified 0 doors, because a word in an unrelated sentence of the slab sheet's text block (`TO`, glyph mapping unverified) un-corroborated a statement whose own lines were fully corroborated. Trust is now judged per word and per printed line, which is what moved the result from 0 to 3.

## 8. What limits the other 11 doors

- Topology (8 doors): rooms are enclosed rings only; a door whose other side opens into space the ring builder could not close has one room, so the proof abstains. The fix is upstream (closing unresolved gaps), not in this proof. The direct ring builder, which merges rooms into 13 larger rings, gives more doors two sides but also larger regions; this proof takes the canonical preview rings.
- Detector receipts (2 doors): the same two marks that fail the wall connection (their jamb records are shared and not at their wall ends) match two closures each.
- Text (1 door): an unverified single glyph inside a room blocks it. A single non-letter glyph cannot spell a level word, but a glyph whose mapping is unverified could be decoded wrongly, so the proof keeps the conservative rule; improving glyph mapping for that character, or a size bound on what an unreadable word could hide, would release it. That is a policy decision, not made here.

