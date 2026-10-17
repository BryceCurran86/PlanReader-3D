"""Original PWD figured terminal-to-face gap is not a finished-face witness."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_original_figured_extension_source_chain_shadow import (
    audit_figured_extension_to_source_face as audit,
)
PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.mark.skipif(not PDF.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_original_pwd_3570_leader_has_real_uncovered_cross_source_gap():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        row=audit(doc[25],original_dimension_line_id="d12615i0",
                  original_face_line_id="d487i0",dimension_endpoint_index=1)
        assert row["native_projected_extension_length_pdf_pts"]==59.76
        assert row["original_uncovered_projection_intervals_pdf_pts"]
        assert not row["candidate_native_ink_projection_covered"]
        assert not row["figured_face_connection_authority"]
        assert row["new_firm_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not PDF.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_original_pwd_2200_leader_has_unproven_extension_to_real_face():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as doc:
        row=audit(doc[25],original_dimension_line_id="d12656i0",
                  original_face_line_id="d514i0",dimension_endpoint_index=1)
        assert row["native_projected_extension_length_pdf_pts"]==67.44
        assert row["original_uncovered_projection_intervals_pdf_pts"]
        assert not row["physical_finished_face_or_wall_role_proven"]
        assert not row["figured_face_connection_authority"]


def _synthetic(extension_sections):
    d=fitz.open();d.new_page(width=250,height=250);p=d[0]
    p.draw_line((20,120),(20,20))
    p.draw_line((100,20),(170,20))
    for a,b in extension_sections:
        p.draw_line((a,20),(b,20))
    r=audit(p,original_dimension_line_id="d0i0",
            original_face_line_id="d1i0",dimension_endpoint_index=1)
    d.close();return r


def test_synthetic_complete_extension_is_geometric_only_not_authority():
    row=_synthetic([(20,60),(60,100)])
    assert row["candidate_native_ink_projection_covered"]
    assert row["original_uncovered_projection_intervals_pdf_pts"]==[]
    assert not row["figured_extension_source_role_proven"]
    assert not row["figured_face_connection_authority"]


def test_synthetic_split_fixture_ink_cannot_bridge_uncovered_interval():
    row=_synthetic([(20,60),(70,100)])
    assert row["original_uncovered_projection_intervals_pdf_pts"]==[[60.,70.]]
    assert not row["candidate_native_ink_projection_covered"]
    assert not row["figured_face_connection_authority"]


@pytest.mark.skipif(not PDF.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_source_projection_vs_true_contact_validation_is_fail_closed():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as d:
        with pytest.raises(ValueError,match="opposed"):
            audit(d[25],original_dimension_line_id="d12615i0",
                  original_face_line_id="d514i0",dimension_endpoint_index=1)
        with pytest.raises(ValueError,match="original_native_source_path_missing"):
            audit(d[25],original_dimension_line_id="d999999i0",
                  original_face_line_id="d487i0",dimension_endpoint_index=1)
        r=audit(d[25],original_dimension_line_id="d12615i0",
                original_face_line_id="d487i0",dimension_endpoint_index=1,
                max_source_paths=100)
        assert r["status"]=="native_source_path_cap_exceeded"
        assert not r["figured_face_connection_authority"]
