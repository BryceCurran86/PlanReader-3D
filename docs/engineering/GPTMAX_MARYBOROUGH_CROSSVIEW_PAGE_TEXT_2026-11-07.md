# Maryborough cross-view room-area page text addressing

Base: current main `665d8c4`. Owner: GPT MAX; coordination #4135.

## Observed

Read the governing agent contract, succession handover and engineering
playbook. The protected original Maryborough run completed native ingestion,
all 31 wall pages, canonical rooms/floors and same-view areas, then timed out
inside `CrossViewRoomAreaProducer.publish` without a role seal. The subsequent
empty-scale-word optimization is downstream and does not resolve this stage.

Traced `publish` into `_trusted_lines_for_page`: for each decoded page it
resolves every text observation in the whole snapshot before rejecting missing
receipts or receipts from another page. A second annotation pass repeats that
work. The existing `PdfTextIntegrityAuthority.observation_ids_with_receipt_page`
is explicitly a pure, order-preserving filter over exactly those receipts.
It grants no text authority; each retained ID must still pass `resolve_text`.

An independent SHA-original page-11 OFFICE subcase completed native ingestion,
two trusted label lines and nine authenticated dimension facts in 24.702s.
This is not a room-area, customer or full-run completion claim. The full
multi-page cost and the complete source/customer outcome require replay.

## Inference and proposed change

Other-page receipt IDs cannot contribute to this page's label lines. Use the
existing receipt-page filter before calling the unchanged text resolver,
grouping, raw-label, isolated-OCR and ambiguity predicates. Keep the published
ID order and source/snapshot selector exactly unchanged.

## Validation requirements

Compare complete label records with the existing unfiltered resolution path.
Verify only addressed-page words are authenticated, and that missing or
changed receipt pages preserve the old results. Keep existing positive,
duplicate-label, witness, lineage and source-tamper tests. Run the real original
floor producer and signed/customer retention before claiming acceptance.

## Benchmark boundary

No source PDF, reference value, evaluator, mapping, snap/cap, geometry, metric
predicate, issuer or customer writer is changed. No new quantity or accuracy
gain is claimed by a performance-only input filter.

## Local regression result

The new page-addressing regression fails on the parent because unrelated-page
words are resolved. With the filter, the existing cross-view, same-view,
physical-scale room-area and source-page-scope tests pass all 80 cases. Complete
label records match the unfiltered implementation; missing and foreign-page
receipt cases return the same abstentions. Local Python 3.12.14; this does not
substitute for original signed/customer or final-head dual-Python acceptance.

The caller also excludes own-page room labels before requesting text proof.
Those labels were already discarded by the unchanged post-proof cross-view
predicate. Compound annotation lines remain eligible when any other-page room
matches. Two regressions (one room page and mixed room pages) fail on the
parent, check the actual requested normalized labels, and retain complete
publication-result equality. All existing duplicate, lineage and witness
checks remain in place.

The combined candidate includes the existing target-owned door-height repair
from #4227 and the empty-scale-word exit omitted when old #4224 was merged.
Its room, scale, opening, issuer, append-only and customer regression set
passes **470 tests**, with six optional/original-only skips.

## Original-source observations

Using the SHA-verified original, complete page-7 and page-11 label records
match the unfiltered immutable-main implementation. The native two-page
ingestion took 14.663s; the label comparisons took 1.425s/1.204s on page 7
and 1.839s/1.710s on page 11 (old/new). This proves retention for this reader,
not an end-to-end timing result.

A diagnostic support-reader pass over all 31 original pages completed in
178.53s. It exercised the existing label and dimension readers with a bounded
label set; it does not substitute for publication against all production
rooms. The unchanged real floor producer is still subject to its own
sealed/customer retention gate. No new finish or benchmark item is credited.
