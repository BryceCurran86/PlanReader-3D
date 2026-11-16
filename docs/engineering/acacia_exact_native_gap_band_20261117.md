# Acacia p2: source band vs native path search radius (17 Nov 2026)

Original private Acacia House Brisbane technical drawings, SHA-256
`435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a`,
page 2 (zero-based index 1). Original `get_drawings()` native path indices:
4000, 4002, 5862, 5848, 5849. The exact source audit found path
4000 to 5862 bounding-box contact of 0.000488 PDF pt, but physical
jamb / opening ownership remains **unproven**. Source path 4000 and
4002 occupy parallel ink bands separated by 4.320374 PDF pt. Their
contact and near parallelism cannot authorize one physical wall.

The previous shadow `_closure_covers_edge` already required an
entire gap span, but used the `_EDGE_SEARCH_PT=2.5` association
window to decide whether a closure belongs to the **same** source
wall band. This permitted a false topology-only closure when a
different parallel source face lay just 1.5 pt away. This patch
separates path *discovery* from physical *contact*: the full-span
closure must intersect the exact band within `NOISE_PT=0.05` PDF
pt representation tolerance. No snapping, bridging or invented
frame/wall/opening is permitted. Nonfinite gap/ink bounds abstain.

Tests cover nearby parallel horizontal/vertical faces, valid same
band closures, nonfinite bounds, partial gap coverage, and separate
partial closures that must not combine into a full closure.

**Acceptance status:** this is only a conservative source-native
topology shadow; no customer quantity is minted. The held-out
original Acacia complete building footprint, room/wall/ceiling,
opening and frame customer output remains unsealed until complete
source-backed production acceptance. Do not claim a frozen120 score.
