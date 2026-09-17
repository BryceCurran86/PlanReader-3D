"""Item 29 — source-backed secondary-footprint authority red team V2.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

The production contract is deliberately rooted in immutable PDF ingestion:

    PDF bytes -> SourceVisibilityProducer -> SecondaryFootprintProducer
              -> selector-only publish/resolve

No caller polygon, category, width, area, confidence, evidence list, mapping,
probe flag, or test-specific red-team API may mint positive authority.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_secondary_footprint_evidence import resolve_secondary_footprint_width_m
from pb_source_visibility_authority import SourceVisibilityProducer


MODULE_NAME = "pb_secondary_footprint_authority"
HAS_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_AUTHORITY,
    strict=True,
    reason="source-backed Item 29 authority is intentionally absent on current main",
)


def _draw_depth(
    page: fitz.Page,
    *,
    x: float,
    y0: float,
    y1: float,
    text: str,
    witness_main: bool = True,
    witness_outer: bool = True,
) -> None:
    page.draw_line((x, y0), (x, y1))
    if witness_main:
        page.draw_line((x - 18, y0), (x + 18, y0))
    if witness_outer:
        page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=10, rotate=90)


def _source_pdf(
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    depth_text: str = "1800",
    second_depth_text: str | None = None,
    include_depth: bool = True,
    witness_main: bool = True,
    witness_outer: bool = True,
    regex_only_text: str | None = None,
) -> bytes:
    """Gold-free synthetic plan with an attached verandah and graphic scale bar."""
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)

    # Primary plan rectangle and attached secondary footprint.
    x0, y0, x1, y1 = 80 + dx, 80 + dy, 500 + dx, 300 + dy
    vy1 = 365 + dy
    page.draw_rect(fitz.Rect(x0, y0, x1, y1))
    page.draw_line((x0, y1), (x0, vy1))
    page.draw_line((x1, y1), (x1, vy1))
    page.draw_line((x0, vy1), (x1, vy1))
    page.insert_text((x0 + 20, y1 - 12), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text(((x0 + x1) / 2.0 - 30, y1 + 38), "VERANDAH", fontsize=10)
    page.insert_text((x0 + 20, y0 + 30), "150 5,700 150", fontsize=10)

    # F.23 orthogonal figured depth with both boundary witnesses.
    if include_depth:
        x = (x0 + x1) / 2.0
        d0, d1 = y1 + 5, y1 + 55
        _draw_depth(
            page,
            x=x,
            y0=d0,
            y1=d1,
            text=depth_text,
            witness_main=witness_main,
            witness_outer=witness_outer,
        )
        if second_depth_text is not None:
            _draw_depth(
                page,
                x=x + 65,
                y0=d0,
                y1=d1,
                text=second_depth_text,
            )

    if regex_only_text:
        page.insert_text((x0 + 150, y0 + 40), regex_only_text, fontsize=10)

    # Authenticated graphic scale-bar shape: baseline + two crossing ticks +
    # physical endpoint labels. Ratio text is intentionally unnecessary.
    sx0, sx1, sy = x0 + 20, x0 + 120, y0 + 75
    page.draw_line((sx0, sy), (sx1, sy))
    page.draw_line((sx0, sy - 8), (sx0, sy + 8))
    page.draw_line((sx1, sy - 8), (sx1, sy + 8))
    page.insert_text((sx0 - 3, sy + 20), "0", fontsize=8)
    page.insert_text((sx1 - 5, sy + 20), "1m", fontsize=8)

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(
        producer_method="item29_source_backed_redteam_v2",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="doc-secondary",
        source_bytes=pdf_bytes,
        source_locator="memory:item29-redteam.pdf",
    )
    return source, published


def _f23(pdf_bytes: bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return resolve_secondary_footprint_width_m(doc[0], page_num=1)
    finally:
        doc.close()


def _future_selector(mod, published, *, viewport_id: str | None):
    return mod.SecondaryFootprintSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport_id,
        secondary_space_id="verandah-1",
    )


def _future_resolve(pdf_bytes: bytes):
    mod = importlib.import_module(MODULE_NAME)
    source, published = _ingest(pdf_bytes)
    width = _f23(pdf_bytes)
    viewport_id = None if width is None else width.view_id
    selector = _future_selector(mod, published, viewport_id=viewport_id)
    producer = mod.SecondaryFootprintProducer.from_source_visibility_producer(source)
    producer.publish(selector)
    return producer.authority().resolve(selector), selector


# ---------------------------------------------------------------------------
# Current-main source behavior — GREEN
# ---------------------------------------------------------------------------


def test_current_source_ingestion_owns_pdf_snapshot_and_observation_universe() -> None:
    source, published = _ingest(_source_pdf())
    assert source.published_snapshot_for_revision(published.revision.revision_id) == published
    assert published.visible_observation_ids
    assert published.text_observation_ids


def test_current_f23_resolves_witness_bound_verandah_depth_from_real_pdf() -> None:
    evidence = _f23(_source_pdf())
    assert evidence is not None
    assert evidence.width_m == pytest.approx(1.8)
    assert evidence.binding_status == "witness_bound"


def test_current_f23_rejects_regex_only_prose() -> None:
    evidence = _f23(
        _source_pdf(
            include_depth=False,
            regex_only_text="2,000mm wide verandah",
        )
    )
    assert evidence is None


def test_current_f23_rejects_one_sided_boundary_witness() -> None:
    assert _f23(_source_pdf(witness_outer=False)) is None


def test_current_f23_rejects_competing_depths() -> None:
    assert _f23(_source_pdf(second_depth_text="2400")) is None


# ---------------------------------------------------------------------------
# Frozen future production contract — EXPECTED RED on current main
# ---------------------------------------------------------------------------


@EXPECTED_RED
def test_future_authority_has_source_producer_factory_and_selector_only_publication() -> None:
    mod = importlib.import_module(MODULE_NAME)
    assert hasattr(mod, "SecondaryFootprintProducer")
    assert hasattr(mod, "SecondaryFootprintAuthority")
    assert hasattr(mod, "SecondaryFootprintSelector")

    factory = inspect.signature(mod.SecondaryFootprintProducer.from_source_visibility_producer)
    factory_params = set(factory.parameters)
    assert "source_visibility_producer" in factory_params
    forbidden_factory = {
        "observations",
        "evidence",
        "polygon",
        "category",
        "width_m",
        "area_m2",
        "perimeter_m",
        "scale_ratio",
        "is_authenticated",
    }
    assert not factory_params.intersection(forbidden_factory)

    publish_params = tuple(inspect.signature(mod.SecondaryFootprintProducer.publish).parameters)
    assert publish_params == ("self", "selector")
    resolve_params = tuple(inspect.signature(mod.SecondaryFootprintAuthority.resolve).parameters)
    assert resolve_params == ("self", "selector")


@EXPECTED_RED
def test_future_real_source_can_publish_authenticated_verandah_geometry() -> None:
    result, _selector = _future_resolve(_source_pdf())
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    category = getattr(result.record.category, "value", result.record.category)
    assert str(category).lower() == "verandah"
    assert float(result.record.area_m2) > 0.0
    assert float(result.record.perimeter_m) > 0.0


@EXPECTED_RED
def test_future_caller_polygon_category_or_width_are_not_public_truth_inputs() -> None:
    mod = importlib.import_module(MODULE_NAME)
    source = inspect.getsource(mod.SecondaryFootprintProducer)
    signature_text = str(inspect.signature(mod.SecondaryFootprintProducer.publish))
    assert "observations" not in signature_text
    assert "polygon_points" not in signature_text
    assert "category" not in signature_text
    assert "width_m" not in signature_text
    # A public evidence dataclass may exist for diagnostics, but the producer
    # must not accept it as an authority input.
    assert "publish(self, selector, observations" not in source.replace("\n", " ")


@EXPECTED_RED
def test_future_wrong_revision_source_or_snapshot_cannot_replay_record() -> None:
    mod = importlib.import_module(MODULE_NAME)
    pdf = _source_pdf()
    source, published = _ingest(pdf)
    width = _f23(pdf)
    assert width is not None
    producer = mod.SecondaryFootprintProducer.from_source_visibility_producer(source)
    good = _future_selector(mod, published, viewport_id=width.view_id)
    producer.publish(good)
    authority = producer.authority()

    bad = mod.SecondaryFootprintSelector(
        document_id=good.document_id,
        revision_id=good.revision_id + "-stale",
        source_sha256="f" * 64,
        snapshot_id=good.snapshot_id + "-stale",
        page_id=good.page_id,
        viewport_id=good.viewport_id,
        secondary_space_id=good.secondary_space_id,
    )
    result = authority.resolve(bad)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is None


@EXPECTED_RED
def test_future_one_sided_or_competing_depth_source_fails_closed() -> None:
    for pdf in (
        _source_pdf(witness_outer=False),
        _source_pdf(second_depth_text="2400"),
    ):
        result, _selector = _future_resolve(pdf)
        assert result.status is not EvidenceResolutionStatus.CORROBORATED
        assert result.record is None


@EXPECTED_RED
def test_future_translation_does_not_change_physical_secondary_geometry() -> None:
    baseline, _ = _future_resolve(_source_pdf())
    shifted, _ = _future_resolve(_source_pdf(dx=35.0, dy=20.0))
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    assert shifted.status is EvidenceResolutionStatus.CORROBORATED
    assert baseline.record is not None and shifted.record is not None
    assert float(shifted.record.area_m2) == pytest.approx(float(baseline.record.area_m2))
    assert float(shifted.record.perimeter_m) == pytest.approx(float(baseline.record.perimeter_m))


@EXPECTED_RED
def test_future_authority_has_no_commercial_or_jobhub_shortcut() -> None:
    mod = importlib.import_module(MODULE_NAME)
    for name in (
        "publish_firm_quantity",
        "publish_commercial",
        "publish_to_jobhub",
        "evaluate_redteam_attack",
    ):
        assert not hasattr(mod, name)
