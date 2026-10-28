# Architectural Report: Source-Authenticated Structural Shared Stud Pier & Multi-Opening Cluster Host Authority

**Document ID**: `docs/engineering/antigravity_shared_stud_pier_cluster_architecture_report_v1.md`  
**Author**: AntiGravity (Autonomous Structural Opening Accuracy Recovery)  
**Date**: 2026-10-28 AEST  
**Status**: DRAFT ARCHITECTURE & STRUCTURAL EVIDENCE (SHADOW MODE)

---

## 1. Observed Repository Behavior

### 1.1 Narrow Inter-Aperture Pier Discarding and Opening Fusion
- In residential and commercial construction plans:
  - Doors and windows frequently appear in close proximity along the same wall run:
    1. Adjacent passage doors branching off a hallway (e.g. Bedroom 1 and Bedroom 2, or Master Bedroom and Ensuite).
    2. Side-by-side window assemblies sharing a narrow timber/steel stud mullion.
    3. Multi-door service cupboards or double access doors.
  - The flanking separation between the two openings is a structural stud pack:
    - 2-stud timber pack: $2 \times 35$ mm $= 70$ mm ($\approx 3.97$ pt at 1:100 scale).
    - 2-stud timber pack (45mm): $2 \times 45$ mm $= 90$ mm ($\approx 5.10$ pt at 1:100 scale).
    - 3-stud timber pack: $3 \times 45$ mm $= 135$ mm ($\approx 7.65$ pt at 1:100 scale).
- The Failure in Existing Tracing Authorities:
  - Standard wall vector linkers enforce a minimum wall length threshold ($L_{\text{min}} \ge 10.0$–$20.0$ pt).
  - Because the narrow $70$–$90$ mm ($4.0$–$5.1$ pt) stud pier falls below this minimum length threshold, existing routines discard it as noise.
  - Downstream consequences:
    1. **Aperture Fusion**: Merges both independent doors into a single massive opening void, obliterating the discrete opening marks and corrupting schedule quantities.
    2. **Orphan Host Error**: Binds only the first opening to the left wall and drops the second opening with `opening_host_frame_host_unavailable`.
    3. **Centerline Severance**: Breaks the continuous wall into disconnected fragments, dropping both openings.

---

## 2. Inferred Engineering Causes

### 2.1 The Shared Stud Pier Structural Rule (AS 1684 / NCC)
- In framed wall construction, adjacent door frames do not sit in isolated independent walls. They share a common structural stud column (stud pack) that carries header loads down to the floor structure.
- These narrow $70$–$135$ mm solid sections are authentic structural piers, not missing primitives.

### 2.2 Multi-Opening Cluster Geometry
A cluster along a continuous through-wall consists of:
1. Master Through-Wall centerline vector ($\mathbf{u}, \mathbf{n}, \mathbf{o}$).
2. Outer Left Terminal Jamb $\mathbf{p}_{\text{start}}$.
3. Opening 1 clear span $W_1 = \|\mathbf{p}_{1, \text{end}} - \mathbf{p}_{1, \text{start}}\|$.
4. Shared Stud Pier: width $W_{\text{pier}} = \|\mathbf{p}_{2, \text{start}} - \mathbf{p}_{1, \text{end}}\| \in [3.0, 15.0]$ pt.
5. Opening 2 clear span $W_2 = \|\mathbf{p}_{2, \text{end}} - \mathbf{p}_{2, \text{start}}\|$.
6. Outer Right Terminal Jamb $\mathbf{p}_{\text{end}}$.
7. Total cluster extent $L_{\text{cluster}} = W_1 + W_{\text{pier}} + W_2$.

---

## 3. Proposed Structural Authority Contract

### 3.1 Architectural Scope & Invariant Guarantees
We implement `pb_structural_shared_stud_pier_cluster_authority.py`:
- **Sealed Production & Authority**: `StructuralSharedStudPierClusterProducer` and `StructuralSharedStudPierClusterAuthority`.
- **Classification Status**:
  - `CLUSTER_HOST_CONFIRMED`: Openings and shared stud pier verified; independent aperture records generated and bound to master through-wall.
  - `ABSTAINED_PIER_WIDTH_OUT_OF_BOUNDS`: Intermediary pier width outside allowable stud bounds ($< 3.0$ pt or $> 15.0$ pt).
  - `ABSTAINED_NON_COLLINEAR_CLUSTER`: Openings deviate from shared wall axis by $> 0.5^\circ$.
  - `ABSTAINED_DEGENERATE_OPENING_SPAN`: Any opening span $< 20.0$ pt or $> 300.0$ pt.
- **Strict Shadow Isolation**:
  - `commercial_projection_allowed = False`
  - `takeoff_eligible = False`
  - `shadow_only = True`
  - Zero modification to existing frozen evaluators or signed customer outputs.
