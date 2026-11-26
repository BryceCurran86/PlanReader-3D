"""Guided review surface for the existing original Plan Mapper."""
import hashlib
from pathlib import Path
import sqlite3

from pb_guided_plan_review import (
    DECISIONS, ISSUES, ReviewScope, editor_rows, editor_shapes,
    load_review, normalise_answer, normalise_editor_shapes, review_issues,
    save_review,
)


def _original_page_png(path, source_sha, pdf_page):
    # Display fallback only, NOT a second tracing engine.
    import fitz
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != source_sha:
        raise ValueError("Original drawing changed")
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[pdf_page - 1]
        zoom = min(1.2, 1800 / max(page.rect.width, page.rect.height))
        return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")


def render_guided_plan_review(st, *, workspace, page, native_trace, doc_path,
                              registered_sha, connect, line_editor):
    st.markdown("### Guided plan review")
    st.caption("Automatic reading first; correct only what is missing or uncertain. "
               "Drawn corrections and your answers stay separate from automatic source evidence.")
    digest = native_trace.get("digest")
    if not digest or digest != str(registered_sha or "").strip().lower():
        st.warning("The original PDF must match its registered source before corrections can be saved.")
        return
    report = native_trace.get("summary") or {}
    pdf_page = int(page["page_no"])
    overlay = native_trace.get("png")
    overlay_matches = (
        isinstance(overlay, bytes) and bool(overlay)
        and report.get("source_sha256") == digest
        and report.get("page_index") == pdf_page - 1
    )
    if overlay_matches:
        image = overlay
        st.caption("Original-plan trace overlay: cyan/blue/purple wall candidates, orange "
                   "temporary doorway closures, green candidate room rings. None of these colours "
                   "proves a measured quantity. Magenta near-miss marks need review.")
    else:
        # Failure or an incomplete source trace must not hide the original sheet.
        cache_key = f"guided_original_image_{workspace['id']}_{page['id']}"
        cached = st.session_state.get(cache_key)
        try:
            if not cached or cached[0] != digest:
                cached = (digest, _original_page_png(doc_path, digest, pdf_page))
                st.session_state[cache_key] = cached
            image = cached[1]
        except (ValueError, OSError, RuntimeError, IndexError):
            st.error("The registered drawing could not be displayed; no corrections saved.")
            return
        st.warning("Automatic trace unavailable for this page. Review the original drawing; "
                   "no automatic wall, opening or room authority is inferred.")
    scope = ReviewScope(int(workspace["id"]), int(page["id"]), pdf_page,
                        digest, hashlib.sha256(image).hexdigest())
    try:
        saved = load_review(connect, scope)
    except (ValueError, sqlite3.Error, KeyError, TypeError) as exc:
        st.error(f"Could not open the local review draft: {exc}")
        return
    issues = review_issues(report, scale_verified=page.get("scale_verified") == 1)
    prefix = f"guided_{scope.key}_{saved['revision']}"
    pending_key = f"guided_pending_{scope.key}"
    pending = st.session_state.get(pending_key)
    if pending is None or pending[0] != saved["revision"]:
        pending = (saved["revision"], editor_shapes(saved["shapes"]))
        st.session_state[pending_key] = pending
    st.caption(f"{len(issues)} review questions · {len(saved['shapes'])} saved drawn corrections · "
               f"{len(saved['answers'])} saved answers")
    st.warning("Review draft only: closure, scale, material and quantity authority have not yet "
               "been recomputed. Saving an answer does not verify automatic geometry.")
    if line_editor is None:
        st.image(image, use_container_width=True)
        st.info("Interactive editing is unavailable; you can still record review answers.")
    else:
        st.markdown("**Mark or correct the drawing**")
        st.caption("Choose a correction category, then Line (two points) or Outline "
                   "(room or exclusion). Select, move or delete your own shapes. "
                   "Use 'Reject an existing wall / opening candidate' to flag unwanted automatic ink.")
        from pb_guided_plan_review_snap import build_review_snap_targets
        snap_cache_key = f"guided_snap_targets_{scope.key}"
        if snap_cache_key not in st.session_state:
            targets = []
            if overlay_matches:
                try:
                    targets = build_review_snap_targets(
                        scope=scope, pdf_path=doc_path, image_bytes=image, report=report,
                    )
                except (ValueError, OSError, RuntimeError, TypeError, KeyError):
                    pass  # Preserve manual editing if source snap provenance is incomplete.
            st.session_state[snap_cache_key] = targets
        targets = st.session_state[snap_cache_key]
        st.caption(f"Magnetic placement: {len(targets)} source endpoint candidates plus "
                   "your own drawn vertices. Toggle Snap or hold Alt for free placement. "
                   "Snapping is a positioning aid, not proof of a physical wall or opening.")
        result = line_editor(image, pending[1], editor_rows(), 0.0, saved["revision"],
                             key=prefix + "_canvas", height=760, review_snap_targets=targets)
        if result is not None:
            st.session_state[pending_key] = (saved["revision"], result)
            pending = st.session_state[pending_key]
    st.markdown("**Review questions**")
    descriptions = dict(issues)
    # Keep previously answered questions available even if a page calibration
    # subsequently removes one from the initial question inventory.
    question_ids = list(dict.fromkeys([*descriptions, *saved["answers"]]))
    issue = st.selectbox("Select a question", question_ids,
                         format_func=lambda k: ISSUES[k], key=prefix + "_issue")
    st.caption(descriptions.get(issue, "Previously recorded review question"))
    previous = saved["answers"].get(issue, {})
    decision = st.selectbox("Review decision", DECISIONS,
                            index=DECISIONS.index(previous.get("decision", DECISIONS[0])),
                            format_func=lambda v: {
                                "needs_information": "Still needs information",
                                "correction_recorded": "Correction / information recorded",
                                "reviewed_no_change": "Reviewed; no change proposed",
                            }[v], key=prefix + "_decision_" + issue)
    note = st.text_area("Drawing reference, finish specification or explanation",
                        value=previous.get("note", ""), max_chars=2000,
                        key=prefix + "_note_" + issue)
    dimension = None
    if issue in {"scale", "height", "openings"}:
        entered = st.number_input("Source dimension (mm; 0 means not supplied)",
                                  min_value=0.0, max_value=1_000_000.0,
                                  value=float(previous.get("dimension_mm") or 0),
                                  step=1.0, key=prefix + "_dim_" + issue)
        dimension = entered or None
    witness = None
    if issue == "scale" and decision == "correction_recorded" and dimension is not None:
        try:
            marks = normalise_editor_shapes(pending[1])
        except ValueError:
            marks = []
        witnesses = {m["id"]: m for m in marks if m["category"] == "dimension_witness"}
        choices = [None, *witnesses]
        initial = previous.get("correction_id")
        chosen = st.selectbox(
            "Which drawn dimension line does this value describe?",
            choices, index=choices.index(initial) if initial in choices else 0,
            format_func=lambda k: "Not bound — information only" if k is None
            else f"Dimension witness {list(witnesses).index(k)+1}: {k}",
            key=prefix + "_scale_witness",
        )
        witness = witnesses.get(chosen)
        if witness is not None:
            st.caption("The dimension applies to these exact two selected points only. "
                       "Moving or deleting them requires clearing or reconfirming the answer.")
    clear_answer = st.checkbox("Remove this saved answer", value=False,
                               key=prefix + "_clear_" + issue) if previous else False
    include_answer = st.checkbox("Save this question's answer with my corrections",
                                 value=False, key=prefix + "_include_" + issue)
    if st.button("Save user review draft", type="primary", key=prefix + "_save"):
        try:
            # Validate all the current shapes before any database mutation.
            normalise_editor_shapes(pending[1])
            answers = dict(saved["answers"])
            if clear_answer:
                answers.pop(issue, None)
            elif include_answer:
                answers[issue] = normalise_answer(
                    issue, decision, note, dimension,
                    correction_id=witness["id"] if witness else None,
                    witness_points=witness["points"] if witness else None,
                )
            save_review(connect, scope, expected_revision=saved["revision"],
                        shapes=pending[1], answers=answers)
        except (ValueError, TypeError, sqlite3.Error) as exc:
            st.error(f"Review not saved: {exc}")
        else:
            st.session_state.pop(pending_key, None)
            st.rerun()
    if saved["answers"]:
        st.markdown("**Saved answers — user review, not measured evidence**")
        st.dataframe([
            {"Question": ISSUES[k], "Decision": v["decision"],
             "Reference / explanation": v["note"], "Dimension (mm)": v["dimension_mm"]}
            for k, v in saved["answers"].items()
        ], hide_index=True, use_container_width=True)
    st.markdown("**Prepare corrected geometry for the measurement engine**")
    if saved["revision"] > 0:
        from pb_guided_plan_review_native import build_native_review_packet
        packet_key = f"guided_native_packet_{scope.key}"
        packet = st.session_state.get(packet_key)
        if packet is None or packet.get("review_revision") != saved["revision"]:
            st.session_state.pop(packet_key, None)
            try:
                packet = build_native_review_packet(
                    scope=scope, pdf_path=doc_path, image_bytes=image, saved=saved,
                    canonical_report=report if overlay_matches else None,
                )
                st.session_state[packet_key] = packet
            except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
                packet = None
                st.warning(f"Native correction handoff blocked: {exc}")
        if packet is not None:
            st.caption(
                f"{len(packet['corrections'])} source-page correction marks prepared. "
                "Affected stages: "
                + (", ".join(packet["affected_stage_candidates"]) or "none proposed")
                + ". Geometry and quantities have not yet been regenerated."
            )
            from pb_guided_review_source_questions import (
                build_review_to_issuer_handoff, build_user_assisted_scale_issuer_request,
            )
            handoff = build_review_to_issuer_handoff(native_review_packet=packet)
            st.caption(f"Source review routing: {len(handoff.actionable_directives)} "
                       f"proposed directives; {len(handoff.unresolved_information_requests)} "
                       "explicit information requests. These are not completed measurements.")
            if handoff.status == "ABSTAINED":
                st.warning("Source review routing blocked: " + ", ".join(handoff.reason_codes))
            scale_request = build_user_assisted_scale_issuer_request(handoff=handoff)
            if scale_request.status == "USER_ASSISTED_SCALE_INPUT_READY":
                st.info(f"Selected dimension: {scale_request.figured_mm:g} mm across "
                        f"{scale_request.span_pdf_pts:g} PDF points. "
                        f"Proposed local scale: {scale_request.implied_mm_per_pt:g} mm/pt. "
                        "Not applied to a viewport or measured quantities.")
            elif "scale" in saved["answers"]:
                st.caption("Scale remains unresolved: " + ", ".join(scale_request.reason_codes))
            import json
            st.download_button(
                "Export private correction packet (JSON)",
                data=json.dumps(packet, indent=2, sort_keys=True),
                file_name=f"plan-review-page-{pdf_page}-r{saved['revision']}.json",
                mime="application/json", key=prefix + "_packet",
            )
    st.caption("Drafts are stored locally against this exact registered PDF, page and displayed "
               "image. A changed image or revision does not silently inherit old correction geometry. "
               "The prepared native marks require the existing topology/quantity consumers to "
               "validate them before any automatic re-closure, recalculation or VR handoff.")
