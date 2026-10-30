"""Source-only native grid row membership; no door quantity, metric, or benchmark."""
from dataclasses import replace
from hashlib import sha256

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_schedule_authority import SourceDoorScheduleWord
from pb_gpt2_native_grid_row_membership_shadow import (
    NativeGridRowScope, inspect_original_native_grid_row_shadow,
)


def _case(*, duplicate_code=False, untrusted=False, shifted=0.0,
          overpaint=None, image_overpaint=None, image_overlay=True,
          rotation=0, stroke_overpaint=None, stroke_shift=0.0,
          stroke_horizontal=False, stroke_before=False):
    pdf = fitz.open()
    page = pdf.new_page(width=420, height=340)

    def _paint_strokes():
        if stroke_overpaint is None:
            return
        for x in (100+shifted, 142+shifted):
            if stroke_horizontal:
                start, end, width = (x-5, 60), (x+5, 60), .48
            else:
                start, end, width = (
                    (x+stroke_shift, 45), (x+stroke_shift, 85), 2.0
                )
            page.draw_line(
                fitz.Point(*start), fitz.Point(*end),
                color=stroke_overpaint, width=width,
            )

    if stroke_before:
        _paint_strokes()
    for x in (100+shifted, 142+shifted):
        for a,b in ((30,100),(100,170),(170,260)):
            page.draw_line(fitz.Point(x,a),fitz.Point(x,b),
                           color=(0,0,0),width=.48)
    if not stroke_before:
        _paint_strokes()
    if overpaint is not None:
        for x in (100+shifted, 142+shifted):
            page.draw_rect(fitz.Rect(x-2,30,x+2,260),
                           color=None,fill=overpaint,overlay=True)
    if image_overpaint is not None:
        # Black images are essential: final dark pixels are NOT source ink.
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), False)
        pix.clear_with(image_overpaint)
        for x in (100+shifted, 142+shifted):
            page.insert_image(
                fitz.Rect(x-2, 30, x+2, 260),
                pixmap=pix, overlay=image_overlay,
            )
    page.set_rotation(rotation)
    content = pdf.tobytes()
    pdf.close()
    words = [
        SourceDoorScheduleWord(
            observation_id=f"native:{i}",page_id="1",partition_id="page:1",
            block_no=i,line_no=0,word_no=0,literal=literal,
            trusted=(not untrusted or i != 2),
            bbox_pdf_pts=(x+shifted,y,x+shifted+width,y+10.0),
        ) for i,(literal,x,y,width) in enumerate((
            ("D13",106,217,20), ("TRUCK",106,196,30),
            ("SWING",107,142,29), ("920",106,75,18),
            ("D14",162,214,21),
            *((("D13",107,184,20),) if duplicate_code else ()),
        ))
    ]
    return content,tuple(words),NativeGridRowScope(
        page_number=1,
        left_boundary_paths=(2,3,4) if stroke_before and stroke_overpaint is not None
            else (0,1,2),
        right_boundary_paths=(5,6,7) if stroke_before and stroke_overpaint is not None
            else (3,4,5),
        code_address=(0,0,0))


def _audit(b=None, words=None, scope=None, **kwargs):
    if b is None:
        b, words, scope = _case()
    return inspect_original_native_grid_row_shadow(
        b,source_sha256=sha256(b).hexdigest(),
        words=words,scope=scope,**kwargs)


def test_original_ruled_row_connects_multiple_native_blocks_without_grants():
    b,w,s=_case()
    result=_audit(b,w,s)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.native_blocks==(0,1,2,3)
    assert result.code_observation_id=="native:0"
    assert result.competing_same_code_observation_ids==()
    assert result.first_unclosed_gate.endswith("no_kind_host_count_or_dimensions")
    assert result.shadow_only
    assert not any((result.source_dimension_authorized,
                    result.physical_door_identity_proven,
                    result.opening_count_granted,
                    result.firm_quantity_issued,
                    result.commercial_projection_allowed))
    assert b==b[:]


def test_source_grid_metamorphic_translation_preserves_membership():
    first,w,s=_case()
    moved,wm,sm=_case(shifted=33.0)
    assert _audit(first,w,s).native_blocks==_audit(moved,wm,sm).native_blocks


def test_competing_printed_code_stays_abstained():
    b,w,s=_case(duplicate_code=True)
    result=_audit(b,w,s)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "competing_or_untrusted" in result.first_unclosed_gate


