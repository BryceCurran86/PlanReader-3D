# 3Laurel finished face: doorway flank members and the three open source facts (shadow, 2026-11-08)

Assignment (MAX, #4135 comment 6714939597): continue the isolated physical/source case for `internal_strip_thickness_not_the_stated_frame`, `wall_fill_not_classified` and `external_wall_internal_lining_not_stated`. "If the original set cannot establish a needed fact, preserve the precise ABSTAIN and negative regression rather than guessing." Counts, sheet ids and reason codes only: this note quotes no drawing text and gives no drawing measurement.

## 1. Compliance (AGENTS.md / playbook section 1)
- **Read:** `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, `docs/engineering/ACCURACY_LEVERS_AND_AGENT_INSTRUCTIONS_20261016.md`, `docs/engineering/claude_3laurel_finished_face_source_case_20261107.md`, the archived #4242 report, #4135 comments 6714939597 and 6715148959.
- **Traced:** `pb_layered_wall_doorway_room_ring_shadow._collect_strips`, `_attach_caps`, `build_layered_wall_doorway_room_rings` (the edge-owner assignment), `pb_layered_wall_face_identity_shadow.wall_strip_facts`, `_edge_class`, `_classify_edges`, and the sole consumer `pb_live_physical_net_wall_integration._finished_face_receipts`.
- **Authority boundaries crossed:** none raised. The identity record stays `takeoff_eligible=False`, `commercial_projection_allowed=False`, `metric_area_issued=False`, `floor_finish_issued=False`. The page scale remains an input from the existing physical-scale authority; the lining remains an authenticated-statement input.
- **Untouched:** `pb_layered_wall_doorway_room_ring_shadow.py` (so ring record ids are unchanged), `pb_live_physical_net_wall_integration.py`, every scale, length, height and opening authority, the frozen benchmark tree, the signed Lot16 and Maryborough artifacts, W2-W4 (PR-A is merged as #4239; PR-B is deferred).

## 2. Source facts: not stated anywhere in the 18-sheet set
A read-only inventory of all 18 indexed sheets, two independent readers per sheet, skeptic checks on every flagged sheet and a completeness critic (model readers; an inventory cannot establish a fact, it only supports leaving the ABSTAIN in place):

| Fact | Established on any sheet | What the sweep found instead |
|---|---|---|
| F1 room-side lining of an EXTERNAL wall | 0 of 18 | Other-scope statements only (sheets A0.3, A0.13, A0.14). A0.7 defers the external build-up to a notes page / specification that is not in the set (also A0.1). |
| F2 internal door-jamb build-up | 0 of 18 | The one jamb detail (A0.6) belongs to an external door at the slab edge. Internal doors are drawn as swing arcs and clear-opening labels only. |
| F3 meaning of the small filled wall-end shapes | 0 of 18 | No legend, key or hatch convention on any sheet; A0.3 and A0.6 carry labels for posts that do not tie to the plan wall-end fills. |

Skeptic checks on A0.3, A0.6, A0.13 and A0.14 all resolved the flagged reads to "other scope". The critic and the readers also found that the set refers to a specification and a notes page that are not among the 18 sheets, so a fact may exist outside this set. Nothing here is inferred as a default: the wall frame thickness is stated, the external lining and the small flank members are not.

## 3. Observed repository behavior (main `22ebd4e3`)
- `build_layered_wall_doorway_room_rings` assigns an edge's owners at the **edge midpoint** (shapes within twice the noise bound of the midpoint). A ring edge is a union face and can be made of several collinear shapes.
- `_edge_class` classified an edge from those owners only. A thin end cap, or a non-strip block, on the same face as a frame run but away from the midpoint is therefore invisible to it.
- `_attach_caps` makes the ring treat a cap as part of the wall run it ends; the identity classifier did not apply the same rule consistently: a cap at the midpoint made the edge `internal_strip_thickness_not_the_stated_frame`, a cap elsewhere on the same edge did not.

Synthetic demonstration (swing doorway, frame-thickness runs, counts only):

| Scenario | Before (main) | After |
|---|---|---|
| no flank members (control) | resolved | resolved |
| thin cap (two lengths tried) on the upper run's face, away from the midpoint | **resolved** (cap hidden), 5 lined edges | unresolved, 0 lined |
| thin cap at the midpoint | unresolved | unresolved |
| mitred non-strip block at the doorway | unresolved (`wall_fill_not_classified`) | unresolved; the exposed run end face is also no longer lined |
| frame-thickness wall stub (its end face is on the ring) | **resolved**, 9 lined edges including the end face | unresolved (`wall_end_face_not_classified`), 0 lined |
| non-strip block abutting a stub's face | unresolved (through its own fill edges) | unresolved; its collinear side is also no longer lined |
| run drawn as two abutting frame strips | resolved | resolved (no over-abstention) |

So the previous ABSTAIN for the real flank edges held only where the member happened to own an edge of its own; the verdict also depended on where a member sat along the face (a violation of the repository's splitting-invariance rule).

## 4. Inference
A flank member is an unclassified member whatever its position. A lined face may only be claimed when every drawn wall shape lying on the edge is a frame-thickness strip running parallel to the edge and together they cover the edge. The change cannot raise authority: it can only turn a lined edge into an unresolved one.

## 5. What was built (default-off path only)
- `WallStripFact.shapes_pt`: every drawn shape of a path as `(x0, y0, x1, y1, is_strip)` (a path can hold several shapes; the path-level thickness was only the last strip's).
- `pb_layered_wall_face_identity_shadow._verify_lined_edge`, applied only to an edge the owner list calls a lined frame face: the edge must be axis-aligned; every wall-layer shape whose boundary lies on it and overlaps it must be a frame-thickness strip of an internal layer whose long axis is parallel to the edge; the shapes must cover the edge within the representation noise; missing geometry abstains. New classes (all unresolved): `wall_end_face_not_classified`, `wall_edge_extent_not_covered_by_classified_members`, `wall_edge_geometry_not_verifiable`; a mix of classes on one edge is `edge_owned_by_mixed_classes`.
- Reachability: the module is imported only inside `_finished_face_receipts`, behind `layered_finished_face_gate` (default False). With the flag off nothing changes, so the signed Lot16 eight and Maryborough three cannot be reached by this change.

## 6. Tests and validation (local, Windows CPython 3.13)
- `tests/test_layered_wall_face_identity_flank_members_v1.py`: 34 tests. Synthetic positives and the control, look-alike negatives (cap at the end and in the middle, square block, non-strip block, stub end, notch), no over-abstention for a run drawn as abutting frame strips, direction and coverage unit cases, drawing-order, translation and unrelated-content invariance, a multi-shape drawing path, blind geometry abstains, no mutation, deterministic replay.
- Mutation: 21 of 21 mutants killed (first run left one survivor, a member-thickness check, closed by a parallel thin-strip case).
- Related suites (ring, wiring, partition, statement, gate, identity, diag first gate): 225 passed. Ruff F821/F823/F401/F841, compileall and the V2 truth-separation gate pass.

## 7. Result on the original
Run: SHA-authenticated original (`014e9f68...`), plan sheet A0.3, every control on, glyph-ledger trust, RapidOCR, `PYTHONHASHSEED=0`, local Windows CPython 3.13.15. Counts, shares and codes only.

**The guard is not a no-op on the original.** It changes how much edge length is credited as a lined frame face; it changes no verdict, because no real ring resolved before or after.

| Measure | Before | After |
|---|---|---|
| Gated rings (claim path, 700 s): verdict | unresolved x2 | unresolved x2 |
| Gated ring 1: share of wall edge length that is lined | about 97% | about 62% (about 35% now `edge_owned_by_mixed_classes`) |
| Gated ring 2 (the external-wall ring): share lined | about 84% | 0% (about 84% now mixed) |
| Receipt reasons | every earlier reason | every earlier reason plus `edge_owned_by_mixed_classes` on both |
| Candidate rings on the page (ring builder, 8 rings): resolved | 0 | 0 |
| Lined edge length credited over those 8 rings | 100% | about 19% |
| Lined edges that changed class | | 18: 16 `edge_owned_by_mixed_classes`, 2 `wall_end_face_not_classified` |

What the 16 mixed edges contain (members on the edge that the ring's owner list never named):
- **11 edges:** a hairline end cap beyond a frame-thickness run (full wall width across, a fraction of a point along the wall). These carry about 73% of the length that stopped being lined.
- **5 edges:** an unclassified fill, a thin end piece and/or a square end block.

The 2 end-face edges are the end faces of wall pieces (frame thickness wide), which the old classifier counted as lined faces with a lining offset.

Reading: the real flank pieces on the doorway edges (a cap plus a thin piece, which together make the short unresolved edge) are the same kind of member that, at other doorway ends, silently extended a lined edge. The old verdict depended on which piece happened to own the edge midpoint, which is exactly the inconsistency the synthetic scenarios show.

**Decision for MAX, not taken here.** Counting a hairline end cap as part of its run would keep most of the lined credit, but it would also have to absorb the thin end pieces and square blocks (the same strips attach end to end), and the set states nothing about them (F2/F3). So the strict rule stands: it costs only lined-length bookkeeping on rings that were already unresolved, and no tolerance was tuned. Because receipt class lengths and reason codes change when the gate is on, any protected check that pins them needs a look; the statement-hash check does not depend on them.

## 8. Not proven here
- No wet/dry, finish, quantity or customer row is produced; no finished-polygon applier exists.
- The protected original-source replay, dual-Python CI and the Lot16-eight / Maryborough-three retention are MAX's. Local retention is by reachability (flag-off path does not import the changed module), not by a regenerated signed run.
- The fact inventory is a model-read sweep of the 18 sheets, not an authority; the missing specification and notes page may exist outside this set.
- The local run uses RapidOCR; the protected Tesseract environment abstains earlier by design.
