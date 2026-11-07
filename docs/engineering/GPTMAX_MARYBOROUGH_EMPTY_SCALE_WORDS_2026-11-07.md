# Maryborough: do not enumerate scale geometry without authenticated labels

Base: fixed integration candidate #4224, `4caa71a92`. Owner: GPT MAX.

## Observed before editing production

Read the agent contract, succession handover, engineering playbook and actual
room-area integration/scale paths. `PhysicalScaleProducer.publish_scope`
authenticates original source, page coverage and viewport, then obtains scoped
trusted words. It still materializes visible segments from the entire snapshot
before invoking `_bar_candidates`, which already returns an empty tuple for
empty words. Each visible observation is resolved through source authority.

On the SHA-verified Maryborough original, the existing producer ingested pages
7 and 11 with 81,854 visible / 2,676 text records in 19.327 seconds. The existing
scale word reader returned zero trusted words on each page (0.068 seconds
initially, then cached). No source strings or geometry are published here.

## Inference and proposed change

With no authenticated scoped labels, no geometry can create an accepted graphic
scale bar. Return the existing PHYSICAL_SCALE_BAR_UNAVAILABLE abstention before
enumerating that unused geometry. Retain original revision, byte, coverage and
viewport authentication, cached-source revalidation and every positive bar
predicate. This is not a physical-scale grant or a change to detection rules.

## Expected validation

An authentic label-free source produces exactly the old abstention while doing
no segment enumeration. Source mutation after that negative result still fails
integrity validation. Existing positive/negative scale and room/customer tests
must pass. The full original Maryborough role must be reexecuted with the same
memory/time budget before claiming runtime completion. Its existing stage/stack
observation is separate and confers no source or quantity authority.

## Benchmark boundary

No source PDF, reference quantity, mapping, benchmark file, 20,000 primitive cap,
2.5-point snap, geometry or customer writer changes. No FIRM quantity or score is
claimed by this optimization.

## Local validation completed

The new real-source-contract synthetic regression fails on the parent at the
otherwise unnecessary visible-segment call, then passes after this repair.
The existing physical-scale/cache/tick/retrace/bridge/room-area suite passes
65 tests with one optional/source skip. Changed-source negative-cache checks
still raise the existing integrity failure. Positive scale-bar tests remain
unchanged. Local Python 3.12.14 with pinned core dependencies; full exact-head
dual-Python and original full-role/customer acceptance remain pending.
