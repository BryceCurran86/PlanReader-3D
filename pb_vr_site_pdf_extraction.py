"""Conservative native-PDF survey traverse reader. Review-only, not title survey authority.
Accepts explicitly numbered boundary legs in a site/boundary schedule; does not
guess ordering from PDF text order, infer a missing bearing or use building walls.
"""
from __future__ import annotations
import hashlib
import re
from pb_vr_site_boundary import BoundaryLeg, reconstruct_site_boundary

_TITLE = re.compile(r"\b(?:site plan|survey plan|boundary schedule|boundary traverse)\b", re.I)
_HEADING = re.compile(r"\b(?:boundary|lot)\s+(?:schedule|traverse|dimensions)\b", re.I)
_ROW = re.compile(r"^\s*(?:leg\s+)?(\d{1,3})\s*[.:)]?\s+(\d{1,3})(?:\s*[°º]\s*(\d{1,2})\s*['′]\s*(\d{1,2}(?:\.\d+)?)\s*[\"″]?|(?:\.\d+)?\s*(?:°|deg))\s+(\d+(?:\.\d+)?)\s*(m|mm)\s*$",re.I)
_DECIMAL = re.compile(r"^\s*(?:leg\s+)?(\d{1,3})\s*[.:)]?\s+(\d{1,3}(?:\.\d+)?)\s*(?:°|deg)\s+(\d+(?:\.\d+)?)\s*(m|mm)\s*$",re.I)

def extract_numbered_traverse(text: str) -> tuple[BoundaryLeg,...]:
    if not _TITLE.search(text) or not _HEADING.search(text):
        raise ValueError("site_boundary_schedule_not_identified")
    rows = {}
    for line in text.splitlines():
        d = _DECIMAL.fullmatch(line)
        if d:
            index,bearing,length,unit = d.groups()
            angle=float(bearing)
        else:
            m=_ROW.fullmatch(line)
            if not m or m.group(3) is None:
                continue
            index,degree,minute,second,length,unit=m.groups()
            if int(minute)>=60 or float(second)>=60:
                raise ValueError("site_boundary_invalid_dms")
            angle=int(degree)+int(minute)/60+float(second)/3600
        index=int(index)
        if index in rows:
            raise ValueError("site_boundary_duplicate_leg")
        rows[index]=BoundaryLeg(float(length)/(1000 if unit.lower()=="mm" else 1),angle)
    if not 3<=len(rows)<=100 or sorted(rows)!=list(range(1,len(rows)+1)):
        raise ValueError("site_boundary_missing_ordered_legs")
    return tuple(rows[i] for i in sorted(rows))

def extract_site_boundary_pdf(pdf_bytes: bytes, *, expected_sha256: str,
                              origin_xz: tuple[float,float], north_rotation_deg: float,
                              page_index: int|None=None) -> dict:
    """Read exact source bytes; registration must be supplied by a trusted caller.
    Returns only a review candidate, with source page and text provenance.
    """
    import fitz
    sha=hashlib.sha256(pdf_bytes).hexdigest()
    if sha!=expected_sha256.lower():
        raise ValueError("site_boundary_source_sha_mismatch")
    candidates=[]
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        pages=range(len(doc)) if page_index is None else (page_index,)
        for i in pages:
            if not 0<=i<len(doc):
                raise ValueError("site_boundary_page_out_of_range")
            text=doc[i].get_text("text",sort=True)
            try:
                legs=extract_numbered_traverse(text)
                result=reconstruct_site_boundary(legs,origin_xz=origin_xz,north_rotation_deg=north_rotation_deg)
            except ValueError:
                continue
            candidates.append({**result,"sourceSha256":sha,"pageIndex":i,
                               "method":"numbered_native_boundary_schedule",
                               "registration":"caller_supplied_review",
                               "legs":[{"lengthM":x.length_m,"bearingDeg":x.bearing_deg} for x in legs]})
    if len(candidates)!=1:
        raise ValueError("site_boundary_missing_or_ambiguous_candidate")
    return candidates[0]
