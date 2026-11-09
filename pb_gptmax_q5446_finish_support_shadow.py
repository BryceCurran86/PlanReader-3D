"""Q5446 original supporting material-scope witness, never a quantity issuer.

A byte-authenticated inclusion document and sales document can corroborate
floor-tile *material scope*, but cannot measure room area, host finished faces,
or create a commercial/customer seal. No original text, names or PDF bytes
are written to the report.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping

import fitz

# Original immutable file identities already listed in the frozen public source manifest.
# Matching these does NOT authenticate a physical area or benchmark answer.
SOURCE_IDS = {
    "standard_inclusions": "db0af9871032e9b77f151cd2f8bddf171aa10ad3a3c975abba0d24a020e0bd63",
    "scope_and_allowance_reference": "a2b134a0bca2b314737e2f58351018b65e0ff011774780f3e5758e9f576444dd",
}
SOURCE_PAGE_COUNTS = {"standard_inclusions": 2, "scope_and_allowance_reference": 6}


@dataclass(frozen=True)
class Q5446FinishMaterialWitness:
    status: str
    source_roles: tuple[str, ...] = ()
    source_sha256s: tuple[str, ...] = ()
    supporting_page_numbers: tuple[int, ...] = ()
    corroborated_material_scopes: tuple[str, ...] = ()
    reason_code: str = ""
    authentic_finished_face_area: bool = False
    authenticated_customer_quantity: bool = False
    benchmark_score_granted: bool = False

    def public_summary(self) -> dict:
        """Only source-safe categories/counts and explicit non-authority gates."""
        return {
            "status": self.status,
            "source_roles": list(self.source_roles),
            "source_sha256s": list(self.source_sha256s),
            "supporting_page_numbers": list(self.supporting_page_numbers),
            "material_scope_count": len(self.corroborated_material_scopes),
            "reason_code": self.reason_code,
            "authentic_finished_face_area": False,
            "authenticated_customer_quantity": False,
            "benchmark_score_granted": False,
        }


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _section(text: str, start: str, end: str) -> str:
    normalized = _normalize(text)
    a, b = normalized.find(start), normalized.find(end)
    return normalized[a:b] if a >= 0 and b > a else ""


def parse_source_material_scope(inclusions_p1: str, sales_p6: str) -> tuple[str, ...]:
    """Text-only diagnostic; by itself this grants no original-source authority."""
    if type(inclusions_p1) is not str or type(sales_p6) is not str:
        return ()
    bath = _section(inclusions_p1, "bathroom & ensuite", "laundry")
    laundry = _section(inclusions_p1, "laundry", "windows & external doors")
    upgrade = _section(sales_p6, "47 - 3", "48 - 1")
    if not bath or not laundry or not upgrade:
        return ()
    if (
        not all(term in bath for term in ("floor tiles", "skirting tiles", "throughout"))
        or not all(term in laundry for term in ("floor tiles", "skirting tiles", "throughout"))
        or "600mm x 600mm" not in upgrade
        or "porcelain floor tiles" not in upgrade
        or not all(word in upgrade for word in ("entry", "kitchen", "living"))
        or "wet area ceramic floor tiles" not in upgrade
    ):
        return ()
    return (
        "bathroom_and_ensuite_floor_tiles",
        "laundry_floor_tiles",
        "entry_kitchen_living_porcelain_tiles",
        "wet_area_tile_upgrade",
    )


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as fd:
        for block in iter(lambda: fd.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inspect_q5446_finish_support(roster: Iterable[Mapping[str, object]]) -> Q5446FinishMaterialWitness:
    """Inspect original support documents, not scored takeoffs or role substitutes.

    The roster's source SHA and page claims are rechecked on immutable bytes;
    that same snapshot is parsed. A changed or replaced on-disk source fails
    closed after extraction. No source bytes escape to any status report.
    """
    roles = {}
    for record in roster:
        role = record.get("role")
        if role in SOURCE_IDS:
            if role in roles:
                return Q5446FinishMaterialWitness("ABSTAIN", reason_code="duplicate_supporting_role")
            roles[role] = record
    if set(roles) != set(SOURCE_IDS):
        return Q5446FinishMaterialWitness("ABSTAIN", reason_code="supporting_role_missing")
    original_texts = {}
    for role in SOURCE_IDS:
        record = roles[role]
        path = record.get("path")
        if (
            not isinstance(path, Path) or path.is_symlink() or not path.is_file()
            or record.get("sha256") != SOURCE_IDS[role]
            or record.get("page_count") != SOURCE_PAGE_COUNTS[role]
        ):
            return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_identity_invalid")
        try:
            # One immutable byte snapshot is BOTH the SHA-authenticated source
            # and the exact PDF parsed. Hashing a path and opening that path
            # again is unsafe: it could have been replaced in between.
            source_bytes = path.read_bytes()
        except OSError:
            return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_identity_invalid")
        if sha256(source_bytes).hexdigest() != SOURCE_IDS[role]:
            return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_identity_invalid")
        try:
            with fitz.open(stream=source_bytes, filetype="pdf") as doc:
                if len(doc) != SOURCE_PAGE_COUNTS[role]:
                    return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_page_count_invalid")
                index = 0 if role == "standard_inclusions" else 5
                original_texts[role] = doc[index].get_text("text")
        except (OSError, RuntimeError, ValueError):
            return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_decode_failed")
        try:
            if path.is_symlink() or _digest(path) != SOURCE_IDS[role]:
                return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_changed_during_read")
        except OSError:
            return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_source_changed_during_read")
    scopes = parse_source_material_scope(
        original_texts["standard_inclusions"],
        original_texts["scope_and_allowance_reference"],
    )
    if not scopes:
        return Q5446FinishMaterialWitness("ABSTAIN", reason_code="support_material_scope_unverified")
    return Q5446FinishMaterialWitness(
        status="SUPPORTING_SOURCE_CORROBORATED_NO_QUANTITY",
        source_roles=tuple(SOURCE_IDS),
        source_sha256s=tuple(SOURCE_IDS.values()),
        supporting_page_numbers=(1, 6),
        corroborated_material_scopes=scopes,
    )
