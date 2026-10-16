# Profile summary: 21675 samples

## Inclusive time per pipeline stage (a sample counts once per stage it passes through)

| stage | inclusive | share |
|---|---|---|
| W2/W3/W4 topology and wall candidates | 16552 | 76.4% |
| source ingest / visibility / snapshots | 12280 | 56.7% |
| openings (G17/host/frame/label) | 3924 | 18.1% |
| quantity generation / publication | 1761 | 8.1% |
| measurement / scale / dimensions | 945 | 4.4% |
| rooms / floors / canonical objects | 879 | 4.1% |
| raster (render, OCR, ink, G17) | 666 | 3.1% |
| viewport / title segmentation | 385 | 1.8% |
| sealing / customer verification | 1 | 0.0% |

## Self time by owning stage (leaf frame)

| stage | self | share |
|---|---|---|
| source ingest / visibility / snapshots | 8224 | 37.9% |
| W2/W3/W4 topology and wall candidates | 3987 | 18.4% |
| openings (G17/host/frame/label) | 744 | 3.4% |
| measurement / scale / dimensions | 600 | 2.8% |
| raster (render, OCR, ink, G17) | 589 | 2.7% |
| rooms / floors / canonical objects | 371 | 1.7% |
| viewport / title segmentation | 45 | 0.2% |
| other / stdlib / third-party leaf | 7075 | 32.6% |

## Top 45 functions by inclusive samples (pb_/tools only)

| function | inclusive | share |
|---|---|---|
| <module> (run_source_closed_project_handoff.py) | 20684 | 95.4% |
| main (run_source_closed_project_handoff.py) | 20642 | 95.2% |
| generate_project_handoff (run_source_closed_project_handoff.py) | 20642 | 95.2% |
| _generate_project_handoff_locked (run_source_closed_project_handoff.py) | 20642 | 95.2% |
| collect_live_physical_net_wall_claim (pb_live_physical_net_wall_integration.py) | 18409 | 84.9% |
| _from_source_visibility_producer (pb_physical_wall_candidate_authority.py) | 16452 | 75.9% |
| from_source_visibility_producer (pb_physical_wall_candidate_authority.py) | 15872 | 73.2% |
| compose_live_wall_opening_authority (pb_live_wall_opening_authority_composition.py) | 15858 | 73.2% |
| _build_scope_result (pb_physical_wall_candidate_authority.py) | 11070 | 51.1% |
| _assemble_scope_result (pb_physical_wall_candidate_authority.py) | 10535 | 48.6% |
| _producer_opening_relation_overrides (pb_physical_wall_candidate_authority.py) | 5306 | 24.5% |
| _producer_proven_page_opening_records (pb_physical_wall_candidate_authority.py) | 5252 | 24.2% |
| augment_with_raster_visible_segments (pb_source_visibility_authority.py) | 4801 | 22.1% |
| build_wall_graph_for_viewport (pb_wall_room_topology_stage_a.py) | 4324 | 19.9% |
| _point_pairs_to_segment_dicts (pb_wall_room_topology_stage_a.py) | 3457 | 15.9% |
| attach_lineage_to_split_fragments (pb_wall_room_topology_primitive_lineage.py) | 3457 | 15.9% |
| _native_dimension_source_proof_batch (pb_source_visibility_authority.py) | 2796 | 12.9% |
| publish_derived_observations (pb_source_observation_authority.py) | 2711 | 12.5% |
| authenticated_visible_observations (pb_source_visibility_authority.py) | 2397 | 11.1% |
| prove_existence (pb_physical_opening_authority.py) | 2308 | 10.6% |
| _commit (pb_source_observation_authority.py) | 2083 | 9.6% |
| sources_for_fragment (pb_wall_room_topology_primitive_lineage.py) | 1961 | 9.0% |
| fragment_contained_in_segment (pb_wall_room_topology_primitive_lineage.py) | 1882 | 8.7% |
| collect_live_ceiling_lining_claims (pb_live_ceiling_lining_integration.py) | 1720 | 7.9% |
| ingest_native_pdf_bytes (pb_source_visibility_authority.py) | 1609 | 7.4% |
| resolve (pb_source_observation_authority.py) | 1510 | 7.0% |
| clone (pb_source_observation_authority.py) | 1372 | 6.3% |
| render_native_page_png (pb_source_observation_authority.py) | 1223 | 5.6% |
| _record (pb_source_visibility_authority.py) | 1160 | 5.4% |
| _bind_record_to_snapshot (pb_source_observation_authority.py) | 1092 | 5.0% |
| _visible_candidates_for (pb_physical_opening_authority.py) | 1025 | 4.7% |
| _visible_all_structural_candidates (pb_physical_opening_authority.py) | 1023 | 4.7% |
| compose_live_physical_opening_voids (pb_live_physical_opening_void_composition.py) | 986 | 4.5% |
| run_source_owned_ceiling_lining_shadow (pb_source_owned_ceiling_lining_pipeline.py) | 898 | 4.1% |
| publish_scope (pb_physical_scale_authority.py) | 832 | 3.8% |
| native_unstroked_fill_evidence (pb_source_visibility_authority.py) | 775 | 3.6% |
| _producer_owned_points_per_mm (pb_physical_wall_candidate_authority.py) | 765 | 3.5% |
| resolve_text (pb_pdf_text_integrity_authority.py) | 764 | 3.5% |
| compose_live_canonical_rooms (pb_live_canonical_room_composition.py) | 737 | 3.4% |
| extract_native_page (pb_vector_geometry_v130.py) | 701 | 3.2% |
| _point_on_segment (pb_wall_room_topology_primitive_lineage.py) | 689 | 3.2% |
| _visible_generic_correlated_candidates (pb_physical_opening_authority.py) | 686 | 3.2% |
| publish_scope (pb_schedule_opening_instance_binding_authority.py) | 684 | 3.2% |
| ingest_native_pdf_bytes (pb_source_observation_authority.py) | 649 | 3.0% |
| isolated_lineage (pb_wall_room_topology_primitive_lineage.py) | 638 | 2.9% |

