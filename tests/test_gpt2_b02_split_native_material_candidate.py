"""B02 two-line native schedule candidates remain strictly source-gated."""
from types import SimpleNamespace
from pb_source_material_semantic_authority import _material_definition_candidate


def _words(*lines):
    return tuple(SimpleNamespace(
        line_no=i, word_no=0, text=text,
        bbox=(0.0, float(i)*20, 200.0, float(i)*20+10),
        observation_id=f"source:{i}", page_id="9",
    ) for i, text in enumerate(lines))


def test_split_native_alpha_material_row_is_candidate():
    result = _material_definition_candidate(_words("FPB", "FLUSHSET PLASTERBOARD"))
    assert result is not None
    assert result[0] == "FPB"
    assert "PLASTERBOARD" in result[1]["description"]


def test_bare_code_no_material_definition():
    assert _material_definition_candidate(_words("FPB")) is None


def test_multiline_native_specification_is_candidate_only():
    # A source schedule may legitimately contain separate code, role and
    # specification cells. Parsing a candidate does not authenticate its
    # source words or schedule ownership.
    candidate = _material_definition_candidate(_words(
        "IPF1", "CONTRACTOR", "13mm FLUSH-SET PLASTERBOARD CEILING LININGS"
    ))
    assert candidate is not None
    assert candidate[0] == "IPF1"
    assert "13mm" in candidate[1]["description"]
    assert "PLASTERBOARD" in candidate[1]["description"]
