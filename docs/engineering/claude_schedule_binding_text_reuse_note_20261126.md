# Speed: read the trusted page text once per composer loop in the schedule-opening binder

Date: 2026-11-26. Order: owner work order #4764 7190405332 item 1; claim 7190772374; design approved by the owner before the build.

## Observed (cold profiles, `main` ecad4123d)

- `ScheduleOpeningInstanceBindingProducer.publish_scope` resolved every text observation of the whole document for each opening.
- Maryborough: 348 calls x 29,466 words (10.3 million `resolve_text` calls); 3Laurel: 540 x 3,515 (1.9 million).
- Three loops call it once per opening (count publication, opening deduction, physical void composition); nothing else runs between iterations.
- The lookup reads receipts filed under the snapshot, and some producer steps replace receipts in place, so a cache kept across calls could be stale.

## Change

- The original read moved unchanged into `_read_trusted_text`.
- `reusing_page_text()`: only inside this block, the text of a snapshot is read once; before each reuse the published snapshot object and every text receipt must be the same objects as when it was read (a read-only `receipt_objects` accessor on the text-integrity authority). Outside the block, and for direct calls, nothing changes.
- The three composer loops publish inside the block.
- No evidence, ordering, ambiguity or identity rule changes.

## Verification

- 10 tests (`tests/test_schedule_binding_text_reuse_v1.py`): same result with and without reuse; one read per block, every time outside; replaced or downgraded receipt and republished snapshot read again; block exit by error; nesting; two snapshots; accessor. 6 single-line mutants each fail one.
- Tests touching the changed modules, with originals: 1,006 passed, 2 skipped.

AB_PLACEHOLDER

## Benchmark observations that must not influence the implementation

The counts above are measurements. No page, project, count or expected value enters code.
