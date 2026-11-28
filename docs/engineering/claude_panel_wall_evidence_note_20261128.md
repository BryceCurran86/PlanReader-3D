# Typed white-panel wall evidence (report only, CL-R04, MAX 7236084226)

## Observed
Some wall runs on one original plan sheet are drawn as opaque white strips between two lines of one ink, so the
finish-face support check sees only a report-only `panel_candidate` there. White rectangles of the same shape also
come from masks, boxes painted twice, table rows and cells.

## Rule (`pb_panel_wall_evidence_shadow.typed_panel_walls`)
A distinct white rectangle of wall thickness (1.2 to 14 pt, at least three times as long) with both long sides drawn
by one ink is one record. It is CANDIDATE only when, at both short ends, the strip (or a straight run it continues
into) meets wall paint at a right angle or a dark wall bar, contains no text, and no white rectangle of the same
length sits against a long side. Otherwise ABSTAINED with `contains_text`, `stacked_cells`, `one_end_open` or
`isolated_strip`. Records keep the sha, page, fill and face-line path indices. `viewport_id` is None: nothing yet
separates a plan from an elevation, so a plan viewport binding is required before any use. `counts_as_support` and
`wall_authority` are always False; no live path imports the module.

## Synthetic proof
19 tests: a panel room (plain, shifted, reversed), isolated and duplicated boxes, an open corner, text, table rows, a
row of cells, one face only, short and thick shapes, a run split in line and a gapped run, near-repeated boxes, dark
bars closing ends, source paths, inputs, determinism. All 17 single-line mutants are caught.

## Original sheet (local, counts only)
Maryborough plan sheet: 138 strips; 15 candidate, 88 isolated, 15 with text (door-style tags), 12 stacked,
8 one end open. No strip lies on the Office, Food Prep or Sales cells; on the cold-room outline 2 candidates,
10 tagged pieces and 1 isolated. The Lot16 and 3Laurel plan sheets have none.

## Not claimed
No wall, quantity or room change. Walls whose ends meet only line-drawn walls abstain.
