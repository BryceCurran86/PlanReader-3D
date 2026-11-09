# Claude: 3Laurel external door heights from the elevations (owner source fact). Architecture report, no code change

Date: 2026-11-09. Base `origin/main` `22ebd4e3c`. Branch `claude/3laurel-door-elevation-vertical-witness-20261109`. **Docs only: no production module, test, benchmark-defining file, identity map, signed fixture, 2.5 pt snap or 20k cap is changed.** Short ids, counts and point coordinates only. No private drawing text, names or addresses are repeated; the general-note wording is paraphrased.

This answers the owner correction relayed by MAX on #4135 (6731095632, 6731112282): the external doors are drawn on the elevations at 2100 high, same as joinery. **My earlier statement that the 18 sheets carry no door-height source was too strong and is withdrawn.**

## 0. Compliance block (AGENTS.md, playbook reread this session)

- **Read:** `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` (full), the MAX handoffs above, `pb_live_physical_opening_void_composition.py` (`_canonical_opening_area`, elevation selector region), `pb_opening_elevation_frame_area_authority.py` (outline), `pb_live_opening_area_quantity_publication._opening_quantity`, and the headers of the legacy `pb_elevation_registration_v135`, `pb_elevation_evidence_v172`, `pb_elevation_calibration_v177`, `pb_elevation_production_bridge_v178`.
- **Traced (original 3Laurel, read in place, no benchmark file read):** native vector geometry of sheets A0.3 (page 3), A0.4 and A0.5 (pages 4 and 5) through `PyMuPDF` drawings for the elevation datum chains and outlines, and `compose_live_wall_opening_authority` + `PhysicalOpeningAuthority.prove_existence` for the plan openings (180 records).
- **Authority boundaries crossed:** none changed. This report reads geometry and calls existing producers read-only.
- **Untouched:** every `pb_*.py`, `tools/`, benchmark truth, both identity maps, signed baselines.

## 1. Observed source facts (counts and coordinates)

| Fact | Observation |
|---|---|
| Elevation sheets | 4 views on 2 sheets (Front, Lhs on A0.4; Rear, Rhs on A0.5). Plan elevation markers make Front = east, Lhs = south, Rear = west, Rhs = north |
| Datum chain | Every view has TP, FCL, **JOINERY** and **FFL** extension lines and three vertical figured dimensions. The JOINERY one reads **2,100** from FFL to the JOINERY line |
| Printed vs drawn | Front: FFL line y 277.57, JOINERY line y 218.0, spacing 59.57 pt = 2,101 mm at 1:100. Lhs: 594.13 and 534.6 = 59.53 pt = 2,100 mm. The printed 2,100 and the drawn geometry agree to 0.1 percent |
| General note | A printed note on both sheets sets a default joinery head height unless noted otherwise. It is **separate** from, and consistent with, the dimensioned datum above. The datum, not the note, is the witness used here |
| Existing authority | `OpeningElevationFrameAreaProducer` binds an opening's own figured frame dimensions via a type mark. These doors carry no frame dimension of their own and no type mark, so it cannot reach them (confirmed by MAX 6731112282) |

### Plan to elevation registration without type marks

An elevation's horizontal axis equals one plan axis at the same 1:100 scale, so each view needs one offset (and a sign). It is fixed by matching widths, not by names:

- **Front (east):** entry-door plan gap 34.02 pt equals the elevation leaf width 34.02 pt; that fixes the offset. The 4,800 garage opening (plan gap 134.31 pt) then predicts an elevation interval **[490.55, 624.87]**; the elevation garage slat block spans **[490.56, 624.86]**. Two independent anchors of different widths agree to 0.01 pt.
- **Lhs (south):** offset +15.5 pt is confirmed by five independent openings (an 870 window, three 1,200 windows, and the two-figure slider), each within 0.8 pt over frames and 0.05 pt on the 870 door below.

### Per-door findings (each physical opening handled separately)

