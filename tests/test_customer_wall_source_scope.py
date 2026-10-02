"""Customer bridge regressions; mocked claims exercise routing, not PDF accuracy.

The typed publication case uses the existing synthetic authority fixture. The
real missing-height source case remains in test_live_canonical_family_coverage.
No fixture is production truth and no missing source geometry is defaulted.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import pb_auto_geometry_v1219 as auto
from pb_live_external_physical_net_wall_publication import compose_live_external_physical_net_wall_publication
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_ag09_customer_coverage_runtime import _summary
from tests.test_customer_runtime_net_wall_and_opening_parity import _test_workspace
from tests.test_live_external_physical_net_wall_publication import _chain
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


CLAIM_TOOL = "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim"


def _claim(quantity_id="quantity:source:1", quantity=12.123456):
    return SimpleNamespace(status=EvidenceResolutionStatus.CORROBORATED,
                           quantity_id=quantity_id, quantity_m2=quantity, source_pages=(1,),
                           confidence=0.95, reason_codes=(), external_wall_ids=(quantity_id + ":wall",))


def _abstained():
    return SimpleNamespace(status=EvidenceResolutionStatus.ABSTAINED,
                           quantity_id=None, quantity_m2=None, source_pages=(),
                           confidence=0.0, reason_codes=("missing_source_geometry",))


def _page(document_id, *, page_no=1, page_id=None, text="NORTH ELEVATION", selected=1):
    return dict(id=page_id or document_id, document_id=document_id, page_no=page_no,
                page_label=f"Drawing {document_id}", page_type="Elevation",
                extracted_text=text, selected=selected)


def _app(tmp_path, sources):
    documents = []
    for document_id, content in sources:
        directory = tmp_path / str(document_id)
        directory.mkdir()
        path = directory / "same-name.pdf"
        path.write_bytes(content)
        documents.append(dict(id=document_id, path=str(path)))
    return SimpleNamespace(lquery=lambda *_: documents), documents


def _named(rows):
    return [dict(zip(auto.TAKEOFF_ROW_FIELDS, row)) for row in rows]


def test_all_selected_independent_pdfs_publish_even_with_same_filename_and_type_mark(tmp_path):
    app, documents = _app(tmp_path, [(1, b"source-a"), (2, b"source-b"), (3, b"unselected")])
    pages = [_page(1, page_no=2, text="W1 NORTH ELEVATION"), _page(2, page_no=3, text="W1 NORTH ELEVATION")]
    with patch(CLAIM_TOOL, side_effect=[_claim("qa", 12.123456), _claim("qb", 25.654321)]) as collect:
        rows, facades = auto._build_facade_rows(app, 1, pages)
    assert collect.call_count == 2
    assert collect.call_args_list[0].args == (Path(documents[0]["path"]),)
    assert collect.call_args_list[0].kwargs == {"pages": (1,)}
    assert collect.call_args_list[1].kwargs == {"pages": (2,)}
    assert [row["quantity"] for row in _named(rows)] == [12.123456, 25.654321]
    assert all(row["unit"] == "m²" for row in _named(rows))
    assert all(facade["superseded_by_physical_net_wall"] for facade in facades)


def test_byte_identical_uploads_replay_selected_page_union_once(tmp_path):
    app, _ = _app(tmp_path, [(1, b"one-physical-source"), (2, b"one-physical-source")])
    pages = [_page(1, page_no=1), _page(2, page_no=3)]
    with patch(CLAIM_TOOL, return_value=_claim()) as collect:
        rows, facades = auto._build_facade_rows(app, 1, pages)
    collect.assert_called_once()
    assert collect.call_args.kwargs == {"pages": (0, 2)}
    assert len(rows) == 1
    assert all(facade["superseded_by_physical_net_wall"] for facade in facades)
    assert app._ag09_family_coverage_by_workspace[1]["physical_net_document_ids"] == [1, 2]


@pytest.mark.parametrize("pages", [[], [_page(1, selected=0)], [_page(1, page_no=0)],
                                  [_page(1, page_no=None)], [_page(1, page_no=1.5)]])
def test_no_selected_valid_page_never_means_scan_entire_pdf(tmp_path, pages):
    app, _ = _app(tmp_path, [(1, b"unselected-source")])
    with patch(CLAIM_TOOL) as collect:
        assert auto._try_physical_net_wall_rows(app, 1, pages, []) is None
    collect.assert_not_called()
    assert app._ag09_family_coverage_by_workspace[1]["source_sha256s"] == []


def test_independent_source_quantity_id_collision_abstains_and_blocks_registered_rescue(tmp_path):
    app, _ = _app(tmp_path, [(1, b"source-a"), (2, b"source-b")])
    app.build_registered_walls_v139 = lambda _: pytest.fail("a conflicting physical identity must not fall through")
    with patch(CLAIM_TOOL, side_effect=[_claim("shared-q", 12.0), _claim("shared-q", 12.0)]):
        rows = auto._try_physical_net_wall_rows(app, 1, [_page(1), _page(2)], [])
    assert rows is None
    coverage = app._ag09_family_coverage_by_workspace[1]
    assert coverage["physical_net_document_ids"] == []
    assert "conflicting_quantity_identity_across_sources" in coverage["family_gaps"]["wall"]
    assert all(report["status"] == "review" for report in coverage["source_reports"])


@pytest.mark.parametrize("status", ["conflict", "ambiguous"])
def test_explicit_source_conflict_cannot_be_promoted_by_registered_fallback(tmp_path, status):
    app, _ = _app(tmp_path, [(1, b"contradictory-source")])
    claim = _abstained()
    claim.status = status
    app.build_registered_walls_v139 = lambda _: pytest.fail("conflicting source must remain in review")
    with patch(CLAIM_TOOL, return_value=claim):
        assert auto._try_physical_net_wall_rows(app, 1, [_page(1)], []) is None


@pytest.mark.parametrize("failed", [RuntimeError("failed source"), _abstained()])
def test_failed_or_abstained_source_does_not_drop_independent_sibling(tmp_path, failed):
    app, _ = _app(tmp_path, [(1, b"bad-source"), (2, b"good-source")])
    with patch(CLAIM_TOOL, side_effect=[failed, _claim("good-q")]) as collect:
        rows = auto._try_physical_net_wall_rows(app, 1, [_page(1), _page(2)], [])
    assert collect.call_count == 2
    assert len(rows) == 1 and "good-q" in _named(rows)[0]["source_reference"]
    assert app._ag09_family_coverage_by_workspace[1]["physical_net_document_ids"] == [2]


@pytest.mark.parametrize("quantity", [float("nan"), float("inf"), -1.0, True])
def test_invalid_positive_claim_cannot_publish(tmp_path, quantity):
    app, _ = _app(tmp_path, [(1, b"source-a")])
    with patch(CLAIM_TOOL, return_value=_claim(quantity=quantity)):
        assert auto._try_physical_net_wall_rows(app, 1, [_page(1)], []) is None


def test_unresolved_sibling_retains_its_explicit_facade_without_material_leakage(tmp_path):
    app, _ = _app(tmp_path, [(1, b"good-source"), (2, b"unresolved-source")])
    pages = [_page(1), _page(2, text="NORTH ELEVATION\nLB - LINEABOARD CLADDING 42.5 m2")]
    with patch(CLAIM_TOOL, side_effect=[_claim("good-q"), _abstained()]):
        rows, facades = auto._build_facade_rows(app, 1, pages)
    named = _named(rows)
    assert len(named) == 2
    direct = next(row for row in named if "physical_net_wall:" in row["source_reference"])
    fallback = next(row for row in named if "facade:2" in row["source_reference"])
    assert direct["substrate"] == "External walling"
    assert fallback["quantity"] == 42.5 and fallback["substrate"] == "Lineaboard Cladding"
    assert facades[0]["superseded_by_physical_net_wall"]
    assert not facades[1].get("superseded_by_physical_net_wall")


def test_unreadable_selected_pdf_is_reported_and_siblings_continue(tmp_path):
    app, documents = _app(tmp_path, [(1, b"missing"), (2, b"good")])
    Path(documents[0]["path"]).unlink()
    with patch(CLAIM_TOOL, return_value=_claim("good-q")) as collect:
        rows = auto._try_physical_net_wall_rows(app, 1, [_page(1), _page(2)], [])
    assert len(rows) == 1 and collect.call_count == 1
    assert "selected_pdf_source_unreadable:FileNotFoundError" in app._ag09_family_coverage_by_workspace[1]["family_gaps"]["wall"]


def test_scope_filters_stale_global_extractor_and_other_workspace_attachments(tmp_path):
    app, _ = _app(tmp_path, [(1, b"current-source")])
    stale = _summary()
    app.extractor = SimpleNamespace(coverage_registry_summaries_live=(stale,))
    with patch(CLAIM_TOOL, return_value=_abstained()):
        auto._try_physical_net_wall_rows(app, 1, [_page(1)], [])
    assert auto._runtime_coverage_registry_summaries(app, 1) == []
    assert auto._runtime_coverage_registry_summaries(app, 2) == []
    sha256 = hashlib.sha256(b"current-source").hexdigest()
    current = replace(stale, manifest=replace(stale.manifest, source_sha256=sha256),
                      object_universe_snapshots=tuple(replace(s, source_sha256=sha256) for s in stale.object_universe_snapshots),
                      quantity_evidence_universe_snapshots=tuple(replace(s, source_sha256=sha256) for s in stale.quantity_evidence_universe_snapshots),
                      takeoff_output_row_universe_snapshots=tuple(replace(s, source_sha256=sha256) for s in stale.takeoff_output_row_universe_snapshots),
                      object_records=tuple(replace(r, source_sha256=sha256) for r in stale.object_records))
    app.coverage_registry_summaries_live = (current,)
    assert auto._runtime_coverage_registry_summaries(app, 1) == [current]
    with patch(CLAIM_TOOL) as collect:
        auto._try_physical_net_wall_rows(app, 1, [], [])
    collect.assert_not_called()
    assert auto._runtime_coverage_registry_summaries(app, 1) == []


def _typed_publication_claim(path):
    """Existing synthetic authority fixture; never a source closure assertion."""
    # Native PDF generation assigns a new trailer id on each call. Reuse the
    # uploaded bytes so both fixture routes retain the same actual source hash.
    with patch("tests.test_live_external_physical_net_wall_publication._complete_void_pdf", return_value=path.read_bytes()):
        wall_opening, physical_void, gross, roles, _, _ = _chain()
    publication = compose_live_external_physical_net_wall_publication(
        wall_opening_composition=wall_opening, physical_void_composition=physical_void,
        gross_wall_composition=gross, whole_wall_role_composition=roles,
    )
    quantity = publication.quantity_evidence
    assert publication.status is EvidenceResolutionStatus.CORROBORATED and quantity is not None
    template = collect_live_physical_net_wall_claim(path, pages=(0,))
    return replace(template, status=publication.status, quantity_m2=quantity.value,
                   quantity_id=quantity.quantity_id, canonical_walls=publication.canonical_walls,
                   canonical_openings=(), canonical_rooms=(), canonical_floors=(),
                   external_wall_ids=publication.external_wall_ids, source_pages=(1,),
                   confidence=1.0, publication=publication)


def test_typed_original_identity_and_quantity_reach_sqlite_and_ag09_then_rerun_once():
    with _test_workspace() as ws:
        path = ws.root / "drawing.pdf"
        path.write_bytes(_complete_void_pdf())
        ws.add_document(path)
        ws.add_page(1, "Elevation", "North", "NORTH ELEVATION")
        claim = _typed_publication_claim(path)
        for _ in range(2):
            with patch(CLAIM_TOOL, return_value=claim):
                rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
            with auto._auto_publication(ws.app, 1, rows) as transaction:
                lifecycle = auto._runtime_coverage_lifecycle_report(transaction, 1)
                stored = transaction.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1")
                assert len(stored) == 1
                assert stored[0]["quantity"] == claim.publication.quantity_evidence.value
                assert stored[0]["unit"] == "m²"
                family = lifecycle["family_reports"]["wall"]
                assert family["classification"] == "CONNECTED"
                assert family["stage_counts"]["PUBLISHED"] == len(claim.canonical_walls)
                assert set(family["object_ids"]) == {wall.physical_wall_id for wall in claim.canonical_walls}
                assert all(obj["highest_stage_reached"] == "PUBLISHED"
                           for report in lifecycle["registry_reports"] for obj in report["object_reports"])
        assert len(ws.app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1")) == 1


@pytest.mark.parametrize("defect", ["value", "quantity_identity", "physical_identity", "source_hash", "page_scope"])
def test_typed_claim_must_preserve_original_publication_identity_value_and_source(tmp_path, defect):
    path = tmp_path / "drawing.pdf"
    path.write_bytes(_complete_void_pdf())
    claim = _typed_publication_claim(path)
    if defect == "value":
        claim = replace(claim, quantity_m2=claim.quantity_m2 + 0.01)
    elif defect == "quantity_identity":
        claim = replace(claim, quantity_id="unrelated-quantity-id")
    elif defect == "physical_identity":
        claim = replace(claim, external_wall_ids=("unrelated-physical-wall",))
    elif defect == "source_hash":
        claim = replace(claim, canonical_walls=tuple(replace(wall, source_sha256="f" * 64) for wall in claim.canonical_walls))
    else:
        claim = replace(claim, source_pages=(999,))
    app = SimpleNamespace(lquery=lambda *_: [{"id": 1, "path": str(path)}])
    app.build_registered_walls_v139 = lambda _: pytest.fail("a conflicting original publication must remain in review")
    with patch(CLAIM_TOOL, return_value=claim):
        assert auto._try_physical_net_wall_rows(app, 1, [_page(1)], []) is None
    coverage = app._ag09_family_coverage_by_workspace[1]
    assert coverage["physical_net_document_ids"] == []
    assert coverage["source_reports"][0]["status"] == "review"


def test_verified_precision_survives_actual_sqlite_writer_and_failed_publication_rolls_back():
    with _test_workspace() as ws:
        path = ws.root / "drawing.pdf"
        path.write_bytes(b"mock-source")
        ws.add_document(path)
        ws.add_page(1, "Elevation", "North", "NORTH ELEVATION")
        with patch(CLAIM_TOOL, return_value=_claim("original-q", 12.123456)):
            rows, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
        auto._replace_auto_rows(ws.app, 1, rows)
        stored = ws.app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1")
        assert len(stored) == 1 and stored[0]["quantity"] == 12.123456
        with patch(CLAIM_TOOL, return_value=_claim("replacement-q", 25.654321)):
            replacement, _ = auto._build_facade_rows(ws.app, 1, ws.pages())
        with pytest.raises(RuntimeError, match="report failure"):
            with auto._auto_publication(ws.app, 1, replacement):
                raise RuntimeError("report failure")
        stored = ws.app.lquery("SELECT * FROM takeoff_rows WHERE workspace_id=1")
        assert len(stored) == 1 and stored[0]["quantity"] == 12.123456
        assert "original-q" in stored[0]["source_reference"]
