"""pb_title_block_extractor_v173.py — Vector & Text Title Block / Scale Bar / Legend Extraction Engine.

Extracts structured title block fields (Project Name, Job No, Drawing Title, Sheet No, Revision,
Date, Scale, Architect), scale bar geometries, and legend symbol keys for PB PlanReader.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import pb_page_title_authority as title_authority


@dataclass
class TitleBlockMetadata:
    page_id: int
    project_name: str
    job_no: str
    drawing_title: str
    sheet_no: str
    revision: str
    scale_text: str
    date_str: str
    architect_name: str
    legend_keys: Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.90

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "project_name": self.project_name,
            "job_no": self.job_no,
            "drawing_title": self.drawing_title,
            "sheet_no": self.sheet_no,
            "revision": self.revision,
            "scale_text": self.scale_text,
            "date_str": self.date_str,
            "architect_name": self.architect_name,
            "legend_keys": self.legend_keys,
            "confidence": round(self.confidence, 2),
        }


_JOB_RE = re.compile(
    r"(?:job|project|proj)[\s\-_#]*no\.?[\s:]*([a-z0-9\-_]{3,15})",
    re.IGNORECASE,
)
_SHEET_RE = re.compile(
    r"(?:dwg|drawing|sheet)[\s\-_#]*no\.?[\s:]*([a-z]{1,2}[\s\-_]?\d{3,4}[a-z]?)",
    re.IGNORECASE,
)
_REV_RE = re.compile(
    r"rev(?:ision)?(?![a-z0-9])[\s\-_:]*([a-z0-9]{1,3})\b",
    re.IGNORECASE,
)
_SCALE_RE = re.compile(
    r"scale[\s:]*(1\s*[:/]\s*\d{2,4}(?:\s*@\s*a[130])?)",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\bdate[\s:]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})\b",
    re.IGNORECASE,
)
_LEGEND_RE = re.compile(
    r"^\s*([a-z0-9]{1,4})\s*[:=\-]\s*(.{4,50})$",
    re.IGNORECASE,
)


def _one_printed_value(values: List[str]) -> Tuple[str, bool]:
    """Keep a value only when every reading is the same non-empty value."""

    distinct = {value for value in values if value}
    if len(distinct) == 1:
        return next(iter(distinct)), False
    return "", len(distinct) > 1


def extract_title_block_from_text(page_id: int, text: str) -> TitleBlockMetadata:
    """Extract structured title block fields and legend symbol keys from page text content.

    A field printed twice with two different values stays empty. The same
    value printed twice is kept. An unlabelled date-shaped token is not a date,
    and the word REVISIONS is not revision S.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    job_values: List[str] = []
    sheet_values: List[str] = []
    revision_values: List[str] = []
    scale_values: List[str] = []
    date_values: List[str] = []
    title_values: List[str] = []
    legend_values: Dict[str, List[str]] = {}
    conflict = False

    for l in lines:
        job_values.extend(match.group(1).upper() for match in _JOB_RE.finditer(l))
        sheet_values.extend(
            match.group(1).upper().replace(" ", "")
            for match in _SHEET_RE.finditer(l)
        )
        revision_values.extend(match.group(1).upper() for match in _REV_RE.finditer(l))
        scale_values.extend(match.group(1) for match in _SCALE_RE.finditer(l))
        date_values.extend(match.group(1) for match in _DATE_RE.finditer(l))

        legend = _LEGEND_RE.search(l)
        if legend:
            key = legend.group(1).upper()
            legend_values.setdefault(key, []).append(legend.group(2).strip())

        # Drawing Title: only a value bound to a title label ("DRAWING TITLE:",
        # "SHEET TITLE:", "TITLE:"; never "PROJECT TITLE"). Text alone has no
        # geometry to tell a sheet title from a note that mentions a plan.
        label = title_authority.parse_label(title_authority.Cell(l, 0.0, 0.0, 1.0, 1.0, 1.0))
        if (label is not None and label.field == "title" and label.remainder
                and title_authority.title_shape(label.remainder, bound=True)[0] > 0):
            title_values.append(label.remainder)

    job_no, job_conflict = _one_printed_value(job_values)
    sheet_no, sheet_conflict = _one_printed_value(sheet_values)
    revision, revision_conflict = _one_printed_value(revision_values)
    scale_text, scale_conflict = _one_printed_value(scale_values)
    date_str, date_conflict = _one_printed_value(date_values)
    drawing_title, title_conflict = _one_printed_value(title_values)
    conflict = any((
        job_conflict,
        sheet_conflict,
        revision_conflict,
        scale_conflict,
        date_conflict,
        title_conflict,
    ))

    legend_keys: Dict[str, str] = {}
    for key, descriptions in legend_values.items():
        description, key_conflict = _one_printed_value(descriptions)
        if key_conflict:
            conflict = True
            continue
        if description:
            legend_keys[key] = description

    # Fail closed: a field the text does not support, or that prints two
    # different values, stays empty. There is no default title, sheet number,
    # revision, scale, date or party.
    if conflict:
        confidence = 0.0
    elif sheet_no or scale_text:
        confidence = 0.90
    else:
        confidence = 0.60
    return TitleBlockMetadata(
        page_id=page_id,
        project_name="",
        job_no=job_no,
        drawing_title=drawing_title,
        sheet_no=sheet_no,
        revision=revision,
        scale_text=scale_text,
        date_str=date_str,
        architect_name="",
        legend_keys=legend_keys,
        confidence=confidence,
    )


class TitleBlockRegistry:
    """Manages title block metadata across all pages in a workspace."""

    def __init__(self, metadata_list: List[TitleBlockMetadata]):
        self.metadata_list = metadata_list
        self._by_id = {m.page_id: m for m in metadata_list}

    @classmethod
    def derive_for_workspace(cls, conn: sqlite3.Connection, workspace_id: int) -> "TitleBlockRegistry":
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, page_label, scale_text
            FROM pages
            WHERE workspace_id=?
            ORDER BY id ASC
            """,
            (workspace_id,)
        )
        pages = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

        results = []
        for p in pages:
            pid = int(p["id"])
            label = str(p.get("page_label") or "")
            stext = str(p.get("scale_text") or "")

            meta = extract_title_block_from_text(pid, f"{label}\nScale {stext}")
            results.append(meta)

        return cls(results)


def derive_title_block_metadata(conn: sqlite3.Connection, workspace_id: int) -> TitleBlockRegistry:
    return TitleBlockRegistry.derive_for_workspace(conn, workspace_id)
