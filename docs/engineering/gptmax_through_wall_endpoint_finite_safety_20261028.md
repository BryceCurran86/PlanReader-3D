# GPT MAX — through-wall endpoint and finite-input safety

2026-10-28. Review basis: current `AGENTS.md`, `docs/AI_ENGINEERING_PLAYBOOK.md`, coordination #3462, merged AntiGravity #4063 and its nine tests, and `pb_structural_through_wall_aperture_host_authority.py::bind_openings_to_through_wall`.

## OBSERVED (source-code behavior, not benchmark evidence)

The default-off shadow host producer accepted a 1000pt-long, 20pt-thick wall and an opening from (0,-15) to (1000,+15). Its average transverse offset was zero and the opening's alignment cosine was 0.9995503, greater than the threshold 0.9995; both physical jambs were nevertheless outside the actual wall half-thickness plus fixed 2.5pt snap allowance (12.5pt). It therefore emitted a `CORROBORATED` shadow host without a geometrically valid endpoint host. Constructors and an optional caller-supplied snap tolerance lacked finite/cap checks: NaN comparisons can bypass bounding predicates.

## INFERRED

A long, shallow slant can meet angular tolerance without proving both jambs are inside the wall. A shadow-only false CORROBORATED record must never be mistaken for source-verified physical wall authority. Synthetic coordinates do not establish an actual aperture, continuous wall, pier, elevation frame, physical size, customer output, or original-positive drawing receipt.

## PROPOSED CHANGE

Check each transverse endpoint separately; reject nonfinite/degenerate wall and aperture points, nonfinite wall thickness, and invalid, negative or over-2.5pt snap tolerances. Preserve the existing angular, longitudinal, transverse obstruction and 2.5pt geometric gates and all output schemas/flags. Source-neutral adversarial tests cover the former false positive, rotation, in-band positive, finite values, bounded snap and deterministic replay.

## BENCHMARK FIREWALL / REMAINING AUTHORITY GATES

Do not derive any threshold from the frozen 120 objects or change any original PDF, frozen evaluator, source corpus, signed run, customer retention, measurement issuer, cache, or snap cap. This PR yields **zero new FIRM quantities and zero claimed score increase**. The #4063 `is_structural_masonry_pier=True` field still relies only on geometric gap; it is NOT an authenticated physical pier and must not be wired to commercial quantities without independent source proof. This safety correction does not resolve those separate source-identity gates.

## Validation

Target exact-head Python 3.13 and 3.14 required CI, synthetic positive/negative and order/rotation, signed/customer regression, original-source source-authority replay before any promotion. A public green synthetic run does not replace SHA-verified original-positive release evidence. Review the actual diff before merge.

## 2026-10-28 — additional observed shadow identity defect

**OBSERVED:** `bind_openings_to_through_wall` minted an `inter_aperture_pier` ID with document and wall ID but without original `revision_id` or `source_sha256`; a same-named wall at the same stations across different original receipts could alias. The `through_wall_hosted_opening` ID already bound source SHA/revision but omitted the host's own geometry, so moving or thickening a same-named wall could also alias. Neither record is an original-source-authenticated physical pier.

**INFERENCE / CHANGE:** Add source revision/SHA, both physical-opening identities, and host endpoints/thickness to the deterministic pier payload. Add host endpoints/thickness to the existing shadow opening ID payload. Source-neutral tests cover unchanged deterministic replay, opening order, changed source/revision, wall translation and thickness, and permanent noncommercial flags. Existing public output schema, geometric gates, 2.5pt snap cap and frozen evaluator remain untouched. This fixes shadow provenance collisions, **not** a signed customer quantity or frozen V2 accuracy item.

**RELEASE:** Exact-head Python3.13/3.14, owner-only original-source replay and signed9/customer retention must pass before merge; no original PDF, token, benchmark or signed artifact may enter this branch.


## 2026-10-29 — endpoint snap versus physical host overlap

**OBSERVED:** The extent check accepts opening endpoints up to 2.5pt beyond the wall ends. Previously the producer then clamped `u_min` and `u_max` independently without proving a nonempty intersection with the physical host. For a 0..100pt wall, openings -2..-1, 101..102 and edge-only touches passed extent/band checks and could be shadow CORROBORATED with inverted or zero host intervals. **INFERENCE:** Snap tolerance cannot manufacture an actual host interval. **CHANGE:** After extent validation, require strictly positive (>1e-4pt) clipped host overlap; retain such outside candidates as ABSTAINED with `aperture_no_host_wall_overlap`. Real partial straddles remain shadow CORROBORATED with clipped positive spans. Tests cover both ends, edge touches, rigid transforms, deterministic replay, disjoint pier ordering and commercial veto. **BENCHMARK:** No expected BOQ/Full Plan V2 values or source filenames were used as algorithm inputs. Original source and signed/customer replay still required; no FIRM or score claim.


## 2026-10-29 — complete-universe physical identity veto

**OBSERVED:** The producer's duplicate physical-opening-ID check used only valid_items, after rejecting out-of-band, misaligned, obstructed or unhosted observations. A valid A and a rejected A therefore left the valid A shadow CORROBORATED and able to create a pier with another opening, despite contradictory claims to the same physical identity. **INFERENCE:** geometry rejection cannot erase a conflicting physical identity; retain both candidate records and the original negative's first-failing gate. **CHANGE:** Count physical identities in the full supplied opening universe, and downgrade otherwise-valid repeated identities to aperture_physical_interval_conflict before pier creation. Existing valid-valid overlap behavior is preserved. Regression cases cover invalid band, outside extent, transverse obstruction, misalignment, reversed input, rigid rotation, stable replay, unaffected unrelated valid piers and shadow-only commercial veto. **BENCHMARK FIREWALL:** no expected quantities, original PDFs, customer issuer, frozen truth or scoring inputs used; no new FIRM/score claim. Source-positive replay and signed9/customer parity remain outstanding.


## 2026-10-29 — narrow-aperture transverse obstruction clipping

**OBSERVED:** A fixed 2.5pt trim on each end emptied the obstruction-testing interval for an aperture at or below 5pt, so a finite transverse wall crossing the centre of a 4pt opening was skipped and its shadow host incorrectly CORROBORATED. **INFERENCE:** snap tolerance must not erase an entire physical aperture from structural obstruction testing. **CHANGE:** the exclusion margin is now the smaller of configured snap and one-quarter of actual aperture span, retaining a nonempty physical interior; numerical collapse fails closed. The 2.5pt cap is unchanged. Synthetic regression covers 4/5/6/10pt spans, zero/default snap, rigid transforms, reversed/split/order-invariant crossing, unrelated obstruction, replay and immutable noncommercial flags. **BENCHMARK FIREWALL:** no original PDF or expected score was used. Source-positive replay, signed9/customer retention and frozen120 remain unverified.
