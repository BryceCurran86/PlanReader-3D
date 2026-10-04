#!/usr/bin/env python3
"""Shadow-only census for pb_raster_opening_existence_shadow.

Runs the raster physical-opening authority over every page (or chosen pages) of local
PDFs and reports, per page and per file: raster-layer availability, wall-band pieces,
candidate decisions, proven records, rejection reasons, runtime and peak memory.

It reads nothing but the PDFs it is given: no text, no benchmark truth, no expected
quantity. ``--expect-none TAG`` turns a file into a negative control: the run exits
non-zero if that file produces a single proven record. ``--montage TAG:PAGE`` writes
contact sheets (full render, gap boxed) so every proven record can be reviewed by eye.

``--simulate-scan DPI`` adds a generalisation pass: every page of every file is rendered
whole (vector content included) at that resolution, as if it had been scanned, and the
raster authority is run on those pixels. Vector-native plans then act as scans of
drawings whose openings are known to exist; ``--expect-none-simulated TAG`` gates the
files that must still produce nothing (BOQ text pages, hatched or double-line walls).

    python scripts/raster_opening_existence_shadow_diff.py \\
        --pdf plan=path/to/plan.pdf --pdf vector=path/to/vector_native.pdf \\
        --expect-none vector --simulate-scan 150 --out census.json \\
        --montage plan:3 --montage-dir sheets/
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

import pb_raster_opening_existence_shadow as shadow  # noqa: E402


def _peak_rss_mb() -> Optional[float]:
    """Peak resident set size of this process in MB (best effort, no extra deps)."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class _Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = _Counters()
            counters.cb = ctypes.sizeof(_Counters)
            ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_Counters),
                wintypes.DWORD,
            ]
            ctypes.windll.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return round(counters.PeakWorkingSetSize / (1024 * 1024), 1)
            return None
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)
    except Exception:  # noqa: BLE001 - memory is a courtesy figure
        return None


def _parse_pdf_args(values: list[str]) -> list[tuple[str, Path]]:
    pdfs: list[tuple[str, Path]] = []
    for value in values:
        tag, sep, path = value.partition("=")
        if not sep or not tag or not path:
            raise SystemExit(f"--pdf expects TAG=PATH, got {value!r}")
        pdfs.append((tag, Path(path)))
    return pdfs


def _page_selection(spec: Optional[str], page_count: int) -> list[int]:
    if not spec:
        return list(range(page_count))
    chosen: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            low, high = part.split("-", 1)
            chosen.update(range(int(low) - 1, int(high)))
        elif part:
            chosen.add(int(part) - 1)
    return sorted(i for i in chosen if 0 <= i < page_count)


def _simulated_scan(doc: Any, index: int, dpi: int) -> tuple[Any, int]:
    """Whole page (vector content included) as gray pixels, within the pixel budget."""
    import numpy as np

    page = doc[index]
    width_pt, height_pt = float(page.rect.width), float(page.rect.height)
    while width_pt * dpi / 72.0 * height_pt * dpi / 72.0 > shadow.MAX_PIXELS and dpi > shadow.MIN_DPI:
        dpi -= 20
    pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
    gray = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width).copy()
    return gray, dpi


def _analyse_simulated(doc: Any, index: int, dpi: int, sha: str) -> shadow.RasterOpeningExistenceResult:
    gray, used_dpi = _simulated_scan(doc, index, dpi)
    lineage = shadow.RasterLayerLineage(
        source_sha256=sha,
        page_number=index + 1,
        render_dpi=used_dpi,
        pixel_height=int(gray.shape[0]),
        pixel_width=int(gray.shape[1]),
        placements=(),
        render_spec="simulated_full_page_scan_v1",
        algorithm_version=shadow.RASTER_OPENING_ALGORITHM_VERSION,
        layer_id=f"simulated_scan:{sha[:16]}:{index + 1}:{used_dpi}",
    )
    return shadow.analyse_raster_layer(gray, dpi=used_dpi, lineage=lineage)


