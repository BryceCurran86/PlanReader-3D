"""COUNTERFACTUAL HARNESS, NOT A REPOSITORY CHANGE: what does the unchanged source-stage chain do on a page once the structural-ink
typed negatives are withheld from the wall-topology input?

The live wall authority stops a page whose wall-topology input (after its motif filter) exceeds ``MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS``
(20,000). This harness leaves that cap, every authority and every threshold untouched. In a child process only, it wraps the
authority's own motif filter so that the primitives ``classify_structural_wall_ink`` types ``NOT_WALL_INK`` are not passed on, then runs
``tools/diag_gptmax_source_authority_stages.py`` unchanged and keeps counts only. Nothing is written to the checkout, and no result
of this harness is a measurement authority: it is the evidence an authority-promotion review would need, nothing more.

usage:  python run_cap_counterfactual.py REPO PDF OUTDIR PAGES [MODES]
        REPO   a checkout of the repository (its modules are imported from there)
        PDF    the original PDF (read-only)          OUTDIR  where per-page outputs and summary.json go
        PAGES  comma separated 1-based pages         MODES   comma separated, default baseline,negatives_withheld
"""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import subprocess
import sys
import time


def child(repo: str, pdf: str, page: int, mode: str, out: str) -> None:
    sys.dont_write_bytecode = True
    sys.path.insert(0, repo)
    if mode == "negatives_withheld":
        import fitz

        import pb_physical_wall_candidate_authority as authority
        from pb_structural_wall_ink_shadow import NOT_WALL_INK, classify_structural_wall_ink
        from pb_vector_geometry_v130 import extract_native_page

        native_page = fitz.open(pdf)[page - 1]
        segments = extract_native_page(native_page)["segments"]
        report = classify_structural_wall_ink(segments, page_width=native_page.rect.width, page_height=native_page.rect.height)
        withheld = set(report.ids_with(NOT_WALL_INK))
        original = authority._filter_repeated_non_physical_drafting_primitives

        def without_typed_negatives(rows, **kwargs):
            kept = tuple(s for s in original(rows, **kwargs) if str(s.get("id")) not in withheld)
            print("wall topology input", len(kept), "of", len(rows))
            return kept

        authority._filter_repeated_non_physical_drafting_primitives = without_typed_negatives
    sys.argv = ["diag_gptmax_source_authority_stages.py", "--pdf", pdf, "--page-id", str(page), "--output", out]
    runpy.run_path(repo + "/tools/diag_gptmax_source_authority_stages.py", run_name="__main__")


def parent(repo: str, pdf: str, outdir: Path, pages: list, modes: list) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for page in pages:
        for mode in modes:
            out_json, out_log = outdir / f"p{page}_{mode}.json", outdir / f"p{page}_{mode}.out"
            started = time.time()
            with open(out_log, "w", encoding="utf-8") as log:
                code = subprocess.run([sys.executable, __file__, "--child", repo, pdf, str(page), mode, str(out_json)],
                                      stdout=log, stderr=subprocess.STDOUT, timeout=2400).returncode
            text = out_log.read_text(encoding="utf-8", errors="replace")
            row = {"page": page, "mode": mode, "exit_code": code, "seconds": round(time.time() - started, 1)}
            for line in text.splitlines():
                if line.startswith("wall topology input"):
                    row["wall_topology_input"] = line
                if line.startswith("{") and "physical_existence_claims" in line:
                    summary = json.loads(line)
                    row["physical_existence_claims"] = summary.get("physical_existence_claims")
                    row["authenticated_hosts"] = summary.get("authenticated_hosts")
            if "LiveWallOpeningScopeComplexityExceeded" in text:
                row["blocker"] = "physical_wall_candidate_scope_complexity_exceeded"
            if out_json.exists() and out_json.stat().st_size:
                data = json.loads(out_json.read_text(encoding="utf-8"))
                scope = (data.get("source_owned_wall_scopes") or [{}])[0]
                faces = ((data.get("source_room_face_scopes") or [{}])[0]).get("result") or {}
                row["wall_scope"] = {"status": scope.get("status"), "scope_complete": scope.get("scope_complete"),
                                     "wall_candidate_records": len(scope.get("records") or [])}
                row["room_face_scope"] = {"reason_codes": faces.get("reason_codes"), "face_records": len(faces.get("records") or []),
                                          "abstained_faces": len(faces.get("abstained_faces") or [])}
            rows.append(row)
            (outdir / "summary.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
            print(page, mode, code, row["seconds"], row.get("blocker", ""), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], sys.argv[6])
    else:
        repo_, pdf_, outdir_, pages_ = sys.argv[1], sys.argv[2], Path(sys.argv[3]), [int(p) for p in sys.argv[4].split(",")]
        parent(repo_, pdf_, outdir_, pages_, sys.argv[5].split(",") if len(sys.argv) > 5 else ["baseline", "negatives_withheld"])
