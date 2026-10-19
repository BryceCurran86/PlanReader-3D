from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows


def test_kind_unproven_without_token_and_single_axis_refuses_area():
    report = attach_kind_and_axis_shadows(
        opening_decisions=[{
            "physical_opening_id": "op-1",
            "first_remaining_gate": "opening_filling_kind_unproven",
            "prior_signed_quantity_id": None,
        }],
        canonical_by_id={"op-1": {
            "opening_kind": None,
            "width_record_id": None,
            "height_record_id": None,
            "width_m": None,
            "height_m": None,
        }},
        observe_rows_by_id={"op-1": {
            "original_label_dimension_result": {
                "evidence": {
                    "dimension_values_mm": [870.0],
                    "axis_order_resolved": False,
                    "area_m2": None,
                    "evidence_id": None,
                },
            },
        }},
    )
    row = report["openings"][0]
    assert row["kind_shadow"]["first_remaining_gate"] == "opening_filling_kind_unproven"
    assert row["axis_shadow"]["first_remaining_gate"] == (
        "single_figured_dimension_second_axis_unproven"
    )
    assert row["axis_shadow"]["invented_second_axis"] is False
    assert report["measurement_published"] is False


def test_pair_without_axis_order_stays_unproven():
    report = attach_kind_and_axis_shadows(
        opening_decisions=[{
            "physical_opening_id": "op-2",
            "first_remaining_gate": "width_height_axis_authority_unproven",
            "prior_signed_quantity_id": "qty-signed",
        }],
        canonical_by_id={"op-2": {
            "opening_kind": "window",
            "opening_kind_evidence_id": "kind-ev",
            "evidence_ids": ["kind-ev", "fig-1"],
            "width_record_id": None,
            "height_record_id": None,
            "width_m": None,
            "height_m": None,
        }},
        observe_rows_by_id={"op-2": {
            "original_label_dimension_result": {
                "evidence": {
                    "dimension_values_mm": [1200.0, 1500.0],
                    "axis_order_resolved": False,
                    "area_m2": 1.8,
                    "evidence_id": "fig-1",
                },
            },
        }},
    )
    row = report["openings"][0]
    assert row["kind_shadow"]["filling_kind_source_supported"] is True
    assert row["axis_shadow"]["first_remaining_gate"] == "width_height_axis_authority_unproven"
    assert row["prior_signed_quantity_id"] == "qty-signed"
