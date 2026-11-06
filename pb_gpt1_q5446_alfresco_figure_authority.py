"""Original outlined-ink Q5446 ALFRESCO figured area witness.

Independent native page-one dimension figures and their printed dimension
lines must all be present. They corroborate the separate architectural
schedule, but this receipt alone does not grant floor finish, net interior
floor, physical W4 ownership, or customer quantity authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math

from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256

FIGURE_HORIZONTAL_PATHS = (6863, 6864, 6865, 6866)
FIGURE_VERTICAL_PATHS = (10682, 10683, 10684, 10685)
FIGURE_HORIZONTAL_LINE = 6838
FIGURE_VERTICAL_LINE = 10657
PLAN_ALFRESCO_LABEL_PATHS = tuple(range(5494, 5599))
SOURCE_PRIMITIVE_CAP = 20000
EPSILON_PT = 0.05


@dataclass(frozen=True)
class OriginalAlfrescoFigureWitness:
    source_sha256: str
    horizontal_mm: int
    vertical_mm: int
    area_m2: Decimal
    source_vector_path_ids: tuple[int, ...]
    status: str = "CANDIDATE"
    diagnostic_only: bool = True


def _rect(record):
    r = record.get("rect")
    try:
        values = tuple(float(x) for x in (r.x0, r.y0, r.x1, r.y1))
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(x) for x in values):
        return None
    if values[0] > values[2] or values[1] > values[3]:
        return None
    return values


def _stroke(record, width):
    return (
        record.get("type") == "s"
        and record.get("color") == (0.0, 0.0, 0.0)
        and type(record.get("width")) in (int, float)
        and abs(record["width"] - width) <= EPSILON_PT
        and _rect(record) is not None
    )


def _digit(record, vertical):
    if not _stroke(record, 0.72):
        return None
    b = _rect(record)
    w, h = b[2] - b[0], b[3] - b[1]
    if vertical:
        if not (5.6 < w < 6.0 and 2.8 < h < 3.9):
            return None
    elif not (3.0 < w < 3.9 and 5.6 < h < 6.0):
        return None
    lines = record.get("items")
    if type(lines) not in (tuple, list) or not lines or lines[0][0] != "l":
        return None
    try:
        px = (float(lines[0][1].x) - b[0]) / w
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None
    if not vertical and len(lines) == 14:
        return "3"
    if vertical and len(lines) == 3 and h >= 3.4:
        return "4"
    if len(lines) == 16 and ((vertical and px < .05) or
                             (not vertical and .3 < px < .55)):
        return "0"
    return None


def original_alfresco_figure_witness(drawings):
    """Read actual original dimension strokes, not a transcribed gold number."""
    if type(drawings) is not list or len(drawings) > SOURCE_PRIMITIVE_CAP:
        return None
    ids = (*FIGURE_HORIZONTAL_PATHS, *FIGURE_VERTICAL_PATHS,
           FIGURE_HORIZONTAL_LINE, FIGURE_VERTICAL_LINE,
           *PLAN_ALFRESCO_LABEL_PATHS)
    if len(ids) != len(set(ids)) or any(i < 0 or i >= len(drawings) for i in ids):
        return None

    horizontal = []
    vertical = []
    for path, is_vertical, digits in ((FIGURE_HORIZONTAL_PATHS, False, horizontal),
                                      (FIGURE_VERTICAL_PATHS, True, vertical)):
        for i in path:
            b = _rect(drawings[i])
            if b is None:
                return None
            if is_vertical:
                if not (1048 < b[0] < b[2] < 1065 and 395 < b[1] < b[3] < 420):
                    return None
            elif not (825 < b[0] < b[2] < 851 and 650 < b[1] < b[3] < 665):
                return None
            digit = _digit(drawings[i], is_vertical)
            if digit is None:
                return None
            digits.append(digit)

    # Exact source-dimension line/terminator span; never convert its PDF points.
    for i, expected in (
        (FIGURE_HORIZONTAL_LINE, (799.68, 661.8, 880.32, 661.8)),
        (FIGURE_VERTICAL_LINE, (1061.28, 352.8, 1061.28, 461.64)),
    ):
        record = drawings[i]
        if not _stroke(record, 0.48) or len(record.get("items", ())) != 1:
            return None
        if any(abs(x - y) > EPSILON_PT for x, y in zip(_rect(record), expected)):
            return None

    label_boxes = []
    for i in PLAN_ALFRESCO_LABEL_PATHS:
        record = drawings[i]
        b = _rect(record)
        if not _stroke(record, 0.96) or b is None:
            return None
        if not (813 <= b[0] <= b[2] < 869 and 395 <= b[1] <= b[3] < 403):
            return None
        label_boxes.append(b)
    label = (min(b[0] for b in label_boxes), min(b[1] for b in label_boxes),
             max(b[2] for b in label_boxes), max(b[3] for b in label_boxes))
    if any(abs(x-y) > EPSILON_PT for x,y in
           zip(label, (813.84, 395.28, 867.84, 402.24))):
        return None

    h_mm = int("".join(horizontal))
    v_mm = int("".join(vertical))
    if not (100 <= h_mm <= 50000 and 100 <= v_mm <= 50000):
        return None
    return OriginalAlfrescoFigureWitness(
        SOURCE_SHA256, h_mm, v_mm,
        Decimal(h_mm) * Decimal(v_mm) / Decimal(1000000),
        ids,
    )