@pytest.mark.parametrize("competing_code", ["D0", "D00", "D3"])
def test_any_second_d_digit_glyph_inside_ruled_row_vetoes_unique_code(competing_code):
    # A malformed D0/D00 is still an original printed D-code competitor.
    # The clean D13 grid receipt must remain a candidate, but a second
    # source word in the SAME ruled row must never disappear by regex.
    original, words, scope = _case()
    assert _audit(original, words, scope).status is EvidenceResolutionStatus.CANDIDATE
    rival = replace(
        words[-1], literal=competing_code,
        bbox_pdf_pts=(106.0, 183.0, 124.0, 193.0),
    )
    result = _audit(original, words[:-1] + (rival,), scope)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.first_unclosed_gate == (
        "original_grid_row_competing_or_untrusted_source_words"
    )
    assert not any((
        result.source_dimension_authorized, result.physical_door_identity_proven,
        result.opening_count_granted, result.firm_quantity_issued,
        result.commercial_projection_allowed,
    ))
    assert words[-1].literal == "D14"
    assert original == bytes(original)


def test_untrusted_original_word_blocks_source_membership():
    b,w,s=_case(untrusted=True)
    assert _audit(b,w,s).status is EvidenceResolutionStatus.ABSTAINED


def test_unrelated_outside_row_code_does_not_grant_extra_door():
    b,w,s=_case()
    duplicate=replace(w[-1],observation_id="native:outside",literal="D13")
    result=_audit(b,w[:-1]+(duplicate,),s)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.competing_same_code_observation_ids==("native:outside",)
    assert not result.opening_count_granted


def test_rotated_original_schedule_row_is_a_vertical_strip():
    # Original A600 p28 is rotated 90 degrees. The two vertical
    # unrotated ink chains delimit one physical row, not a text column.
    b,w,s=_case(rotation=90)
    result=_audit(b,w,s)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.member_observation_ids==(
        "native:0","native:1","native:2","native:3")


@pytest.mark.parametrize("overpaint", [(1,1,1),(0,0,0)])
def test_later_opaque_overpaint_vetoes_historical_grid_paths(overpaint):
    b,w,s=_case(overpaint=overpaint)
    with pytest.raises(ValueError,match="overpainted"):
        _audit(b,w,s)


@pytest.mark.parametrize("pixel", [0, 255])
@pytest.mark.parametrize("rotation", [0, 90])
def test_later_raster_image_overpaint_vetoes_historical_grid(pixel, rotation):
    # get_drawings() retains six old strokes while get_bboxlog() sees
    # the later black/white raster. Darkness is not stroke provenance.
    b, w, s = _case(image_overpaint=pixel, rotation=rotation)
    with fitz.open(stream=b, filetype="pdf") as pdf:
        assert len(pdf[0].get_drawings()) == 6
        assert [entry[0] for entry in pdf[0].get_bboxlog()][-2:] == [
            "fill-image", "fill-image",
        ]
    with pytest.raises(ValueError, match="overpainted by later image"):
        _audit(b, w, s)


@pytest.mark.parametrize("rotation", [0, 90])
def test_raster_painted_behind_visible_grid_does_not_false_veto(rotation):
    b, w, s = _case(
        image_overpaint=0, image_overlay=False, rotation=rotation,
    )
    assert _audit(b, w, s).status is EvidenceResolutionStatus.CANDIDATE


@pytest.mark.parametrize("color", [(1,1,1), (0,0,0)])
def test_later_source_stroke_overpaint_vetoes_even_dark_final_pixels(color):
    b, w, s = _case(stroke_overpaint=color)
    with fitz.open(stream=b, filetype="pdf") as pdf:
        assert [kind for kind, _ in pdf[0].get_bboxlog()][-2:] == [
            "stroke-path", "stroke-path",
        ]
    with pytest.raises(ValueError, match="overpainted by later stroke"):
        _audit(b, w, s)


def test_later_unrelated_source_strokes_preserve_clean_grid():
    b, w, s = _case(stroke_overpaint=(1,1,1), stroke_shift=30.0)
    assert _audit(b, w, s).status is EvidenceResolutionStatus.CANDIDATE


def test_later_thin_transverse_grid_crossings_are_not_erasure():
    b, w, s = _case(stroke_overpaint=(0,0,0), stroke_horizontal=True)
    assert _audit(b, w, s).status is EvidenceResolutionStatus.CANDIDATE


def test_earlier_stroke_is_not_later_source_overpaint():
    b, w, s = _case(stroke_overpaint=(1,1,1), stroke_before=True)
    assert _audit(b, w, s).status is EvidenceResolutionStatus.CANDIDATE


