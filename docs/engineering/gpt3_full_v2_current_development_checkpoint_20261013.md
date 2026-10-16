# GPT3 Full V2 current development checkpoint — 2026-10-13

This checkpoint prevents the verified Lot16 development result from being
misreported as a full-suite product accuracy number.

It reads the **SHA-256 pinned, committed** original-source eight-opening signed output
(`docs/engineering/lot16_original_signed_eight_row_20261015/`, from GitHub run 38636511093, original producer
head `4e5aedf085cf63f92dac0935132b1e1c1dbaa178`), independently re-verifies the sealed fingerprint and the
customer-row bijection, then replays its authenticated benchmark-side identity map through the unchanged
four-project Full Plan V2 development scoreboard. The older seven-row committed archive remains intact; this
checkpoint does not rewrite it. No other project is supplied unless it has an
independently verified sealed production run and exact identity map.

Expected current result:

- configured projects: **4**
- frozen denominator: **120**
- executed projects: **1**
- executed denominator: **27**
- execution coverage: **22.5%**
- Lot16 matched within tolerance: **8**
- Lot16 missed: **19**
- observed accuracy on executed denominator: **8 / 27 = 29.6296296%**
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
status 2 because the four-project suite is incomplete.

The fixture files are authenticated by `SHA256SUMS` in the fixture directory and by the sealed-run
fingerprint `ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb`. They are byte-identical to the
production output of the source-positive run (GitHub artifact `11929406140`, ZIP SHA-256
`950e1074d270e6b1d4558b165e5345cf49b2ac0c962a3cc8edf420f11f67bd91`, which GitHub retention deletes on
2026-11-13) and to the signed originals compared after every owner merge. `tests/test_lot16_signed_eight_row_fixture.py`
re-verifies the fixture in the ordinary CI run. The genuinely new source-sealed and customer-verified item is
original physical opening `physical_opening_existence_2b2a91e8afaf8b7e9a3e07605a80a4a9`, 1215 SGW obs, 1.8 m²,
with unique original native source location evidence. The exact 27-object project reconciler has already passed on
that output in GitHub Actions run `38736919991`; the checkpoint replays the full partial four-project development
summary without inventing any unavailable project.

A changed fixture byte fails the hash check; never substitute an unverified output or silently fall back to
seven rows. Any non-null full
development accuracy at this checkpoint is a regression.

This does not modify benchmark truth, source manifests, object universes,
denominators, tolerances, evaluator logic, or production authority.
