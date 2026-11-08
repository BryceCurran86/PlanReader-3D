# GPT MAX — 3Laurel room wet/dry source-receipt integrity (8 November 2026)

## Actual first failing boundary

Claude's #4242 introduces a bounded, default-off source-label wet/dry diagnostic consumed by `_finished_face_receipts` during an original 3Laurel finished-face shadow replay. Its source-scope matching is already sound for **unmodified** records, but `wet_area_status_by_face_record` accepts any public dataclass `RoomWetDryClassification` with matching page/source identifiers, `CORROBORATED` and either wet or dry class. A consumer could receive a reconstructed or `dataclasses.replace`-altered class and incorrectly use it as a lining-variant fact. A frozen dataclass is not producer-authentication; class+scope equality alone does not verify a rule and label binding.

This is not a hypothetical metric score: on the original, Claude reports two source-labelled dry rooms with `room_wet_area_status_not_established` cleared, yet both face receipts remain unresolved because of frame/lining/fill source gaps and issue **zero** measured quantities. It is therefore important to protect the semantic input now without claiming a finished floor.

## Narrow patch on the separate child

This child is based on **exact #4242 head `5c69f50d1febfb86bf4b293508c35cb38be26f2a`**. It does **not** edit Claude's branch or any of his `pb_live_physical_net_wall_integration.py` code.

- Only the producer `_classify_one` can mint a room wet/dry receipt with the private per-process seal.
- The source-stable receipt identifier now additionally binds its physical room ID. Existing document, revision, original SHA, snapshot, page, decision scope, source room face, canonical room, label binding and evidence remain bound.
- Before a receipt affects a finished-face's wet/dry status, its private seal, exact source lineage, noncommercial flags, schema/rule version, CORROBORATED status, canonical/physical room IDs, non-empty label lineage, rule-id/class pairing and recomputed stable receipt ID must all agree.
- A missing/unknown/conflicting/borrowed/rerouted/modified receipt maps to `None` (unknown), never by default to dry or wet. An intact positive still yields the original `False` for a dry room and `True` for a wet room.

No new OCR rule, source document, W2/W3/W4 host, physical face, threshold, metric, floor or ceiling issuer, customer row, evaluator truth or benchmark score. All existing production rules remain default-off, including `room_wet_dry_classification=False`. No new finish authorization.

## Release proof

`tests/test_gptmax_3laurel_wet_dry_receipt_integrity.py` checks a direct copied dataclass, null/foreign producer seal, dry→wet forged replacement, changed rule/version/id, foreign physical owner, source/document/revision/page/snapshot/decision scope, fake commercial flags, altered evidence and ABSTAIN→CORROBORATED forgery, plus intact dry/wet positives and duplicate rival veto. The existing #4242 test suite must also pass unmodified.

Exact integrated head still requires Python 3.13 and 3.14, V2 truth/provider isolation, independent original-source flag-off Lot16 eight + Maryborough three signed/customer **byte-identical** retention, and genuine original 3Laurel source-positive/negative label and physical face replay before a merge. A default-off retention pass alone **cannot** establish new FIRM or customer quantities. The 120-item frozen denominator remains unchanged. This is a stacked DRAFT until the tests and protected source gates have receipts.