def test_wrong_original_hash_cannot_use_source_ink():
    b,w,s=_case()
    with pytest.raises(ValueError,match="SHA"):
        inspect_original_native_grid_row_shadow(
            b,source_sha256="0"*64,words=w,scope=s)


@pytest.mark.parametrize("paths", [(0,1), (1,2), (0,0,2), (0,1,2,3)])
def test_partial_duplicate_or_foreign_boundary_sources_fail(paths):
    b,w,s=_case()
    with pytest.raises(ValueError):
        _audit(b,w,replace(s,left_boundary_paths=paths))


def test_wrong_page_and_code_address_fail_closed():
    b,w,s=_case()
    with pytest.raises(ValueError,match="page"):
        _audit(b,w,replace(s,page_number=2))
    with pytest.raises(ValueError,match="canonical"):
        _audit(b,w,replace(s,code_address=(1,0,0)))


def test_global_two_point_five_snap_is_not_grid_source_tolerance():
    with pytest.raises(ValueError,match="scope"):
        _audit(tolerance_pdf_pt=2.5)


def test_duplicate_native_word_addresses_are_rejected():
    b,w,s=_case()
    with pytest.raises(ValueError,match="duplicated"):
        _audit(b,w+(replace(w[2],observation_id="other"),),s)


def test_source_ink_and_word_universe_not_modified_by_shadow():
    b,w,s=_case()
    before=(b,w,s)
    first=_audit(b,w,s)
    second=_audit(b,w,s)
    assert first==second
    assert (b,w,s)==before


def _source_grid_with_later_native_text(*, color=(1, 1, 1),
                                        rotation=0, text="M", x=96):
    source, words, scope = _case(rotation=rotation)
    with fitz.open(stream=source, filetype="pdf") as pdf:
        # Draw AFTER the authenticated grid strokes. Text glyphs do not
        # appear in get_drawings(), and the final raster samples can miss
        # a narrow painted character between the 20/50/80% sample points.
        pdf[0].insert_text((x, 126), text, fontsize=10, color=color)
        changed = pdf.tobytes()
    return changed, words, scope


@pytest.mark.parametrize("color", ((1, 1, 1), (0, 0, 0)))
@pytest.mark.parametrize("rotation", (0, 90))
def test_later_native_text_glyph_over_grid_abstains_even_if_samples_stay_dark(
    color, rotation,
):
    source, words, scope = _source_grid_with_later_native_text(
        color=color, rotation=rotation,
    )
    with fitz.open(stream=source, filetype="pdf") as pdf:
        assert len(pdf[0].get_drawings()) == 6
        assert pdf[0].get_bboxlog()[-1][0] == "fill-text"
    with pytest.raises(ValueError, match="overpainted by later text glyph"):
        _audit(source, words, scope)


@pytest.mark.parametrize("rotation", (0, 90))
def test_later_native_text_outside_original_grid_keeps_source_candidate(rotation):
    source, words, scope = _source_grid_with_later_native_text(
        color=(1, 1, 1), rotation=rotation, x=310,
    )
    result = _audit(source, words, scope)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert not result.physical_door_identity_proven
    assert not result.opening_count_granted
    assert not result.firm_quantity_issued


def test_later_wide_text_span_whitespace_is_not_painted_grid_occlusion():
    # A single native texttrace bbox spans the grid at x=100, but the
    # source glyph at that x is a SPACE (advance only), not painted ink.
    # Rejecting the entire texttrace bbox would falsely veto real CAD tables.
    source, words, scope = _source_grid_with_later_native_text(
        text="M" + " " * 14 + "M", x=55,
    )
    with fitz.open(stream=source, filetype="pdf") as pdf:
        trace = pdf[0].get_texttrace()[-1]
        assert trace["bbox"][0] < 100 < trace["bbox"][2]
        assert any(
            chr(glyph[0]).isspace()
            and glyph[3][0] <= 100 <= glyph[3][2]
            for glyph in trace["chars"]
        )
    result = _audit(source, words, scope)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert not result.firm_quantity_issued


