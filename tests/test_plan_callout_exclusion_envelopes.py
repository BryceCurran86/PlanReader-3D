"""Generated-source opposition only. No physical, metric or count promotion."""

from dataclasses import replace
import math

import fitz
import pytest

import pb_source_plan_glazing_strip_callout_shadow as shadow
from plan_callout_strip_fixture import (
    ABST,
    CAND,
    CONF,
    GAP,
    HEX_H,
    Sheet,
    add_window,
    by_mark,
    ink_of,
    run,
    scope_for,
    three_windows,
    types_of,
    words_of,
)
from test_plan_callout_glazing_strip_shadow_producer import (
    ELEVATION_MM_PER_PT,
    SPECS,
    _audit,
    _draw_elevation,
    _plan_sheet,
    _publish,
    _resolved_viewport,
)


def polygon(sheet, centre, sides, radius=12.0, *, mark="D99", drop_edge=None):
    cx, cy = centre
    pts = [
        (
            cx + radius * math.cos(i * math.tau / sides),
            cy + radius * math.sin(i * math.tau / sides),
        )
        for i in range(sides)
    ]
    for i in range(sides):
        if i != drop_edge:
            sheet.line(pts[i], pts[(i + 1) % sides])
    sheet.text((cx - 5.0, cy + 2.5), mark)


def untrusted_run(sheet, mark, **kw):
    words = words_of(sheet.pdf())
    unknown = tuple(replace(w, text="") for w in words if w.text == mark)
    return run(
        sheet,
        words=[w for w in words if w.text != mark],
        untrusted_plan_words=unknown,
        **kw,
    )


@pytest.mark.parametrize("sides", [3, 4, 8, 12])
@pytest.mark.parametrize("y", [270.0, 302.5, 345.0])
@pytest.mark.parametrize("pattern", [r"[WD]\d+", r"W1"])
def test_other_closed_envelopes_oppose_on_both_sides_and_over_the_strip(
    sides, y, pattern
):
    sheet = three_windows()
    polygon(sheet, (120.0, y), sides)
    result = run(sheet, callout_mark_pattern=pattern)
    c = by_mark(result)["W1"]
    assert c.status is CONF and "strip_has_other_callout_claimants" in c.reason_codes
    assert c.rival_callout_ids and c.strip_id is None
    assert result.callout_exclusions
    assert all(getattr(result, flag) is False for flag in shadow._GRANT_FLAGS)
    # A non-hexagonal envelope never becomes a target that can grant a strip.
    if "D99" in by_mark(result):
        assert by_mark(result)["D99"].status is ABST


@pytest.mark.parametrize("y", [270.0, 302.5, 345.0])
def test_an_untrusted_polygon_label_opposes_without_reading_its_text(y):
    sheet = three_windows()
    polygon(sheet, (120.0, y), 8)
    result = untrusted_run(sheet, "D99")
    c = by_mark(result)["W1"]
    assert (
        c.status is ABST and "strip_has_claimant_with_untrusted_label" in c.reason_codes
    )
    assert c.rival_callout_ids
    assert any(not e.label_trusted for e in result.callout_exclusions)


def test_an_unclosed_polygon_and_a_trusted_nonopening_label_do_not_establish_a_claim():
    sheet = three_windows()
    polygon(sheet, (120.0, 345.0), 8, drop_edge=2)
    assert by_mark(run(sheet))["W1"].status is CAND
    other = three_windows()
    polygon(other, (120.0, 345.0), 8, mark="A7")
    assert by_mark(run(other))["W1"].status is CAND


def test_a_second_envelope_around_the_same_target_is_not_silently_ignored():
    sheet = three_windows()
    words = words_of(sheet.pdf())
    word = next(w for w in words if w.text == "W1")
    cx, cy = (word.bbox[0] + word.bbox[2]) / 2.0, (word.bbox[1] + word.bbox[3]) / 2.0
    pts = [
        (cx + 16.0 * math.cos(i * math.tau / 8), cy + 16.0 * math.sin(i * math.tau / 8))
        for i in range(8)
    ]
    for i in range(8):
        sheet.line(pts[i], pts[(i + 1) % 8])
    c = by_mark(run(sheet))["W1"]
    assert (
        c.status is ABST and "strip_has_unresolved_callout_envelope" in c.reason_codes
    )


