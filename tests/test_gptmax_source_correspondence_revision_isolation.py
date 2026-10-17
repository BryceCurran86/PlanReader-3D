"""Source correspondence must never cross independent issuer roots.

Original and alternate packets can share pixels or root observation identities
without being the same drawing revision or document authority.
"""
from copy import deepcopy

import pytest

from pb_opening_source_review_shadow import compare_opening_source_correspondence


def _packet(oid="opening-a", document="document-a", revision="revision-a"):
    return {
        "packet_id": oid,
        "opening_identity_id": oid,
        "page_id": "page-3",
        "physical_opening": {
            "document_id": document,
            "revision_id": revision,
            "source_sha256": "a" * 64,
            "source_observation_ids": ["source-1"],
        },
        "source_lineage": {
            "source_proof_closed": True,
            "observations": [{
                "observation_id": "source-1",
                "observation_kind": "raster",
                "source_primitive_ref": "original-ink",
                "geometry": [10, 20, 30, 40],
            }],
        },
    }


def test_same_revision_source_support_remains_review_correspondence():
    old = _packet()
    new = deepcopy(old)
    new["packet_id"] = "alternate-packet"
    new["opening_identity_id"] = "alternate-opening"
    result = compare_opening_source_correspondence([old], [new])
    assert result[0]["exact_source_support_original_ids"] == ["opening-a"]
    assert result[0]["physical_identity_alias_granted"] is False
    assert result[0]["signed_record_migration_granted"] is False


def test_identical_ink_from_another_revision_is_not_same_source_support():
    old = _packet()
    new = _packet("opening-b", revision="revision-b")
    result = compare_opening_source_correspondence([old], [new])
    assert result[0]["exact_source_support_original_ids"] == []
    assert result[0]["source_relationship"] == "additional_or_changed_source_support"


def test_identical_ink_from_another_document_is_not_same_source_support():
    old = _packet()
    new = _packet("opening-b", document="document-b")
    result = compare_opening_source_correspondence([old], [new])
    assert result[0]["exact_source_support_original_ids"] == []
    assert result[0]["physical_identity_alias_granted"] is False


def test_duplicate_original_packets_cannot_overwrite_source_support():
    original = _packet()
    duplicate = deepcopy(original)
    duplicate["opening_identity_id"] = "another-original"
    with pytest.raises(ValueError, match="duplicate original"):
        compare_opening_source_correspondence([original, duplicate], [_packet("alternate")])


def test_duplicate_alternate_packets_cannot_repeat_same_review_identity():
    alternate = _packet("alternate")
    with pytest.raises(ValueError, match="duplicate alternate"):
        compare_opening_source_correspondence([_packet()], [alternate, deepcopy(alternate)])


def test_empty_original_roots_never_establish_exact_correspondence():
    original = _packet()
    altered = deepcopy(original)
    altered["packet_id"] = "another"
    altered["physical_opening"]["source_observation_ids"] = []
    altered["source_lineage"]["observations"] = []
    result = compare_opening_source_correspondence([altered], [deepcopy(altered)])
    assert result[0]["exact_source_support_original_ids"] == []


def test_duplicate_parent_roots_cannot_establish_exact_correspondence():
    altered = _packet()
    altered["physical_opening"]["source_observation_ids"] = ["source-1", "source-1"]
    result = compare_opening_source_correspondence([altered], [altered])
    assert result[0]["exact_source_support_original_ids"] == []


def test_duplicate_observation_rows_cannot_substitute_for_missing_root():
    altered = _packet()
    altered["physical_opening"]["source_observation_ids"] = ["source-1", "source-2"]
    altered["source_lineage"]["observations"] *= 2
    result = compare_opening_source_correspondence([altered], [altered])
    assert result[0]["exact_source_support_original_ids"] == []
