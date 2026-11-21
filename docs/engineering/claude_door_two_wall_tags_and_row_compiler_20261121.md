# Door two-wall tags (every wall convention) and the door row evidence compiler

Date: 2026-11-21 (Brisbane). Base: GPT1's draft contract branch `gpt1/universal-two-wall-opening-tags-20261121` (head `277cc42ba`, on `origin/main` `73d710872`). Branch `claude/interior-door-two-wall-tags-20261121`. Shadow only: nothing here is wired, issued, sealed or scored.

## 1. What the owner asked for (chat, 21 Nov)

1. Finish the adapter to GPT1's two-wall rule: after tracing, tag each door with the two wall sections that bound it, including at an intersection, and check that it works with filled wall strips and outlined walls.
2. Score one row per physical door once the drawings verify both wall connections, the width, the head level and the base level; use the joinery head note (`AFL U.N.O.`) where it applies and verify the base separately.
3. Prove the same rule on the original 3Laurel and Maryborough plans, using Maryborough pages 24 to 27 alongside the floor plan.

## 2. What was built (new files only; no existing module is edited)

| File | Role |
|---|---|
| `pb_source_door_wall_end_sections.py` | Core. Builds the inputs of GPT1's contract (`pb_opening_two_wall_contact_tags`) from native path rows of any convention: a wall end is a GROUP of paths (a filled strip, two stroked face lines, one hairline, a cavity pocket drawn as two lips). The contact is anchored on the opening's own edge (a jamb return, or a proved door interval), never on the wall. Ends may face each other (straight gap) or sit on perpendicular axes (corner, junction, angled opening). |
| `pb_source_internal_door_two_wall_tags.py` | Front end for the strict internal door inventory: every hinged and cavity-slider mark appears once, tagged or with a named reason. |
| `pb_door_row_evidence_compiler_shadow.py` | Composition of the four verifications into one candidate row per physical door. Evidence only; `READY_FOR_EXISTING_ISSUER` is input for the authority-promotion review, not an issuance. |

Rules kept: nothing is elected by proximity, rank or order; the contract owns the vocabulary and the endpoint rule and is consumed, not forked; every authority flag is False by construction; public summaries are counts only.

Compiler rules: only text-integrity-corroborated witnesses verify; witnesses that disagree conflict and none is chosen; a door-specific head (schedule row, elevation outline on a datum) beats the document U.N.O. note, which applies only when the door has no door-specific head, and a door-specific head whose text is not corroborated blocks the note rather than falling back to it; the base is never assumed (a head level above the finished floor is not an opening height until the base is proven); the opening height is head minus base and must be positive; every view of one door (plan, inset, elevation, schedule) enriches ONE row.

## 3. Evidence of correctness

