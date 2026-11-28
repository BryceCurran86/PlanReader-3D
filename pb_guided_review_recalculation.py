"""Recalculate a page with a saved guided-review packet: one call for the review screen, one piece cache per session.

The review screen builds a packet (``pb_guided_plan_review_native.build_native_review_packet``). ``recalculate_review`` runs the
canonical preview with it, using a bounded ``LayeredPieceCache`` that belongs to the caller's session, and keeps the result only
for the exact packet and source it came from. A packet older than the one already applied, or a different packet with the same
revision, is refused; a changed source file drops that source's pieces and results. The preview's own consumer still checks the
packet against the source bytes and page frame. Nothing here measures, prices, authenticates or writes anything, and nothing runs
unless the screen calls it.
"""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping, MutableMapping
import copy
import hashlib
from pathlib import Path
from typing import Any, Optional

import pb_new_source_trace_preview as preview
from pb_next_wall_ring_preview import LayeredPieceCache

SESSION_KEY = "guided_review_recalculation"
MAX_RESULTS = 8  # pages whose latest result is kept in one session


class ReviewRecalculationError(ValueError):
    """The packet does not match the page on screen, is stale, or the original file changed."""


def _state(session: MutableMapping) -> dict:
    state = session.get(SESSION_KEY)
    if state is None:
        state = session[SESSION_KEY] = {"cache": LayeredPieceCache(), "results": OrderedDict()}
    return state


def session_piece_cache(session: MutableMapping) -> LayeredPieceCache:
    """The one piece cache of this session; the app's automatic trace may share it so the first correction is fast too."""
    return _state(session)["cache"]


def _scope_of(packet: Mapping[str, Any]) -> tuple[tuple[int, int, int], str, int, str]:
    """(workspace, page, pdf page), source, revision and digest of a packet; the consumer validates the rest."""
    scope = packet.get("scope") if isinstance(packet, Mapping) else None
    if not isinstance(scope, Mapping):
        raise ReviewRecalculationError("review_packet_has_no_scope")
    key = (scope.get("workspace_id"), scope.get("page_id"), scope.get("pdf_page"))
    source, revision, digest = scope.get("source_sha256"), packet.get("review_revision"), packet.get("packet_sha256")
    if (any(type(value) is not int for value in key) or type(source) is not str or type(revision) is not int or revision < 1
            or type(digest) is not str or not digest):
        raise ReviewRecalculationError("review_packet_scope_or_revision_invalid")
    return key, source, revision, digest


def stored_review_result(session: MutableMapping, *, packet: Mapping[str, Any], registered_sha: str) -> Optional[dict]:
    """The result already calculated for exactly this packet and registered source, else None."""
    key, source, _revision, digest = _scope_of(packet)
    entry = _state(session)["results"].get(key)
    if entry is None or entry["packet_sha256"] != digest or entry["source_sha256"] != source or source != registered_sha:
        return None
    return {"summary": copy.deepcopy(entry["summary"]), "png": entry["png"]}


def recalculate_review(
    session: MutableMapping, *, pdf_path: str | Path, packet: Mapping[str, Any], registered_sha: str, workspace_id: int,
    page_id: int, pdf_page: int, progress_callback: Callable[[dict], None] | None = None,
) -> dict:
    """The preview of the page on screen with the packet's marks applied: ``{"summary": ..., "png": ...}``.

    ``summary["user_assisted_review"]`` holds the user-assisted rooms; the automatic result and the PNG are unchanged by the
    marks. The same packet again returns the stored result without tracing. Raises ``ReviewRecalculationError`` (or the
    consumer's ``ReviewPacketError``, both ``ValueError``) and stores nothing when the packet does not fit.
    """
    key, source, revision, digest = _scope_of(packet)
    if key != (workspace_id, page_id, pdf_page):
        raise ReviewRecalculationError("review_packet_is_for_another_workspace_or_page")
    registered = str(registered_sha or "").strip().lower()
    if source != registered:
        raise ReviewRecalculationError("review_packet_is_for_another_source")
    state = _state(session)
    results: OrderedDict = state["results"]
    applied = results.get(key)
    if applied is not None and applied["source_sha256"] != source:
        state["cache"].drop_source(applied["source_sha256"])
        del results[key]
        applied = None
    if hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest() != registered:
        state["cache"].drop_source(registered)
        results.pop(key, None)
        raise ReviewRecalculationError("original_pdf_changed")
    if applied is not None:
        if revision < applied["review_revision"]:
            raise ReviewRecalculationError("review_packet_older_than_the_applied_one")
        if revision == applied["review_revision"] and digest != applied["packet_sha256"]:
            raise ReviewRecalculationError("review_packet_conflicts_with_the_applied_revision")
        if digest == applied["packet_sha256"]:
            results.move_to_end(key)
            return {"summary": copy.deepcopy(applied["summary"]), "png": applied["png"]}
    summary, png = preview.source_native_trace_preview(
        pdf_path, pdf_page - 1, review_packet=packet, piece_cache=state["cache"], progress_callback=progress_callback,
    )
    block = summary.get("user_assisted_review") or {}
    if (summary.get("source_sha256") != registered or summary.get("page_index") != pdf_page - 1
            or block.get("packet_sha256") != digest or block.get("review_revision") != revision):
        raise ReviewRecalculationError("recalculated_result_does_not_match_the_packet")
    results[key] = {"source_sha256": source, "review_revision": revision, "packet_sha256": digest,
                    "summary": summary, "png": png}
    results.move_to_end(key)
    while len(results) > MAX_RESULTS:
        results.popitem(last=False)
    return {"summary": copy.deepcopy(summary), "png": png}
