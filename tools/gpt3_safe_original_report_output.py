"""Create-only original-source diagnostic publication.

A source-authenticated report is never permission to overwrite another report,
customer output, sealed run, source PDF or frozen benchmark file. Keep all
existing bytes unchanged, including in a competing-writer race.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Callable, Iterable


def preflight_new_diagnostic(
    output: Path, *, protected_roots: Iterable[Path | None],
) -> None:
    """Reject ambiguous output ownership before original PDFs are read."""
    if not isinstance(output, Path):
        raise TypeError("diagnostic output must be a Path")
    destination = output.resolve()
    if output.is_symlink():
        raise FileExistsError("original-source diagnostic output must be a new path")
    if not output.name or output.name in (".", ".."):
        raise ValueError("original-source diagnostic output name is missing")
    for root in protected_roots:
        if root is None:
            continue
        source = Path(root).resolve()
        if destination == source or destination.is_relative_to(source):
            raise ValueError("original-source diagnostic may not overwrite protected evidence")
    if output.exists():
        raise FileExistsError("original-source diagnostic output must be a new path")


def write_new_diagnostic(
    output: Path, encoded: str, *, protected_roots: Iterable[Path | None],
    verify_inputs: Callable[[], None] | None = None,
) -> None:
    """Stage/fsync report before exclusive hard-link; unlink on failure.

    os.link is exclusive: it does not replace an existing target even if
    another producer claims that target after the first preflight. No private
    document bytes are copied to the output.
    """
    protected = tuple(protected_roots)
    preflight_new_diagnostic(output, protected_roots=protected)
    if type(encoded) is not str:
        raise TypeError("diagnostic payload must be a Unicode string")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    our_output_created = False
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=output.parent, encoding="utf-8", newline="\n",
            prefix=".gpt3-original-report-", suffix=".tmp", delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        preflight_new_diagnostic(output, protected_roots=protected)
        # Exact source/customer/frozen-input receipts must remain stable
        # through output staging, not just while the report was calculated.
        if verify_inputs is not None:
            verify_inputs()
        os.link(temp, output)
        our_output_created = True
        if verify_inputs is not None:
            verify_inputs()
        # Exclusive creation alone cannot prevent another writer from
        # replacing the destination before this function returns. An input
        # recheck is not an output-identity check: fail closed if the linked
        # report no longer refers to the staged bytes.
        try:
            still_ours = output.samefile(temp)
        except OSError as exc:
            raise ValueError("original-source diagnostic output changed during publication") from exc
        if not still_ours:
            raise ValueError("original-source diagnostic output changed during publication")
    except BaseException:
        if our_output_created and temp is not None:
            # Retain another writer's output if it replaced ours after link.
            try:
                still_ours = output.samefile(temp)
            except OSError:
                still_ours = False
            if still_ours:
                output.unlink(missing_ok=True)
        raise
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