| Plan opening | Gap (mm) | Elevation outline at the registered interval | Head | Base | Result |
|---|---|---|---|---|---|
| `22e7e155` (east wall, printed single width) | 1,200 | Front: leaf [649.98, 684.0], width equals the plan gap exactly | y 218.05, **on the JOINERY line 218.0** (0.05 pt) | leaf bottom 275.31 (80 mm sill), surround to FFL 277.57 | **Height witness provable: 2,100 to FFL** (drawn leaf 2,020 plus 80 mm sill). Competing duplicate record `1cd959cc` (gap 35.7 pt) occupies the same position |
| `be1e67bf` (mid-plan partition, 870) | 870 | none: it is not on any facade; no elevation shows a door at its registered position | n/a | n/a | **Typed negative: no elevation witness** |
| `9d4dc1b3` (laundry to garage partition) | 930 | none: its Front position lies behind the closed garage door; no own outline | n/a | n/a | **Typed negative: no elevation witness** |
| `a93486dc` (870, set back in the south porch; **not** one of the three) | 870 | Lhs: leaf [266.15, 290.82] (24.67 pt) equals plan gap 24.66 pt, within 0.05 pt of the registered interval | y 534.6, on JOINERY | y 594.13, **on FFL** | Provable 2,100 (full FFL to JOINERY, no sill band) |

The 4,800 panel-lift garage door head is also drawn at y 218.05 on the JOINERY line with its slat block ending at FFL (59.52 pt), which agrees with its printed two figures.

## 2. Inference

1. For `22e7e155` a per-door vertical witness exists in the original and is reachable by geometric registration alone. The remaining gates for its quantity are **not** height: it is hostless (`no_authenticated_host_wall_band`), its canonical kind is `None`, and a second record overlaps it.
2. `be1e67bf` and `9d4dc1b3` are not external by the drawing, so the owner's statement does not apply to them; with no outline there is no per-door witness.
3. The physical door that the south elevation actually shows (an 870 door) is `a93486dc`, not either of the two interior 870 ids. If the three single-figure items were intended to be external doors, the identity map may bind a different physical opening than the drawing shows. **This is flagged for MAX; I change no map and use no item name as an input.**
4. "Height" has to be defined before any quantity: the figured datum gives FFL to head = 2,100 for every door above; the drawn leaf of the main entry is 2,020 because a sill band is drawn under it. Which one an opening area takes is an authority-definition decision, not mine.

## 3. Proposed change (shadow, default off, not implemented)

A new diagnostic `elevation_door_vertical_witness_shadow` reusing `EvidenceResolutionStatus` and the existing figured-dimension and scale authorities only as readers:

1. Per elevation view: read the FFL and JOINERY extension lines and the figured dimension between them; require drawn spacing x scale to equal the printed value within 0.5 percent (self-calibration from the figured value, never from the title block alone).
2. Register plan to view with one sign and offset that matches **all** facade openings by width and interval; require a **unique** hypothesis (a margin over every alternative), else abstain.
3. For one plan opening, find the elevation outline at its registered interval whose width equals the plan gap; require head on the JOINERY line and base on FFL (or on a drawn sill band tied to FFL) within a stated tolerance.
4. Output a height **candidate** with every competing record retained; never `CORROBORATED`, never a quantity, never a customer row. Host, frame, kind and promotion gates stay separate and closed.

**Rejected:** a blanket joinery default; matching by item name; matching by nearest elevation outline; a fake type mark; waiving the host gate; owner-approved records as a substitute for the source witness (they remain a separate review-only fallback).

**Proof plan:** synthetic positives; look-alikes (cabinet joinery text, an outline whose head is off the datum, a second elevation with the same widths so registration is ambiguous, a door at a different offset, swapped identities, wrong revision or viewport, no datum chain, an exception height); translation, rotation, scale; order, splitting, unrelated-content and viewport-expansion invariance; replay and stable ids; no mutation; signed Lot16 eight and Maryborough three byte-identical with the diagnostic enabled.

