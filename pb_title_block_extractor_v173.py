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


def extract_title_block_from_text(page_id: int, text: str) -> TitleBlockMetadata:
    """Extract structured title block fields and legend symbol keys from page text content.

    A field with two different printed values stays empty. The same value
    repeated is kept. A filename is not read here.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    job_nos: List[str] = []
    sheet_nos: List[str] = []
    revisions: List[str] = []
    scales: Dict[str, str] = {}
    dates: List[str] = []
    titles: List[str] = []
    legend_values: Dict[str, List[str]] = {}
    revision_re = re.compile(
        r"(?<![A-Za-z])rev(?:ision)?[\s\-_:]+([A-Za-z0-9]{1,3})(?![A-Za-z0-9])",
        re.IGNORECASE,
    )

    for line in lines:
        job_match = re.search(
            r"(?:job|project|proj)[\s\-_#]*no\.?[\s:]*([a-z0-9\-_]{3,15})",
            line,
            re.IGNORECASE,
        )
        if job_match:
            job_no = job_match.group(1).upper()
            if job_no not in job_nos:
                job_nos.append(job_no)

        sheet_match = re.search(
            r"(?:dwg|drawing|sheet)[\s\-_#]*no\.?[\s:]*([a-z]{1,2}[\s\-_]?\d{3,4}[a-z]?)",
            line,
            re.IGNORECASE,
        )
        if sheet_match:
            sheet_no = sheet_match.group(1).upper().replace(" ", "")
            if sheet_no not in sheet_nos:
                sheet_nos.append(sheet_no)

        revision_match = revision_re.search(line)
        if revision_match:
            revision = revision_match.group(1).upper()
            if revision not in revisions:
                revisions.append(revision)

        scale_match = re.search(
            r"scale[\s:]*(1\s*[:/]\s*\d{2,4}(?:\s*@\s*a[130])?)",
            line,
            re.IGNORECASE,
        )
        if scale_match:
            raw_scale = scale_match.group(1).strip()
            scale_key = re.sub(r"\s+", "", raw_scale).upper()
            scales.setdefault(scale_key, raw_scale)

        date_match = re.search(
            r"date[\s:]*(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})",
            line,
            re.IGNORECASE,
        )
        if date_match:
            date_str = date_match.group(1)
            if date_str not in dates:
                dates.append(date_str)

        legend_match = re.search(r"^\s*([a-z0-9]{1,4})\s*[:=\-]\s*(.{4,50})$", line, re.IGNORECASE)
        if legend_match:
            key = legend_match.group(1).upper()
            value = legend_match.group(2).strip()
            values = legend_values.setdefault(key, [])
            if value not in values:
                values.append(value)

        label = title_authority.parse_label(title_authority.Cell(line, 0.0, 0.0, 1.0, 1.0, 1.0))
        if (label is not None and label.field == "title" and label.remainder
                and title_authority.title_shape(label.remainder, bound=True)[0] > 0):
            if label.remainder not in titles:
                titles.append(label.remainder)

    def _one(values: List[str]) -> str:
        return values[0] if len(values) == 1 else ""

    legend_keys = {
        key: values[0]
        for key, values in legend_values.items()
        if len(values) == 1
    }
    sheet_no = _one(sheet_nos)
    scale_text = next(iter(scales.values())) if len(scales) == 1 else ""
    return TitleBlockMetadata(
        page_id=page_id,
        project_name="",
        job_no=_one(job_nos),
        drawing_title=_one(titles),
        sheet_no=sheet_no,
        revision=_one(revisions),
        scale_text=scale_text,
        date_str=_one(dates),
        architect_name="",
        legend_keys=legend_keys,
        confidence=0.90 if (sheet_no or scale_text) else 0.60,
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
