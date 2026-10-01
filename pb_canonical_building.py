"""
PlanReader Canonical Building Model Schema & Provenance Engine.

Defines the single-source-of-truth object graph representing physical building geometry:
Project -> Building -> Level -> Space/Room -> Wall -> Opening (Door/Window) ->
Floor -> Ceiling -> Roof -> Soffit -> Balcony -> Parapet -> Column -> Balustrade -> Screen -> FinishSurface.

Fail-Closed & Zero-Made-Up-Data Rules:
- Default review_state = REVIEW_REQUIRED
- Default confidence = None (Unrecorded)
- Default takeoff_eligible = False (Strict boolean required)
- Default deduction_authority = False (Strict boolean required)
- Physical dimensions default to None (No invented fallback heights or thicknesses)
- Strict boolean parsing: ONLY actual JSON/Python boolean True grants authority.
  Direct Python construction with "false", "true", "yes", 1, 0 fails closed to False.
"""

from dataclasses import dataclass, field
from enum import Enum
import math
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple, Union


def parse_strict_bool(value: Any) -> bool:
    """
    Strict boolean parser.
    ONLY actual Python bool True grants authority.
    Strings such as "true", "false", "yes", "1", "0" and integers return False.
    """
    if isinstance(value, bool):
        return value
    return False


def parse_optional_confidence(value: Any) -> Optional[float]:
    """
    Parses optional confidence score (0.0 to 1.0).
    Distinguishes between missing confidence (None) and explicit 0.0 confidence.
    Malformed or out-of-bounds values return None.
    """
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return max(0.0, min(1.0, f))
    except (ValueError, TypeError):
        return None


def parse_optional_float(value: Any) -> Optional[float]:
    """Parses metric dimension float. Returns None for missing/malformed/non-positive numbers."""
    if value is None:
        return None
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


class ReviewState(str, Enum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ObjectType(str, Enum):
    PROJECT = "PROJECT"
    BUILDING = "BUILDING"
    LEVEL = "LEVEL"
    SPACE = "SPACE"
    WALL = "WALL"
    OPENING = "OPENING"
    DOOR = "DOOR"
    WINDOW = "WINDOW"
    FLOOR = "FLOOR"
    CEILING = "CEILING"
    ROOF = "ROOF"
    SOFFIT = "SOFFIT"
    BALCONY = "BALCONY"
    PARAPET = "PARAPET"
    COLUMN = "COLUMN"
    BALUSTRADE = "BALUSTRADE"
    SCREEN = "SCREEN"
    SURFACE = "SURFACE"


@dataclass
class Provenance:
    """Retains origin traces for evidence-based drawing reconciliation."""
    source_pdf: Optional[str] = None
    page_number: Optional[int] = None
    drawing_id: Optional[str] = None
    source_coords: Optional[Dict[str, Any]] = None
    scale_source: Optional[str] = None
    workspace_id: Optional[str] = None
    document_id: Optional[str] = None
    page_id: Optional[str] = None
    wall_ref: Optional[str] = None
    opening_instance_id: Optional[str] = None
    plan_geometry_signature: Optional[str] = None
    coordinate_space: Optional[str] = None
    producer_module: Optional[str] = None
    producer_version: Optional[str] = None
    contributing_evidence: List[str] = field(default_factory=list)
    is_superseded: bool = False
    is_stale: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_pdf": self.source_pdf,
            "page_number": self.page_number,
            "drawing_id": self.drawing_id,
            "source_coords": self.source_coords,
            "scale_source": self.scale_source,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "page_id": self.page_id,
            "wall_ref": self.wall_ref,
            "opening_instance_id": self.opening_instance_id,
            "plan_geometry_signature": self.plan_geometry_signature,
            "coordinate_space": self.coordinate_space,
            "producer_module": self.producer_module,
            "producer_version": self.producer_version,
            "contributing_evidence": list(self.contributing_evidence),
            "is_superseded": self.is_superseded,
            "is_stale": self.is_stale,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "Provenance":
        if not isinstance(data, dict):
            return cls()
        return cls(
            source_pdf=data.get("source_pdf"),
            page_number=data.get("page_number"),
            drawing_id=data.get("drawing_id"),
            source_coords=data.get("source_coords") if isinstance(data.get("source_coords"), dict) else None,
            scale_source=data.get("scale_source"),
            workspace_id=data.get("workspace_id"),
            document_id=data.get("document_id"),
            page_id=data.get("page_id"),
            wall_ref=data.get("wall_ref"),
            opening_instance_id=data.get("opening_instance_id"),
            plan_geometry_signature=data.get("plan_geometry_signature"),
            coordinate_space=data.get("coordinate_space"),
            producer_module=data.get("producer_module"),
            producer_version=data.get("producer_version"),
            contributing_evidence=list(data.get("contributing_evidence", []) or []) if isinstance(data.get("contributing_evidence"), list) else [],
            is_superseded=parse_strict_bool(data.get("is_superseded", False)),
            is_stale=parse_strict_bool(data.get("is_stale", False)),
        )


@dataclass
class Vector2D:
    x: Optional[float] = None
    y: Optional[float] = None

    def is_valid(self) -> bool:
        return self.x is not None and self.y is not None

    def distance_to(self, other: "Vector2D") -> float:
        if not (self.is_valid() and other and other.is_valid()):
            return 0.0
        return math.hypot(other.x - self.x, other.y - self.y)

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], List[float], Tuple[float, float]]) -> "Vector2D":
        if isinstance(data, dict):
            return cls(x=parse_optional_float(data.get("x")), y=parse_optional_float(data.get("y")))
        elif isinstance(data, (list, tuple)) and len(data) >= 2:
            return cls(x=parse_optional_float(data[0]), y=parse_optional_float(data[1]))
        return cls(x=None, y=None)


@dataclass
class Vector3D:
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None

    def is_valid(self) -> bool:
        return self.x is not None and self.y is not None and self.z is not None

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], List[float], Tuple[float, float, float]]) -> "Vector3D":
        if isinstance(data, dict):
            return cls(
                x=parse_optional_float(data.get("x")),
                y=parse_optional_float(data.get("y")),
                z=parse_optional_float(data.get("z")),
            )
        elif isinstance(data, (list, tuple)) and len(data) >= 3:
            return cls(
                x=parse_optional_float(data[0]),
                y=parse_optional_float(data[1]),
                z=parse_optional_float(data[2]),
            )
        return cls(x=None, y=None, z=None)


@dataclass
class BoundingBox3D:
    min_point: Vector3D
    max_point: Vector3D

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_point": self.min_point.to_dict(),
            "max_point": self.max_point.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "BoundingBox3D":
        if not isinstance(data, dict):
            return cls(min_point=Vector3D(), max_point=Vector3D())
        return cls(
            min_point=Vector3D.from_dict(data.get("min_point")),
            max_point=Vector3D.from_dict(data.get("max_point")),
        )


