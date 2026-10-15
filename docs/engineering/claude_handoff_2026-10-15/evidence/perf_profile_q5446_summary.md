# Profile summary: 9579 samples

## Inclusive time per pipeline stage (a sample counts once per stage it passes through)

| stage | inclusive | share |
|---|---|---|
| source ingest / visibility / snapshots | 7592 | 79.3% |
| W2/W3/W4 topology and wall candidates | 4849 | 50.6% |
| quantity generation / publication | 1211 | 12.6% |
| measurement / scale / dimensions | 797 | 8.3% |
| openings (G17/host/frame/label) | 496 | 5.2% |
| raster (render, OCR, ink, G17) | 447 | 4.7% |
| viewport / title segmentation | 58 | 0.6% |
| rooms / floors / canonical objects | 19 | 0.2% |

## Self time by owning stage (leaf frame)

| stage | self | share |
|---|---|---|
| source ingest / visibility / snapshots | 5004 | 52.2% |
| W2/W3/W4 topology and wall candidates | 478 | 5.0% |
| measurement / scale / dimensions | 400 | 4.2% |
| raster (render, OCR, ink, G17) | 378 | 3.9% |
| openings (G17/host/frame/label) | 121 | 1.3% |
| quantity generation / publication | 3 | 0.0% |
| other / stdlib / third-party leaf | 3145 | 32.8% |

## Top 45 functions by inclusive samples (pb_/tools only)

| function | inclusive | share |
|---|---|---|
| <module> (run_source_closed_project_handoff.py) | 9055 | 94.5% |
| main (run_source_closed_project_handoff.py) | 8985 | 93.8% |
| generate_project_handoff (run_source_closed_project_handoff.py) | 8985 | 93.8% |
| _generate_project_handoff_locked (run_source_closed_project_handoff.py) | 8985 | 93.8% |
| collect_live_physical_net_wall_claim (pb_live_physical_net_wall_integration.py) | 7399 | 77.2% |
| compose_live_wall_opening_authority (pb_live_wall_opening_authority_composition.py) | 6238 | 65.1% |
| _from_source_visibility_producer (pb_physical_wall_candidate_authority.py) | 4824 | 50.4% |
| from_source_visibility_producer (pb_physical_wall_candidate_authority.py) | 4553 | 47.5% |
| publish_derived_observations (pb_source_observation_authority.py) | 3159 | 33.0% |
| augment_with_raster_visible_segments (pb_source_visibility_authority.py) | 2823 | 29.5% |
| ingest_native_pdf_bytes (pb_source_visibility_authority.py) | 2281 | 23.8% |
| _commit (pb_source_observation_authority.py) | 2277 | 23.8% |
| _build_scope_result (pb_physical_wall_candidate_authority.py) | 1764 | 18.4% |
| augment_with_raster_opening_primitives (pb_source_visibility_authority.py) | 1405 | 14.7% |
| collect_live_ceiling_lining_claims (pb_live_ceiling_lining_integration.py) | 1144 | 11.9% |
| ingest_native_pdf_bytes (pb_source_observation_authority.py) | 916 | 9.6% |
| _assemble_scope_result (pb_physical_wall_candidate_authority.py) | 912 | 9.5% |
| clone (pb_source_observation_authority.py) | 834 | 8.7% |
| render_native_page_png (pb_source_observation_authority.py) | 767 | 8.0% |
| resolve (pb_source_observation_authority.py) | 764 | 8.0% |
| _producer_owned_points_per_mm (pb_physical_wall_candidate_authority.py) | 761 | 7.9% |
| publish_scope (pb_physical_scale_authority.py) | 761 | 7.9% |
| _producer_opening_relation_overrides (pb_physical_wall_candidate_authority.py) | 499 | 5.2% |
| _producer_proven_page_opening_records (pb_physical_wall_candidate_authority.py) | 495 | 5.2% |
| authenticated_visible_observations (pb_source_visibility_authority.py) | 492 | 5.1% |
| _visible_segments (pb_physical_scale_authority.py) | 448 | 4.7% |
| _decode_native_page_for_cache (pb_source_observation_authority.py) | 435 | 4.5% |
| extract_native_page (pb_vector_geometry_v130.py) | 422 | 4.4% |
| _gc_stage_boundary (run_source_closed_project_handoff.py) | 396 | 4.1% |
| _bind_record_to_snapshot (pb_source_observation_authority.py) | 379 | 4.0% |
| resolve_visible (pb_source_visibility_authority.py) | 375 | 3.9% |
| build_wall_graph_for_viewport (pb_wall_room_topology_stage_a.py) | 365 | 3.8% |
| detect_raster_opening_source_primitives (pb_raster_opening_source_primitives.py) | 328 | 3.4% |
| _point_pairs_to_segment_dicts (pb_wall_room_topology_stage_a.py) | 314 | 3.3% |
| attach_lineage_to_split_fragments (pb_wall_room_topology_primitive_lineage.py) | 314 | 3.3% |
| _derive_visibility_page (pb_source_visibility_authority.py) | 293 | 3.1% |
| _bar_candidates (pb_physical_scale_authority.py) | 287 | 3.0% |
| from_opening_local_supplemental_source_visibility_producer (pb_physical_wall_candidate_authority.py) | 280 | 2.9% |
| prove_existence (pb_physical_opening_authority.py) | 272 | 2.8% |
| exact_ticks_for_endpoint (pb_physical_scale_authority.py) | 237 | 2.5% |
| classify_native_word_integrity (pb_pdf_text_integrity_authority.py) | 235 | 2.5% |
| detect_unchanged_terminal_band_segments (pb_raster_unchanged_band_segments.py) | 230 | 2.4% |
| _record (pb_source_visibility_authority.py) | 225 | 2.3% |
| _native_dimension_source_proof_batch (pb_source_visibility_authority.py) | 219 | 2.3% |
| _visibility_status (pb_pdf_text_integrity_authority.py) | 216 | 2.3% |

