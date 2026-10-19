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
        drawings = page.get_drawings()
        if len(drawings) > 120000:
            raise ValueError("bounded_original_source_drawings_required")
        native_dim_strokes = []
        for path_id, draw in enumerate(drawings):
            if (draw.get("type") != "s"
                    or draw.get("color") != (0., 0., 0.)
                    or draw.get("stroke_opacity") != 1):
                continue
            width = draw.get("width")
            if type(width) not in (float, int) or width <= 0:
                continue
            for item_id, item in enumerate(draw.get("items") or ()):
                if len(item) < 3 or item[0] != "l":
                    continue
                a, b = item[1:3]
                if abs(a.x - b.x) > 0.03 or abs(a.y - b.y) < 30:
                    continue
                native_dim_strokes.append((
                    float((a.x + b.x) / 2),
                    float(min(a.y, b.y)), float(max(a.y, b.y)),
                    int(path_id), int(item_id), float(width),
                ))
        if len(native_dim_strokes) > 10000:
            raise ValueError("bounded_original_source_dimension_lines_required")
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
    # A printed standalone dimension can have its own exact black-stroked
    # source line. Keep ALL rivals and their native parents. This is not
    # physical overhead-face / scale / dimension-issuer authentication.
    individual_figure_stroke_candidates = []
    for value, word in number_rows:
        center_y = (word[1] + word[3]) / 2
        for stroke in native_dim_strokes:
            if (0 < stroke[0] - word[2] < 3.0
                    and stroke[1] <= center_y <= stroke[2]):
                individual_figure_stroke_candidates.append({
                    "printed_value_untrusted": value,
                    "printed_source_word_address": address(word),
                    "original_source_path_item_id": (stroke[3], stroke[4]),
                    "original_stroke_pdf_pt_not_metric": round(
                        stroke[2] - stroke[1], 5
                    ),
                    "original_dim_extension_line_owner_proven": False,
                    "physical_soffit_surface_axis_proven": False,
                })
    if len(individual_figure_stroke_candidates) > 10000:
        raise ValueError("bounded_individual_dimension_line_rivals_required")
    numbers = tuple({
        "printed_value_untrusted": value,
        "source_word_address": address(w),
        "original_bbox_pdf_pts": tuple(float(v) for v in w[:4]),
    } for value, w in number_rows)
    by_numeric_block = defaultdict(list)
    # Preserve the complete original text order within each printed number
    # while replacing a repeated full-page scan with an exact-value index.
    # A matching arithmetic total is only an untrusted source candidate.
    by_number_value = defaultdict(list)
    for value, w in number_rows:
        by_numeric_block[int(w[5])].append((value, w))
        by_number_value[value].append(w)
    chains = []
    for block, members in by_numeric_block.items():
        if not 2 <= len(members) <= 12:
            continue
        total = sum(value for value, _ in members)
        rivals = [
            w for w in by_number_value.get(total, ())
            if int(w[5]) != block
        ]
        if not rivals:
            continue
        # Search original ink for the printed dimension chain, retaining
        # every complete stroke ancestry. Nearby labels/ink are candidates,
        # not extension-line ownership or measured geometry authority.
        original_ink_chains = []
        grouped_words = sorted(
            members, key=lambda member: (member[1][1] + member[1][3]) / 2
        )
        source_letters_x2 = sum(w[2] for _, w in members) / len(members)
        for overall_word in rivals:
            for overall in native_dim_strokes:
                if not 0 < overall[0] - overall_word[2] < 3.0:
                    continue
                component_rows = []
                for _value, word in grouped_words:
                    center_y = (word[1] + word[3]) / 2
                    near = tuple(
                        stroke for stroke in native_dim_strokes
                        if 0 < stroke[0] - source_letters_x2 < 3.0
                        and stroke[1] <= center_y <= stroke[2]
                    )
                    component_rows.append(near)
                if any(not options for options in component_rows):
                    continue
                import itertools
                for combination in itertools.product(*component_rows):
                    ids = tuple((line[3], line[4]) for line in combination)
                    if len(set(ids)) != len(members):
                        continue
                    low = min(line[1] for line in combination)
                    high = max(line[2] for line in combination)
                    if abs(low - overall[1]) > 0.05 or abs(high - overall[2]) > 0.05:
                        continue
                    original_ink_chains.append({
                        "original_ink_component_path_item_ids": ids,
                        "original_ink_overall_path_item_id": (overall[3], overall[4]),
                        "original_ink_overall_line_pdf_pt_not_metric": round(
                            overall[2] - overall[1], 5
                        ),
                        "figure_extension_line_endpoint_binding_proven": False,
                        "physical_soffit_dimension_axis_proven": False,
                        "firm_metric_authority": False,
                    })
                    if len(original_ink_chains) >= 128:
                        break
                if len(original_ink_chains) >= 128:
                    break
            if len(original_ink_chains) >= 128:
                break
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
            "source_ink_line_correspondence_candidates": tuple(original_ink_chains),
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
        "original_individual_figured_stroke_candidates": tuple(
            individual_figure_stroke_candidates
        ),
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
