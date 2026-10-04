import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_diagnostics_records import (
    test_diag_eviction_policy,
    test_diagnostics_are_thread_safe,
    test_diagnostics_records,
)


def test_suite() -> None:
    test_diagnostics_records()
    test_diag_eviction_policy()
    test_diagnostics_are_thread_safe()


if __name__ == "__main__":
    test_suite()
    print("eviction and thread-safety tests passed")
