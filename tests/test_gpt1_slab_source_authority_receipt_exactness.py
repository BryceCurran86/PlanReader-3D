"""Slab source tokens and metric flags cannot borrow original authority."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib

import fitz
import pytest

from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_canonical_slab_projection import project_resolved_slab_entity
from pb_live_slab_area_quantity_publication import publish_live_slab_area_quantity
from pb_slab_classification_geometry import (
    CandidateBoundary,
    SlabResolutionState,
    resolve_slabs_from_page,
)
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication


class PrintedToken:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def __str__(self):
        self.calls += 1
        return self.text


@pytest.fixture
def source():
    # The real positioned PDF annotation resolver supplies the slab record.
    # Metre geometry is an explicit synthetic authority input, as in F.21;
    # neither PDF text nor these tests invent a scale/metric promotion.
    with fitz.open() as document:
        page = document.new_page(width=500, height=500)
        page.insert_text((100, 100), "150mm THICK RC SLAB\nT12@200 EW")
        source_sha = hashlib.sha256(document.tobytes()).hexdigest()
        boundary = CandidateBoundary(
            boundary_id="synthetic-boundary",
            polygon=[(0.0, 0.0), (8.0, 0.0), (8.0, 6.0), (0.0, 6.0)],
            area_m2=48.0,
            source_page=1,
            units_authoritative=True,
            spatial_envelope=(80.0, 70.0, 260.0, 140.0),
        )
        records = resolve_slabs_from_page(page, [boundary], source_page=1)
    assert len(records) == 1
    assert records[0].resolution_state == SlabResolutionState.RESOLVED.value
    return records[0], boundary, {
        "document_id": f"pdf-sha256:{source_sha}",
        "revision_id": "synthetic-revision",
        "source_sha256": source_sha,
        "snapshot_id": "synthetic-snapshot",
    }


def _publish(source):
    slab, boundary, lineage = source
    projection = project_resolved_slab_entity(
        slab=slab, boundary=boundary, **lineage,
    )
    quantity = (
        publish_live_slab_area_quantity(projection.object)
        if projection.object is not None else None
    )
    return projection, quantity


def test_original_pdf_resolver_to_quantity_and_coverage_replays_unchanged(source):
    before = deepcopy(source)
    first, quantity = _publish(source)
    second, repeated = _publish(source)
    assert source == before
    assert first == second
    assert quantity == repeated
    assert quantity is not None
    assert quantity.value == 48.0
    assert quantity.metadata["commercial_projection_allowed"] is False
    summaries, gaps = collect_live_canonical_coverage(
        objects=(first.object,), quantities=(quantity,),
        registry_run_scope="synthetic-slab-source",
    )
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    assert report["family_reports"]["floor_slab"]["stage_counts"] == {
        "DETECTED": 1, "AUTHENTICATED": 1, "CANONICALIZED": 1,
        "QUANTIFIED": 1, "PUBLISHED": 0,
    }


@pytest.mark.parametrize("flag", [
    "false", "true", 1, 1.0, {"verified": False}, [True], False, None,
])
def test_only_explicit_true_metric_receipt_can_reissue_source_slab(source, flag):
    slab, boundary, lineage = source
    damaged_boundary = replace(boundary, units_authoritative=flag)
    projection, quantity = _publish((slab, damaged_boundary, lineage))
    assert projection.object is None
    assert quantity is None
    assert slab.resolution_state == SlabResolutionState.RESOLVED.value
    assert boundary.units_authoritative is True


@pytest.mark.parametrize("field", [
    "document_id", "revision_id", "source_sha256", "snapshot_id",
    "slab_id", "boundary_id", "provenance_boundary_id",
])
@pytest.mark.parametrize("variant", ["padded", "printed", "blank", "integer"])
def test_altered_source_tokens_never_inherit_normalized_identity(source, field, variant):
    slab, boundary, lineage = source
    if field == "slab_id":
        original = slab.slab_id
    elif field in {"boundary_id", "provenance_boundary_id"}:
        original = boundary.boundary_id
    else:
        original = lineage[field]
    damaged = {
        "padded": f" {original} ", "printed": PrintedToken(original),
        "blank": " ", "integer": 1,
    }[variant]
    if field == "slab_id":
        slab = replace(slab, slab_id=damaged)
    elif field == "boundary_id":
        boundary = replace(boundary, boundary_id=damaged)
    elif field == "provenance_boundary_id":
        slab = replace(slab, provenance={**slab.provenance, "boundary_id": damaged})
    else:
        lineage = {**lineage, field: damaged}
    projection, quantity = _publish((slab, boundary, lineage))
    assert projection.object is None
    assert quantity is None
    if variant == "printed":
        assert damaged.calls == 0
    assert _publish(source)[1] is not None


def test_zero_digest_abstains_at_canonical_and_replayed_quantity_seams(source):
    slab, boundary, lineage = source
    original, quantity = _publish(source)
    assert quantity is not None
    projected, rejected = _publish((
        slab, boundary, {**lineage, "source_sha256": "0" * 64},
    ))
    assert projected.object is None
    assert rejected is None
    assert publish_live_slab_area_quantity(
        replace(original.object, source_sha256="0" * 64)
    ) is None
    assert _publish(source) == (original, quantity)


def test_genuine_uppercase_digest_keeps_original_canonical_and_quantity_ids(source):
    slab, boundary, lineage = source
    assert _publish((slab, boundary, {
        **lineage, "source_sha256": lineage["source_sha256"].upper(),
    })) == _publish(source)


@pytest.mark.parametrize("scale,offset,rotate", [
    (1.0, (17.0, -9.0), False),
    (1.0, (0.0, 0.0), True),
    (2.0, (17.0, -9.0), True),
])
def test_unit_receipt_rule_is_invariant_to_metric_geometry_transforms(
    source, scale, offset, rotate,
):
    slab, boundary, lineage = source
    polygon = []
    for x, y in boundary.polygon:
        x, y = (-y, x) if rotate else (x, y)
        polygon.append((x * scale + offset[0], y * scale + offset[1]))
    changed_slab = replace(slab, boundary_polygon=polygon, area_m2=48.0 * scale**2)
    changed_boundary = replace(boundary, polygon=polygon, area_m2=48.0 * scale**2)
    _, quantity = _publish((changed_slab, changed_boundary, lineage))
    assert quantity is not None and quantity.value == 48.0 * scale**2
    assert _publish((changed_slab, replace(
        changed_boundary, units_authoritative="false",
    ), lineage))[0].object is None


@pytest.mark.parametrize("variant", ["cyclic", "reversed", "split"])
def test_polygon_order_and_collinear_split_preserve_metric_receipt_rule(source, variant):
    slab, boundary, lineage = source
    polygon = boundary.polygon
    polygon = {
        "cyclic": polygon[1:] + polygon[:1],
        "reversed": list(reversed(polygon)),
        "split": [polygon[0], (4.0, 0.0), *polygon[1:]],
    }[variant]
    changed = (replace(slab, boundary_polygon=polygon),
               replace(boundary, polygon=polygon), lineage)
    projected, quantity = _publish(changed)
    assert quantity is not None and quantity.value == 48.0
    if variant != "split":
        assert projected.object.physical_slab_id == _publish(source)[0].object.physical_slab_id
    assert _publish((changed[0], replace(
        changed[1], units_authoritative=1,
    ), lineage))[1] is None
