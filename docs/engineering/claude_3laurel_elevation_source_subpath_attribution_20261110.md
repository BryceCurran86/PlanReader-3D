# 3Laurel elevation witness: source-subpath attribution of the #4264 original-source difference (MAX review 5837478802, comment 6760464403)

Scope: shadow-only elevation vertical witness (default off, CANDIDATE only). No host, kind, frame, quantity or customer row, no frozen file and no expected-score input changed. Counts, short ids and statuses only; no coordinates, words or source bytes.

## Observed (same genuine, SHA-verified original, one environment)

| tree | source-owned candidates | diagnostic (PyMuPDF) candidates | `owned == diagnostic` |
|---|---|---|---|
| parent #4256 `4c10ad613` | `22e7e155`, `a93486dc` | `22e7e155`, `a93486dc` | passes |
| fixed #4264 `b179b1ad3` | `836b31c3`, `a93486dc`, `b5091e15` | `22e7e155`, `a93486dc` | fails (MAX reproduced; so did I) |

## Attribution (what actually drew each outline)

1. **The parent's agreement came from a shared defect, not from shared evidence.** Both paths read a filled path as `min/max` over its edges (source-owned) or as PyMuPDF `drawing["rect"]` (diagnostic): the bounding box of the whole path. The original's elevation pages hold compound filled paths (page 4: 27 paths with two to six disjoint loops; page 5: 25). One 22e7e155 outline in the parent carried 74 receipts, 72 of them from two 36-edge, seven-loop paths whose bounding box spanned the whole door.
2. **#4264 correctly stopped inventing those rectangles, but over-corrected on thin strips.** The producer drops native line edges shorter than 0.5 pt (`pb_vector_geometry_v130`), so a filled strip thinner than that (the sill/base bars, vertical edge bars; measured 0.25 to 0.43 pt thick) arrives as its two long sides only. A closed-loop rule rejects it, the 22e7e155 base was lost (`elevation_base_not_on_ffl`), and the diagnostic path (which sees all four sides) kept it: the one remaining disagreement between the paths.
3. **Fix (this change):** `rectangle_components` reads exactly two lone parallel sides of one fill, with the same extent and less than the producer's 0.5 pt floor apart, as that strip, carrying only those two observation ids; three or more such sides in a cluster, a lone side, different extent or fill, and sides 0.5 pt or more apart abstain. The diagnostic path now takes rectangles through the same rule (it no longer uses the path bounding box). Both paths therefore read the same drawn rectangles.
4. **Result on the original, both paths:** `22e7e155`, `836b31c3`, `a93486dc`, `b5091e15` (identical lists, identical heights, leaf heights and datum levels).

## Which candidate is the witnessed physical instance

Per candidate the outline, view, drawing paths and receipts were traced; each outline was also viewed as a rendered crop of the original (local review only, nothing published).

| record | parent | fixed + strips | verdict |
|---|---|---|---|
| `22e7e155` | candidate, 74-receipt outline | candidate, **same outline** (same page, view and extent), 10 receipts: its own two strip sides plus the sides of two closed rectangles | same physical instance; receipts now exactly the drawn sides |
| `a93486dc` | candidate, 148-receipt outline | candidate, **same outline**, 124 receipts | same physical instance |
| `836b31c3` | abstained (`no_elevation_outline_at_registered_interval`) | candidate | a drawn glazed door outline built from thin closed bars; its view did not register before (15 inflated outlines, no unique axis) and now registers on one axis with **two** anchors, weaker than the three to five elsewhere (the pure core's rule is unchanged) |
| `b5091e15` | abstained | candidate | a drawn glazed double-door outline; registers with five anchors on the same view as `a93486dc` |

The crops show an outline of a door or glazed door for all four, not a window, wall or frame fragment. This is a visual confirmation of identity, not a measurement authority: the candidates stay CANDIDATE only and the producer, host and quantity vetoes are untouched.

## Negatives preserved

Compound-path (two rectangles never span their gap), L-shaped and open outlines (no rectangle), ambiguous-leader retention (#4264 kind-proposal tests), and the interior-door and frame-record abstentions (`1cd959cc`, `be1e67bf`, `9d4dc1b3` are still not candidates).

## Tests

`tests/test_elevation_source_owned_rectangle_components_v1.py` (strip rule: pure cases and the real producer's 0.5 pt floor pinned), `tests/test_elevation_diagnostic_rectangle_parity_v1.py` (the two paths agree on synthetic pages; native `re` fills are a strict expected failure), the original-source test updated from the proof above. 22/22 single-line mutants of the strip block are caught.

## Second #4264 review finding: overflowing leader networks (comment 6760871581)

`_network_reaches` (the veto for a label whose routes overflow) tested only segment endpoints against the witnessed outline although its contract is "any point of the connected network". A stroke that crosses the witnessed interior with both ends outside therefore dropped the `LEADER_BRANCHES` veto, and a separate clean DOOR leader could yield CANDIDATE (reproduced with the reviewer's counterexample, both block orders). The check is now a segment-versus-open-interior clip (`_segment_enters`: the same margin as `_inside`, strict at the boundary, an end inside or a crossing counts, touching the margin boundary or only a corner point does not). Unconnected strokes and strokes that only graze remain harmless. 31 of 32 single-line mutants of the helper and its call are caught; the survivor (`a <= b` for `a < b` in the no-interior guard) is equivalent because a zero-width interior leaves an empty parameter interval.

## Not done / separate gaps

- The source-owned adapter reads native `line` facts only; a filled `re` operator arrives as `rect_edge` facts it ignores (none of the 3Laurel elevation pages uses them). Recorded as a strict expected failure, not changed here.
- `836b31c3` rests on a two-anchor registration; promotion would need corroboration the shadow does not have.
- No original-source verification, score or customer output is claimed.
