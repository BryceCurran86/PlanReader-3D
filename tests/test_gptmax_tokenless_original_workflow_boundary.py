from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow(filename):
    raw = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
    return raw, yaml.load(raw, Loader=yaml.BaseLoader)


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
