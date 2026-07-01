"""Pytest discovery helper — ensures the project root is on sys.path."""
import sys
from pathlib import Path

_VARIANT_ROOT = Path(__file__).resolve().parent          # DIVERSITAS/momentum
_PROJECT_ROOT = _VARIANT_ROOT.parent                     # DIVERSITAS
for p in (_PROJECT_ROOT, _VARIANT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
