# Item 8: source-owned classification of face ink, and its paint relations (S1 + S2, shadow, no role)

Status: shadow, unwired. Written under `AGENTS.md`. It implements steps S1 and S2 of the framed-window roles report
(`claude_item8_framed_window_roles_report_20261031.md`, section 3) and the owner's 2026-11-02 directive ("continue
source-owned opening-local versus shared-wall-face classification, with all competing layers, frames, stubs and solid
piers retained"). It decides nothing, asserts no role, grants no quantity, and nothing calls it.

## 1. Observed repository behavior (before this change)

- The seeded proof (#4147) lumped every face-collinear line that overlaps a gap into "stub" or "continuing", dropped a
  set-aside structure from view, and could not say what a line is made of.
- A line running ACROSS the aperture (a post, a mullion, a full-thickness pier) has no length along the wall, so
  `_seeded_ink_checks` never saw it. Found while writing the S2 tests; fixed in #4147 (`bc0232fba`).
- The producer's paint knowledge was private to `native_unstroked_fill_evidence`, which only reports opposition.

## 2. Inference (labelled)

- "Opening-local versus shared wall face" is a property of where a line's ends lie relative to the two jamb stations. It
  can be read from the source geometry alone, so the authority that owns the six-line rule is the right owner.
- How a line is painted (path, order, style, opacity) is provenance the PDF holds; relating it to the wall's own lines
  with exact measures, and no threshold, keeps the comparison honest. Whether any relation means "window" or "wall" is a
  separate decision that nothing here makes.

## 3. As built (additive)

- **S1 (#4158)** `SourceVisibilityProducer.native_paint_facts`: authenticated paint facts per native observation: kind,
  paint type, stroke colour, width and opacity, dashes, layer, fill and fill opacity, drawing path, paint order, clip.
  Re-proves the source like `native_unstroked_fill_evidence`. `asserts_role` can only be False.
- **S2a** `PhysicalOpeningAuthority.seeded_face_ink_inventory(selector, members)`: every structure the six-line rule
  finds among the named members, survivor or set aside, none dropped. For each: every non-member line collinear with one
  of its faces that overlaps its gap, with `start_relation` / `end_relation` (beyond, at, within), a rotation- and
  reflection-invariant `extent_class` (at_at, at_within, at_beyond, within_within, beyond_within, beyond_beyond) and a
  `locality` (`opening_local`, `extends_past_one_jamb`, `extends_past_both_jambs` = shared wall face); the lines
  between the faces that are not on a face; and the members another structure also rests on (shared support, i.e. piers
  between neighbouring openings). It reuses the veto's own definitions, so inventory and veto cannot disagree (tested).
- **S2b** `pb_face_ink_paint_relation_shadow`: joins the inventory with the paint facts. Per line, per structure:
  same style as, and same drawing path as, the structure's own face lines; before / after / among their paint order and
  the nearest paint-order distance to a face line and to any nominated strip ink; unstroked fill boundary; transparent or
  partially transparent stroke. A missing fact is reported, not guessed. Atoms are CANDIDATE with unknown polarity; the
  receipt grants nothing; an integrity failure or the default-off adapter abstains.

## 4. Result on the SHA-verified Maryborough original (private, read-only; counts and relations only)

First window, S2 audit in 11 s after the source audit: 2 structures (the outer layer pair, which survives, and the
layer pair that holds the glazing, which is set aside), 2 shared support lines, 81 relations, none unresolved.

- **Outer pair, 4 face lines.** Two unstroked fill-rectangle edges that span the gap exactly (opening-local, painted
  before every face line); ONE stroked wall-style line that spans the gap exactly (opening-local, painted after every
  face line); ONE stroked wall-style line that runs on past both jambs (shared wall face). The two stroked lines are
  now told apart by where they end, which the earlier any-overlap rule could not.
- **Glazing pair, 77 relations.** 38 interior lines in wall style painted after every face line (the nominated strip
  itself: it is wall-style ink, so style cannot mark glazing here); 26 interior unstroked fill edges; 5 thin 0.24 pt
  stubs lying inside the gap and 2 that cross a jamb (all in another style, painted after everything); 4 wall-style
  returns anchored at a jamb (painted before every face line); and 2 unstroked fill edges on the faces.
- Nothing is decided: every atom is CANDIDATE with unknown polarity, and no receipt flag is set.

What this shows for the framed-window question: the structure that is open (the glazing pair) is set aside only
because of 5 thin lines in a different style, painted late, lying on its inner face; the structure that survives is
closed by a stroked wall-style line that spans its gap. Whether those thin lines are frame linework or wall is exactly the
role that is still not authenticated. S2 makes the question answerable from exact measures; it does not answer it.

## 5. Tests

`tests/test_physical_opening_face_ink_inventory_v1.py` (37, written first): every class in five poses, split segments,
set-aside structures kept with shared support named, interior ink apart from face ink, ink beyond the gap ignored,
agreement with the veto inputs, order / repetition / replay / no mutation / no memo use, foreign and unknown members.
`tests/test_face_ink_paint_relation_shadow_v1.py` (13): a real producer and authority, ink drawn in a controlled paint
order, every relation checked against PyMuPDF, five poses, determinism, missing facts, a damaged producer, default off,
import hygiene (nothing imports it; it imports no authority, issuer or binder). `tests/test_native_paint_facts_v1.py`
(23) is S1. 302 tests across the stack pass.

## 6. Standing limits and not proven

- Relations are exact measures, not roles; there is no threshold for "same drawing block", only distances in the PDF's
  own sequence numbers.
- Raster-origin observations have no native paint facts (`()`), so their relations are reported as unavailable.
- One window of one document has been read. Whether any relation separates window-block ink from wall-block ink across
  documents is the S3 population question and is NOT answered here.
- No consumer, no release rule, no quantity. Promotion needs the authority owner's decision.

## 7. Benchmark observations that must not influence implementation

None were used. No expected quantity, tolerance or score was consulted, and no threshold was tuned to the window read.
