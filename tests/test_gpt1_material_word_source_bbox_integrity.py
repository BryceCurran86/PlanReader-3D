"""GPT1 Q07: source material text cannot authenticate malformed PDF geometry."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE,
    _trusted_words_by_page,
)


def _read(geometry, *, trusted=True):
    receipt = SimpleNamespace(
        geometry=geometry, page_id="1", source_partition_id="native-p1",
        raw_text="FPB PLASTERBOARD", block_no=1, line_no=0, word_no=0,
    )
    result = SimpleNamespace(
        receipt=receipt,
        status=(EvidenceResolutionStatus.CORROBORATED if trusted
                else EvidenceResolutionStatus.ABSTAINED),
        trusted_text="FPB PLASTERBOARD" if trusted else None,
        reason_codes=() if trusted else ("glyph_unresolved",),
    )
    authority = SimpleNamespace(resolve_text=lambda _selector: result)
    source = SimpleNamespace(text_integrity_authority=lambda: authority)
    published = SimpleNamespace(
        revision=SimpleNamespace(
            document_id="doc-1", revision_id="rev-1", source_sha256="a" * 64,
        ),
        snapshot=SimpleNamespace(snapshot_id="snap-1"),
        text_observation_ids=("source-word-observation-1",),
    )
    return _trusted_words_by_page(source, published)


def test_original_valid_material_text_receipt_keeps_exact_source_bbox():
    words = _read((10.0, 20.0, 40.0, 34.0))
    assert len(words["1"]) == 1
    word = words["1"][0]
    assert word.trusted
    assert word.observation_id == "source-word-observation-1"
    assert word.bbox == (10.0, 20.0, 40.0, 34.0)
    assert word.source_partition_id == "native-p1"


@pytest.mark.parametrize("bbox", [
    None, "10,20,40,34", (10, 20, 40),
    (10.0, 20.0, True, 34.0),
    (10.0, 20.0, "40", 34.0),
    (10.0, 20.0, 10**400, 34.0),
    (10.0, 20.0, float("nan"), 34.0),
    (10.0, 20.0, 40.0, float("-inf")),
    (10.0, 20.0, 10.0, 34.0),
    (10.0, 20.0, 40.0, 20.0),
])
@pytest.mark.parametrize("trusted", [True, False])
def test_invalid_original_material_source_geometry_never_enters_text_authority(
    bbox, trusted,
):
    with pytest.raises(RuntimeError, match=SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE):
        _read(bbox, trusted=trusted)
