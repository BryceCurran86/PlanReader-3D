"""Original-PDF source declared area FIRM handoff; not construction publication."""
from hashlib import sha256

import fitz

from pb_gpt1_native_architectural_area_schedule import issue_native_scheduled_areas


def _original_like_source(*, changes=None, pages=2, opaque_mask=None):
    doc = fitz.open()
    try:
        for i in range(pages):
            p = doc.new_page(width=1190, height=842)
            p.insert_text((300, 700), "AREA CALCULATIONS", fontsize=8)
            values = ["RESIDENCE", "193.24 m2", "ALFRESCO", "28.10 m2",
                      "PORCH", "3.02 m2", "TOTAL:", "224.36 m2"]
            if changes and i in changes:
                position, value = changes[i]
                values[position] = value
            p.insert_textbox(
                fitz.Rect(300, 716, 550, 810),
                "\n".join(values), fontsize=8, lineheight=1.15,
            )
            if i == 0 and opaque_mask is not None:
                if opaque_mask == "numeric_word":
                    target = next(w for w in p.get_text("words")
                                  if w[4] == "193.24")
                    region = fitz.Rect(target[:4])
                elif opaque_mask == "whole_schedule":
                    region = fitz.Rect(295, 695, 580, 816)
                elif opaque_mask == "unrelated_late_decor":
                    region = fitz.Rect(20, 20, 70, 40)
                else:
                    raise ValueError("unrecognized paint setup")
                p.draw_rect(region, color=None, fill=(1, 1, 1), overlay=True)
        return doc.tobytes()
    finally:
        doc.close()


def _issue(raw):
    return issue_native_scheduled_areas(
        raw, expected_sha256=sha256(raw).hexdigest(),
        project_id="source-neutral-original-test", workspace_id=10,
    )


def test_two_repeated_schedule_sheets_issue_only_three_source_firm_quantities():
    raw = _original_like_source()
    report = _issue(raw)
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY", report.reason_codes
    assert len(report.rows) == len(report.quantities) == 3
    assert report.repeated_source_pages == (1, 2)
    assert [float(q.value) for q in report.quantities] == [193.24, 28.10, 3.02]
    assert float(report.total_m2) == 224.36
    assert all(q.status == "firm" and q.family == "architectural_scheduled_area"
               and q.unit == "m2" for q in report.quantities)
    assert report.sealed_run is not None
    assert report.customer_release_allowed is False
    assert report.canonical_physical_floor_bound is False
    assert all(q.metadata["commercial_projection_allowed"] is False
               and q.metadata["canonical_physical_floor_owner_authenticated"] is False
               for q in report.quantities)
    assert _issue(raw) == report



def test_later_opaque_source_paint_over_one_numeric_word_invalidates_firm():
    for mask in ("numeric_word", "whole_schedule"):
        raw = _original_like_source(opaque_mask=mask)
        with fitz.open(stream=raw, filetype="pdf") as document:
            page = document[0]
            # An occluded word remains native-extractable and trace-painted,
            # which was the exact prior false-positive source issuer.
            assert any(w[4] == "193.24" for w in page.get_text("words"))
            assert any(t["type"] == 0 and t["opacity"] == 1.0
                       for t in page.get_texttrace())
            assert page.get_bboxlog()[-1][0] == "fill-path"
        report = _issue(raw)
        assert report.status == "ABSTAIN"
        assert report.quantities == ()
        assert report.sealed_run is None
        assert not report.customer_release_allowed


def test_later_unrelated_source_fill_keeps_original_source_firm_values():
    raw = _original_like_source(opaque_mask="unrelated_late_decor")
    report = _issue(raw)
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY", report.reason_codes
    assert [float(row.value) for row in report.quantities] == [193.24, 28.10, 3.02]
    assert not report.customer_release_allowed
    assert not report.canonical_physical_floor_bound


def test_sha_pinned_lot16_original_architectural_schedule_preserves_three_not_thirteen():
    import pytest
    from pathlib import Path
    source = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
    if not source.is_file():
        pytest.skip("owner-private original Lot16 not provisioned; cannot claim original CI parity")
    raw = source.read_bytes()
    expected_sha = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
    assert sha256(raw).hexdigest() == expected_sha
    report = issue_native_scheduled_areas(
        raw, expected_sha256=expected_sha,
        project_id="source-neutral-original-test", workspace_id=10,
    )
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY", report.reason_codes
    assert report.repeated_source_pages == tuple(range(1, 14))
    assert len(report.quantities) == 3
    assert [float(q.value) for q in report.quantities] == [193.24, 28.10, 3.02]
    assert report.customer_release_allowed is False
    assert report.canonical_physical_floor_bound is False
    assert report.sealed_run is not None
    assert sha256(source.read_bytes()).hexdigest() == expected_sha


def test_single_schedule_is_one_set_not_one_per_repeated_page():
    raw = _original_like_source(pages=1)
    report = _issue(raw)
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY"
    assert len(report.quantities) == 3
    assert report.repeated_source_pages == (1,)


def test_different_original_second_sheet_printed_area_fails_closed():
    raw = _original_like_source(changes={1: (1, "193.25 m2")})
    report = _issue(raw)
    assert report.status == "ABSTAIN"
    assert report.quantities == ()
    assert report.sealed_run is None


def test_missing_source_numeric_or_rollup_fails_closed():
    for replacement in ("not on drawing", "999.99 m2"):
        raw = _original_like_source(changes={0: (7, replacement)}, pages=1)
        report = _issue(raw)
        assert report.status == "ABSTAIN"
        assert report.quantities == ()


def test_missing_separate_component_value_not_accepted():
    raw = _original_like_source(changes={0: (3, "UNMEASURED")}, pages=1)
    assert _issue(raw).quantities == ()


def test_sha_gate_rejects_original_source_substitution():
    raw = _original_like_source()
    denied = issue_native_scheduled_areas(
        raw, expected_sha256="0" * 64,
        project_id="source-neutral-original-test", workspace_id=10,
    )
    assert denied.status == "ABSTAIN"
    assert denied.quantities == ()


def test_source_document_not_promoted_for_empty_project_or_invalid_scope():
    raw = _original_like_source()
    report = issue_native_scheduled_areas(
        raw, expected_sha256=sha256(raw).hexdigest(),
        project_id="", workspace_id=10,
    )
    assert report.status == "ABSTAIN"
    assert report.quantities == ()
