# Avoid a scale-bar geometry search with no authenticated words

## Observed runtime and authority path

Read AGENTS.md, engineering playbook, W1-W10/firewall/CI rules, takeover, and
`PhysicalScaleProducer.publish_scope` -> `_trusted_words` / `_visible_segments`
-> `_bar_candidates` -> `_TickEndpointIndex.exact_ticks_for_endpoint`.
The isolated original scoped room replay passed the visibility bottleneck and
then sampled this scale geometry search before the local diagnostic timeout.

A SHA-original preflight through the existing default source producer and
`PhysicalScaleProducer._trusted_words` returned zero authenticated words on
both pages 7 and 11. These are observed source/runtime facts, not new parsing
rules. No source words, coordinates or expected quantities are copied here.

## Bounded change

`_bar_candidates` can succeed only with a trusted zero label at one endpoint
and a trusted positive physical-unit label at the other. Empty words therefore
make every geometric candidate impossible. Return the same empty tuple before
constructing the tick index. `publish_scope` still authenticates revision,
bytes, page/viewport, words and visible geometry, and returns its existing
`PHYSICAL_SCALE_BAR_UNAVAILABLE` / ABSTAIN. Nonempty source words use the exact
same complete geometry/competitor path. No new scale, ratio, threshold, source
scope or exception to any authority gate.

## Validation and exclusions

Prove the empty-word path does no tick search, retain differential full-scan
bar/tick/retrace/transform tests and authenticated scale/room tests, then rerun
the real original scoped producer and signed/customer gates at a fixed head.
The current #4224 candidate stays frozen during its own checks. No frozen120,
20k primitive cap,2.5pt snap, quantity, ceiling or private original edits. A
faster source rejection does not establish physical scale or benchmark gain.

The empty-word work-bound regression failed before the early return. All35
existing scale/tick/retrace/full-scan/transform/calibration/room/cached-scope and
workflow-security tests pass with it. The next original scoped producer run
must retain source/customer gates and all original source evidence.