- Core: 111 tests (solid strips, outlined walls as two face lines, with an end cap, as hairlines, cavity pockets; straight gaps; perpendicular corners; coincident junctions; the face of a passing wall; ends facing the same way; offset walls; a wall running through the other contact; every tolerance boundary; translation, rotation, mirroring, scaling, unrelated rows, replay, no mutation). Front end: 29 tests. Compiler: 40 tests.
- Mutation: core and front end 83 of 84 single-line mutants caught (the survivor is equivalent within the contract tolerance: the parallel gate bounds a face line's two endpoints to the same tolerance the comparison uses); compiler 46 of 46.
- Contract tests of the base branch (GPT1) still pass with these files present (156 tests together at the first check). The repository guards (private source, truth separation, canonical route, provider isolation) and `ruff --select F821,F823` pass locally.

## 4. Measured on the original plans (counts only)

**3Laurel Rev3, SHA prefix `014e9f68`, page 3 (index 2), filled wall strips.**

| Step | Result |
|---|---|
| Internal door marks (strict inventory) | 14 (8 hinged, 6 cavity slider) |
| Two wall sections tagged (straight gap) | 12 of 14 (6 hinged, 6 cavity slider) |
| Not tagged | 2 hinged marks, `opening_edge_does_not_meet_wall_end`: the jamb rows the existing detector recorded for these two marks do not sit at their wall ends (one jamb row is claimed by both marks). A finding about that detector's receipts, not a drawing fact |
| Printed width tokens owned by a mark | 14 of 14 |
| Width tokens corroborated by text integrity (default trust) | 0 of 14: all 1,989 native text observations on pages 3 to 5 are `abstained` under default trust |
| Document joinery head note (existing authority) | `document_joinery_head_height_unavailable` under default trust, for the same reason |
| Base level witness | none exists in the drawings for these doors |
| Rows ready for the issuer | 0 of 14; first open gates: `width_text_not_corroborated` (12), `wall_connections_not_tagged` (2) |

Why the canonical chain still cannot host these doors (measured with the live composition, earlier the same day): the 29 canonical opening records inside the 14 apertures all fail the same first gate, `opening_two_face_wall_lineage_unmapped`; only 8 of the 29 carry the doorway's own geometry (one per hinged door, none for the six sliders); in the local wall scope the wall candidates are mostly `ambiguous` and the left-role candidate is missing for 7 of 8. The wall-side defect is in the wall producer (short filled stubs at the doorway are dropped and chains are blocked at junctions), not in the door.

Evidence the drawings DO hold for the base level and head level (read, not yet usable by an authority): the elevations (pages 4 and 5) carry the note "JOINERY HEIGHTS TO BE 2100 AFL U.N.O." and a datum chain FFL, 2,100, 2,700 (FCL); the slab plan (page 6) states "SERVICE SLAB STEPPED DOWN 100mm FROM FFL" with four "100 STEP" labels, and the floor plan (page 3) carries four "100 STEP DOWN" notes. The count reconciles (4 and 4). A base proof for an interior door would be: both adjoining floors are on the finished-floor-level slab, i.e. neither is one of those stepped areas. That needs room membership of each door's two sides, which this change does not provide.

**Maryborough, SHA prefix `b1be5353`, outlined walls.** Pages 24 to 27 (A500 to A503) are enlarged amenity plan insets with elevations, 90 degree rotated sheets, no layer names, walls drawn as thin stroked line pairs and heavy single lines.
- A500 (page 24) is above the 20,000-primitive cap and the layered ring abstains (needs a bounded viewport). A501 to A503 (pages 25 to 27) run.
- The core, fed exact-contact receipts built from the ring's doorway closures: 5 swing doorways found, 4 tagged (`STRAIGHT_GAP`) from outlined walls; the fifth ends at the face of a perpendicular wall and has no wall end there (the intersection case below). Of 11 wall-end stroke closures (not doors) 1 was tagged and 10 stay unresolved with a named reason, as they should.
- No self-calibrating elevation datum view is found on A500 to A503 by the existing elevation witness (0 views on each page), so that authority cannot verify head or base there today. Maryborough has no joinery head note: the floor plan carries "ALL DOORWAYS TO HAVE A MINIMUM UNOBSTRUCTED HEIGHT OF 2.0m (UNLESS OTHERWISE NOTED)", which is a minimum, not a head level, and the door schedule (A600, page 28) carries per-door width and height. The head must therefore come from the schedule row (door specific), which the compiler ranks above any note.
- Not done for Maryborough: the floor plan A110 (page 7, 109,354 paths) was not run; door code to symbol registration across the insets, the plan and the schedule is not implemented here; so no Maryborough door has been compiled to a row.

## 5. Intersections

Perpendicular wall ends (a corner doorway) and ends that meet at one point (a junction) are tagged by the core as `ANGLED_OPENING` and `WALL_JUNCTION` and tested synthetically for solid strips. A doorway that ends at the FACE of a passing wall (a T junction: no wall section ends there) is not tagged: the core reports it (`wall_end_group_is_far_thicker_than_the_opening_edge_a_wall_face_not_an_end`, or no wall end at that edge) because the contract needs a real wall endpoint at each contact, and fabricating one would be an invented wall. Where the wall tracer splits the passing wall at the junction, both resulting sections end at the contact and the contract retains them as competing; that is the expected result, not a failure. This is the one geometry class left for the wall producer lane.

## 6. What is needed before a door row can be scored

1. Text trust: widths and the head note are corroborated only under the opt-in glyph-ledger text trust on these originals; that option is default off.
2. A base-level proof for interior doors. Existing authorities offer: an elevation outline on a datum (not available for interior doors), a schedule row with an explicit sill (none), and nothing else. Candidate: the level-scope proof described in section 4. It is a new authority and needs the owner's approval of the rule, because absence of a step annotation is not by itself proof.
3. Wall side: the two tagged sections must be recognised by the canonical host binding. Today the host binding wants a band from the wall producer; the owner's two-wall rule needs the host binding to accept two traced sections instead of one elected host. That is a change to the host authority (MAX's lane) and to the wall producer (Cursor's lane).
4. Issuer, seal and customer row through the existing opening-area issuer with a new area basis, then the documented authority-promotion review (AGENTS.md). Nothing in this change moves commercial output, so no score changes.
