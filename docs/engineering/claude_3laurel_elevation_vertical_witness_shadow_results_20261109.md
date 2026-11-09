# Claude: elevation vertical witness SHADOW (diagnostic only, default off). Results

Date: 2026-11-09. Base `22ebd4e3c`. Implements decision (C) of MAX 6731795141 (already approved by the owner). Short ids, counts and point coordinates only.

## What changed

New files only: `pb_elevation_door_vertical_witness_shadow.py`, `tests/test_elevation_door_vertical_witness_shadow_v1.py`, `tools/diag_elevation_door_vertical_witness_shadow.py`. **No existing production module, benchmark-defining file, identity map, signed fixture, 2.5 pt snap or 20k cap is edited.** No production module imports the shadow (a test enforces it). It writes no kind, host, frame, quantity or customer field.

## Rule (diagnostic evidence, never authority)

1. **Datum calibration.** The view's FFL and head levels are joined by figured vertical dimensions. Drawn spacing times one common scale must reproduce every printed value within 0.5 percent, or the view abstains. The title-block scale is never used.
2. **Registration.** One (sign, offset) must explain at least two elevation outlines of different widths and strictly more than every other hypothesis (equal widths in points also prove one shared scale). Symmetric or single-anchor scenes abstain; ambiguity is a conflict.
3. **Witness.** The outline at the registered interval (width and both edges) must have its head on exactly one datum level and its base on FFL (leaf base or an enclosing frame base). Two plan records that match the same outline are both held (no winner). A stated competing height conflicts.
4. **Height definition (MAX 6731795141 B).** `opening_height_mm` is the printed datum value (FFL to head). The drawn leaf height is a separate field with its own provenance and is never substituted. A positive is `CANDIDATE`, never `CORROBORATED`; kind, host and frame gates stay closed.

## Measured (3Laurel original, read in place; plan page 3, elevation pages 4 and 5)

| Measure | Result |
|---|---|
| Elevation views with a figured datum chain | 4 (Front, Lhs, Rear, Rhs) |
| Views with one unique plan registration | 3 (Front offset 984.286 pt, sign -1; Lhs offset 15.496 pt, sign +1; Rhs registered) |
| Not registered / not usable | Rear: no unique registration. Rhs: its chain picked up a window dimension that does not self-calibrate, so every record there abstains on the datum |
| Candidates | **2**: `22e7e155` (opening 2,100 mm, leaf 2,020 mm) and `a93486dc` (opening 2,100 mm, leaf 2,105 mm because that door has no sill band) |
| Nested frame record `1cd959cc` | `ABSTAINED`, `elevation_head_not_on_datum`: its outline is the door frame, head 0.85 pt above the datum. Held, not merged into `22e7e155` |
| Interior doors `be1e67bf`, `9d4dc1b3` | no elevation outline at their registered intervals |
| First gate per plan record, aggregated across views (one row per record) | no outline 164, competing outlines 5, head not on datum 6, base not on FFL 3 (windows), candidate 2 |

Registration found the same offsets as my manual measurement (Front 984.285, Lhs 15.5), independently, from widths alone.

## Proof

68 source-neutral tests: positives; sign x scale x translation metamorphic; input order, unrelated content and viewport expansion; replay and stable ids; no mutation; duplicate physical candidate (both held), nested frame record, interior doorway, wrong elevation, single anchor, symmetric (ambiguous) scene, foreign or stale scope (four fields), competing explicit height, two outlines at one interval, head off datum, base off FFL, non-calibrating datum, leaf-vs-opening confusion; extractor on a synthetic drawing (nested frame and leaf, contaminated chain, no chain); default-off strict-bool; no production importer; no project or id special case. One original-source test (skipped without the private PDF). Thirteen single-line mutations of the rule (including leaf height used as opening height, and every check added after review) were each caught; two survivors found along the way were closed with new tests.


## Review fixes (MAX 6732228656, head `c9e76a8f2`)

1. **Non-finite values fail closed.** `calibrate_datum` rejects NaN, infinity, booleans, strings, zero or negative spacing and values, and an overflowing ratio whose mean is infinite (inf/inf is NaN and would otherwise slip past the tolerance). Plan spans and outlines are validated (finite, `a0 < a1`, `x0 < x1`, head above base, finite positive explicit height) before any selection, and abstain with `elevation_witness_input_invalid`.
2. **No silent pick on a duplicate identity.** A repeated `record_id` or `outline_id` (even with different geometry) is a `CONFLICT` (`elevation_witness_duplicate_identity`); the old `next(...)` is gone and input order cannot choose.
3. **Cross-view uniqueness gate.** `assess_elevation_vertical_witness_shadow` now returns ONE result per record through `aggregate_across_views`. Two views that both witness a record, or a candidate plus a record-level conflict elsewhere, are a `CONFLICT` (`competing_elevation_views`). A view that cannot calibrate or register says nothing about the record and does not poison a clean candidate. The diagnostic tool uses the same gate, so its candidate list cannot be cherry-picked.
4. **Production note (accepted, not built).** The PyMuPDF extraction remains a diagnostic. A production slice must source-authenticate exact revision, snapshot, page and viewport native witness observations, a unique registered physical instance, door semantic kind and host binding, and must not select the nested frame record or the two interior openings.

## Not proven / limits

The extractor reads vector fills and words with PyMuPDF; it is a diagnostic, not yet a source-authenticated observation path. The kind (door) gate for `22e7e155` and `a93486dc` is still `None` (no elevation leader label is bound), their host and frame gates are unchanged, and no quantity is issued. No score, no benchmark item newly eligible. Protected-environment behaviour and Lot16-eight / Maryborough-three retention at this head are not run here (no production code changed).
