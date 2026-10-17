"""Exact PWD-style source dimension terminal extension evidence only."""
from dataclasses import replace
from pb_gpt1_original_figured_face_witness_shadow import (
    SourceFiguredAxis,SourceStructuralFaceStroke,
)
from pb_gpt1_original_figured_extension_to_face_shadow import (
    OriginalFigureTerminalExtension,resolve_original_figure_extension_faces_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status


SHA="a"*64

def _axis():
    return SourceFiguredAxis(
        "original-figured-length",3570,"vertical",
        (157.68,1774.64),(157.68,2179.52),("original-tick-1","original-tick-2"),
        "26",source_sha256=SHA,revision_id="rev",
    )


def _ext():
    return (
        OriginalFigureTerminalExtension(
            "original-source-extension-top",0,
            (157.68,1774.64),(217.44,1774.64),SHA,"rev","26",
        ),
        OriginalFigureTerminalExtension(
            "original-source-extension-bottom",1,
            (157.68,2179.52),(217.44,2179.52),SHA,"rev","26",
        ),
    )


def _walls():
    return (
        SourceStructuralFaceStroke(
            "wall-top",(217.44,1774.64),(346.56,1774.64),
            "physical-wall-one","finished_inner_face","stroke",
            source_sha256=SHA,revision_id="rev",page_id="26",
        ),
        SourceStructuralFaceStroke(
            "wall-bottom",(217.44,2179.52),(346.56,2179.52),
            "physical-wall-two","finished_inner_face","stroke",
            source_sha256=SHA,revision_id="rev",page_id="26",
        ),
    )


def test_independent_original_extensions_reach_both_proven_finished_faces():
    result=resolve_original_figure_extension_faces_shadow(_axis(),_ext(),_walls())
    assert result.status is Status.CANDIDATE
    assert result.bound_finished_face_stroke_ids==("wall-top","wall-bottom")
    assert result.diagnostic_only


def test_source_top_extension_ending_before_wall_fails_no_gap_imputation():
    original=list(_ext())
    original[0]=replace(original[0],end_pdf_pt=(168.96,1774.64))
    result=resolve_original_figure_extension_faces_shadow(
        _axis(),tuple(original),_walls()
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("original_figured_extension_competing_finished_faces",)


def test_figure_bound_to_original_outer_face_cannot_prove_inner_net_area():
    wall=list(_walls())
    wall[0]=replace(wall[0],physical_face_role="structural_outer_face")
    result=resolve_original_figure_extension_faces_shadow(
        _axis(),_ext(),tuple(wall)
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("original_figured_extension_finished_face_unproved",)


def test_same_original_face_competing_wall_ids_cannot_select_nearest():
    wall=_walls()+(replace(_walls()[0],original_stroke_id="competing-face",
                            classified_physical_wall_id="other-wall"),)
    result=resolve_original_figure_extension_faces_shadow(_axis(),_ext(),wall)
    assert result.status is Status.ABSTAINED
    assert "wall-top" in result.competing_face_stroke_ids_by_terminal[0]


def test_foreign_original_figure_source_revision_cannot_reuse_witness():
    ext=list(_ext());ext[0]=replace(ext[0],revision_id="stale")
    out=resolve_original_figure_extension_faces_shadow(
        _axis(),tuple(ext),_walls()
    )
    assert out.status is Status.ABSTAINED
