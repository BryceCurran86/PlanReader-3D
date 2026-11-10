# Door-swing figure binding (shadow only): a printed width inside the swing drawing belongs to that door

Status: shadow-only, default off, candidate-only, nothing imports it from production. 2026-11-10. Lane: Claude, 3Laurel source-to-customer. Owner rule (2026-11-10): "if the measurement is inside the door swinging drawing then it is for the door".

## Compliance (AGENTS.md)

- **Read:** `AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` (sections 5, 11, 12, 13); `pb_plan_door_swing_geometry.py`, `pb_gpt2_native_door_swing_source_shadow.py`, `pb_source_visibility_authority.py` (`native_paint_facts`), `pb_opening_label_dimension_authority.py` (`publish_scope`, read only, not edited), the opening geometry used by `pb_opening_host_binding_authority._opening_geometry`.
- **Authority boundaries crossed:** none. The result is a `CANDIDATE` binding that a reviewer compares with the label authority's own choice. It writes no width, kind, host, frame, quantity, seal or customer value and is never `CORROBORATED`.
- **Untouched:** every file in playbook section 11, `pb_opening_label_dimension_authority.py`, `pb_plan_door_swing_geometry.py` (a live-extractor helper), the frozen 120, the Lot16 signed eight, the Maryborough signed three, the 2.5 pt snap, the 20k cap.

## Observed repository behavior

- `pb_plan_door_swing_geometry` only counts quarter-circle cubics to emit a sole unlabeled D1; `pb_gpt2_native_door_swing_source_shadow` verifies caller-supplied leaf, swing and jamb path ids. Neither returns a hinge, radius or arc midpoint, so neither can bind a figure to a door.
- The visibility producer exposes straight native segments only: on 3Laurel page 3 all 9,679 native paint facts are `line`, and none lies on the Front entry's arc. Door-swing arcs are native cubic Bezier drawings, so they cannot come from visibility observations.
- The opening label authority already binds one printed word to each opening and does not expose why that word belongs to the door.

## Inference

A door swing is a quarter circle hinged at one end of the opening with a leaf as long as the opening. A printed figure that lies wholly inside that quarter disc is printed on the door it describes. That is checkable from geometry alone, independently of the label authority, and without reading the figure's value.

## What was built

- `pb_door_swing_figure_binding_shadow.py` (pure core): a swing is a quarter arc with a square bounding box; its **hinge** is the corner one radius from both arc ends **and from the arc midpoint** (the opposite corner is not), lying within the opening's **own wall thickness** of one opening end; the radius equals the opening length within that thickness; an opening whose thickness is not smaller than its length abstains (the tolerance would accept any arc). A figure is inside only if all four corners of its box lie in the quarter disc; some corners is a boundary straddler. Exactly one hinged swing per opening (a swing painted twice is one swing), exactly one figure-like word inside it, no straddler, and that figure inside no other hinged swing; otherwise abstain with a named reason. The figure's value, the opening's width and any benchmark value never decide the binding.
- `pb_door_swing_figure_binding_adapter.py`: quarter-circle arcs from the native cubic drawings of the SHA-pinned page (opaque, dark, stroke-only; true quarter circles only; ids are native path ids, **not** visibility observation ids), figure-like words from the text-integrity receipts with a trust tag (every figure-like receipt counts, whatever its trust, so an untrusted figure can still veto), opening end points from the live composition.
- `tools/diag_door_swing_figure_binding_shadow.py`: counts-only, compares each candidate with the word the label authority bound.

## Original 3Laurel, page 3 (read in place, SHA verified, default producer so words are raw)

| Count | Value |
|---|---|
| Native quarter-circle arcs (includes window-corner fillets and tiny arcs) | 620 |
| Figure-like words | 228 (all `raw_unverified` under the default producer) |
| Plan opening records | 180 |
| `CANDIDATE` bindings | **10 records on 5 distinct swings and 5 distinct figures** (Front entry `22e7e155` and its nested frame `1cd959cc`: `1,200`; the Lhs door `a93486dc` and 7 more records: `870`) |
| Label authority bound the same word | **10 of 10** (0 different, 0 without a word) |
| Abstained: figure straddles the swing boundary | 3 (three records at three different doors; the label box crosses the closed-leaf line by about 2.4 pt, less than the 2.55 pt wall thickness) |
| Abstained: no swing hinged with leaf length equal to the opening | 115 |
| Abstained: opening wall thickness not less than its length | 52 |

The Front entry's swing has radius 34.0 pt equal to the opening length, is hinged at the opening's top end, and holds exactly one figure, the `1,200`; the binding therefore corroborates which word belongs to the door. Its remaining gap is the rotated-word glyph recovery (separate change), not the binding.

**Two defects found while building, not hidden.** My first probe took the wrong corner as the hinge (the opposite corner also satisfies the equal-distance test) and the wrong quadrant for containment, which produced a false extra figure; the core now requires the arc midpoint to be one radius from the hinge and tests the arc's own quarter disc. A degenerate opening record with thickness 98 pt and length 0.28 pt matched 80 tiny arcs; records whose thickness is not smaller than their length now abstain.

## Not proven / limits

- The three straddling records stay abstained: whether wall-thickness slack at the closed-leaf line is acceptable is a review decision, not made here.
- Only page 3 of one original was read; sliders, the garage door and double-leaf doors have no hinged full-radius swing and abstain by design.
- Arcs are native drawing paths of the pinned PDF, not producer observations; text trust here is raw because the default producer is used.
- This corroborates the binding only. It does not authenticate the width text (the Front entry's rotated `1,200` is still untrusted), the door kind, the host or any quantity. No score, no newly eligible item.

## Proof

60 source-neutral tests (positives, look-alike negatives such as window-corner fillets, double-leaf and opposite-corner arcs, ambiguity, translation / rotation / mirror / scale metamorphic, input order, unrelated content, deterministic replay, no mutation, non-finite and duplicate input, stubbed text-trust tagging, a synthetic PDF through the real ingest) and 33 single-line mutations of the core and adapter rules, all caught (a first run left five survivors; each closed with a test). Truth-separation gate passes. No original-source test is committed: the original run above is a local read-only measurement, not a protected-runner result.

