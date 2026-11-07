# Main host and nominal-axis regression repair

Base: `2aebbfd5bdd04d005cce06b4d6467b0442ae0821`.
Coordination: #4135, claim 6694890388. Owner: GPT MAX.

## Observed before editing production

Read AGENTS.md, the three-agent succession handover, the engineering
playbook, adopted W1-W10 architecture, topology specification, benchmark
firewall and CI configuration. Traced the actual host/frame and label paths:

- `OpeningHostBindingProducer.publish_scope` calls
  `_resolve_raster_whole_wall_host` through
  `_raster_whole_wall_axis_data_is_role`. That last predicate adds half the
  wall thickness to the existing cross-render centerline equality allowance.
- `OpeningHostFrameProducer._raster_whole_wall_frame` independently reuses
  that host resolver, so the widened predicate also admits an off-centre
  whole-wall frame.
- `OpeningLabelDimensionProducer.ordered_compact_axes_shadow` calls the
  existing source-owned label/area publisher, then gives an unordered pair
  height/width ownership using only typical numeric ranges when the explicit
  compact HHWW convention did not resolve it.

Completed public main CI 42284935827 reports three failures in the existing
source recovery, raster whole-wall host and raster frame tests. Its other
30,502 passing tests do not negate these failures.

## Inference

Centerline equality and membership somewhere inside a thick wall band are
different propositions. Thickness cannot enlarge a centerline equality
allowance. Two plausible dimensions plus a door/window type cannot establish
which source axis each dimension owns. Neither condition authorizes physical
host/frame or nominal axis promotion.

## Proposed bounded repair

Restore only the original whole-wall centerline predicate and explicit HHWW
axis requirement. Keep the remaining structural implementation for separate
source validation. Preserve the original label/area publisher and complete
legacy outputs. Extend existing tests with thick/rotated off-centre walls and
both orders of an authentic unordered dimension pair. Existing assertions
must continue to reject these cases.

Expected abstentions: an off-centre raster candidate produces no whole-wall
host/frame; an unordered pair produces no ordered nominal axes. Centered
source-owned hosts and explicitly owned compact HHWW axes remain valid.

## Benchmark observations excluded from implementation

No reference quantities, item IDs, source identity maps or scorer tolerances
are inputs to this repair. No benchmark, private original PDF, source bytes,
20,000-primitive cap, 2.5-point snap, quantity/customer writer, Claude OFFICE
file or shared frame/runtime implementation is changed. A source-private
replay and exact-head CI remain required before a release merge. This repair
does not itself establish a new customer quantity or score.

## Validation

- Before the production repair: 23 failures / 40 passes, reproducing the
  three existing failures and 20 new adversarial cases.
- After the repair: all 63 cases pass; the wider existing host/frame/label
  regression suite passes 367 tests (local Python 3.12.14, repository-pinned
  core geometry/PDF dependencies).
- Full Plan V2 integrity, production-provider/gold isolation, undefined-name
  checks and `git diff --check` pass.
- Protected original-source/customer retention and exact-head Python
  3.13/3.14 full CI remain pending. Local source-unavailable checks do not
  establish those results.
