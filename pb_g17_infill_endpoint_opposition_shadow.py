"""Original endpoint-local infill opposition, never whole-edge wall semantics."""
from __future__ import annotations

import math

from pb_g17_dual_dpi_source_correspondence_shadow import _axis_line
from pb_g17_w4_equivalence_competitor_shadow import _positive_collinear_source_overlap
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY


def _endpoint_infill_witnesses(edge, junction_position, intervals, *, tolerance):
    geometry = tuple(edge[k] for k in ('x1','y1','x2','y2'))
    axis = _axis_line(geometry)
    if axis is None:
        return ()
    endpoints = (geometry[:2],geometry[2:])
    near = [p for p in endpoints if math.dist(p,junction_position)<=tolerance+1e-6]
    if len(near)!=1:
        return ()
    endpoint = near[0]
    scalar = endpoint[0 if axis[0]=='horizontal' else 1]
    witnesses = []
    for interval in intervals:
        if (not interval.get('physical_opening_id')
                or interval['source_primitive_id'] not in edge[LINEAGE_KEY]['source_primitive_ids']
                or not _positive_collinear_source_overlap(geometry,interval['geometry'])):
            continue
        value = _axis_line(interval['geometry'])
        if value is None or not value[1]-1e-6<=scalar<=value[2]+1e-6:
            continue
        witnesses.append(dict(
            physical_opening_id=interval['physical_opening_id'],
            source_observation_id=interval['source_observation_id'],
            source_primitive_id=interval['source_primitive_id'],
            actual_edge_endpoint=endpoint, original_infill_interval=tuple(interval['geometry']),
            actual_w3_junction_position=tuple(junction_position),
            endpoint_incidence_tolerance_pt=tolerance,
            whole_edge_semantic_role_granted=False,
        ))
    return tuple(sorted(witnesses,key=lambda r:(r['physical_opening_id'],r['source_observation_id'])))


def build_g17_infill_endpoint_opposition_shadow(source, *, revision_id, page_id):
    """Actual source factory performs all opening, paint and F.07 proofs."""
    from pb_g17_source_infill_opposition_shadow import build_g17_source_infill_opposition_shadow
    return build_g17_source_infill_opposition_shadow(source,revision_id=revision_id,
        page_id=page_id,infill_endpoint_opposition=True)