def curve_rival(sheet, *, mark="D99", centre=(160.0, 345.0), radius=12.0, fill=None):
    cx, cy = centre
    sheet.plan.draw_circle(
        fitz.Point(cx, cy), radius, color=(0, 0, 0), width=0.7, fill=fill
    )
    sheet.text((cx - 5.0, cy + 2.5), mark)


@pytest.mark.parametrize("pattern", [r"[WD]\d+", r"W[12]", r"W1"])
@pytest.mark.parametrize("y", [270.0, 302.5, 345.0])
def test_real_producer_retains_curved_envelopes_as_unverified_exclusion_only(
    monkeypatch, pattern, y
):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    curve_rival(sheet, centre=(160.0, y))
    source, published = _publish(sheet)
    result = _audit(source, published, pattern=pattern)
    c = by_mark(result)["W1"]
    assert (
        c.status is ABST and "strip_has_unresolved_callout_envelope" in c.reason_codes
    )
    assert any(
        e.native_primitive_refs and not e.visible_ink_ids
        for e in result.callout_exclusions
    )
    visible = set(published.visible_observation_ids)
    for e in result.callout_exclusions:
        assert set(e.visible_ink_ids) <= visible
        assert not (set(e.native_primitive_refs) & visible)
    assert all(getattr(result, flag) is False for flag in shadow._GRANT_FLAGS)


def test_an_untrusted_curved_label_never_becomes_trusted_by_its_raw_spelling(
    monkeypatch,
):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    curve_rival(sheet)
    source, published = _publish(sheet)
    authority = source.text_integrity_authority()
    original = authority.resolve_text

    def unresolved(selector):
        result = original(selector)
        return (
            replace(result, status=ABST, trusted_text=None)
            if result.trusted_text == "D99"
            else result
        )

    monkeypatch.setattr(authority, "resolve_text", unresolved)
    monkeypatch.setattr(source, "text_integrity_authority", lambda: authority)
    result = _audit(source, published, pattern=r"W1")
    assert by_mark(result)["W1"].status is ABST
    assert (
        "strip_has_claimant_with_untrusted_label" in by_mark(result)["W1"].reason_codes
    )
    assert any(
        e.native_primitive_refs and not e.label_trusted
        for e in result.callout_exclusions
    )


def test_curve_inventory_work_exhaustion_is_a_typed_page_abstention(monkeypatch):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    curve_rival(sheet)
    source, published = _publish(sheet)
    monkeypatch.setattr(shadow, "_MAX_ENVELOPE_PAIR_CHECKS", 0)
    result = _audit(source, published)
    assert "native_curve_inventory_budget_exceeded" in result.page_reason_codes
    assert all(
        c.status is ABST
        and c.reason_codes == ("native_curve_inventory_budget_exceeded",)
        for c in result.correspondences
    )
    assert result.strips and all(
        getattr(result, flag) is False for flag in shadow._GRANT_FLAGS
    )


def test_exclusion_inventory_and_full_rows_are_deterministic_on_replay(monkeypatch):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    curve_rival(sheet)
    source, published = _publish(sheet)
    broad = _audit(source, published)
    assert broad == _audit(source, published)
    narrow = _audit(source, published, pattern="W1")
    assert narrow.callout_exclusions == broad.callout_exclusions
    assert by_mark(narrow)["W1"] == by_mark(broad)["W1"]


@pytest.mark.parametrize(
    "patch",
    [
        dict(bbox=(0.0, 0.0, math.nan, 1.0)),
        dict(bbox=(1.0, 0.0, 0.0, 1.0)),
        dict(label_trusted=1),
        dict(word_observation_id=""),
        dict(reason_codes=()),
        dict(bbox=[0.0, 0.0, 1.0, 1.0]),
        dict(reason_codes=["uncertain"]),
        dict(visible_ink_ids=("visible-id",)),
        dict(native_primitive_refs=()),
        dict(native_primitive_refs=["mutable-address"]),
        dict(record_id=3),
    ],
)
def test_malformed_exclusion_receipts_are_rejected(patch):
    params = dict(
        record_id="exclusion",
        word_observation_id="word",
        bbox=(0.0, 0.0, 1.0, 1.0),
        reason_codes=("uncertain",),
        label_trusted=False,
        native_primitive_refs=("native:path:0:item:0",),
    )
    params.update(patch)
    with pytest.raises(ValueError):
        shadow.CalloutExclusion(**params)


