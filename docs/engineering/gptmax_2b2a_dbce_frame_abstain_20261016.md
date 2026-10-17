# GPT MAX — 2b2a neighbour host and dbce band ABSTAIN

Issue #2396. Continues PR #2813 / #2809. Original Lot16 SHA256
`10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844`, page 3,
snapshot `source_snapshot_3fcb6bc5c44b51d930e9600080501d27`. F07 remains
supporting physical-view evidence, not host membership.

## Observed repository behavior

Traced `compose_live_wall_opening_authority` →
`OpeningHostBindingProducer.publish` →
`_resolve_raster_source_band_host_from_records`. Selector lookup is
`OpeningHostBindingAuthority.resolve`.
`_proven_raster_opening_flank_boxes` belongs to
`SourceVisibilityProducer` and runs during source augmentation, not as a
binding-producer method. The neighbour check is
`OpeningHostFrameProducer._scope_bindings`. No measurement seam was
crossed. `#273` ranking was not consulted.

### `physical_opening_existence_2b2a91e8afaf8b7e9a3e07605a80a4a9` (1215 SGW)

Host is corroborated: `opening_host_binding_resolved`,
`opening_local_supplemental_source_band_host_resolved`,
`raster_source_band_host_resolved`. Members
`wall_ad5e43e87149682d9900` (661.44–692.4 at y=427.8) and
`wall_f92ac8eb34b0048e144b` (581.04–619.68 at y=427.8) exist only in the
opening-local supplemental W4 scope. They are absent from the ordinary
complete page wall_scope (2094 records).

Frame first fail is `opening_host_frame_aligned_opening_binding_unavailable`.
`_scope_bindings` discovers same-axis / same-center / same-thickness neighbour
`physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f` and requires a
corroborated host record. The neighbour has none, so the lookup is
`host_binding_record_unavailable`.

### `physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f`

Origin (692.64, 427.92), length 23.52, thickness 3.36. G17 support includes
closed left faces 661.44–692.4 and right faces 716.16–760.32, plus both
jamb ends. Original paint on the left pier is a solid 3.36 pt band
(y≈426.22–429.53). `wall_ad5e43e87149682d9900` already occupies that exact
left interval.

Host reasons: `no_authenticated_host_wall_band`,
`raster_source_band_left_source_primitive_unmapped`. Ordinary source-band
cannot see supplemental `wall_ad5e`. The page supplemental scope contains
only the two 1215 members. There is no ordinary or supplemental W4 wall on
the right pier 716.16–760.32.

`_proven_raster_opening_flank_boxes` nominates a box only when
`OpeningLabelDimensionProducer.publish_scope` has `evidence.area_m2`. All
eight a68d label rows resolve with `area_m2 is None`. The 12 nominated
page boxes therefore include 2b2a's left (581.04–619.68) and right
(661.44–692.4) and omit a68d's unique right box (716.16–760.32).

`exact_source_ref_w4_candidates` is empty for every a68d G17 flank. G17
`raster_opening_primitive` namespace is not the ordinary
`raster_segment:64e58ab8…:1.0.0` W4 namespace. In-aperture
`raster_line_run:482` remains opposing continuation evidence.

### `physical_opening_existence_dbcec9c3cfa8e22b332479d09a601985` (0621 SGW)

Host is corroborated on ordinary `wall_b689beedb69c1be4eae7` via
`raster_source_primitive_host_resolved`. Opening thickness is the G17
aperture height 2.40.

Original 16× ink rows on the immutable PDF:

| Interval | Solid paint y | Thickness |
|---|---|---|
| Left pier x=320–348 | 193.03–195.59 | ≈2.56 pt |
| Aperture x=346–406 | sash lines only | ≈2.4 pt void |
| Right pier x=403–430 | 192.03–195.59 | ≈3.56 pt |

G17 left faces are y=192.96 / 195.36 (2.40). G17 right faces are y=192.00 /
195.36 (3.36). A thin leftover stroke near y=192 on the left is not the
solid wall fill. `_scope_bindings` thickness_tol is `max(0.75, 2.4×0.15)=0.75`.

The thickness check returns
`opening_host_frame_aligned_band_geometry_inconsistent` inside the
discovery loop, before host lookup and before any DISTINCT test. An
aligned opening outside that tolerance fails the frame even when its
host is positively `DISTINCT_PHYSICAL_WALLS`. An independent current-main
replay names the first such opening as
`physical_opening_existence_91ae06327d4fcc8004a557b116a77820`, origin
(645.12, 193.68), thickness 3.36, host `wall_44435f10931bfe1d18b4`,
DISTINCT from dbce host `wall_b689beedb69c1be4eae7`. That DISTINCT
result does not pass the thickness gate. dbce's own faces are also a
real step, so dropping the remote context would still leave a
non-constant band. Do not widen 0.75 and do not skip a context against
only the selected member.

## Inference

a68d's left jamb already has a source-owned supplemental wall from 1215.
The missing W4 owner is the right pier. That pier is painted and longer
than the 4 pt production rule. It is withheld from supplemental nomination
because a width-only figured label does not mint `area_m2`. Transferring
the 1215 member set, raising snap, lowering 4 pt, or treating
`raster_line_run:482` as wall would invent a host.

Even if a68d gained a host, `OpeningHostFrameProducer` still requires every
component member to exist in the ordinary complete wall_scope
(`wall_id not in records_by_id` returns None). 1215 members stay
supplemental-only, so a whole-wall frame still cannot seal.

dbce has two separate blockers. The function returns first on an
aligned 3.36 pt context, and dbce's own flanks are also a real thickness
step. Averaging faces, widening thickness_tol, or excluding that context
only because its host is DISTINCT would still not prove one constant band.

## Proposed change

None in default production. Keep ABSTAIN on a68d host, 2b2a frame, and
dbce frame. Do not remove the `area_m2` flank-box gate here: #2660 already
showed that relaxing source-perception nomination rekeyed existing hosts.
Default must remain 21 openings / 15 hosts / 9 frames / 8 signed receipts.

A later opt-in source-perception workstream may nominate closed G17 flank
boxes without `area_m2`, but only after proving snapshot
`source_snapshot_3fcb6bc5c44b51d930e9600080501d27`, the 15 host identities
including 1215 members `wall_ad5e43e87149682d9900` /
`wall_f92ac8eb34b0048e144b`, and the eight signed receipts are unchanged.

## Benchmark observations that must not influence implementation

Lot16 Full Plan V2 8/27, expected BOQ, the 0621 / 1215 labels as prediction
inputs, and room names (LINEN/BROOM, ENS.) were not used to choose a host
or thickness. Signed customer receipts stay unverified here.
