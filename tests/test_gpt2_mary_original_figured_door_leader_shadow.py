"""Original source figure/leader ink tests. Never accepts numeric dimension as FIRM."""
from hashlib import sha256
from pathlib import Path
import os
import fitz
import pytest
from pb_gpt2_mary_original_figured_door_leader_shadow import (
    OriginalDoorLeaderScope, inspect_original_door_figure_leader_shadow,
)


def _fixture(*,missing_tick=False, wrong_figure=False, shifted_cap=False,
             far_figure=False, invisible_baseline=False, dashed_tick=False,
             translucent_cap=False, invisible_figure=False,
             white_figure=False, later_overpaint=False, partial_overpaint=False):
    pdf=fitz.open();page=pdf.new_page(width=700,height=700)
    def line(p,q,*,opacity=1.0,dashes=None):
        d=page.new_shape();d.draw_line(fitz.Point(*p),fitz.Point(*q))
        d.finish(color=(0,0,0),width=.48,stroke_opacity=opacity,dashes=dashes)
        d.commit()
    line((100,150),(230,150),opacity=0.0 if invisible_baseline else 1.0)
    line((100,170),(100,178),opacity=0.5 if translucent_cap else 1.0)
    line((200+(2 if shifted_cap else 0),170),(200+(2 if shifted_cap else 0),178))
    for x in (100,200):
        line((x,150),(x+3,147),
             dashes="[2 2] 0" if dashed_tick and x==100 else None)
        line((x,150),(x-3,153))
        line((x,150),(x,138))
        line((x,150),(x,160))
    page.insert_text((350,350) if far_figure else (145,160),
                     '70' if wrong_figure else '1000',fontsize=11,
                     render_mode=3 if invisible_figure else 0,
                     color=(1,1,1) if white_figure else (0,0,0))
    if later_overpaint:
        page.draw_rect(fitz.Rect(144,147,171,165), color=None, fill=(1,1,1))
    if partial_overpaint:
        page.draw_rect(fitz.Rect(153,152,159,159), color=None, fill=(1,1,1))
    data=pdf.tobytes();pdf.close()
    return data,OriginalDoorLeaderScope(1,0,0,0,0,(1,2),(3,4,5,6),(7,8,9,10))


def _run(b=None,scope=None,**kwargs):
    if b is None:b,scope=_fixture()
    return inspect_original_door_figure_leader_shadow(
        b,source_sha256=sha256(b).hexdigest(),scope=scope,
        expected_cap_x_pdf_pt=(100.,200.),**kwargs)


def test_source_figure_leader_positive_does_not_grant_physical_door_or_width():
    r=_run()
    assert r.status=='SOURCE_FIGURE_LEADER_CANDIDATE'
    assert r.original_figured_text=='1000'
    assert r.original_gap_span_pdf_pt==100.
    assert r.shadow_only and not any((r.original_w4_wall_issued,
        r.actual_door_identity_proven,r.opening_jamb_identity_granted,
        r.physical_doorway_threshold_issued,r.figure_width_mm_authorized_for_physical_opening,
        r.floor_finish_area_issued,r.customer_projection_allowed))


def test_competing_short_70_word_never_becomes_1000_door_figure():
    b,scope=_fixture(wrong_figure=True)
    with pytest.raises(ValueError,match='figured dimension'):_run(b,scope)


def test_foreign_cap_does_not_match_figure_leader():
    b,scope=_fixture(shifted_cap=True)
    with pytest.raises(ValueError,match='cap'):_run(b,scope)


def test_spliced_tick_from_other_original_source_cannot_be_accepted():
    b,scope=_fixture()
    from dataclasses import replace
    with pytest.raises(ValueError,match='distinct'):
        _run(b,replace(scope,left_tick_paths=(3,4,5,7)))


def test_wrong_original_source_digest_rejected():
    b,scope=_fixture()
    with pytest.raises(ValueError,match='SHA'):
        inspect_original_door_figure_leader_shadow(b,source_sha256='0'*64,
            scope=scope,expected_cap_x_pdf_pt=(100.,200.))


def test_figure_cannot_use_global_wall_snap_tolerance():
    with pytest.raises(ValueError,match='tolerance'):
        _run(tolerance_pdf_pt=2.5)


