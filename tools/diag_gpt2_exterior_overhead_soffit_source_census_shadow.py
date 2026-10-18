"""Exterior overhead soffit/cladding original-source census, NOT a takeoff.

Source-native printed labels and dimension arithmetic nominate witnesses only:
they do not authenticate ink/clip, structural faces, dimension extension lines,
material ownership, a canopy union, metric area, or contractor painting scope.
No customer QuantityEvidence or CarpentryTakeoffItem is created.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

import fitz

_NUMERIC = re.compile(r"[0-9]{2,6}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9]{1,7}\Z")


def audit_exterior_overhead_source_census_shadow(
    pdf_bytes: bytes, *, expected_sha256: str, page_number: int,
    material_code: str,
) -> dict:
    """Preserve ALL native code/dimension competitors; never elect one span.

    Printed descriptions and numbers are UNTRUSTED native text candidates.
    Source producer glyph/active paint/clip and figured extension-line issuers
    must independently prove them before any commercial publication.
    """
    if (type(pdf_bytes) is not bytes or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256):
        raise ValueError("immutable_original_pdf_source_sha_required")
    if type(page_number) is not int or page_number <= 0:
        raise ValueError("positive_original_page_number_required")
    if type(material_code) is not str or not _CODE.fullmatch(material_code):
        raise ValueError("literal_original_material_code_required")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if page_number > len(doc):
            raise ValueError("original_source_page_out_of_range")
        page = doc[page_number - 1]
        words = tuple(page.get_text("words", sort=False))
    if len(words) > 120000:
        return {
            "status": "source_word_universe_over_bound",
            "first_unclosed_gate": "complete_original_source_word_universe",
            "new_firm_quantities": 0,
            "exterior_soffit_area_m2": None,
        }
    def address(w):
        return (page_number, int(w[5]), int(w[6]), int(w[7]))
    by_block = defaultdict(list)
    for w in words:
        by_block[int(w[5])].append(w)
    codes = [
        {"source_word_address": address(w),
         "original_literal_untrusted": str(w[4]),
         "original_bbox_pdf_pts": tuple(float(v) for v in w[:4])}
        for w in words if str(w[4]) == material_code
    ]
    # A genuine legend may have many different codes in one PDF block.
    # A sole code accompanied by explicit SOFFIT + CLADDING nouns in
    # its own source block is only a MATERIAL DEFINITION CANDIDATE.
    definitions = []
    for block, rows in by_block.items():
        strings = [str(w[4]).upper().strip(".,") for w in rows]
        if (strings.count(material_code) == 1 and "SOFFIT" in strings
                and "CLADDING" in strings):
            definitions.append({
                "block_no": block,
                "material_code_word_address": next(
                    address(w) for w in rows if w[4] == material_code
                ),
                "source_description_word_addresses": tuple(
                    address(w) for w in rows if w[4] != material_code
                ),
                "native_description_literals_untrusted": tuple(strings),
                "material_definition_issued": False,
            })
    # Enumerate all source-number groups and ALL arithmetic competitors.
    # An equality does not bind any printed figure to physical endpoints.
    number_rows = [
        (int(w[4]), w) for w in words if _NUMERIC.fullmatch(str(w[4]))
    ]
    numbers = tuple({
        "printed_value_untrusted": value,
        "source_word_address": address(w),
        "original_bbox_pdf_pts": tuple(float(v) for v in w[:4]),
    } for value, w in number_rows)
    by_numeric_block = defaultdict(list)
    for value, w in number_rows:
        by_numeric_block[int(w[5])].append((value, w))
    chains = []
    for block, members in by_numeric_block.items():
        if not 2 <= len(members) <= 12:
            continue
        total = sum(value for value, _ in members)
        rivals = [
            w for value, w in number_rows
            if value == total and int(w[5]) != block
        ]
        if not rivals:
            continue
        chains.append({
            "component_source_word_addresses": tuple(
                address(w) for _, w in members
            ),
            "component_printed_values_untrusted": tuple(v for v, _ in members),
            "arithmetic_total_untrusted": total,
            "rival_total_source_word_addresses": tuple(
                address(w) for w in rivals
            ),
            "source_extension_lines_proven": False,
            "physical_soffit_axes_proven": False,
        })
    chains.sort(key=lambda c: c["component_source_word_addresses"])
    return {
        "status": (
            "original_exterior_overhead_source_candidates_only"
            if codes else "source_material_mark_unavailable"
        ),
        "material_code": material_code,
        "original_page_number": page_number,
        "original_source_sha256": expected_sha256,
        "all_original_code_word_candidates": tuple(codes),
        "original_soffit_material_description_candidates": tuple(definitions),
        "original_figured_number_candidates": numbers,
        "all_competing_figured_arithmetic_chains": tuple(chains),
        "external_material_issuer_authenticated": False,
        "source_clip_and_active_paint_authenticated": False,
        "original_dimension_axes_and_extension_lines_proven": False,
        "physical_overhead_surface_polygon_proven": False,
        "source_canopy_union_overlap_proven": False,
        "source_contractor_scope_proven": False,
        "source_fascia_or_gutter_quantity_proven": False,
        "exterior_soffit_area_m2": None,
        "new_firm_quantities": 0,
        "first_unclosed_gate": (
            "source_active_paint_clip_material_and_physical_overhead_owner"
            if codes else "original_source_material_mark_unavailable"
        ),
    }
