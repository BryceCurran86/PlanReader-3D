"""Twenty independent read-only consumer identity/provenance adversarial tests.

This tests the *shadow* G07/G08/G09 interpretation against the existing
authoritative V1 customer verifier. It never changes a saved signed/customer
fixture, issues producer scope, scores gold or approves commercial release.
"""
from __future__ import annotations

from copy import deepcopy

from test_gpt3_ten_customer_release_gates import _inspect, _source_and_customers


def _rows():
    source, customers = _source_and_customers()
    return source, deepcopy(customers)


def _machine_identity_stripped(row):
    row.pop("quantity_id", None)
    row.pop("commercial_projection_provenance", None)
    row.pop("notes", None)
    return row


def _g(report, gate):
    return report["gates"][gate]["passed"]


def test_01_manual_quantity_word_in_plain_notes_is_not_machine_provenance():
    source, customers = _rows()
    customers.append({"notes": "Please verify quantity with the estimator"})
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")
    assert _g(report, "G08_customer_provenance_exact_v1")


def test_02_manual_quantity_word_in_source_reference_is_not_signed_receipt():
    source, customers = _rows()
    customers.append({"source_reference": "Manual estimate of quantity of tiles"})
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")
    assert _g(report, "G08_customer_provenance_exact_v1")


def test_03_manual_structured_notes_without_adapter_are_not_machine_rows():
    source, customers = _rows()
    customers.append({"notes": '{"type":"manual","quantity":"five"}'})
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")
    assert _g(report, "G08_customer_provenance_exact_v1")


def test_04_manual_unstructured_notes_without_machine_marker_remain_manual():
    source, customers = _rows()
    customers.append({"notes": "Handwritten estimate: {not-json}"})
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")
    assert _g(report, "G08_customer_provenance_exact_v1")


def test_05_provenance_embedded_quantity_id_is_read_when_display_id_missing():
    source, customers = _rows()
    del customers[0]["quantity_id"]
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")


def test_06_signed_persisted_notes_identity_is_read_without_direct_provenance():
    source, customers = _rows()
    del customers[0]["quantity_id"]
    del customers[0]["commercial_projection_provenance"]
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")


def test_07_missing_id_with_machine_receipt_can_never_hide_as_manual():
    source, customers = _rows()
    _machine_identity_stripped(customers[0])
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")
    assert not _g(report, "G08_customer_provenance_exact_v1")


def test_08_caption_prefix_does_not_hide_original_quantity_source_marker():
    source, customers = _rows()
    row = _machine_identity_stripped(customers[0])
    row["source_reference"] = "Page 3 · QuantityEvidence forged-reference; signed=true"
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_09_extra_automated_row_without_any_quantity_id_fails_g07():
    source, customers = _rows()
    customers.append({
        "commercial_projection_provenance": {"adapter": "commercial_takeoff"},
        "notes": "",
        "source_reference": "",
    })
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_10_boolean_quantity_id_is_invalid_before_v1_bijection():
    source, customers = _rows()
    customers[0]["quantity_id"] = True
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_11_numeric_quantity_id_is_invalid_before_v1_bijection():
    source, customers = _rows()
    customers[0]["quantity_id"] = 7
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_12_padded_quantity_id_must_not_be_silently_stripped():
    source, customers = _rows()
    customers[0]["quantity_id"] = " " + customers[0]["quantity_id"] + " "
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_13_empty_identity_with_malformed_structured_provenance_fails():
    source, customers = _rows()
    row = _machine_identity_stripped(customers[0])
    row["commercial_projection_provenance"] = {"adapter": "commercial_takeoff"}
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_14_duplicate_json_provenance_key_must_fail_even_without_direct_id():
    source, customers = _rows()
    row = _machine_identity_stripped(customers[0])
    row["source_reference"] = "manual note without machine receipt"
    row["notes"] = '{"adapter":"manual","adapter":"commercial_takeoff"}'
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_15_bad_machine_notes_cannot_fall_back_to_manual_without_id():
    source, customers = _rows()
    row = _machine_identity_stripped(customers[0])
    row["notes"] = "{invalid-machine-projection"
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_16_nonmapping_customer_entry_is_rejected_before_projection():
    source, customers = _rows()
    customers.append(None)
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")
    assert not _g(report, "G08_customer_provenance_exact_v1")


def test_17_mapping_container_is_not_a_sequence_of_customer_rows():
    source, customers = _rows()
    report = _inspect(source, {"source": "not-a-customer-array"})
    assert not _g(report, "G07_customer_identity_bijection")


def test_18_missing_original_customer_row_fails_exact_bijection():
    source, customers = _rows()
    customers.pop(3)
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")
    assert report["official_four_project_coverage_accuracy"] is None


def test_19_duplicate_id_extracted_from_embedded_provenance_is_rejected():
    source, customers = _rows()
    duplicate = deepcopy(customers[0])
    duplicate.pop("quantity_id")
    customers.append(duplicate)
    report = _inspect(source, customers)
    assert not _g(report, "G07_customer_identity_bijection")


def test_20_fake_commercial_approval_with_bad_trace_never_unlocks_g09():
    source, customers = _rows()
    for row in customers:
        row["inclusion_status"] = "APPROVED"
        row["status"] = "approved"
    customers[0]["commercial_projection_provenance"]["source_trace"]["evidence_ids"][0] += "_forged"
    report = _inspect(source, customers)
    assert _g(report, "G07_customer_identity_bijection")
    assert not _g(report, "G08_customer_provenance_exact_v1")
    assert not _g(report, "G09_producer_execution_and_customer_inclusion")
    assert not _g(report, "G10_source_issuer_scope_attestation")
    assert report["customer_release_approved"] is False
    assert report["official_four_project_coverage_accuracy"] is None
