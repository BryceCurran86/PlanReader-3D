"""Regression: the shadow diff selects its wall scope from the producer's CURRENT published snapshot.

Confirmed defect (found on a real /Rotate 90 plan set): ``_page_report`` read the snapshot id from the
object returned by ingest, but building the wall authority runs ``augment_with_raster_visible_segments``,
which publishes a NEWER snapshot (B) for the same revision and keys every wall scope by it. A selector
built from the ingest-time snapshot (A) resolved to ``physical_wall_candidate_scope_unavailable`` with no
walls while ``pipeline_status`` stayed ``ok`` and ``cross_check`` stayed ``match``.

The fixture is a raster-only page (an embedded image of wall-like line pairs, no vector strokes), so the
REAL augmentation path runs and publishes snapshot B. Nothing about snapshots is mocked. Synthetic fixtures
only; this proves the harness, not any real-source result.
"""
from __future__ import annotations

import json
import types

import cv2
import fitz
import numpy as np
import pytest

import pb_physical_wall_candidate_authority as pw
from page_frame_test_support import DOC_ID, build_sheet
from pb_source_visibility_authority import SourceVisibilityProducer
from scripts import page_frame_wall_boundary_shadow_diff as D

RESOLVED = pw.PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
UNAVAILABLE = pw.PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE


def raster_only_sheet(rotation: int = 0) -> bytes:
    """A4 page holding only a 144 dpi bitmap: a double-line room outline plus a double-line partition."""
    width_px, height_px = 1190, 1684
    image = np.full((height_px, width_px), 255, np.uint8)
    for x0, y0, x1, y1 in ((200, 300, 1000, 1200), (224, 324, 976, 1176)):
        cv2.rectangle(image, (x0, y0), (x1, y1), 0, 3)
    for x in (600, 624):
        cv2.line(image, (x, 324), (x, 1176), 0, 3)
    ok, png = cv2.imencode(".png", image)
    assert ok
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    page.insert_image(page.rect, stream=png.tobytes())
    if rotation:
        page.set_rotation(rotation)
    data = doc.tobytes()
    doc.close()
    return data


def _pipeline(data: bytes):
    """Mirror run_shadow_diff's setup, exposing the ingest-time snapshot A."""
    src = SourceVisibilityProducer(producer_method=D.PRODUCER_METHOD, producer_version="1")
    pub = src.ingest_native_pdf_bytes(document_id=DOC_ID, source_bytes=data, source_locator=D.SOURCE_LOCATOR)
    snapshot_a = pub.snapshot.snapshot_id
    auth = pw.PhysicalWallCandidateProducer.from_source_visibility_producer(src).authority()
    return src, pub, auth, snapshot_a


def _lookup(auth, published, page_no: int = 1):
    selector = pw.PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=str(page_no),
        decision_scope_id=f"wall-source:page-{page_no}",
    )
    result = auth.resolve_scope(selector)
    return tuple(result.reason_codes), len(result.records)


def _report(src, pub, auth, data: bytes, page_no: int = 1) -> dict:
    document = fitz.open(stream=data, filetype="pdf")
    try:
        return D._page_report(src=src, pub=pub, pdf_bytes=data, document=document, page_no=page_no, auth=auth)
    finally:
        document.close()


# ---- 1. snapshot A exists, augmentation publishes B, and A really yields no walls --------------------------------
@pytest.mark.parametrize("rotation", (0, 90))
def test_real_augmentation_publishes_snapshot_b_and_the_stale_snapshot_a_resolves_to_zero_walls(rotation):
    data = raster_only_sheet(rotation)
    src, pub, auth, snapshot_a = _pipeline(data)
    current = src.published_snapshot_for_revision(pub.revision.revision_id)
    snapshot_b = current.snapshot.snapshot_id
    assert snapshot_a != snapshot_b  # augmentation published a newer snapshot for the same revision
    assert pub.snapshot.snapshot_id == snapshot_a  # the ingest-time object still carries A
    assert current.revision == pub.revision
    codes_a, walls_a = _lookup(auth, pub)
    assert codes_a == (UNAVAILABLE,) and walls_a == 0  # what the unpatched script would have used
    codes_b, walls_b = _lookup(auth, current)
    assert RESOLVED in codes_b and UNAVAILABLE not in codes_b and walls_b > 0  # the actual wall scope


