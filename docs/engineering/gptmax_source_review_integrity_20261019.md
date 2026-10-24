# Source review and retention integrity

Delivery ledger #3161, items 13–29. No benchmark prediction or authority
promotion is part of this batch.

## Trace and observed failures

Read the agent contract, playbook and its required architecture, topology,
benchmark separation and CI documents, plus the accuracy-levers agreement.
Traced `opening_source_lineage_packet` →
`compare_opening_source_correspondence` → `opening_quantity_addition_review`
→ `build_opening_source_review_package`, and both recovery entry points →
`SourceVisibilityProducer.fork_native_source_shadow`.

The old comparison trusted a closure Boolean without checking missing
transitive parents, cycles, unreachable records or parent-edge budgets. Its
signature covered only physical roots, so changed ancestors could still be
reported as exact support. Original packet coverage was not checked before
reviewing an apparent additive occurrence. Duplicate explanation aliases could
repeat one physical ID in the correspondence result.

ZIP creation overwrote existing files and could leave a partial output after a
write failure. Packet and subordinate review authority flags were not checked
consistently before serialization. Nominal OBJ identifiers could contain OBJ
record separators. Batch recovery validated policies after starting original
composition. Native source forks replayed a complete original decode as an
explicit partial-page selection, changing its revision identity, and did not
compare replayed decode coverage with the original.

## Implemented behavior and expected abstentions

The existing explanation seam now validates root/occurrence identity, selector
and source ownership, finite geometry, full parent membership and reachability,
acyclic closure, and node/edge budgets. An iterative parent fingerprint covers
the complete physical source ancestry; it ignores explanation-row ordering and
retains every distinct alternative without treating aliases as occurrences.
Missing, malformed, foreign, cyclic or over-budget support stays incomplete.
These structural checks never authenticate imported evidence, issue physical
SAME identity, migrate a signed record, or authorize quantity publication.

Addition review requires original and alternate occurrence packet coverage and
closed original ancestry. It retains candidate rows with their first missing
parent gate rather than treating an incomplete original inventory as proof of
a new physical object.

Portable reports validate their review-only state, source identity, local-frame
limitations, unplaced nominal identity and matching nominal axes before any
output creation. ZIP output is create-only and failure-atomic, including races
and symlink collisions. OBJ names cannot introduce records or external assets.
The CSV preserves each object's first gate, every required evidence code, its
rank, exact packet/source address, and unresolved-parent count.

Recovery rejects invalid flags, stale revisions and undecoded pages before
original composition. Native forks validate decode provenance and page bounds,
preserve full versus explicitly selected decode scope, and compare actual
native replay coverage with the original. No serialized authority is imported.

## Execution receipts

`tools/run_gptmax_original_retention_check.py` executes the existing original
producer from an exact clean head, records the tree and dependency/OCR context,
checks original source bytes and archived artifacts before and after execution,
and compares both signed/customer files byte for byte. Missing outputs, changed
heads, source mutations, archive mutations or a failed child cannot yield a
positive retention receipt. Its file-comparison helper alone never claims
execution. Missing Maryborough OCR is a preflight failure, not a zero-floor
source result. This is validation tooling, not a new producer or quantity seam.

At preceding tested head 418a0399, original Lot16 retained eight quantities with
fingerprint ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb;
Maryborough retained three with fingerprint
9f3ab9ac1497cae5c29f8873af9287a5d6e3b3a386937fdeb37f8b5989fd780d.
Those are post-producer observations. Exact final-head execution and CI must be
recorded separately before claiming completion.

Synthetic cases cover positive controls, missing/cyclic/changed ancestry,
ordering and replay, no mutation, malformed exports, atomic failure, existing
file/symlink protection, source-fork scope and early policy rejection. Fake
children in retention-runner unit tests are explicitly not original-source
validation. Source PDFs, frozen truth, mapping/scoring, archived receipts,
20,000-primitive caps, snap tolerances, W10 and commercial gates are unchanged.