@pytest.mark.parametrize(
    "failure",
    ["ink_status", "ink_proposition", "ink_geometry", "text_receipt", "text_geometry"],
)
def test_source_inventory_failures_cannot_erase_a_rival(monkeypatch, failure):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    sheet.callout((160.0, 345.0), "D99")
    source, published = _publish(sheet)
    full = by_mark(_audit(source, published))
    assert full["W1"].status is CONF
    rival = full["D99"]
    if failure.startswith("ink"):
        visibility = source.authority()
        old = visibility.resolve_visible
        selected = set(rival.ring.ink_ids)

        def damaged(selector):
            result = old(selector)
            if selector.observation_id not in selected:
                return result
            if failure == "ink_status":
                return replace(result, status=ABST, observation=None, proposition=None)
            if failure == "ink_proposition":
                return replace(result, proposition=None)
            return replace(
                result,
                observation=replace(result.observation, geometry=(0.0, 0.0, 1.0, 1.0)),
            )

        monkeypatch.setattr(visibility, "resolve_visible", damaged)
        monkeypatch.setattr(source, "authority", lambda: visibility)
        reason = "source_visible_ink_inventory_incomplete"
    else:
        authority = source.text_integrity_authority()
        old = authority.resolve_text

        def damaged(selector):
            result = old(selector)
            if selector.observation_id != rival.tag_observation_id:
                return result
            return (
                replace(result, status=ABST, receipt=None, trusted_text=None)
                if failure == "text_receipt"
                else replace(result, receipt=replace(result.receipt, geometry=()))
            )

        monkeypatch.setattr(authority, "resolve_text", damaged)
        monkeypatch.setattr(source, "text_integrity_authority", lambda: authority)
        reason = "source_text_inventory_incomplete"
    result = _audit(source, published, pattern=r"W1")
    c = by_mark(result)["W1"]
    assert c.status is ABST and reason in c.reason_codes
    assert reason in result.page_reason_codes and c.strip_id is None
    assert all(getattr(result, flag) is False for flag in shadow._GRANT_FLAGS)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_curve_opposition_uses_native_page_coordinates_under_rotation(
    monkeypatch, rotation
):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet(plan_rotation=rotation)
    curve_rival(sheet)
    source, published = _publish(sheet)
    c = by_mark(_audit(source, published, pattern="W1"))["W1"]
    assert (
        c.status is ABST and "strip_has_unresolved_callout_envelope" in c.reason_codes
    )


def test_unrelated_components_in_one_drawing_are_not_joined_into_a_false_envelope(
    monkeypatch,
):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    shape = sheet.plan.new_shape()
    shape.draw_circle(fitz.Point(80.0, 345.0), 12.0)
    shape.draw_circle(fitz.Point(240.0, 345.0), 12.0)
    shape.finish(color=(0, 0, 0), width=0.7)
    shape.commit()
    sheet.text((155.0, 347.5), "D99")
    source, published = _publish(sheet)
    assert by_mark(_audit(source, published, pattern="W1"))["W1"].status is CAND


def test_native_path_item_budget_is_fail_closed_even_before_pair_matching(monkeypatch):
    _resolved_viewport(monkeypatch)
    source, published = _publish(_plan_sheet())
    monkeypatch.setattr(shadow, "_MAX_NATIVE_PATH_ITEMS", 0)
    result = _audit(source, published)
    assert all(
        c.status is ABST and "native_curve_inventory_budget_exceeded" in c.reason_codes
        for c in result.correspondences
    )


@pytest.mark.parametrize("paint", ["dashed", "transparent", "partial_opacity"])
def test_path_geometry_cannot_stand_in_for_continuous_opaque_ink(monkeypatch, paint):
    _resolved_viewport(monkeypatch)

    def line(self, a, b, page=None, double=False, width=0.48, color=(0, 0, 0)):
        for _ in range(2 if double else 1):
            (page or self.plan).draw_line(
                fitz.Point(*a),
                fitz.Point(*b),
                width=width,
                color=color,
                dashes="[1 2] 0" if paint == "dashed" else None,
                stroke_opacity=0.0
                if paint == "transparent"
                else (0.3 if paint == "partial_opacity" else 1.0),
            )

    monkeypatch.setattr(Sheet, "line", line)
    sheet = _plan_sheet()
    drawings = sheet.plan.get_drawings()
    assert (
        any(d.get("dashes") != "[] 0" for d in drawings) if paint == "dashed" else True
    )
    source, published = _publish(sheet)
    result = _audit(source, published)
    assert all(c.status is ABST and c.strip_id is None for c in result.correspondences)
    assert not result.strips


