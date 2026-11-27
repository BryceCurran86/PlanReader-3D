# Angled openings are never found: precision design (task C14, 2026-11-27)

Architecture note before any change (AGENTS). Not built yet; prioritised by MAX 7215518648 after C05/C06.

## Observed (synthetic, `main` + #4810)
The same jamb-bounded two-face opening is found and hosted at 0/90/180/270°, at scales 0.25-4, mirrored and with a split face
line, and never at 15/30/45/60/89.5/135°. The face-break predicates require relative parallelism `1e-9` and a collinear offset
`<= 1e-6 pt` (`_PARALLEL_REL_TOL`, `_COORD_EQ_ABS_TOL`). Parsed coordinates are float32: for angled collinear lines the offset
is about `1.4e-5 pt` at 500 pt, so `_parallel` and `_collinear` fail. Axis-aligned lines share exact coordinates and pass.

## Inference
This is representation precision, not geometry: equality should allow a few float32 ulps at the coordinate magnitude.

## Proposed (opt-in, default off)
- A page tolerance `max(1e-6, 4 * 2**-23 * max|coordinate|)` (about `2.4e-4 pt` at 500 pt; far below drawing precision).
- Use it in `_parallel` (`|cross| <= tol * (len_a + len_b)`), `_collinear`, `_face_break` gap positivity, `_same_gap`,
  the break-index bins and `_candidate_collinear_record_pairs` bins of `_visible_structural_candidates`, then the host
  binding `_opening_geometry`. A source producer constructor option, like the existing raster shadow options.
- Tests: the rotation set; translate/scale/mirror; near-parallel negatives (walls 0.1° apart must stay distinct; two faces
  offset by `0.01 pt` stay separate); hatching at 45° must not mint openings; input order and segment splitting.

## Risk and measurement
Angled hatching becomes comparable for the first time, so originals must be measured before/after (opening candidates,
corroborated openings and hosts) before any default change. No claim of impact on a current drawing.
