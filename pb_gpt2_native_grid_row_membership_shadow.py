"""Read-only source-ink grid membership for PDF schedule rows spanning native blocks.

A native PyMuPDF text block is not an installed door or even a printed table
row. This shadow requires independently drawn source grid boundaries and ALL
producer-owned native words; it issues no type, size, count, or commercial row.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord,
    _DOOR_CODE,
    _producer_owned_native_words,
)
from pb_source_visibility_authority import SourceVisibilityProducer


@dataclass(frozen=True)
class NativeGridRowScope:
    page_number: int
    left_boundary_paths: tuple[int, ...]
    right_boundary_paths: tuple[int, ...]
    code_address: tuple[int, int, int]


@dataclass(frozen=True)
class NativeGridRowShadow:
    status: EvidenceResolutionStatus
    source_sha256: str
    page_number: int
    code_observation_id: str
    native_blocks: tuple[int, ...]
    member_observation_ids: tuple[str, ...]
    competing_same_code_observation_ids: tuple[str, ...]
    source_grid_boundary_paths: tuple[int, ...]
    first_unclosed_gate: str
    shadow_only: bool = True
    source_dimension_authorized: bool = False
    physical_door_identity_proven: bool = False
    opening_count_granted: bool = False
    firm_quantity_issued: bool = False
    commercial_projection_allowed: bool = False


def _original_vertical_chain(drawings, indices, *, tolerance):
    if (type(indices) is not tuple or not 1 <= len(indices) <= 100
            or any(type(i) is not int or i < 0 or i >= len(drawings)
                   for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError("distinct original grid path addresses required")
    lines = []
    for i in indices:
        d = drawings[i]
        color = d.get("color")
        if (d.get("type") != "s" or d.get("stroke_opacity") != 1
                or d.get("fill") is not None or d.get("dashes") != "[] 0"
                or not isinstance(color, (tuple, list)) or len(color) != 3
                or any(type(v) not in (float, int) or not isfinite(v)
                       or not 0 <= v <= .04 for v in color)
                or type(d.get("width")) not in (int, float)
                or not isfinite(d["width"]) or d["width"] <= 0):
            raise ValueError("grid boundary not opaque solid source ink")
        items = d.get("items", ())
        if len(items) != 1 or items[0][0] != "l":
            raise ValueError("grid boundary must be source line, not hatch/rect")
        a, b = items[0][1:3]
        if not all(isfinite(v) for v in (a.x, a.y, b.x, b.y)):
            raise ValueError("nonfinite source grid line")
        if abs(a.x - b.x) > tolerance or abs(a.y - b.y) <= tolerance:
            raise ValueError("grid boundary must be nondegenerate vertical ink")
        lines.append((float(a.x), min(float(a.y), float(b.y)),
                      max(float(a.y), float(b.y)), float(d["width"])))
    lines.sort(key=lambda item: (item[1], item[2]))
    x = lines[0][0]
    width = lines[0][3]
    for index, line in enumerate(lines):
        if abs(line[0] - x) > tolerance or abs(line[3] - width) > tolerance:
            raise ValueError("grid path x or source stroke width disagrees")
        if index and abs(line[1] - lines[index-1][2]) > tolerance:
            raise ValueError("grid boundary contains missing or overlapping ink")
    return x, lines[0][1], lines[-1][2], width


def inspect_original_native_grid_row_shadow(
    original_pdf_bytes: bytes, *, source_sha256: str,
    words: tuple[SourceDoorScheduleWord, ...],
    scope: NativeGridRowScope,
    tolerance_pdf_pt: float = .06,
) -> NativeGridRowShadow:
    """Return a negative-only source grid receipt; never select an installed door."""
    if (type(original_pdf_bytes) is not bytes or not original_pdf_bytes
            or sha256(original_pdf_bytes).hexdigest() != source_sha256):
        raise ValueError("original PDF SHA mismatch")
    if (type(scope) is not NativeGridRowScope
            or type(tolerance_pdf_pt) not in (float, int)
            or not isfinite(tolerance_pdf_pt)
            or not .001 <= tolerance_pdf_pt <= .25
            or type(words) is not tuple or not words or len(words) > 25000):
        raise ValueError("invalid original grid row source scope")
    if (len(scope.code_address) != 3
            or any(type(x) is not int or x < 0 for x in scope.code_address)):
        raise ValueError("exact native code word address required")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as pdf:
        if type(scope.page_number) is not int or not 1 <= scope.page_number <= len(pdf):
            raise ValueError("original page outside source")
        drawings = pdf[scope.page_number-1].get_drawings()
        left = _original_vertical_chain(
            drawings, scope.left_boundary_paths, tolerance=tolerance_pdf_pt)
        right = _original_vertical_chain(
            drawings, scope.right_boundary_paths, tolerance=tolerance_pdf_pt)
    if left[0] + tolerance_pdf_pt >= right[0] or abs(left[3]-right[3]) > tolerance_pdf_pt:
        raise ValueError("source grid row boundaries not distinct")
    if (abs(left[1]-right[1]) > tolerance_pdf_pt
            or abs(left[2]-right[2]) > tolerance_pdf_pt):
        raise ValueError("paired source grid rows span unequal columns")
    addresses = set()
    observations = set()
    for w in words:
        if (type(w) is not SourceDoorScheduleWord
                or w.page_id != str(scope.page_number)
                or w.partition_id != "page:" + str(scope.page_number)
                or (w.block_no, w.line_no, w.word_no) in addresses
                or w.observation_id in observations):
            raise ValueError("unverified or duplicated complete source word universe")
        addresses.add((w.block_no, w.line_no, w.word_no))
        observations.add(w.observation_id)
    codes = [w for w in words
             if (w.block_no, w.line_no, w.word_no) == scope.code_address]
    if len(codes) != 1 or _DOOR_CODE.fullmatch(codes[0].literal) is None:
        raise ValueError("exact canonical source code observation unavailable")
    members, touching = [], []
    for w in words:
        x0,y0,x1,y1 = w.bbox_pdf_pts
        if not all(isfinite(v) for v in (x0,y0,x1,y1)) or x0 >= x1 or y0 >= y1:
            raise ValueError("invalid original source word bbox")
        if y1 <= left[1] or y0 >= left[2] or x1 <= left[0] or x0 >= right[0]:
            continue
        if (x0 <= left[0]+tolerance_pdf_pt or x1 >= right[0]-tolerance_pdf_pt
                or y0 <= left[1]-tolerance_pdf_pt
                or y1 >= left[2]+tolerance_pdf_pt):
            touching.append(w)
        else:
            members.append(w)
    if codes[0] not in members:
        raise ValueError("source code not entirely within original ruled row")
    member_code = [w for w in members if _DOOR_CODE.fullmatch(w.literal)]
    conflict = bool(touching or len(member_code) != 1 or
                    any(not w.trusted for w in members))
    rivals = tuple(sorted(w.observation_id for w in words
                          if w not in members and w.literal == codes[0].literal))
    return NativeGridRowShadow(
        status=EvidenceResolutionStatus.ABSTAINED if conflict
               else EvidenceResolutionStatus.CANDIDATE,
        source_sha256=source_sha256,
        page_number=scope.page_number,
        code_observation_id=codes[0].observation_id,
        native_blocks=tuple(sorted(set(w.block_no for w in members))),
        member_observation_ids=tuple(w.observation_id for w in sorted(
            members, key=lambda w:(w.block_no,w.line_no,w.word_no))),
        competing_same_code_observation_ids=rivals,
        source_grid_boundary_paths=tuple(sorted((
            *scope.left_boundary_paths, *scope.right_boundary_paths))),
        first_unclosed_gate=(
            "original_grid_row_competing_or_untrusted_source_words" if conflict
            else "source_grid_membership_only_no_kind_host_count_or_dimensions"
        ),
    )


def audit_published_native_grid_row_shadow(
    producer: SourceVisibilityProducer, *, revision_id: str, page_id: str,
    original_pdf_bytes: bytes, scope: NativeGridRowScope,
) -> NativeGridRowShadow:
    """Derive ALL words from producer receipts, not caller-curated text boxes."""
    if type(producer) is not SourceVisibilityProducer or type(revision_id) is not str:
        raise ValueError("authentic published original source producer required")
    published = producer.published_snapshot_for_revision(revision_id)
    if (published is None or published.revision.revision_id != revision_id
            or page_id != str(scope.page_number)
            or scope.page_number not in published.coverage.decoded_pages):
        raise ValueError("foreign original source revision/page")
    words = _producer_owned_native_words(producer, published, page_id)
    return inspect_original_native_grid_row_shadow(
        original_pdf_bytes, source_sha256=published.revision.source_sha256,
        words=words, scope=scope)