def test_distinct_near_width_classes_cannot_jointly_fabricate_a_strip():
    sheet = three_windows()
    ink = [
        replace(s, width=0.4801 if i % 2 else 0.4804)
        for i, s in enumerate(ink_of(sheet.pdf()))
    ]
    result = run(sheet, ink=ink)
    assert not result.strips
    assert all(c.status is ABST for c in result.correspondences)


def test_uncertain_paint_envelope_can_oppose_but_never_be_positive_support():
    sheet = three_windows()
    polygon(sheet, (120.0, 345.0), 8)
    pdf = sheet.pdf()
    words = words_of(pdf)
    rival = next(w for w in words if w.text == "D99")
    complete = shadow._ring_for_word(
        rival, shadow._black_lines(ink_of(pdf)), 0.06, sides=None
    )
    ids = set(complete.ink_ids)
    ink = [
        replace(s, continuous_opaque=False) if s.ink_id in ids else s
        for s in ink_of(pdf)
    ]
    result = run(sheet, ink=ink)
    c = by_mark(result)["W1"]
    assert (
        c.status is ABST and "strip_has_unresolved_callout_envelope" in c.reason_codes
    )
    assert any(
        "callout_envelope_paint_coverage_unproven" in e.reason_codes
        for e in result.callout_exclusions
    )


@pytest.mark.parametrize("factor", [1.0, 0.37, 0.01, 0.001, 0.0001])
@pytest.mark.parametrize("rival", [False, True])
def test_uniform_coordinate_changes_preserve_positive_and_opposed_decisions(
    factor, rival
):
    sheet = three_windows()
    if rival:
        polygon(sheet, (120.0, 345.0), 8)
    pdf = sheet.pdf()
    ink, words, types = ink_of(pdf), words_of(pdf), types_of(sheet)
    scope = scope_for(sheet)
    baseline = run(sheet, scope=scope, ink=ink, words=words, types=types)
    ink = [
        replace(
            s,
            x0=s.x0 * factor,
            y0=s.y0 * factor,
            x1=s.x1 * factor,
            y1=s.y1 * factor,
            width=s.width * factor,
        )
        for s in ink
    ]
    words = [replace(w, bbox=tuple(c * factor for c in w.bbox)) for w in words]
    scope = replace(
        scope,
        coordinate_quantum_pt=scope.coordinate_quantum_pt * factor,
        plan_viewports=tuple(
            replace(v, bbox=tuple(c * factor for c in v.bbox))
            for v in scope.plan_viewports
        ),
    )
    result = run(sheet, scope=scope, ink=ink, words=words, types=types)
    assert {
        m: (c.status, c.reason_codes, c.conditions) for m, c in by_mark(result).items()
    } == {
        m: (c.status, c.reason_codes, c.conditions)
        for m, c in by_mark(baseline).items()
    }


def test_coordinate_identity_cannot_chain_beyond_its_equality_bound():
    values = [i * 0.04 for i in range(30)]
    for order in (values, list(reversed(values))):
        representative = shadow._snapper(order, 0.05)
        assert all(abs(v - representative(v)) <= 0.05 for v in values)


def test_losing_trust_in_one_elevation_panel_cannot_forge_a_smaller_panel_count(
    monkeypatch,
):
    _resolved_viewport(monkeypatch)
    sheet = Sheet(size=(1500.0, 700.0))
    for k, (mark, panels, width, _height) in enumerate(SPECS):
        strip = sheet.strip(
            "H",
            100.0 + 400.0 * k,
            300.0,
            panels=2 if k == 0 else panels,
            frame_len=width / (ELEVATION_MM_PER_PT / 2.0),
        )
        sheet.callout(
            (
                (strip["frame"][0] + strip["frame"][1]) / 2.0 + 2.0,
                strip["band"][1] + GAP + HEX_H,
            ),
            mark,
        )
    _draw_elevation(sheet)
    source, published = _publish(sheet)
    full = by_mark(_audit(source, published))
    assert full["W1"].status is ABST
    authority = source.text_integrity_authority()
    original = authority.resolve_text
    from pb_source_observation_authority import ObservationSelector

    selected = None
    for oid in published.text_observation_ids:
        result = original(
            ObservationSelector(
                published.revision.document_id,
                published.revision.revision_id,
                published.revision.source_sha256,
                published.snapshot.snapshot_id,
                oid,
            )
        )
        if (
            result.trusted_text == "FG"
            and result.receipt.page_id == "2"
            and result.receipt.geometry[0] < 300.0
        ):
            selected = oid
            break
    assert selected

    def unknown(selector):
        result = original(selector)
        return (
            replace(result, status=ABST, trusted_text=None)
            if selector.observation_id == selected
            else result
        )

    monkeypatch.setattr(authority, "resolve_text", unknown)
    monkeypatch.setattr(source, "text_integrity_authority", lambda: authority)
    c = by_mark(_audit(source, published))["W1"]
    assert c.status is ABST and "elevation_panel_inventory_unverified" in c.reason_codes


