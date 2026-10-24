# Lot16 segment-parent line end-reach shadow receipt (2026-10-20)

Source SHA `10109b4b…`, page 3.

| Field | Value |
|---|---|
| unhosted openings | 6 |
| segment lines authenticated / opening | 8 |
| flank dispositions | left+right `source_primitive_unmapped` ×6 |
| segment↔W4 ID gate | `segment_line_ids_disjoint_from_w4_primitives` ×6 |
| signed_eight_retained | true |
| host_granted | false |

Interpretation: G17 derivation parents yield usable segment geometries, but their
raw primitive IDs do **not** intersect usable W4 `source_primitive_ids` (exact or
after `visible:` strip). End-reach cannot see W4-owned flank geometry until GPT MAX
closes segment↔W4 primitive identity — not proximity hosting.

Sample segment line ids: raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_thin_ink_run:955, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_thin_ink_run:958, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_wall_band_end:1325, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_wall_band_end:1332, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_wall_band_face:1467, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_wall_band_face:1468, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_wall_band_face:1486, raster_opening_primitive:59c0a519dfce190cb2637292b8f9891985e937020271b6de9965e5546d178cfe:2.0.0:raster_wall_band_face:1487
Sample W4 primitive ids: d0i0, d1002i0, d1006i0, d1010i0, d1012i0, d1022i0, d1032i0, d1042i0
