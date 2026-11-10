# Candidate 3 trace: tag, leader and schedule ownership for openings (2026-11-02)

**Status.** Decided 2026-11-02: candidate 3 closed as no-code (section 8). Architecture report, per `AGENTS.md` ("First deliverable on a new change"). No code, test, workflow, threshold or truth change. It grants no authority and is not an input to any producer. This is the trace that candidate 3 of `claude_accuracy_gate_census_report_20261102.md` said it needed before any code. Only counts and public module names appear; no expected quantity, item id or private drawing content was used.

**Result in one line.** The proposed "joint tag, leader and schedule ownership graph" already exists twice (one legacy shadow, one production authority). Building a third would break the "no second canonical graph" rule, and on the two originals I can measure it is not the first failing gate. Recommendation: close candidate 3 as no-code and move to the gate that is measured in my lane (section 5).

## 1. Files read and functions traced

`AGENTS.md`; `docs/AI_ENGINEERING_PLAYBOOK.md` section 13 (priority 4); `pb_opening_provenance_graph.py` (all); `pb_hosted_opening_geometry.resolve_hosted_opening_spans` and `pb_hosted_opening_wall_binding.bind_hosted_opening_to_walls` (docstrings and call sites); `pb_schedule_opening_instance_binding_authority.py` (`publish_scope`, `_opening_aperture_for_physical_opening`, `_aperture_contains_bbox`); `pb_opening_tag_normalization.py`; `pb_g17_original_plan_tag_census_shadow.py` and `tools/diag_gptmax_original_plan_tag_source.py`; `pb_opening_label_leader_witness_shadow.py`; `pb_opening_kind_authority.py` (docstring); `pb_source_plan_glazing_strip_callout_shadow.py` (docstring); the extractor call site `pb_planreader_pdf_extractor.py:3497`.

Authority boundaries crossed by the traced path: `PhysicalOpeningAuthority` existence (G17) -> `SourceVisibilityProducer` text integrity -> `ScheduleOpeningInstanceBindingProducer` -> `pb_opening_kind_authority`. Nothing in the path publishes a measurement; height and area stay with their own authorities.

## 2. Observed repository behaviour

| Seam | What it is | Wired? |
|---|---|---|
| `pb_opening_provenance_graph` (826 lines) | Shadow graph: nodes `physical_hosted_span`, plan tags, schedule rows, size callouts; edges `contained_tag`, `direct_leader`, `schedule_type_match`, `dimension_bound_to_tag`; statuses RESOLVED / AMBIGUOUS / CONFLICT / UNBOUND. | Only as `opening_provenance_shadow` on the extractor (`pb_planreader_pdf_extractor.py:3497`), wrapped in `try/except`, never mutates predictions. |
| `pb_schedule_opening_instance_binding_authority` v2.3.0 | Producer-owned, sealed. Needs a CORROBORATED physical opening, complete source coverage, a jamb-bounded aperture, one trusted tag whose centre is inside that aperture (native and OCR duplicates collapsed at 0.75 overlap), and exactly one schedule row for that mark. Distinct reason codes for each failure (`no_contained_tag`, `ambiguous_tags`, `no_matching_row`, `ambiguous_rows`, ...). Does not publish height. | Yes, via `ScheduleOpeningInstanceBindingProducer.publish_scope`; `pb_opening_kind_authority` consumes the bound row for trade type. |
| `pb_g17_original_plan_tag_census_shadow` | Diagnostic census of trusted tags against authenticated apertures; every grant flag is False, including `actual_source_leader_topology_proven`. Run by the MAX workflow `test-gptmax-original-plan-tag-first-gate.yml`. | Shadow, owned by MAX. |
| `pb_opening_label_leader_witness_shadow` (68 lines) | Takes already-chosen ids as strings and returns flags. No geometry. | Shadow stub. |
| `pb_source_plan_glazing_strip_callout_shadow` (mine) | Ring-enclosed callout with no leader -> glazing strip candidates; everything stays candidate. | Shadow. |

