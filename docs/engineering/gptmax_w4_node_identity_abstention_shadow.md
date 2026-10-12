# W4 node-identity abstention shadow

## Architecture report before implementation

Read AGENTS.md, AI_ENGINEERING_PLAYBOOK.md including section 13, the adopted
wall-topology observability architecture/spec, retired benchmark notice and
CI workflow. Trace: original SourceObservationRecord inventory -> existing
build_wall_graph_for_viewport -> W3 deduplicate_coincident_edges and
classify_junctions -> W4 assemble_wall_candidates -> WallCandidate guard.
No commercial measurement or publication boundary is crossed.

Observed: exact endpoint running means can leave distinct graph node indices
at identical final coordinates. W3 identities include raw node indices as well
as six-decimal positions, so those junction records remain distinct. W4's
position-only lookup overwrites them at the same rounded address. An otherwise simple graph-index chain can
therefore start/end at the same junction identity; the existing constructor
correctly refuses it. The authenticated bounded original control reproduces
this failure identically under legacy/indexed zero snapping. Renaming the
endpoints would not prove a valid physical wall or fix its geometry.

Inference: this ambiguity must remain explicit negative evidence. It need
not erase independently assembled, nonconflicting chains from a diagnostic
inventory, but a partial candidate list must never imply a complete universe.

Proposed change: add an explicit boolean shadow opt-in to the existing W4
assembler, requiring a fresh empty abstention output list. Before constructing
a WallCandidate with equal end-node IDs, retain the actual attempted chain,
raw endpoint indices/positions, original fragment geometry and source-parent
lineage as an ABSTAINED diagnostic row. Continue the same existing assembly
loop for other chains. Do not create a substitute wall, merge duplicate nodes,
change snap/rounding thresholds, elect a junction or bypass the constructor.
Default callers still execute their exact prior path and raise at the guard.

Related observed ambiguity: relationship lookup elects the first matching
junction ID if a caller supplies competing records; actual W3 already uses
node indices to avoid that ID alias. Endpoint lookup overwrites by rounded
position on the real source. Shadow mode
must instead retain all matching junctions and require unique actual incident
edge ownership. Unavailable or competing matches abstain the affected chain;
do not use a fallback node name to disguise ambiguity. Exact raw node indices
remain diagnostic addresses, never physical-wall equivalence proof. Index
these existing records once for lookup; do not build another topology graph.
Distinct source-owned junction IDs must not disguise identical endpoint
geometry. A coincident endpoint or non-simple fallback chain also stays
ABSTAINED, preserving its complete fragment inventory without manufacturing
a closed wall or a best-effort physical path.

The existing original-source diagnostic will opt in only in a separate third
mode. Retain the default and original indexed-zero failure controls. Require
an exact partition of actual W3-retained edges between candidate-owned and
abstained chains, with no transfer or dropped edge. Distinguish known chain
disposition from unavailable candidate membership. Report retained ancestry
without claiming source authentication from a bare graph; the byte-verified
source reader must independently validate every parent against its inventory.

Synthetic evidence must cover the real guard, unrelated valid chains, multiple
collisions, equal rounded IDs at distinct positions, absent/contradictory
lineage, strict configuration, whole default parity, mutation, replay,
permutations, transformations and segment splitting. Fresh original replay
must preserve all production receipts and independently show every retained
fragment's disposition. Existing viewport, wall-role/equivalence, frame,
measurement, candidate-universe and publication authorities remain mandatory.

Benchmark/source observations excluded from implementation: original source
SHA, project/page names, opening IDs and observed fragment counts are only
validation controls. None determines a chain's eligibility or ownership.

Untouched: frozen Full Plan V2 truth/denominators/evaluator/tolerances, source
PDFs, the 20,000 input cap, W3/default W4 identities, scale/measurement engines,
host binding, quantity/customer publication and W10 eligibility/deductions.
