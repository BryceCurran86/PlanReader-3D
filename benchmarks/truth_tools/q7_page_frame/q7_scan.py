"""Q7 real-source rotation inventory (scratch tool, NOT part of the repo).

Metadata only: hashes the file, then reads each page dictionary's own and
inherited /Rotate straight from the PDF object graph (independent of
pb_page_frame_shadow). It never reads page content.

Approved-source guard: a file is opened as a PDF only if its SHA-256 equals a
hash recorded in a *development* benchmarks/public_tenders/*/download_manifest.json.
Anything else (including any frozen-holdout file) is REJECTED before parsing.
`--synthetic-self-test` bypasses the guard and stamps the output
source_class="synthetic" so a self-test can never be mistaken for Q7 evidence.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys

import fitz

REPO = "/home/user/PlanReader-3D"
ORTHOGONAL = {0, 90, 180, 270}


def approved_hashes() -> dict:
    out = {}
    for p in sorted(glob.glob(os.path.join(REPO, "benchmarks/public_tenders/*/download_manifest.json"))):
        if "frozen_holdout" in p:
            continue
        d = json.load(open(p))
        for doc in d.get("documents", []):
            h = doc.get("sha256")
            if h:
                out.setdefault(h, []).append(
                    {"benchmark_id": d.get("benchmark_id"), "role": doc.get("role"), "filename": doc.get("filename")}
                )
    return out


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _own_rotate(doc, xref):
    kind, val = doc.xref_get_key(xref, "Rotate")
    return None if kind == "null" else (kind, val)


def raw_rotate(doc, page_xref: int):
    """Own /Rotate, else nearest ancestor's via /Parent. Returns (effective, source, raw)."""
    seen, xref, depth = set(), page_xref, 0
    while xref and xref not in seen and depth < 64:
        seen.add(xref)
        got = _own_rotate(doc, xref)
        if got is not None:
            kind, val = got
            where = "own" if depth == 0 else f"inherited_depth_{depth}"
            if kind == "int":
                n = int(val)
                # PDF allows any multiple of 90 (negatives included); normalise those only.
                return (n % 360 if n % 90 == 0 else n), where, val
            return None, where, f"{kind}:{val}"  # non-integer: unresolved, flagged by caller
        pk, pv = doc.xref_get_key(xref, "Parent")
        if pk != "xref":
            break
        xref = int(pv.split()[0])
        depth += 1
    return 0, "absent", None


def scan_pdf(path: str) -> dict:
    doc = fitz.open(path)
    try:
        pages = []
        for i in range(doc.page_count):
            page = doc[i]
            eff, src, raw = raw_rotate(doc, doc.page_xref(i))
            entry = {
                "page_no": i + 1,
                "raw_rotate": raw,
                "rotate_source": src,
                "effective_rotate": eff,
                "pymupdf_rotation": page.rotation,
                "orthogonal": eff in ORTHOGONAL if eff is not None else False,
                "agrees_with_pymupdf": (eff is not None and (eff % 360) == page.rotation),
                "mediabox": [round(v, 4) for v in page.mediabox],
                "cropbox": [round(v, 4) for v in page.cropbox],
                "rect_wh": [round(page.rect.width, 4), round(page.rect.height, 4)],
            }
            pages.append(entry)
        by_rot = {}
        for e in pages:
            key = str(e["effective_rotate"]) if e["effective_rotate"] is not None else "unresolved"
            by_rot.setdefault(key, []).append(e["page_no"])
        return {
            "page_count": doc.page_count,
            "rotation_histogram": {k: len(v) for k, v in sorted(by_rot.items())},
            "pages_by_effective_rotation": {k: v for k, v in sorted(by_rot.items())},
            "disagreements_with_pymupdf": [e["page_no"] for e in pages if not e["agrees_with_pymupdf"]],
            "pages": pages,
        }
    finally:
        doc.close()


def expand(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                # never descend into a holdout directory
                dirs[:] = [d for d in dirs if "frozen_holdout" not in d.lower()]
                for f in sorted(files):
                    if f.lower().endswith(".pdf"):
                        yield os.path.join(root, f)
        else:
            yield p


def refused(path: str, excludes) -> str:
    """Path-based refusal, decided BEFORE the file is opened, hashed or parsed."""
    low = os.path.abspath(path).lower()
    if "frozen_holdout" in low:
        return "REFUSED_frozen_holdout_path"
    for pat in excludes:
        if pat.lower() in low:
            return f"REFUSED_user_exclude:{pat}"
    return ""


def census_row(scan: dict) -> dict:
    h = scan["rotation_histogram"]
    orth = sum(h.get(k, 0) for k in ("0", "90", "180", "270"))
    return {
        "pages": scan["page_count"],
        "rot0": h.get("0", 0),
        "rot90": h.get("90", 0),
        "rot180": h.get("180", 0),
        "rot270": h.get("270", 0),
        "non_orthogonal_or_unresolved": scan["page_count"] - orth,
        "pymupdf_disagreements": len(scan["disagreements_with_pymupdf"]),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="PDF files and/or directories (searched recursively)")
    ap.add_argument("--any-pdf", action="store_true",
                    help="REAL user-supplied plans: no benchmark-manifest requirement. Holdout paths and --exclude still refused.")
    ap.add_argument("--exclude", action="append", default=[],
                    help="case-insensitive path substring to refuse (repeatable). REQUIRED for any copy of the sealed holdout outside benchmarks/frozen_holdout.")
    ap.add_argument("--synthetic-self-test", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    allow = approved_hashes()
    if args.synthetic_self_test:
        cls = "synthetic"
    elif args.any_pdf:
        cls = "real_user_supplied"
    else:
        cls = "real_approved_dev_manifest"
    report = {
        "source_class": cls,
        "metadata_only": True,
        "note": "holdout exclusion is path-based; pass --exclude for any copy of the sealed holdout stored elsewhere",
        "files": [],
    }
    for path in expand(args.paths):
        rec = {"path": path}
        why = refused(path, args.exclude)
        if why:
            rec["status"] = why  # not opened, not hashed
            report["files"].append(rec)
            continue
        rec.update(bytes=os.path.getsize(path), sha256=sha256_file(path))
        match = allow.get(rec["sha256"])
        if match is None and cls == "real_approved_dev_manifest":
            rec["status"] = "REJECTED_not_in_approved_development_manifest"
        else:
            rec["status"] = {"synthetic": "SYNTHETIC_SELF_TEST", "real_user_supplied": "REAL_USER_SUPPLIED"}.get(cls, "APPROVED_DEV_SOURCE")
            rec["manifest_match"] = match
            try:
                rec["scan"] = scan_pdf(path)
                rec["census"] = census_row(rec["scan"])
            except Exception as exc:  # report, never crash the census
                rec["status"] += f"|SCAN_ERROR:{type(exc).__name__}"
        report["files"].append(rec)
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.out:
        open(args.out, "w").write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
