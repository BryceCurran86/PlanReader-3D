"""Nonpublishing original CAD source-role witnesses for wall T-junctions/returns.

No bridging, tolerance expansion, nearest/first host, or W4 promotion.
All geometry must be owned by distinct original structural source paths.
"""
from __future__ import annotations
from math import isfinite


def _finite(*vals):
    return all(type(x) in (int, float) and isfinite(x) for x in vals)


def _lines(drawings, index, layer):
    if type(index) is not int or not 0 <= index < len(drawings):
        raise ValueError('invalid original source path index')
    path = drawings[index]
    if path.get('layer') != layer:
        raise ValueError('original structural source layer mismatch')
    out = []
    for item in path.get('items', ()):
        if item[0] != 'l':
            continue
        a, b = item[1:3]
        if not _finite(a.x, a.y, b.x, b.y):
            raise ValueError('nonfinite original CAD source')
        out.append(((a.x, a.y), (b.x, b.y)))
    return out


def _has_segment(lines, a, b, tol):
    def close(p, q):
        return abs(p[0]-q[0]) <= tol and abs(p[1]-q[1]) <= tol
    return any((close(u,a) and close(v,b)) or (close(u,b) and close(v,a))
               for u,v in lines)


def _overlaps_required(segment, required, tol):
    """Detect partial collinear duplicate; touching only at endpoints is not overlap."""
    (u, v), (a, b) = segment, required
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = (dx * dx + dy * dy) ** .5
    if length <= tol:
        return False
    def signed_offset(p):
        return ((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / length
    if abs(signed_offset(u)) > tol or abs(signed_offset(v)) > tol:
        return False
    def projected(p):
        return ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length
    lo, hi = sorted((projected(u), projected(v)))
    return min(hi, length) - max(lo, 0) > tol


def _uncontested(drawings, owners, layer, required, tol):
    """Competing source paths may duplicate only part of a required face."""
    competitors = []
    for i, path in enumerate(drawings):
        if i in owners or path.get('layer') != layer:
            continue
        for line in _lines(drawings, i, layer):
            if any(_overlaps_required(line, (a, b), tol) for a,b in required):
                competitors.append(i)
                break
    return competitors


def source_t_junction(drawings, *, upper_left_path, upper_right_path,
                      vertical_left_path, vertical_right_path, opposite_path,
                      wall_layer, x_outer_left, x_gap_left, x_gap_right,
                      x_outer_right, y_upper, y_opposite,
                      vertical_left_start_y, vertical_right_start_y,
                      tolerance=.001):
    """Authenticate source T-junction, never physical W4 equivalence."""
    ids = [upper_left_path, upper_right_path, vertical_left_path,
           vertical_right_path, opposite_path]
    nums = [x_outer_left,x_gap_left,x_gap_right,x_outer_right,y_upper,
            y_opposite,vertical_left_start_y,vertical_right_start_y,tolerance]
    if (len(set(ids)) != len(ids) or not isinstance(wall_layer,str) or not wall_layer
            or not _finite(*nums) or not 0 < tolerance <= .01
            or not x_outer_left < x_gap_left < x_gap_right < x_outer_right
            or not y_upper < y_opposite
            or not vertical_left_start_y < y_upper
            or not vertical_right_start_y < y_upper):
        raise ValueError('invalid structural T-junction source geometry')
    required = [
        ((x_outer_left,y_upper),(x_gap_left,y_upper)),
        ((x_gap_right,y_upper),(x_outer_right,y_upper)),
        ((x_gap_left,vertical_left_start_y),(x_gap_left,y_upper)),
        ((x_gap_right,vertical_right_start_y),(x_gap_right,y_upper)),
        ((x_outer_left,y_opposite),(x_outer_right,y_opposite)),
    ]
    for idx, (a,b) in zip(ids, required):
        if not _has_segment(_lines(drawings,idx,wall_layer),a,b,tolerance):
            raise ValueError('required exact source-owned wall face missing')
    competitors = _uncontested(drawings,set(ids),wall_layer,required,tolerance)
    bridge = []
    for idx,path in enumerate(drawings):
        if path.get('layer') != wall_layer:
            continue
        for a,b in _lines(drawings,idx,wall_layer):
            if _overlaps_required((a,b), ((x_gap_left,y_upper),
                                   (x_gap_right,y_upper)), tolerance):
                bridge.append(idx)
                break
    status = ('SOURCE_PERPENDICULAR_T_JUNCTION_OBSERVATION_ONLY'
              if not competitors and not bridge else
              'ABSTAIN_COMPETING_OR_BRIDGED_STRUCTURAL_SOURCE')
    return dict(status=status,source_path_ids=ids,
                exact_cad_gap_pt=x_gap_right-x_gap_left,
                perpendicular_wall_faces_end_at_gap=True,
                opposite_wall_face_continuous=True,
                competing_paths=sorted(set(competitors)),
                horizontal_bridge_paths=sorted(set(bridge)),
                canonical_w4_host='ABSTAIN',cross_document_same_physical_wall='ABSTAIN',
                opening_frame='ABSTAIN',opening_area='ABSTAIN',
                opening_count='ABSTAIN',new_firm_quantity=False)


def source_perpendicular_return(drawings, *, cap_path, upper_vertical_path,
                                lower_vertical_path, opposite_vertical_path,
                                wall_layer, x_face, x_cap, x_opposite,
                                y_cap_top, y_cap_bottom,
                                y_upper_start, y_lower_end,
                                y_opposite_start, y_opposite_end,
                                tolerance=.001):
    """Authenticate a source-owned three-sided return, not a physical host."""
    ids=[cap_path,upper_vertical_path,lower_vertical_path,opposite_vertical_path]
    nums=[x_face,x_cap,x_opposite,y_cap_top,y_cap_bottom,y_upper_start,
          y_lower_end,y_opposite_start,y_opposite_end,tolerance]
    if (len(set(ids))!=len(ids) or not isinstance(wall_layer,str) or not wall_layer
            or not _finite(*nums) or not 0<tolerance<=.01
            or not x_opposite<x_face<x_cap
            or not y_upper_start<y_cap_top<y_cap_bottom<y_lower_end
            or not y_opposite_start<=y_cap_top<y_cap_bottom<=y_opposite_end):
        raise ValueError('invalid perpendicular return source geometry')
    cap_lines=_lines(drawings,cap_path,wall_layer)
    req=[((x_face,y_cap_top),(x_cap,y_cap_top)),
         ((x_cap,y_cap_top),(x_cap,y_cap_bottom)),
         ((x_cap,y_cap_bottom),(x_face,y_cap_bottom))]
    if not all(_has_segment(cap_lines,a,b,tolerance) for a,b in req):
        raise ValueError('exact three-sided structural return missing')
    other=[((x_face,y_upper_start),(x_face,y_cap_top)),
           ((x_face,y_cap_bottom),(x_face,y_lower_end)),
           ((x_opposite,y_opposite_start),(x_opposite,y_opposite_end))]
    for idx,(a,b) in zip(ids[1:],other):
        if not _has_segment(_lines(drawings,idx,wall_layer),a,b,tolerance):
            raise ValueError('required original perpendicular wall face missing')
    competitors=_uncontested(drawings,set(ids),wall_layer,req+other,tolerance)
    return dict(status=('SOURCE_PERPENDICULAR_RETURN_OBSERVATION_ONLY'
                        if not competitors else 'ABSTAIN_COMPETING_SOURCE'),
                source_path_ids=ids,return_cap_width_pt=x_cap-x_face,
                vertical_face_gap_pt=y_cap_bottom-y_cap_top,
                opposite_vertical_face_continuous=True,
                competing_paths=competitors,canonical_w4_host='ABSTAIN',
                cross_document_same_physical_wall='ABSTAIN',
                opening_frame='ABSTAIN',opening_area='ABSTAIN',
                opening_count='ABSTAIN',new_firm_quantity=False)
