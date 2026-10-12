# GPT3 Full V2 current development checkpoint — 2026-10-13

This checkpoint prevents the verified Lot16 development result from being
misreported as a full-suite product accuracy number.

It replays the committed, source-authenticated Lot16 sealed run and exact
benchmark-side identity map through the unchanged four-project Full Plan V2
development scoreboard. No other project is supplied unless it has an
independently verified sealed production run and exact identity map.

Expected current result:

- configured projects: **4**
- frozen denominator: **120**
- executed projects: **1**
- executed denominator: **27**
- execution coverage: **22.5%**
- Lot16 matched within tolerance: **7**
- Lot16 missed: **20**
- observed accuracy on executed denominator: **7 / 27 = 25.9259259%**
- full development accuracy: **null**
- full precision-adjusted accuracy: **null**

Missing executions must remain explicit for:

- `au_qld_3laurel`
- `au_qld_maryborough_service_station`
- `au_qld_q5446_armstrong32_harlequin`

Maryborough has a real three-row generic floor-area sealed source input on main,
but the exact original FT3 diagnostic currently fails first at
`FT3_DEFINITION_UNAVAILABLE`. Those floor-area rows therefore cannot be
promoted to the frozen FT3 floor-finish objects.

The workflow intentionally expects the development-scoreboard CLI to exit with
status 2 because the four-project suite is incomplete. Any non-null full
development accuracy at this checkpoint is a regression.

This does not modify benchmark truth, source manifests, object universes,
denominators, tolerances, evaluator logic, or production authority.
