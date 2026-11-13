# Maryborough original-production authority corrections — 11 November 2026

This integration retains AntiGravity's source-to-customer work from PR #4253 at `042affde2275fbecaee64014033e7a40e6af3733` on main `fc76f95428c45011e895b3dfd8fff37f03f67ace`. The original app, evidence contracts, quantity issuers and customer projection remain the target.

## Observed behavior and change

The room-area and floor/ceiling correspondence registries accepted a distinct dataclass-equal object at an occupied authority key. That replaced the first producer instance used by identity-based authentication. Direct registration now permits the same object only. Completed producer replays validate all aliases, reuse the original equal issuance and return that same object; conflicts write no partial aliases. Weak-reference cleanup remains intact.

The ceiling composer could count one numeric alias for both equal room axes. Each axis now requires its own unambiguous producer-owned reference. Two different figured-number aliases remain compatible for nonsquare rooms; a square needs distinct native axis IDs. A source-generated square PDF tests the actual room-area producer and both valid and invalid ceiling consumers.

Ceiling rejection messages no longer interpolate private source IDs, dimensions, metadata or record representations. Numeric conversion errors suppress their source-bearing exception chain. Nonfinite caller axis values cannot evade comparison. Accepted typed area quantities carry the authentic upstream atom ID into ceiling evidence, rather than a Python object representation.

## Existing call path

Original PDF bytes -> SourceVisibilityProducer -> CrossViewRoomAreaProducer / source cross-sheet correspondence -> floor-finish or ceiling QuantityEvidence -> existing source-closed exporter -> verify_sealed_customer_output.

No changes to source PDFs, frozen evaluation inputs/denominator/tolerances, geometry primitive cap/snap, Next package, or historical signed fixtures.

## Validation at implementation checkpoint

- Corrected pre-fix regressions: 16 failures and 12 passes on the unmodified integration baseline; failures reproduced identity replacement/replay, ambiguous square-axis evidence, private-data error disclosure and NaN comparison bypass. Later coverage also tests canonical atom lineage and transactional alias registration.
- New regressions plus complete room-area suite: 71 passed, Windows Python 3.13.
- Broader selected original production/ceiling/correspondence/revision tests: 162 passed, 18 private-source skips, 16 deselected. These tests do not establish original-PDF acceptance.
- Full Python 3.13/3.14 CI and final-head original-source/customer acceptance are required before release. Original Office floor/GRID source-positive baseline run remains separate and is not counted as a completed customer result at this checkpoint.

No new production accuracy or official benchmark result is claimed by these corrections. The previously completed four-project development packets remain separate from these pending new quantities.
