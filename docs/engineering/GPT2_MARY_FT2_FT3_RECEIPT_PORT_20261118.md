# GPT2 — Original PlanReader Maryborough FT2/FT3 cross-sheet receipt safety (fresh-main port)

**18 November 2026 AEST.** Owner resumed the GPT2 source-correspondence lane via coordination #4135; original measuring engine only. This is a precise, source-neutral preservation of the inspected three-file safety patch from draft #4478 (head `62ff2047d5ebcf8883ad741ccfbf9335864e8814`) without modifying that historical draft or replacing the current mainline. Do not interpret synthetic source-shadow acceptance as measured finish output.

## Repository inspection and call graph

Read `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, current `pb_source_cross_view_floor_correspondence_shadow.py`, existing focused tests, exact #4478 patch, and latest #4135 claims. Source path: `SourceCrossViewFloorCorrespondenceProducer.evaluate_synthetic` → native registration and producer-owned overlapping measured-box census → `box_correspondence` → `classify_floor` → immutable candidate record. `classify_floor` only owns source-shadow classification, not physical wall identity, metric measurement, customer takeoff or signed publication.

## Defect and bounded implementation

Two direct `correspondence[...]` lookups could raise on missing wall evidence. Unchecked truthiness of explicit `other_labelled_boxes_overlapping` accepted malformed counts, including `False`, `None` and `"0"`, as a false/nonconflicting source receipt. Missing or nonliteral wall booleans now produce an existing typed source ABSTAIN reason, as do malformed, noninteger, negative or positive overlap counts. Omitted overlap hint defaults to exact integer zero **only while the producer independently sweeps all measured boxes** and includes verified geometric rival-overlap flags. No first/nearest mark or tie-breaking is introduced. A correctly registered and unique FT2/FT3 source mark remains a **CANDIDATE**, never FIRM or eligible for commercial projection.

## Actual original-source context (not replayed by this port)

Original Maryborough architectural PDF identity recorded in earlier private evidence: SHA-256 `b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007`, 31 pages, room geometry p7, reflected ceilings p9 A120, floor-finish schedule p11 A140. The #4478 verified original schedule labels: FT2 Stockton White 800×400 R10; FT3 Dura Grey 600×600 min R12. These printed source words are **not** physical room-face equivalence, definitive region assignment or measured area. Office D15, PWD D13, room-local thresholds and competing unclosed room rings remain independently gated.

## Validation and release boundaries

Historical source-neutral exact-head #4478 full CI run 44080564954 passed Python 3.13/3.14, but cannot validate this new head. Require fresh exact-head dual-Python CI, focused floor-correspondence tests and relevant protected customer/frozen120 retention checks before merge. Even after source-neutral tests pass, private source→physical→finish→issuer→customer replay and four-project scorer remain **ABSTAIN** without their own complete authenticated evidence. No source PDFs, golden values, scorer inputs, production quantity issuers, door schedule, customer rows or frozen120 contracts changed here.
