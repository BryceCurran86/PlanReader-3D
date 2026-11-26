# Rooms recovered from a drawing area name their walls in the page-keyed canonical map (default off)

Date: 2026-11-26. Order: owner directive on issue #4764 (comment 7172590477, item 5); evidence #4764 7171556273; claim #4764 7184050672. Owner approved the design ("Yes, build it").

## 1. Observed repository behaviour

- `compose_live_canonical_walls` keys canonical walls from the whole-page wall scope (`wall-source:page-N`); `candidate_to_canonical_wall_id` uses that scope's candidate IDs.
- When the page-wide room scope abstains, `compose_live_canonical_rooms` takes rooms from the authenticated drawing-area (viewport) wall scope. Candidate IDs hash the scope ID, so none of those rooms' wall IDs are in the page map and `canonical_bounding_wall_ids` is empty.
- Each wall candidate also carries a scope-independent signature: its traced path (`PhysicalWallIdentity.path_fingerprint`) and exact source primitive IDs (`source_primitive_ids`).
- On the Maryborough floor-plan page (counts only): 3,447 of 3,467 drawing-area walls have exactly one page twin under that signature, both ways; the other 20 bound no room; all 832 walls its 683 rooms use match. A weaker rule (every source fragment contained in one page wall) links only 607 rooms, because the two scopes split lines differently.
- No quantity, seal, row, room ID or floor ID includes the wall links.

## 2. Inference

Two candidates with the same path and the same source primitives are the same wall by construction, whichever scope traced it. That is an explicit shared-primitive mapping: no proximity, no string rewriting, no tie-break.

## 3. Change

- `_viewport_to_page_wall_candidate_ids(page_scope, viewport_scope)`: drawing-area candidate ID to page candidate ID only when both scopes are corroborated and agree on document, revision, source hash and page, both identities are usable and own their candidate, the signature has source lines, and it is unique in both scopes. Anything else is left out.
- `compose_live_canonical_rooms(viewport_wall_identity_links=False)`: in the viewport fallback only, linked walls are looked up through their page candidate. An unresolved page wall stays unresolved (`wall_relationships_complete` stays False). The links the mapped rooms used are recorded on `LiveCanonicalRoomComposition.viewport_wall_identity_links`.
- `collect_live_physical_net_wall_claim(viewport_wall_identity_links=False)` passes the switch through. GPT MAX's draft #4646 edits the same module; this adds only the pass-through keyword.
- Untouched: wall composition, page-scope rooms, quantities, seals, authority, floor finishes, W10, the frozen benchmark.

## 4. What it does not do

- It restores references only. `wall_relationships_complete` stays False while the page walls are unresolved candidates. A floor-finish quantity over these rooms would still be refused (the walls have no finished-face role).
- It is off by default; the app and the source-closed tools do not pass it.

## 5. Verification

Synthetic: `tests/test_viewport_wall_identity_links_v1.py` (link rule, ambiguity and look-alikes, order, the real fallback fixture, receipt, pass-through, switch off identical, page-scope rooms untouched); 12 single-line mutants all fail a test. Tests touching the changed modules, with originals: 2,043 passed, 15 skipped, 2 failed; both failures are the Maryborough Office FT3 original-source tests, which fail the same way on `main` and on `main` from before 26 November's merges.

Original drawing (counts and digests only; live claim, floor-plan page with its support page): switch off is identical to `main` in every field. Switch on: all 683 rooms name canonical walls (0 before), every named wall is in the claim, no room is marked complete, and rooms, floors, walls, openings, every quantity family, the 3 published floor areas and the room-area, floor-area and floor-finish seals are unchanged.

## 6. Benchmark observations that must not influence the implementation

The page, view and counts above are observations used to verify only. No page number, view ID, count or project name enters code.
