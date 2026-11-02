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
1. A document is **qualifying** for a relation only if it has at least 20 labelled windows contributing at least one applicable
   item (R-A/R-B: structure with interior ink; R-C: structure with face ink). If fewer than two documents qualify, the study is
   **inconclusive as a rule** for that relation. A single-document figure is reported as a document-local observation: it cannot
   become a rule, and the question stays ABSTAIN. (A paint convention in one drawing is not evidence about the next.)
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
- Owner effort: one click per window on two plan pages, then one choice per window. If only one document is labelled, rule A4.1
  makes the result inconclusive by construction; the owner should decide before labelling whether a second document is worth it.
- The study can only close the question, or show a consistent signature worth a separate proposal. It cannot move any item on its
  own.

---

## Part B. RESULTS

Not yet run. Part A is committed first; results follow only after the owner supplies labels.