def test_private_original_d02_grid_membership_from_published_source_if_provisioned():
    """Original p28 source-positive gate, not a door count or synthetic pass.

    The paired printed grid is source evidence, not a prediction or an
    authority shortcut. All words must come from SourceVisibilityProducer.
    This intentionally FAILS on private replay if the pinned native parser,
    glyph trust, or exact source stroke correspondence changes.
    """
    import os
    from pathlib import Path

    from pb_gpt2_native_grid_row_membership_shadow import (
        audit_published_native_grid_row_shadow,
    )
    from pb_source_visibility_authority import SourceVisibilityProducer

    loc = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not loc:
        pytest.skip("SHA-authenticated private original not provisioned on public CI")
    original = Path(loc).read_bytes()
    original_sha = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    assert sha256(original).hexdigest() == original_sha

    # These eleven exact endpoints are an original p28 printed ruled-row
    # witness, independently inspected at source SHA above. Find unique native
    # path addresses afresh: get_drawings() indices may differ by MuPDF version.
    ends = (
        (1196.24, 1300.40), (1300.40, 1425.20), (1425.20, 1524.08),
        (1524.08, 1702.16), (1702.16, 1931.36), (1931.36, 1986.32),
        (1986.32, 2031.44), (2031.44, 2072.72), (2072.72, 2193.20),
        (2193.20, 2265.20), (2265.20, 2296.64),
    )
    with fitz.open(stream=original, filetype="pdf") as pdf:
        assert len(pdf) >= 28
        page = pdf[27]
        drawings = page.get_drawings()
        d02 = [w for w in page.get_text("words") if w[4] == "D02"]
        assert len(d02) == 1, "unique original D02 native word required"
        code_address = tuple(int(x) for x in d02[0][5:8])

        def exact_original_chain(x):
            indices = []
            for y0, y1 in ends:
                matching = []
                for index, drawing in enumerate(drawings):
                    items = drawing.get("items", ())
                    if drawing.get("type") != "s" or len(items) != 1:
                        continue
                    if items[0][0] != "l":
                        continue
                    a, b = items[0][1:3]
                    if (abs(a.x - x) <= .06 and abs(b.x - x) <= .06
                            and abs(min(a.y, b.y) - y0) <= .06
                            and abs(max(a.y, b.y) - y1) <= .06):
                        matching.append(index)
                assert len(matching) == 1, (
                    "original D02 grid source path absent or ambiguous"
                )
                indices.append(matching[0])
            return tuple(indices)

        scope = NativeGridRowScope(
            page_number=28,
            left_boundary_paths=exact_original_chain(1001.28),
            right_boundary_paths=exact_original_chain(1036.32),
            code_address=code_address,
        )

    producer = SourceVisibilityProducer(
        producer_method="gpt2-private-original-grid-row-review",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    publication = producer.ingest_native_pdf_bytes(
        document_id="maryborough-original-a600-grid",
        source_bytes=original,
        source_locator="memory://private-original.pdf",
        page_ids=("28",),
    )
    result = audit_published_native_grid_row_shadow(
        producer,
        revision_id=publication.revision.revision_id,
        page_id="28",
        original_pdf_bytes=original,
        scope=scope,
    )
    assert result.source_sha256 == original_sha
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.member_observation_ids) == 21
    assert not result.competing_same_code_observation_ids
    assert result.first_unclosed_gate == (
        "source_grid_membership_only_no_kind_host_count_or_dimensions"
    )
    assert result.shadow_only
    assert not any((
        result.source_dimension_authorized,
        result.physical_door_identity_proven,
        result.opening_count_granted,
        result.firm_quantity_issued,
        result.commercial_projection_allowed,
    ))
    assert sha256(Path(loc).read_bytes()).hexdigest() == original_sha


def _native_grid_inventory_case(*, touching=False):
    """Real native PDF words, not hand-authored producer receipt addresses."""
    pdf = fitz.open()
    page = pdf.new_page(width=420, height=340)
    for x in (100, 142):
        for lo, hi in ((30, 100), (100, 170), (170, 260)):
            page.draw_line(
                fitz.Point(x, lo), fitz.Point(x, hi),
                color=(0, 0, 0), width=.48,
            )
    for text, x, y in (
        ("D13", 106, 75), ("SWING", 106, 145),
        ("920", 106, 215), ("D14", 165, 75),
    ):
        page.insert_text(fitz.Point(x, y), text, fontsize=8)
    if touching:
        # This glyph intersects the original left boundary. Even though it
        # is not a fully contained member, losing it must fail closed.
        page.insert_text(fitz.Point(99, 250), "X", fontsize=8)
    original = pdf.tobytes()
    pdf.close()
    with fitz.open(stream=original, filetype="pdf") as opened:
        raw = opened[0].get_text("words")
    words = tuple(SourceDoorScheduleWord(
        observation_id=f"source:{i}",
        page_id="1", partition_id="page:1",
        block_no=int(word[5]), line_no=int(word[6]),
        word_no=int(word[7]), literal=str(word[4]).strip(),
        trusted=True, bbox_pdf_pts=tuple(float(v) for v in word[:4]),
    ) for i, word in enumerate(raw))
    code = next(w for w in words if w.literal == "D13")
    scope = NativeGridRowScope(
        page_number=1, left_boundary_paths=(0, 1, 2),
        right_boundary_paths=(3, 4, 5),
        code_address=(code.block_no, code.line_no, code.word_no),
    )
    return original, words, scope


