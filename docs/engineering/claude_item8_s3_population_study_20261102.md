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

---

## Part B. RESULTS (the Part A rules were applied unchanged)

Pre-registration commit: `f2ab6fe2d`, pushed to #4160 before any result below existed. The census ran afterwards on the
code at `f97bc3515`'s content (S1, S2a, S2b), read-only, on the four local originals. No coordinates or drawing content
appear here.

### B1. What was processed
- 72 pages: Lot16 13, 3Laurel 18, Q5446 standard plans 10, Maryborough 31. Every page was attempted, smallest first, with a
  25-minute budget per page declared before the run.
- 70 pages complete. Two are partial because of the budget: Q5446 p1 (91 of 173 structures) and Q5446 p4 (52 of 75), taken in
  candidate-id order, which is a hash order that does not depend on content. No page was dropped or chosen because of what it
  shows. No page failed. The 0 anomalies mean every structure was reproduced from its own members.
- 29,473 structures: 3Laurel 7,570; Lot16 503; Maryborough 20,604; Q5446 796.

### B2. The three registered relations
| relation | 3Laurel | Lot16 | Maryborough | Q5446 |
|---|---|---|---|---|
| R-A, interior ink entirely outside the face-line paint range (items; share true) | 5,040; 26.8% | 283; 71.7% | 13,141; 35.2% | 745; 50.2% |
| R-B, face ink decisively nearer one paint block (items; decisive; dominant side) | 21,091; 56.4%; interior | 195; 76.9%; wall | 35,688; 65.9%; interior | 2,397; 70.2%; interior |
| R-C, face ink has the wall's style (items; same style) | 28,871; 64.1% | 297; 100% | 53,674; 91.1% | 2,453; 76.1% |

All four documents qualify (at least 20 items) for every relation.

### B3. Verdict by the registered rules (A4)
- **R-A: NOT a clean separator.** No document reaches 90% (26.8% to 71.7%); the spread is 45 points.
- **R-B: NOT a clean separator.** Decisive assignment is 56.4% to 76.9%, below 90%, and the dominant side differs between
  documents (Lot16 is nearer the wall; the other three are nearer the interior ink).
- **R-C: NOT a clean separator.** Same style holds in 64.1% to 100%; only Lot16 and Maryborough reach 90%.
- **Rule 4 therefore applies: no exact paint relation separates the blocks across these documents, and the framed-window
  question stays ABSTAIN on this evidence.** Nothing here supports S4 (releasing a veto), and it is not an accuracy gain.

### B4. Descriptive only (not a decision): face ink by locality and style
| document | opening_local same / other | past one jamb same / other | past both jambs same / other |
|---|---|---|---|
| 3Laurel | 13,638 / 3,660 | 2,885 / 2,841 | 1,992 / 3,855 |
| Lot16 | 295 / 0 | 2 / 0 | 0 / 0 |
| Maryborough | 29,726 / 2,124 | 14,352 / 1,351 | 4,823 / 1,298 |
| Q5446 | 786 / 293 | 538 / 274 | 542 / 20 |

Opening-local face ink is mostly in the wall's own style in every document (73% to 100%), so style does not mark it as
something other than wall. Shared wall-face ink (past both jambs) is in another style in a large share of 3Laurel (66%) and a
small share elsewhere. The classification of locality (S2a) is robust and source-owned; what the lines ARE is not told by
paint.

### B5. What this does and does not show
- It shows that, across about 29 thousand structures in four documents, the exact paint relations tested are not a stable
  signal of "window block versus wall block". Direction and strength change from document to document.
- It does NOT refute that, in one drawing, a nominated strip is its own contiguous block (the Maryborough readout in the
  S2 note is true of that strip). The unit here was every six-line structure, including rooms, furniture and other things
  that are not openings; no label was used, by design. A labelled subset (structures whose interior ink is nominated by an
  independent identity) would be a different study with a much smaller population and needs the owner's labels.
- R-A is strict (every interior line must sit outside the face-line range), and dense pages with interleaved fills lower it;
  that is a property of the registered measure, which was not changed after seeing results.

### B6. What would still be worth doing (for the authority owner; not started)
1. Accept the frame-linework ambiguity as permanent ABSTAIN for the six-line rule, as the evidence stands.
2. If more provenance is wanted, look beyond paint: form-XObject boundaries, marked content and optional-content layers
   (the `layer` field is empty on the Maryborough plan page), which S1 could expose without asserting a role. This is a new
   measurement, not a conclusion from this one.
3. A labelled-subset study over structures with an independent identity (callout, schedule, elevation, whole aperture)
   if the owner can supply or approve the labels.