def _analyse_pdf(
    tag: str, path: Path, pages: Optional[str], simulate_dpi: Optional[int] = None
) -> dict[str, Any]:
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    rows: list[dict[str, Any]] = []
    reasons: collections.Counter[str] = collections.Counter()
    rejected: collections.Counter[str] = collections.Counter()
    evidence: collections.Counter[str] = collections.Counter()
    started = time.perf_counter()
    try:
        for index in _page_selection(pages, len(doc)):
            page_started = time.perf_counter()
            if simulate_dpi is None:
                result = shadow.propose_raster_opening_existence(doc, index, source_sha256=sha)
            else:
                result = _analyse_simulated(doc, index, simulate_dpi, sha)
            seconds = time.perf_counter() - page_started
            for code in result.reason_codes:
                reasons[code] += 1
            for decision in result.decisions:
                if decision.record is None:
                    for code in decision.reason_codes:
                        rejected[code] += 1
            for record in result.records:
                for item in record.symbol_evidence:
                    evidence[item.kind] += 1
            rows.append(
                {
                    "page": index + 1,
                    "status": result.status.value,
                    "reason_codes": list(result.reason_codes),
                    "wall_band_pieces": result.poche_piece_count,
                    "decisions": len(result.decisions),
                    "records": len(result.records),
                    "render_dpi": result.lineage.render_dpi if result.lineage else None,
                    "seconds": round(seconds, 3),
                    "record_ids": [r.record_id for r in result.records],
                    "gap_lengths_pt": [r.gap_length_pt for r in result.records],
                }
            )
    finally:
        doc.close()
    analysed = [r for r in rows if shadow.RASTER_NO_RASTER_LAYER not in r["reason_codes"]]
    return {
        "tag": tag,
        "mode": "native" if simulate_dpi is None else f"simulated_scan_{simulate_dpi}dpi",
        "source_sha256": sha,
        "pages": len(rows),
        "pages_with_raster_layer": len(analysed),
        "pages_with_records": sum(1 for r in rows if r["records"]),
        "records": sum(r["records"] for r in rows),
        "decisions": sum(r["decisions"] for r in rows),
        "page_reason_codes": dict(reasons),
        "rejected_decision_reasons": dict(rejected),
        "proven_evidence_kinds": dict(evidence),
        "seconds_total": round(time.perf_counter() - started, 2),
        "seconds_max_page": max((r["seconds"] for r in rows), default=0.0),
        "rows": rows,
    }


def _write_montage(
    path: Path, page_number: int, out_dir: Path, tag: str, simulate_dpi: Optional[int] = None
) -> list[Path]:
    import cv2
    import numpy as np

    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        if simulate_dpi is None:
            result = shadow.propose_raster_opening_existence(doc, page_number - 1, source_sha256=sha)
            if result.lineage is None:
                return []
            dpi = result.lineage.render_dpi
        else:
            result = _analyse_simulated(doc, page_number - 1, simulate_dpi, sha)
            dpi = result.lineage.render_dpi if result.lineage else simulate_dpi
        pixmap = doc[page_number - 1].get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        image = cv2.cvtColor(
            np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3).copy(),
            cv2.COLOR_RGB2BGR,
        )
    finally:
        doc.close()
    tile_w, tile_h = 560, 380
    tiles = []
    for index, decision in enumerate(result.decisions):
        x0, y0, x1, y1 = decision.gap_box_px
        pad = max(int(0.35 * max(x1 - x0, y1 - y0)), 45)
        cx0, cy0 = max(x0 - pad, 0), max(y0 - pad, 0)
        cx1, cy1 = min(x1 + pad, image.shape[1]), min(y1 + pad, image.shape[0])
        crop = image[cy0:cy1, cx0:cx1].copy()
        cv2.rectangle(crop, (x0 - cx0, y0 - cy0), (x1 - cx0, y1 - cy0), (0, 0, 255), 1)
        scale = min((tile_h - 18) / crop.shape[0], tile_w / crop.shape[1])
        crop = cv2.resize(
            crop,
            (max(int(crop.shape[1] * scale), 1), max(int(crop.shape[0] * scale), 1)),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST,
        )
        tile = np.full((tile_h, tile_w, 3), 255, np.uint8)
        tile[18 : 18 + crop.shape[0], : crop.shape[1]] = crop
        proven = decision.record is not None
        kinds = ",".join(item.kind for item in decision.symbol_evidence)
        reasons = ",".join(code.replace("raster_", "")[:22] for code in decision.reason_codes)
        label = f"#{index} {'PROVEN' if proven else 'REJECTED'} {decision.axis[0]} {decision.gap_box_px} {kinds} {reasons}"
        cv2.putText(tile, label[:96], (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 110, 0) if proven else (0, 0, 200), 1, cv2.LINE_AA)
        cv2.rectangle(tile, (0, 0), (tile_w - 1, tile_h - 1), (180, 180, 180), 1)
        tiles.append(tile)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    per_sheet = 6
    suffix = "" if simulate_dpi is None else f"_scan{simulate_dpi}"
    for start in range(0, len(tiles), per_sheet):
        chunk = tiles[start : start + per_sheet]
        while len(chunk) < per_sheet:
            chunk.append(np.full((tile_h, tile_w, 3), 255, np.uint8))
        sheet = np.vstack([np.hstack(chunk[0:2]), np.hstack(chunk[2:4]), np.hstack(chunk[4:6])])
        target = out_dir / f"{tag}_p{page_number}{suffix}_{start // per_sheet}.png"
        cv2.imwrite(str(target), sheet)
        written.append(target)
    return written


