"""pb_jobhub_publishing_pipeline.py — End-to-End PlanReader -> JobHub Publishing Pipeline.

Orchestrates package construction, gate validation, TOCTOU verification,
and atomic publishing to JobHub with full support for DRAFT and COMMERCIAL modes.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_jobhub_publishing_contract import (
    BenchmarkStatusPayload,
    DrawingRevisionPayload,
    ExcludedScopePayload,
    ProjectIdentityPayload,
    PublishingGateResult,
    PublishingMode,
    PublishingPackagePayload,
    PublishingWarningPayload,
    QuantityLineItemPayload,
    validate_publishing_gate,
)


def build_publishing_package_from_workspace(
    conn: sqlite3.Connection,
    workspace_id: int,
    mode: PublishingMode = PublishingMode.COMMERCIAL,
    benchmark_status: Optional[BenchmarkStatusPayload] = None,
    preflight_fingerprint: str = "",
    acting_user: Optional[str] = None,
) -> PublishingPackagePayload:
    """Build a standard PublishingPackagePayload from an active PlanReader SQLite database.

    Attribution must be explicit:
    - ``estimator`` comes from workspace metadata when present (never a named default).
    - ``created_by`` comes from ``acting_user`` when provided, before payload fingerprinting.
    Missing commercial attribution remains missing and is blocked by the publishing gate.
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Fetch Workspace Metadata
    cur.execute(
        """
        SELECT id, job_no, job_name, builder_client, site_address, drawing_issue, jobhub_job_id, estimator
        FROM workspaces WHERE id=?
        """,
        (workspace_id,),
    )
    ws_row = cur.fetchone()
    if not ws_row:
        raise ValueError(f"Workspace #{workspace_id} not found")

    job_no = str(ws_row["job_no"] or "")
    job_name = str(ws_row["job_name"] or "")
    site_address = str(ws_row["site_address"] or "")
    builder_client = str(ws_row["builder_client"] or "")
    raw_estimator = ws_row["estimator"]
    estimator = str(raw_estimator).strip() if raw_estimator else None
    if estimator == "":
        estimator = None
    # A workspace SQLite INTEGER-affinity column can still hold REAL/TEXT/BLOB.
    # int(501.9) silently truncates to 501, then the freshly computed payload
    # hash seals that WRONG target as an exact integer, bypassing the final
    # writer's canonical-ID check. Never mint destination identity by casting.
    raw_target_job_id = ws_row["jobhub_job_id"]
    if raw_target_job_id is None:
        target_job_id = None  # Missing link remains unpublishable downstream.
    elif type(raw_target_job_id) is not int or raw_target_job_id <= 0:
        raise ValueError(
            "Workspace JobHub job ID must be an exact positive integer"
        )
    else:
        target_job_id = raw_target_job_id

    project_identity = ProjectIdentityPayload(
        job_no=job_no,
        job_name=job_name,
        site_address=site_address,
        builder_client=builder_client,
        estimator=estimator,
        target_jobhub_job_id=target_job_id,
    )

    # 2. Fetch Document & Revision Metadata
    cur.execute("PRAGMA table_info(documents)")
    document_columns = {row[1] for row in cur.fetchall()}
    has_original_sha = "sha256" in document_columns
    cur.execute(
        (
            "SELECT file_name, sha256 FROM documents WHERE workspace_id=? ORDER BY id ASC"
            if has_original_sha else
            "SELECT file_name FROM documents WHERE workspace_id=? ORDER BY id ASC"
        ),
        (workspace_id,),
    )
    doc_rows = cur.fetchall()
    # SQLite ingestion row order is not drawing-revision authority. Preserve the
    # full filename multiset but seal it in canonical order, consistent with
    # the already-sorted (filename, source SHA-256) revision manifest.
    # The source revision manifest below already strips incidental filename
    # padding before hashing (filename, SHA-256). Use the SAME canonical name
    # for the separately sealed file roster, or byte-identical re-ingestion
    # with padded names can evade the transactional JobHub duplicate check.
    # Preserve case and multiplicity; an empty canonical name remains invalid
    # source evidence for the commercial revision manifest.
    file_names = sorted(
        name for row in doc_rows
        if (name := str(row["file_name"] or "").strip())
    )
    # The publisher must never substitute filename equality for PDF byte
    # identity. SHA values originate from source ingestion; separate original
    # byte replay is still required for full benchmark/issuer certification.
    revision_documents = []
    if has_original_sha:
        for doc in doc_rows:
            name = str(doc["file_name"] or "").strip()
            digest = str(doc["sha256"] or "").strip()
            if (
                not name or len(digest) != 64
                or any(ch not in "0123456789abcdef" for ch in digest)
            ):
                revision_documents = []
                break
            revision_documents.append((name, digest))

    cur.execute(
        "SELECT COUNT(*) FROM pages WHERE workspace_id=?",
        (workspace_id,),
    )
    sheet_count = cur.fetchone()[0] or 0

    # A missing workspace issue is unknown, not a default BA revision.
    drawing_issue = str(ws_row["drawing_issue"] or "").strip()
    rev_hash = (
        hashlib.sha256(json.dumps(
            sorted(revision_documents),
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        if revision_documents and len(revision_documents) == len(doc_rows)
        else ""  # source SHA missing or invalid: not commercial-publishable
    )

    drawing_revision = DrawingRevisionPayload(
        drawing_issue=drawing_issue,
        # The workspace has no authenticated original drawing date. Publishing
        # time is not a drawing revision: using today() changes the sealed
        # payload hash across days and lets unchanged packages evade the
        # JobHub duplicate check. Keep source date explicitly unknown.
        drawing_date="",
        sheet_count=sheet_count,
        source_files_hash=rev_hash,
        file_names=file_names,
    )

    # 3. Fetch Takeoff Line Items & Measurement Authorities
    cur.execute("PRAGMA table_info(takeoff_rows)")
    cols = {r[1] for r in cur.fetchall()}

    query = """
    SELECT id, section, location, substrate, finish_tag, element, unit, quantity, rate, total_price,
           commercial_authority_status, commercial_authority_source, commercial_authority_reviewed_by,
           commercial_authority_reviewed_at, source_page, notes
    FROM takeoff_rows
    WHERE workspace_id=?
    ORDER BY id ASC
    """ if "commercial_authority_status" in cols else """
    SELECT id, section, location, substrate, '' AS finish_tag, element, unit, quantity, rate, total_price,
           'provisional' AS commercial_authority_status, 'provisional' AS commercial_authority_source,
           NULL AS commercial_authority_reviewed_by, NULL AS commercial_authority_reviewed_at,
           '' AS source_page, '' AS notes
    FROM takeoff_rows
    WHERE workspace_id=?
    ORDER BY id ASC
    """

    cur.execute(query, (workspace_id,))
    takeoff_rows = cur.fetchall()

    quantities: List[QuantityLineItemPayload] = []
    excluded_items: List[ExcludedScopePayload] = []
    warnings: List[PublishingWarningPayload] = []

    for r in takeoff_rows:
        row_id = int(r["id"])
        section = str(r["section"] or "Takeoff")
        loc = str(r["location"] or "General")
        sub = str(r["substrate"] or "Plasterboard")
        tag = str(r["finish_tag"] or "")
        elem = str(r["element"] or "Element")
        unit = str(r["unit"] or "m²")
        qty = float(r["quantity"] or 0.0)
        rate = float(r["rate"] or 0.0)
        # Price is a client-owned commercial input. A zero entered amount is
        # never permission to silently replace it with quantity × rate, nor
        # is a missing price approval to quote a computed line to JobHub.
        if r["total_price"] is None and mode == PublishingMode.COMMERCIAL:
            raise ValueError(
                f"Missing client commercial line total for takeoff row #{row_id}"
            )
        tot = (
            float(r["total_price"])
            if r["total_price"] is not None
            else (qty * rate)  # draft estimate only, never a published sale
        )

        # Missing provenance cannot become source-authenticated FIRM by a
        # schema fallback or NULL from an older PlanReader workspace.
        auth_status = str(
            r["commercial_authority_status"] or AuthorityStatus.PROVISIONAL.value
        ).lower()
        auth_src = str(
            r["commercial_authority_source"] or MeasurementAuthorityType.PROVISIONAL.value
        ).lower()
        reviewed_by = r["commercial_authority_reviewed_by"]
        reviewed_at = r["commercial_authority_reviewed_at"]
        source_page = str(r["source_page"] or "")
        notes = str(r["notes"] or "")

        # Do not guess exclusion by section/finish/material words. Screed,
        # sealants, powder-coated products and mastic can be genuine separately
        # measured construction trade scope. Only the issuer's EXPLICIT
        # excluded authority can remove a row from a customer takeoff.
        if auth_status == AuthorityStatus.EXCLUDED.value or (
            auth_src == MeasurementAuthorityType.EXCLUDED.value
        ):
            excluded_items.append(
                ExcludedScopePayload(
                    item_code=tag or f"EXCL_{row_id}",
                    description=f"{elem} ({sub})",
                    reason=notes or "Explicitly excluded by source measurement authority",
                    trade=section,
                )
            )
            continue

        quantities.append(
            QuantityLineItemPayload(
                row_id=row_id,
                section=section,
                location=loc,
                substrate=sub,
                finish_tag=tag,
                element=elem,
                unit=unit,
                quantity=qty,
                rate=rate,
                total_price=tot,
                authority_type=auth_src,
                authority_status=auth_status,
                confidence=1.0 if auth_status == AuthorityStatus.FIRM.value else 0.7,
                source_page=source_page,
                approved_by=reviewed_by,
                approved_at=reviewed_at,
                notes=notes,
            )
        )

    created_by = acting_user.strip() if acting_user and str(acting_user).strip() else None

    pkg = PublishingPackagePayload(
        workspace_id=workspace_id,
        mode=mode.value,
        project_identity=project_identity,
        drawing_revision=drawing_revision,
        quantities=quantities,
        excluded_items=excluded_items,
        warnings=warnings,
        benchmark_status=benchmark_status,
        preflight_fingerprint=preflight_fingerprint,
        created_by=created_by,
    )
    pkg.payload_hash = pkg.compute_payload_hash()
    return pkg


def execute_jobhub_publishing(
    package: PublishingPackagePayload,
    bridge: Any,
    user_name: str,
    override_preflight_check: bool = False,
) -> Dict[str, Any]:
    """Execute publishing through the gate and persist to JobHub."""
    if not bridge:
        raise RuntimeError("JobHub bridge is unavailable")

    # Historical override flag was a commercial safety bypass: a blocked
    # source / wrong project / fabricated quantity could be written as Published.
    # Keep the parameter for callers but never allow a gate override.
    if override_preflight_check:
        raise RuntimeError(
            "Publishing gate override is prohibited: correct evidence and rerun preflight"
        )
    # 1. Evaluate Publishing Gate
    gate_result = validate_publishing_gate(package)
    if not gate_result.is_publishable:
        reasons = "; ".join(gate_result.blocking_reasons)
        raise RuntimeError(f"Publishing blocked by gate QA checks: {reasons}")

    # validate_publishing_gate deliberately tolerates an absent hash for
    # source-neutral diagnostics. A real JobHub write cannot: without the
    # complete original payload seal, its duplicate lookup degenerates to
    # SQL LIKE '%' and the customer package loses immutable identity.
    # Recheck the exact full evidence fingerprint at the final write boundary,
    # before opening SQLite or PostgreSQL or touching destination rows.
    if (
        type(package.payload_hash) is not str
        or len(package.payload_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in package.payload_hash)
        or package.payload_hash != gate_result.payload_hash
    ):
        raise RuntimeError(
            "JobHub publishing requires a sealed matching SHA-256 payload hash"
        )

    target_job_id = package.project_identity.target_jobhub_job_id
    if not target_job_id:
        raise RuntimeError("Target JobHub job ID is required to publish package")
    # ProjectIdentityPayload's Optional[int] hint is not runtime authority.
    # Boolean True, float 1.0 and string "1" can be coerced by SQLite into
    # real job row 1 (even when its job_no matches the intended project).
    # Refuse aliases before opening or locking any JobHub destination.
    if type(target_job_id) is not int or target_job_id <= 0:
        raise RuntimeError(
            "Target JobHub job ID must be an exact positive integer"
        )

    # Calculate aggregates
    total_qty_m2 = 0.0
    interior_m2 = 0.0
    exterior_m2 = 0.0
    total_cost = 0.0

    for q in package.quantities:
        total_cost += q.total_price
        if q.unit in ("m²", "m2", "sqm"):
            total_qty_m2 += q.quantity
            sec_lower = q.section.lower()
            # External WALLS must not be consumed by the generic "wall"
            # interior fallback. Contradictory explicit interior/exterior
            # section labels have no defensible category: retain the source
            # line but abstain from both customer summary buckets.
            explicit_interior = any(
                key in sec_lower for key in ("internal", "interior", "ceiling")
            )
            explicit_exterior = any(
                key in sec_lower for key in (
                    "external", "exterior", "facade", "façade",
                    "elevation", "soffit",
                )
            )
            if explicit_exterior and not explicit_interior:
                exterior_m2 += q.quantity
            elif explicit_interior and not explicit_exterior:
                interior_m2 += q.quantity
            elif not explicit_exterior and not explicit_interior and "wall" in sec_lower:
                # Preserve the historical generic wall bucket only where no
                # conflicting exterior or interior marker was provided.
                interior_m2 += q.quantity

    takeoff_no = f"PR-{package.project_identity.job_no}-{'PUB' if package.mode == PublishingMode.COMMERCIAL.value else 'DFT'}-{package.payload_hash[:8]}"
    status_label = "Published" if package.mode == PublishingMode.COMMERCIAL.value else "Draft"
    notes_str = (
        f"Mode: {package.mode.upper()} | Fingerprint: {package.preflight_fingerprint} | "
        f"Payload: {package.payload_hash} | Published by {user_name}"
    )

    # A previous bridge.query() checked job_no on a separate connection,
    # allowing another writer to change the destination before package INSERT.
    # Reserve a SQLite writer or lock the PostgreSQL job row before checking
    # its identity. Keep that lock through duplicate detection and BOTH writes.
    # A pre-existing SQLite caller transaction is not restarted.
    is_postgres = getattr(bridge, "kind", "sqlite") == "postgres"
    placeholder = "%s" if is_postgres else "?"
    with bridge.connect() as conn:
        cur = conn.cursor()
        if is_postgres:
            # psycopg2 starts a transaction on first statement; FOR UPDATE
            # prevents a competing job_no change until this transaction ends.
            cur.execute("SELECT job_no FROM jobs WHERE id=%s FOR UPDATE", (target_job_id,))
        else:
            if not conn.in_transaction:
                cur.execute("BEGIN IMMEDIATE")
            cur.execute("SELECT job_no FROM jobs WHERE id=?", (target_job_id,))

        # The numeric JobHub id alone is never physical project identity.
        target_row = cur.fetchone()
        if target_row is None:
            raise RuntimeError(f"Job #{target_job_id} does not exist in JobHub")
        target_no = target_row[0]
        original_no = package.project_identity.job_no
        if (
            type(target_no) is not str
            or not target_no.strip()
            or target_no.strip() != original_no.strip()
        ):
            raise RuntimeError(
                "JobHub target job number conflicts with PlanReader project identity"
            )

        # Check existing package duplicate
        cur.execute(
            f"SELECT id FROM painting_takeoff_packages WHERE job_id={placeholder} AND notes LIKE {placeholder}",
            (target_job_id, f"%{package.payload_hash}%"),
        )
        dup = cur.fetchone()
        if dup:
            raise RuntimeError(
                f"Duplicate package with payload hash {package.payload_hash[:12]}... already exists on JobHub (Package #{dup[0]})"
            )

        insert_pkg_sql = """
        INSERT INTO painting_takeoff_packages (
            job_id, takeoff_no, status, interior_m2, exterior_m2, total_hours, total_litres, created_by, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cur.execute(
            (insert_pkg_sql.replace("?", "%s") + " RETURNING id")
            if is_postgres else insert_pkg_sql,
            (
                target_job_id,
                takeoff_no,
                status_label,
                round(interior_m2, 2),
                round(exterior_m2, 2),
                0.0,
                0.0,
                user_name,
                notes_str,
            ),
        )
        pkg_id = cur.fetchone()[0] if is_postgres else cur.lastrowid

        # Insert lines
        insert_line_sql = """
        INSERT INTO painting_takeoff_package_lines (
            package_id, section, location, substrate, element, unit, quantity, rate, total_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for q in package.quantities:
            cur.execute(
                insert_line_sql.replace("?", "%s") if is_postgres else insert_line_sql,
                (
                    pkg_id,
                    q.section,
                    q.location,
                    q.substrate,
                    q.element,
                    q.unit,
                    # The full-evidence payload SHA seals the original measured
                    # quantity and client-supplied unit rate without rounding.
                    # The commercial gate explicitly allows sub-cent rates when
                    # the payable line total is cent-exact. Rounding either
                    # field here silently changes the customer JobHub line
                    # after its source and commercial evidence were sealed.
                    q.quantity,
                    q.rate,
                    round(q.total_price, 2),
                ),
            )

        conn.commit()

    return {
        "success": True,
        "published": True,
        "package_id": pkg_id,
        "takeoff_no": takeoff_no,
        "mode": package.mode,
        "status": status_label,
        "job_id": target_job_id,
        "total_lines": len(package.quantities),
        "total_cost": round(total_cost, 2),
        "interior_m2": round(interior_m2, 2),
        "exterior_m2": round(exterior_m2, 2),
        "preflight_fingerprint": package.preflight_fingerprint,
        "payload_hash": package.payload_hash,
    }
