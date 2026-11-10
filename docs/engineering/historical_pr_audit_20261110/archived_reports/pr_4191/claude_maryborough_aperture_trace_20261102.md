# Maryborough strip-to-whole-aperture trace (2026-11-02)

**Status.** Architecture report for review, per `AGENTS.md` ("First deliverable on a new change"). No code, test, workflow, threshold or truth change. It grants no authority and is not an input to any producer. This is the "next primary task" the owner chose after `claude_opening_ownership_trace_20261102.md` closed candidate 3. Only counts and public module names appear; no expected quantity, item id or private drawing content was used.

**Result in one line.** On the Maryborough original, nothing in the source file can authenticate which lines at a framed window's faces are glazing and which are wall: not paint (the S3 study, merged), and not structure (new today: no marked content, layers, forms or tag tree on the plan and elevation pages). The existing path abstains for that reason and is right to. I recommend accepting permanent ABSTAIN for Maryborough framed windows and building nothing toward it.

## 1. Files read and functions traced

`AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` section 13; `claude_item8_s3_population_study_20261102.md` (B5, B6); `claude_item8_framed_window_roles_report_20261031.md`; `pb_source_plan_glazing_strip_callout_shadow.py` (`_ring_for_word`, `audit_plan_callout_to_glazing_strip_from_source`); `pb_strip_structural_assessment_shadow.py` (docstring and output fields); `pb_callout_strip_whole_aperture_correspondence_shadow.py` (docstring); `pb_structural_whole_opening_aperture_authority.py` and `pb_structural_through_wall_aperture_host_authority.py` (docstrings; AntiGravity/MAX modules, not edited); `pb_physical_opening_authority.py` (seeded path, commit list); `SourceVisibilityProducer.native_paint_facts` (carries `layer`); `tools/diag_plan_callout_strip_census.py`.

Authority boundaries crossed by the traced path: callout ring -> glazing strip (shadow) -> `PhysicalOpeningAuthority` existence (six-line rule, seeded path default-off) -> whole-opening aperture authority -> host hypotheses. No step publishes a measurement.

## 2. Observed repository behaviour

Run locally on the SHA-verified Maryborough original, plan page 7 and elevation page 29, `main` `782b4e3ef`, with the existing census tool and the strip structural assessment (needs `fontTools` on the path, or the native glyph chain abstains silently).

| Quantity | Count |
|---|---:|
| plan callouts matching the mark pattern | 34 (28 door marks, 6 window marks) |
| glazing strips | 6 (panel counts 1, 1, 3, 3, 3, 7) |
| window marks CANDIDATE | 2 |
| window marks CONFLICT (16 other callout claimants on the strip) | 1 |
| window marks ABSTAINED (`elevation_type_record_missing`) | 3 |
| door marks ABSTAINED (`callout_ring_not_found`) | 28 |

The 28 door rows are not a failure: the ring finder models hexagonal callouts only (`_ring_for_word(..., sides=6)`; other shapes are "for exclusion ONLY"), and this shadow answers a glazing-strip question.

For the two CANDIDATE strips, the existing physical-opening stack sees:

| | Strip A | Strip B |
|---|---:|---:|
| fragments | 11 | 16 |
| corroborated fragments | 2 | 3 |
| contested fragments | 9 | 13 |
| fragments spanning the whole strip extent | 0 | 0 |

Reason codes on both: `ambiguous_physical_opening_candidates`, `strip_fragments_only_no_whole_extent_candidate`, `original_terminal_paint_structural_role_unproven`. The corroborated fragments are single-pane gaps inside a multi-pane strip, so reading them as openings would count one window several times. That is why the path fails closed.