def test_wrong_original_page_address_rejected():
    b,scope=_fixture()
    from dataclasses import replace
    with pytest.raises(ValueError,match='page'):
        _run(b,replace(scope,page_number=2))


def test_private_original_maryborough_native_leader_source_if_provisioned():
    loc=os.environ.get('PLANREADER_MARYBOROUGH_ORIGINAL_PDF')
    if not loc:pytest.skip('original private PDF not provided to test runner')
    b=Path(loc).read_bytes()
    # Native block ordinals change between MuPDF extractors (61 vs 62).
    # Locate the one source-visible figured glyph by original text AND its
    # exact PDF glyph geometry, not by an assumed 1.26/1.28 block ordinal.
    # This is private original-source test selection, not production authority.
    with fitz.open(stream=b,filetype='pdf') as pdf:
        figures=[
            w for w in pdf[10].get_text('words')
            if w[4]=='1000'
            and all(abs(float(w[i])-target)<0.25 for i,target in
                    enumerate((274.25,1359.99,292.80,1373.71)))
        ]
    assert len(figures)==1, 'original figured glyph not uniquely located'
    block,line,word=map(int,figures[0][5:8])
    r=inspect_original_door_figure_leader_shadow(
        b,source_sha256=os.environ['PLANREADER_MARYBOROUGH_SOURCE_SHA256'],
        scope=OriginalDoorLeaderScope(11,block,line,word,25698,(2843,2850),
            (25699,25700,25701,25702),(25703,25704,25705,25706)),
        expected_cap_x_pdf_pt=(254.87999,311.75998))
    assert r.status=='SOURCE_FIGURE_LEADER_CANDIDATE'
    assert r.original_gap_span_pdf_pt==pytest.approx(56.87999,abs=.001)
    assert r.original_figured_text=='1000' and r.rival_same_line_word_texts==('70',)
    assert not r.figure_width_mm_authorized_for_physical_opening


def test_same_printed_1000_elsewhere_on_original_page_cannot_own_leader():
    """Authentic text source address alone does not prove dimension ownership."""
    original, scope = _fixture(far_figure=True)
    with pytest.raises(ValueError, match="glyph does not belong"):
        _run(original, scope)


@pytest.mark.parametrize("source_style", [
    {"invisible_baseline": True},
    {"dashed_tick": True},
    {"translucent_cap": True},
])
def test_invisible_dashed_or_partial_original_dimension_ink_cannot_prove_leader(source_style):
    source,scope=_fixture(**source_style)
    with pytest.raises(ValueError, match="not visible solid ink"):
        _run(source,scope)


@pytest.mark.parametrize("foreign_rgb", (
    (-0.1,0.0,0.0),
    (float("nan"),0.0,0.0),
    (0.0,float("inf"),0.0),
    (0.0,0.0,float("-inf")),
    (0.0,0.0,0.25),
))
def test_original_native_dimension_paint_must_have_finite_black_channels(foreign_rgb):
    from pb_gpt2_mary_original_figured_door_leader_shadow import _native_line
    native={"items":[("l",fitz.Point(20,30),fitz.Point(40,30))],
            "color":foreign_rgb,"fill":None,"stroke_opacity":1.0,
            "dashes":"[] 0","width":0.48}
    with pytest.raises(ValueError, match="black source line"):
        _native_line(None,[native],0)
    actual=dict(native,color=(0.0,0.0,0.0))
    assert _native_line(None,[actual],0)==(20.0,30.0,40.0,30.0,0.48)


@pytest.mark.parametrize("source_style", [
    {"invisible_figure": True},
    {"white_figure": True},
    {"later_overpaint": True},
    {"partial_overpaint": True},
])
def test_invisible_or_occluded_original_figure_cannot_be_source_authenticated(source_style):
    source, scope = _fixture(**source_style)
    with pytest.raises(ValueError, match="figured text"):
        _run(source, scope)


def test_source_figure_native_word_and_trace_may_share_span_with_foreign_70():
    """Private original p11 uses one texttrace for 1000 and the distinct 70.

    The SHA-gated original test above exercises the exact real word; this
    source-neutral regression preserves the subspan requirement without
    relying on source-private PDF bytes in public CI.
    """
    source, scope = _fixture()
    with fitz.open(stream=source, filetype='pdf') as pdf:
        assert any(t['type'] == 0 and t['opacity'] == 1 for t in pdf[0].get_texttrace())
    assert _run(source, scope).status == 'SOURCE_FIGURE_LEADER_CANDIDATE'


