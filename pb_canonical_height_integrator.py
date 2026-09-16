from __future__ import annotations

import logging
import dataclasses
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_height_authority import OpeningHeightProducer, OpeningHeightSelector
from pb_source_observation_authority import SourceObservationAuthority

logger = logging.getLogger(__name__)

@dataclasses.dataclass(frozen=True)
class CanonicalHeightResult:
    height_mm: Optional[float]
    source: str
    confidence: float
    reason_codes: frozenset[str]

class CanonicalHeightIntegrator:
    """Canonical integration path for opening height.
    
    Consumes outputs from OpeningHeightProducer (Route B) and 
    SourceObservationAuthority (Route A direct physical dimensions).
    """
    def __init__(
        self,
        height_producer: OpeningHeightProducer,
        observation_authority: SourceObservationAuthority,
    ) -> None:
        self._height_producer = height_producer
        self._observation_authority = observation_authority

    def resolve_height(self, selector: OpeningHeightSelector) -> CanonicalHeightResult:
        logger.info("CanonicalHeightIntegrator: resolving height for %s", selector.opening_record_id)
        
        # Route B (Schedule)
        route_b = self._height_producer.publish_scope(selector)
        if route_b.status is EvidenceResolutionStatus.CORROBORATED and route_b.evidence is not None:
            logger.info(
                "CanonicalHeightIntegrator: Route B success: %s mm for %s", 
                route_b.evidence.height_mm, 
                selector.opening_record_id
            )
            return CanonicalHeightResult(
                height_mm=route_b.evidence.height_mm,
                source="schedule_route_b",
                confidence=1.0,
                reason_codes=route_b.reason_codes
            )
            
        logger.info(
            "CanonicalHeightIntegrator: Route B failed for %s. Reasons: %s", 
            selector.opening_record_id, 
            route_b.reason_codes
        )

        # Route A (Source dimensions)
        # TODO: Implement physical dimension parsing from SourceObservationAuthority
        
        logger.info("CanonicalHeightIntegrator: all routes failed for %s", selector.opening_record_id)
        return CanonicalHeightResult(
            height_mm=None,
            source="unresolved",
            confidence=0.0,
            reason_codes=route_b.reason_codes
        )
