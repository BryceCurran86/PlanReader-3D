"""Producer-owned bridge from immutable raster OCR to TagObservation.

Item 35 / PR 2.

The trust boundary is deliberately narrow:

* callers provide only a PortableRasterOCRSelector (an address) plus an
  already-authenticated floor-plan viewport decision;
* the source page raster is rendered by SourceObservationProducer from the
  exact immutable PDF bytes it previously ingested;
* the native_pdf_page parent and source partition are resolved internally;
* OCR is executed inside this producer with an exact production backend type;
* caller-authored OCRLine values, page images, parent observation ids and
  source partition ids are not accepted by the production API.

The output remains only TagObservation evidence.  It does not establish a
physical opening, identity, schedule binding, completeness, or a commercial
count; those propositions remain owned by their existing authorities.
"""
from __future__ import annotations

import io
import math
from typing import List, Optional, Sequence, Tuple

from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import (
    MockOCRBackend,
    NullOCRBackend,
    OCRLine,
    PortableRasterOCRSelector,
    RapidOCRBackend,
    RasterOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_opening_candidate_authority import (
    AuthenticatedViewportDecision,
    TagObservation,
)

__all__ = [
    "OCR_TAG_OBSERVATION_KIND",
    "OCR_TAG_OBSERVATION_ORIGIN_KIND",
    "RasterOCRTagObservationProducer",
    "publish_raster_ocr_as_tag_observations",
]

OCR_TAG_OBSERVATION_KIND = "ocr_text"
OCR_TAG_OBSERVATION_ORIGIN_KIND = "ocr"

_BRIDGE_PRODUCER_SEAL = object()
_PRODUCTION_BACKEND_TYPES = (
    NullOCRBackend,
    TesseractOCRBackend,
    WinOCRBackend,
    RapidOCRBackend,
)


def _choose_environment_backend() -> RasterOCRBackend:
    """Use the same deterministic production preference as the OCR authority."""
    rapid = RapidOCRBackend()
    if rapid.is_available():
        return rapid
    tess = TesseractOCRBackend()
    if tess.is_available():
        return tess
    win = WinOCRBackend()
    if win.is_available():
        return win
    return NullOCRBackend()


def _normalized_text(value: str) -> str:
    return str(value or "").strip().upper()


def _bbox_area(box: Tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = box
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _bbox_iou(
    a: Tuple[float, float, float, float],
    b: Tuple[float, float, float, float],
) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if intersection <= 0.0:
        return 0.0
    union = _bbox_area(a) + _bbox_area(b) - intersection
    return intersection / union if union > 0.0 else 0.0


def _dedupe_ocr_lines(lines: Sequence[OCRLine]) -> List[OCRLine]:
    """Collapse repeat detections only when same-text boxes substantially overlap.

    The threshold is dimensionless IoU, not a fixed page/pixel distance. Distinct
    nearby marks that do not actually overlap are therefore preserved.
    """
    ordered = sorted(
        enumerate(lines),
        key=lambda item: (
            -(item[1].confidence if item[1].confidence is not None else -1.0),
            item[0],
        ),
    )
    kept: List[OCRLine] = []
    for _, line in ordered:
        if line.bbox_pt is None:
            continue
        text_norm = _normalized_text(line.text)
        if not text_norm:
            continue
        if any(
            _normalized_text(existing.text) == text_norm
            and existing.bbox_pt is not None
            and _bbox_iou(line.bbox_pt, existing.bbox_pt) >= 0.5
            for existing in kept
        ):
            continue
        kept.append(line)
    return kept


def _box_within(
    inner: Tuple[float, float, float, float],
    outer: Tuple[float, float, float, float],
) -> bool:
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    return (
        ix1 > ix0
        and iy1 > iy0
        and ix0 >= ox0
        and iy0 >= oy0
        and ix1 <= ox1
        and iy1 <= oy1
    )


class RasterOCRTagObservationProducer:
    """Trusted bridge producer.

    Production construction accepts only exact built-in production OCR backend
    types.  Tests have a separate exact-Mock factory so a mocked OCR engine can
    exercise the bridge without creating a production path for caller-authored
    OCRLine values.
    """

    def __init__(
        self,
        *,
        source_producer: SourceObservationProducer,
        backend: RasterOCRBackend,
        dpi: int,
        allow_test_backend: bool,
        _seal: object = None,
    ) -> None:
        if _seal is not _BRIDGE_PRODUCER_SEAL:
            raise TypeError(
                "RasterOCRTagObservationProducer must be obtained from create() "
                "or create_for_tests()"
            )
        if type(source_producer) is not SourceObservationProducer:
            raise TypeError("source_producer must be exact SourceObservationProducer")
        if allow_test_backend:
            if type(backend) is not MockOCRBackend:
                raise TypeError("create_for_tests requires exact MockOCRBackend")
        elif type(backend) not in _PRODUCTION_BACKEND_TYPES:
            raise TypeError(
                "production backend must be exact RapidOCRBackend, "
                "TesseractOCRBackend, WinOCRBackend, or NullOCRBackend"
            )
        dpi_value = int(dpi)
        if dpi_value <= 0:
            raise ValueError("dpi must be a positive integer")

        self._source_producer = source_producer
        self._authority = source_producer.authority()
        self._backend = backend
        self._dpi = dpi_value

    @classmethod
    def create(
        cls,
        *,
        source_producer: SourceObservationProducer,
        backend: Optional[RasterOCRBackend] = None,
        dpi: int = 300,
    ) -> "RasterOCRTagObservationProducer":
        active = backend if backend is not None else _choose_environment_backend()
        return cls(
            source_producer=source_producer,
            backend=active,
            dpi=dpi,
            allow_test_backend=False,
            _seal=_BRIDGE_PRODUCER_SEAL,
        )

    @classmethod
    def create_for_tests(
        cls,
        *,
        source_producer: SourceObservationProducer,
        backend: MockOCRBackend,
        dpi: int = 300,
    ) -> "RasterOCRTagObservationProducer":
        return cls(
            source_producer=source_producer,
            backend=backend,
            dpi=dpi,
            allow_test_backend=True,
            _seal=_BRIDGE_PRODUCER_SEAL,
        )

    def _scope_matches(
        self,
        selector: PortableRasterOCRSelector,
        viewport_decision: AuthenticatedViewportDecision,
    ) -> bool:
        if type(selector) is not PortableRasterOCRSelector:
            raise TypeError("selector must be PortableRasterOCRSelector")
        if type(viewport_decision) is not AuthenticatedViewportDecision:
            raise TypeError(
                "viewport_decision must be AuthenticatedViewportDecision"
            )
        if viewport_decision.status != EvidenceResolutionStatus.CORROBORATED:
            return False
        decision_selector = viewport_decision.selector
        if decision_selector is None or selector.viewport_id is None:
            return False
        if (
            decision_selector.document_id != selector.document_id
            or decision_selector.revision_id != selector.revision_id
            or decision_selector.source_sha256 != selector.source_sha256
            or decision_selector.snapshot_id != selector.snapshot_id
            or decision_selector.viewport_id != selector.viewport_id
            or viewport_decision.viewport.view_id != selector.viewport_id
        ):
            return False
        if str(viewport_decision.viewport.page_number) != selector.page_id:
            return False
        return True

    def _run_ocr(
        self,
        *,
        png_bytes: bytes,
        page_geometry: Tuple[float, float],
        selector: PortableRasterOCRSelector,
        viewport_decision: AuthenticatedViewportDecision,
    ) -> Tuple[OCRLine, ...]:
        if not self._backend.is_available():
            return ()

        try:
            image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        except Exception:
            return ()

        page_width_pt, page_height_pt = page_geometry
        page_bbox = (0.0, 0.0, float(page_width_pt), float(page_height_pt))
        view_bbox = tuple(float(v) for v in viewport_decision.viewport.bounding_box)
        if len(view_bbox) != 4 or not _box_within(view_bbox, page_bbox):
            return ()

        target_bbox = (
            tuple(float(v) for v in selector.target_region_pt)
            if selector.target_region_pt is not None
            else view_bbox
        )
        if len(target_bbox) != 4 or not _box_within(target_bbox, view_bbox):
            return ()

        pt_to_px = float(self._dpi) / 72.0
        x0, y0, x1, y1 = target_bbox
        crop_px = (
            max(0, int(math.floor(x0 * pt_to_px))),
            max(0, int(math.floor(y0 * pt_to_px))),
            min(image.width, int(math.ceil(x1 * pt_to_px))),
            min(image.height, int(math.ceil(y1 * pt_to_px))),
        )
        if crop_px[2] <= crop_px[0] or crop_px[3] <= crop_px[1]:
            return ()
        target = image.crop(crop_px)
        offset_x_px, offset_y_px = crop_px[0], crop_px[1]

        try:
            raw_lines = self._backend.extract_lines(target, dpi=self._dpi)
        except Exception:
            return ()

        px_to_pt = 72.0 / float(self._dpi)
        normalized: List[OCRLine] = []
        for line in raw_lines:
            text = str(line.text or "").strip()
            if not text:
                continue
            try:
                lx0, ly0, lx1, ly1 = (float(v) for v in line.bbox_px)
            except Exception:
                continue
            if not all(math.isfinite(v) for v in (lx0, ly0, lx1, ly1)):
                continue
            if (
                lx0 < 0.0
                or ly0 < 0.0
                or lx1 <= lx0
                or ly1 <= ly0
                or lx1 > float(target.width)
                or ly1 > float(target.height)
            ):
                continue

            gx0 = (lx0 + offset_x_px) * px_to_pt
            gy0 = (ly0 + offset_y_px) * px_to_pt
            gx1 = (lx1 + offset_x_px) * px_to_pt
            gy1 = (ly1 + offset_y_px) * px_to_pt
            bbox_pt = (
                round(gx0, 4),
                round(gy0, 4),
                round(gx1, 4),
                round(gy1, 4),
            )
            if not _box_within(bbox_pt, page_bbox):
                continue
            normalized.append(
                OCRLine(
                    text=text,
                    confidence=line.confidence,
                    bbox_px=(
                        lx0 + offset_x_px,
                        ly0 + offset_y_px,
                        lx1 + offset_x_px,
                        ly1 + offset_y_px,
                    ),
                    bbox_pt=bbox_pt,
                )
            )

        return tuple(_dedupe_ocr_lines(normalized))

    def publish(
        self,
        *,
        selector: PortableRasterOCRSelector,
        viewport_decision: AuthenticatedViewportDecision,
    ) -> Tuple[Tuple[TagObservation, ...], str]:
        """Run OCR on immutable source pixels and publish authenticated tags.

        Scope mismatch, unavailable OCR, empty OCR, or malformed backend output
        fail closed to no tags and the unchanged input snapshot.
        """
        if not self._scope_matches(selector, viewport_decision):
            return (), selector.snapshot_id

        try:
            png_bytes, page_parent = self._source_producer.render_native_page_png(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                dpi=self._dpi,
            )
        except (ValueError, RuntimeError):
            return (), selector.snapshot_id

        if len(page_parent.geometry) < 2:
            return (), selector.snapshot_id
        page_geometry = (float(page_parent.geometry[0]), float(page_parent.geometry[1]))
        lines = self._run_ocr(
            png_bytes=png_bytes,
            page_geometry=page_geometry,
            selector=selector,
            viewport_decision=viewport_decision,
        )
        if not lines:
            return (), selector.snapshot_id

        parent_result = self._authority.resolve(
            ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=page_parent.observation_id,
            )
        )
        if (
            parent_result.status != EvidenceResolutionStatus.CORROBORATED
            or parent_result.snapshot is None
            or parent_result.observation is None
            or parent_result.observation.observation_kind != "native_pdf_page"
            or parent_result.observation.page_id != selector.page_id
        ):
            return (), selector.snapshot_id

        known_ids = set(parent_result.snapshot.observation_ids)
        current_snapshot_id = selector.snapshot_id
        derived_ids: List[str] = []

        for line in lines:
            assert line.bbox_pt is not None
            text_norm = str(line.text).strip()
            box = line.bbox_pt
            primitive_ref = (
                f"ocr:{self._backend.name}:"
                f"{box[0]:.4f}:{box[1]:.4f}:{box[2]:.4f}:{box[3]:.4f}:"
                f"{text_norm}"
            )
            snapshot = self._source_producer.publish_derived_observation(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                base_snapshot_id=current_snapshot_id,
                page_id=page_parent.page_id,
                source_partition_id=page_parent.source_partition_id,
                observation_kind=OCR_TAG_OBSERVATION_KIND,
                source_primitive_ref=primitive_ref,
                origin_kind=OCR_TAG_OBSERVATION_ORIGIN_KIND,
                parent_observation_ids=(page_parent.observation_id,),
                raw_text=text_norm,
                geometry=box,
                viewport_id=selector.viewport_id,
            )
            current_snapshot_id = snapshot.snapshot_id
            new_ids = set(snapshot.observation_ids) - known_ids
            known_ids.update(new_ids)
            if len(new_ids) == 1:
                derived_ids.append(next(iter(new_ids)))

        tags: List[TagObservation] = []
        for observation_id in derived_ids:
            resolved = self._authority.resolve(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=current_snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                resolved.status == EvidenceResolutionStatus.CORROBORATED
                and resolved.observation is not None
            ):
                tags.append(
                    TagObservation.from_source_observation(
                        resolved.observation,
                        viewport_id=selector.viewport_id,
                    )
                )

        return tuple(tags), current_snapshot_id


def publish_raster_ocr_as_tag_observations(
    *,
    source_producer: SourceObservationProducer,
    selector: PortableRasterOCRSelector,
    viewport_decision: AuthenticatedViewportDecision,
    backend: Optional[RasterOCRBackend] = None,
    dpi: int = 300,
) -> Tuple[Tuple[TagObservation, ...], str]:
    """Production convenience wrapper around RasterOCRTagObservationProducer."""
    bridge = RasterOCRTagObservationProducer.create(
        source_producer=source_producer,
        backend=backend,
        dpi=dpi,
    )
    return bridge.publish(
        selector=selector,
        viewport_decision=viewport_decision,
    )
