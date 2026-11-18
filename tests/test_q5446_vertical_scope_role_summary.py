"""Q5446 source-only vertical review cannot alter source-closed customer seal."""
from __future__ import annotations

from dataclasses import replace
import json

from tests.test_q5446_source_role_two_family_bridge import (
    _original_fixture, _produce,
)
from tools import q5446_source_role_customer_runtime as runtime
from pb_q5446_original_vertical_scope_authority import Q5446VerticalScopeReview


def test_source_role_attaches_abstained_scope_with_no_synthetic_promotion(
    tmp_path, monkeypatch,
):
    plan, _sha, project, prior, two, inclusions, sales = _original_fixture(
        tmp_path, monkeypatch,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_alfresco_plus_ensuite_customer",
        lambda *_args, **_kw: two,
    )
    calls = []
    def source_review(*paths):
        calls.append(paths)
        return Q5446VerticalScopeReview(
            "ABSTAINED", ("source_sha_unverified",),
        )
    monkeypatch.setattr(runtime, "inspect_original_q5446_vertical_scope",
                        source_review)
    result, folder = _produce(tmp_path, plan, project)
    assert calls == [(plan, inclusions, sales)]
    assert result["status"] == "sealed"
    assert result["verified_customer_row_count"] == 2
    assert result["benchmark_score_granted"] is False
    review = result["source_vertical_scope_review"]
    assert review["status"] == "ABSTAINED"
    assert review["physical_wall_height_authorized"] is False
    assert review["commercial_quantity_authorized"] is False
    assert (json.loads(
        (folder / "production_summary.json").read_text()
    )["source_vertical_scope_review"] == review)
    assert (folder / (project + ".json")).is_file()


def test_missing_companion_sources_do_not_attach_vertical_scope(
    tmp_path, monkeypatch,
):
    from tests.test_q5446_source_role_customer_runtime import _setup
    plan, _sha, project, _prior = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        runtime, "inspect_original_q5446_vertical_scope",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("source scope must not run without both originals"),
        ),
    )
    result, _folder = _produce(tmp_path, plan, project)
    assert result["status"] == "sealed"
    assert result["source_vertical_scope_review"] is None


def test_claimed_vertical_review_cannot_grant_unsourced_commercial_quantity(
    tmp_path, monkeypatch,
):
    plan, _sha, project, _prior, two, _incl, _sales = _original_fixture(
        tmp_path, monkeypatch,
    )
    monkeypatch.setattr(
        runtime, "issue_original_q5446_alfresco_plus_ensuite_customer",
        lambda *_args, **_kw: two,
    )
    malicious = Q5446VerticalScopeReview(
        "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW", (),
        commercial_quantity_authorized=True,
    )
    monkeypatch.setattr(
        runtime, "inspect_original_q5446_vertical_scope",
        lambda *_args: malicious,
    )
    result, output = _produce(tmp_path, plan, project)
    assert result["status"] == "no_sealable_quantities"
    assert result["benchmark_score_granted"] is False
    assert not (output / (project + ".json")).exists()


def test_real_original_vertical_scope_is_noncommercial_review(
    tmp_path, monkeypatch,
):
    from tests.original_source_q5446 import require_original_q5446_triple
    original = require_original_q5446_triple()
    q = runtime.inspect_original_q5446_vertical_scope(*original)
    assert q.status == "SOURCE_CORROBORATED_VERTICAL_SCOPE_REVIEW"
    assert q.promoted_ground_dwelling_and_garage_height_mm == 2740
    assert q.promoted_hinged_sliding_alfresco_door_height_mm == 2400
    assert q.promoted_ground_flush_panel_hinged_door_height_mm == 2340
    assert q.master_ensuite_full_height_wall_tile_scope
    assert q.standard_nonmaster_shower_recess_wall_tile_scope
    assert not q.commercial_quantity_authorized
