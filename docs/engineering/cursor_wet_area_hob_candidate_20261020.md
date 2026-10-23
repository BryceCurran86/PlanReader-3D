# Architecture: wet-area hob geometry stays CANDIDATE

## Observed repository behavior

`evaluate_hob` returns `CORROBORATED` when caller centerline, width, and height pass local bounds. `compute_wet_area_takeoff` then treats those hobs as corroborated and mints `CORROBORATED` whenever `room_gross_floor_area_sqm > 0`. Commercial flags are already False.

## Inference

Caller geometry bounds are not independently re-resolved hob / SourceRoomFace ownership. A positive caller floor area is not membrane or tiling authority.

## Proposed change

Return `CANDIDATE` on the hob success path. Takeoff status is `CANDIDATE` when gross area is positive, else `ABSTAINED`. Takeoff still includes only `CORROBORATED` hobs, so candidate hobs do not enter tiling or upturn totals.

## Benchmark observations that must not influence implementation

`FT2` and expected wet-area BOQ quantities are not inputs. Test finish-code strings stay caller-supplied fixtures only.