## Top 30 leaf (self) lines

| leaf | self | share |
|---|---|---|
| _bind_record_to_snapshot (pb_source_observation_authority.py:449) | 623 | 2.9% |
| fragment_contained_in_segment (pb_wall_room_topology_primitive_lineage.py:300) | 619 | 2.9% |
| page_get_textpage (extra.py:195) | 581 | 2.7% |
| clone (pb_source_observation_authority.py:423) | 538 | 2.5% |
| _gc_stage_boundary (run_source_closed_project_handoff.py:927) | 482 | 2.2% |
| fz_write_pixmap_as_png (mupdf.py:57335) | 449 | 2.1% |
| _point_on_segment (pb_wall_room_topology_primitive_lineage.py:281) | 432 | 2.0% |
| _commit (pb_source_observation_authority.py:1566) | 411 | 1.9% |
| clone (pb_source_observation_authority.py:415) | 395 | 1.8% |
| get_cdrawings (extra.py:180) | 390 | 1.8% |
| render_native_page_png (pb_source_observation_authority.py:631) | 348 | 1.6% |
| native_unstroked_fill_evidence (pb_source_visibility_authority.py:930) | 332 | 1.5% |
| authenticated_visible_observations (pb_source_visibility_authority.py:2900) | 252 | 1.2% |
| close (__init__.py:4312) | 251 | 1.2% |
| <genexpr> (pb_source_visibility_authority.py:2793) | 251 | 1.2% |
| _commit (pb_source_observation_authority.py:1602) | 247 | 1.1% |
| publish_derived_observations (pb_source_observation_authority.py:1439) | 238 | 1.1% |
| __init__ (<string>:11) | 237 | 1.1% |
| iterencode (encoder.py:263) | 225 | 1.0% |
| _record (pb_source_visibility_authority.py:2791) | 204 | 0.9% |
| authenticated_visible_observations (pb_source_visibility_authority.py:2827) | 201 | 0.9% |
| _record (pb_source_visibility_authority.py:2813) | 201 | 0.9% |
| fragment_contained_in_segment (pb_wall_room_topology_primitive_lineage.py:294) | 195 | 0.9% |
| fz_load_page (mupdf.py:50627) | 176 | 0.8% |
| _commit (pb_source_observation_authority.py:1550) | 175 | 0.8% |
| sources_for_fragment (pb_wall_room_topology_primitive_lineage.py:380) | 169 | 0.8% |
| <genexpr> (pb_raster_unchanged_band_segments.py:76) | 163 | 0.8% |
| _deepcopy_dict (copy.py:222) | 155 | 0.7% |
| deepcopy (copy.py:169) | 138 | 0.6% |
| _commit (pb_source_observation_authority.py:1580) | 136 | 0.6% |
