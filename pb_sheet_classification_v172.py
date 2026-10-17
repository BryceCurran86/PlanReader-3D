"""pb_sheet_classification_v172.py — Multi-Page Plan Classification & Sheet Role Detection Engine.

Classifies drawing pages into canonical construction sheet roles (Floor Plan, RCP, Elevation,
Schedules, Cover/Legend) and extracts storey/discipline context for PB PlanReader.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SheetClassificationRecord:
    page_id: int
    page_label: str
    canonical_role: str  # FLOOR_PLAN | REFLECTED_CEILING_PLAN | ELEVATION | FINISH_SCHEDULE | DOOR_WINDOW_SCHEDULE | COVER_INDEX_LEGEND | OTHER_GENERAL
    confidence: float
    discipline: str      # ARCHITECTURAL | STRUCTURAL | INTERIOR | GENERAL
    storey_level: str    # e.g. 'Level 1', 'Ground Floor', 'All Levels', 'Unspecified'
    primary_takeoff_target: str # 'WALL_FLOOR', 'CEILING', 'ELEVATION_SURFACE', 'FINISHES', 'OPENINGS', 'NONE'
    source_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "page_label": self.page_label,
            "canonical_role": self.canonical_role,
            "confidence": round(self.confidence, 2),
            "discipline": self.discipline,
            "storey_level": self.storey_level,
            "primary_takeoff_target": self.primary_takeoff_target,
            "source_note": self.source_note,
        }


_ROLE_RULES: Tuple[Tuple[str, float, str, str, Tuple[str, ...]], ...] = (
    ("RENDER_3D_VIEW", 0.95, "ARCHITECTURAL", "NONE", (
        "artist impression", "3d elevation", "3d view", "perspective",
        "render", "visualisation", "visualization",
    )),
    ("REFLECTED_CEILING_PLAN", 0.95, "ARCHITECTURAL", "CEILING", (
        "reflected ceiling", "rcp", "ceiling plan",
    )),
    ("DOOR_WINDOW_SCHEDULE", 0.95, "ARCHITECTURAL", "OPENINGS", (
        "door schedule", "window schedule", "door & window", "door and window",
        "opening schedule", "door elevations", "window elevations",
    )),
    ("FINISH_SCHEDULE", 0.95, "INTERIOR", "FINISHES", (
        "finish schedule", "finishes schedule", "paint schedule", "room finish",
    )),
    ("COVER_INDEX_LEGEND", 0.95, "GENERAL", "NONE", (
        "cover sheet", "title sheet", "locality plan", "drawing index",
        "legend & notes", "abbreviations",
    )),
    ("ELEVATION", 0.90, "ARCHITECTURAL", "ELEVATION_SURFACE", (
        "external elevation", "internal elevation", "elevations", "elevation",
        "facade", "building section", "wall section", "cross section",
        "sections", "section",
    )),
    ("FLOOR_PLAN", 0.90, "ARCHITECTURAL", "WALL_FLOOR", (
        "ground floor plan", "floor plan", "ground plan", "basement plan",
        "layout plan",
    )),
)
_ROLE_BY_NAME = {rule[0]: rule for rule in _ROLE_RULES}


def _reference_line(line: str) -> bool:
    return line.startswith(("refer ", "see ", "matchline ", "keynote "))


def _phrase_hit(line: str, phrase: str) -> bool:
    if " " in phrase or "&" in phrase:
        return phrase in line
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", line) is not None


def _roles_on_line(line: str) -> set[str]:
    matched = [
        (name, phrase)
        for name, _confidence, _discipline, _target, phrases in _ROLE_RULES
        for phrase in phrases
        if _phrase_hit(line, phrase)
    ]
    kept = [
        name
        for name, phrase in matched
        if not any(phrase != other and phrase in other for _name, other in matched)
    ]
    return set(kept)


def _roles_in_text(text: str) -> set[str]:
    found: set[str] = set()
    for raw in str(text or "").splitlines() or [""]:
        line = re.sub(r"\s+", " ", raw).strip().lower()
        if not line or _reference_line(line):
            continue
        found.update(_roles_on_line(line))
    return found


def _role_result(name: str) -> Tuple[str, float, str, str]:
    role, confidence, discipline, target, _phrases = _ROLE_BY_NAME[name]
    return (role, confidence, discipline, target)


def classify_sheet_role(title: str, text_content: str = "") -> Tuple[str, float, str, str]:
    """Classify a sheet from its own title, then from its own body text.

    Two roles abstain. A storey number is not a sheet type, a reference line
    does not vote, and the first matching category is not a winner.
    """
    title_roles = _roles_in_text(title)
    if len(title_roles) > 1:
        return ("OTHER_GENERAL", 0.0, "GENERAL", "NONE")
    if len(title_roles) == 1:
        return _role_result(next(iter(title_roles)))
    body_roles = _roles_in_text(text_content)
    if len(body_roles) == 1:
        return _role_result(next(iter(body_roles)))
    return ("OTHER_GENERAL", 0.0, "GENERAL", "NONE")


def _canonical_storey(token: str) -> str:
    compact = re.sub(r"\s+", " ", token).strip().lower()
    level = re.fullmatch(r"level\s*(\d{1,2})", compact)
    if level:
        return f"level {int(level.group(1))}"
    coded = re.fullmatch(r"l\s*(\d{1,2})", compact)
    if coded:
        return f"level {int(coded.group(1))}"
    if compact.startswith("roof"):
        return "roof"
    return compact


def _display_storey(key: str) -> str:
    if key.startswith("level "):
        return f"Level {key.split()[1]}"
    return key.title()


def extract_storey_level(text: str) -> str:
    """Return one storey. Two different storeys abstain."""
    if not text:
        return "Unspecified"
    found: set[str] = set()
    for match in re.finditer(
        r"(ground\s*floor|level\s*\d{1,2}|basement(?:\s*\d)?|mezzanine|roof(?:\s*plan)?)",
        text,
        re.IGNORECASE,
    ):
        found.add(_canonical_storey(match.group(1)))
    for match in re.finditer(r"\bL(\d{1,2})\b", text, re.IGNORECASE):
        found.add(f"level {int(match.group(1))}")
    if len(found) != 1:
        return "Unspecified"
    return _display_storey(next(iter(found)))


class SheetClassificationRegistry:
    """Manages sheet role classifications across all pages in a workspace."""

    def __init__(self, records: List[SheetClassificationRecord]):
        self.records = records
        self._by_id = {r.page_id: r for r in records}

    @classmethod
    def derive_for_workspace(cls, conn: sqlite3.Connection, workspace_id: int) -> "SheetClassificationRegistry":
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, page_label, page_type
            FROM pages
            WHERE workspace_id=?
            ORDER BY id ASC
            """,
            (workspace_id,)
        )
        pages = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

        records = []
        for p in pages:
            pid = int(p["id"])
            label = str(p.get("page_label") or "")
            ptype = str(p.get("page_type") or "")

            role, conf, disc, target = classify_sheet_role(f"{label} {ptype}")
            level = extract_storey_level(label)

            records.append(SheetClassificationRecord(
                page_id=pid,
                page_label=label,
                canonical_role=role,
                confidence=conf,
                discipline=disc,
                storey_level=level,
                primary_takeoff_target=target,
                source_note=f"Classified as {role} ({target})",
            ))

        return cls(records)

    def apply_roles_to_db(self, conn: sqlite3.Connection, workspace_id: int) -> int:
        """Update page_type column in pages table with canonical roles."""
        cur = conn.cursor()
        count = 0
        for r in self.records:
            cur.execute(
                "UPDATE pages SET page_type=? WHERE id=? AND workspace_id=?",
                (r.canonical_role, r.page_id, workspace_id)
            )
            count += 1
        conn.commit()
        return count


def derive_sheet_classifications(conn: sqlite3.Connection, workspace_id: int) -> SheetClassificationRegistry:
    return SheetClassificationRegistry.derive_for_workspace(conn, workspace_id)
