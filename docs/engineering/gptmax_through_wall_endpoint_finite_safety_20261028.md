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
