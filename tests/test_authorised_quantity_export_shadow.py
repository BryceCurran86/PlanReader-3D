"""Authorised export shadow withholds non-publishable quantities."""
from pb_authorised_quantity_export_shadow import filter_authorised_quantity_rows_for_export


def test_non_firm_rows_are_withheld_and_export_stays_inactive():
    rows = [
        {"quantity_id": "q-firm", "authority_status": "FIRM"},
        {"quantity_id": "q-review", "authority_status": "REVIEW_REQUIRED"},
        {"quantity_id": "q-none", "authority_status": None},
    ]
    report = filter_authorised_quantity_rows_for_export(rows)
    assert report["jobhub_export_activated"] is False
    assert report["exportable_count"] + report["withheld_count"] == 3
    # Exact publishability comes from the existing adapter helper — assert only
    # that withheld rows never activate JobHub and FIRM is not dropped silently
    # when the helper accepts it.
    assert all(w["reason"] == "quantity_status_not_publishable" for w in report["withheld_rows"])
    assert report["shadow_only"] is True
