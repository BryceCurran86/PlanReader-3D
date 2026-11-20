"""Production-reachable Cursor-07..10 interior-face / open-plan stage.

Wires finished-interior-face recovery, open-plan room-ring audit, opening↔host
correlation index, and non-commercial live-trace diagnostics into the original
footprint runtime. Review/topology receipts only — never FIRM, customer rows,
or frozen-benchmark authority.

Room labels are discovered from page words (unique alphabetic sequences).
Never use project names, filenames, or expected BOQ values as prediction inputs.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pb_source_finished_interior_face_recovery_shadow import (
    recover_finished_interior_face_candidates,
)
from pb_source_native_live_trace_diagnostics_shadow import (
    build_source_native_live_trace_diagnostics,
)
from pb_source_opening_host_correlation_index_shadow import (
    build_opening_host_correlation_index,
)
from pb_source_open_plan_room_ring_shadow import audit_open_plan_room_rings

# Drafting / title-block noise — not BOQ room targets.
_NOISE_TOKENS = frozenset(
    {
        "SCALE",
        "DRAWING",
        "SHEET",
        "REV",
        "REVISION",
        "DATE",
        "PROJECT",
        "PLAN",
        "FLOOR",
        "NORTH",
        "NOTE",
        "NOTES",
        "DETAIL",
        "SECTION",
        "ELEVATION",
        "TITLE",
        "CLIENT",
        "ARCHITECT",
        "PAGE",
        "OF",
        "AND",
        "THE",
        "FOR",
        "TO",
        "MM",
        "M",
        "N",
        "S",
        "E",
        "W",
    }
)
_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,24}$")
_SUFFIX_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9]{0,24}|\d{1,3})$")
_MAX_DISCOVERED_LABELS = 24


def _word_tokens(source_words: Sequence[Any]) -> tuple[tuple[str, tuple[float, float, float, float]], ...]:
    out: list[tuple[str, tuple[float, float, float, float]]] = []
    for row in source_words:
        try:
            if isinstance(row, Mapping):
                text = str(row.get("text") or "").strip()
                bounds = row.get("bbox_pdf_pts") or row.get("bbox")
            else:
                text = str(row[4]).strip()
                bounds = row[:4]
            box = tuple(float(v) for v in bounds)
            if (
                text
                and len(box) == 4
                and all(math.isfinite(v) for v in box)
                and _SUFFIX_RE.match(text)
            ):
                out.append((text, box))  # type: ignore[arg-type]
        except (TypeError, ValueError, IndexError, KeyError):
            continue
    return tuple(out)


def discover_room_labels_from_words(
    source_words: Sequence[Any],
    *,
    max_labels: int = _MAX_DISCOVERED_LABELS,
) -> tuple[str, ...]:
    """Unique 1–2 token page labels present once on the page.

    Discovery only — no project/BOQ vocabulary. Noise drafting tokens skipped.
    Numeric tokens alone are never room labels; they may suffix a letter token.
    """
    words = _word_tokens(source_words)
    candidates: list[str] = []
    seen_norm: set[str] = set()
    for i, (tok, _box) in enumerate(words):
        upper = tok.upper()
        if upper in _NOISE_TOKENS or tok.isdigit():
            continue
        if not _TOKEN_RE.match(tok):
            continue
        singles = (tok,)
        pairs: tuple[str, ...] = ()
        if i + 1 < len(words):
            nxt = words[i + 1][0]
            if nxt.upper() not in _NOISE_TOKENS and _SUFFIX_RE.match(nxt):
                # "BED" + "2" / "BED" + "ROOM" style pairs from page ink only.
                pairs = (tok, nxt)
        for parts in (singles, pairs) if pairs else (singles,):
            label = " ".join(parts)
            norm = label.upper()
            if norm in seen_norm:
                continue
            # Uniqueness: count exact case-insensitive matches of the sequence.
            n_parts = len(parts)
            hits = 0
            for j in range(len(words) - n_parts + 1):
                if all(
                    words[j + k][0].upper() == parts[k].upper()
                    for k in range(n_parts)
                ):
                    hits += 1
            if hits != 1:
                continue
            seen_norm.add(norm)
            candidates.append(label)
            if len(candidates) >= int(max_labels):
                return tuple(candidates)
    return tuple(candidates)


def _open_section_labels_present(
    source_words: Sequence[Any],
    *,
    candidates: Sequence[str] = ("LIVING", "KITCHEN"),
) -> tuple[str, ...]:
    """Keep open-plan pair only when those exact words appear on the page."""
    uppers = {w[0].upper() for w in _word_tokens(source_words)}
    return tuple(c for c in candidates if c in uppers)


def _opening_rows_from_drawings(
    drawings: Sequence[Mapping[str, Any] | object],
) -> tuple[dict[str, Any], ...]:
    """Best-effort opening stubs from native path indices — review index only."""
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "").lower()
        if not any(tok in layer for tok in ("door", "opening", "slider", "window")):
            continue
        path_id = row.get("path_id")
        if type(path_id) is not int:
            path_id = index
        rows.append(
            {
                "opening_id": f"path:{path_id}",
                "host_path_ids": (int(path_id),),
            }
        )
    return tuple(rows)


def run_interior_face_open_plan_runtime_stage(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_words: Sequence[Any] = (),
    page_index: int = -1,
    source_sha256: str = "",
    room_candidate_count: int = 0,
) -> dict[str, object]:
    """Executable Cursor-07..10 stage for original-app topology review receipts."""
    drawing_maps = tuple(d for d in drawings if isinstance(d, Mapping))
    labels = discover_room_labels_from_words(source_words)
    try:
        faces = recover_finished_interior_face_candidates(
            drawing_maps, source_words, room_labels=labels,
        )
        finished_interior = {
            "status": "CANDIDATE" if faces else "ABSTAINED",
            "reason": (
                "finished_interior_face_candidates_review_only"
                if faces
                else "no_unique_page_room_labels_for_face_recovery"
            ),
            "discovered_label_count": len(labels),
            "discovered_labels": list(labels),
            "candidates": [f.to_dict() for f in faces],
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    except Exception as exc:  # fail closed
        finished_interior = {
            "status": "ABSTAINED",
            "reason": f"finished_interior_face_runtime_exception:{type(exc).__name__}",
            "discovered_label_count": len(labels),
            "candidates": [],
            "measurement_authorized": False,
            "commercial_publishable": False,
        }

    open_labels = _open_section_labels_present(source_words)
    if not open_labels:
        open_plan = {
            "status": "ABSTAINED",
            "reason": "open_plan_section_labels_absent_on_page",
            "ring_count": 0,
            "open_section_labels": [],
            "invented_partition_count": 0,
            "doorway_threshold_closure_count": 0,
            "topology_only": True,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    else:
        try:
            audit = audit_open_plan_room_rings(
                drawing_maps,
                source_sha256=str(source_sha256 or ("0" * 64)),
                page_index=int(page_index),
                open_section_labels=open_labels,
            )
            open_plan = audit.to_dict()
        except Exception as exc:
            open_plan = {
                "status": "ABSTAINED",
                "reason": f"open_plan_room_ring_runtime_exception:{type(exc).__name__}",
                "invented_partition_count": 0,
                "measurement_authorized": False,
                "commercial_publishable": False,
            }

    try:
        index = build_opening_host_correlation_index(
            _opening_rows_from_drawings(drawings),
        )
        opening_host_index = index.to_dict()
    except Exception as exc:
        opening_host_index = {
            "status": "ABSTAINED",
            "reason": f"opening_host_index_runtime_exception:{type(exc).__name__}",
            "measurement_authorized": False,
            "commercial_publishable": False,
        }

    try:
        face_candidate_count = sum(
            1
            for row in finished_interior.get("candidates", [])
            if isinstance(row, Mapping) and row.get("status") == "CANDIDATE"
        )
        diag = build_source_native_live_trace_diagnostics(
            page_index=int(page_index),
            source_sha256=str(source_sha256 or ""),
            room_candidate_count=int(room_candidate_count or face_candidate_count),
        )
        live_trace = diag.to_dict()
    except Exception as exc:
        live_trace = {
            "status": "ABSTAINED",
            "reason": f"live_trace_diagnostics_runtime_exception:{type(exc).__name__}",
            "visual_output_non_commercial": True,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }

    statuses = (
        str(finished_interior.get("status")),
        str(open_plan.get("status")),
        str(opening_host_index.get("status")),
        str(live_trace.get("status")),
    )
    overall = "CANDIDATE" if any(s == "CANDIDATE" for s in statuses) else "ABSTAINED"
    return {
        "status": overall,
        "reason": "cursor_07_10_interior_open_plan_runtime_review_only",
        "page_index": int(page_index),
        "finished_interior_faces": finished_interior,
        "open_plan_room_rings": open_plan,
        "opening_host_correlation_index": opening_host_index,
        "live_trace_diagnostics": live_trace,
        "tasks_covered": ["Cursor-07", "Cursor-08", "Cursor-09", "Cursor-10"],
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }
