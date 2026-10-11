"""Independent immutable PDF-backed full foreground-run source; shadow only."""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import re

import cv2
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_raster_visible_segment_detector import _foreground_mask, _MIN_LINE_LENGTH_PT
from pb_source_observation_authority import (
    ObservationSelector, PublishedSourceSnapshot, SourceObservationAuthorityResult,
    SourceObservationProducer, PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PRODUCER_INTEGRITY_FAILURE, OBSERVATION_UNAVAILABLE,
)
from pb_source_visibility_authority import RASTER_RENDER_DPI

FULL_RUN_SCHEMA_VERSION = "1.0.0"
FULL_RUN_KIND = "raster_full_foreground_run_shadow"
FULL_RUN_ORIGIN = "producer_raster_full_foreground_run_shadow"
_FACTORY_SEAL = object()


@dataclass(frozen=True)
class FullRunProof:
    orientation: str
    pixel_geometry: tuple[int, int, int, int]
    geometry: tuple[float, float, float, float]
    foreground_sha256: str
    scanline_sha256: str
    run_pixel_count: int


def _digest(array):
    return sha256(array.tobytes(order="C")).hexdigest()


def _inventory(png_bytes: bytes) -> tuple[FullRunProof, ...]:
    """Enumerate EVERY full, axis-aligned original-positive foreground run.

    Neither image component morphology nor an opening/query window controls
    nomination. Endpoint ownership is original positive pixel evidence only.
    It cannot assert the foreground was structural wall ink.
    """
    gray = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None or not gray.size:
        raise ValueError("full-foreground full-foreground source render decode unavailable")
    foreground = _foreground_mask(gray)
    if foreground is None:
        return ()
    scale = RASTER_RENDER_DPI / 72.0
    source_sha = _digest(foreground)
    rows: list[FullRunProof] = []
    for orientation, oriented in (
        ("horizontal", foreground),
        ("vertical", foreground.T),
    ):
        for fixed, row in enumerate(oriented):
            if not np.any(row):
                continue
            # Boundary sentinels ensure runs touching edges are complete.
            transitions = np.diff(np.pad((row != 0).astype(np.int8), (1, 1)))
            starts = np.flatnonzero(transitions == 1)
            ends = np.flatnonzero(transitions == -1)
            if len(starts) != len(ends):
                raise ValueError("unbalanced full-foreground run boundaries")
            for lo, exclusive_hi in zip(starts, ends):
                start, finish = int(lo), int(exclusive_hi) - 1
                if (finish-start)/scale < _MIN_LINE_LENGTH_PT:
                    continue
                pixels = (
                    (start, fixed, finish, fixed)
                    if orientation == "horizontal"
                    else (fixed, start, fixed, finish)
                )
                rows.append(FullRunProof(
                    orientation=orientation, pixel_geometry=pixels,
                    geometry=tuple(float(v)/scale for v in pixels),
                    foreground_sha256=source_sha,
                    scanline_sha256=_digest(row),
                    run_pixel_count=finish-start+1,
                ))
                if len(rows) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
                    # Never truncate the producer source universe.
                    raise ValueError("full-foreground source primitive count exceeds safety bound")
    rows.sort(key=lambda value: (value.orientation, value.pixel_geometry))
    if len({(r.orientation, r.pixel_geometry) for r in rows}) != len(rows):
        raise ValueError("duplicate original foreground run address")
    return tuple(rows)

def _reference(render_sha, proof):
    address = stable_contract_id("pixel_run", {
        "schema_version": FULL_RUN_SCHEMA_VERSION, "orientation": proof.orientation,
        "pixel_geometry": proof.pixel_geometry,
    }, digest_chars=32)
    return f"{FULL_RUN_KIND}:{render_sha}:{FULL_RUN_SCHEMA_VERSION}:{address}"


def _blocked(reason, *, conflict=False):
    return SourceObservationAuthorityResult(
        status=EvidenceResolutionStatus.CONFLICT if conflict else EvidenceResolutionStatus.ABSTAINED,
        proposition=None, physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
        reason_codes=(reason,), semantic_enumeration_complete=False, decision_scope_complete=False,
    )


class FullForegroundSourceProducer:
    """Independent shadow store. No caller pixels, geometry, masks or receipts."""

    def __init__(self, source_bytes: bytes, *, expected_source_sha: str, page_id: str):
        if not isinstance(source_bytes, bytes):
            raise TypeError("full-foreground source PDF must be immutable bytes")
        if (not isinstance(expected_source_sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", expected_source_sha) is None
                or sha256(source_bytes).hexdigest() != expected_source_sha):
            raise ValueError("full-foreground source PDF SHA mismatch")
        if (not isinstance(page_id, str) or not page_id.isascii() or not page_id.isdigit()
                or int(page_id) < 1 or str(int(page_id)) != page_id):
            raise ValueError("invalid canonical full-foreground source page")
        self._source = SourceObservationProducer(producer_method="raster-full-foreground-run-shadow",
            producer_version=FULL_RUN_SCHEMA_VERSION)
        self._base = self._source.ingest_native_pdf_bytes(
            document_id=f"full-foreground-source:{expected_source_sha}", source_bytes=source_bytes,
            source_locator="memory://full-foreground-run-shadow.pdf", page_ids=(page_id,))
        self._page_id = page_id
        self._published = None
        self._proofs = {}
        self._render_receipt = None
        self._verified_inventory = None

    @property
    def base_snapshot(self):
        return self._copy_published(self._base)

    @staticmethod
    def _copy_published(published):
        return replace(published, revision=replace(published.revision),
            coverage=replace(published.coverage), snapshot=replace(published.snapshot))

    def _render(self):
        base = self._base
        return self._source.render_native_page_png(document_id=base.revision.document_id,
            revision_id=base.revision.revision_id, source_sha256=base.revision.source_sha256,
            snapshot_id=base.snapshot.snapshot_id, page_id=self._page_id,
            dpi=float(RASTER_RENDER_DPI), include_native_frame=True)

    def nominate(self) -> PublishedSourceSnapshot:
        if self._published is not None:
            self._verify_render()
            return self._copy_published(self._published)
        png, parent, frame = self._render()
        if frame.rotation != 0:
            raise ValueError("full-foreground source native/display rotation unresolved")
        proofs = _inventory(png)
        render_sha = sha256(png).hexdigest()
        source_authority = self._source.authority()
        base = self._base
        native_segment_count = 0
        for observation_id in base.snapshot.observation_ids:
            result = source_authority.resolve(ObservationSelector(base.revision.document_id,
                base.revision.revision_id, base.revision.source_sha256, base.snapshot.snapshot_id,
                observation_id))
            if result.status != EvidenceResolutionStatus.CORROBORATED or result.observation is None:
                raise ValueError("full-foreground source base observation unavailable")
            native_segment_count += result.observation.observation_kind == "native_pdf_segment"
        if native_segment_count + len(proofs) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
            raise ValueError("full-foreground source primitive count exceeds safety bound")
        specs = []
        pending = {}
        for proof in proofs:
            reference = _reference(render_sha, proof)
            payload = {"document_id": base.revision.document_id, "revision_id": base.revision.revision_id,
                "page_id": self._page_id, "partition_id": parent.source_partition_id,
                "kind": FULL_RUN_KIND, "primitive_ref": reference, "origin_kind": FULL_RUN_ORIGIN,
                "parents": (parent.observation_id,), "raw_text": "", "geometry": proof.geometry}
            observation_id = stable_contract_id("source_observation", payload, digest_chars=32)
            specs.append(dict(page_id=self._page_id, source_partition_id=parent.source_partition_id,
                observation_kind=FULL_RUN_KIND, source_primitive_ref=reference,
                origin_kind=FULL_RUN_ORIGIN, parent_observation_ids=(parent.observation_id,),
                raw_text="", geometry=proof.geometry, viewport_id=None, observation_id=observation_id))
            pending[observation_id] = proof
        if len(pending) != len(proofs):
            raise ValueError("duplicate producer full-foreground source identity")
        # Complete inventory and cap validation precede the sole append operation.
        snapshot = (self._source.publish_derived_observations(document_id=base.revision.document_id,
            revision_id=base.revision.revision_id, base_snapshot_id=base.snapshot.snapshot_id,
            observations=specs) if specs else base.snapshot)
        self._published = PublishedSourceSnapshot(base.revision, base.coverage, snapshot)
        self._proofs = pending
        self._render_receipt = (png, parent, frame)
        self._verified_inventory = {proof.pixel_geometry: proof for proof in proofs}
        return self._copy_published(self._published)

    def _verify_render(self):
        png, parent, frame = self._render()
        if self._render_receipt != (png, parent, frame):
            raise ValueError("immutable full-foreground source render receipt changed")
        return png, parent, frame

    def authority(self):
        return FullForegroundSourceAuthority(self, _seal=_FACTORY_SEAL)

    def selectors(self):
        published = self.nominate()
        revision = published.revision
        return tuple(ObservationSelector(revision.document_id, revision.revision_id,
            revision.source_sha256, published.snapshot.snapshot_id, observation_id)
            for observation_id in sorted(self._proofs))


class FullForegroundSourceAuthority:
    """Proves source pixels only. Normal visibility remains a separate gate."""

    def __init__(self, producer, *, _seal=None):
        if _seal is not _FACTORY_SEAL:
            raise TypeError("pixel authority must come from FullForegroundSourceProducer.authority()")
        self._owner = producer

    def resolve(self, selector: ObservationSelector):
        return self._resolve(selector)

    def resolve_many(self, selectors):
        if not isinstance(selectors, tuple) or len(selectors) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
            raise ValueError("invalid bounded full-foreground source selector inventory")
        if not selectors:
            return ()
        try:
            render = self._owner._verify_render()
        except ValueError:
            return tuple(_blocked(PRODUCER_INTEGRITY_FAILURE, conflict=True) for _ in selectors)
        return tuple(self._resolve(selector, render=render) for selector in selectors)

    def _resolve(self, selector, *, render=None):
        if not isinstance(selector, ObservationSelector):
            return _blocked(OBSERVATION_UNAVAILABLE)
        owner = self._owner
        published = owner._published
        if published is None:
            return _blocked(OBSERVATION_UNAVAILABLE)
        proof = owner._proofs.get(selector.observation_id)
        if proof is None or selector.snapshot_id != published.snapshot.snapshot_id:
            return _blocked(OBSERVATION_UNAVAILABLE)
        result = owner._source.authority().resolve(selector)
        if result.status != EvidenceResolutionStatus.CORROBORATED or result.observation is None:
            return result
        try:
            png, parent, frame = owner._verify_render() if render is None else render
        except ValueError:
            return _blocked(PRODUCER_INTEGRITY_FAILURE, conflict=True)
        record = result.observation
        parent_result = owner._source.authority().resolve(replace(selector, observation_id=parent.observation_id))
        expected = owner._verified_inventory.get(proof.pixel_geometry)
        if (proof != expected or frame.rotation != 0
                or record.observation_kind != FULL_RUN_KIND or record.origin_kind != FULL_RUN_ORIGIN
                or record.geometry != proof.geometry or record.viewport_id is not None
                or record.page_id != owner._page_id or record.raw_text != ""
                or record.producer_method != "raster-full-foreground-run-shadow"
                or record.producer_version != FULL_RUN_SCHEMA_VERSION
                or record.source_partition_id != parent.source_partition_id
                or record.derivation_parent_ids != (parent.observation_id,)
                or record.source_primitive_ref != _reference(sha256(png).hexdigest(), proof)
                or parent_result.status != EvidenceResolutionStatus.CORROBORATED
                or parent_result.observation is None
                or parent_result.observation.observation_kind != "native_pdf_page"
                or parent_result.observation.geometry != parent.geometry
                or parent_result.observation.derivation_parent_ids):
            return _blocked(PRODUCER_INTEGRITY_FAILURE, conflict=True)
        return replace(result, semantic_enumeration_complete=False, decision_scope_complete=False)


__all__ = ["FullForegroundSourceProducer", "FullForegroundSourceAuthority", "FULL_RUN_KIND", "FULL_RUN_SCHEMA_VERSION"]
