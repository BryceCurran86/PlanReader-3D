"""Optional original-source regression: skipped (NOT VERIFIED) unless a private drawing is supplied.

The drawing, its SHA, the pages and the pattern/token/quanta are test PARAMETERS taken from the environment;
nothing here names a project, a file or a benchmark value, and nothing is asserted about quantities, tags or which
strip should correspond. The checks are structural: ownership, grants, claim fidelity to the nominator, the stroke
inventory the producer authenticated, replay, and that a CANDIDATE never carries an unvetoed rival.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow
import pb_source_plan_glazing_strip_callout_shadow as nominator
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer

_ENV = "PLANREADER_PLAN_CALLOUT_STRIP_ORIGINAL"       # the nominator's own parameters: {"pdf","sha256","plan_page",...}


def _parameters():
    raw = os.environ.get(_ENV)
    if not raw:
        pytest.skip(f"NOT VERIFIED: set {_ENV} to a JSON parameter object to run the original-source regression")
    params = json.loads(raw)
    path = Path(params["pdf"])
    if not path.is_file():
        pytest.skip("NOT VERIFIED: the original drawing is not present on this machine")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != params["sha256"]:
        pytest.fail("the supplied drawing does not match the pinned SHA-256")
    return params, data


@pytest.fixture(scope="module", params=[(False, False), (True, False), (True, True)],
                ids=["faithful", "backdrop-withheld", "backdrop-and-terminal-adjacent-withheld"])
def original(request):
    params, data = _parameters()
    source = SourceVisibilityProducer(
        producer_method="strip-whole-aperture-original-test", producer_version="1",
        source_native_finish_text_shadow=bool(params.get("native_finish_text_shadow", True)))
    published = source.ingest_native_pdf_bytes(
        document_id=f"original:{params['sha256'][:32]}", source_bytes=data, source_locator="memory://original.pdf",
        page_ids=(params["plan_page"], params["elevation_page"]))
    receipt = nominator.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=params["plan_page"],
        elevation_page_id=params["elevation_page"], callout_mark_pattern=params["callout_mark_pattern"],
        panel_token=params["panel_token"], coordinate_quantum_pt=params["coordinate_quantum_pt"],
        dimension_quantum_mm=params["dimension_quantum_mm"])
    nominations = shadow.nominations_from_callout_receipt(receipt)
    if not nominations:
        pytest.skip("NOT VERIFIED: the nominator corresponded no strip on this tree, so there is nothing to relate")
    out = shadow.StripWholeApertureCorrespondenceShadow(
        source, enabled=True, withhold_backdrop_fills=request.param[0],
        withhold_terminal_adjacent_fills=request.param[1]).audit(
        revision_id=published.revision.revision_id, plan_page_id=params["plan_page"], nominations=nominations,
        coordinate_quantum_pt=params["coordinate_quantum_pt"])
    return params, source, published, nominations, out, request.param


def test_ownership_and_grants_belong_to_the_producer(original):
    params, source, published, nominations, out, options = original
    assert out.ownership.source_sha256 == params["sha256"] == published.revision.source_sha256
    assert out.ownership.snapshot_id == published.snapshot.snapshot_id and out.ownership.page_id == str(params["plan_page"])
    assert out.shadow_only is True and all(getattr(out, name) is False for name in shadow._GRANT_FLAGS)
    assert out.standing_limits == shadow.STANDING_LIMITS
    assert out.input_provenance == (
        shadow._PROVENANCE_BY_OPTIONS[options])


def test_every_nominated_strip_is_answered_once_with_the_nominators_claims(original):
    params, source, published, nominations, out, options = original
    assert [c.strip_id for c in out.correspondences] == [n.strip_id for n in nominations]
    assert [c.claims for c in out.correspondences] == [n.claims for n in nominations]


def test_the_producer_authenticated_every_stroke_it_gave_the_authority(original):
    params, source, published, nominations, out, options = original
    counts = dict(out.stroke_counts)
    admitted = counts.get("stroked", 0) + counts.get("fill_only", 0)
    assert admitted > 0
    for key in ("primitive_join_failed", "drawing_join_failed", "visible_observation_unresolved",
                "stroke_width_unresolved", "stroke_colour_unresolved"):
        assert counts.get(key, 0) == 0, (key, counts)


def test_a_candidate_never_carries_an_unvetoed_rival_or_a_missing_linkage(original):
    params, source, published, nominations, out, options = original
    for c in out.correspondences:
        if c.status is EvidenceResolutionStatus.CANDIDATE:
            assert len(c.equal_record_ids) == 1 and c.unvetoed_rival_record_ids == () and c.linkage_basis is not None
        else:
            assert c.reason_codes and c.linkage_basis is None


def test_replay_gives_the_identical_result(original):
    params, source, published, nominations, out, options = original
    again = shadow.StripWholeApertureCorrespondenceShadow(
        source, enabled=True, withhold_backdrop_fills=options[0], withhold_terminal_adjacent_fills=options[1]).audit(
        revision_id=published.revision.revision_id, plan_page_id=params["plan_page"], nominations=nominations,
        coordinate_quantum_pt=params["coordinate_quantum_pt"])
    assert again == out


def test_withheld_backdrop_fills_are_only_ever_fill_edges_the_producer_saw_and_are_reported(original):
    params, source, published, nominations, out, options = original
    counts = dict(out.stroke_counts)
    withheld = counts.get("backdrop_fill_edge_withheld", 0)
    adjacent = counts.get("terminal_adjacent_fill_edge_withheld", 0)
    assert (adjacent > 0) is (shadow.TERMINAL_ADJACENT_FILL_EDGES_WITHHELD in out.page_reason_codes)
    if not options[1]:
        assert adjacent == 0
    if not options[0]:
        assert withheld == 0 and shadow.BACKDROP_FILL_EDGES_WITHHELD not in out.page_reason_codes
    else:
        assert 0 <= withheld + adjacent <= counts.get("fill_only", 0)
        assert (shadow.BACKDROP_FILL_EDGES_WITHHELD in out.page_reason_codes) is (withheld > 0)
    for n, c in zip(nominations, out.correspondences):
        if c.status is EvidenceResolutionStatus.CANDIDATE:
            assert any(options) or not (withheld or adjacent)     # a CANDIDATE never rests on withheld input unless asked
