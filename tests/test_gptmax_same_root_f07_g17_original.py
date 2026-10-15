"""Same-root plan-view diagnostic must not elect competing/untrusted F07 products."""
from types import SimpleNamespace as NS
import pytest

import tools.diag_gptmax_same_root_f07_g17_original as diag


def view(*, vid="one", kind="floor_plan", status="derived", page=3,
         source_proof=True, authentic=True):
    return NS(view_id=vid, view_type=kind, status=status, page_number=page,
              bounding_box=(10., 20., 90., 100.),
              provenance={"source_owned_plan_view_proven": source_proof},
              authentic=authentic)


def _run(monkeypatch, views, page=3):
    monkeypatch.setattr(diag, "is_authoritative_derived_viewport",
                        lambda v: v.authentic)
    return diag.classify_live_view(views, expected_page=page)


def test_unique_same_root_candidate_is_still_not_host_or_count(monkeypatch):
    r = _run(monkeypatch, [view()])
    assert r["status"] == "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY"
    assert r["reason"] == "cross_family_physical_instance_correspondence_unproven"
    assert r["selected_view_id"] == "one"
    assert r["selected_bbox_pt"] == [10., 20., 90., 100.]


def test_unsupported_legend_does_not_hide_unique_floor_plan(monkeypatch):
    r = _run(monkeypatch, [view(vid="legend",kind="legend",status="unsupported",authentic=False),
                           view()])
    assert r["status"] == "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY"
    assert len(r["views"]) == 2


def test_competing_authentic_plan_cannot_be_elected_by_first_or_largest(monkeypatch):
    a=view();b=view(vid="other")
    assert _run(monkeypatch, [a,b])["status"] == "ABSTAIN"
    assert _run(monkeypatch, [b,a])["status"] == "ABSTAIN"


@pytest.mark.parametrize("bad", [
    {"kind":"legend"},
    {"status":"unsupported"},
    {"source_proof":False},
    {"authentic":False},
])
def test_unproved_original_plan_abstains(monkeypatch,bad):
    assert _run(monkeypatch,[view(**bad)])["status"]=="ABSTAIN"


def test_foreign_page_source_product_abstains(monkeypatch):
    r = _run(monkeypatch, [view(page=4),view()])
    assert r["status"] == "ABSTAIN"
    assert r["reason"] == "foreign_page_view"


@pytest.mark.parametrize("page", ["0","03","-1","bad",3,True])
def test_noncanonical_original_pdf_page_is_rejected_before_ingest(page):
    with pytest.raises((ValueError,TypeError)):
        diag.replay_original_live_f07_g17(b"original source",page_id=page,
                                          expected_sha256="other")


def test_original_source_digest_conflict_rejected_before_producer():
    with pytest.raises(ValueError,match="SHA256"):
        diag.replay_original_live_f07_g17(
            b"original bytes",page_id="3",expected_sha256="0"*64)
