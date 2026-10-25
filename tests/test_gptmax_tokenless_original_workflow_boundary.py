"""Previously tokenless original jobs must use the same trusted-main boundary.

These tests execute only isolated synthetic shell/Git commands, never source
PDFs or construction producers. The existing dynamic token census owns the
shared credential checker and automatically includes these new provisioners.
"""
from pathlib import Path
from runpy import run_path
import os
import re
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SECURITY = run_path(str(ROOT / 'tests/test_gpt3_private_original_dynamic_workflow_census.py'))
Loader = SECURITY['Loader']
CHECK = SECURITY['check_original_token_boundary']
FILES = (
    'test-gptmax-native-paint-partition-shadow.yml',
    'test-gpt2-source-symbol-embedded-glyph.yml',
    'test_gpt2_maryborough_grid_component_completion.yml',
    'test_gpt2_freezer_exact_backtrack_normalization.yml',
    'gpt1-q5446-source-positive-floor-area.yml',
    'gpt1-3laurel-original-floor-area.yml',
    'gpt1-3laurel-source-positive-opening.yml',
    'gpt1-live-source-plan-metric-scope.yml',
    'test_only_gpt2_maryborough_core_host_scope.yml',
)


def _workflow(filename):
    if isinstance(filename, tuple):
        filename = filename[0]
    raw = (ROOT / '.github/workflows' / filename).read_text(encoding='utf-8')
    assert CHECK(raw) >= 1
    return raw, yaml.load(raw, Loader=Loader)


def _source_job(filename):
    wanted = filename[1] if isinstance(filename, tuple) else None
    raw, document = _workflow(filename)
    matches = [j for name,j in document['jobs'].items()
               if '${{ secrets.ORIGINAL_SOURCES_TOKEN }}' in str(j)
               and (wanted is None or name == wanted)]
    assert len(matches) == 1
    return matches[0]


CASES = tuple((filename,name) for filename in FILES
              for name,job in _workflow(filename)[1]['jobs'].items()
              if '${{ secrets.ORIGINAL_SOURCES_TOKEN }}' in str(job))


@pytest.mark.parametrize('filename', CASES)
def test_original_job_is_provisioned_and_private_steps_are_nonpublishing(filename):
    raw, document = _workflow(filename)
    assert document['permissions'] == {'contents': 'read'}
    job = _source_job(filename)
    steps = job['steps']
    provision = next(i for i, s in enumerate(steps)
                     if s.get('uses') == './.github/actions/provision-original-sources')
    assert steps[provision]['with']['allow-missing'] == 'false'
    assert steps[provision]['with']['names'].endswith('.pdf')
    source_commands = []
    for s in steps[provision + 1:]:
        command = s.get('run', '')
        if s.get('if') == 'always()':
            continue
        assert 'PRIVATE_ORIGINAL_COMMANDS' in command
        assert 'bash -euo pipefail "$private_script" > "$private_output" 2>&1' in command
        assert 'cat "$private_output"' not in command
        source_commands.append(command)
    assert source_commands
    assert 'actions/upload-artifact@' not in str(job)
    assert 'github.event.pull_request.head.sha' not in str(job)
    # Verify actual generated shell/heredoc grammar, including nested Python.
    for command in source_commands:
        subprocess.run(['bash', '-n'], input=command, text=True, check=True,
                       capture_output=True)


