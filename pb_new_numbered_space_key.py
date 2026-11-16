"""Numbered plan-space legend evidence from original PDF, never floor authority.

If the architectural PDF has outlined-glyph labels instead of searchable
native text, the existing production OCR backend can read a numbered KEY.
The result is an automatic source-owned mapping of numbers to space *names*.
Room-wall geometry and paid quantities require independent physical evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Sequence


@dataclass(frozen=True)
class SpaceKeyEntry:
    number: int
    name: str
    semantic_role: str
    key_label_bbox_pdf_pts: tuple[float, float, float, float]
    number_markers_pdf_pts: tuple[tuple[float, float], ...] = ()
    number_marker_status: str = "not_located"
    physical_room_authenticated: bool = False
    area_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return dict(
            number=self.number, name=self.name, semantic_role=self.semantic_role,
            key_label_bbox_pdf_pts=list(self.key_label_bbox_pdf_pts),
            number_markers_pdf_pts=[list(x) for x in self.number_markers_pdf_pts],
            number_marker_status=self.number_marker_status,
            physical_room_authenticated=False, area_authorized=False,
        )


@dataclass(frozen=True)
class NumberedSpaceKeyResult:
    status: str
    reason: str
    page_index: int
    source_sha256: str
    entries: tuple[SpaceKeyEntry, ...] = ()
    matched_number_count: int = 0
    backend: str = "native_or_portable_ocr"
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return dict(
            status=self.status, reason=self.reason,
            page_index=self.page_index, source_sha256=self.source_sha256,
            entries=[e.to_dict() for e in self.entries],
            matched_number_count=self.matched_number_count,
            backend=self.backend, commercial_publishable=False,
        )


def _role(name: str) -> str:
    t = " " + re.sub(r"[^A-Z ]", " ", name.upper()) + " "
    if any(x in t for x in (
        " CARPORT ", " COURT ", " COURTYARD ", " PORTICO ",
        " PATIO ", " PORCH ", " TERRACE ", " VERANDAH ",
        " BALCONY ", " DRIVEWAY ", " DECK ", " PERGOLA ",
        " WATER TANK ", " GARDEN ",
    )):
        return "outdoor_or_nonroom_candidate"
    if any(x in t for x in (" SERVICES ", " METER ", " GARAGE ")):
        return "service_or_nonliving_candidate"
    return "named_interior_candidate_not_verified"


def _unpack_line(line: Any, origin: tuple[float, float] = (0., 0.)):
    """Extract visible OCR record, preserving source coordinates not indices."""
    if getattr(line, "bbox_pt", None) is None:
        return None
    text = str(getattr(line, "text", "")).strip().strip('"“”')
    confidence = getattr(line, "confidence", None)
    if not text or (confidence is not None and confidence < .68):
        return None
    a,b,c,d = map(float, line.bbox_pt)
    if not all(math.isfinite(v) for v in (a,b,c,d)) or a>=c or b>=d:
        return None
    return dict(
        text=text, confidence=confidence,
        bbox=(a+origin[0],b+origin[1],c+origin[0],d+origin[1]),
        x=a+origin[0],cy=(b+d)/2+origin[1],
    )


def parse_numbered_key(
    cropped_ocr_lines: Sequence[Any],
    fullpage_ocr_lines: Sequence[Any],
    *,
    anchor_bbox_pdf_pts: tuple[float, float, float, float],
    crop_origin_pdf_pts: tuple[float, float],
    source_sha256: str,
    page_index: int,
) -> NumberedSpaceKeyResult:
    """Generic numbered key: one number and one name on each source row."""
    anchor_y = anchor_bbox_pdf_pts[1]
    rows = [r for line in cropped_ocr_lines
            if (r:=_unpack_line(line,crop_origin_pdf_pts)) is not None]
    numbers = []
    for item in rows:
        if item["cy"] <= anchor_y + 8:
            continue
        if not re.fullmatch(r"[1-9][0-9]?", item["text"]):
            continue
        number=int(item["text"])
        if number>99:
            continue
        numbers.append((number,item))
    pairs={}
    for number, num_item in numbers:
        nbox = num_item["bbox"]
        near = [
            label for label in rows
            if label["x"] > nbox[2]+1.
            and label["x"] <= nbox[2]+180.
            and abs(label["cy"]-num_item["cy"]) <= max(4.2,(nbox[3]-nbox[1])*.50)
            and len(re.findall(r"[A-Za-z]",label["text"]))>=2
            and not re.fullmatch(r"[0-9.]+",label["text"])
        ]
        if not near:
            continue
        near.sort(key=lambda x:(x["x"],abs(x["cy"]-num_item["cy"])))
        name=near[0]
        if number in pairs:
            # Two conflicting names for the same numbered source key:
            # fail closed rather than silently choosing a source view.
            if pairs[number]["text"]!=name["text"]:
                return NumberedSpaceKeyResult(
                    "ABSTAINED", "numbered_key_duplicate_number_conflict",
                    page_index, source_sha256,
                )
        pairs[number]=name
    if len(pairs)<3:
        return NumberedSpaceKeyResult(
            "ABSTAINED", "numbered_key_insufficient_source_rows",
            page_index, source_sha256,
        )
    # A numbered room key is sequential. Three unrelated numeric annotations
    # aligned by coincidence should not become a semantic room schedule.
    nums=sorted(pairs)
    contiguous=max(
        (j-i+1 for i in range(len(nums)) for j in range(i,len(nums))
         if nums[j]-nums[i]==j-i),
        default=0,
    )
    if contiguous<3:
        return NumberedSpaceKeyResult(
            "ABSTAINED", "numbered_key_sequence_not_authenticated",
            page_index, source_sha256,
        )
    full=[r for line in fullpage_ocr_lines if (r:=_unpack_line(line)) is not None]
    xlo=min(x["bbox"][0] for _,x in numbers)-4.
    xhi=max(x["bbox"][2] for _,x in numbers)+200.
    ylo=anchor_y-5.
    yhi=max(x["bbox"][3] for _,x in numbers)+6.
    entries=[]
    matched=0
    for number in nums:
        name=pairs[number]
        markers=[]
        for label in full:
            if label["text"] != str(number):
                continue
            px=label["bbox"]
            if xlo<=label["x"]<=xhi and ylo<=label["cy"]<=yhi:
                continue
            center=((px[0]+px[2])/2,(px[1]+px[3])/2)
            if all(math.hypot(center[0]-x,center[1]-y)>4. for x,y in markers):
                markers.append(tuple(round(t,3) for t in center))
        status=("unique_candidate" if len(markers)==1 else
                "ambiguous_markers" if len(markers)>1 else "not_located")
        matched+=status=="unique_candidate"
        entries.append(SpaceKeyEntry(
            number=number,name=name["text"].strip(),
            semantic_role=_role(name["text"]),
            key_label_bbox_pdf_pts=tuple(round(x,3) for x in name["bbox"]),
            number_markers_pdf_pts=tuple(markers),number_marker_status=status,
        ))
    return NumberedSpaceKeyResult(
        "CANDIDATE", "numbered_source_key_requires_physical_room_boundary",
        page_index, source_sha256, tuple(entries),matched,
    )


def _has_readable_native_room_labels(words: Sequence[Any]) -> bool:
    """Avoid auxiliary full-page OCR when room names already print as native text.

    Evidence threshold is generic across plans: many separately printed
    recognisable spaces in several categories, not a fixture/project hash.
    This does NOT authenticate a room or any area.
    """
    if len(words) < 100:
        return False
    types = {
        "LIVING": "living", "DINING": "dining", "MEALS": "dining",
        "BED": "bed", "BEDROOM": "bed", "MEDIA": "media",
        "KITCHEN": "kitchen", "KIT": "kitchen",
        "BATH": "bath", "BATHROOM": "bath", "WC": "bath",
        "ENS": "bath", "ENSUITE": "bath",
        "GARAGE": "garage", "OFFICE": "office", "STUDY": "office",
        "LAUNDRY": "laundry", "LDY": "laundry",
        "ENTRY": "entry", "HALL": "hall",
        "WIR": "closet", "WIP": "closet", "STORE": "store",
    }
    labels = []
    for word in words:
        if not isinstance(word, (tuple, list)) or len(word) < 5:
            continue
        name = re.sub(r"[^A-Z0-9]", "", str(word[4]).upper())
        if name in ("KEY", "ROOMKEY", "SPACEKEY", "AREAKEY"):
            return False  # Explicit key may still need OCR.
        category = types.get(name)
        if category is None and re.fullmatch(r"BED(?:ROOM)?[0-9]+", name):
            category = "bed"
        if category is not None:
            labels.append(category)
    return len(labels) >= 8 and len(set(labels)) >= 4


def detect_numbered_space_key(page: Any, *,
                              page_index: int, source_sha256: str,
                              max_ocr_px: int = 2700,
                              force_ocr: bool = False) -> NumberedSpaceKeyResult:
    """Automatic on each original floor page, source-OCR only if necessary."""
    import fitz
    from PIL import Image
    from pb_portable_raster_ocr_authority import RapidOCRBackend
    if type(source_sha256) is not str or len(source_sha256)!=64:
        raise ValueError("room_key_source_digest_required")
    if hashlib.sha256(b"").hexdigest()==source_sha256:
        return NumberedSpaceKeyResult(
            "ABSTAINED","source_pdf_empty",page_index,source_sha256,
        )
    native=page.get_text("words")
    drawings=page.get_drawings()
    # Empty/primitive-sparse test sheets and genuinely blank originals have
    # no outlined glyph key to OCR. Do not launch a heavyweight OCR backend
    # for a handful of physical wall rectangles.
    if not native and sum(len(row.get("items", ())) for row in drawings) < 75:
        return NumberedSpaceKeyResult(
            "ABSTAINED", "numbered_key_no_source_printed_glyph_evidence",
            page_index, source_sha256,
        )
    # Thousands of CAD vector paths do NOT by themselves justify a 2,700px
    # full-page OCR scan. On native-text floor plans with printed room names,
    # the optional numbered-key scan adds no room wall authority and can
    # dominate preview time. Preserve OCR for outlined glyphs (no readable
    # native room labels) and allow explicit forced diagnostic use.
    readable_native_rooms = _has_readable_native_room_labels(native)
    scan_needed = (
        force_ocr or (
            (len(native) < 35 or len(drawings) > 3500)
            and not readable_native_rooms
        )
    )
    if not scan_needed:
        reason = (
            "native_room_names_visible_numbered_key_ocr_deferred"
            if readable_native_rooms and not force_ocr
            else "native_text_page_no_numbered_key_ocr_not_required"
        )
        return NumberedSpaceKeyResult(
            "ABSTAINED", reason, page_index, source_sha256,
        )
    backend=RapidOCRBackend()
    if not backend.is_available():
        return NumberedSpaceKeyResult(
            "ABSTAINED","source_numbered_key_ocr_backend_unavailable",
            page_index,source_sha256,
        )
    scale=min(160/72,max_ocr_px/max(float(page.rect.width),float(page.rect.height)))
    dpi=int(round(scale*72))
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),
                        alpha=False,colorspace=fitz.csRGB)
    image=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
    full=backend.extract_lines(image,dpi=dpi)
    anchors=[]
    for line in full:
        rec=_unpack_line(line)
        if rec is not None and re.fullmatch(
            r"(?:ROOM |AREA |SPACE )?(?:KEY|LEGEND)(?: TO ROOMS)?",
            rec["text"].upper().strip(),
        ):
            anchors.append(rec)
    if not anchors:
        return NumberedSpaceKeyResult(
            "ABSTAINED","source_numbered_key_anchor_not_found",
            page_index,source_sha256,
        )
    # Prefer the explicit KEY over a title-block's unrelated LEGEND symbol.
    anchors.sort(key=lambda a:(
        not a["text"].upper().endswith("KEY"),
        a["bbox"][1],a["bbox"][0],
    ))
    for anchor in anchors[:4]:
        x0,y0,x1,y1=anchor["bbox"]
        rect=fitz.Rect(
            max(0.,x0-8.),max(0.,y0-3.),
            min(page.rect.width,x0+max(120.,min(220.,page.rect.width*.25))),
            min(page.rect.height,y0+min(280.,page.rect.height*.40)),
        )
        if rect.is_empty:
            continue
        # The high-DPI source crop is based on the OCR-located KEY, not any
        # hard-coded plan/project coordinates, page numbers, or number list.
        dpi2=300
        pix2=page.get_pixmap(matrix=fitz.Matrix(dpi2/72,dpi2/72),
                             clip=rect,alpha=False,colorspace=fitz.csRGB)
        image2=Image.frombytes("RGB",(pix2.width,pix2.height),pix2.samples)
        lines=backend.extract_lines(image2,dpi=dpi2)
        got=parse_numbered_key(
            lines,full,anchor_bbox_pdf_pts=tuple(anchor["bbox"]),
            crop_origin_pdf_pts=(rect.x0,rect.y0),
            source_sha256=source_sha256,page_index=page_index,
        )
        if got.status=="CANDIDATE":
            return got
    return NumberedSpaceKeyResult(
        "ABSTAINED","source_numbered_key_not_source_pairable",
        page_index,source_sha256,
    )
