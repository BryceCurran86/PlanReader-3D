"""Item 28: Source-hash/revision-safe evidence cache, spatial aperture index, and stage profiler shadow.

Provides deterministic, tamper-checked caching and profiling for:
1. Native PDF page extraction (drawings/text summaries keyed by raw PDF SHA-256)
2. Schedule parsing outputs
3. 2D spatial grid indexing for aperture/segment neighborhood lookup (with exact
   brute-force parity verification)

Safety invariants:
- Cache keys NEVER use file paths, filenames, mtimes, or mutable process globals.
  Every key binds `(source_sha256, document_id, revision_id, page_index,
  viewport_id, stage_name, producer_schema_version, options_digest_sha256)`.
- Stored payloads are canonical JSON serialized with an explicit `value_sha256`
  digest; reads verify integrity before returning a fresh deep copy so downstream
  mutation cannot poison the cache.
- Corrupt or tampered cache payloads fail closed (`CacheIntegrityError`).
- Spatial index queries are guaranteed exact-set-identical to linear scan.

Shadow-only utility; never alters scoring or commercial authority and contains
zero job-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Callable, Mapping, Sequence


_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


class CacheIntegrityError(ValueError):
    """Raised when a cached evidence artifact fails SHA-256 integrity or schema checks."""


def _clean(value: object) -> str:
    return str(value or "").strip()


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize JSON-compatible data canonically with sorted keys and compact separators."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class SourceEvidenceCacheKey:
    """Immutable composite cache key bound strictly to source content + revision + options."""

    source_sha256: str
    document_id: str
    revision_id: str
    page_index: int
    viewport_id: str
    stage_name: str
    producer_schema_version: str
    options_digest_sha256: str

    def __post_init__(self) -> None:
        sha = _clean(self.source_sha256).lower()
        if not _SHA256_HEX_RE.match(sha):
            raise ValueError("source_sha256 must be a valid 64-char hex digest")
        opt_sha = _clean(self.options_digest_sha256).lower()
        if not _SHA256_HEX_RE.match(opt_sha):
            raise ValueError("options_digest_sha256 must be a valid 64-char hex digest")
        if isinstance(self.page_index, bool) or not isinstance(self.page_index, int) or self.page_index < 0:
            raise ValueError("page_index must be a non-negative integer")
        for field_name in ("document_id", "revision_id", "viewport_id", "stage_name", "producer_schema_version"):
            if not _clean(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be non-empty")

    @classmethod
    def from_raw_bytes(
        cls,
        raw_source_bytes: bytes,
        *,
        document_id: str,
        revision_id: str,
        page_index: int,
        viewport_id: str,
        stage_name: str,
        producer_schema_version: str,
        options: Mapping[str, Any] | None = None,
    ) -> "SourceEvidenceCacheKey":
        if not isinstance(raw_source_bytes, (bytes, bytearray)) or len(raw_source_bytes) == 0:
            raise ValueError("raw_source_bytes must be non-empty bytes")
        src_sha = hashlib.sha256(bytes(raw_source_bytes)).hexdigest()
        opt_sha = canonical_sha256(dict(options or {}))
        return cls(
            source_sha256=src_sha,
            document_id=_clean(document_id),
            revision_id=_clean(revision_id),
            page_index=int(page_index),
            viewport_id=_clean(viewport_id),
            stage_name=_clean(stage_name),
            producer_schema_version=_clean(producer_schema_version),
            options_digest_sha256=opt_sha,
        )

    def key_digest_sha256(self) -> str:
        return canonical_sha256(
            {
                "source_sha256": _clean(self.source_sha256).lower(),
                "document_id": _clean(self.document_id),
                "revision_id": _clean(self.revision_id),
                "page_index": self.page_index,
                "viewport_id": _clean(self.viewport_id),
                "stage_name": _clean(self.stage_name),
                "producer_schema_version": _clean(self.producer_schema_version),
                "options_digest_sha256": _clean(self.options_digest_sha256).lower(),
            }
        )


@dataclass(frozen=True)
class StageProfileReceipt:
    stage_name: str
    cache_key_sha256: str
    value_sha256: str
    cache_hit: bool
    elapsed_ms: float
    path_based_key_forbidden: bool = True
    cache_poisoning_protected: bool = True
    commercial_authority_granted: bool = False
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "cache_key_sha256": self.cache_key_sha256,
            "value_sha256": self.value_sha256,
            "cache_hit": self.cache_hit,
            "elapsed_ms": round(self.elapsed_ms, 4),
            "path_based_key_forbidden": True,
            "cache_poisoning_protected": True,
            "commercial_authority_granted": False,
            "shadow_only": True,
        }


class SourceHashEvidenceCache:
    """In-memory or optional directory-backed source-hash/revision-safe evidence cache."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, tuple[str, bytes]] = {}
        self.hits = 0
        self.misses = 0
        self.profile_receipts: list[StageProfileReceipt] = []

    def _entry_path(self, key_sha: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"{key_sha}.json"

    def _read_verified(self, key_sha: str) -> tuple[Any, str] | None:
        if key_sha in self._mem:
            expected_sha, raw = self._mem[key_sha]
            actual_sha = hashlib.sha256(raw).hexdigest()
            if actual_sha != expected_sha:
                raise CacheIntegrityError(f"in-memory cache payload tampered for key {key_sha[:16]}")
            return json.loads(raw.decode("utf-8")), expected_sha

        entry_path = self._entry_path(key_sha)
        if entry_path is None or not entry_path.is_file():
            return None

        try:
            envelope = json.loads(entry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CacheIntegrityError(f"corrupt cache envelope for key {key_sha[:16]}") from exc

        if not isinstance(envelope, dict) or envelope.get("cache_key_sha256") != key_sha:
            raise CacheIntegrityError(f"cache key mismatch for {key_sha[:16]}")
        expected_sha = str(envelope.get("value_sha256") or "")
        if "payload" not in envelope or not _SHA256_HEX_RE.match(expected_sha):
            raise CacheIntegrityError(f"missing payload or value_sha256 for {key_sha[:16]}")
        raw = canonical_json_bytes(envelope["payload"])
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != expected_sha:
            raise CacheIntegrityError(f"on-disk cache integrity failure for {key_sha[:16]}")

        self._mem[key_sha] = (expected_sha, raw)
        return json.loads(raw.decode("utf-8")), expected_sha

    def _write_verified(self, key_sha: str, payload: Any) -> tuple[Any, str]:
        raw = canonical_json_bytes(payload)
        value_sha = hashlib.sha256(raw).hexdigest()
        self._mem[key_sha] = (value_sha, raw)
        entry_path = self._entry_path(key_sha)
        if entry_path is not None:
            envelope = {
                "cache_key_sha256": key_sha,
                "value_sha256": value_sha,
                "payload": json.loads(raw.decode("utf-8")),
            }
            entry_path.write_text(
                json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                encoding="utf-8",
            )
        # Always return a freshly deserialized copy to prevent downstream mutation poisoning
        return json.loads(raw.decode("utf-8")), value_sha

    def get_or_compute(
        self,
        key: SourceEvidenceCacheKey,
        producer: Callable[[], Any],
    ) -> tuple[Any, StageProfileReceipt]:
        """Fetch verified cached result or invoke producer, recording a profile receipt."""
        key_sha = key.key_digest_sha256()
        t0 = time.perf_counter()
        cached = self._read_verified(key_sha)
        if cached is not None:
            value, val_sha = cached
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.hits += 1
            receipt = StageProfileReceipt(
                stage_name=key.stage_name,
                cache_key_sha256=key_sha,
                value_sha256=val_sha,
                cache_hit=True,
                elapsed_ms=elapsed_ms,
            )
            self.profile_receipts.append(receipt)
            return value, receipt

        computed = producer()
        value, val_sha = self._write_verified(key_sha, computed)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.misses += 1
        receipt = StageProfileReceipt(
            stage_name=key.stage_name,
            cache_key_sha256=key_sha,
            value_sha256=val_sha,
            cache_hit=False,
            elapsed_ms=elapsed_ms,
        )
        self.profile_receipts.append(receipt)
        return value, receipt


@dataclass(frozen=True)
class IndexedSpatialItem:
    item_id: str
    bbox_pdf_pts: tuple[float, float, float, float]


class SpatialApertureEvidenceIndex:
    """Uniform 2D grid index with exact parity against brute-force bbox intersection."""

    def __init__(self, items: Sequence[IndexedSpatialItem], *, cell_size_pts: float = 36.0) -> None:
        if not math.isfinite(cell_size_pts) or cell_size_pts <= 0.0:
            raise ValueError("cell_size_pts must be positive finite")
        self._cell = float(cell_size_pts)
        self._items: dict[str, tuple[float, float, float, float]] = {}
        self._grid: dict[tuple[int, int], list[str]] = {}
        for item in items:
            x0, y0, x1, y1 = item.bbox_pdf_pts
            norm = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            if not all(math.isfinite(v) for v in norm):
                continue
            self._items[item.item_id] = norm
            gx0, gy0 = math.floor(norm[0] / self._cell), math.floor(norm[1] / self._cell)
            gx1, gy1 = math.floor(norm[2] / self._cell), math.floor(norm[3] / self._cell)
            for gx in range(gx0, gx1 + 1):
                for gy in range(gy0, gy1 + 1):
                    self._grid.setdefault((gx, gy), []).append(item.item_id)

    def query_bbox(self, bbox: tuple[float, float, float, float], *, pad_pts: float = 0.0) -> tuple[str, ...]:
        qx0 = min(bbox[0], bbox[2]) - pad_pts
        qy0 = min(bbox[1], bbox[3]) - pad_pts
        qx1 = max(bbox[0], bbox[2]) + pad_pts
        qy1 = max(bbox[1], bbox[3]) + pad_pts
        gx0, gy0 = math.floor(qx0 / self._cell), math.floor(qy0 / self._cell)
        gx1, gy1 = math.floor(qx1 / self._cell), math.floor(qy1 / self._cell)

        seen: set[str] = set()
        hits: list[str] = []
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                for item_id in self._grid.get((gx, gy), ()):
                    if item_id in seen:
                        continue
                    seen.add(item_id)
                    ix0, iy0, ix1, iy1 = self._items[item_id]
                    if ix1 >= qx0 and ix0 <= qx1 and iy1 >= qy0 and iy0 <= qy1:
                        hits.append(item_id)
        hits.sort()
        return tuple(hits)

    def brute_force_query_bbox(
        self, bbox: tuple[float, float, float, float], *, pad_pts: float = 0.0
    ) -> tuple[str, ...]:
        """Reference O(N) linear scan for exact parity verification."""
        qx0 = min(bbox[0], bbox[2]) - pad_pts
        qy0 = min(bbox[1], bbox[3]) - pad_pts
        qx1 = max(bbox[0], bbox[2]) + pad_pts
        qy1 = max(bbox[1], bbox[3]) + pad_pts
        hits = [
            item_id
            for item_id, (ix0, iy0, ix1, iy1) in self._items.items()
            if ix1 >= qx0 and ix0 <= qx1 and iy1 >= qy0 and iy0 <= qy1
        ]
        hits.sort()
        return tuple(hits)