def test_unrelated_trace_sharing_paint_sequence_does_not_erase_selected_source(monkeypatch):
    from dataclasses import replace
    import pb_gpt2_mary_original_figured_door_leader_shadow as module
    original=module.extract_native_text_render_evidence
    def additional(page):
        records=original(page)
        assert records
        unrelated=replace(records[0],bbox=(800.,800.,820.,820.),raw_text='UNRELATED',
                          render_state='PROVEN_NON_RENDERING',render_eligible=False)
        return records+(unrelated,)
    monkeypatch.setattr(module,'extract_native_text_render_evidence',additional)
    source,scope=_fixture()
    assert _run(source,scope).status == 'SOURCE_FIGURE_LEADER_CANDIDATE'


@pytest.mark.parametrize('reverse',(False,True))
def test_duplicate_selected_render_trace_is_never_first_or_last_wins(monkeypatch,reverse):
    import pb_gpt2_mary_original_figured_door_leader_shadow as module
    original=module.extract_native_text_render_evidence
    def duplicated(page):
        records=original(page)
        duplicate=records+records
        return tuple(reversed(duplicate)) if reverse else duplicate
    monkeypatch.setattr(module,'extract_native_text_render_evidence',duplicated)
    source,scope=_fixture()
    with pytest.raises(ValueError,match='selected native render trace ambiguous'):
        _run(source,scope)


# A separate original-p7/p11 wall-cap check is a physical-identity veto only.
# It is not a dimension leader, threshold, floor finish, count, or FIRM quantity.
def _two_sheet_caps(*, left_error=0.0, target_width=.48, dashed=False):
    doc = fitz.open()
    for page_index, dx in ((0, 0.0), (1, 78.0)):
        pg = doc.new_page(width=500, height=500)
        for index, x in enumerate((100.0, 160.0)):
            x += dx + (left_error if page_index and index == 0 else 0)
            drawing = pg.new_shape()
            drawing.draw_line(fitz.Point(x, 100), fitz.Point(x, 107))
            drawing.finish(
                color=(0, 0, 0),
                width=(target_width if page_index else .48),
                dashes="[2 2] 0" if dashed and page_index else None,
            )
            drawing.commit()
    blob = doc.tobytes()
    doc.close()
    return blob


def _crosssheet_caps(blob, *, hypotheses=((78., 0.), (43.92, 0.)), **kwargs):
    from pb_gpt2_mary_original_figured_door_leader_shadow import (
        audit_original_crosssheet_door_caps_shadow,
    )
    return audit_original_crosssheet_door_caps_shadow(
        blob, source_sha256=sha256(blob).hexdigest(),
        floor_page=1, finish_page=2,
        cap_path_pairs=((0, 0), (1, 1)),
        translation_hypotheses=hypotheses, **kwargs,
    )


def test_source_equal_caps_are_diagnostic_only_and_preserve_rival_shift():
    receipt = _crosssheet_caps(_two_sheet_caps())
    assert receipt["status"] == "SOURCE_CAP_PAIR_CANDIDATE"
    assert receipt["matches"][0]["translation_pdf_pt"] == (78.0, 0.0)
    assert len(receipt["all_tested_hypotheses"]) == 2
    assert receipt["unexamined_transforms_remain"] is True
    assert not receipt["physical_opening_authority"]
    assert not receipt["doorway_threshold_issued"]
    assert not receipt["floor_finish_area_issued"]
    assert not receipt["firm_quantity_issued"]


def test_subpoint_original_cap_conflict_abstains_not_global_snap():
    receipt = _crosssheet_caps(_two_sheet_caps(left_error=.24))
    assert receipt["status"] == "ABSTAINED"
    assert receipt["matches"] == ()
    assert receipt["all_tested_hypotheses"][0]["max_cap_residual_pdf_pt"] > .23


def test_second_equally_valid_translation_retained_not_tiebroken():
    receipt = _crosssheet_caps(
        _two_sheet_caps(), hypotheses=((78., 0.), (78.03, 0.))
    )
    assert receipt["status"] == "ABSTAINED"
    assert len(receipt["matches"]) == 2