Defects and limits in the legacy graph (read from source, not run):
- Its physical nodes come from the legacy hatch/fill-gap `hosted_opening_shadow`, not from `PhysicalOpeningAuthority`. Nodes carry page and viewport but no document id, revision, `source_sha256` or snapshot, so the ownership rule in `AGENTS.md` ("preserve document, source hash, revision") is not met.
- `collect_opening_provenance_shadow_for_doc` harvests plan tags and size callouts only. Its docstring says schedule rows are not inferred, and it passes no leaders. So `schedule_type_match` and `direct_leader` edges cannot occur in the wired path; they exist only in unit tests.
- Containment uses `local_opening_bbox`: an axis-aligned box around the jamb segment widened by half the wall thickness. A tag must sit inside the wall band, and the box is not rotation-invariant for a diagonal wall. A tag printed beside the opening, the common case, falls outside it and is not contained.
- A size callout inside the box is recorded as `dimension_bound_to_tag` although no tag is involved (naming only).

Tag grammar: `normalize_opening_tag` accepts only `W`/`WIN`/`WINDOW`/`D`/`DR`/`DOOR` plus one to three digits. A compact size callout is not a tag.

Measurement (SHA-verified Lot16 original, page 3, `main` `782b4e3ef`, `tools/diag_gptmax_original_plan_tag_source.py`, run locally, counts only):

| Quantity | Count |
|---|---:|
| physical openings | 21 |
| openings with authentic aperture geometry | 21 |
| trusted source tag candidates (native + OCR) | 0 |
| tags outside all apertures | 0 |
| signed customer rows, before vs after the census | 8, unchanged |
| document text observations that were not usable (no trusted text or no usable box) | 2,080 |

The last row matters: zero trusted tags does not prove zero printed tags, only that none survived text integrity. The 2,080 are counted over the whole document, not page 3, so I cannot say how many of them sit on this page. Maryborough was measured on 2026-10-31 and re-measured today with the callout-to-strip census: its window marks are hexagon callouts with no leader, and its first failing gate is the missing whole-aperture candidate, not tag ownership. 3Laurel and Q5446 were not measured here.

## 3. Inference (not observed)

- Playbook priority 4 is already realised in two places. A new joint graph would be a third structure and would break "do not introduce a second ... canonical graph". The right move is to use the production authority, not to add a layer.
- On the two originals I can measure, tag or schedule ownership moves no quantity: Lot16 has no trusted tags (its second axis comes from size labels, and 13 of 13 unsigned openings fail that pair test), and Maryborough is blocked at the aperture. The value of this work sits on drawings that print tags beside openings and carry a schedule, which I cannot measure from the originals available here.
- The one real gap is **leader-owned tags**: a tag outside the aperture joined by a leader. No leader topology is proven anywhere (`actual_source_leader_topology_proven=False`). Leaders are drawn like dimension lines and hatch, so a leader detector without typed negative evidence (playbook priority 3) would fabricate ownership. That ordering is the reason not to start there.

## 4. Proposed change

**Nothing new for candidate 3.** Close it as no-code. Two small follow-ups, both optional and neither started:
1. Mark the legacy `pb_opening_provenance_graph` as superseded in its docstring (comment only), so no later agent builds on its dead edges. It is a shadow module, so this needs no authority review, but it should wait for a PR that already touches the file.
2. If a tag-bearing original with a schedule becomes available, run the existing tag census on it first; only a measured non-zero "tags outside all apertures" count would justify designing leader evidence, and that design would start from typed negative evidence, not from the graph.

## 5. What I recommend doing next instead

The first failing gate that is measured and sits in my lane is the Maryborough strip-to-whole-aperture step: both candidate strips produce fragments only, none spans the whole extent (layered faces for one, stepped returns for the other). That is a geometric hypothesis, so it needs the full test matrix (synthetic positives, look-alike negatives, ambiguity, translation/rotation/scale, order and splitting invariance, no-mutation, shadow-only). It would start with its own trace and stop for review, like this one. Candidates 5 and 6 stay MAX-owned.

## 6. Benchmark observations that must not influence implementation

None were read. The Lot16 counts come from producer receipts, read after the producer ran. No item id, expected quantity, tolerance or identity map was used, and none of the numbers above is a threshold or an input.

## 7. Untouched

Every `.py` file, test, workflow, benchmark and truth file, and all committed signed outputs. Local-only untracked outputs (the census JSON, which contains observation ids) are not committed.

## 8. Owner decision (2026-11-02)

The owner answered "Yes, both": candidate 3 is **closed as no-code**, and the Maryborough strip-to-whole-aperture trace is the next primary task in this lane. That trace is a separate report; this PR carries no further work.
