# GPT1 Q01 — Source-F07 floor-plan transport into physical-scale scope

The production room metric path in `pb_live_physical_net_wall_integration`
previously saw only **page-only W4-accepted F07** viewports. A source
geometry/text plan view independently authenticated by the newer F.07
source reader (merged #2716) could reach `PhysicalScaleProducer` in
an isolated test (#2727), but could never be selected by the live room
measurement entry point.

## Narrow same-producer source authority

After retaining the existing legacy W4 viewport path unchanged, and only
if that producer returns **no** authenticated plan selector, the live
measurement bridge may inspect `segment_source_page_viewports` on
the **same exact SourceVisibilityProducer instance/revision/snapshot**.
It admits exactly one producer-sealed source F07 floor-plan drawing box
(never a finish plan or bare title), exact unmodified document, SHA,
revision and snapshot ancestry, finite source bbox and *every* source
physical room's polygon inside that box. A room already owning a
different viewport, a competing page-only W4 plan, mismatched source,
malformed geometry, absent independent F.07 title/orthogonal rails or
multiple source-plan views must ABSTAIN.

The admitted view ID is ONLY transported to the existing
`PhysicalScaleProducer.publish_scope`, which still requires a genuine
visible native graphic scale bar; PDF title-scale text cannot create
m². This code does not change any W2/W3/W4/SourceRoomFace/CanonicalRoom
identity, room label, figured dimension, material ownership, wall
shape, opening host, historical FIRM quantity or commercial status.

## Original-source verification

Run the immutable Lot16 original p3 SHA
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`
through the actual live source→room→floor production reader and
independent 8-opening customer source seal. Report W4 room source first
gates and the actual per-room physical-scale failures, without counting
the existing p3 61 canonical floors as metric floors. If a genuine
source-root F07 viewport is unavailable, ABSTAIN; never borrow the
separately authenticated 1.0 source-root viewport from a 1.3.0 live
snapshot. Verify original Maryborough three Food Prep/Office/Cold Room
source→FIRM→signed/customer rows on the original 31-page SHA via a
separate source control before merge.

Adversarial positive and negative tests cover source-owned exact
viewport, foreign SHA, revision, snapshot, document, source page,
other-owned viewport, incomplete/off-box polygon, original source
tampering, absent frames/titles, competing views, two-axis/graphic-bar
ABSTAIN and deterministic snapshot retention.

Frozen Full Plan V2 evaluation, gold/manifests/denominators/tolerances,
global W2 2.5 point snap, 20,000 raster cap, physical opening identities,
customer output, all source bytes and AG-09 producer rules unchanged.
No benchmark score, FIRM floor or tile finish granted by this scope bridge.
