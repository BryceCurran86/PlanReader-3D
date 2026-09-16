"""Merged host-binding prerequisite checks for Physical Opening Void V2.

TEST ONLY. These tests verify the real upstream host authority now present on main.
They do not manufacture physical-void, height, vertical-placement, or unit authority.
"""
from __future__ import annotations

from dataclasses import fields
import inspect

import pytest

from pb_opening_host_binding_authority import (
    OpeningHostBindingAuthority,
    OpeningHostBindingRecord,
    OpeningHostBindingSelector,
)


_EXPECTED_HOST_SELECTOR_FIELDS = {
    "document_id",
    "revision_id",
    "source_sha256",
    "snapshot_id",
    "page_id",
    "decision_scope_id",
    "opening_identity_id",
}


def test_merged_host_authority_lookup_is_selector_only() -> None:
    params = set(inspect.signature(OpeningHostBindingAuthority.resolve).parameters)
    assert params == {"self", "selector"}


def test_host_selector_is_lineage_and_opening_address_only() -> None:
    selector_fields = {item.name for item in fields(OpeningHostBindingSelector)}
    assert selector_fields == _EXPECTED_HOST_SELECTOR_FIELDS
    forbidden = {
        "host_wall_id",
        "wall_id",
        "candidate_wall_id",
        "candidate_wall_ids",
        "complete",
        "claimed_complete",
        "radius",
        "nearest",
        "first",
        "confidence",
        "x",
        "y",
        "u",
        "u0",
        "u1",
    }
    assert not (selector_fields & forbidden)


def test_host_authority_cannot_be_caller_constructed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        OpeningHostBindingAuthority({})


def test_host_record_keeps_candidate_addressing_and_equivalence_proof_separate() -> None:
    record_fields = {item.name for item in fields(OpeningHostBindingRecord)}
    assert "host_wall_id" in record_fields
    assert "member_wall_candidate_ids" in record_fields
    assert "member_candidate_identity_ids" in record_fields
    assert "member_equivalence_groups" in record_fields
    assert "physical_wall_id" not in record_fields
    assert "physical_identity_id" not in record_fields
