"""Preveri lestvico mehanizma z merili, ki nimajo patologije negativnega Sortina.

    python testing/scripts/preveri_mehanizem.py

ZAKAJ
Lestvica v porocilu je bila zgrajena na Sortinu v padajocem trgu. Ko je stevec
negativen, se razmerje obnasa narobe:

    povprecen donos -5 %, nihanje navzdol 10 %   ->  Sortino -0,50
    povprecen donos -5 %, nihanje navzdol 20 %   ->  Sortino -0,25

Druga vrstica izgleda boljse, cetudi je izguba enaka in tveganje vecje. Zato se
razlicic, ki izgubljajo, NE sme razvrscati po Sortinu.

KAJ SE MERI NAMESTO TEGA
Enoznacna merila, pri katerih vec pomeni vec:

    izguba v padcu       koliko odstotkov kapitala se izgubi na dneh, ko je
                         cena pod 200-dnevnim povprecjem. Zlozeno, ne povprecje
    najhujsi padec       znotraj medvedjih obdobij
    izpostavljenost      povprecna pozicija na teh dneh
    izguba na enoto      izguba v padcu deljena z izpostavljenostjo. Odgovori
                         na vprasanje, ali je vec izgube samo posledica tega,
                         da si bil vec casa tam

Zadnje je bistveno. Ce je izguba sorazmerna izpostavljenosti, je mehanizem samo
racunovodstvo. Ce raste hitreje od izpostavljenosti, je mehanizem prava
ugotovitev.

Merjeno na BTC, cela zgodovina, 0,30 % na stran.

Izhod: testing/data/preveri_mehanizem.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from itertools import product
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, _cfg, cene, pozicija
from ansambel import DC_MREZA, OSNOVA, TL_MREZA, ena_pozicija
from diversitas.strategy import position, run_strategy
from shared.warmup import trim_warmup


def z_dnom(raw, dno: float) -> pd.Series:
    cfg = replace(_cfg(), bear_alloc_pct=dno)
    return position(trim_warmup(run_strategy(raw, config=cfg).df), cfg).astype(float)


def razclenitev(p: pd.Series, ret: pd.Series, maska: pd.Series) -> dict:
    """Enoznacna merila na podmnozici dni."""
    t = p.diff().abs().fillna(0.0)
    r = (p * ret - t * FEE).fillna(0.0)
    rm = r[maska].to_numpy(float)
    if len(rm) < 30:
        return {}
    eq = np.cumprod(1 + rm)
    dd = eq / np.maximum.accumulate(eq) - 1
    izp = float(p[maska].mean())
    zlozeno = float((eq[-1] - 1) * 100)
    return {
        "zlozeno": round(zlozeno, 1),
        "letno": round(float((eq[-1] ** (PPY / len(rm)) - 1) * 100), 1),
        "maxdd": round(float(dd.min() * 100), 1),
        "izpost": round(izp * 100, 1),
        "na_enoto": round(zlozeno / (izp * 100), 2) if izp > 0 else np.nan,
        "nihanje_navzdol": round(float(
            np.sqrt(np.mean(np.minimum(rm, 0.0) ** 2)) * np.sqrt(PPY) * 100), 1),
        "sortino": round(float(rm.mean() * PPY / (
            np.sqrt(np.mean(np.minimum(rm, 0.0) ** 2)) * np.sqrt(PPY))), 2),
        "dni": len(rm),
    }


def main() -> int:
    C = cene()
    raw = C["BTC"]

    V = {
        "dno 0 %": z_dnom(raw, 0.0),
        "dno 5 % (danes)": z_dnom(raw, 5.0),
        "dno 10 %": z_dnom(raw, 10.0),
        "ansambel DC (5)": None,
        "ansambel TL (5)": None,
        "ansambel oba (25)": None,
        "stopnje k>=1": pozicija(raw, 1),
        "stopnje k>=2": pozicija(raw, 2),
        "stopnje k>=3": pozicija(raw, 3),
    }
    P = {}
    for k in {OSNOVA} | {(t, OSNOVA[1]) for t in TL_MREZA} \
            | {(OSNOVA[0], d) for d in DC_MREZA} | set(product(TL_MREZA, DC_MREZA)):
        P[k] = ena_pozicija(raw, *k)
    V["ansambel TL (5)"] = pd.concat(
        [P[(t, OSNOVA[1])] for t in TL_MREZA], axis=1).mean(axis=1)
    V["ansambel DC (5)"] = pd.concat(
        [P[(OSNOVA[0], d)] for d in DC_MREZA], axis=1).mean(axis=1)
    V["ansambel oba (25)"] = pd.concat(
        [P[k] for k in product(TL_MREZA, DC_MREZA)], axis=1).mean(axis=1)

    idx = V["dno 5 % (danes)"].index
    for v in V.values():
        idx = idx.intersection(v.index)
    V = {k: v.reindex(idx) for k, v in V.items()}
    ret = raw["close"].pct_change().reindex(idx).fillna(0.0)

    ma200 = raw["close"].rolling(200).mean().reindex(idx)
    bik = (raw["close"].reindex(idx) > ma200).fillna(False)
    medved = ~bik

    print("BTC, %s do %s, %d dni. Medvedjih dni: %d (%.0f %%)"
          % (idx[0].date(), idx[-1].date(), len(idx), int(medved.sum()),
             medved.mean() * 100))
    print("0,30 %% na stran. Medvedji dan = cena pod 200-dnevnim povprecjem.\n")

    out = {}
    print("V PADAJOCEM TRGU")
    print("  %-20s%10s%10s%10s%10s%12s%10s"
          % ("razlicica", "zlozeno", "letno", "MaxDD", "izpost",
             "na enoto", "Sortino"))
    vrstice = []
    for n, v in V.items():
        m = razclenitev(v, ret, medved)
        out.setdefault("medved", {})[n] = m
        vrstice.append((n, m))
        print("  %-20s%9.1f%%%9.1f%%%9.1f%%%9.1f%%%12.2f%10.2f"
              % (n, m["zlozeno"], m["letno"], m["maxdd"], m["izpost"],
                 m["na_enoto"], m["sortino"]))

    print("\n  isto, urejeno po ZLOZENI IZGUBI, od najmanjse")
    for n, m in sorted(vrstice, key=lambda x: -x[1]["zlozeno"]):
        print("     %-20s%9.1f%%   izpost %4.1f %%   na enoto %6.2f"
              % (n, m["zlozeno"], m["izpost"], m["na_enoto"]))

    print("\n  isto, urejeno po SORTINU, od najmanj negativnega")
    for n, m in sorted(vrstice, key=lambda x: -x[1]["sortino"]):
        print("     %-20s%9.2f" % (n, m["sortino"]))

    print("\n\nV RASTOCEM TRGU")
    print("  %-20s%10s%10s%10s%10s%12s"
          % ("razlicica", "zlozeno", "letno", "MaxDD", "izpost", "na enoto"))
    for n, v in V.items():
        m = razclenitev(v, ret, bik)
        out.setdefault("bik", {})[n] = m
        print("  %-20s%9.0f%%%9.1f%%%9.1f%%%9.1f%%%12.2f"
              % (n, m["zlozeno"], m["letno"], m["maxdd"], m["izpost"],
                 m["na_enoto"]))

    # korelacija med izpostavljenostjo in izgubo
    x = np.array([out["medved"][n]["izpost"] for n in V])
    y = np.array([out["medved"][n]["zlozeno"] for n in V])
    r = float(np.corrcoef(x, y)[0, 1])
    k, n0 = np.polyfit(x, y, 1)
    print("\n\nJE IZGUBA SAMO POSLEDICA VEC CASA V TRGU?")
    print("  korelacija med izpostavljenostjo in zlozeno izgubo: %.3f" % r)
    print("  naklon: %.2f odstotne tocke izgube na odstotno tocko izpostavljenosti"
          % k)
    print("  ce bi bilo zgolj racunovodstvo, bi bila 'na enoto' pri vseh enaka.")
    ne = [out["medved"][n]["na_enoto"] for n in V]
    print("  na enoto: od %.2f do %.2f, razpon %.2f" % (min(ne), max(ne),
                                                        max(ne) - min(ne)))
    out["povezava"] = {"korelacija": round(r, 3), "naklon": round(float(k), 2)}

    (ROOT / "testing" / "data" / "preveri_mehanizem.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/preveri_mehanizem.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