def test_unverified_elevation_panels_do_not_support_another_types_ratio_group():
    sheet = three_windows()
    types = types_of(sheet)
    types = [
        replace(t, unverified_panel_observation_ids=("untrusted-word",)) for t in types
    ]
    result = run(sheet, types=types)
    assert all(
        c.status is ABST and "elevation_panel_inventory_unverified" in c.reason_codes
        for c in result.correspondences
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_a_twice_winding_six_edge_star_is_not_a_convex_hexagon(reverse):
    sheet = Sheet(size=(1400.0, 900.0))
    _, (cx, cy) = add_window(sheet, 0, "W1", panels=3, length=204.0, callout=False)
    angles = (0, 110, 220, 330, 80, 190)
    points = [
        (cx + 12.0 * math.cos(math.radians(a)), cy + 12.0 * math.sin(math.radians(a)))
        for a in angles
    ]
    if reverse:
        points.reverse()
    for i in range(6):
        sheet.line(points[i], points[(i + 1) % 6])
    sheet.text((cx - 5.0, cy + 2.5), "W1")
    add_window(sheet, 1, "W2", panels=3, length=232.0)
    add_window(sheet, 2, "W3", panels=5, length=120.0)
    c = by_mark(run(sheet))["W1"]
    assert c.status is ABST and "callout_ring_not_found" in c.reason_codes


def test_the_local_census_exposes_reviewable_exclusions_and_source_scope(
    monkeypatch, tmp_path
):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    curve_rival(sheet)
    path = tmp_path / "generated.pdf"
    path.write_bytes(sheet.pdf())
    from tools.diag_plan_callout_strip_census import census

    result = census(
        path,
        plan_page=1,
        elevation_page=2,
        callout_mark_pattern=r"W1",
        panel_token="FG",
        coordinate_quantum_pt=0.24,
        dimension_quantum_mm=5.0,
        native_finish_text_shadow=False,
    )
    assert result["document_id"] and result["revision_id"] and result["snapshot_id"]
    assert any(
        e["unverified_native_primitive_refs"] and not e["visible_ink_ids"]
        for e in result["callout_exclusions"]
    )
    assert result["rows"][0]["rival_callout_ids"]
    assert result["rows"][0]["status"] == ABST.value
    assert all(value is False for value in result["grants"].values())


def test_an_unverified_control_box_does_not_erase_an_edge_word_claimant():
    sheet = three_windows()
    sheet.text((252.0, 347.5), "D99")
    word = next(w for w in words_of(sheet.pdf()) if w.text == "D99")
    scope = scope_for(sheet)
    exclusion = shadow._exclusion(
        scope,
        word,
        (250.0, 333.0, 284.0, 357.0),
        ("native_curve_callout_visibility_unproven",),
        True,
        primitive_refs=("native:path:0:item:0",),
    )
    scope = replace(scope, native_curve_exclusions=(exclusion,))
    c = by_mark(run(sheet, scope=scope))["W1"]
    assert (
        c.status is ABST and "strip_has_unresolved_callout_envelope" in c.reason_codes
    )


def test_native_evidence_replication_budget_cannot_silently_drop_opposition(
    monkeypatch,
):
    _resolved_viewport(monkeypatch)
    sheet = _plan_sheet()
    curve_rival(sheet)
    source, published = _publish(sheet)
    monkeypatch.setattr(shadow, "_MAX_ENVELOPE_EVIDENCE_REFS", 0)
    result = _audit(source, published)
    assert all(
        c.status is ABST and "native_curve_inventory_budget_exceeded" in c.reason_codes
        for c in result.correspondences
    )