# ---- 2. the patched _page_report consumes B and resolves the scope -------------------------------------------------
@pytest.mark.parametrize("rotation", (0, 90))
def test_page_report_given_the_stale_ingest_object_consumes_snapshot_b_and_resolves_the_wall_scope(rotation):
    data = raster_only_sheet(rotation)
    src, pub, auth, snapshot_a = _pipeline(data)
    snapshot_b = src.published_snapshot_for_revision(pub.revision.revision_id).snapshot.snapshot_id
    expected_walls = _lookup(auth, src.published_snapshot_for_revision(pub.revision.revision_id))[1]
    report = _report(src, pub, auth, data)  # pub is the STALE ingest-time object (snapshot A)
    assert report["snapshot_id_at_ingest"] == snapshot_a
    assert report["snapshot_id_consumed"] == snapshot_b and snapshot_a != snapshot_b
    assert report["snapshot_refreshed"] is True
    assert report["scope_resolution_status"] == D.SCOPE_RESOLVED and report["comparison_valid"] is True
    assert report["pipeline_status"] == "ok"
    assert RESOLVED in report["scope_reason_codes"] and UNAVAILABLE not in report["scope_reason_codes"]
    assert report["summary"]["walls"] == expected_walls > 0
    assert report["frame"]["status"] == "raw" and report["frame"]["rotation"] == rotation


def test_run_shadow_diff_reports_the_consumed_snapshot_and_no_unresolved_pages():
    report = D.run_shadow_diff(raster_only_sheet(90), document_id=DOC_ID)
    page = report["pages"][0]
    assert report["schema_version"] == D.SHADOW_DIFF_SCHEMA_VERSION == "1.1.0"
    assert report["snapshot_id_at_ingest"] == page["snapshot_id_at_ingest"]
    assert report["snapshot_id_consumed"] == page["snapshot_id_consumed"] != report["snapshot_id_at_ingest"]
    assert report["unresolved_pages"] == []
    assert page["comparison_valid"] is True and page["summary"]["walls"] > 0


# ---- 3. the old behaviour (selecting from A) can no longer masquerade as a successful result ---------------------
def test_selecting_from_the_stale_snapshot_is_reported_as_unresolved_never_as_ok_or_match(monkeypatch):
    data = raster_only_sheet(90)
    src, pub, auth, snapshot_a = _pipeline(data)
    monkeypatch.setattr(D, "_current_published", lambda _src, stale: (stale, None))  # the pre-fix behaviour
    report = _report(src, pub, auth, data)
    assert report["snapshot_id_consumed"] == snapshot_a and report["snapshot_refreshed"] is False
    assert report["scope_reason_codes"] == [UNAVAILABLE]
    assert report["pipeline_status"] == D.PIPELINE_SCOPE_UNRESOLVED != "ok"
    assert report["scope_resolution_status"] == D.SCOPE_UNRESOLVED
    assert report["comparison_valid"] is False
    assert report["cross_check"] == "not_run" != "match"
    assert report["walls"] == [] and report["summary"]["walls"] == 0
    assert report["consumer_width"] is None and report["consumer_height"] is None
    assert report["frame"]["status"] == "raw"  # the descriptor is independent of the consumer


def test_an_unresolved_page_cannot_feed_a_zero_difference_claim(monkeypatch):
    monkeypatch.setattr(D, "_current_published", lambda _src, stale: (stale, None))
    report = D.run_shadow_diff(raster_only_sheet(90), document_id=DOC_ID)
    assert report["unresolved_pages"] == [1]
    page = report["pages"][0]
    assert page["comparison_valid"] is False and page["summary"]["divergent_default_tol"] == 0  # a bare zero ...
    with pytest.raises(ValueError):  # ... is refused wherever it could be read as "no difference"
        D.label_page_report(page, {"w": ((10.0, 10.0), (500.0, 500.0), "EI")})
    with pytest.raises(ValueError):
        D.rotation_equivalence({0: page, 90: page}, column="current_decision")


