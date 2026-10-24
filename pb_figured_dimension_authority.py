"""pb_figured_dimension_authority.py — Figured-Dimension Measurement Authority.

Resolves a single linear measurement's authoritative value by applying the
precedence rule that a figured/documented dimension (text printed on the
drawing, e.g. "6500" or "6.5m") outranks scaled PDF geometry. Extracted
figured-dimension text is normalized (mm and m units supported) and
validated: malformed, negative, zero, NaN, or infinite values are rejected
rather than silently treated as "no figured dimension available".

Every resolution returns a MeasurementAuthorityResult carrying full
authority metadata (source_type, authority_status, scaled_delta_mm, notes)
so callers never have to guess why a value was accepted, warned, or blocked.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
import math
import numbers
import re
from typing import Any, Dict, Optional

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType


class DimensionParseError(ValueError):
    """Raised when figured-dimension text cannot be parsed into a usable mm value."""


# Matches an optionally-signed number (plain, decimal, or comma-thousands-separated)
# followed by an optional unit suffix of "mm" or "m" (case-insensitive), with nothing
# else in the string. Anchored on both ends so trailing/leading noise is rejected
# rather than silently truncated.
_DIMENSION_TEXT_RE = re.compile(
    r"^\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[+-]?\d+(?:\.\d+)?)\s*(mm|m)?\s*$",
    re.IGNORECASE,
)


def parse_figured_dimension_mm(raw: Optional[str]) -> float:
    """Parse figured-dimension text into a positive, finite millimetre value.

    Supports bare numbers (assumed mm, matching AU drawing convention),
    explicit "mm" suffixes, and "m" suffixes (converted to mm). Rejects
    empty/missing text, unparseable text, and non-positive values.
    """
    if raw is None or not str(raw).strip():
        raise DimensionParseError("Figured dimension text is empty or missing")

    match = _DIMENSION_TEXT_RE.match(str(raw))
    if not match:
        raise DimensionParseError(f"Figured dimension text is not a recognizable measurement: {raw!r}")

    number_text, unit = match.group(1), (match.group(2) or "mm").lower()
    try:
        value = float(number_text.replace(",", ""))
    except ValueError as exc:
        raise DimensionParseError(f"Figured dimension text is not a recognizable measurement: {raw!r}") from exc

    if not math.isfinite(value):
        raise DimensionParseError(f"Figured dimension value must be finite, got {value}")

    value_mm = value * 1000.0 if unit == "m" else value

    if not math.isfinite(value_mm) or value_mm <= 0.0:
        raise DimensionParseError(f"Figured dimension value must be finite and strictly positive, got {value_mm}mm")

    return value_mm


# Two representations of the same figured dimension (printed text and a normalized number) agree when they match to
# float rounding; anything looser would let a real contradiction through.
_REPRESENTATION_REL_TOL = 1e-9
_REPRESENTATION_ABS_TOL_MM = 1e-6


def _validate_direct_figured_mm(value: float) -> float:
    """A direct figured value must be a real number, never bool or coerced text."""
    if isinstance(value, bool) or not isinstance(value, (numbers.Real, Decimal)):
        raise DimensionParseError("Figured dimension must be real numeric millimetres (not bool)")
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise DimensionParseError("Figured dimension cannot be represented as finite") from None
    if not math.isfinite(number) or number <= 0.0:
        raise DimensionParseError("Figured dimension must be finite and strictly positive")
    return number


def _finite_positive_numeric(value: object) -> Optional[float]:
    """Return a typed finite positive numeric value; reject bool and coercions."""
    if isinstance(value, bool) or not isinstance(value, (numbers.Real, Decimal)):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0.0 else None


@dataclass
class MeasurementAuthorityResult:
    """Authority metadata for a single resolved (or blocked) linear measurement."""
    value_m: Optional[float]
    source_type: Optional[str]  # from MeasurementAuthorityType, or None if nothing was provided
    authority_status: str  # from AuthorityStatus
    scaled_delta_mm: Optional[float]
    figured_mm: Optional[float]
    scaled_mm: Optional[float]
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_measurement_authority(
    scaled_mm: Optional[float] = None,
    *,
    figured_text: Optional[str] = None,
    figured_mm: Optional[float] = None,
    scale_reliable: bool = True,
    max_delta_ratio: float = 0.05,
) -> MeasurementAuthorityResult:
    """Resolve the authoritative measurement from figured and/or scaled inputs.

    Precedence:
      1. A valid figured dimension (from `figured_text` or `figured_mm`) always
         wins. If it disagrees with `scaled_mm` by more than `max_delta_ratio`,
         the result is flagged REVIEW_REQUIRED with a warning rather than FIRM;
         either way the delta is recorded.
      2. A malformed, negative, zero, NaN, or infinite figured value is REJECTED
         outright (authority_status=BLOCKED) rather than silently falling back
         to scaled geometry — an unreadable figured dimension is a data-quality
         problem, not the absence of one.
      3. With no usable figured dimension, scaled geometry may only be used as
         PROVISIONAL when `scale_reliable` is True. An unreliable scale (even if
         `scaled_mm` is itself a finite positive number) blocks rather than
         producing a provisional value, since a fabricated/uncalibrated scale
         cannot be trusted even provisionally.
    """
    # An invalid comparison tolerance must not turn conflicting dimensions FIRM.
    if (isinstance(max_delta_ratio, bool)
            or not isinstance(max_delta_ratio, (numbers.Real, Decimal))
            or (_finite_positive_numeric(max_delta_ratio) is None and max_delta_ratio != 0)):
        return MeasurementAuthorityResult(
            value_m=None,
            source_type=(MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
                         if figured_text is not None or figured_mm is not None
                         else MeasurementAuthorityType.PDF_SCALED.value if scaled_mm is not None else None),
            authority_status=AuthorityStatus.BLOCKED.value,
            scaled_delta_mm=None,
            figured_mm=None,
            scaled_mm=None,
            notes="Blocked: comparison tolerance must be finite and nonnegative",
        )

    figured_value_mm: Optional[float] = None
    figured_error: Optional[str] = None

    if figured_text is not None:
        try:
            figured_value_mm = parse_figured_dimension_mm(figured_text)
        except DimensionParseError as exc:
            figured_error = str(exc)
        if figured_error is None and figured_mm is not None:
            # Two representations of one dimension must agree. Silently letting the text win
            # (or the number win) would hide a contradiction behind a FIRM result.
            try:
                direct_mm = _validate_direct_figured_mm(figured_mm)
            except DimensionParseError as exc:
                figured_error = str(exc)
            else:
                if not math.isclose(
                    figured_value_mm, direct_mm, rel_tol=_REPRESENTATION_REL_TOL, abs_tol=_REPRESENTATION_ABS_TOL_MM
                ):
                    return MeasurementAuthorityResult(
                        value_m=None,
                        source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                        authority_status=AuthorityStatus.BLOCKED.value,
                        scaled_delta_mm=None,
                        figured_mm=None,
                        scaled_mm=scaled_mm,
                        notes=(
                            "Blocked: figured representations disagree "
                            f"(text {figured_value_mm}mm vs value {direct_mm}mm)"
                        ),
                    )
    elif figured_mm is not None:
        try:
            figured_value_mm = _validate_direct_figured_mm(figured_mm)
        except DimensionParseError as exc:
            figured_error = str(exc)

    if figured_error is not None:
        return MeasurementAuthorityResult(
            value_m=None,
            source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            authority_status=AuthorityStatus.BLOCKED.value,
            scaled_delta_mm=None,
            figured_mm=None,
            scaled_mm=scaled_mm,
            notes=f"Blocked: malformed figured dimension rejected ({figured_error})",
        )

    trusted_scaled_mm = _finite_positive_numeric(scaled_mm)
    scaled_valid = trusted_scaled_mm is not None
    if scaled_mm is not None and not scaled_valid and figured_value_mm is not None:
        return MeasurementAuthorityResult(
            value_m=None,
            source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            authority_status=AuthorityStatus.BLOCKED.value,
            scaled_delta_mm=None,
            figured_mm=figured_value_mm,
            scaled_mm=None,
            notes="Blocked: supplied scaled comparison is not finite positive numeric",
        )

    if figured_value_mm is not None:
        value_m = round(figured_value_mm / 1000.0, 4)
        if value_m <= 0.0:
            return MeasurementAuthorityResult(
                value_m=None,
                source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                authority_status=AuthorityStatus.BLOCKED.value,
                scaled_delta_mm=None,
                figured_mm=figured_value_mm,
                scaled_mm=trusted_scaled_mm,
                notes="Blocked: documented dimension would round to zero metres",
            )

        if scaled_valid:
            delta_mm = round(abs(figured_value_mm - trusted_scaled_mm), 2)
            # Keep the historical rounded-delta comparison byte-for-byte for
            # valid measurements (including the exact tolerance boundary).
            delta_ratio = delta_mm / figured_value_mm
            if delta_ratio > max_delta_ratio:
                return MeasurementAuthorityResult(
                    value_m=value_m,
                    source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                    authority_status=AuthorityStatus.REVIEW_REQUIRED.value,
                    scaled_delta_mm=delta_mm,
                    figured_mm=figured_value_mm,
                    scaled_mm=scaled_mm,
                    notes=(
                        f"Warning: scaled-vs-figured delta {delta_mm}mm "
                        f"({delta_ratio * 100:.1f}%) exceeds tolerance"
                    ),
                )
            return MeasurementAuthorityResult(
                value_m=value_m,
                source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                authority_status=AuthorityStatus.FIRM.value,
                scaled_delta_mm=delta_mm,
                figured_mm=figured_value_mm,
                scaled_mm=scaled_mm,
                notes=f"Figured dimension precedence applied (scaled delta: {delta_mm}mm)",
            )

        return MeasurementAuthorityResult(
            value_m=value_m,
            source_type=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            authority_status=AuthorityStatus.FIRM.value,
            scaled_delta_mm=None,
            figured_mm=figured_value_mm,
            scaled_mm=None,
            notes="Figured dimension applied without scaled comparison",
        )

    # No usable figured dimension: scaled geometry may only be used provisionally
    # when the underlying page scale is itself reliable.
    if scaled_valid and scale_reliable:
        return MeasurementAuthorityResult(
            value_m=round(trusted_scaled_mm / 1000.0, 4),
            source_type=MeasurementAuthorityType.PDF_SCALED.value,
            authority_status=AuthorityStatus.PROVISIONAL.value,
            scaled_delta_mm=None,
            figured_mm=None,
            scaled_mm=scaled_mm,
            notes="Scaled geometry applied as provisional (no figured dimension available)",
        )

    if scaled_mm is not None and not scaled_valid:
        notes = "Blocked: scaled geometry is invalid (non-finite or non-positive) and no figured dimension is available"
    elif scaled_valid and not scale_reliable:
        notes = "Blocked: page scale is not reliable and no figured dimension is available"
    else:
        notes = "Blocked: no figured dimension and no scaled geometry available"

    return MeasurementAuthorityResult(
        value_m=None,
        source_type=MeasurementAuthorityType.PDF_SCALED.value if scaled_mm is not None else None,
        authority_status=AuthorityStatus.BLOCKED.value,
        scaled_delta_mm=None,
        figured_mm=None,
        scaled_mm=scaled_mm,
        notes=notes,
    )
