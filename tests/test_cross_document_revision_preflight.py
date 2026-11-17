"""Source-neutral cross-document registration and callout preflight tests."""
from dataclasses import replace

import pytest

from pb_cross_document_revision_preflight import (
    CrossDocumentSourceLink, RegisteredRevisionDocument,
    preflight_cross_document_revision,
)

SHA1 = "a" * 64
SHA2 = "b" * 64
REQUIRED = frozenset({"floor", "elevation"})


def original():
    floor = RegisteredRevisionDocument(
        "tenant", "workspace", "floor", "rev-a", "snap-a",
        SHA1, SHA1, 0, 3, (1,))
    elevation = RegisteredRevisionDocument(
        "tenant", "workspace", "elevation", "rev-b", "snap-b",
        SHA2, SHA2, 4, 2, (0,))
    link = CrossDocumentSourceLink(
        "floor", "elevation", 1, 0, "physical-wall-1", "producer-callout-9")
    return [floor, elevation], [link]


def run(documents=None, links=None, *, ids=REQUIRED, verify_doc=None, verify_edge=None):
    originals, edges = original()
    return preflight_cross_document_revision(
        originals if documents is None else documents,
        edges if links is None else links,
        required_document_ids=ids,
        verify_document=(lambda _: True) if verify_doc is None else verify_doc,
        verify_link=(lambda _: True) if verify_edge is None else verify_edge,
    )


def test_positive_source_preflight_is_not_a_write_authorization():
    result = run()
    assert result.source_preflight_passed and result.document_count == 2
    assert result.blockers == ()
    assert not result.atomic_write_authorized
    assert not result.commercial_publication_allowed


def test_missing_required_document_is_blocked():
    docs, links = original()
    result = run(documents=docs[:1], links=links)
    assert "source_document_census_incomplete" in result.blockers


def test_cross_tenant_or_workspace_is_blocked():
    docs, links = original()
    docs[1] = replace(docs[1], tenant_id="other")
    assert "mixed_tenant_or_workspace_documents" in run(docs, links).blockers


def test_duplicate_document_registration_is_blocked():
    docs, links = original()
    assert "duplicate_document_registration" in run(docs + docs[:1], links).blockers


def test_invalid_sha_and_stale_model_schema_are_blocked():
    docs, links = original()
    docs[1] = replace(docs[1], source_pdf_sha256="bad", current_model_revision=-1)
    issues = run(docs, links).blockers
    assert "document_source_or_head_sha_invalid" in issues
    assert "document_page_or_model_scope_invalid" in issues


def test_bad_page_and_duplicate_page_are_blocked():
    docs, links = original()
    docs[0] = replace(docs[0], affected_page_indices=(2, 2))
    assert "document_page_or_model_scope_invalid" in run(docs, links).blockers
    docs[0] = replace(docs[0], affected_page_indices=(3,))
    assert "document_page_or_model_scope_invalid" in run(docs, links).blockers


def test_missing_graph_or_unowned_pages_fail_closed():
    docs, links = original()
    assert "cross_document_source_graph_disconnected" in run(docs, []).blockers
    wrong = replace(links[0], from_page_index=0)
    assert "source_link_page_or_witness_invalid" in run(docs, [wrong]).blockers


def test_unverified_callout_or_exception_fail_closed():
    docs, links = original()
    assert "unverified_source_link" in run(docs, links, verify_edge=lambda _: False).blockers
    def fail(_):
        raise RuntimeError("producer unavailable")
    assert "unverified_source_link" in run(docs, links, verify_edge=fail).blockers


def test_unverified_head_and_nonboolean_verifier_fail_closed():
    docs, links = original()
    assert "unverified_document:floor" in run(
        docs, links, verify_doc=lambda d: d.document_id != "floor").blockers
    assert "unverified_document:floor" in run(
        docs, links, verify_doc=lambda _: 1).blockers


def test_self_link_or_duplicate_link_fail_closed():
    docs, links = original()
    self_link = replace(links[0], to_document_id="floor", to_page_index=1)
    assert "source_link_document_missing_or_self_link" in run(docs, [self_link]).blockers
    assert "duplicate_cross_document_link" in run(docs, links + links).blockers


def test_untrusted_document_census_rejected():
    docs, links = original()
    assert "at_least_two_source_documents_required" in run(
        docs, links, ids=frozenset({"floor"})).blockers
    with pytest.raises(TypeError):
        run(docs, links, ids={"floor", "elevation"})


def test_connected_documents_with_unwitnessed_affected_page_abstain():
    docs, links = original()
    docs[0] = replace(docs[0], affected_page_indices=(1, 2))
    preflight = run(docs, links)
    assert not preflight.source_preflight_passed
    assert "cross_document_affected_page_unwitnessed:floor" in preflight.blockers
    assert not preflight.atomic_write_authorized


def test_only_verified_producer_links_qualify_for_page_coverage():
    docs, links = original()
    docs[0] = replace(docs[0], affected_page_indices=(1, 2))
    second = replace(links[0], from_page_index=2, producer_witness_id="producer-callout-10")
    passed = run(docs, links + [second])
    assert passed.source_preflight_passed
    failed = run(docs, links + [second], verify_edge=lambda link: link.from_page_index != 2)
    assert "cross_document_affected_page_unwitnessed:floor" in failed.blockers
