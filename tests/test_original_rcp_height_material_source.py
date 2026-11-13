"""Original PlanReader RCP height/material pairing: shadow-only source-trusted evidence."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from pb_source_rcp_height_material_evidence import (
    _paired,
    collect_original_rcp_height_material_evidence,
)
from pb_source_visibility_authority import SourceVisibilityProducer

MARYBOROUGH_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def w(text, obs, *, block=1, line=0, box=(0, 0, 4, 4), trusted=True, partition="p"):
    return SimpleNamespace(text=text, observation_id=obs, block_no=block, line_no=line,
                           bbox=box, trusted=trusted, page_id="9", source_partition_id=partition)


def test_same_native_block_consecutive_lines_and_rotated_geometry_are_required():
    material = w("GRID", "material", box=(0, 0, 4, 4))
    height = w("2400", "height", line=1, box=(12, 0, 17, 4))
    assert [(h.observation_id, m.observation_id, mm) for h, m, mm in _paired((material, height), None)] == [
        ("height", "material", 2400)
    ]
    assert not _paired((material, w("2400", "h2", line=3, box=(12, 0, 17, 4))), None)
    assert not _paired((material, w("2400", "h2", block=2, line=1, box=(12, 0, 17, 4))), None)
    assert not _paired((material, w("2400", "h2", line=1, box=(40, 0, 45, 4))), None)
    assert not _paired((material, w("2400", "h2", line=1, partition="foreign", box=(12, 0, 17, 4))), None)


def test_source_integrity_and_ambiguous_material_pairing_abstain():
    material = w("GRID", "material", box=(0, 0, 4, 4))
    height = w("2400", "height", line=1, box=(12, 0, 17, 4))
    assert not _paired((w("GRID", "m2", trusted=False), height), None)
    assert not _paired((material, height), (100, 100, 200, 200))
    # A nearby IPF1 on a different source block is not paired, even if the bboxes touch.
    assert not _paired((w("IPF1", "m3", block=3), height), None)
    assert not _paired((material, w("1980", "fixture", block=4, line=1, box=(12, 0, 17, 4))), None)
    # One height assigned to two material labels is ambiguous.
    m2 = w("FPB", "other-material", line=0, box=(0, 0, 4, 4))
    assert not _paired((material, m2, height), None)
    assert not _paired((material, height, w("2500", "other-height", line=1, box=(12, 0, 17, 4))), None)


def test_explicit_untrusted_height_or_material_cannot_pair():
    material = w("GRID", "material", box=(0, 0, 4, 4))
    height = w("2400", "height", line=1, box=(12, 0, 17, 4))
    assert not _paired((w("GRID", "bad-m", trusted=False), height), None)
    assert not _paired((material, w("2400", "bad-h", line=1, box=(12, 0, 17, 4), trusted=False)), None)
    # Untrusted symbol/height evidence must never trigger a default floor/ceiling value.
    assert not _paired((w("2700", "random", line=1, box=(12, 0, 17, 4)),), None)


def test_invalid_public_selectors_rejected():
    with pytest.raises(ValueError, match="selector_invalid"):
        collect_original_rcp_height_material_evidence(source=None, revision_id="valid", page_id="9")


def test_genuine_maryborough_rcp_source_text_cross_engine_if_provisioned():
    named = os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH") or os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not named:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: Maryborough PDF not provisioned; no original-source pass")
    path = Path(named)
    assert path.is_file() and not path.is_symlink()
    source_bytes = path.read_bytes()
    assert hashlib.sha256(source_bytes).hexdigest() == MARYBOROUGH_SHA
    producer = SourceVisibilityProducer(
        producer_method="gptmax-original-rcp-height-proof",
        producer_version="1.0",
        source_native_finish_text_shadow=True,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="maryborough-original-rcp-height-proof",
        source_bytes=source_bytes,
        source_locator=str(path),
        page_ids=("9",),
    )
    result = collect_original_rcp_height_material_evidence(
        source=producer,
        revision_id=published.revision.revision_id,
        page_id="9",
    )
    assert len(result.candidate_records) == 18
    assert {(r.height_mm, r.material_code) for r in result.candidate_records} >= {
        (2400, "GRID"), (3000, "FPB")
    }
    assert result.source_sha256 == MARYBOROUGH_SHA
    assert len({r.record_id for r in result.candidate_records}) == 18
    assert all(
        r.source_sha256 == MARYBOROUGH_SHA
        and r.snapshot_id == published.snapshot.snapshot_id
        and r.document_id == published.revision.document_id
        and r.source_partition_id
        and not r.commercial_projection_allowed
        and not r.benchmark_credit
        for r in result.candidate_records
    )
    assert not result.commercial_projection_allowed
    assert not result.physical_ceiling_zone_authenticated
    assert not result.wall_finish_height_authenticated
    assert not result.benchmark_credit
    # All 18 are source-word observations only; no unverified zone or customer quantity.
    assert result.reason_codes == ()
    bogus = collect_original_rcp_height_material_evidence(
        source=producer, revision_id=published.revision.revision_id + "-wrong",
        page_id="9",
    )
    assert not bogus.candidate_records
    assert not bogus.commercial_projection_allowed
    repeated = collect_original_rcp_height_material_evidence(
        source=producer, revision_id=published.revision.revision_id,
        page_id="9",
    )
    assert [r.record_id for r in repeated.candidate_records] == [
        r.record_id for r in result.candidate_records
    ]