def _check_native_inventory(original, words, scope):
    from pb_gpt2_native_grid_row_membership_shadow import (
        _assert_original_grid_word_inventory,
    )
    with fitz.open(stream=original, filetype="pdf") as pdf:
        _assert_original_grid_word_inventory(pdf[0], scope, words)


def test_original_grid_inventory_parity_preserves_native_words_and_outside_notes():
    original, words, scope = _native_grid_inventory_case()
    _check_native_inventory(original, words, scope)
    outside = next(w for w in words if w.literal == "D14")
    _check_native_inventory(
        original,
        tuple(replace(w, literal="FOREIGN") if w is outside else w
              for w in words),
        scope,
    )
    assert sha256(original).hexdigest() == sha256(bytes(original)).hexdigest()


@pytest.mark.parametrize("failure", ["missing", "literal", "geometry", "duplicate"])
def test_original_grid_inventory_parity_rejects_missing_published_native_word(failure):
    original, words, scope = _native_grid_inventory_case()
    selected = next(w for w in words if w.literal == "920")
    if failure == "missing":
        modified = tuple(w for w in words if w is not selected)
    elif failure == "literal":
        modified = tuple(replace(w, literal="921") if w is selected else w
                         for w in words)
    elif failure == "geometry":
        modified = tuple(replace(w, bbox_pdf_pts=(
            w.bbox_pdf_pts[0] + .2, *w.bbox_pdf_pts[1:],
        )) if w is selected else w for w in words)
    else:
        modified = words + (replace(selected, observation_id="duplicate"),)
    with pytest.raises(ValueError, match="inventory|duplicate"):
        _check_native_inventory(original, modified, scope)


def test_original_grid_inventory_parity_rejects_missing_touching_glyph():
    original, words, scope = _native_grid_inventory_case(touching=True)
    _check_native_inventory(original, words, scope)
    assert any(w.literal == "X" for w in words)
    with pytest.raises(ValueError, match="inventory differs"):
        _check_native_inventory(
            original, tuple(w for w in words if w.literal != "X"), scope)


def test_producer_grid_audit_vetoes_original_native_word_omission(monkeypatch):
    import pb_gpt2_native_grid_row_membership_shadow as grid
    from pb_source_visibility_authority import SourceVisibilityProducer

    original, _, scope = _native_grid_inventory_case()
    producer = SourceVisibilityProducer(
        producer_method="gpt2-native-grid-parity-test",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="native-grid-parity",
        source_bytes=original,
        source_locator="memory://native-grid-parity.pdf",
        page_ids=("1",),
    )
    actual = grid._producer_owned_native_words(
        producer, published, "1")
    assert any(w.literal == "920" for w in actual)
    omitted = tuple(w for w in actual if w.literal != "920")
    monkeypatch.setattr(
        grid, "_producer_owned_native_words",
        lambda *args, **kwargs: omitted,
    )
    with pytest.raises(ValueError, match="inventory differs"):
        grid.audit_published_native_grid_row_shadow(
            producer,
            revision_id=published.revision.revision_id,
            page_id="1", original_pdf_bytes=original, scope=scope,
        )
    assert sha256(original).hexdigest() == published.revision.source_sha256


@pytest.mark.parametrize("invalid_address", [
    None, 0, "0,0,0", [0, 0, 0], (0, 0), (0, 0, 0, 0),
    (0, 0, True), (0, 0, -1), (0, 0, 0.0),
])
def test_native_code_address_requires_immutable_literal_integer_triplet(invalid_address):
    # Source-owned native word identity must not accept coercions, mutable
    # addresses or a malformed scalar that raises before typed abstention.
    original, words, scope = _case()
    assert _audit(original, words, scope).status is EvidenceResolutionStatus.CANDIDATE
    with pytest.raises(ValueError, match="exact native code word address required"):
        _audit(original, words, replace(scope, code_address=invalid_address))
    assert original == bytes(original)
    assert words == _case()[1]
    assert scope.code_address == (0, 0, 0)