## Top 30 leaf (self) lines

| leaf | self | share |
|---|---|---|
| _commit (pb_source_observation_authority.py:1566) | 445 | 4.6% |
| _gc_stage_boundary (run_source_closed_project_handoff.py:927) | 396 | 4.1% |
| fz_write_pixmap_as_png (mupdf.py:57335) | 299 | 3.1% |
| clone (pb_source_observation_authority.py:423) | 295 | 3.1% |
| render_native_page_png (pb_source_observation_authority.py:631) | 273 | 2.8% |
| _commit (pb_source_observation_authority.py:1602) | 254 | 2.7% |
| __init__ (<string>:11) | 247 | 2.6% |
| clone (pb_source_observation_authority.py:415) | 240 | 2.5% |
| _commit (pb_source_observation_authority.py:1550) | 208 | 2.2% |
| iterencode (encoder.py:263) | 201 | 2.1% |
| publish_derived_observations (pb_source_observation_authority.py:1439) | 195 | 2.0% |
| _bind_record_to_snapshot (pb_source_observation_authority.py:449) | 175 | 1.8% |
| page_get_textpage (extra.py:195) | 160 | 1.7% |
| get_cdrawings (extra.py:180) | 155 | 1.6% |
| _commit (pb_source_observation_authority.py:1551) | 140 | 1.5% |
| _commit (pb_source_observation_authority.py:1580) | 130 | 1.4% |
| <genexpr> (pb_source_observation_authority.py:1495) | 115 | 1.2% |
| _commit (pb_source_observation_authority.py:1524) | 111 | 1.2% |
| clone (pb_source_observation_authority.py:414) | 99 | 1.0% |
| _content_sha256 (pb_source_observation_authority.py:172) | 93 | 1.0% |
| detect_raster_opening_source_primitives (pb_raster_opening_source_primitives.py:333) | 79 | 0.8% |
| render_native_page_png (pb_source_observation_authority.py:630) | 76 | 0.8% |
| <genexpr> (pb_raster_unchanged_band_segments.py:76) | 72 | 0.8% |
| _commit (pb_source_observation_authority.py:1523) | 70 | 0.7% |
| _replace (dataclasses.py:1679) | 64 | 0.7% |
| publish_derived_observations (pb_source_observation_authority.py:1474) | 63 | 0.7% |
| publish_derived_observations (pb_source_observation_authority.py:1473) | 62 | 0.6% |
| __init__ (<string>:3) | 62 | 0.6% |
| dumps (__init__.py:242) | 61 | 0.6% |
| fz_run_display_list (mupdf.py:55118) | 61 | 0.6% |
