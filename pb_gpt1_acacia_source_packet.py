"""Original Acacia House four-role source admission — no takeoff authority.

This verifies that the *same* exact regional source contains its genuine
floor, section, setout and window/door schedule. It does not OCR outlined
dimension glyphs, invent installed openings, close walls or issue quantities.
Never use a cover drawing index as evidence of a sheet's title.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from stat import S_ISREG

import fitz

ACACIA_ORIGINAL_SHA256 = {
    "Sydney": "f5ac166a21c9348c5ee55a7e518ec487140e9888d8af21fa39dbc5a9ca28000e",
    "Melbourne": "fcc5e032968f62028dd4254db61bb676582027655881ecbad7a21001ef12cd2a",
    "Brisbane": "435a6b610fea904f2b27dc330667d92a25919ada3368e5905e58ff92e047f37a",
}
# Page numbers are zero-based. Source title block says 2/10,8/10,9/10,10/10.
ACACIA_REQUIRED_ROLES = (
    (1, "Floor Plan", "1:100"),
    (7, "Section", "1:100"),
    (8, "Setout Plan", "1:100"),
    (9, "Window and Door Schedule", "1:50"),
)
ACACIA_ALL_TITLES = (
    "Site Plan", "Floor Plan", "Roof Plan", "Elevation-East",
    "Elevation-North", "Elevation-South", "Elevation-West", "Section",
    "Setout Plan", "Window and Door Schedule",
)
_TITLE_FIELDS = (
    "Drawing title", "Scale", "Paper size", "Drawing number",
    "Date issued", "Project stage",
)


@dataclass(frozen=True)
class AcaciaOriginalSheet:
    page_index: int
    drawing_title: str
    drawing_number: str
    scale: str
    source_page_path_count: int


@dataclass(frozen=True)
class AcaciaOriginalPackage:
    status: str
    reason: str
    source_sha256: str
    region: str | None
    source_pages: int = 0
    sheets: tuple[AcaciaOriginalSheet, ...] = ()
    original_byte_roles_verified: bool = False
    physical_outer_wall_verified: bool = False
    interior_finished_face_verified: bool = False
    cross_sheet_metric_bindings_verified: bool = False
    installed_door_window_hosts_verified: bool = False
    finish_material_authorized: bool = False
    customer_quantities_authorized: bool = False
    frozen120_score_authorized: bool = False

    def to_dict(self):
        return {
            "status": self.status, "reason": self.reason,
            "source_sha256": self.source_sha256,
            "region": self.region, "source_pages": self.source_pages,
            "sheets": [vars(s) for s in self.sheets],
            "original_byte_roles_verified": self.original_byte_roles_verified,
            "physical_outer_wall_verified": False,
            "interior_finished_face_verified": False,
            "cross_sheet_metric_bindings_verified": False,
            "installed_door_window_hosts_verified": False,
            "finish_material_authorized": False,
            "customer_quantities_authorized": False,
            "frozen120_score_authorized": False,
            "missing_original_design_options_specification": True,
        }


def _single_field(text: str, field: str, next_field: str) -> str:
    # The optional wrapped p10 title becomes "Window and Door Schedule".
    flattened = " ".join(text.split())
    pattern = (r"\b" + re.escape(field) + r"\s*:\s*(.*?)\s*"
               r"(?=\b" + re.escape(next_field) + r"\s*:)")
    matches = re.findall(pattern, flattened, flags=re.IGNORECASE)
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError("acacia_source_title_block_missing_or_ambiguous_" +
                         field.casefold().replace(" ", "_"))
    return " ".join(matches[0].split())


def _title_block(text: str, page_index: int, region: str) -> tuple[str, str, str]:
    title = _single_field(text, "Drawing title", "Scale")
    scale = _single_field(text, "Scale", "Paper size")
    paper = _single_field(text, "Paper size", "Drawing number")
    number = _single_field(text, "Drawing number", "Date issued")
    date = _single_field(text, "Date issued", "Project stage")
    stage = _single_field(text, "Project stage", "DISCLAIMER")
    if (title.casefold() != ACACIA_ALL_TITLES[page_index].casefold()
            or number != f"{page_index + 1}/10"
            or paper != "A3" or date != "June 2023"
            or stage.casefold() != "preliminary"):
        raise ValueError("acacia_source_sheet_metadata_conflict")
    required = {idx: (name, s) for idx, name, s in ACACIA_REQUIRED_ROLES}
    if page_index in required and (
            title.casefold() != required[page_index][0].casefold()
            or scale != required[page_index][1]):
        raise ValueError("acacia_source_role_scale_conflict")
    # Do not admit a wrong region even if it uses an otherwise valid title.
    # Check the explicitly printed DESIGNED FOR field, not arbitrary text.
    designed_for = re.findall(
        r"\bDESIGNED\s+FOR\s+(Sydney|Melbourne|Brisbane)\s+Technical\s+drawings",
        " ".join(text.split()), flags=re.IGNORECASE)
    if len(designed_for) != 1 or designed_for[0].casefold() != region.casefold():
        raise ValueError("acacia_source_region_field_conflict")
    if "Design Options" not in text:
        raise ValueError("acacia_source_missing_reference_to_unprovided_spec")
    return title, number, scale


def inspect_acacia_original_bytes(raw: bytes, *, expected_region: str) -> AcaciaOriginalPackage:
    """Validate exact original source bytes and four page roles fail-closed."""
    if type(raw) is not bytes or type(expected_region) is not str:
        raise ValueError("acacia_source_invalid_input_types")
    pinned = ACACIA_ORIGINAL_SHA256.get(expected_region)
    if pinned is None:
        raise ValueError("acacia_source_unrecognized_region")
    digest = sha256(raw).hexdigest()
    if digest != pinned:
        # Never parse a foreign/replaced source to discover "matching" roles.
        return AcaciaOriginalPackage(
            "ABSTAINED", "acacia_original_sha256_or_region_mismatch",
            digest, expected_region,
        )
    try:
        with fitz.open(stream=raw, filetype="pdf") as source:
            if len(source) != 10:
                return AcaciaOriginalPackage(
                    "ABSTAINED", "acacia_original_sheet_count_mismatch",
                    digest, expected_region, source_pages=len(source),
                )
            sheets = []
            for index, page in enumerate(source):
                title, number, scale = _title_block(
                    page.get_text(), index, expected_region
                )
                if index in (1, 7, 8, 9):
                    sheets.append(AcaciaOriginalSheet(
                        index, title, number, scale, len(page.get_drawings())
                    ))
        return AcaciaOriginalPackage(
            "ORIGINAL_ROLES_AUTHENTICATED_REVIEW_ONLY",
            "exact_original_four_roles_verified_missing_physical_metric_and_spec",
            digest, expected_region, 10, tuple(sheets),
            original_byte_roles_verified=True,
        )
    except (RuntimeError, ValueError, TypeError, OSError, IndexError):
        return AcaciaOriginalPackage(
            "ABSTAINED", "acacia_original_sheet_title_or_role_unverified",
            digest, expected_region,
        )


def inspect_acacia_original_file(path: Path, *, expected_region: str) -> AcaciaOriginalPackage:
    """Reject symlinks/directory inputs; byte identity always wins over name."""
    path = Path(path)
    try:
        if not S_ISREG(path.lstat().st_mode):
            raise ValueError("acacia_original_regular_file_required")
        return inspect_acacia_original_bytes(path.read_bytes(),
                                             expected_region=expected_region)
    except (OSError, ValueError):
        return AcaciaOriginalPackage(
            "ABSTAINED", "acacia_original_file_not_regular_or_unavailable",
            "", expected_region,
        )
