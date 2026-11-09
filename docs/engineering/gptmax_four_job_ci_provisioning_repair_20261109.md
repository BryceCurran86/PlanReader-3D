# Four-job CI source provisioning and duplicate-run repair

## Observed behavior

Merged production head `ffd73f42de0802bd62ffa528fb8843706e86c67a` passed exact-head full Python 3.13/3.14 CI and protected original signed/customer retention. Its main push exposed two older viewport workflows that run `sha256sum --check` on a PDF never provisioned into the public checkout. Runs 42556993112 and 42556993013 failed before their original tests. A nonempty repository variable alone does not download an original.

The three dedicated runner workflows also execute the entire public suite on pull requests, duplicating the unchanged required CI dual-Python matrix three times.

## Change

Keep public source-neutral viewport regressions on PR/main push, with the existing explicit missing-private-source policy and a visible original NOT RUN notice. Actual original tests remain fail-closed: owner and rerun owner, manual dispatch on merged main, exact checkout, existing SHA-verified provisioner, unchanged source SHA assertion, original test execution, no source artifacts or raw source logs, unconditional cleanup. These jobs can no longer mistake a configured repository variable for provisioned source bytes.

Keep focused role/customer regressions and frozen/provider guards on every matching PR. Dedicated full matrices still run for their isolated branch pushes/manual dispatch; required `CI / test (3.13)` and `(3.14)` continue to run the full tests tree on PR/main. Dependency downloads use the existing setup-python pip cache.

## Authority boundaries

CI scheduling and existing source provisioning only. Production modules, source PDFs, signed/customer fixtures, source text defaults, geometry caps/snaps, identity maps, frozen truth, evaluator and measurement authorities are untouched. Public success is not source-positive proof. No new quantity or accuracy is claimed.

## Validation

Full CI on the first candidate exposed an older push-NOT-RUN guard that assumed every source job used the legacy variable gate. Its census now retains every SHA-reading job, recognizes only the already validated owner/rerun-owner/manual/main provisioned source boundary, and requires the public NOT RUN notice. Adversarial tests retain rejection of unsafe checkout, removed provisioning/cleanup/notice, PR execution and foreign rerun. The legacy push-variable convention and its 29-job census remain checked.

Run existing source-neutral viewport tests, workflow trust/dynamic census, PR trigger/path coverage, coordinated CI entrypoint guards, and frozen/provider/truth separation. Inspect YAML and syntax-check all shell bodies. Before merge, run standard full dual-Python CI on a fixed head and a protected exact-original run of the affected viewport tests with genuine original execution and no skips. Source/customer code is unchanged from the protected-retention-tested merged tree.
