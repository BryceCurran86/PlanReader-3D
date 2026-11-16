"""Private original Q5446 floor finish issuer/seaI/customer and strict source negatives.

Public CI without original PDFs skips real-source tests, not their pure-source
negatives. This test never copies private plans into GitHub.
"""
from __future__ import annotations

from pathlib import Path
import os

import fitz
import pytest

from pb_gpt1_q5446_alfresco_original_customer import (
    issue_original_q5446_alfresco_customer_area,
)
from pb_gptmax_q5446_original_tiled_floor_customer import (
    issue_original_q5446_first_ensuite_tiled_floor,
    issue_original_q5446_ground_ensuite_tiled_floor,
    issue_original_q5446_ground_laundry_tiled_floor,
)
from pb_source_native_tiled_room_face_authority import (
    find_unique_native_tiled_room_face,
)
from pb_customer_output_verification import verify_sealed_customer_output


@pytest.fixture
def originals():
    from tests.original_source_q5446 import require_original_q5446_triple
    return require_original_q5446_triple()


def test_source_native_ground_ensuite_complete_tiled_customer(originals):
    result = issue_original_q5446_ground_ensuite_tiled_floor(*originals)
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW", result.reason_codes
    q = result.quantity
    assert q is not None and q.status == "firm" and not q.abstained
    assert q.family == "floor_finish_area"
    assert q.unit == "m2"
    assert q.value == 4.247308
    assert q.metadata["semantic_finish"] == "tile"
    assert q.metadata["tiled_floor_finish_authorized"] is True
    assert q.metadata["net_internal_finished_face_authorized"] is True
    assert q.metadata["original_source_page_role"] == "ground_floor_plan"
    assert q.metadata["finish_scope_source_sha256s"]
    assert q.metadata["source_face_boundary_path_ids"]
    assert len(q.input_entity_ids) == 1
    assert result.trace is not None
    assert result.sealed_run is not None
    assert len(result.sealed_run.quantities) == 1
    assert result.sealed_run.quantities[0].lineage_ok
    assert len(result.customer_rows) == 1
    assert result.customer_rows[0]["quantity"] == q.value
    assert result.customer_rows[0]["quantity_status"] == "To review"
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_source_native_first_floor_ensuite_does_not_skip_independent_scale(originals):
    # This source face is genuine, but page-two metric authority is NOT
    # inherited from the ground-floor alfresco without its own scale proof.
    with fitz.open(originals[0]) as doc:
        face = find_unique_native_tiled_room_face(
            page=doc[1], page_number=2, room_label="ENS",
        )
    assert face is not None
    assert face.physical_source_verified is True
    assert face.commercial_permission is False


def test_original_alfresco_existing_customer_keeps_independent_signed_quantity(originals):
    result = issue_original_q5446_alfresco_customer_area(
        str(originals[0]), workspace_id=1,
    )
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
    assert result.quantity is not None
    assert result.quantity.family == "floor_area"
    assert result.quantity.value == 12.0
    assert result.sealed_run is not None
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_wrong_original_source_sha_abstains_without_customer(originals, tmp_path):
    bad = tmp_path / "tampered_source.pdf"
    bad.write_bytes(originals[0].read_bytes() + b"\n%source_modified")
    result = issue_original_q5446_ground_ensuite_tiled_floor(
        bad, originals[1], originals[2],
    )
    assert result.status == "ABSTAIN"
    assert result.reason_codes == ("original_source_sha_mismatch",)
    assert result.quantity is None and result.sealed_run is None
    assert result.customer_rows == ()


@pytest.mark.parametrize("i", [1, 2])
def test_tampered_supporting_document_abstains(originals, tmp_path, i):
    paths = list(originals)
    modified = tmp_path / f"untrusted_support_{i}.pdf"
    modified.write_bytes(paths[i].read_bytes() + b"\n%untrusted")
    paths[i] = modified
    result = issue_original_q5446_ground_ensuite_tiled_floor(*paths)
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (
        "authentic_ensuite_tiled_material_scope_unavailable",
    )
    assert result.quantity is None and result.customer_rows == ()


def test_cross_role_support_substitution_abstains(originals):
    result = issue_original_q5446_ground_ensuite_tiled_floor(
        originals[0], originals[2], originals[1],
    )
    assert result.status == "ABSTAIN"
    assert result.quantity is None


def test_no_original_or_invalid_workspace_never_claims_source(originals, tmp_path):
    missing = issue_original_q5446_ground_ensuite_tiled_floor(
        tmp_path / "absent.pdf", originals[1], originals[2],
    )
    assert missing.status == "ABSTAIN"
    bad_workspace = issue_original_q5446_ground_ensuite_tiled_floor(
        *originals, workspace_id=0,
    )
    assert bad_workspace.status == "ABSTAIN"
    assert missing.quantity is None
    assert bad_workspace.quantity is None


def test_missing_source_owned_face_prevents_customer(originals, monkeypatch):
    import pb_gptmax_q5446_original_tiled_floor_customer as target
    monkeypatch.setattr(target, "find_unique_native_tiled_room_face",
                        lambda **_kwargs: None)
    result = target.issue_original_q5446_ground_ensuite_tiled_floor(*originals)
    assert result.status == "ABSTAIN"
    assert result.reason_codes == (
        "source_tiled_ensuite_finished_face_unavailable",
    )
    assert result.sealed_run is None and result.customer_rows == ()


def test_source_native_ground_laundry_complete_tiled_customer(originals):
    result = issue_original_q5446_ground_laundry_tiled_floor(*originals)
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW", result.reason_codes
    q = result.quantity
    assert q is not None and q.status == "firm" and not q.abstained
    assert q.family == "floor_finish_area"
    assert q.unit == "m2"
    assert q.value == 4.210609
    assert q.metadata["room_label"] == "LDRY"
    assert q.metadata["semantic_finish"] == "tile"
    assert q.metadata["tiled_floor_finish_authorized"] is True
    assert q.metadata["net_internal_finished_face_authorized"] is True
    assert q.metadata["original_source_page_role"] == "ground_floor_plan"
    assert q.metadata["source_face_boundary_path_ids"]
    assert result.sealed_run is not None
    assert len(result.sealed_run.quantities) == 1
    assert result.sealed_run.quantities[0].lineage_ok
    assert len(result.customer_rows) == 1
    assert result.customer_rows[0]["quantity"] == q.value
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)


def test_source_native_first_floor_ensuite_complete_tiled_customer_with_same_page_scale(originals):
    result = issue_original_q5446_first_ensuite_tiled_floor(*originals)
    assert result.status == "FIRM_SOURCE_CUSTOMER_TO_REVIEW", result.reason_codes
    q = result.quantity
    assert q is not None and q.status == "firm" and not q.abstained
    assert q.family == "floor_finish_area"
    assert q.unit == "m2"
    assert q.value == 5.966132
    assert q.metadata["room_label"] == "ENS"
    assert q.metadata["source_page"] == "2"
    assert q.metadata["original_source_page_role"] == "first_floor_plan"
    assert any("_p2_path_" in sid for sid in q.metadata["original_scale_source_path_ids"])
    assert result.sealed_run is not None
    assert len(result.sealed_run.quantities) == 1
    assert result.sealed_run.quantities[0].lineage_ok
    assert len(result.customer_rows) == 1
    assert result.customer_rows[0]["quantity"] == q.value
    verify_sealed_customer_output(result.sealed_run, result.customer_rows)