@pytest.mark.parametrize('filename', CASES)
@pytest.mark.parametrize('fail', (False, True))
def test_private_command_exit_and_output_are_preserved_without_leak(filename, fail, tmp_path):
    steps = _source_job(filename)['steps']
    command = next(s['run'] for s in steps if 'PRIVATE_ORIGINAL_COMMANDS' in s.get('run', ''))
    pattern = r"(<<'PRIVATE_ORIGINAL_COMMANDS'\n).*?(\nPRIVATE_ORIGINAL_COMMANDS\n)"
    fake = 'echo PRIVATE_PDF_CANARY\necho PRIVATE_STDERR_CANARY >&2\n'
    fake += 'false\necho UNREACHABLE_AFTER_FAILURE' if fail else 'true'
    command, replaced = re.subn(pattern, lambda m: m[1] + fake + m[2], command,
                               count=1, flags=re.S)
    assert replaced == 1
    result = subprocess.run(['bash', '-euo', 'pipefail'], input=command, text=True,
                            capture_output=True,
                            env={**os.environ, 'RUNNER_TEMP': str(tmp_path)})
    assert (result.returncode != 0) is fail
    emitted = result.stdout + result.stderr
    assert 'PRIVATE_PDF_CANARY' not in emitted
    assert 'PRIVATE_STDERR_CANARY' not in emitted
    assert 'UNREACHABLE_AFTER_FAILURE' not in emitted
    assert ('PRIVATE ORIGINAL STEP PASS' in emitted) is not fail
    private = '\n'.join(p.read_text() for p in tmp_path.glob('*.log'))
    assert 'PRIVATE_PDF_CANARY' in private
    assert 'UNREACHABLE_AFTER_FAILURE' not in private


@pytest.mark.parametrize('filename,test_path', (
    ('test_gpt2_freezer_exact_backtrack_normalization.yml',
     'tests/test_source_room_face_authority_v1.py'),
    ('test_gpt2_maryborough_grid_component_completion.yml',
     'tests/test_source_room_face_same_source_aliases.py'),
    ('test-gptmax-native-paint-partition-shadow.yml',
     'tests/test_gptmax_native_dimension_source_partition.py'),
))
def test_public_synthetic_checks_still_execute_on_pull_requests(filename, test_path):
    _, doc = _workflow(filename)
    assert 'pull_request' in doc['on']
    focused = doc['jobs']['focused']
    assert 'if' not in focused
    assert test_path in str(focused)
    assert 'secrets.' not in str(focused)
    assert 'documents/sources' not in str(focused)


@pytest.mark.parametrize('case', ('ancestor', 'same_head', 'foreign', 'malformed'))
def test_native_retention_baseline_must_be_a_proper_trusted_ancestor(case, tmp_path):
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, text=True,
                              capture_output=True, check=True).stdout.strip()
    git('init', '-q')
    git('config', 'user.name', 'Source neutral workflow test')
    git('config', 'user.email', 'test@example.invalid')
    git('commit', '--allow-empty', '-qm', 'ancestor')
    ancestor = git('rev-parse', 'HEAD')
    git('commit', '--allow-empty', '-qm', 'head')
    head = git('rev-parse', 'HEAD')
    foreign = git('commit-tree', 'HEAD^{tree}', '-m', 'unrelated root')
    baseline = {'ancestor': ancestor, 'same_head': head,
                'foreign': foreign, 'malformed': 'invalid; echo CANARY'}[case]
    step = next(s for s in _source_job(FILES[0])['steps']
                if s.get('name') == 'Validate explicit trusted main baseline before private source')
    target = tmp_path / 'job-env'
    result = subprocess.run(['bash', '-euo', 'pipefail'], input=step['run'],
                            cwd=tmp_path, text=True, capture_output=True,
                            env={**os.environ, 'BASELINE_SHA': baseline,
                                 'GITHUB_SHA': head, 'GITHUB_ENV': str(target)})
    assert (result.returncode == 0) is (case == 'ancestor')
    if case == 'ancestor':
        assert target.read_text() == f'BASELINE_SHA={ancestor}\n'
    else:
        assert not target.exists()
    assert 'CANARY' not in result.stdout


def test_native_baseline_receives_verified_source_before_running_comparison():
    job = _source_job(FILES[0])
    command = next(s['run'] for s in job['steps']
                   if s.get('name') == 'Exact trusted main baseline and head opening receipts')
    assert command.index('git worktree add') < command.index('copy_provisioned_originals_into_worktree.py')
    assert command.index('copy_provisioned_originals_into_worktree.py') < command.index('cd /tmp/native-partition-original-base')
    assert 'github.event.pull_request.base.sha' not in command


@pytest.mark.parametrize('filename', CASES)
def test_cleanup_removes_source_logs_scripts_and_reports(filename):
    cleanup = _source_job(filename)['steps'][-1]
    assert cleanup['if'] == 'always()'
    for path in ('documents/sources', 'artifacts', 'guarded-original-*.sh',
                 'guarded-original-*.log'):
        assert path in cleanup['run']