# ---- 4. an unresolvable published snapshot fails closed ---------------------------------------------------------------
def _missing(_revision_id):
    return None


def _boom(_revision_id):
    raise RuntimeError("synthetic lookup failure")


def _foreign(_revision_id):
    revision = types.SimpleNamespace(document_id=DOC_ID, source_sha256="0" * 64, revision_id="source_revision_other")
    return types.SimpleNamespace(revision=revision, snapshot=types.SimpleNamespace(snapshot_id="source_snapshot_other"))


@pytest.mark.parametrize(
    "lookup,reason",
    [
        (_missing, "published_snapshot_missing"),
        (_boom, "published_snapshot_lookup_error:RuntimeError"),
        (_foreign, "published_snapshot_ownership_mismatch"),
    ],
)
def test_unresolvable_published_snapshot_fails_closed(monkeypatch, lookup, reason):
    data = raster_only_sheet(0)
    src, pub, auth, snapshot_a = _pipeline(data)
    monkeypatch.setattr(src, "published_snapshot_for_revision", lookup)
    report = _report(src, pub, auth, data)
    assert report["pipeline_status"] == f"{D.PIPELINE_SNAPSHOT_UNRESOLVED}:{reason}"
    assert report["scope_resolution_status"] == D.SCOPE_SNAPSHOT_UNRESOLVED
    assert report["snapshot_id_at_ingest"] == snapshot_a
    assert report["snapshot_id_consumed"] is None and report["snapshot_refreshed"] is None
    assert report["comparison_valid"] is False and report["cross_check"] == "not_run"
    assert report["walls"] == [] and report["scope_reason_codes"] == []
    assert report["frame"]["status"] == "raw"


# ---- 5. pages without augmentation are unchanged; no mutation; CLI signals unresolved pages ------------------------
def test_vector_page_without_augmentation_keeps_one_snapshot_and_a_valid_comparison():
    data = build_sheet(90)
    src, pub, auth, snapshot_a = _pipeline(data)
    assert src.published_snapshot_for_revision(pub.revision.revision_id).snapshot.snapshot_id == snapshot_a
    report = _report(src, pub, auth, data)
    assert report["snapshot_refreshed"] is False and report["snapshot_id_consumed"] == snapshot_a
    assert report["scope_resolution_status"] == D.SCOPE_RESOLVED and report["comparison_valid"] is True
    assert report["pipeline_status"] == "ok" and report["cross_check"] == "match" and report["summary"]["walls"] > 0


def test_refresh_does_not_mutate_the_producer_or_the_ingest_object():
    data = raster_only_sheet(0)
    src, pub, auth, snapshot_a = _pipeline(data)
    current_before = src.published_snapshot_for_revision(pub.revision.revision_id)
    before = (pub.snapshot.snapshot_id, current_before.snapshot.snapshot_id, tuple(current_before.visible_observation_ids))
    _report(src, pub, auth, data)
    _report(src, pub, auth, data)
    current_after = src.published_snapshot_for_revision(pub.revision.revision_id)
    assert current_after is current_before
    assert before == (pub.snapshot.snapshot_id, current_after.snapshot.snapshot_id, tuple(current_after.visible_observation_ids))


def test_replay_of_the_refreshed_report_is_deterministic():
    data = raster_only_sheet(90)
    first = D.render_json(D.run_shadow_diff(data, document_id=DOC_ID))
    second = D.render_json(D.run_shadow_diff(data, document_id=DOC_ID))
    assert first == second and json.loads(first)["unresolved_pages"] == []


def test_cli_warns_on_stderr_only_when_pages_are_unresolved(monkeypatch, tmp_path, capsys):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(raster_only_sheet(0))
    assert D.main(["--pdf", str(pdf), "--document-id", DOC_ID]) == 0
    captured = capsys.readouterr()
    assert captured.err == "" and json.loads(captured.out)["unresolved_pages"] == []
    monkeypatch.setattr(D, "_current_published", lambda _src, stale: (stale, None))
    assert D.main(["--pdf", str(pdf), "--document-id", DOC_ID]) == 0
    captured = capsys.readouterr()
    assert "NO resolved wall scope" in captured.err and json.loads(captured.out)["unresolved_pages"] == [1]
