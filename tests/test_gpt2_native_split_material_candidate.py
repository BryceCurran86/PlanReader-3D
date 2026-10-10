"""Split native material text is a parser candidate, never independent authority."""
from types import SimpleNamespace

from pb_source_material_semantic_authority import _material_definition_candidate


def _words(*lines: str):
    return tuple(
        SimpleNamespace(
            line_no=index,
            word_no=0,
            text=value,
            bbox=(0.0, index * 20.0, 160.0, index * 20.0 + 10.0),
            observation_id=f"native-text:{index}",
            page_id="9",
        )
        for index, value in enumerate(lines)
    )


def test_two_line_same_native_block_can_propose_material_candidate():
    result = _material_definition_candidate(
        _words("FPB", "FLUSHSET PLASTERBOARD")
    )
    assert result is not None
    assert result[0] == "FPB"
    assert result[1]["description"] == "FLUSHSET PLASTERBOARD"


def test_bare_code_is_not_material_definition():
    assert _material_definition_candidate(_words("FPB")) is None


def test_two_line_row_without_semantic_material_description_abstains():
    # One material-bearing word can be a parser candidate; absence of a
    # meaningful material description must not be promoted even to candidate.
    assert _material_definition_candidate(_words("FPB", "REFERENCE")) is None


def test_invalid_code_grammar_and_generic_nonmaterial_stay_blocked():
    assert _material_definition_candidate(_words("LONGCODE", "FLUSHSET PLASTERBOARD")) is None
    assert _material_definition_candidate(_words("Grid", "FLUSHSET PLASTERBOARD")) is None
    assert _material_definition_candidate(_words("GRID", "SET OUT PLAN")) is None


def test_source_native_multiline_specification_requires_semantic_parser():
    result = _material_definition_candidate(
        _words("IPF1", "CONTRACTOR", "13mm FLUSH-SET PLASTERBOARD CEILING LININGS")
    )
    assert result is not None
    assert result[0] == "IPF1"
    assert "PLASTERBOARD" in result[1]["description"]
