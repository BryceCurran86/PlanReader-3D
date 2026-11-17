# GPT2 — Maryborough cross-sheet finish correspondence: malformed source receipts

**Scope:** Source-shadow guard only; no measured floor, ceiling, door, score or customer-output claim. **Coordination:** #4135; GPT MAX owns current Maryborough producer/customer integration. Original architectural PDF expected SHA-256: `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, 31 pages, physical floor p7, RCP p9, finish plan A140 p11. A matching historic manifest is not a current original-source replay.

## Observed repository behaviour

- Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md` and existing GPT2 source-authority reviews; traced `pb_source_cross_view_floor_correspondence_shadow.SourceCrossViewFloorCorrespondenceProducer.evaluate_synthetic` -> `box_correspondence` -> `classify_floor` -> source-only `SourceCrossViewFloorCorrespondenceRecord`.
- `classify_floor` indexed `correspondence["wall_bounded_on_both_sheets"]` and `correspondence["wall_evidence_identical_on_both_sheets"]` directly. A missing or malformed provenance receipt therefore could raise `KeyError`/`TypeError` instead of a typed abstention. An explicitly supplied malformed `other_labelled_boxes_overlapping` value could also be coerced through truthiness, discarding its source-receipt type. The optional absent hint remains a typed zero **only because** the producer independently sweeps all measured boxes for actual overlap.
- Even a valid source registration returns **CANDIDATE only**; `authenticated_physical_wall_face_equivalence=False`. This is not enough for the room, metric, finish, issuer, sealed customer or scorer gates.

## Inference and correction

A caller with a partial wall/overlap receipt must never be permitted to imply a unique physically bounded finish region, nor crash a batch in place of an auditable abstention. Validate both wall receipts via literal `is True`, and require an exact nonnegative, nonboolean integer overlap count; only an omitted optional hint uses the producer's computed geometric overlap census. If a field is absent or malformed, emit the existing `BOX_NOT_WALL_BOUNDED`, `WALL_EVIDENCE_DIFFERS` or `OVERLAPPING_MEASURED_BOXES` code rather than inventing a new evidence vocabulary. Preserve authentic single-mark, fully typed candidate behaviour and all competing mark conflicts.

## Validation boundary

Source-neutral positive and negative regression tests must execute on **both Python 3.13 and 3.14** on the final head. Independently inspect resulting shadow records; retain `takeoff_eligible=False`, `commercial_projection_allowed=False` and unchanged customer bytes. Source-positive Maryborough replay remains **ABSTAIN** until the SHA-matching authorized original PDF is independently executed. The paired device BrycesPC was reported online, but Desktop Commander rejects commands due to monthly quota; no private replay has been run by this change. Do not push original PDF bytes or crop coordinates to GitHub.

## Benchmark observations that must not influence implementation

The frozen 120-item denominator, original scored identities and historical Maryborough areas are *evaluation controls* only. No gold quantities, expected finish areas, labels-as-room replacements, guessed thresholds, metric shortcuts or scorer code are introduced. GPT MAX's active PWD D13/FT2/WFPB integration and frozen customer rows remain untouched.