def test_original_cap_width_or_ink_conflict_fails_closed():
    receipt = _crosssheet_caps(_two_sheet_caps(target_width=.96))
    assert receipt["status"] == "ABSTAINED"
    with pytest.raises(ValueError, match="solid"):
        _crosssheet_caps(_two_sheet_caps(dashed=True))


def test_reused_original_cap_address_foreign_sha_and_global_snap_rejected():
    from pb_gpt2_mary_original_figured_door_leader_shadow import (
        audit_original_crosssheet_door_caps_shadow as audit,
    )
    blob = _two_sheet_caps()
    parameters = dict(source_sha256=sha256(blob).hexdigest(),
                      floor_page=1, finish_page=2,
                      cap_path_pairs=((0, 0), (1, 1)),
                      translation_hypotheses=((78., 0.),))
    with pytest.raises(ValueError, match="SHA"):
        audit(blob, **{**parameters, "source_sha256": "0" * 64})
    with pytest.raises(ValueError, match="distinct"):
        audit(blob, **{**parameters, "cap_path_pairs": ((0, 0), (0, 1))})
    with pytest.raises(ValueError, match="tolerance"):
        audit(blob, **parameters, tolerance_pdf_pt=2.5)
    assert sha256(blob).hexdigest() == parameters["source_sha256"]


def test_original_cap_receipt_is_order_invariant_and_never_mutates_source():
    from pb_gpt2_mary_original_figured_door_leader_shadow import (
        audit_original_crosssheet_door_caps_shadow as audit,
    )
    source = _two_sheet_caps()
    data = dict(source_sha256=sha256(source).hexdigest(),
                floor_page=1, finish_page=2,
                translation_hypotheses=((78., 0.), (43.92, 0.)))
    first = audit(source, cap_path_pairs=((0, 0), (1, 1)), **data)
    second = audit(source, cap_path_pairs=((1, 1), (0, 0)), **data)
    assert first["all_tested_hypotheses"] == second["all_tested_hypotheses"]
    assert sha256(source).hexdigest() == data["source_sha256"]


@pytest.mark.parametrize("mutation", (
    "same_letters_wrong_order",
    "same_letters_wrong_positions",
    "reversed_native_direction",
    "nonunit_native_direction",
))
def test_figured_word_cannot_be_authenticated_by_an_unordered_glyph_bag(
    monkeypatch, mutation,
):
    """The extracted native word still says 1000; altered source ink must veto."""
    original, scope = _fixture()
    digest = sha256(original).hexdigest()
    get_texttrace = fitz.Page.get_texttrace
    witnessed = []

    def altered_trace(page):
        traces = list(get_texttrace(page))
        for idx, trace in enumerate(traces):
            chars = list(trace.get("chars") or ())
            if "".join(chr(char[0]) for char in chars) != "1000":
                continue
            witnessed.append(idx)
            if mutation == "same_letters_wrong_order":
                chars[0], chars[1] = chars[1], chars[0]
            elif mutation == "same_letters_wrong_positions":
                first, second = chars[0], chars[1]
                chars[0] = (first[0], first[1], second[2], second[3])
                chars[1] = (second[0], second[1], first[2], first[3])
            else:
                # A valid trace's direction must match the actual spatial
                # progression; a reversed/zero vector cannot prove the word.
                trace = {
                    **trace,
                    "dir": (-1.0, 0.0)
                    if mutation == "reversed_native_direction"
                    else (0.0, 0.0),
                }
            traces[idx] = {**trace, "chars": tuple(chars)}
        return traces

    monkeypatch.setattr(fitz.Page, "get_texttrace", altered_trace)
    with pytest.raises(ValueError, match="figured text.*(order|direction|positions)"):
        _run(original, scope)
    assert witnessed
    assert sha256(original).hexdigest() == digest


def test_genuine_horizontal_figured_word_remains_source_only_not_a_door():
    source, scope = _fixture()
    result = _run(source, scope)
    assert result.status == "SOURCE_FIGURE_LEADER_CANDIDATE"
    assert result.original_figured_text == "1000"
    assert result.shadow_only
    assert not any((
        result.actual_door_identity_proven,
        result.original_w4_wall_issued,
        result.opening_jamb_identity_granted,
        result.physical_doorway_threshold_issued,
        result.figure_width_mm_authorized_for_physical_opening,
        result.floor_finish_area_issued,
        result.customer_projection_allowed,
    ))
