"""Title-bearing original source frame rules are non-walls only with full proof."""
from copy import deepcopy
from pb_source_sheet_frame_roles_shadow import source_sheet_frame_nonwall_path_ids as detect


def line(a,b, *, layer="", width=0.7, fill=None):
    return {
        "layer": layer, "fill": fill, "color": (0,0,0), "width": width,
        "type": "s", "items": [("l", a,b)],
    }


def source():
    rows = [
        line((10,10),(190,10)), line((10,10),(10,160)),
        line((190,10),(190,160)), line((10,160),(190,160)),
        line((10,180),(190,180)), line((85,160),(85,180)),
    ]
    words=[
        (90,165,115,171,"Drawing",0,0,0),
        (115,165,136,171,"REVISION",0,0,0),
        (142,165,164,171,"Scale:",0,0,0),
    ]
    return rows, words


def test_sheet_frame_is_original_native_four_wallless_lines_and_title_grid():
    rows, words = source()
    result=detect(rows, words)
    assert result == frozenset(range(6))


def test_sheet_frame_refuses_missing_corner_title_foreign_wall_or_ambiguous_frame():
    rows, words=source()
    assert not detect(rows, words[:2])
    incomplete=deepcopy(rows)
    incomplete[2] = line((190,10),(190,159.8))
    assert not detect(incomplete, words)
    wrong_layer=deepcopy(rows)
    wrong_layer[1]["layer"]="Enclosure_WallExternal"
    assert not detect(wrong_layer, words)
    painted=deepcopy(rows)
    painted[1]["fill"]=(0,0,0)
    assert not detect(painted, words)
    duplicate=deepcopy(rows)
    duplicate.append(deepcopy(duplicate[0]))
    assert not detect(duplicate,words)
    duplicate_vertical=deepcopy(rows)
    duplicate_vertical.append(deepcopy(duplicate_vertical[1]))
    assert not detect(duplicate_vertical,words)


def test_nonwall_requires_footer_text_and_relative_page_coverage():
    rows,words=source()
    unrelated=deepcopy(rows)
    unrelated.append(line((500,0),(1000,0)))
    assert not detect(unrelated,words)
    outside_words=[(190,165,215,171,word[4],0,0,0) for word in words]
    assert not detect(rows,outside_words)



def test_original_3laurel_p3_source_owned_title_frame_without_viewport():
    """Held-out original: source-only sheet ink, never building wall authority."""
    import hashlib

    import fitz

    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel

    source = require_original_3laurel()
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=raw, filetype="pdf") as doc:
        page = doc[2]
        drawings = page.get_drawings()
        words = page.get_text("words")
        assert len(drawings) == 11030
        assert len(words) >= 1200
        # Four full-page source rule segments (26-29) and their exact
        # original title-grid drawing items (2-25,30-40), not walls.
        ids = detect(drawings, words)
        assert ids == frozenset(range(2, 41))
        assert {26, 27, 28, 29} <= ids
        assert all(
            drawings[idx].get("fill") is None and
            not str(drawings[idx].get("layer") or "").strip()
            for idx in ids
        )
        assert all(
            not drawings[idx].get("source_viewport_id")
            and not drawings[idx].get("viewport_id")
            for idx in ids
        )
        # This detector must not fabricate closure or emit quantities.
        assert len(page.get_drawings()) == len(drawings)