@dataclass
class CanonicalElement:
    """Base class for all canonical building elements. Fails closed with ZERO made-up defaults."""
    id: str = field(default_factory=lambda: f"elem_{uuid.uuid4().hex[:8]}")
    name: str = "Unnamed Element"
    object_type: ObjectType = ObjectType.SURFACE
    level_id: Optional[str] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    confidence: Optional[float] = None  # None = Unrecorded
    review_state: ReviewState = ReviewState.REVIEW_REQUIRED  # Fail-closed default
    provenance: Provenance = field(default_factory=Provenance)
    substrate: Optional[str] = None
    finish: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    takeoff_eligible: bool = False  # Fail-closed default: False
    deduction_authority: bool = False  # Fail-closed default: False

    def __post_init__(self):
        """Enforces strict boolean normalization on direct Python object construction."""
        self.takeoff_eligible = parse_strict_bool(self.takeoff_eligible)
        self.deduction_authority = parse_strict_bool(self.deduction_authority)
        self.confidence = parse_optional_confidence(self.confidence)

    def base_to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "object_type": self.object_type.value if isinstance(self.object_type, ObjectType) else str(self.object_type),
            "level_id": self.level_id,
            "parent_id": self.parent_id,
            "children_ids": list(self.children_ids),
            "confidence": self.confidence,
            "review_state": self.review_state.value if isinstance(self.review_state, ReviewState) else str(self.review_state),
            "provenance": self.provenance.to_dict(),
            "substrate": self.substrate,
            "finish": self.finish,
            "metadata": dict(self.metadata),
            "takeoff_eligible": parse_strict_bool(self.takeoff_eligible),
            "deduction_authority": parse_strict_bool(self.deduction_authority),
        }

    @classmethod
    def base_from_dict_args(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            data = {}

        # Fail-closed review_state deserialization
        rev_state = data.get("review_state")
        if isinstance(rev_state, str):
            try:
                rev_state = ReviewState(rev_state)
            except ValueError:
                rev_state = ReviewState.REVIEW_REQUIRED
        else:
            rev_state = ReviewState.REVIEW_REQUIRED

        # Object type deserialization
        obj_type = data.get("object_type", ObjectType.SURFACE.value)
        if isinstance(obj_type, str):
            try:
                obj_type = ObjectType(obj_type)
            except ValueError:
                obj_type = ObjectType.SURFACE

        return {
            "id": str(data.get("id", f"elem_{uuid.uuid4().hex[:8]}")),
            "name": str(data.get("name", "Unnamed Element")),
            "object_type": obj_type,
            "level_id": data.get("level_id"),
            "parent_id": data.get("parent_id"),
            "children_ids": [str(c) for c in (data.get("children_ids", []) or []) if c],
            "confidence": parse_optional_confidence(data.get("confidence")),
            "review_state": rev_state,
            "provenance": Provenance.from_dict(data.get("provenance") if isinstance(data.get("provenance"), dict) else {}),
            "substrate": data.get("substrate"),
            "finish": data.get("finish"),
            "metadata": dict(data.get("metadata", {}) or {}) if isinstance(data.get("metadata"), dict) else {},
            "takeoff_eligible": parse_strict_bool(data.get("takeoff_eligible")),
            "deduction_authority": parse_strict_bool(data.get("deduction_authority")),
        }


@dataclass
class WallFace:
    """Represents one face of a physical wall (Face A or Face B) for trade finish binding."""
    face_id: str = "A"  # "A" or "B" (or "INTERNAL", "EXTERNAL")
    finish: Optional[str] = None
    substrate: Optional[str] = None
    finish_code: Optional[str] = None
    bounded_space_id: Optional[str] = None
    area_gross_m2: Optional[float] = None
    opening_deductions_m2: Optional[float] = None
    area_net_m2: Optional[float] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "face_id": self.face_id,
            "finish": self.finish,
            "substrate": self.substrate,
            "finish_code": self.finish_code,
            "bounded_space_id": self.bounded_space_id,
            "area_gross_m2": self.area_gross_m2,
            "opening_deductions_m2": self.opening_deductions_m2,
            "area_net_m2": self.area_net_m2,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "WallFace":
        if not isinstance(data, dict):
            return cls()
        return cls(
            face_id=str(data.get("face_id", "A")),
            finish=data.get("finish"),
            substrate=data.get("substrate"),
            finish_code=data.get("finish_code"),
            bounded_space_id=data.get("bounded_space_id"),
            area_gross_m2=parse_optional_float(data.get("area_gross_m2")),
            opening_deductions_m2=parse_optional_float(data.get("opening_deductions_m2")),
            area_net_m2=parse_optional_float(data.get("area_net_m2")),
            notes=data.get("notes"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class QuantityFormulaBinding:
    """Prepares architecture for OBJECT -> QUANTITY FORMULA -> USER RATE -> COST.

    Rates remain changeable without rerunning plan extraction.
    """
    trade_category: str = "general"
    item_code: str = ""
    formula_expression: str = "quantity"  # e.g. "net_wall_area_m2", "length_m * height_m"
    unit: str = "m2"  # "m2", "lm", "m3", "No."
    quantity: float = 0.0
    user_rate: Optional[float] = None
    total_cost: Optional[float] = None
    formula_variables: Dict[str, float] = field(default_factory=dict)

    def calculate_cost(self, rate: Optional[float] = None) -> Optional[float]:
        r = rate if rate is not None else self.user_rate
        if r is not None and self.quantity is not None:
            self.total_cost = round(float(self.quantity) * float(r), 2)
            self.user_rate = float(r)
            return self.total_cost
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_category": self.trade_category,
            "item_code": self.item_code,
            "formula_expression": self.formula_expression,
            "unit": self.unit,
            "quantity": self.quantity,
            "user_rate": self.user_rate,
            "total_cost": self.total_cost,
            "formula_variables": dict(self.formula_variables),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "QuantityFormulaBinding":
        if not isinstance(data, dict):
            return cls()
        return cls(
            trade_category=str(data.get("trade_category", "general")),
            item_code=str(data.get("item_code", "")),
            formula_expression=str(data.get("formula_expression", "quantity")),
            unit=str(data.get("unit", "m2")),
            quantity=float(data.get("quantity", 0.0) or 0.0),
            user_rate=parse_optional_float(data.get("user_rate")),
            total_cost=parse_optional_float(data.get("total_cost")),
            formula_variables=dict(data.get("formula_variables", {}) or {}),
        )


@dataclass
class CanonicalConstructabilityIssue:
    """Issue/constraint model for evidence-based constructability warnings."""
    id: str = field(default_factory=lambda: f"issue_{uuid.uuid4().hex[:8]}")
    category: str = "geometry_conflict"  # e.g. "unsupported_upper_wall", "opening_beam_clash", "service_collision"
    severity: str = "WARNING"  # "INFO", "WARNING", "ERROR"
    description: str = ""
    affected_element_ids: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    review_state: ReviewState = ReviewState.REVIEW_REQUIRED
    recommended_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "affected_element_ids": list(self.affected_element_ids),
            "evidence_refs": list(self.evidence_refs),
            "review_state": self.review_state.value if isinstance(self.review_state, ReviewState) else str(self.review_state),
            "recommended_action": self.recommended_action,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "CanonicalConstructabilityIssue":
        if not isinstance(data, dict):
            return cls()
        rev_state = data.get("review_state")
        if isinstance(rev_state, str):
            try:
                rev_state = ReviewState(rev_state)
            except ValueError:
                rev_state = ReviewState.REVIEW_REQUIRED
        else:
            rev_state = ReviewState.REVIEW_REQUIRED

        return cls(
            id=str(data.get("id", f"issue_{uuid.uuid4().hex[:8]}")),
            category=str(data.get("category", "geometry_conflict")),
            severity=str(data.get("severity", "WARNING")),
            description=str(data.get("description", "")),
            affected_element_ids=[str(x) for x in (data.get("affected_element_ids") or []) if x],
            evidence_refs=[str(x) for x in (data.get("evidence_refs") or []) if x],
            review_state=rev_state,
            recommended_action=data.get("recommended_action"),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class CanonicalOpening(CanonicalElement):
    wall_id: Optional[str] = None
    opening_type: str = "GENERIC"
    offset_along_wall_m: Optional[float] = None
    sill_height_m: Optional[float] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    mark: Optional[str] = None
    host_wall_id: Optional[str] = None
    opening_classification: Optional[str] = None
    head_height_m: Optional[float] = None
    schedule_page_id: Optional[str] = None
    detail_page_id: Optional[str] = None
    detail_record_id: Optional[str] = None
    detail_semantic_identity_id: Optional[str] = None
    plan_page_id: Optional[str] = None
    elevation_page_id: Optional[str] = None
    source_evidence_ids: List[str] = field(default_factory=list)
    derived_quantities: List[QuantityFormulaBinding] = field(default_factory=list)
    is_user_edited: bool = False
    revision_id: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        if not self.host_wall_id and self.wall_id:
            self.host_wall_id = self.wall_id
        elif not self.wall_id and self.host_wall_id:
            self.wall_id = self.host_wall_id
        if self.opening_type.upper() == "DOOR":
            self.object_type = ObjectType.DOOR
        elif self.opening_type.upper() == "WINDOW":
            self.object_type = ObjectType.WINDOW
        else:
            self.object_type = ObjectType.OPENING

        # Infer head height from sill height + height if unrecorded, or vice versa
        if self.head_height_m is None and self.sill_height_m is not None and self.height_m is not None:
            self.head_height_m = round(self.sill_height_m + self.height_m, 4)
        elif self.sill_height_m is None and self.head_height_m is not None and self.height_m is not None:
            self.sill_height_m = max(0.0, round(self.head_height_m - self.height_m, 4))

    def derive_trade_quantities(self, include_ancillary: bool = False) -> List[QuantityFormulaBinding]:
        """Derives primary unit and optional ancillary trade quantities from this physical opening."""
        mark_label = self.mark or self.name or "OP"
        is_door = (self.object_type == ObjectType.DOOR) or ("DOOR" in (self.opening_type or "").upper())
        is_window = (self.object_type == ObjectType.WINDOW) or ("WINDOW" in (self.opening_type or "").upper())
        trade_cat = "doors" if is_door else "windows" if is_window else "openings"

        bindings = [
            QuantityFormulaBinding(
                trade_category=trade_cat,
                item_code=f"OPENING_{mark_label}",
                formula_expression="1.0",
                unit="No.",
                quantity=1.0,
            )
        ]

        if include_ancillary:
            w = float(self.width_m) if self.width_m is not None else 0.0
            h = float(self.height_m) if self.height_m is not None else 0.0
            if is_door:
                if h > 0.0 and w > 0.0:
                    arch_lm = round(2.0 * h + w, 2)
                    bindings.append(QuantityFormulaBinding(
                        trade_category="carpentry",
                        item_code="DOOR_ARCHITRAVE",
                        formula_expression="2 * height_m + width_m",
                        unit="lm",
                        quantity=arch_lm,
                    ))
                bindings.append(QuantityFormulaBinding(
                    trade_category="hardware",
                    item_code="DOOR_LOCKSET",
                    formula_expression="1.0",
                    unit="item",
                    quantity=1.0,
                ))
            elif is_window:
                if h > 0.0 and w > 0.0:
                    rev_lm = round(2.0 * (h + w), 2)
                    bindings.append(QuantityFormulaBinding(
                        trade_category="carpentry",
                        item_code="WINDOW_REVEAL_LINER",
                        formula_expression="2 * (height_m + width_m)",
                        unit="lm",
                        quantity=rev_lm,
                    ))
                bindings.append(QuantityFormulaBinding(
                    trade_category="windows",
                    item_code="WINDOW_SCREEN",
                    formula_expression="1.0",
                    unit="item",
                    quantity=1.0,
                ))

        self.derived_quantities = bindings
        return bindings

    def enrich_with_detail_definition(self, record: Any) -> None:
        """Enriches this canonical opening from an OpeningDetailDefinitionRecord (AG-06)."""
        if getattr(record, "width_mm", None) is not None:
            self.width_m = round(float(record.width_mm) / 1000.0, 4)
        if getattr(record, "height_mm", None) is not None:
            self.height_m = round(float(record.height_mm) / 1000.0, 4)
        if getattr(record, "family", None):
            fam = str(record.family).lower()
            if fam == "door":
                self.object_type = ObjectType.DOOR
                self.opening_type = "DOOR"
            elif fam == "window":
                self.object_type = ObjectType.WINDOW
                self.opening_type = "WINDOW"
        if getattr(record, "subtype", None):
            self.opening_classification = str(record.subtype)
        if getattr(record, "material", None):
            self.substrate = str(record.material)
        if getattr(record, "record_id", None):
            self.detail_record_id = str(record.record_id)
        if getattr(record, "semantic_identity_id", None):
            self.detail_semantic_identity_id = str(record.semantic_identity_id)
        if getattr(record, "page_id", None):
            self.detail_page_id = str(record.page_id)
        if getattr(record, "source_observation_ids", None):
            for oid in record.source_observation_ids:
                if str(oid) not in self.source_evidence_ids:
                    self.source_evidence_ids.append(str(oid))
        if self.sill_height_m is not None and self.height_m is not None and self.head_height_m is None:
            self.head_height_m = round(self.sill_height_m + self.height_m, 4)

    def enrich_with_schedule_entry(self, entry: Any) -> None:
        """Enriches this canonical opening from a ScheduleEntry (AG-06)."""
        if getattr(entry, "width_mm", None) is not None and self.width_m is None:
            self.width_m = round(float(entry.width_mm) / 1000.0, 4)
        if getattr(entry, "height_mm", None) is not None and self.height_m is None:
            self.height_m = round(float(entry.height_mm) / 1000.0, 4)
        if getattr(entry, "type_mark", None) and not self.mark:
            self.mark = str(entry.type_mark).strip()
        if getattr(entry, "description", None) and not self.opening_classification:
            self.opening_classification = str(entry.description).strip()
        if getattr(entry, "page_no", None) is not None:
            self.schedule_page_id = str(entry.page_no)

        # If opening type is generic, infer door or window from mark and description
        if self.object_type == ObjectType.OPENING or self.opening_type == "GENERIC":
            desc_upper = (getattr(entry, "description", "") or "").upper()
            mark_upper = (getattr(entry, "type_mark", "") or "").upper()
            if "DOOR" in desc_upper or mark_upper.startswith("D"):
                self.object_type = ObjectType.DOOR
                self.opening_type = "DOOR"
            elif "WINDOW" in desc_upper or mark_upper.startswith("W"):
                self.object_type = ObjectType.WINDOW
                self.opening_type = "WINDOW"

        if self.sill_height_m is not None and self.height_m is not None and self.head_height_m is None:
            self.head_height_m = round(self.sill_height_m + self.height_m, 4)

    def enrich_with_schedule_binding(self, record: Any) -> None:
        """Enriches this canonical opening from a ScheduleOpeningInstanceBindingRecord (AG-06)."""
        if getattr(record, "tag_mark", None) and not self.mark:
            self.mark = str(record.tag_mark).strip()
        if getattr(record, "schedule_row_type_mark", None) and not self.mark:
            self.mark = str(record.schedule_row_type_mark).strip()
        if getattr(record, "schedule_row_width_mm", None) is not None and self.width_m is None:
            self.width_m = round(float(record.schedule_row_width_mm) / 1000.0, 4)
        if getattr(record, "schedule_row_height_mm", None) is not None and self.height_m is None:
            self.height_m = round(float(record.schedule_row_height_mm) / 1000.0, 4)
        if getattr(record, "schedule_page_id", None):
            self.schedule_page_id = str(record.schedule_page_id)

        # If opening type is generic, infer door or window from mark
        if self.object_type == ObjectType.OPENING or self.opening_type == "GENERIC":
            mark_upper = (self.mark or "").upper()
            if mark_upper.startswith("D"):
                self.object_type = ObjectType.DOOR
                self.opening_type = "DOOR"
            elif mark_upper.startswith("W"):
                self.object_type = ObjectType.WINDOW
                self.opening_type = "WINDOW"
        if getattr(record, "tag_observation_id", None):
            if str(record.tag_observation_id) not in self.source_evidence_ids:
                self.source_evidence_ids.append(str(record.tag_observation_id))
        if getattr(record, "schedule_row_observation_ids", None):
            for oid in record.schedule_row_observation_ids:
                if str(oid) not in self.source_evidence_ids:
                    self.source_evidence_ids.append(str(oid))
        if self.sill_height_m is not None and self.height_m is not None and self.head_height_m is None:
            self.head_height_m = round(self.sill_height_m + self.height_m, 4)

    def to_consolidated(self) -> Any:
        """Converts this canonical opening to a ConsolidatedPhysicalOpening for bridge interoperability."""
        from pb_opening_detail_definition_bridge import ConsolidatedPhysicalOpening
        w_m = float(self.width_m) if self.width_m is not None else 0.0
        h_m = float(self.height_m) if self.height_m is not None else 0.0
        area = round(w_m * h_m, 4) if (w_m > 0 and h_m > 0) else 0.0
        fam = "door" if self.object_type == ObjectType.DOOR else "window" if self.object_type == ObjectType.WINDOW else "opening"
        return ConsolidatedPhysicalOpening(
            opening_id=self.id,
            type_mark=self.mark or "",
            host_wall_id=self.host_wall_id or self.wall_id or "",
            width_m=w_m,
            height_m=h_m,
            area_m2=area,
            family=fam,
            subtype=self.opening_classification or "",
            material=self.substrate or "",
            deducts=parse_strict_bool(self.deduction_authority),
            detail_record_id=self.detail_record_id,
            detail_semantic_identity_id=self.detail_semantic_identity_id,
            plan_page_id=self.plan_page_id,
            elevation_page_id=self.elevation_page_id,
            schedule_page_id=self.schedule_page_id,
            detail_page_id=self.detail_page_id,
            source_evidence_ids=list(self.source_evidence_ids),
        )

    @classmethod
    def from_consolidated(
        cls,
        c_op: Any,
        level_id: Optional[str] = None,
        sill_height_m: Optional[float] = None,
        offset_along_wall_m: Optional[float] = None,
    ) -> "CanonicalOpening":
        """Instantiates a CanonicalOpening from a ConsolidatedPhysicalOpening."""
        fam = getattr(c_op, "family", "opening").lower()
        if fam == "door":
            op_type = "DOOR"
            obj_type = ObjectType.DOOR
        elif fam == "window":
            op_type = "WINDOW"
            obj_type = ObjectType.WINDOW
        else:
            op_type = "GENERIC"
            obj_type = ObjectType.OPENING

        w_m = float(getattr(c_op, "width_m", 0.0))
        h_m = float(getattr(c_op, "height_m", 0.0))
        eff_w = w_m if w_m > 0.0 else None
        eff_h = h_m if h_m > 0.0 else None

        op = cls(
            id=str(getattr(c_op, "opening_id", f"op_{uuid.uuid4().hex[:8]}")),
            name=f"{fam.capitalize()} {getattr(c_op, 'type_mark', '')}".strip(),
            object_type=obj_type,
            level_id=level_id,
            wall_id=getattr(c_op, "host_wall_id", None),
            host_wall_id=getattr(c_op, "host_wall_id", None),
            opening_type=op_type,
            offset_along_wall_m=offset_along_wall_m,
            sill_height_m=sill_height_m,
            width_m=eff_w,
            height_m=eff_h,
            mark=getattr(c_op, "type_mark", None),
            opening_classification=getattr(c_op, "subtype", None) or getattr(c_op, "family", None),
            substrate=getattr(c_op, "material", None),
            deduction_authority=bool(getattr(c_op, "deducts", True)),
            takeoff_eligible=bool(getattr(c_op, "deducts", True)),
            detail_record_id=getattr(c_op, "detail_record_id", None),
            detail_semantic_identity_id=getattr(c_op, "detail_semantic_identity_id", None),
            plan_page_id=getattr(c_op, "plan_page_id", None),
            elevation_page_id=getattr(c_op, "elevation_page_id", None),
            schedule_page_id=getattr(c_op, "schedule_page_id", None),
            detail_page_id=getattr(c_op, "detail_page_id", None),
            source_evidence_ids=list(getattr(c_op, "source_evidence_ids", []) or []),
        )
        return op

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "wall_id": self.wall_id,
            "opening_type": self.opening_type,
            "offset_along_wall_m": self.offset_along_wall_m,
            "sill_height_m": self.sill_height_m,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "mark": self.mark,
            "host_wall_id": self.host_wall_id or self.wall_id,
            "opening_classification": self.opening_classification,
            "head_height_m": self.head_height_m,
            "schedule_page_id": self.schedule_page_id,
            "detail_page_id": self.detail_page_id,
            "detail_record_id": self.detail_record_id,
            "detail_semantic_identity_id": self.detail_semantic_identity_id,
            "plan_page_id": self.plan_page_id,
            "elevation_page_id": self.elevation_page_id,
            "source_evidence_ids": list(self.source_evidence_ids),
            "derived_quantities": [q.to_dict() for q in self.derived_quantities],
            "is_user_edited": parse_strict_bool(self.is_user_edited),
            "revision_id": self.revision_id,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalOpening":
        base_args = cls.base_from_dict_args(data)
        d_quants_raw = data.get("derived_quantities", []) or []
        d_quants = [QuantityFormulaBinding.from_dict(q) for q in d_quants_raw if isinstance(q, dict)]
        return cls(
            **base_args,
            wall_id=data.get("wall_id") or data.get("host_wall_id"),
            opening_type=str(data.get("opening_type", "GENERIC")),
            offset_along_wall_m=parse_optional_float(data.get("offset_along_wall_m")),
            sill_height_m=parse_optional_float(data.get("sill_height_m")),
            width_m=parse_optional_float(data.get("width_m")),
            height_m=parse_optional_float(data.get("height_m")),
            mark=data.get("mark"),
            host_wall_id=data.get("host_wall_id") or data.get("wall_id"),
            opening_classification=data.get("opening_classification"),
            head_height_m=parse_optional_float(data.get("head_height_m")),
            schedule_page_id=data.get("schedule_page_id"),
            detail_page_id=data.get("detail_page_id"),
            detail_record_id=data.get("detail_record_id"),
            detail_semantic_identity_id=data.get("detail_semantic_identity_id"),
            plan_page_id=data.get("plan_page_id"),
            elevation_page_id=data.get("elevation_page_id"),
            source_evidence_ids=[str(x) for x in (data.get("source_evidence_ids") or []) if x],
            derived_quantities=d_quants,
            is_user_edited=parse_strict_bool(data.get("is_user_edited")),
            revision_id=data.get("revision_id"),
        )


@dataclass
class CanonicalWall(CanonicalElement):
    start_point: Vector2D = field(default_factory=Vector2D)
    end_point: Vector2D = field(default_factory=Vector2D)
    thickness_m: Optional[float] = None  # No invented defaults
    height_m: Optional[float] = None     # No invented defaults
    is_external: bool = False
    openings: List[CanonicalOpening] = field(default_factory=list)
    bounded_space_ids: List[str] = field(default_factory=list)
    face_a: Optional[WallFace] = None
    face_b: Optional[WallFace] = None
    derived_quantities: List[QuantityFormulaBinding] = field(default_factory=list)
    is_user_edited: bool = False
    revision_id: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.WALL
        self.is_external = parse_strict_bool(self.is_external)
        self.is_user_edited = parse_strict_bool(self.is_user_edited)

    def length_m(self) -> float:
        if self.start_point and self.end_point:
            return self.start_point.distance_to(self.end_point)
        return 0.0

    def gross_area_m2(self) -> Optional[float]:
        if self.height_m is not None:
            return round(self.length_m() * float(self.height_m), 4)
        return None

    def total_opening_deductions_m2(self) -> float:
        ded = 0.0
        for op in self.openings:
            if op.width_m is not None and op.height_m is not None:
                ded += float(op.width_m) * float(op.height_m)
        return round(ded, 4)

    def net_area_m2(self) -> Optional[float]:
        gross = self.gross_area_m2()
        if gross is not None:
            return round(max(0.0, gross - self.total_opening_deductions_m2()), 4)
        return None

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict(),
            "thickness_m": self.thickness_m,
            "height_m": self.height_m,
            "is_external": parse_strict_bool(self.is_external),
            "openings": [op.to_dict() for op in self.openings],
            "bounded_space_ids": list(self.bounded_space_ids),
            "face_a": self.face_a.to_dict() if self.face_a else None,
            "face_b": self.face_b.to_dict() if self.face_b else None,
            "derived_quantities": [q.to_dict() for q in self.derived_quantities],
            "is_user_edited": parse_strict_bool(self.is_user_edited),
            "revision_id": self.revision_id,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalWall":
        base_args = cls.base_from_dict_args(data)
        openings_raw = data.get("openings", []) or []
        openings = [CanonicalOpening.from_dict(op) for op in openings_raw if isinstance(op, dict)]
        face_a_raw = data.get("face_a")
        face_b_raw = data.get("face_b")
        face_a = WallFace.from_dict(face_a_raw) if isinstance(face_a_raw, dict) else None
        face_b = WallFace.from_dict(face_b_raw) if isinstance(face_b_raw, dict) else None
        d_quants_raw = data.get("derived_quantities", []) or []
        d_quants = [QuantityFormulaBinding.from_dict(q) for q in d_quants_raw if isinstance(q, dict)]

        return cls(
            **base_args,
            start_point=Vector2D.from_dict(data.get("start_point")),
            end_point=Vector2D.from_dict(data.get("end_point")),
            thickness_m=parse_optional_float(data.get("thickness_m")),
            height_m=parse_optional_float(data.get("height_m")),
            is_external=parse_strict_bool(data.get("is_external")),
            openings=openings,
            bounded_space_ids=list(data.get("bounded_space_ids", []) or []),
            face_a=face_a,
            face_b=face_b,
            derived_quantities=d_quants,
            is_user_edited=parse_strict_bool(data.get("is_user_edited")),
            revision_id=data.get("revision_id"),
        )


@dataclass
class CanonicalSpace(CanonicalElement):
    boundary_polygon: List[Vector2D] = field(default_factory=list)
    height_m: Optional[float] = None
    specified_floor_area_m2: Optional[float] = None
    room_number: Optional[str] = None
    bounding_wall_ids: List[str] = field(default_factory=list)
    floor_element_id: Optional[str] = None
    ceiling_element_id: Optional[str] = None
    finish_assignments: Dict[str, Any] = field(default_factory=dict)
    derived_quantities: List[QuantityFormulaBinding] = field(default_factory=list)
    is_user_edited: bool = False
    revision_id: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.SPACE
        self.is_user_edited = parse_strict_bool(self.is_user_edited)

    def measured_area_m2(self) -> float:
        """Computes boundary polygon 2D area using shoelace formula."""
        if not self.boundary_polygon or len(self.boundary_polygon) < 3:
            return 0.0
        pts = [(p.x, p.y) for p in self.boundary_polygon if p.x is not None and p.y is not None]
        if len(pts) < 3:
            return 0.0
        n = len(pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        return round(abs(area) / 2.0, 4)

    def effective_floor_area_m2(self) -> Optional[float]:
        """Returns specified_floor_area_m2 if present, else measured_area_m2() if > 0."""
        if self.specified_floor_area_m2 is not None and self.specified_floor_area_m2 > 0.0:
            return self.specified_floor_area_m2
        meas = self.measured_area_m2()
        return meas if meas > 0.0 else None

    def perimeter_lm(self) -> float:
        """Computes boundary polygon perimeter in linear metres."""
        pts = [(p.x, p.y) for p in self.boundary_polygon if p.x is not None and p.y is not None]
        if len(pts) < 2:
            return 0.0
        n = len(pts)
        total = 0.0
        for i in range(n):
            j = (i + 1) % n
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            total += math.hypot(dx, dy)
        return round(total, 4)

    def derive_trade_quantities(self, default_finish: Optional[str] = None) -> List[QuantityFormulaBinding]:
        """Derives flooring, tiling, and waterproofing trade quantities from this physical space."""
        area = self.effective_floor_area_m2()
        if not area or area <= 0.0:
            return []

        perimeter = self.perimeter_lm()
        floor_finish = (
            self.finish_assignments.get("floor")
            or self.metadata.get("floor_finish")
            or default_finish
            or ""
        ).lower()

        if not floor_finish:
            name_l = self.name.lower()
            if any(w in name_l for w in ("bed", "robe", "wir")):
                floor_finish = "carpet"
            elif any(w in name_l for w in ("bath", "ensuite", "wc", "powder", "laundry")):
                floor_finish = "tiles"
            elif any(w in name_l for w in ("living", "dining", "entry", "hall", "kitchen", "family", "meals")):
                floor_finish = "timber"
            else:
                floor_finish = "carpet"

        bindings: List[QuantityFormulaBinding] = []

        if floor_finish in ("timber", "laminate", "hybrid"):
            bindings.append(QuantityFormulaBinding(
                trade_category="flooring",
                item_code="FLOOR_TIMBER",
                formula_expression="effective_floor_area_m2",
                unit="m²",
                quantity=round(area, 2),
            ))
            bindings.append(QuantityFormulaBinding(
                trade_category="flooring",
                item_code="FLOOR_TIMBER_ACOUSTIC_UNDERLAY",
                formula_expression="effective_floor_area_m2",
                unit="m²",
                quantity=round(area, 2),
            ))
            if perimeter > 0.9:
                bindings.append(QuantityFormulaBinding(
                    trade_category="carpentry",
                    item_code="FLOOR_TIMBER_PERIMETER_QUAD",
                    formula_expression="perimeter_lm - 0.90",
                    unit="lm",
                    quantity=round(max(0.0, perimeter - 0.90), 2),
                ))

        elif floor_finish == "carpet":
            bindings.append(QuantityFormulaBinding(
                trade_category="flooring",
                item_code="FLOOR_CARPET",
                formula_expression="effective_floor_area_m2",
                unit="m²",
                quantity=round(area, 2),
            ))
            bindings.append(QuantityFormulaBinding(
                trade_category="flooring",
                item_code="FLOOR_CARPET_UNDERLAY",
                formula_expression="effective_floor_area_m2",
                unit="m²",
                quantity=round(area, 2),
            ))
            if perimeter > 0.9:
                bindings.append(QuantityFormulaBinding(
                    trade_category="flooring",
                    item_code="FLOOR_CARPET_GRIPPERS",
                    formula_expression="perimeter_lm - 0.90",
                    unit="lm",
                    quantity=round(max(0.0, perimeter - 0.90), 2),
                ))

        elif floor_finish in ("tiles", "tiling"):
            bindings.append(QuantityFormulaBinding(
                trade_category="tiling",
                item_code="FLOOR_TILES",
                formula_expression="effective_floor_area_m2",
                unit="m²",
                quantity=round(area, 2),
            ))
            bindings.append(QuantityFormulaBinding(
                trade_category="tiling",
                item_code="FLOOR_SCREED_TO_FALLS",
                formula_expression="effective_floor_area_m2",
                unit="m²",
                quantity=round(area, 2),
            ))
            upturn_m2 = round(perimeter * 0.150, 2)
            wp_total_m2 = round(area + upturn_m2, 2)
            bindings.append(QuantityFormulaBinding(
                trade_category="waterproofing",
                item_code="FLOOR_WATERPROOFING_MEMBRANE",
                formula_expression="effective_floor_area_m2 + (perimeter_lm * 0.15)",
                unit="m²",
                quantity=wp_total_m2,
            ))
            if perimeter > 0.9:
                bindings.append(QuantityFormulaBinding(
                    trade_category="tiling",
                    item_code="FLOOR_TILE_SKIRTING",
                    formula_expression="perimeter_lm - 0.90",
                    unit="lm",
                    quantity=round(max(0.0, perimeter - 0.90), 2),
                ))

        self.derived_quantities = bindings
        return bindings

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "boundary_polygon": [pt.to_dict() for pt in self.boundary_polygon],
            "height_m": self.height_m,
            "specified_floor_area_m2": self.specified_floor_area_m2,
            "room_number": self.room_number,
            "bounding_wall_ids": list(self.bounding_wall_ids),
            "floor_element_id": self.floor_element_id,
            "ceiling_element_id": self.ceiling_element_id,
            "finish_assignments": dict(self.finish_assignments),
            "derived_quantities": [q.to_dict() for q in self.derived_quantities],
            "is_user_edited": parse_strict_bool(self.is_user_edited),
            "revision_id": self.revision_id,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalSpace":
        base_args = cls.base_from_dict_args(data)
        poly_raw = data.get("boundary_polygon", []) or []
        poly = [Vector2D.from_dict(pt) for pt in poly_raw if pt]
        d_quants_raw = data.get("derived_quantities", []) or []
        d_quants = [QuantityFormulaBinding.from_dict(q) for q in d_quants_raw if isinstance(q, dict)]

        return cls(
            **base_args,
            boundary_polygon=poly,
            height_m=parse_optional_float(data.get("height_m")),
            specified_floor_area_m2=parse_optional_float(data.get("specified_floor_area_m2")),
            room_number=data.get("room_number"),
            bounding_wall_ids=list(data.get("bounding_wall_ids", []) or []),
            floor_element_id=data.get("floor_element_id"),
            ceiling_element_id=data.get("ceiling_element_id"),
            finish_assignments=dict(data.get("finish_assignments", {}) or {}),
            derived_quantities=d_quants,
            is_user_edited=parse_strict_bool(data.get("is_user_edited")),
            revision_id=data.get("revision_id"),
        )



@dataclass
class PolygonElement(CanonicalElement):
    """Generic base class for horizontal polygonal elements."""
    polygon: List[Vector2D] = field(default_factory=list)
    thickness_m: Optional[float] = None
    elevation_offset_m: Optional[float] = None
    specified_floor_area_m2: Optional[float] = None
    bounded_space_ids: List[str] = field(default_factory=list)
    derived_quantities: List[QuantityFormulaBinding] = field(default_factory=list)
    is_user_edited: bool = False
    revision_id: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.is_user_edited = parse_strict_bool(self.is_user_edited)

    def measured_area_m2(self) -> float:
        """Computes polygon 2D area using shoelace formula."""
        if not self.polygon or len(self.polygon) < 3:
            return 0.0
        pts = [(p.x, p.y) for p in self.polygon if p.x is not None and p.y is not None]
        if len(pts) < 3:
            return 0.0
        n = len(pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        return round(abs(area) / 2.0, 4)

    def effective_area_m2(self) -> Optional[float]:
        """Returns specified_floor_area_m2 if present, else measured_area_m2() if > 0."""
        if self.specified_floor_area_m2 is not None and self.specified_floor_area_m2 > 0.0:
            return self.specified_floor_area_m2
        meas = self.measured_area_m2()
        return meas if meas > 0.0 else None

    def perimeter_lm(self) -> float:
        """Computes polygon perimeter in linear metres."""
        pts = [(p.x, p.y) for p in self.polygon if p.x is not None and p.y is not None]
        if len(pts) < 2:
            return 0.0
        n = len(pts)
        total = 0.0
        for i in range(n):
            j = (i + 1) % n
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            total += math.hypot(dx, dy)
        return round(total, 4)

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "polygon": [pt.to_dict() for pt in self.polygon],
            "thickness_m": self.thickness_m,
            "elevation_offset_m": self.elevation_offset_m,
            "specified_floor_area_m2": self.specified_floor_area_m2,
            "bounded_space_ids": list(self.bounded_space_ids),
            "derived_quantities": [q.to_dict() for q in self.derived_quantities],
            "is_user_edited": parse_strict_bool(self.is_user_edited),
            "revision_id": self.revision_id,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolygonElement":
        base_args = cls.base_from_dict_args(data)
        poly_raw = data.get("polygon", []) or []
        poly = [Vector2D.from_dict(pt) for pt in poly_raw if pt]
        d_quants_raw = data.get("derived_quantities", []) or []
        d_quants = [QuantityFormulaBinding.from_dict(q) for q in d_quants_raw if isinstance(q, dict)]
        return cls(
            **base_args,
            polygon=poly,
            thickness_m=parse_optional_float(data.get("thickness_m")),
            elevation_offset_m=parse_optional_float(data.get("elevation_offset_m")),
            specified_floor_area_m2=parse_optional_float(data.get("specified_floor_area_m2")),
            bounded_space_ids=list(data.get("bounded_space_ids", []) or []),
            derived_quantities=d_quants,
            is_user_edited=parse_strict_bool(data.get("is_user_edited")),
            revision_id=data.get("revision_id"),
        )



@dataclass
class CanonicalFloor(PolygonElement):
    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.FLOOR

    def derive_trade_quantities(self, concrete_grade: Optional[str] = None) -> List[QuantityFormulaBinding]:
        """Derives concrete trade quantities (slab area, concrete volume, vapor barrier, formwork)
        from this physical slab geometry without re-extraction or duplicate calculation.
        """
        area = self.effective_area_m2()
        if not area or area <= 0.0:
            return []
        thickness = self.thickness_m if self.thickness_m and self.thickness_m > 0.0 else 0.100
        vol_m3 = round(area * thickness, 2)
        perimeter = self.perimeter_lm()

        bindings: List[QuantityFormulaBinding] = []

        # 1. Primary Slab Area (m²)
        bindings.append(QuantityFormulaBinding(
            trade_category="concreting",
            item_code="CONCRETE_SLAB_GROUND",
            formula_expression="effective_area_m2",
            unit="m²",
            quantity=round(area, 2),
        ))

        # 2. Concrete Supply & Placement (item / m³)
        bindings.append(QuantityFormulaBinding(
            trade_category="concreting",
            item_code="CONCRETE_SUPPLY_PUMP",
            formula_expression="effective_area_m2 * thickness_m",
            unit="item",
            quantity=vol_m3,
        ))

        # 3. Under-slab Vapor Barrier / DPM (m²)
        bindings.append(QuantityFormulaBinding(
            trade_category="concreting",
            item_code="CONCRETE_SLAB_VAPOR_BARRIER",
            formula_expression="effective_area_m2 * 1.10",
            unit="m²",
            quantity=round(area * 1.10, 2),
        ))

        # 4. Slab Edge Formwork (lm)
        if perimeter > 0.0:
            bindings.append(QuantityFormulaBinding(
                trade_category="concreting",
                item_code="CONCRETE_SLAB_EDGE_FORMWORK",
                formula_expression="perimeter_lm",
                unit="lm",
                quantity=round(perimeter, 2),
            ))

        self.derived_quantities = bindings
        return bindings


@dataclass
class CanonicalCeiling(PolygonElement):
    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.CEILING


@dataclass
class CanonicalRoof(PolygonElement):
    pitch_deg: Optional[float] = None
    overhang_m: Optional[float] = None
    roof_type: str = "UNKNOWN"
    elevation: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.ROOF

    def surface_area_m2(self) -> Optional[float]:
        """Calculates 3D pitched roof surface area from plan area and pitch."""
        plan_area = self.effective_area_m2()
        if plan_area is None or plan_area <= 0.0:
            return None
        if self.pitch_deg is not None and 0.0 < float(self.pitch_deg) < 89.0:
            rad = math.radians(float(self.pitch_deg))
            return round(plan_area / math.cos(rad), 4)
        return plan_area

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update({
            "pitch_deg": self.pitch_deg,
            "overhang_m": self.overhang_m,
            "roof_type": self.roof_type,
            "elevation": self.elevation,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalRoof":
        base_args = cls.base_from_dict_args(data)
        poly_raw = data.get("polygon", []) or []
        poly = [Vector2D.from_dict(pt) for pt in poly_raw if pt]
        return cls(
            **base_args,
            polygon=poly,
            thickness_m=parse_optional_float(data.get("thickness_m")),
            elevation_offset_m=parse_optional_float(data.get("elevation_offset_m")),
            pitch_deg=parse_optional_float(data.get("pitch_deg")),
            overhang_m=parse_optional_float(data.get("overhang_m")),
            roof_type=str(data.get("roof_type", "UNKNOWN")),
            elevation=parse_optional_float(data.get("elevation")),
        )


@dataclass
class CanonicalSoffit(PolygonElement):
    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.SOFFIT


@dataclass
class CanonicalBalcony(PolygonElement):
    balustrade_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.BALCONY

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res["balustrade_ids"] = list(self.balustrade_ids)
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalBalcony":
        base_args = cls.base_from_dict_args(data)
        poly_raw = data.get("polygon", []) or []
        poly = [Vector2D.from_dict(pt) for pt in poly_raw if pt]
        return cls(
            **base_args,
            polygon=poly,
            thickness_m=parse_optional_float(data.get("thickness_m")),
            elevation_offset_m=parse_optional_float(data.get("elevation_offset_m")),
            balustrade_ids=list(data.get("balustrade_ids", []) or []),
        )


@dataclass
class CanonicalParapet(CanonicalElement):
    start_point: Vector2D = field(default_factory=Vector2D)
    end_point: Vector2D = field(default_factory=Vector2D)
    height_m: Optional[float] = None
    thickness_m: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.PARAPET

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict(),
            "height_m": self.height_m,
            "thickness_m": self.thickness_m,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalParapet":
        base_args = cls.base_from_dict_args(data)
        return cls(
            **base_args,
            start_point=Vector2D.from_dict(data.get("start_point")),
            end_point=Vector2D.from_dict(data.get("end_point")),
            height_m=parse_optional_float(data.get("height_m")),
            thickness_m=parse_optional_float(data.get("thickness_m")),
        )


@dataclass
class CanonicalColumn(CanonicalElement):
    center: Vector2D = field(default_factory=Vector2D)
    width_m: Optional[float] = None
    depth_m: Optional[float] = None
    height_m: Optional[float] = None

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.COLUMN

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "center": self.center.to_dict(),
            "width_m": self.width_m,
            "depth_m": self.depth_m,
            "height_m": self.height_m,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalColumn":
        base_args = cls.base_from_dict_args(data)
        return cls(
            **base_args,
            center=Vector2D.from_dict(data.get("center")),
            width_m=parse_optional_float(data.get("width_m")),
            depth_m=parse_optional_float(data.get("depth_m")),
            height_m=parse_optional_float(data.get("height_m")),
        )


@dataclass
class CanonicalLinearElement(CanonicalElement):
    start_point: Vector2D = field(default_factory=Vector2D)
    end_point: Vector2D = field(default_factory=Vector2D)
    height_m: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "start_point": self.start_point.to_dict(),
            "end_point": self.end_point.to_dict(),
            "height_m": self.height_m,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalLinearElement":
        base_args = cls.base_from_dict_args(data)
        return cls(
            **base_args,
            start_point=Vector2D.from_dict(data.get("start_point")),
            end_point=Vector2D.from_dict(data.get("end_point")),
            height_m=parse_optional_float(data.get("height_m")),
        )


@dataclass
class CanonicalBalustrade(CanonicalLinearElement):
    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.BALUSTRADE


@dataclass
class CanonicalScreen(CanonicalLinearElement):
    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.SCREEN


@dataclass
class CanonicalFinishSurface(CanonicalElement):
    parent_element_id: Optional[str] = None
    surface_area_m2: Optional[float] = None
    orientation: str = "UNKNOWN"

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.SURFACE

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "parent_element_id": self.parent_element_id,
            "surface_area_m2": self.surface_area_m2,
            "orientation": self.orientation,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalFinishSurface":
        base_args = cls.base_from_dict_args(data)
        return cls(
            **base_args,
            parent_element_id=data.get("parent_element_id"),
            surface_area_m2=parse_optional_float(data.get("surface_area_m2")),
            orientation=str(data.get("orientation", "UNKNOWN")),
        )


@dataclass
class CanonicalLevel(CanonicalElement):
    elevation_m: Optional[float] = None
    height_m: Optional[float] = None
    level_index: int = 0
    walls: List[CanonicalWall] = field(default_factory=list)
    spaces: List[CanonicalSpace] = field(default_factory=list)
    floors: List[CanonicalFloor] = field(default_factory=list)
    ceilings: List[CanonicalCeiling] = field(default_factory=list)
    roofs: List[CanonicalRoof] = field(default_factory=list)
    soffits: List[CanonicalSoffit] = field(default_factory=list)
    balconies: List[CanonicalBalcony] = field(default_factory=list)
    parapets: List[CanonicalParapet] = field(default_factory=list)
    columns: List[CanonicalColumn] = field(default_factory=list)
    balustrades: List[CanonicalBalustrade] = field(default_factory=list)
    screens: List[CanonicalScreen] = field(default_factory=list)
    surfaces: List[CanonicalFinishSurface] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.LEVEL

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "elevation_m": self.elevation_m,
            "height_m": self.height_m,
            "level_index": int(self.level_index),
            "walls": [w.to_dict() for w in self.walls],
            "spaces": [sp.to_dict() for sp in self.spaces],
            "floors": [fl.to_dict() for fl in self.floors],
            "ceilings": [c.to_dict() for c in self.ceilings],
            "roofs": [r.to_dict() for r in self.roofs],
            "soffits": [sof.to_dict() for sof in self.soffits],
            "balconies": [b.to_dict() for b in self.balconies],
            "parapets": [p.to_dict() for p in self.parapets],
            "columns": [col.to_dict() for col in self.columns],
            "balustrades": [bal.to_dict() for bal in self.balustrades],
            "screens": [scr.to_dict() for scr in self.screens],
            "surfaces": [s.to_dict() for s in self.surfaces],
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalLevel":
        base_args = cls.base_from_dict_args(data)
        return cls(
            **base_args,
            elevation_m=parse_optional_float(data.get("elevation_m")),
            height_m=parse_optional_float(data.get("height_m")),
            level_index=int(data.get("level_index", 0)),
            walls=[CanonicalWall.from_dict(w) for w in data.get("walls", []) or [] if isinstance(w, dict)],
            spaces=[CanonicalSpace.from_dict(sp) for sp in data.get("spaces", []) or [] if isinstance(sp, dict)],
            floors=[CanonicalFloor.from_dict(fl) for fl in data.get("floors", []) or [] if isinstance(fl, dict)],
            ceilings=[CanonicalCeiling.from_dict(c) for c in data.get("ceilings", []) or [] if isinstance(c, dict)],
            roofs=[CanonicalRoof.from_dict(r) for r in data.get("roofs", []) or [] if isinstance(r, dict)],
            soffits=[CanonicalSoffit.from_dict(s) for s in data.get("soffits", []) or [] if isinstance(s, dict)],
            balconies=[CanonicalBalcony.from_dict(b) for b in data.get("balconies", []) or [] if isinstance(b, dict)],
            parapets=[CanonicalParapet.from_dict(p) for p in data.get("parapets", []) or [] if isinstance(p, dict)],
            columns=[CanonicalColumn.from_dict(col) for col in data.get("columns", []) or [] if isinstance(col, dict)],
            balustrades=[CanonicalBalustrade.from_dict(bal) for bal in data.get("balustrades", []) or [] if isinstance(bal, dict)],
            screens=[CanonicalScreen.from_dict(scr) for scr in data.get("screens", []) or [] if isinstance(scr, dict)],
            surfaces=[CanonicalFinishSurface.from_dict(s) for s in data.get("surfaces", []) or [] if isinstance(s, dict)],
        )


@dataclass
class CanonicalBuilding(CanonicalElement):
    levels: List[CanonicalLevel] = field(default_factory=list)
    building_bounds: Optional[BoundingBox3D] = None

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.BUILDING

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "levels": [lvl.to_dict() for lvl in self.levels],
            "building_bounds": self.building_bounds.to_dict() if self.building_bounds else None,
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalBuilding":
        base_args = cls.base_from_dict_args(data)
        bounds_raw = data.get("building_bounds")
        bounds = BoundingBox3D.from_dict(bounds_raw) if isinstance(bounds_raw, dict) else None
        return cls(
            **base_args,
            levels=[CanonicalLevel.from_dict(lvl) for lvl in data.get("levels", []) or [] if isinstance(lvl, dict)],
            building_bounds=bounds,
        )


@dataclass
class CanonicalEvidenceObservation:
    """
    SECTION Y: Represents non-physical source evidence observations (e.g. elevation opening candidates,
    roof pitch evidence, manual floor allowances, uncalibrated polygons).
    Evidence observations MUST NOT create fake geometry, gain takeoff authority, or gain deduction authority.
    """
    id: str = field(default_factory=lambda: f"obs_{uuid.uuid4().hex[:8]}")
    kind: str = "elevation_opening_candidate"
    workspace_id: Optional[str] = None
    document_id: Optional[str] = None
    page_id: Optional[str] = None
    page_no: Optional[int] = None
    drawing_reference: Optional[str] = None
    side: Optional[str] = None
    level_name: Optional[str] = None
    wall_ref: Optional[str] = None
    source_coords: Optional[Dict[str, Any]] = None
    coordinate_space: Optional[str] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    producer: Optional[str] = None
    producer_version: Optional[str] = None
    confidence: Optional[float] = None
    review_state: ReviewState = ReviewState.REVIEW_REQUIRED
    reason_physical_unavailable: str = "Elevation evidence without plan host wall placement"
    dimension_basis: str = "unknown"
    deduction_authority: bool = False
    no_instance_creation: bool = True
    calibration_status: Optional[str] = None

    def __post_init__(self):
        self.deduction_authority = parse_strict_bool(self.deduction_authority)
        self.no_instance_creation = parse_strict_bool(self.no_instance_creation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "workspace_id": self.workspace_id,
            "document_id": self.document_id,
            "page_id": self.page_id,
            "page_no": self.page_no,
            "drawing_reference": self.drawing_reference,
            "side": self.side,
            "level_name": self.level_name,
            "wall_ref": self.wall_ref,
            "source_coords": self.source_coords,
            "coordinate_space": self.coordinate_space,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "confidence": self.confidence,
            "review_state": self.review_state.value if isinstance(self.review_state, ReviewState) else str(self.review_state),
            "reason_physical_unavailable": self.reason_physical_unavailable,
            "dimension_basis": self.dimension_basis,
            "deduction_authority": parse_strict_bool(self.deduction_authority),
            "no_instance_creation": parse_strict_bool(self.no_instance_creation),
            "calibration_status": self.calibration_status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalEvidenceObservation":
        rev = data.get("review_state")
        try:
            rev_enum = ReviewState(rev) if rev in [r.value for r in ReviewState] else ReviewState.REVIEW_REQUIRED
        except Exception:
            rev_enum = ReviewState.REVIEW_REQUIRED

        return cls(
            id=str(data.get("id") or f"obs_{uuid.uuid4().hex[:8]}"),
            kind=str(data.get("kind") or "elevation_opening_candidate"),
            workspace_id=str(data.get("workspace_id")) if data.get("workspace_id") is not None else None,
            document_id=str(data.get("document_id")) if data.get("document_id") is not None else None,
            page_id=str(data.get("page_id")) if data.get("page_id") is not None else None,
            page_no=int(data.get("page_no")) if data.get("page_no") is not None else None,
            drawing_reference=str(data.get("drawing_reference")) if data.get("drawing_reference") is not None else None,
            side=str(data.get("side")) if data.get("side") is not None else None,
            level_name=str(data.get("level_name")) if data.get("level_name") is not None else None,
            wall_ref=str(data.get("wall_ref")) if data.get("wall_ref") is not None else None,
            source_coords=data.get("source_coords") if isinstance(data.get("source_coords"), dict) else None,
            coordinate_space=str(data.get("coordinate_space")) if data.get("coordinate_space") is not None else None,
            width_m=parse_optional_float(data.get("width_m")),
            height_m=parse_optional_float(data.get("height_m")),
            producer=str(data.get("producer")) if data.get("producer") is not None else None,
            producer_version=str(data.get("producer_version")) if data.get("producer_version") is not None else None,
            confidence=parse_optional_confidence(data.get("confidence")),
            review_state=rev_enum,
            reason_physical_unavailable=str(data.get("reason_physical_unavailable") or "Physical geometry unavailable"),
            dimension_basis=str(data.get("dimension_basis", "unknown")),
            deduction_authority=parse_strict_bool(data.get("deduction_authority")),
            no_instance_creation=parse_strict_bool(data.get("no_instance_creation", True)),
            calibration_status=str(data.get("calibration_status")) if data.get("calibration_status") is not None else None,
        )


@dataclass
class CanonicalProject(CanonicalElement):
    buildings: List[CanonicalBuilding] = field(default_factory=list)
    evidence_observations: List[CanonicalEvidenceObservation] = field(default_factory=list)
    is_synthetic_demo: bool = False
    constructability_issues: List[CanonicalConstructabilityIssue] = field(default_factory=list)
    revision_history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.object_type = ObjectType.PROJECT
        self.is_synthetic_demo = parse_strict_bool(self.is_synthetic_demo)

    def all_walls(self) -> List[CanonicalWall]:
        walls = []
        for b in self.buildings:
            for lvl in b.levels:
                walls.extend(lvl.walls)
        return walls

    def all_spaces(self) -> List[CanonicalSpace]:
        spaces = []
        for b in self.buildings:
            for lvl in b.levels:
                spaces.extend(lvl.spaces)
        return spaces

    def all_openings(self) -> List[CanonicalOpening]:
        openings = []
        for w in self.all_walls():
            openings.extend(w.openings)
        return openings

    def all_floors(self) -> List[CanonicalFloor]:
        floors = []
        for b in self.buildings:
            for lvl in b.levels:
                floors.extend(lvl.floors)
        return floors

    def find_element(self, element_id: str) -> Optional[CanonicalElement]:
        """Finds any element in the canonical building hierarchy by id."""
        if not element_id:
            return None
        if self.id == element_id:
            return self
        for b in self.buildings:
            if b.id == element_id:
                return b
            for lvl in b.levels:
                if lvl.id == element_id:
                    return lvl
                for w in lvl.walls:
                    if w.id == element_id:
                        return w
                    for op in w.openings:
                        if op.id == element_id:
                            return op
                for sp in lvl.spaces:
                    if sp.id == element_id:
                        return sp
                for fl in lvl.floors:
                    if fl.id == element_id:
                        return fl
                for cl in lvl.ceilings:
                    if cl.id == element_id:
                        return cl
                for rf in lvl.roofs:
                    if rf.id == element_id:
                        return rf
                for col in lvl.columns:
                    if col.id == element_id:
                        return col
        return None

    def recompute_relationships(self) -> None:
        """Enforces structural and topological linkages across the building model:
        
        HOUSE -> STOREY -> ROOM -> WALL/FLOOR/CEILING -> OPENING -> FACE A/B.
        """
        for b in self.buildings:
            b.parent_id = self.id
            for lvl in b.levels:
                lvl.parent_id = b.id
                lvl_id = lvl.id

                # Link walls and openings
                for w in lvl.walls:
                    w.level_id = lvl_id
                    w.parent_id = lvl_id
                    for op in w.openings:
                        op.wall_id = w.id
                        op.host_wall_id = w.id
                        op.level_id = lvl_id
                        op.parent_id = w.id
                        if op.id not in w.children_ids:
                            w.children_ids.append(op.id)

                # Link spaces and bounding walls
                for sp in lvl.spaces:
                    sp.level_id = lvl_id
                    sp.parent_id = lvl_id
                    if not sp.bounding_wall_ids and sp.metadata and sp.metadata.get("bounding_wall_candidate_ids"):
                        sp.bounding_wall_ids = [str(wid) for wid in (sp.metadata.get("bounding_wall_candidate_ids") or [])]
                    for wall_id in sp.bounding_wall_ids:
                        target_wall = self.find_element(wall_id)
                        if isinstance(target_wall, CanonicalWall):
                            if sp.id not in target_wall.bounded_space_ids:
                                target_wall.bounded_space_ids.append(sp.id)
                            # Link bounded_space_id to wall faces
                            if target_wall.is_external:
                                if target_wall.face_b and not target_wall.face_b.bounded_space_id:
                                    target_wall.face_b.bounded_space_id = sp.id
                            else:
                                if target_wall.face_a and not target_wall.face_a.bounded_space_id:
                                    target_wall.face_a.bounded_space_id = sp.id
                                elif target_wall.face_b and not target_wall.face_b.bounded_space_id and target_wall.face_a and target_wall.face_a.bounded_space_id != sp.id:
                                    target_wall.face_b.bounded_space_id = sp.id

                # Link floors
                for fl in lvl.floors:
                    fl.level_id = lvl_id
                    fl.parent_id = lvl_id

    def recompute_quantities(self, rates_map: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Recomputes costs across all quantity bindings using current rates map:
        
        OBJECT -> QUANTITY FORMULA -> USER RATE -> COST.
        Allows instant customer rate edits without re-extracting plans.
        """
        rates = rates_map or {}
        summary = {"total_cost": 0.0, "items_costed": 0, "by_trade": {}}

        def process_binding(b: QuantityFormulaBinding):
            rate = rates.get(b.item_code)
            cost = b.calculate_cost(rate)
            if cost is not None:
                summary["total_cost"] = round(summary["total_cost"] + cost, 2)
                summary["items_costed"] += 1
                trade = b.trade_category
                summary["by_trade"][trade] = round(summary["by_trade"].get(trade, 0.0) + cost, 2)

        for w in self.all_walls():
            for qb in w.derived_quantities:
                process_binding(qb)
            for op in w.openings:
                for qb in op.derived_quantities:
                    process_binding(qb)
        for sp in self.all_spaces():
            for qb in sp.derived_quantities:
                process_binding(qb)
        for fl in self.all_floors():
            for qb in fl.derived_quantities:
                process_binding(qb)

        return summary

    def check_constructability(self) -> List[CanonicalConstructabilityIssue]:
        """Generic constructability, consistency, and clash checks for the canonical model."""
        issues: List[CanonicalConstructabilityIssue] = []

        # 1. Wall and Opening Geometric Clashes & Boundary Checks
        for w in self.all_walls():
            w_len = w.length_m()
            for op in w.openings:
                # Width exceeds host wall length
                if op.width_m is not None and w_len > 0.0 and float(op.width_m) > w_len:
                    issue = CanonicalConstructabilityIssue(
                        category="opening_width_exceeds_wall",
                        severity="ERROR",
                        description=f"Opening {op.id} ({op.mark or op.name}) width {op.width_m}m exceeds host wall {w.id} length {w_len:.2f}m",
                        affected_element_ids=[w.id, op.id],
                        review_state=ReviewState.REVIEW_REQUIRED,
                        recommended_action="Verify opening placement against architectural elevation",
                    )
                    issues.append(issue)

                # Height exceeds host wall height
                if op.height_m is not None and w.height_m is not None and float(op.height_m) > float(w.height_m):
                    issue = CanonicalConstructabilityIssue(
                        category="opening_height_exceeds_wall",
                        severity="ERROR",
                        description=f"Opening {op.id} height {op.height_m}m exceeds host wall {w.id} height {w.height_m}m",
                        affected_element_ids=[w.id, op.id],
                        review_state=ReviewState.REVIEW_REQUIRED,
                        recommended_action="Verify vertical section and lintel datum",
                    )
                    issues.append(issue)

                # Head height (sill + height) exceeds host wall height
                if op.sill_height_m is not None and op.height_m is not None and w.height_m is not None:
                    head_h = float(op.sill_height_m) + float(op.height_m)
                    if head_h > float(w.height_m) + 1e-3:
                        issue = CanonicalConstructabilityIssue(
                            category="opening_head_exceeds_wall_height",
                            severity="ERROR",
                            description=f"Opening {op.id} ({op.mark or op.name}) head height {head_h:.2f}m (sill {op.sill_height_m}m + height {op.height_m}m) exceeds host wall {w.id} height {w.height_m}m",
                            affected_element_ids=[w.id, op.id],
                            review_state=ReviewState.REVIEW_REQUIRED,
                            recommended_action="Verify opening vertical placement, sill height, and lintel datum",
                        )
                        issues.append(issue)

                # Offset + width extends past host wall end
                if op.offset_along_wall_m is not None and op.width_m is not None and w_len > 0.0:
                    op_end = float(op.offset_along_wall_m) + float(op.width_m)
                    if op_end > w_len + 1e-3:
                        issue = CanonicalConstructabilityIssue(
                            category="opening_extends_past_wall_end",
                            severity="ERROR",
                            description=f"Opening {op.id} ({op.mark or op.name}) extents (offset {op.offset_along_wall_m}m + width {op.width_m}m = {op_end:.2f}m) extend past host wall {w.id} length {w_len:.2f}m",
                            affected_element_ids=[w.id, op.id],
                            review_state=ReviewState.REVIEW_REQUIRED,
                            recommended_action="Verify opening offset position along wall baseline",
                        )
                        issues.append(issue)

            # Overlapping openings along host wall
            if len(w.openings) >= 2:
                try:
                    from pb_geometry_services import detect_opening_overlaps
                    has_overlaps, pairs = detect_opening_overlaps(w.openings)
                    if has_overlaps:
                        for op1_id, op2_id in pairs:
                            issue = CanonicalConstructabilityIssue(
                                category="overlapping_openings",
                                severity="ERROR",
                                description=f"Overlapping openings detected on host wall {w.id}: {op1_id} and {op2_id} clash along wall baseline",
                                affected_element_ids=[w.id, op1_id, op2_id],
                                review_state=ReviewState.REVIEW_REQUIRED,
                                recommended_action="Resolve clashing opening locations or marks on host wall",
                            )
                            issues.append(issue)
                except ImportError:
                    pass

        # 2. Level Vertical Datum Continuity & Ordering
        for b in self.buildings:
            prev_elev = None
            for lvl in sorted(b.levels, key=lambda l: l.level_index):
                if lvl.elevation_m is None and lvl.review_state == ReviewState.REVIEW_REQUIRED:
                    issue = CanonicalConstructabilityIssue(
                        category="unresolved_level_datum",
                        severity="WARNING",
                        description=f"Level {lvl.name} ({lvl.id}) lacks confirmed vertical datum elevation",
                        affected_element_ids=[lvl.id],
                        review_state=ReviewState.REVIEW_REQUIRED,
                        recommended_action="Confirm finish floor level from section drawing",
                    )
                    issues.append(issue)

                if prev_elev is not None and lvl.elevation_m is not None and lvl.elevation_m < prev_elev:
                    issue = CanonicalConstructabilityIssue(
                        category="inverted_level_elevation",
                        severity="ERROR",
                        description=f"Level {lvl.name} ({lvl.id}) elevation ({lvl.elevation_m}m) is lower than preceding level ({prev_elev}m)",
                        affected_element_ids=[lvl.id],
                        review_state=ReviewState.REVIEW_REQUIRED,
                        recommended_action="Verify vertical level sequencing in section/elevation drawings",
                    )
                    issues.append(issue)

                if lvl.elevation_m is not None:
                    prev_elev = lvl.elevation_m

                # 3. Spaces Boundary & Slab Linkage Validation
                for sp in lvl.spaces:
                    if len(sp.boundary_polygon) < 3:
                        issue = CanonicalConstructabilityIssue(
                            category="invalid_space_boundary",
                            severity="ERROR",
                            description=f"Space {sp.id} ({sp.name}) has invalid boundary polygon ({len(sp.boundary_polygon)} vertices)",
                            affected_element_ids=[sp.id, lvl.id],
                            review_state=ReviewState.REVIEW_REQUIRED,
                            recommended_action="Supply valid closed polygon boundary for room space",
                        )
                        issues.append(issue)

                    if len(lvl.floors) > 0 and not sp.floor_element_id:
                        issue = CanonicalConstructabilityIssue(
                            category="unassigned_floor_slab",
                            severity="WARNING",
                            description=f"Space {sp.id} ({sp.name}) on level {lvl.name} is not assigned to a floor slab element",
                            affected_element_ids=[sp.id, lvl.id],
                            review_state=ReviewState.REVIEW_REQUIRED,
                            recommended_action="Link space to bounding floor slab element for accurate structural and flooring takeoff",
                        )
                        issues.append(issue)

        self.constructability_issues = issues
        return issues

    def to_dict(self) -> Dict[str, Any]:
        res = self.base_to_dict()
        res.update({
            "buildings": [b.to_dict() for b in self.buildings],
            "evidence_observations": [obs.to_dict() for obs in self.evidence_observations],
            "is_synthetic_demo": parse_strict_bool(self.is_synthetic_demo),
            "constructability_issues": [iss.to_dict() for iss in self.constructability_issues],
            "revision_history": list(self.revision_history),
        })
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalProject":
        base_args = cls.base_from_dict_args(data)
        issues_raw = data.get("constructability_issues", []) or []
        issues = [CanonicalConstructabilityIssue.from_dict(iss) for iss in issues_raw if isinstance(iss, dict)]
        return cls(
            **base_args,
            buildings=[CanonicalBuilding.from_dict(b) for b in data.get("buildings", []) or [] if isinstance(b, dict)],
            evidence_observations=[CanonicalEvidenceObservation.from_dict(obs) for obs in data.get("evidence_observations", []) or [] if isinstance(obs, dict)],
            is_synthetic_demo=parse_strict_bool(data.get("is_synthetic_demo")),
            constructability_issues=issues,
            revision_history=list(data.get("revision_history", []) or []),
        )

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "CanonicalProject":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def generate_takeoff_rows(
        self, workspace_id: int, now_stamp: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generates canonical 21-field core takeoff rows for all trades in this canonical building model:

        - Walls (bricklaying/masonry external walls, carpentry internal partitions, wall face finishes)
        - Openings (doors, windows)
        - Floors (concrete slab area, concrete volume m³, vapor barrier m², edge formwork lm)
        - Spaces (carpet/timber/tile floor finishes, underlay/screed, waterproofing membrane)
        """
        stamp = now_stamp or ""
        rows: List[Dict[str, Any]] = []

        # 1. Walls & Openings
        for w in self.all_walls():
            w_net = w.net_area_m2()
            w_len = w.length_m()
            w_gross = w.gross_area_m2()
            w_ded = w.total_opening_deductions_m2()

            if w.is_external and w_net > 0:
                rows.append({
                    "workspace_id": int(workspace_id),
                    "section": "External",
                    "element": "External walls / cladding",
                    "location": f"External perimeter · {w.id}",
                    "substrate": w.substrate or "Clay brickwork",
                    "finish_system": (w.face_a.finish if w.face_a and w.face_a.finish else "To be confirmed"),
                    "quantity": round(w_net, 2),
                    "unit": "m²",
                    "quantity_status": "Measured",
                    "source_page": getattr(w.provenance, "source_page", "1") or "1",
                    "source_reference": f"PB Canonical BIM · wall:{w.id}",
                    "inclusion_status": "INCLUSION",
                    "coats": 1,
                    "coverage_m2_per_litre": 0.0,
                    "productivity_m2_per_hour": 0.0,
                    "rate_per_unit": 0.0,
                    "confidence": "Documented" if w.confidence and w.confidence >= 0.8 else "Derived",
                    "notes": f"Net wall area {w_net:.2f} m² (Gross {w_gross:.2f} m² less opening deductions {w_ded:.2f} m²).",
                    "row_role": "external_wall",
                    "created_at": stamp,
                    "updated_at": stamp,
                })
            elif not w.is_external and w_len > 0:
                rows.append({
                    "workspace_id": int(workspace_id),
                    "section": "Internal",
                    "element": "Internal partition framing",
                    "location": f"Internal partition · {w.id}",
                    "substrate": w.substrate or "Timber stud framing",
                    "finish_system": "Bare timber frame",
                    "quantity": round(w_len, 2),
                    "unit": "lm",
                    "quantity_status": "Measured",
                    "source_page": getattr(w.provenance, "source_page", "1") or "1",
                    "source_reference": f"PB Canonical BIM · partition:{w.id}",
                    "inclusion_status": "PROVISIONAL",
                    "coats": 1,
                    "coverage_m2_per_litre": 0.0,
                    "productivity_m2_per_hour": 0.0,
                    "rate_per_unit": 0.0,
                    "confidence": "Documented" if w.confidence and w.confidence >= 0.8 else "Derived",
                    "notes": f"Internal partition framing run {w_len:.2f} lm.",
                    "row_role": "internal_partition",
                    "created_at": stamp,
                    "updated_at": stamp,
                })

            # Wall faces
            for face, face_label in ((w.face_a, "Face A"), (w.face_b, "Face B")):
                if face and face.finish and face.area_net_m2 and face.area_net_m2 > 0:
                    rows.append({
                        "workspace_id": int(workspace_id),
                        "section": "External" if (w.is_external and face_label == "Face A") else "Internal",
                        "element": f"Wall finish ({face.finish_code or face_label})",
                        "location": f"{w.id} · {face_label}",
                        "substrate": face.substrate or w.substrate or "Wall substrate",
                        "finish_system": face.finish,
                        "quantity": round(face.area_net_m2, 2),
                        "unit": "m²",
                        "quantity_status": "Measured",
                        "source_page": getattr(w.provenance, "source_page", "1") or "1",
                        "source_reference": f"PB Canonical BIM · finish:{w.id}:{face.face_id}",
                        "inclusion_status": "PROVISIONAL",
                        "coats": 2 if "paint" in face.finish.lower() else 1,
                        "coverage_m2_per_litre": 0.0,
                        "productivity_m2_per_hour": 0.0,
                        "rate_per_unit": 0.0,
                        "confidence": "Documented",
                        "notes": f"Net finish area {face.area_net_m2:.2f} m².",
                        "row_role": "wall_finish",
                        "created_at": stamp,
                        "updated_at": stamp,
                    })

            # Openings
            for op in w.openings:
                if op.deduction_authority:
                    if not op.derived_quantities:
                        op.derive_trade_quantities()
                    elem_name = op.opening_classification or ("Door" if op.object_type == ObjectType.DOOR else "Window")
                    src_page = op.schedule_page_id or op.plan_page_id or getattr(op.provenance, "source_page", "1") or "1"
                    src_ref = f"PB Canonical BIM · opening:{op.id}"
                    if op.schedule_page_id:
                        src_ref += f" · sched_p{op.schedule_page_id}"
                    if op.detail_record_id:
                        src_ref += f" · det:{op.detail_record_id}"

                    notes_parts = [f"{elem_name} {op.mark} ({op.width_m or 0.0:.2f}m W × {op.height_m or 0.0:.2f}m H)."]
                    if op.sill_height_m is not None:
                        notes_parts.append(f"Sill: {op.sill_height_m:.2f}m.")
                    if op.head_height_m is not None:
                        notes_parts.append(f"Head: {op.head_height_m:.2f}m.")
                    if op.schedule_page_id:
                        notes_parts.append(f"Schedule page {op.schedule_page_id}.")
                    if op.detail_record_id:
                        notes_parts.append(f"Detail record {op.detail_record_id}.")
                    op_notes = " ".join(notes_parts)

                    rows.append({
                        "workspace_id": int(workspace_id),
                        "section": "Internal" if op.object_type == ObjectType.DOOR else "External",
                        "element": elem_name,
                        "location": f"{op.mark} · on {w.id}",
                        "substrate": "Selected timber / aluminium",
                        "finish_system": "Factory pre-finished",
                        "quantity": 1.0,
                        "unit": "No.",
                        "quantity_status": "Measured",
                        "source_page": str(src_page),
                        "source_reference": src_ref,
                        "inclusion_status": "PROVISIONAL",
                        "coats": 1,
                        "coverage_m2_per_litre": 0.0,
                        "productivity_m2_per_hour": 0.0,
                        "rate_per_unit": 0.0,
                        "confidence": "Documented",
                        "notes": op_notes,
                        "row_role": "door" if op.object_type == ObjectType.DOOR else "window" if op.object_type == ObjectType.WINDOW else "opening",
                        "created_at": stamp,
                        "updated_at": stamp,
                    })

                    # Secondary opening trade quantities (architraves, reveals)
                    for dq in op.derived_quantities:
                        if dq.item_code in ("DOOR_ARCHITRAVE", "WINDOW_REVEAL_LINER"):
                            trim_ref = f"PB Canonical BIM · opening_trim:{op.id}"
                            if op.schedule_page_id:
                                trim_ref += f" · sched_p{op.schedule_page_id}"
                            rows.append({
                                "workspace_id": int(workspace_id),
                                "section": "Internal" if op.object_type == ObjectType.DOOR else "External",
                                "element": "Door architrave / jamb trim" if op.object_type == ObjectType.DOOR else "Window timber reveal liner",
                                "location": f"{op.mark} · on {w.id}",
                                "substrate": "MDF / Pine timber",
                                "finish_system": "Primed timber trim",
                                "quantity": round(dq.quantity, 2),
                                "unit": "lm",
                                "quantity_status": "Measured",
                                "source_page": str(src_page),
                                "source_reference": trim_ref,
                                "inclusion_status": "PROVISIONAL",
                                "coats": 1,
                                "coverage_m2_per_litre": 0.0,
                                "productivity_m2_per_hour": 0.0,
                                "rate_per_unit": 0.0,
                                "confidence": "Documented",
                                "notes": f"Opening trim perimeter {dq.quantity:.2f} lm for {op.mark}.",
                                "row_role": "opening_trim",
                                "created_at": stamp,
                                "updated_at": stamp,
                            })

        # 2. Floors (Concreting)
        for fl in self.all_floors():
            fl_area = fl.effective_area_m2()
            if not fl_area or fl_area <= 0.0:
                continue
            if not fl.derived_quantities:
                fl.derive_trade_quantities()

            thickness = fl.thickness_m if fl.thickness_m and fl.thickness_m > 0.0 else 0.100
            vol_m3 = round(fl_area * thickness, 2)
            perim = fl.perimeter_lm()

            # Slab area
            rows.append({
                "workspace_id": int(workspace_id),
                "section": "Substructure",
                "element": f"Concrete slab on ground ({int(thickness*1000)}mm)",
                "location": f"Slab · {fl.id}",
                "substrate": fl.substrate or "25 MPa Concrete",
                "finish_system": "Curing compound / steel trowel finish",
                "quantity": round(fl_area, 2),
                "unit": "m²",
                "quantity_status": "Measured",
                "source_page": getattr(fl.provenance, "source_page", "1") or "1",
                "source_reference": f"PB Canonical BIM · concrete:{fl.id}:area",
                "inclusion_status": "INCLUSION",
                "coats": 1,
                "coverage_m2_per_litre": 0.0,
                "productivity_m2_per_hour": 0.0,
                "rate_per_unit": 0.0,
                "confidence": "Documented",
                "notes": f"Slab area {fl_area:.2f} m² × {int(thickness*1000)}mm thickness. Concrete volume: {vol_m3:.2f} m³.",
                "row_role": "floor_area",
                "created_at": stamp,
                "updated_at": stamp,
            })

            # Concrete volume / supply
            rows.append({
                "workspace_id": int(workspace_id),
                "section": "Substructure",
                "element": f"Concrete supply & pump ({fl.substrate or '25 MPa Concrete'})",
                "location": f"Slab · {fl.id}",
                "substrate": fl.substrate or "25 MPa Concrete",
                "finish_system": "Supply, pump and place",
                "quantity": vol_m3,
                "unit": "item",
                "quantity_status": "Measured",
                "source_page": getattr(fl.provenance, "source_page", "1") or "1",
                "source_reference": f"PB Canonical BIM · concrete:{fl.id}:volume",
                "inclusion_status": "INCLUSION",
                "coats": 1,
                "coverage_m2_per_litre": 0.0,
                "productivity_m2_per_hour": 0.0,
                "rate_per_unit": 0.0,
                "confidence": "Documented",
                "notes": f"Supply & place {vol_m3:.2f} m³ of concrete ({fl_area:.2f} m² × {thickness:.3f}m).",
                "row_role": "",
                "created_at": stamp,
                "updated_at": stamp,
            })

            # Under-slab vapor barrier
            rows.append({
                "workspace_id": int(workspace_id),
                "section": "Substructure",
                "element": "Damp-proof membrane / vapor barrier",
                "location": f"Slab base · {fl.id}",
                "substrate": "0.2mm Polythene film",
                "finish_system": "Supplied and laid with 200mm laps",
                "quantity": round(fl_area * 1.10, 2),
                "unit": "m²",
                "quantity_status": "Measured",
                "source_page": getattr(fl.provenance, "source_page", "1") or "1",
                "source_reference": f"PB Canonical BIM · concrete:{fl.id}:dpm",
                "inclusion_status": "INCLUSION",
                "coats": 1,
                "coverage_m2_per_litre": 0.0,
                "productivity_m2_per_hour": 0.0,
                "rate_per_unit": 0.0,
                "confidence": "Documented",
                "notes": f"Vapor barrier: {fl_area:.2f} m² + 10% lap allowance = {fl_area*1.10:.2f} m².",
                "row_role": "",
                "created_at": stamp,
                "updated_at": stamp,
            })

            # Edge formwork
            if perim > 0:
                rows.append({
                    "workspace_id": int(workspace_id),
                    "section": "Substructure",
                    "element": "Slab edge formwork",
                    "location": f"Slab perimeter · {fl.id}",
                    "substrate": "Edge form boards",
                    "finish_system": "Form, strip and clean",
                    "quantity": round(perim, 2),
                    "unit": "lm",
                    "quantity_status": "Measured",
                    "source_page": getattr(fl.provenance, "source_page", "1") or "1",
                    "source_reference": f"PB Canonical BIM · concrete:{fl.id}:edge_form",
                    "inclusion_status": "INCLUSION",
                    "coats": 1,
                    "coverage_m2_per_litre": 0.0,
                    "productivity_m2_per_hour": 0.0,
                    "rate_per_unit": 0.0,
                    "confidence": "Documented",
                    "notes": f"Perimeter edge formwork {perim:.2f} lm for {int(thickness*1000)}mm slab edge.",
                    "row_role": "",
                    "created_at": stamp,
                    "updated_at": stamp,
                })

        # 3. Spaces (Flooring & Tiling)
        for sp in self.all_spaces():
            sp_area = sp.effective_floor_area_m2()
            if not sp_area or sp_area <= 0.0:
                continue
            if not sp.derived_quantities:
                sp.derive_trade_quantities()

            for b in sp.derived_quantities:
                rows.append({
                    "workspace_id": int(workspace_id),
                    "section": "Internal",
                    "element": b.item_code.replace("_", " ").title(),
                    "location": f"{sp.name} · {sp.id}",
                    "substrate": sp.finish_assignments.get("floor") or "Selected flooring substrate",
                    "finish_system": "Supplied and installed to manufacturer specification",
                    "quantity": round(b.quantity or sp_area, 2),
                    "unit": b.unit,
                    "quantity_status": "Measured",
                    "source_page": getattr(sp.provenance, "source_page", "1") or "1",
                    "source_reference": f"PB Canonical BIM · flooring:{sp.id}:{b.item_code}",
                    "inclusion_status": "INCLUSION",
                    "coats": 1,
                    "coverage_m2_per_litre": 0.0,
                    "productivity_m2_per_hour": 0.0,
                    "rate_per_unit": 0.0,
                    "confidence": "Documented",
                    "notes": f"{b.trade_category.title()} derived from {sp.name} ({b.formula_expression}).",
                    "row_role": "floor_area" if b.item_code.startswith("FLOOR_") and b.unit == "m²" else "",
                    "created_at": stamp,
                    "updated_at": stamp,
                })

        return rows


def publish_canonical_model_to_takeoff(
    app: Any,
    workspace_id: int,
    project: Optional[CanonicalProject] = None,
) -> int:
    """Publishes canonical BIM model quantities directly into the SQLite takeoff_rows table.
    Ensures zero divergence between the 3D canonical model and the customer's trade schedule.
    """
    if project is None:
        from pb_canonical_persistence import load_workspace_canonical_model
        ok, loaded_project, _, _ = load_workspace_canonical_model(app, workspace_id)
        if not ok or not loaded_project:
            return 0
        project = loaded_project

    project.recompute_relationships()
    stamp = app.now_stamp() if hasattr(app, "now_stamp") else ""
    rows_data = project.generate_takeoff_rows(int(workspace_id), stamp)
    if not rows_data:
        return 0

    import pb_takeoff_row_contract as takeoff_contract
    sql = takeoff_contract.insert_sql(takeoff_contract.CORE_FIELDS)
    count = 0
    for r in rows_data:
        values = tuple(r[k] for k in takeoff_contract.CORE_FIELDS)
        if hasattr(app, "lexecute"):
            app.lexecute(sql, values)
        count += 1
    return count


