# Architecture Report: Source Plan Drawing Sheet Registration & North Rotation Alignment Shadow Authority (v1)

## Executive Summary
In multi-sheet drawing sets (architectural, structural, MEP, landscape), different sheets frequently have disparate origins, scales (e.g., 1:100 general vs 1:50 detail), and paper orientations (e.g., 90° rotation to fit title block orientation).
Cross-sheet overlay fails completely when attempting to compare coordinates in raw unaligned PDF space.

This authority computes rigorous 2D similarity transformations (scale $s$, rotation angle $\theta$, translation $t_x, t_y$) from structural grid intersections and datum control points, mapping disparate sheets into a unified Global Project Coordinate System (GPCS) in shadow candidate mode.

## Workstream Reference
- **Workstream C Item 23:** Cross-sheet correspondence, coordinate registration, and orientation alignment.

## 2D Similarity Transformation Model
Given two distinct control points on a sheet:
- Local coordinates: $p_1 = (x_1, y_1)$, $p_2 = (x_2, y_2)$
- Target global coordinates: $P_1 = (X_1, Y_1)$, $P_2 = (X_2, Y_2)$

Calculations:
1. Local distance: $d_{local} = \|p_2 - p_1\|$
2. Global distance: $d_{global} = \|P_2 - P_1\|$
3. Scale factor: $s = \frac{d_{global}}{d_{local}}$
4. Rotation angle: $\theta = \text{atan2}(P_{2,y} - P_{1,y}, P_{2,x} - P_{1,x}) - \text{atan2}(p_{2,y} - p_{1,y}, p_{2,x} - p_{1,x})$
5. Translation vector:
   $$\begin{pmatrix} t_x \\ t_y \end{pmatrix} = \begin{pmatrix} X_1 \\ Y_1 \end{pmatrix} - s \begin{pmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{pmatrix} \begin{pmatrix} x_1 \\ y_1 \end{pmatrix}$$
6. Forward projection of any point $(x, y)$:
   $$X = s \cdot (x \cos\theta - y \sin\theta) + t_x$$
   $$Y = s \cdot (x \sin\theta + y \cos\theta) + t_y$$

## Invariants & Safety
- Candidate shadow mode only (`status = EvidenceResolutionStatus.CANDIDATE`).
- `commercial_projection_allowed = False`, `takeoff_eligible = False`.
- Global 2.5 pt snap tolerance.
- Customer retention baseline preserved byte-for-byte.
