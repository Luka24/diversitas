"""Koliko prodaj ustvari knjiga, v primerjavi s kupi in drzi.

    python testing/scripts/stevilo_odsvojitev.py

Vsak izstop je prodaja, in vsako mesecno uravnavanje je do sest prodaj. Kupi
in drzi ima eno.

To ni davek. Fizicna oseba v Sloveniji od dobicka pri prodaji kriptovalut
dohodnine ne placa, razen ce FURS trgovanje steje za dejavnost (stanje oktober
2026; predlog 25-odstotnega davka je bil novembra 2025 umaknjen). Pri presoji
dejavnosti FURS navaja vrednost prometa in stevilo transakcij, zato je ta
stevilka vseeno vredna poznati. Lestvice v shared/tax.py so za vrednostne
papirje in za kripto ne veljajo.

Izhod: testing/data/stevilo_odsvojitev.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd

from graded_alti import SREDSTVA, cene, pozicija


def main() -> int:
    C = cene()
    POS = {s: pozicija(C[s], None) for s in SREDSTVA}
    idx = POS["BTC"].index
    print("Okno %s do %s, %.1f let.\n"
          % (idx[0].date(), idx[-1].date(), len(idx) / 365.0))

    out = {"po_sredstvu": {}}
    skupaj = 0
    print("  %-6s%10s%10s%14s" % ("sred", "vstopov", "izstopov", "izstopov/leto"))
    for s in SREDSTVA:
        d = POS[s].reindex(idx).fillna(0.0).diff().fillna(0.0)
        vst, izs = int((d > 0.001).sum()), int((d < -0.001).sum())
        leta = len(POS[s]) / 365.0
        skupaj += izs
        out["po_sredstvu"][s] = {"vstopov": vst, "izstopov": izs,
                                 "na_leto": round(izs / leta, 1)}
        print("  %-6s%10d%10d%14.1f" % (s, vst, izs, izs / leta))

    mes = len(pd.Series(1, index=idx).resample("ME").last())
    out.update({"izstopov_skupaj": skupaj, "mesecev_uravnavanja": mes,
                "uravnavanje_najvec": mes * len(SREDSTVA), "kupi_in_drzi": 1})
    print("\n  prodaj iz signala skupaj         %d" % skupaj)
    print("  mesecnih uravnavanj              %d, vsako do %d prodaj -> do %d"
          % (mes, len(SREDSTVA), mes * len(SREDSTVA)))
    print("  kupi in drzi                     1")

    pot = ROOT / "testing" / "data" / "stevilo_odsvojitev.json"
    pot.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nZapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
