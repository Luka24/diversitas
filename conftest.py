"""Top-level pytest conftest — ensures the project root is on sys.path so
`from shared import ...` resolves when running `pytest shared/tests/` from
the project root."""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
