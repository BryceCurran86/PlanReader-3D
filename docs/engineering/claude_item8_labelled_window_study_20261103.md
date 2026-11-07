# Item 8, Study B: do owner-identified framed windows have a consistent paint signature? Labelled study

## Part A. PRE-REGISTRATION (committed before any label or result exists)

Status: written under `AGENTS.md` before the viewer, the analysis or any owner label exists. The decision rules below are fixed
here and are NOT to be changed after seeing results. They are STUDY criteria for judging a measurement; they are not production
thresholds and must not become one. No expected quantity, benchmark item, tolerance or score is an input. This is Option B of
`claude_maryborough_aperture_trace_20261102.md` and the "labelled subset" named in section B5 and B6 item 3 of
`claude_item8_s3_population_study_20261102.md`. The owner chose to run it on 2026-11-03.

### A1. Question
S3 found that no exact paint relation separates window-block ink from wall-block ink across every six-line structure in four
originals, but its population was everything (rooms, furniture, walls) and used no label. The remaining question is narrower:
**among structures the owner identifies as framed windows, do the same three exact relations hold uniformly?** If they do in
two or more documents, a window's interior ink and its wall ink would form two consistent paint blocks. If not, the framed-window
role question stays ABSTAIN permanently on this evidence.

### A2. Labels: owner-supplied, positives only
- The owner designates the plan page of each document before labelling: the plan page the existing tag and strip census tools
  already use (Maryborough page 7, Lot16 page 3). Further documents (3Laurel, Q5446) enter only if the owner supplies labels for
  them. A page is never added or dropped because of what it shows.
- A local viewer shows the page. For each framed window the owner clicks it. The viewer lists **every** six-line structure whose
  extent contains the click, in candidate-id order, and draws all of them. The owner picks the one outline that is that window's
  frame, or "no outline fits". The viewer applies no tie-break: no nearest, first or smallest choice is made for the owner.
- The label file holds only: document label, page, the picked candidate id (or "no outline fits"), and a hash of the page render.
  Nothing else the owner marked is used.
- An unmarked structure is NOT a negative. The owner may miss windows, and doors, rooms and furniture are unmarked on purpose.
  Unmarked structures never enter a decision; they appear only in descriptive counts.
- Doors are out of scope (swing arcs are a different evidence class). Only windows are labelled.

### A3. Relations under test (exactly S3's, unchanged)
Definitions R-A, R-B and R-C are those of S3 section A3, computed by the same code path on the labelled structures only:
- **R-A:** every interior line is painted outside the paint-order range of the structure's own face lines (structures with at
  least one interior line).
- **R-B:** for face-collinear lines in structures with at least one interior line, a line is "decisively assigned" when its nearest
  paint-order distance to one block is at most a tenth of the other; the direction is nearer_interior / nearer_wall.
- **R-C:** a face-collinear line has the same style as at least one of the structure's own face lines.

### A4. Decision rules
1. A document is **qualifying** for a relation only if it has at least 20 items for that relation, exactly as S3 counted them
   (R-A: structures with interior ink; R-B and R-C: face lines), AND those items come from at least 5 distinct labelled
   structures, so that many lines from one or two windows are never taken for a population. If fewer than two documents
   qualify, the study is **inconclusive as a rule** for that relation. A single-document figure is reported as a
   document-local observation: it cannot become a rule, and the question stays ABSTAIN. (A paint convention in one drawing is
   not evidence about the next.) The 5-structure floor is a study criterion fixed here before any label exists; it is
   not a production threshold.
2. A relation is a **clean separator for labelled windows** only if, in EVERY qualifying document, at least 90% of its items take
   the SAME value (R-A: true) or are decisively assigned (R-B), AND the dominant direction is the same in every qualifying
   document, AND the per-document figures differ by no more than 15 percentage points.
3. If no relation is a clean separator, the answer is: **paint does not authenticate window ink even among known windows, and the
   framed-window question stays ABSTAIN permanently** on this evidence. Nothing is built toward it.