def _print_summary(prefix: str, summary: dict[str, Any], *, records: bool) -> None:
    print(
        f"{prefix}{summary['tag']}: pages={summary['pages']} raster_layer={summary['pages_with_raster_layer']} "
        f"pages_with_records={summary['pages_with_records']} records={summary['records']} "
        f"decisions={summary['decisions']} seconds={summary['seconds_total']} "
        f"max_page={summary['seconds_max_page']}"
    )
    print(f"  page reasons: {summary['page_reason_codes']}")
    print(f"  rejected decisions: {summary['rejected_decision_reasons']}")
    if summary["proven_evidence_kinds"]:
        print(f"  proven evidence: {summary['proven_evidence_kinds']}")
    if records:
        for row in summary["rows"]:
            if row["records"]:
                print(f"  page {row['page']}: {row['records']} records, gap_pt={row['gap_lengths_pt']}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", action="append", default=[], metavar="TAG=PATH", help="a PDF to analyse (repeatable)")
    parser.add_argument("--pages", action="append", default=[], metavar="TAG:SPEC", help="restrict a file to pages, e.g. plan:3,5-7")
    parser.add_argument("--expect-none", action="append", default=[], metavar="TAG", help="negative control: fail if TAG proves any record")
    parser.add_argument("--expect-none-simulated", action="append", default=[], metavar="TAG", help="negative control for the --simulate-scan pass")
    parser.add_argument("--simulate-scan", type=int, metavar="DPI", help="also analyse every page rendered whole at DPI, as if scanned")
    parser.add_argument("--montage", action="append", default=[], metavar="TAG:PAGE[:scan]", help="write review contact sheets for one page (':scan' uses the simulated scan)")
    parser.add_argument("--montage-dir", type=Path, default=Path("raster_opening_montage"))
    parser.add_argument("--records", action="store_true", help="print every page that proves records")
    parser.add_argument("--out", type=Path, help="write the full JSON census here")
    args = parser.parse_args(argv)

    pdfs = _parse_pdf_args(args.pdf)
    if not pdfs:
        parser.error("at least one --pdf TAG=PATH is required")
    page_specs = {tag: spec for tag, _, spec in (item.partition(":") for item in args.pages)}

    summaries = []
    for tag, path in pdfs:
        summary = _analyse_pdf(tag, path, page_specs.get(tag))
        summaries.append(summary)
        _print_summary("", summary, records=args.records)

    simulated = []
    if args.simulate_scan:
        for tag, path in pdfs:
            summary = _analyse_pdf(tag, path, page_specs.get(tag), simulate_dpi=args.simulate_scan)
            simulated.append(summary)
            _print_summary(f"[simulated scan {args.simulate_scan} dpi] ", summary, records=args.records)

    for spec in args.montage:
        tag, _, rest = spec.partition(":")
        page, _, mode = rest.partition(":")
        path = dict(pdfs).get(tag)
        if path is None or not page.isdigit():
            parser.error(f"--montage expects TAG:PAGE[:scan] for a given --pdf, got {spec!r}")
        simulate_dpi = args.simulate_scan if mode == "scan" and args.simulate_scan else None
        for written in _write_montage(path, int(page), args.montage_dir, tag, simulate_dpi):
            print(f"montage: {written}")

    peak = _peak_rss_mb()
    print(f"peak_rss_mb={peak}")
    report = {
        "algorithm_version": shadow.RASTER_OPENING_ALGORITHM_VERSION,
        "schema_version": shadow.RASTER_OPENING_SCHEMA_VERSION,
        "shadow_only": True,
        "peak_rss_mb": peak,
        "files": summaries,
        "simulated_scan_files": simulated,
    }
    if args.out:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    violations = [s["tag"] for s in summaries if s["tag"] in set(args.expect_none) and s["records"]]
    violations += [
        f"{s['tag']} (simulated scan)"
        for s in simulated
        if s["tag"] in set(args.expect_none_simulated) and s["records"]
    ]
    if violations:
        print(f"NEGATIVE CONTROL VIOLATED (records proven): {violations}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
