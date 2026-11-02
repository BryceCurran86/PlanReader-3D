# Item 8, S3: do exact paint relations separate window-block ink from wall-block ink? Population study

## Part A. PRE-REGISTRATION (committed before any census was run)

Status: written under `AGENTS.md` before the S3 census existed or ran. The decision rules below are fixed here and are NOT to be
changed after seeing results. They are STUDY criteria for judging a measurement; they are not production thresholds and must
not become one. No expected quantity, benchmark item, tolerance or score is an input.

### A1. Question
The roles report (section 3, S3) asked whether any exact paint relation holds across documents and separates the ink that
lies inside an alleged opening from the wall's own ink, so that the question "is face-collinear ink inside a gap wall or
window frame linework?" could ever be answered from the source. Today the answer is ABSTAIN. S3 asks whether the evidence
could change that.

### A2. Unit and population (label-free)
- Unit: a jamb-bounded structure found by the existing six-line rule on a native vector page, with its own six or more lines
  as the named members. No label (window, door, wall) is used: none is available without expected values.
- Population: EVERY structure on EVERY native page that is processed, in each of the four local originals (Maryborough,
  Lot16 plans, 3Laurel, Q5446 standard plans). Raster pages are excluded because they have no native paint facts. Every
  page that is processed is reported with its structure count; a page that is not processed (time) is listed with the
  reason. No page is chosen or dropped because of what it shows.
- Per structure: the S2a inventory (face ink with `locality`, interior ink, shared support) joined with the S2b paint
  relations (S1 facts), with the structure's own interior ink passed as the "strip" so its paint-order distance is
  measured.

### A3. Relations under test (all exact, none with an algorithm threshold)
- **R-A (interior ink is its own paint block).** For structures with at least one interior line: every interior line is
  painted outside the paint-order range of the structure's own face lines (`before_all` or `after_all`).
- **R-B (face ink falls into one of two blocks).** For face-collinear lines in structures that have at least one interior
  line: `d_I` = nearest paint-order (sequence number) distance to the structure's interior ink, `d_M` = nearest distance to
  its own face lines. A line is "decisively assigned" when one distance is at most a tenth of the other; otherwise it is
  "undecided". Direction: nearer_interior / nearer_wall.
- **R-C (style).** Face-collinear line has the same style (kind, stroke colour, width, opacity, dashes, layer) as at least
  one of the structure's own face lines, or not.

### A4. Decision rules
1. A document is **qualifying** for a relation only if it has at least 20 qualifying items for that relation (so the
   statistic is not noise). If fewer than two documents qualify, S3 is **inconclusive for that relation**, which is NOT
   evidence that the relation holds; the question stays ABSTAIN.
2. A relation is a **clean separator** only if, in EVERY qualifying document, at least 90% of its items take the SAME value
   (R-A: true) or are decisively assigned (R-B), AND the dominant direction is the same in every qualifying document, AND
   the per-document figures differ by no more than 15 percentage points.
3. Invariance under translation, rotation, reflection and scale is by construction (the relations use paint order and
   style, not coordinates) and is verified by the metamorphic tests in the S2 test files; S3 does not re-run it.
4. If no relation is a clean separator, the answer is: **no exact paint relation separates the blocks across these
   documents, and the framed-window question stays ABSTAIN permanently** on this evidence.
5. Even a clean separator would establish only that TWO PAINT BLOCKS EXIST consistently. It would NOT establish that the
   block of interior ink is a window symbol or that the block of wall lines is wall: that meaning is an inference that
   needs an independent identity (callout, schedule, elevation, whole-aperture reading) and the authority owner's
   decision (S4). S3 cannot release a veto, issue a record or change any quantity.

### A5. Reporting
Counts only (structures, items, categories, fractions) per page, per document and in total; no coordinates, no content from
the drawings, no file names beyond the document's project label. Every document and page processed is listed.
