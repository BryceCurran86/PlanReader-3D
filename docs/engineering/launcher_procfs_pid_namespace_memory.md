# Namespace-correct source-run memory sampling

Observed path: `four_job_windows_launcher.run_logged` launches the original
source producer, then calls `sample_memory_kb` to enforce the memory budget.
On Linux, `_children_by_parent` reads the procfs process tree. In a sandbox
whose procfs is mounted outside its PID namespace, `Popen.pid` addresses the
inner namespace while `/proc/<pid>` addresses the outer one. Sampling that
directory can measure an unrelated process or zero memory.

Resolve the root process by matching both its PID namespace inode and its
innermost `NSpid`, then retain the existing outer-procfs descendant census.
The ordinary same-namespace case has a direct lookup. Missing, malformed,
foreign or ambiguous mappings retain the existing unavailable result; no
candidate is selected by order. Windows memory sampling is unchanged.

The fix changes only runtime accounting and enforcement. It does not change
source bytes, extraction policy, quantity authority, memory thresholds,
opening caps, frozen truth or scoring. Tests cover ordinary and host-mounted
procfs, unrelated numeric PIDs, process-tree aggregation, duplicate matches,
invalid metadata and actual launcher memory-limit/peak reporting. Procfs tests
are Linux-specific and do not require Windows symlink privileges.