4. Even a clean separator would establish only that two paint blocks exist consistently among owner-identified windows. It would
   NOT establish that a block is glazing, nor release any veto: that needs an independent identity for each opening and the
   authority owner's decision (S4). The study cannot issue a record, change a quantity or set a threshold.

### A5. Reported regardless of outcome (counts only)
- Windows marked per document; marks for which the owner picked "no outline fits"; marks with no containing structure at all; marks
  with more than one containing structure; structures picked twice (counted once).
- Per relation and document: items, share, direction, qualifying or not.
- A per-document note that "no outline fits" is itself a finding about the six-line rule, not a defect of the labels.

### A6. Privacy and separation
- The page render, the structure geometry, the viewer and the label file contain the owner's private drawings. They are written
  only to the ignored local artifact folder, are never committed, and are never uploaded to CI, a public PR or a hosted page. The
  viewer is a single local file the owner opens in a browser.
- This PR adds diagnostic tools under `tools/item8_b/`, a protocol document and synthetic tests. No production module, test of
  production behaviour, workflow, threshold, benchmark or truth file changes. The results note will carry counts only: no
  coordinates, ids, file names beyond the document label, or drawing content.

### A7. Honest scope and cost
- Owner effort: one click per window on two plan pages, then one choice per window. The sample is small by nature: the
  Maryborough plan carries six window callouts (counted by the callout census) and the Lot16 plan a similarly small number. R-A counts one item per structure,
  so with so few windows R-A cannot reach the 20-item bar in either document; R-B and R-C count face lines and can. That is
  recorded here, not engineered around.
- Even a clean separator from this few windows per document is a lead for a larger, separately pre-registered study (more
  documents, more windows), never a rule and never a production input. Only the opposite result is conclusive: if paint
  does not separate the blocks even among the few owner-identified windows, the question is closed ABSTAIN.
- If only one document is labelled, rule A4.1 makes the result inconclusive by construction; the owner should decide before
  labelling whether a second document is worth it.
- The study can only close the question, or show a consistent signature worth a separate proposal. It cannot move any item on its
  own.

### A8. Procedure (so the run is repeatable)
1. `python tools/item8_b/b_enumerate.py <label> <pdf> <page> <out_dir>` builds the local viewer and the structure file.
2. The owner opens the viewer in a browser, marks every framed window on the page, and downloads the label file.
3. `python tools/item8_b/b_analyse.py <label> <pdf> <page> <labels> <structures> <out>` checks the labels against a fresh
   enumeration (refuses on any difference) and writes counts and id-free per-structure rows.
4. `python tools/item8_b/b_aggregate.py <out> [<out> ...]` applies A4 and prints the verdicts.

### A9. Instrument note (2026-11-05, before any result was read)
The first viewer drew only each outline's bounding box. The owner reported that it "makes boxes and doesn't register the lines
inside of them": with four to nine overlapping boxes per click, the box alone does not show which one holds the window's own
lines. The viewer now also draws each listed outline's member lines in that outline's colour over a faded page, keeps the
dashed box as the extent, and shows only the hovered outline's lines on hover. This changes what the owner can see, not what is
recorded: the label file, the structure fingerprint (ids only), the relations and the decision rules are untouched, and the lines
never enter any decision. Nothing about the Maryborough labels made with the first viewer had been analysed beyond file validation
(counts of marks only); the owner may redo or confirm them with the lines viewer, and only the final label files are used.

---

## Part B. RESULTS

Not yet run. Part A is committed first; results follow only after the owner supplies labels.

Enumeration counts (no labels involved): Maryborough plan page 7 has 1,345 six-line structures; Lot16 plan page 3 has 181. The
viewer reproduced both from the SHA-verified originals, and the structure extents were checked against the page render by eye
on both pages (including the rotated Maryborough page). Most of these structures are furniture, fittings, dimension chains and
text boxes, not openings; that is why the study asks the owner to point at windows instead of sampling structures.
