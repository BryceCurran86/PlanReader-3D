"""Fail-closed source coordination preflight for *cross-document* plan edits.

Original PlanReader's existing atomic writer only covers pages in one PDF.
This module cannot authorize, execute or simulate a multi-document commit.
It checks server-registered source identities, exact page ownership, producer
links and graph coverage before a future multi-document transaction exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class RegisteredRevisionDocument:
    tenant_id: str
    workspace_id: str
    document_id: str
    original_revision_id: str
    source_snapshot_id: str
    source_pdf_sha256: str
    current_pdf_sha256: str
    current_model_revision: int
    page_count: int
    affected_page_indices: tuple[int, ...]


@dataclass(frozen=True)
class CrossDocumentSourceLink:
    from_document_id: str
    to_document_id: str
    from_page_index: int
    to_page_index: int
    canonical_owner_id: str
    producer_witness_id: str


@dataclass(frozen=True)
class CrossDocumentPreflight:
    source_preflight_passed: bool
    blockers: tuple[str, ...]
    document_count: int
    atomic_write_authorized: bool = False
    commercial_publication_allowed: bool = False


def _sha(value: object) -> bool:
    return (
        type(value) is str and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _nonempty(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def preflight_cross_document_revision(
    documents: Sequence[RegisteredRevisionDocument],
    links: Sequence[CrossDocumentSourceLink],
    *,
    required_document_ids: frozenset[str],
    verify_document: Callable[[RegisteredRevisionDocument], bool] | None,
    verify_link: Callable[[CrossDocumentSourceLink], bool] | None,
) -> CrossDocumentPreflight:
    """Require complete authenticated source registrations and linked pages.

    Required document IDs must come from a trusted producer-owned census, not
    a user browser request. A document verifier must inspect actual server
    source/HEAD/CAS state; the link verifier must prove source-page callouts
    and physical owner correspondence. Even success NEVER authorizes writes.
    """
    if (
        not isinstance(documents, (tuple, list))
        or not isinstance(links, (tuple, list))
        or type(required_document_ids) is not frozenset
        or any(not _nonempty(item) for item in required_document_ids)
    ):
        raise TypeError("trusted_cross_document_arguments_required")
    issues: set[str] = set()
    if len(required_document_ids) < 2:
        issues.add("at_least_two_source_documents_required")
    if not callable(verify_document) or not callable(verify_link):
        issues.add("trusted_source_verifiers_required")
    indexed: dict[str, RegisteredRevisionDocument] = {}
    for document in documents:
        if not isinstance(document, RegisteredRevisionDocument):
            issues.add("untrusted_document_registration_type")
            continue
        if document.document_id in indexed:
            issues.add("duplicate_document_registration")
        indexed[document.document_id] = document
        if not all(_nonempty(x) for x in (
            document.tenant_id, document.workspace_id, document.document_id,
            document.original_revision_id, document.source_snapshot_id,
        )):
            issues.add("document_source_identity_missing")
        if not _sha(document.source_pdf_sha256) or not _sha(document.current_pdf_sha256):
            issues.add("document_source_or_head_sha_invalid")
        if (
            type(document.current_model_revision) is not int
            or document.current_model_revision < 0
            or type(document.page_count) is not int
            or document.page_count < 1
            or type(document.affected_page_indices) is not tuple
            or not document.affected_page_indices
            or any(type(p) is not int or p < 0 or p >= document.page_count
                   for p in document.affected_page_indices)
            or len(document.affected_page_indices) != len(set(document.affected_page_indices))
        ):
            issues.add("document_page_or_model_scope_invalid")
    if set(indexed) != set(required_document_ids):
        issues.add("source_document_census_incomplete")
    scopes = {(d.tenant_id, d.workspace_id) for d in indexed.values()}
    if len(scopes) != 1:
        issues.add("mixed_tenant_or_workspace_documents")
    if issues:
        return CrossDocumentPreflight(False, tuple(sorted(issues)), len(indexed))
    # All source and current-head callbacks MUST succeed exactly as bool True.
    for doc in documents:
        try:
            verified = verify_document(doc) is True
        except Exception:
            verified = False
        if not verified:
            issues.add("unverified_document:" + doc.document_id)
    connected: dict[str, set[str]] = {key: set() for key in indexed}
    seen_links: set[tuple[str, str, int, int, str]] = set()
    for link in links:
        if not isinstance(link, CrossDocumentSourceLink):
            issues.add("untrusted_link_type")
            continue
        a, b = indexed.get(link.from_document_id), indexed.get(link.to_document_id)
        if a is None or b is None or a.document_id == b.document_id:
            issues.add("source_link_document_missing_or_self_link")
            continue
        if (
            type(link.from_page_index) is not int
            or type(link.to_page_index) is not int
            or link.from_page_index not in a.affected_page_indices
            or link.to_page_index not in b.affected_page_indices
            or not _nonempty(link.canonical_owner_id)
            or not _nonempty(link.producer_witness_id)
        ):
            issues.add("source_link_page_or_witness_invalid")
            continue
        identity = (a.document_id, b.document_id,
                    link.from_page_index, link.to_page_index, link.canonical_owner_id)
        if identity in seen_links:
            issues.add("duplicate_cross_document_link")
            continue
        seen_links.add(identity)
        try:
            verified = verify_link(link) is True
        except Exception:
            verified = False
        if not verified:
            issues.add("unverified_source_link")
            continue
        connected[a.document_id].add(b.document_id)
        connected[b.document_id].add(a.document_id)
    visited: set[str] = set()
    frontier = [next(iter(indexed))]
    while frontier:
        node = frontier.pop()
        if node not in visited:
            visited.add(node)
            frontier.extend(connected[node] - visited)
    if visited != set(indexed):
        issues.add("cross_document_source_graph_disconnected")
    return CrossDocumentPreflight(not issues, tuple(sorted(issues)), len(indexed))
