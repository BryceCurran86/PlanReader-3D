"""Public CI must not turn missing private drawings into fake source successes."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import conftest as source_ci


PRIVATE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
LOT16 = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
OTHER = Path("documents/sources/Other_Independent_Source.pdf")


def reads_private_pdf():
    return PRIVATE.read_bytes()


def synthetically_checks_source_abi_without_opening_any_pdf():
    return 42


def reads_a_different_source():
    return OTHER.read_bytes()


def reads_lot16_pdf():
    return LOT16.read_bytes()


def calls_original_source_helper():
    return reads_private_pdf()


def test_original_source_detected_but_synthetic_in_same_module_runs():
    assert source_ci._code_uses_original_source(globals()['reads_private_pdf'])
    assert source_ci._code_uses_original_source(globals()['calls_original_source_helper'])
    assert not source_ci._code_uses_original_source(
        synthetically_checks_source_abi_without_opening_any_pdf
    )
    assert not source_ci._code_uses_original_source(globals()['reads_a_different_source'])
    assert source_ci._code_uses_original_source(globals()['reads_lot16_pdf'])
    assert not source_ci._code_uses_original_source(
        globals()['reads_lot16_pdf'],
        original_names=frozenset({source_ci._MARYBOROUGH_ORIGINAL_NAME}),
    )


def test_private_original_source_fixture_dependency_is_not_silently_ignored():
    source_fixture=SimpleNamespace(func=globals()['reads_private_pdf'])
    info=SimpleNamespace(name2fixturedefs={"original_pdf":[source_fixture]})
    item=SimpleNamespace(function=synthetically_checks_source_abi_without_opening_any_pdf,
                         fixturenames=("original_pdf",),_fixtureinfo=info)
    assert source_ci._test_requires_missing_original_pdf(item)
    item.fixturenames=()
    assert not source_ci._test_requires_missing_original_pdf(item)


def test_private_source_policy_requires_explicit_public_ci_optin(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PLANREADER_PRIVATE_ORIGINAL_POLICY",raising=False)
    assert not source_ci._public_ci_source_policy_enabled()
    monkeypatch.setenv("PLANREADER_PRIVATE_ORIGINAL_POLICY",
                       "skip_missing_in_public_ci")
    assert source_ci._public_ci_source_policy_enabled()
    sources = tmp_path / "documents" / "sources"
    sources.mkdir(parents=True)
    maryborough = sources / source_ci._MARYBOROUGH_ORIGINAL_NAME
    maryborough.write_bytes(b"no original source, only policy test fixture")
    assert source_ci._public_ci_source_policy_enabled()
    lot16 = sources / source_ci._LOT16_ARCHITECTURAL_ORIGINAL_NAME
    lot16.write_bytes(b"no original source, only policy test fixture")
    assert not source_ci._public_ci_source_policy_enabled()
    monkeypatch.setenv("PLANREADER_PRIVATE_ORIGINAL_POLICY","unknown")
    with pytest.raises(pytest.UsageError,match="invalid_private_original_source_ci_policy"):
        source_ci._public_ci_source_policy_enabled()


def test_local_literal_original_path_is_detected_without_invoking_it():
    def source_local():
        p=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
        return p.read_bytes()
    def lot16_local():
        p=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
        return p.read_bytes()
    assert source_ci._code_uses_original_source(source_local)
    assert source_ci._code_uses_original_source(lot16_local)


def test_public_ci_skips_only_explicit_missing_source_and_not_synthetic(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLANREADER_PRIVATE_ORIGINAL_POLICY",
                       "skip_missing_in_public_ci")
    fake_original=SimpleNamespace(function=globals()['reads_private_pdf'],
        fixturenames=(),_fixtureinfo=None)
    fake_synthetic=SimpleNamespace(function=synthetically_checks_source_abi_without_opening_any_pdf,
        fixturenames=(),_fixtureinfo=None)
    assert source_ci._public_ci_source_policy_enabled()
    assert source_ci._test_requires_missing_original_pdf(fake_original)
    assert not source_ci._test_requires_missing_original_pdf(fake_synthetic)
    fake_lot16=SimpleNamespace(function=globals()['reads_lot16_pdf'],
        fixturenames=(),_fixtureinfo=None)
    assert source_ci._test_requires_missing_original_pdf(fake_lot16)
    sources = tmp_path / "documents" / "sources"
    sources.mkdir(parents=True)
    (sources / source_ci._MARYBOROUGH_ORIGINAL_NAME).write_bytes(b"fixture")
    assert source_ci._public_ci_source_policy_enabled()
    assert not source_ci._test_requires_missing_original_pdf(fake_original)
    assert source_ci._test_requires_missing_original_pdf(fake_lot16)
