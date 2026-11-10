# Source-proven duplicate-aperture customer publication: default-off consumer (owner/MAX order, 2026-11-10)

Scope: one opening-area quantity (and so one sealed row and one customer row) per source-proven physical aperture. Default off, CANDIDATE-only, no new authority. Counts, short ids and statuses only; no coordinates, words or source bytes. Frozen 120, the Lot16 signed eight, the Maryborough signed three, the identity map and the scorer are untouched.

## Observed repository behaviour (read, not assumed)

- One canonical opening is built per physical-opening existence record and `canonical_opening_id == physical_opening_id == record_id` (`pb_live_physical_opening_void_composition.py`, canonical construction). `publish_live_opening_area_quantities` rejects only an IDENTICAL id, so two records of one aperture each publish a quantity, each seals, and each reaches the customer.
- The COUNT authority already abstains on a pair whose identity is not corroborated (`pb_generic_opening_count_authority.py`, pairwise identity block); the area publication had no equivalent.
- The producer-owned verdict exists: `PhysicalOpeningAuthority.partition_receipt` / `verify_partition_receipt` (re-proves both records, canonical order, `grants_quantity` and `grants_firm_authority` False). It was consumed only to prove DISTINCT (append-only reproof, host binding); nothing consolidated `overlapping_extent`.
- The live claim carries `canonical_openings=physical_void.canonical_openings` (integration, both return sites) and the seal/customer functions read the claim's quantities and canonical inventory, so the consolidation must act on the COMPOSITION before publication for the sealed run and the customer rows to stay one-to-one.

## Rule (owner-approved option A)

`pb_live_opening_aperture_consolidation.py`, only when `enabled is True`:

1. every measured opening is re-proved through the physical authority (a caller's ids certify nothing);
2. every same-page pair's partition receipt is verified (an unverifiable receipt is UNPROVEN, never DISTINCT);
3. the #4267 equivalence rule groups the openings: overlapping extent AND the very same printed-figure words, area and PHYSICAL host (the wall composition's member-wall candidate group, not the per-record host id); anything else not proven apart is ambiguous and recorded;
4. a proven class keeps ONE real member only if its source observations STRICTLY CONTAIN every other member's (order-independent; never first, nearest or smallest) and every member's quantity agrees in authority, status, family, unit, value and basis; otherwise nothing is consolidated and every member publishes as today;
5. the result is a derived composition without the dropped members (the SAME object when none) and a record keeping every member's id, source observations, quantity id and partition-receipt ids. The surviving row is the owner's own, byte for byte.

`publish_live_opening_area_quantities_with_aperture_consolidation` fails closed unless the consolidated publication equals the original publication minus the dropped members' quantities.

## Proof

- Synthetic (the physical authority's answers injected): positives; separate apertures with equal figure/area/host (DISTINCT) never merge; overlapping with a different figure, no figure, a different or unknown host, a different area, or an UNPROVEN pair stays ambiguous and recorded; symmetric or tied members have no owner; differing quantity authority/status/basis/kind blocks; an opening the authority does not re-prove is left alone; unmeasured openings and other pages are never compared; input-order and replay invariance (15 shuffles), no mutation, the same object when nothing consolidates; the publication invariant.
- Sealed/customer bijection (default off): OFF leaves the sealed run fingerprint and the customer rows byte-identical; ON seals and projects exactly one row for the one aperture and it equals the owner's baseline row; several classes stay one-to-one between published quantities, sealed quantities and customer rows; a distinct aperture and a conflicting physical host keep both rows.
- 32/32 single-line mutants of the module are caught (two equivalent mutants are excluded: the redundant strictness of one comparison and a type check the publisher repeats).

## First failing gate on the genuine 3Laurel original (counts only)

- Opening-area figures need the glyph-ledger text-trust opt-in. With default text integrity the label producer returns `opening_label_dimension_text_unavailable` for all 35 sealed opening-area records, so the figure key is empty and every overlapping pair is ambiguous (`overlapping_records_without_printed_figure_evidence`). Re-proving the 35 sealed records: 595 pairs, 577 disjoint, 16 overlapping extent, 2 partitioned; with the opt-in off, 0 classes consolidate and 26 records stay ambiguous.
- With the opt-in on: MEASUREMENT PENDING (filled in before posting).

## Wiring (NOT done: inside functions other lanes own)

At the publish step of `_collect_live_physical_net_wall_claim`, after `apply_live_external_door_height_estimates`, behind a new default-False keyword threaded through the public wrapper:

```python
if aperture_consolidation:
    physical_void = consolidate_live_opening_apertures(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
        composition=physical_void, enabled=True).composition
opening_quantity_evidence = publish_live_opening_area_quantities(physical_void)
```

Risk to settle with the owners of those functions: `recover_source_opening_areas` replays a second producer and APPENDS fresh quantities that are not in the baseline; a dropped member would be re-added as an "addition" unless the same consumer is applied to the fresh composition there. The recovery path must consolidate identically or refuse.

## Not claimed

No quantity, FIRM authority, score or customer promotion; whether consolidation changes what the unchanged identity map and scorer can match is an owner decision (an earlier diagnostic found two classes that each held two mapped identity-map records). No live wiring until the claimed functions are coordinated.