## 3a. Interplay with the owner 2100 external-door policy (#4135 6731245918 and 6731297995, draft PR #4246)

The policy lets an authenticated **external** door use 2,100 mm as an owner-authorised **provisional** assumption only when no specific height is established; a source height overrides it; conflicts, unresolved exceptions or unproven external identity go to manual review; internal doors never use it; it is never FIRM, never source-sealed, never scored. MAX owns the resolver (`pb_external_door_height_estimate_policy`, PR #4246); **I have not edited or read it as authority and will consume it only through its public function.**

Applied to the four openings above, in the policy's own order:

| Opening | Source height | External identity from the drawing | What the policy path gives |
|---|---|---|---|
| `22e7e155` | **Yes** (A0.4 datum, uniquely registered, 2,100) | East wall, on the Front elevation: yes | The **source height overrides**; no assumption is used. Still blocked by host, kind and the overlapping duplicate record `1cd959cc`, which the elevation witness cannot choose between (no nearest, first or smallest) |
| `a93486dc` | **Yes** (A0.4 Lhs datum, exact) | South porch, on the Lhs elevation: yes | Source height; not one of the three items |
| `be1e67bf` | none | **Not proven: mid-plan partition, no facade** | Fallback forbidden for internal doors and for unproven external identity: **manual review** |
| `9d4dc1b3` | none | **Not proven: laundry to garage partition, behind the closed garage door** | Same: **manual review** |

So the policy does not rescue the two ids that the drawing places inside the house. If the owner intends either as an external door, the drawing evidence above contradicts it and the owner should confirm which physical door is meant (for the south entry the drawing points at `a93486dc`). No door is given 2,100 here on the strength of a name.

Even with a height (source or assumed), the policy itself requires authenticated external classification, scope, width, host and frame first. For `22e7e155` the host and kind gates are still closed, so no provisional row can be issued for it yet either.

## 3b. External-door kind gate (MAX 6731504428 action 2: "first authenticate external door kind")

Read-only trace on the original, same composition as above, for the three reported openings, the unmapped south entry and the slider (control):

| Opening | Label authority | Semantic authority | Canonical kind |
|---|---|---|---|
| `22e7e155` | corroborated, one width (1,200) | `ABSTAINED`, `opening_label_semantic_unavailable` | `None` |
| `be1e67bf` | corroborated, one width (870) | same | `None` |
| `9d4dc1b3` | corroborated, one width (870) | same | `None` |
| `a93486dc` (not mapped) | corroborated, one width (870) | same | `None` |
| slider (control) | corroborated, two figures | same | **door**, from its printed opening token in the label |

Why: `pb_opening_kind_authority.resolve_opening_kind` classifies only from a structural door/window pattern or a bound schedule row. The `jamb_bounded_two_face_interruption` pattern carries neither, and these four labels print a width with no opening token. So **there is no kind source today for any single-figure door on this page**, independent of height, host or the policy. Two evidence families could supply one, both new bridges (not built): a plan door-swing symbol bound to the opening, or the elevation leader label that ends on the registered outline (the A0.4 Front and Lhs entry doors each carry one), carried across the plan-to-elevation registration above. Neither is allowed to be a nearest or first guess.

Consequence for the policy path: `be1e67bf` and `9d4dc1b3` stay unclassified, and per the drawing they are not external, so the 2100 assumption cannot apply to them; `22e7e155` needs a proven kind plus host before even a provisional row.

## 4. Benchmark observations that must not influence implementation

None were read. The 2,100 above is the dimension printed on the drawing and re-derived from drawn spacing. No item id, name, tolerance or expected quantity was used.

## 5. Not proven

Kind (door) for `22e7e155` from an elevation leader label (not traced yet); host and frame for it; which of the two competing records is the physical door; that registration stays unique on the other two facades; protected-environment behaviour; any quantity, score or authority. No benchmark item is newly eligible.