Seeded path (the #4147 content now on `main` through #4148, default off): both strips ABSTAIN, because ink on the opening faces has no producer-authenticated role and stepped-return terminals have no pattern (`claude_item8_framed_window_roles_report_20261031.md`).

Paint evidence (merged S3 study, 29,473 six-line structures over 72 pages of the four originals): no exact paint relation separates window-block from wall-block ink, and the direction changes between documents.

**New today, non-paint structure** (`B6` item 2 of the S3 note, counts only, all pages of each file):

| Original | Pages | Optional-content layers | Pages with marked content | Tag tree |
|---|---:|---:|---:|---|
| Maryborough, architectural set | 31 | 0 | 0 | none |
| Lot16, architectural plan set | 13 | 0 | 0 | none |
| Lot16, structural set | 11 | 42 | 11 | none |
| 3Laurel plan set | 18 | 37 | 15 | none |
| Q5446 (six files) | 1 to 10 each | 0 in every file | 8 pages, in two files (not examined) | present in the same two files |

On the Maryborough plan page the content stream has no `BDC`, `BMC` or `EMC` operator, no `/Properties` reference and no declared XObject (one stray `Do` token matched with nothing declared; not relied on). The elevation page is the same. The `layer` field that S1 exposes is therefore empty for every Maryborough path.

3Laurel is the one architectural original with usable layers: on pages 2 to 15, 95 to 99 percent of paths sit in a named layer, with 7 to 19 layers per page. Its 37 layer names are opaque to a generic vocabulary: 0 contain a window-like or door-like token, 4 contain a wall-like token, 33 contain none. The token list is a counting convenience for this measurement only; it is not a role rule and nothing reads it.

**Tags inside Maryborough apertures: the existing tool cannot answer.** The tag first-gate tool (`tools/diag_gptmax_original_plan_tag_source.py`) runs the full live wall and opening composition twice to prove nothing changes; on Maryborough plan page 7 it took 54 minutes. Result: 330 physical openings pass existence with authentic aperture geometry (a count that includes non-window structures; I did not classify them), 0 customer rows, signed output unchanged, and **0 trusted tag candidates with 29,455 document text observations unusable**. The zero is not evidence of no tags. Observed: that tool builds its `SourceVisibilityProducer` without `source_native_finish_text_shadow`, the opt-in the strip census passes. Inference: that is why the text it sees is largely untrusted, since text trust on this drawing was 0 before that opt-in (#3859). A fair tag measurement here needs the opt-in, which is MAX's tool; I did not change it or re-run it.

## 3. Inference (not observed)

- The remaining gate is **role authentication of the face linework**. For Maryborough both source routes that could supply it are empty: paint is not a stable separator (S3) and there is no structure to read. Any rule that nonetheless picks an "outer pair", a "thin red set" or a "nearest pair" would be choosing, which `AGENTS.md` forbids ("never resolve ties with nearest, first, or smallest").
- The existing path is correct, not merely cautious. Its fragments are real single-pane gaps; the whole strip is not provable as one opening from this file.
- Even the cross-view route has an upstream gate: both CANDIDATE strips carry `elevation_viewport_unproven` and `elevation_mark_also_printed_outside_type_frame`, so the elevation type record is not yet owned by an authenticated viewport. Fixing that moves the dimension side of the chain, not the opening-identity side.
- A layer relation is the only untested non-paint signal in the four originals, but it exists in two documents, not in the target one, and one or two documents cannot establish a rule under the S3 stability criterion. It could not help Maryborough at all.

## 4. Options (owner's call)

| | Option | Moves Maryborough? | Cost and risk |
|---|---|---|---|
| A | Accept permanent ABSTAIN for Maryborough framed windows | no | none; recorded as a known source limit |
| B | Owner-labelled study: the owner marks window and non-window among a pre-registered sample of six-line structures; study only, results never become thresholds | only if a separator exists, which two measures say it may not | needs the owner's time and labels; must live in its own PR apart from production code |
| C | Label-free layer-relation study on 3Laurel and the Lot16 structural set, pre-registered like S3 | no | informational; two documents |
| D | A new existence proposition from callout, strip and elevation record without plan jambs | possibly | a second existence authority and a new vocabulary; I recommend against it |

## 5. Recommendation

**Option A.** Record the limit and stop building toward a Maryborough framed-window aperture. The measured gates that can still move an item sit elsewhere: the Lot16 host and frame gates (MAX), kind and axes (GPT1), and the owner's door-height decision, which is closed as "keep abstaining". If the owner wants the question tested with ground truth instead of closed, Option B is the honest way. I will not start B or C without a go-ahead.

## 6. Benchmark observations that must not influence implementation

None were read. Every number above comes from producer receipts or from structure counts of the source file, read after the producers ran. No item id, expected quantity, tolerance or identity map was used. Layer names were never printed.

## 7. Untouched

Every `.py` file, test, workflow, benchmark and truth file, and all committed signed outputs. Local-only outputs (the census JSON files, which hold observation ids) are not committed.

## 8. Stop for review

Ask: accept Option A for Maryborough framed windows, or run Option B with owner labels?
