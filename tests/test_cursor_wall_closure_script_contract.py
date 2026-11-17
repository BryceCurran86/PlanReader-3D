"""Static contract for the Windows-only private-original room-closure runner.

Public CI does not have a Windows PowerShell interpreter, so prevent the
previous concatenation/unterminated ValidatePattern corruption from merging
despite a green Python CI. Does not read or expose original plan files.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "run_antigravity_wall_closure.ps1"
CURSOR = ROOT / "tools" / "run_cursor_wall_closure.ps1"


def test_private_source_runner_has_one_complete_powershell_parameter_block():
    raw = RUNNER.read_text(encoding="utf-8")
    assert len(re.findall(r"(?m)^param\s*\(", raw)) == 1
    assert len(re.findall(r"(?m)^\[CmdletBinding\(\)\]", raw)) == 1
    assert len(re.findall(r"(?m)^\$ErrorActionPreference\s*=", raw)) == 1
    assert "[ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256" in raw
    assert "^[0-9a-fA-F]{64}\n" not in raw
    assert "$hasNewRegression" not in raw
    assert len(re.findall(r"(?m)^\s*finally\s*\{", raw)) == 1
    assert raw.rstrip().endswith("}")


def test_source_hash_and_public_checkout_guard_precede_private_replay():
    raw = RUNNER.read_text(encoding="utf-8")
    sha = raw.index("Get-FileHash -LiteralPath $source -Algorithm SHA256")
    mismatch = raw.index('if ($sha -ne $ExpectedSha256.ToLowerInvariant())')
    output = raw.index('New-Item -ItemType Directory -Path $runDir')
    original_cli = raw.index("'tools/run_original_footprint_first.py'")
    private_guard = raw.index("must be OUTSIDE the public repository checkout")
    assert private_guard < sha < mismatch < output < original_cli
    assert "commercial authority" in raw
    assert "source_sha256 = $sha" in raw


def test_cursor_wrapper_forwards_required_original_hash_without_default():
    raw = CURSOR.read_text(encoding="utf-8")
    assert "[ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256" in raw
    assert "ExpectedSha256 = $ExpectedSha256" in raw
    assert "run_antigravity_wall_closure.ps1" in raw
    assert len(re.findall(r"(?m)^param\s*\(", raw)) == 1
