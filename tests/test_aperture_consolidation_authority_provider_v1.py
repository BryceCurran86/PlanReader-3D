"""The authority-backed evidence provider of the aperture consolidation: the existence re-proof (``reproven``) and its failure modes.

``AuthorityEvidenceProvider.reproven`` accepts an opening only when the producer-owned ``PhysicalOpeningAuthority`` independently re-issues
exactly this opening's existence record. A caller's ids, record ids or coordinates certify nothing. The authority class is replaced by a
controllable stand-in (the module imports it at call time) so every single condition of the re-proof can be broken in turn.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_physical_opening_authority as authority_module
from pb_live_opening_aperture_consolidation import AuthorityEvidenceProvider
from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_view_class_source_adapter import page_viewport_id
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from tests.test_live_opening_aperture_consolidation_v1 import opening

RECORD_FIELDS = (
    "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "semantic_class", "structural_pattern",
    "source_observation_ids", "source_lineage_root_ids",
)


class StubAuthority:
    """Stands in for ``PhysicalOpeningAuthority``: returns one scripted existence proof (or raises)."""

    def __init__(self, proof=None, raises=False):
        self.proof, self.raises, self.selectors = proof, raises, []

    def prove_existence(self, selector):
        self.selectors.append(selector)
        if self.raises:
            raise RuntimeError("authority failure")
        return self.proof


@pytest.fixture(autouse=True)
def authority_class_is_the_stub(monkeypatch):
    monkeypatch.setattr(authority_module, "PhysicalOpeningAuthority", StubAuthority)


def good_proof(op, **changes):
    """The proof the authority would issue for exactly this opening; ``changes`` overrides one part of it."""
    record = {"record_id": op.physical_opening_id, "viewport_id": op.viewport_id, **{f: getattr(op, f) for f in RECORD_FIELDS}}
    record.update(changes.pop("record", {}))
    parts = {
        "status": EvidenceResolutionStatus.CORROBORATED,
        "proposition": PHYSICAL_OPENING_EXISTS,
        "existence_record": SimpleNamespace(**record),
        "source_observation": SimpleNamespace(observation=SimpleNamespace(observation_id=op.representative_observation_id)),
    }
    parts.update(changes)
    return SimpleNamespace(**parts)


def provider_for(authority):
    provider = object.__new__(AuthorityEvidenceProvider)
    provider._authority = authority
    provider._selectors = {}
    return provider


def test_an_opening_the_authority_re_issues_exactly_is_reproven_and_its_selector_is_kept():
    op = opening("a", ("o1", "o2"))
    authority = StubAuthority(good_proof(op))
    provider = provider_for(authority)
    assert provider.reproven(op) is True
    selector = provider._selectors["a"]
    assert isinstance(selector, ObservationSelector) and authority.selectors == [selector]
    assert (selector.document_id, selector.revision_id, selector.source_sha256, selector.snapshot_id, selector.observation_id) == (
        op.document_id, op.revision_id, op.source_sha256, op.snapshot_id, op.representative_observation_id)


@pytest.mark.parametrize("changes", [
    {"status": EvidenceResolutionStatus.CANDIDATE},                                           # raw candidate, not corroborated
    {"status": EvidenceResolutionStatus.ABSTAINED},
    {"status": EvidenceResolutionStatus.CONFLICT},
    {"proposition": "another_proposition"},
    {"existence_record": None},
    {"source_observation": SimpleNamespace(observation=None)},
    {"source_observation": None},
    {"record": {"record_id": "another-record"}},                                              # the authority's record is a different one
    {"record": {"viewport_id": "another-viewport"}},
    {"source_observation": SimpleNamespace(observation=SimpleNamespace(observation_id="another-observation"))},
], ids=lambda c: "-".join(sorted(c)) + ":" + "|".join(str(v)[:18] for v in c.values()))
def test_any_difference_between_the_authoritys_proof_and_the_opening_means_not_reproven(changes):
    op = opening("a", ("o1", "o2"))
    provider = provider_for(StubAuthority(good_proof(op, **dict(changes))))
    assert provider.reproven(op) is False
    assert provider._selectors == {}                                                          # a failed re-proof leaves no selector behind


@pytest.mark.parametrize("field", RECORD_FIELDS)
def test_every_identity_field_of_the_record_must_equal_the_openings(field):
    op = opening("a", ("o1", "o2"))
    current = getattr(op, field)
    other = (*current, "extra") if isinstance(current, tuple) else f"{current}-other"
    provider = provider_for(StubAuthority(good_proof(op, record={field: other})))
    assert provider.reproven(op) is False


def test_the_openings_canonical_id_must_equal_its_physical_id_and_the_record_id():
    op = replace(opening("a", ("o1", "o2")), canonical_opening_id="a-canonical")
    assert provider_for(StubAuthority(good_proof(op, record={"record_id": "a"}))).reproven(op) is False
    assert provider_for(StubAuthority(good_proof(op, record={"record_id": "a-canonical"}))).reproven(op) is False


def test_a_record_without_a_viewport_falls_back_to_the_page_viewport():
    op = replace(opening("a", ("o1", "o2")), viewport_id=page_viewport_id("3"))
    assert provider_for(StubAuthority(good_proof(op, record={"viewport_id": None}))).reproven(op) is True
    other = replace(op, viewport_id="not-the-page-viewport")
    assert provider_for(StubAuthority(good_proof(other, record={"viewport_id": None}))).reproven(other) is False


def test_an_authority_failure_is_never_a_reproof():
    op = opening("a", ("o1", "o2"))
    assert provider_for(StubAuthority(good_proof(op), raises=True)).reproven(op) is False


def test_an_object_that_is_not_the_physical_authority_class_never_reproves_anything(monkeypatch):
    monkeypatch.undo()                                                                        # the REAL authority class is the only accepted type
    op = opening("a", ("o1", "o2"))
    provider = provider_for(StubAuthority(good_proof(op)))
    assert provider.reproven(op) is False and provider._selectors == {}
