"""Read-only, source-SHA-owned two-page native stroke translation census.

This audits ALL eligible source-black structural-looking line strokes inside
two caller-declared diagnostic bounds, for every caller-supplied translation.
It neither authenticates a viewport nor publishes a W4 wall, host, surface,
metric, floor finish, FIRM quantity, customer row, or benchmark match.
Caller hypotheses are NEVER claimed to be the exhaustive universe.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class StructuralTranslationVote:
    translation_pdf_pt: tuple[float, float]
    matched_stroke_groups: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]
    horizontal_matches: int
    vertical_matches: int
    rival_pairing_conflict: bool
    source_ink_candidate: bool


@dataclass(frozen=True)
class OriginalStructuralTranslationShadow:
    status: EvidenceResolutionStatus
    source_sha256: str
    first_page: int
    second_page: int
    first_candidate_stroke_groups: int
    second_candidate_stroke_groups: int
    votes: tuple[StructuralTranslationVote, ...]
    compatible_translations_pdf_pt: tuple[tuple[float, float], ...]
    reasons: tuple[str, ...]
    shadow_only: bool = True
    complete_translation_universe_proven: bool = False
    original_w4_wall_issued: bool = False
    opening_jamb_issued: bool = False
    physical_floor_issued: bool = False
    material_finish_issued: bool = False
    metric_area_issued: bool = False
    customer_projection_allowed: bool = False


def _bounds(value: object) -> tuple[float, float, float, float]:
    if (type(value) not in (tuple, list) or len(value) != 4
            or any(type(x) not in (int, float) or not isfinite(x) for x in value)
            or value[2] <= value[0] or value[3] <= value[1]):
        raise ValueError("finite ordered native source bounds required")
    return tuple(float(x) for x in value)


def _strokes(
    page: fitz.Page,
    bounds: tuple[float, float, float, float],
    *,
    min_length: float,
    reference_width: float,
    axis_tolerance: float,
) -> tuple[tuple[tuple[float, ...], str, tuple[int, ...]], ...]:
    # Group identical source geometric strokes without treating overprinted
    # duplicate ink as independent physical evidence/votes.
    groups: dict[tuple[tuple[float, ...], str], set[int]] = defaultdict(set)
    for path_id, drawing in enumerate(page.get_drawings()):
        color = drawing.get("color")
        opacity = drawing.get("stroke_opacity")
        width = drawing.get("width")
        if (
            type(opacity) not in (int, float) or opacity != 1.0
            or drawing.get("dashes") != "[] 0"
            or drawing.get("fill") is not None
            or type(color) not in (tuple, list) or len(color) != 3
            or any(type(c) not in (int, float) or not isfinite(c)
                   or not 0.0 <= c <= 0.04 for c in color)
            or type(width) not in (int, float) or not isfinite(width)
            or abs(float(width) - reference_width) > 0.05
        ):
            continue
        items = drawing.get("items", ())
        if len(items) not in (1, 2) or items[0][0] != "l":
            continue
        if (len(items) == 2 and
                (items[1][0] != "l" or items[1][1] != items[0][2]
                 or items[1][2] != items[0][1])):
            continue
        a, b = items[0][1:3]
        ax, ay, bx, by = map(float, (a.x, a.y, b.x, b.y))
        if (not all(isfinite(v) for v in (ax, ay, bx, by))
                or not all(bounds[0] <= x <= bounds[2] for x in (ax, bx))
                or not all(bounds[1] <= y <= bounds[3] for y in (ay, by))):
            continue
        dx, dy = abs(ax - bx), abs(ay - by)
        if dx >= min_length and dy <= axis_tolerance:
            orientation = "horizontal"
        elif dy >= min_length and dx <= axis_tolerance:
            orientation = "vertical"
        else:
            continue
        pair = tuple(sorted(((round(ax, 4), round(ay, 4)),
                             (round(bx, 4), round(by, 4)))))
        geometry = (*pair[0], *pair[1], round(float(width), 4))
        groups[(geometry, orientation)].add(path_id)
    return tuple(sorted(
        (geometry, orientation, tuple(sorted(paths)))
        for (geometry, orientation), paths in groups.items()
    ))


def _vote(
    first: tuple[tuple[tuple[float, ...], str, tuple[int, ...]], ...],
    second: tuple[tuple[tuple[float, ...], str, tuple[int, ...]], ...],
    translation: tuple[float, float],
    tolerance: float,
) -> StructuralTranslationVote:
    dx, dy = translation
    pairs: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    used_second: set[int] = set()
    horizontal = vertical = 0
    rival = False
    for a, kind, path_ids in first:
        eligible = []
        for index, (b, other_kind, target_paths) in enumerate(second):
            if kind != other_kind or abs(a[4] - b[4]) > 0.05:
                continue
            if all(abs(a[k] + (dx if k in (0, 2) else dy) - b[k]) <= tolerance
                   for k in range(4)):
                eligible.append((index, target_paths))
        if len(eligible) > 1:
            rival = True
            continue
        if not eligible:
            continue
        second_index, second_paths = eligible[0]
        if second_index in used_second:
            rival = True
            continue
        used_second.add(second_index)
        pairs.append((path_ids, second_paths))
        if kind == "horizontal":
            horizontal += 1
        else:
            vertical += 1
    pairs.sort()
    # Structural-looking source ink only; NEVER enough for a W4 physical wall.
    # Require independent orientations and multiple distinct spans to avoid a
    # single dimension leader or paired hatch lines becoming a registration.
    candidate = not rival and horizontal >= 2 and vertical >= 2
    return StructuralTranslationVote(
        translation, tuple(pairs), horizontal, vertical, rival, candidate
    )


def inspect_original_structural_translation_shadow(
    source_bytes: bytes,
    *,
    source_sha256: str,
    first_page: int,
    second_page: int,
    first_bounds_pdf_pt: tuple[float, float, float, float],
    second_bounds_pdf_pt: tuple[float, float, float, float],
    candidate_translations_pdf_pt: Sequence[tuple[float, float]],
    min_length_pdf_pt: float = 20.0,
    source_stroke_width_pdf_pt: float = 0.48,
    coordinate_tolerance_pdf_pt: float = 0.06,
) -> OriginalStructuralTranslationShadow:
    if (type(source_bytes) is not bytes or not source_bytes
            or type(source_sha256) is not str
            or sha256(source_bytes).hexdigest() != source_sha256):
        raise ValueError("immutable native original source SHA mismatch")
    if (type(first_page) is not int or type(second_page) is not int
            or min(first_page, second_page) < 1
            or first_page == second_page):
        raise ValueError("two distinct native original pages required")
    if (type(min_length_pdf_pt) not in (int, float)
            or not isfinite(min_length_pdf_pt) or min_length_pdf_pt < 2.0
            or type(source_stroke_width_pdf_pt) not in (int, float)
            or not isfinite(source_stroke_width_pdf_pt)
            or source_stroke_width_pdf_pt <= 0.05
            or type(coordinate_tolerance_pdf_pt) not in (int, float)
            or not isfinite(coordinate_tolerance_pdf_pt)
            or not 0.001 <= coordinate_tolerance_pdf_pt <= 0.25):
        raise ValueError("bounded source ink measurement parameters required")
    a_bounds, b_bounds = _bounds(first_bounds_pdf_pt), _bounds(second_bounds_pdf_pt)
    if (not isinstance(candidate_translations_pdf_pt, (tuple, list))
            or not 1 <= len(candidate_translations_pdf_pt) <= 1024):
        raise ValueError("bounded complete caller translation hypotheses required")
    translations = []
    for value in candidate_translations_pdf_pt:
        if (type(value) not in (tuple, list) or len(value) != 2
                or any(type(v) not in (int, float) or not isfinite(v) for v in value)):
            raise ValueError("finite original translation pair required")
        pair = tuple(round(float(v), 5) for v in value)
        if pair in translations:
            raise ValueError("duplicated source translation hypothesis")
        translations.append(pair)
    with fitz.open(stream=source_bytes, filetype="pdf") as pdf:
        if max(first_page, second_page) > len(pdf):
            raise ValueError("original source page missing")
        first = pdf[first_page - 1]
        second = pdf[second_page - 1]
        if first.rotation != second.rotation:
            return OriginalStructuralTranslationShadow(
                EvidenceResolutionStatus.ABSTAINED, source_sha256,
                first_page, second_page, 0, 0, (), (),
                ("original_source_rotation_registration_unavailable",)
            )
        a = _strokes(first, a_bounds, min_length=min_length_pdf_pt,
                     reference_width=source_stroke_width_pdf_pt,
                     axis_tolerance=coordinate_tolerance_pdf_pt)
        b = _strokes(second, b_bounds, min_length=min_length_pdf_pt,
                     reference_width=source_stroke_width_pdf_pt,
                     axis_tolerance=coordinate_tolerance_pdf_pt)
    votes = tuple(sorted(
        (_vote(a, b, tr, coordinate_tolerance_pdf_pt) for tr in translations),
        key=lambda v: v.translation_pdf_pt
    ))
    plausible = tuple(v.translation_pdf_pt for v in votes if v.source_ink_candidate)
    status = (
        EvidenceResolutionStatus.CANDIDATE if len(plausible) == 1
        else EvidenceResolutionStatus.CONFLICT if len(plausible) > 1
        else EvidenceResolutionStatus.ABSTAINED
    )
    return OriginalStructuralTranslationShadow(
        status, source_sha256, first_page, second_page,
        len(a), len(b), votes, plausible,
        ("original_two_view_stroke_translation_candidate_only",)
        if len(plausible) == 1 else
        ("original_two_view_stroke_translation_rivals",)
        if len(plausible) > 1 else
        ("original_two_view_stroke_translation_unavailable",)
    )
