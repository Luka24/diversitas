"""Zgradi samostojno mapo diversitas-lean iz tega repozitorija.

Izvirnik se ne dotakne. Nastane kopija, v kateri sta lean/ in shared/ zdruzena
v en sam paket, tako da mapa deluje sama zase, brez poti nazaj v ta repozitorij.

Pozeni znova, kadarkoli se kaj spremeni. Ciljno mapo prepise.

    python testing/scripts/zgradi_produkcijo.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CILJ = ROOT.parent / "diversitas-lean"

# iz katere datoteke v katero. shared/ se preseli v paket diversitas/.
KODA = {
    "lean/diversitas/__init__.py": "diversitas/__init__.py",
    "lean/diversitas/config.py": "diversitas/config.py",
    "lean/diversitas/strategy.py": "diversitas/strategy.py",
    "lean/diversitas/dashboard.py": "diversitas/dashboard.py",
    "lean/diversitas/backtest.py": "diversitas/backtest.py",
    "shared/indicators.py": "diversitas/indicators.py",
    "shared/warmup.py": "diversitas/warmup.py",
    "shared/costs.py": "diversitas/costs.py",
    "shared/data_source.py": "diversitas/data_source.py",
    "lean/diversitas/tests/__init__.py": "tests/__init__.py",
    "lean/diversitas/tests/test_strategy.py": "tests/test_strategy.py",
    "lean/diversitas/tests/test_donchian.py": "tests/test_donchian.py",
    "lean/diversitas/tests/test_gate_rows.py": "tests/test_gate_rows.py",
    "lean/diversitas/tests/test_chart_hover.py": "tests/test_chart_hover.py",
    "lean/diversitas_lean.pine": "diversitas_lean.pine",
    "deployment.toml": "deployment.toml",
}

PODATKI = {
    "testing/data/sources/BTC_binance_warmup.parquet": "data/BTC_binance.parquet",
    "testing/data/sources/ETH_binance.parquet": "data/ETH_binance.parquet",
    "testing/data/baseline_lean.json": "data/baseline.json",
    "testing/data/baseline_lean.txt": "data/baseline.txt",
}

# shared/ ne obstaja vec, vse je v paketu diversitas
UVOZI = [
    (r"from shared import indicators as ind", "from diversitas import indicators as ind"),
    (r"from shared\.data_source import", "from diversitas.data_source import"),
    (r"from shared\.warmup import", "from diversitas.warmup import"),
    (r"from shared\.costs import", "from diversitas.costs import"),
    (r"from shared import", "from diversitas import"),
]


def prenesi(rel_in: str, rel_out: str) -> None:
    src = ROOT / rel_in
    dst = CILJ / rel_out
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix in (".parquet", ".pine"):
        shutil.copy2(src, dst)
        return
    s = src.read_text(encoding="utf-8")
    for a, b in UVOZI:
        s = re.sub(a, b, s)
    dst.write_text(s, encoding="utf-8")


def main() -> int:
    if not (ROOT / "lean" / "diversitas" / "strategy.py").exists():
        print("Nisem v pravem repozitoriju.")
        return 2

    if CILJ.exists():
        shutil.rmtree(CILJ)
    CILJ.mkdir(parents=True)

    for a, b in KODA.items():
        prenesi(a, b)
    for a, b in PODATKI.items():
        prenesi(a, b)

    # dashboard.py je racunal poti glede na staro postavitev z dvema nivojema
    d = CILJ / "diversitas" / "dashboard.py"
    s = d.read_text(encoding="utf-8")
    staro = """_VARIANT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _VARIANT_ROOT.parent
for p in (_PROJECT_ROOT, _VARIANT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))"""
    novo = """# Koren projekta je mapa nad paketom. Uporablja se za branje deployment.toml.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))"""
    if staro in s:
        s = s.replace(staro, novo, 1)
    else:
        print("OPOZORILO: nastavitve poti v dashboard.py nisem prepoznal")
    d.write_text(s, encoding="utf-8")

    print(f"zgrajeno v {CILJ}")
    for p in sorted(CILJ.rglob("*")):
        if p.is_file():
            print(f"   {p.relative_to(CILJ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
