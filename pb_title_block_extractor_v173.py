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
    """Extract structured title block fields and legend symbol keys from page text content."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    project_name = ""
    job_no = ""
    drawing_title = ""
    sheet_no = ""
    revision = ""
    scale_text = ""
    date_str = ""
    architect = ""
    legend_keys: Dict[str, str] = {}

    for l in lines:
        # Job No
        if not job_no:
            m_job = re.search(r'(?:job|project|proj)[\s\-_#]*no\.?[\s:]*([a-z0-9\-_]{3,15})', l, re.IGNORECASE)
            if m_job:
                job_no = m_job.group(1).upper()

        # Sheet No
        if not sheet_no:
            m_sheet = re.search(r'(?:dwg|drawing|sheet)[\s\-_#]*no\.?[\s:]*([a-z]{1,2}[\s\-_]?\d{3,4}[a-z]?)', l, re.IGNORECASE)
            if m_sheet:
                sheet_no = m_sheet.group(1).upper().replace(" ", "")

        # Revision
        m_rev = re.search(r'rev(?:ision)?[\s\-_:]*([a-z0-9]{1,3})', l, re.IGNORECASE)
        if m_rev:
            revision = m_rev.group(1).upper()

        # Scale
        if not scale_text:
            m_scale = re.search(r'scale[\s:]*(1\s*[:/]\s*\d{2,4}(?:\s*@\s*a[130])?)', l, re.IGNORECASE)
            if m_scale:
                scale_text = m_scale.group(1)

        # Date
        if not date_str:
            m_date = re.search(r'(?:date[\s:]*)?(\d{1,2}[/\.\-]\d{1,2}[/\.\-]\d{2,4})', l, re.IGNORECASE)
            if m_date:
                date_str = m_date.group(1)

        # Legend Keys (e.g. 'P1 - Low Sheen Wall System', 'FC01 = Fibre Cement')
        m_leg = re.search(r'^\s*([a-z0-9]{1,4})\s*[:=\-]\s*(.{4,50})$', l, re.IGNORECASE)
        if m_leg:
            key = m_leg.group(1).upper()
            val = m_leg.group(2).strip()
            legend_keys[key] = val

        # Drawing Title: only a value bound to a title label ("DRAWING TITLE:",
        # "SHEET TITLE:", "TITLE:"; never "PROJECT TITLE"). Text alone has no
        # geometry to tell a sheet title from a note that mentions a plan.
        if not drawing_title:
            label = title_authority.parse_label(title_authority.Cell(l, 0.0, 0.0, 1.0, 1.0, 1.0))
            if (label is not None and label.field == "title" and label.remainder
                    and title_authority.title_shape(label.remainder, bound=True)[0] > 0):
                drawing_title = label.remainder

    # Fail closed: a field the text does not support stays empty. There is no
    # default title, sheet number, revision, scale, date or party.
    return TitleBlockMetadata(
        page_id=page_id,
        project_name=project_name,
        job_no=job_no,
        drawing_title=drawing_title,
        sheet_no=sheet_no,
        revision=revision,
        scale_text=scale_text,
        date_str=date_str,
        architect_name=architect,
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
            SELECT id, page_label, scale_text, file_name
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
            fname = str(p.get("file_name") or "")

            meta = extract_title_block_from_text(pid, f"{label}\nScale {stext}\n{fname}")
            results.append(meta)

        return cls(results)


def derive_title_block_metadata(conn: sqlite3.Connection, workspace_id: int) -> TitleBlockRegistry:
    return TitleBlockRegistry.derive_for_workspace(conn, workspace_id)
