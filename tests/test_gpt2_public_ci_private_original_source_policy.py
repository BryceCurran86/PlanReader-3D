"""Public CI must not turn missing private drawings into fake source successes."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import conftest as source_ci


PRIVATE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
OTHER = Path("documents/sources/Other_Independent_Source.pdf")


def reads_private_pdf():
    return PRIVATE.read_bytes()


def synthetically_checks_source_abi_without_opening_any_pdf():
    return 42


def reads_a_different_source():
    return OTHER.read_bytes()


def calls_original_source_helper():
    return reads_private_pdf()


def test_original_source_detected_but_synthetic_in_same_module_runs():
    assert source_ci._code_uses_original_source(reads_private_pdf)
    assert source_ci._code_uses_original_source(calls_original_source_helper)
    assert not source_ci._code_uses_original_source(
        synthetically_checks_source_abi_without_opening_any_pdf
    )
    assert not source_ci._code_uses_original_source(reads_a_different_source)


def test_private_original_source_fixture_dependency_is_not_silently_ignored():
    source_fixture=SimpleNamespace(func=reads_private_pdf)
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
    supplied=tmp_path/"documents"/"sources"/PRIVATE.name
    supplied.parent.mkdir(parents=True)
    supplied.write_bytes(b"no original source, only policy test fixture")
    assert not source_ci._public_ci_source_policy_enabled()
    monkeypatch.setenv("PLANREADER_PRIVATE_ORIGINAL_POLICY","unknown")
    with pytest.raises(pytest.UsageError,match="invalid_private_original_source_ci_policy"):
        source_ci._public_ci_source_policy_enabled()


def test_local_literal_original_path_is_detected_without_invoking_it():
    def source_local():
        p=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
        return p.read_bytes()
    assert source_ci._code_uses_original_source(source_local)


def test_public_ci_skips_only_explicit_missing_source_and_not_synthetic(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PLANREADER_PRIVATE_ORIGINAL_POLICY",
                       "skip_missing_in_public_ci")
    fake_original=SimpleNamespace(function=reads_private_pdf,
        fixturenames=(),_fixtureinfo=None)
    fake_synthetic=SimpleNamespace(function=synthetically_checks_source_abi_without_opening_any_pdf,
        fixturenames=(),_fixtureinfo=None)
    assert source_ci._public_ci_source_policy_enabled()
    assert source_ci._test_requires_missing_original_pdf(fake_original)
    assert not source_ci._test_requires_missing_original_pdf(fake_synthetic)
