"""Original printed figure/two ticks/two cap lines: source-only, never FIRM."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import os
import fitz
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_original_figured_tick_wall_cap_shadow import (
    OriginalFiguredTickScope,audit_original_figured_cap_chain_shadow,
)


def _source(*,figure="1000",wrong_cap=False,far_figure=False):
    pdf=fitz.open()
    page=pdf.new_page(width=650,height=500)
    def line(a,b,width):
        sh=page.new_shape()
        sh.draw_line(fitz.Point(*a),fitz.Point(*b))
        sh.finish(color=(0,0,0),width=width)
        sh.commit()
    line((230,130),(320,130),.48)
    line((240,130),(243,127),.96)
    line((240,130),(237,133),.96)
    line((300,130),(303,127),.96)
    line((300,130),(297,133),.96)
    line((240,130),(240,120),.48)
    line((240,130),(240,140),.48)
    line((300,130),(300,120),.48)
    line((300,130),(300,140),.48)
    line((240,146),(240,156),.48)
    line((310 if wrong_cap else 300,146),(310 if wrong_cap else 300,156),.48)
    page.insert_text((244 if figure=="70" else 257,
                      341 if far_figure else 141),figure,fontsize=12)
    data=pdf.tobytes();pdf.close();return data


def _scope(page=1,word=(0,0,0)):
    return OriginalFiguredTickScope(
        page,word,0,((1,2),(3,4)),((5,6),(7,8)),(9,10))


def _run(data=None,scope=None,source_sha=None):
    data=data or _source()
    return audit_original_figured_cap_chain_shadow(
        data,expected_sha256=source_sha or sha256(data).hexdigest(),
        scope=scope or _scope(),
    )


def test_original_figured_source_positive_never_grants_physical_door():
    out=_run()
    assert out.status is EvidenceResolutionStatus.CANDIDATE
    assert out.source_declared_figure_mm==1000.
    assert out.source_tick_x_pdf_pt==pytest.approx((240.,300.),abs=.0001)
    assert out.source_cap_x_pdf_pt==pytest.approx((240.,300.),abs=.0001)
    assert not any((out.physical_wall_owned,out.physical_door_owned,
                    out.doorway_threshold_owned,out.metric_measurement_owned,
                    out.floor_or_ceiling_finish_owned,out.signed_quantity_issued,
                    out.commercial_projection_allowed))


def test_nearby_separate_short_figure_cannot_take_two_tick_owner():
    out=_run(_source(figure="70"))
    assert out.status is EvidenceResolutionStatus.ABSTAINED
    assert out.source_declared_figure_mm is None


def test_displaced_wall_cap_rejects_figured_span_correspondence():
    with pytest.raises(ValueError,match="unrelated"):
        _run(_source(wrong_cap=True))


def test_duplicated_native_stroke_not_independent_source():
    with pytest.raises(ValueError,match="distinct"):
        _run(scope=replace(_scope(),wall_cap_paths=(9,9)))


def test_unbound_original_sha_and_page_rejected():
    with pytest.raises(ValueError,match="SHA"):
        _run(source_sha="0"*64)
    with pytest.raises(ValueError,match="page"):
        _run(scope=_scope(page=2))


def test_original_source_immutable_and_replay_deterministic():
    raw=_source()
    before=sha256(raw).hexdigest()
    assert _run(raw)==_run(raw)
    assert before==sha256(raw).hexdigest()


def test_real_maryborough_original_1000_tick_chain_when_provisioned():
    loc=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not loc:
        pytest.skip("source original unavailable")
    original=Path(loc).read_bytes()
    result=audit_original_figured_cap_chain_shadow(
        original,expected_sha256=os.environ["PLANREADER_MARYBOROUGH_SOURCE_SHA256"],
        scope=OriginalFiguredTickScope(
            11,(62,0,0),25698,
            ((25699,25700),(25703,25704)),
            ((25701,25702),(25705,25706)),(2843,2850),
        ),
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.source_declared_figure_mm==1000.
    assert result.source_tick_x_pdf_pt==pytest.approx((254.88,311.76),abs=.0001)
    assert result.source_cap_x_pdf_pt==pytest.approx((254.88,311.76),abs=.0001)
    assert not result.signed_quantity_issued


def test_original_competing_70_source_word_cannot_be_d15_1000_when_provisioned():
    loc=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not loc:
        pytest.skip("source original unavailable")
    original=Path(loc).read_bytes()
    result=audit_original_figured_cap_chain_shadow(
        original,expected_sha256=os.environ["PLANREADER_MARYBOROUGH_SOURCE_SHA256"],
        scope=OriginalFiguredTickScope(
            11,(62,0,1),25698,
            ((25699,25700),(25703,25704)),
            ((25701,25702),(25705,25706)),(2843,2850),
        ),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.source_declared_figure_mm is None


def test_unrelated_1000_text_same_x_but_far_from_source_ticks_abstains():
    # The exact same number, correct native address and horizontal centre
    # cannot borrow unrelated source dimension tick and wall-cap owners.
    r=_run(_source(far_figure=True))
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.source_declared_figure_mm is None
    assert not r.metric_measurement_owned
    assert not r.physical_door_owned
    assert not r.signed_quantity_issued
    assert not r.commercial_projection_allowed
