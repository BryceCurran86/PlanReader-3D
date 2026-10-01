"""PlanReader v1.3.0 Accuracy Lab UI.

Adds native vector analysis, benchmark scoring, and a one-click Fix workflow that
opens the exact source drawing for an error and records the estimator correction.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

VERSION = "1.3.0"
_CATEGORIES = [
    "sheet_classification", "scale", "floor_area", "ceiling_area", "room_perimeter",
    "door_count", "window_count", "external_area", "substrate_allocation",
    "finish_association", "missed_scope", "false_inclusion",
]


def _truth_row(app: Any, workspace_id: int, detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rows = app.lquery(
        "SELECT * FROM accuracy_ground_truth WHERE workspace_id=? AND category=? AND item_key=? LIMIT 1",
        (int(workspace_id), str(detail.get("category") or ""), str(detail.get("item_key") or "")),
    )
    return dict(rows[0]) if rows else None


def _page_row(app: Any, page_id: Any) -> Optional[Dict[str, Any]]:
    if not page_id:
        return None
    rows = app.lquery(
        """SELECT p.*,d.file_name,d.path AS document_path FROM pages p
           JOIN documents d ON d.id=p.document_id WHERE p.id=? LIMIT 1""",
        (int(page_id),),
    )
    return dict(rows[0]) if rows else None


def _is_error(detail: Dict[str, Any]) -> bool:
    if not detail.get("matched"):
        return True
    if "correct" in detail:
        return not bool(detail.get("correct"))
    return float(detail.get("percent_error") or 0.0) > 0.001


def _render_fix_panel(app: Any, workspace_id: int, detail: Dict[str, Any]) -> None:
    truth = _truth_row(app, workspace_id, detail) or {}
    page = _page_row(app, truth.get("page_id"))
    app.st.markdown("### Verify & fix")
    app.st.caption(f"{detail.get('category')} · {detail.get('item_key')}")

    c1, c2, c3 = app.st.columns(3)
    c1.metric("PlanReader", str(detail.get("predicted", "No result")))
    c2.metric("Verified / expected", str(detail.get("expected", "")))
    if detail.get("percent_error") is not None:
        c3.metric("Error", f"{float(detail.get('percent_error') or 0):.2f}%")
    elif "correct" in detail:
        c3.metric("Match", "Yes" if detail.get("correct") else "No")
    else:
        c3.metric("Status", "Missing")

    if page:
        app.st.info(
            f"Source page: {page.get('page_label') or 'Unlabelled'} · page {int(page.get('page_no') or 0)} · "
            f"{page.get('page_type') or 'Other'} · {page.get('file_name') or ''}"
        )
        image_path = Path(str(page.get("image_path") or ""))
        if image_path.is_file():
            app.st.image(str(image_path), caption=f"Verify on {page.get('page_label') or 'source drawing'}", use_container_width=True)
        else:
            app.st.warning("The source page is identified, but its rendered image is not currently available. Re-process/render this page to verify visually.")
    else:
        app.st.warning("This benchmark item is not yet linked to a drawing page. Link it to the correct page before accepting the correction.")

    numeric_expected = truth.get("expected_numeric") is not None
    form_key = f"accuracy_fix_form_{workspace_id}_{detail.get('category')}_{detail.get('item_key')}"
    with app.st.form(form_key):
        if numeric_expected:
            default_value = detail.get("expected")
            corrected_raw = app.st.text_input("Correct value", value=str(default_value if default_value is not None else ""))
            corrected_text = ""
        else:
            corrected_raw = ""
            corrected_text = app.st.text_input("Correct value", value=str(detail.get("expected") or ""))
        reason = app.st.text_area(
            "Why was PlanReader wrong?",
            placeholder="e.g. missed breezeway wall; wrong scale; opening deducted twice; finish code linked to wrong legend row",
        )
        save = app.st.form_submit_button("Save fix as verified", type="primary", use_container_width=True)
    if save:
        corrected_numeric = None
        if numeric_expected:
            try:
                corrected_numeric = float(str(corrected_raw).replace(",", ""))
            except ValueError:
                app.st.error("Correct value must be numeric.")
                return
        user = str((app.st.session_state.get("planreader_user") or {}).get("username") or "")
        app.accuracy_record_correction_v130(
            int(workspace_id), str(detail.get("category") or ""), str(detail.get("item_key") or ""),
            predicted_numeric=float(detail.get("predicted")) if numeric_expected and detail.get("predicted") is not None else None,
            corrected_numeric=corrected_numeric,
            predicted_text="" if numeric_expected else str(detail.get("predicted") or ""),
            corrected_text=corrected_text,
            unit=str(truth.get("unit") or ""),
            page_id=int(truth.get("page_id")) if truth.get("page_id") else None,
            reason=str(reason or "").strip(),
            source_reference=str(truth.get("source_reference") or ""),
            corrected_by=user,
            engine_version=VERSION,
        )
        app.st.session_state.pop(f"accuracy_fix_{workspace_id}", None)
        report = app.accuracy_evaluate_workspace_v130(int(workspace_id), VERSION)
        app.st.session_state[f"accuracy_benchmark_{workspace_id}"] = report
        app.st.success("Fix saved. The correction is now retained as verified learning/benchmark evidence.")
        app.st.rerun()

    if app.st.button("Close verification", use_container_width=True, key=f"accuracy_fix_close_{workspace_id}"):
        app.st.session_state.pop(f"accuracy_fix_{workspace_id}", None)
        app.st.rerun()


def apply(app: Any) -> None:
    """RETIRED LEGACY BENCHMARK UI.
    
    Per permanent project directive, the legacy canonical-five / Accuracy Lab UI
    is completely retired and deactivated. Active validation is governed by the
    V2 full-plan truth framework.
    """
    if getattr(app, "_pb_accuracy_ui_v130_applied", False):
        return
    app._pb_accuracy_ui_v130_applied = True
    return

