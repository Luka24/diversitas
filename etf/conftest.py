"""Pytest discovery helper — ensures the project root (one level above `etf/`)
is on sys.path so `from shared import ...` resolves during tests. Also adds
`etf/` so `from diversitas import ...` resolves to this variant."""
import sys
from pathlib import Path

_VARIANT_ROOT = Path(__file__).resolve().parent          # DIVERSITAS/etf
_PROJECT_ROOT = _VARIANT_ROOT.parent                     # DIVERSITAS
for p in (_PROJECT_ROOT, _VARIANT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
