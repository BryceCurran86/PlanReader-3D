# Original source incidence preservation in shadow

Tracker #2396. Architecture before code: comments 6185694620 and 6185737054.
Read AGENTS, engineering playbook, adopted W1–W10/spec, benchmark firewall and
CI. Traced producer-owned G17 source paint/F07 → W2 split/snap/degree-two merge
→ W3 classifier → W4 assembly. No producer authority is promoted.

## Observed first failure: overlapping rays erase original source paint

The existing degree-two merge checks a modulo-180 angle and connects the two
far endpoints. Two same-direction, overlapping originals can share a start;
connecting their far endpoints erases their entire common prefix. This is not
a real short original arm. On immutable original Lot16, full-painted
`raster_line_run:481` (24.48pt) and `raster_thin_ink_run:1049` (24pt) become a
0.48pt far-end chord at `merged_split_286_split_386`. W3 correctly abstains on
that resulting short isolated arm, so changing W3's threshold is inappropriate.

An explicit `preserve_overlapping_spans_shadow` argument now requires opposing
endpoint vectors at both existing merge implementations. Same-side or
degenerate inputs retain original edges and ancestry. The existing angle rule
still applies; no tolerance, parent-length guess or nearest selection is added.
Default callers and the historical zero-index graph remain unchanged.

## Observed second failure: averaging identical exact vertices moves them

The exact-index shadow intentionally follows legacy running-mean arithmetic.
Three identical decimal endpoints can move their stored centroid by one ULP;
the next identical source endpoint then fails distance<=0 and creates a second
node. Original source x737.76 became737.7599999999999 at node683 while the
same original endpoint later became node1202. This disconnects the real source
parent1518 into a long edge and an apparently isolated3.12pt arm.

A separate `immutable_exact_endpoints_shadow` option is valid only with the
explicit indexed-zero mode. All coordinates must be finite. A distance-zero
match increments occurrence count without averaging equal source coordinates.
Truly different one-ULP source points remain distinct; no rounded/proximity
join or global snap change is made.

## Functional source proof and remaining authority boundary

The producer-owned G17 reader keeps both original graphs unchanged and adds
separately scoped candidate graphs when explicitly requested. Original image
paint, F07, source receipt and exit-integrity checks remain authoritative for
input ownership. No caller-provided geometry or serialized diagnostic can
become a published wall/host universe.

Archived-source hypothesis replay: freshly downloaded original #2744 artifact
11931953022, ZIP SHA
`c9d942c19c3055323739f44cc2116c61b57feb279a23a81812931815361dcab7`.
The same1162 source-positive inputs reproduce the original1698 W2/1312 W3
retained edges. Baseline W2 fully conserves1088/1162 original source intervals;
the overlap guard conserves1162/1162. The combined mode also conserves1162/1162
and removes spurious exact-coordinate incidence splits. This archive analysis
is not itself a fresh PDF authentication; dedicated original CI replays the
immutable PDF and repeats these source invariants.

A fresh local PDF replay with both flags completed successfully on 2026-10-15.
The original SHA is
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`;
the producer snapshot is `source_snapshot_7ad8bf09e3ebbec9797df89842574683`.
Executing the committed workflow assertions against that replay confirmed
74 lost source intervals before the guard and zero afterward. The replay's
original sealed customer receipts exactly equal the previously verified
all-page producer replay, including all eight quantities, seal and customer
verification. Selected-page and all-page snapshots remain distinct.

Actual a68 upper original horizontal span661.44..692.40 at y426.24 now resides
in one candidate W4, including its previously disconnected final0.48pt piece.
The lower original junction is no longer falsely isolated; it correctly remains
AMBIGUOUS/ABSTAINED with `degenerate_angle_group_size_over_two` from actual
overlapping source branches. The combined source graph has868 candidate W4s,
zero abstained-chain fallbacks in the archived experiment. These counts are
observations, never decision thresholds or wall-role proof.

No independent structural wall role, physical equivalence, real new host,
opening frame, second measurement axis, count or ninth quantity follows from
source conservation. Those stages remain blocked and must not consume these
candidate scopes without separate authority review.

## Verification and untouched contracts

Synthetic tests cover same-side cancellation, opposing joins, gaps/corners,
source splitting/order, rigid transforms, scale, index/reference parity,
one-ULP distinctions, repeated finite decimals/subnormals/large values,
nonfinite rejection, explicit flags, no mutation and actual producer exit
damage. Existing legacy-equivalent graph tests remain unchanged. Original
SHA replay must preserve21 opening records/15 hosts/nine frames/eight source
areas and every original signed customer receipt before/after the observer.

Original PDFs/snapshot, global2.5pt production snap, W3/W4 decision rules,
physical role/equivalence/host producers,20k input cap, canonical and quantity
publication, V1 signatures and frozen truth/evaluator are untouched. This
requires independent review before any authority promotion. DRAFT until exact
head source workflows and CI succeed.
