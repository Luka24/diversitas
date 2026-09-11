"""Profesionalne tehnike skozi protokol faz.

    python testing/scripts/profesionalni_protokol.py

ZAKAJ TO
Protokol faz je doslej presojal samo moje strukturne razlicice. Profesionalnih
tehnik ni presodil nobene. Najbolj univerzalna med njimi je CILJANJE
VOLATILNOSTI, in nas lean je nima:

    Zarattini      w = min(0,25 / sigma, 200 %)
    Man Group      velikost pozicije po volatilnosti
    AQR            skaliranje na stalno ciljno volatilnost
    Monash         isto

Nas lean je binaren, 0 ali 1. Dnevnik projekta pravi, da je target_vol_pct na
leanu "genuine no-op", ampak to je zato, ker je vgrajena pot pri binarnem
target_alloc izklopljena. Kot PREKRIVNI sloj cez ze izracunano pozicijo ni bila
nikoli merjena. To je razlika.

RAZLICICE
    ciljanje X %, brez vzvoda    p = p_lean * clip(X / sigma60, 0, 1)
    ciljanje X %, do 2x          p = p_lean * clip(X / sigma60, 0, 2)
    Zarattini Combo              njihova strategija v celoti, kot primerjava

sigma60 je 60-dnevna realizirana volatilnost do vceraj, letno. Brez pogleda
naprej.

Brez vzvoda pomeni, da se pozicija lahko samo ZMANJSA. To skoraj zagotovo
zmanjsa cas v trgu, zato je izpostavljenost povsod izpisana. Prav zaradi te
pasti je v protokolu pogoj C2: ce kandidat zmaga samo zato, ker ga v padcih ni
bilo, ne bo zmagal v rastocih fazah.

MERILO je isto kot v protokol_faze.py:
    C1  zmaga v vsaj 3 od 4 rastocih faz
    C2  zmaga v vsaj 3 od 5 padajocih faz
    C3  zmaga v vsaj 70 % od 84 podmnozic po tri faze
    C4  95 % interval zaupanja izkljucuje niclo NAVZGOR

Izhod: testing/data/profesionalni_protokol.json
"""
from __future__ import annotations

import json
import sys
import warnings
from itertools import combinations
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, cene, pozicija
from faze_ciklov import datiraj
from protokol_faze import BLOK, K_TEST, NBOOT, boot_zlozen, neto, zlozen

CILJI = (30.0, 50.0, 70.0)


def sigma60(raw: pd.DataFrame) -> pd.Series:
    r = raw["close"].pct_change()
    return (r.rolling(60).std() * np.sqrt(PPY)).shift(1)


def zarattini(raw: pd.DataFrame, cilj=0.25, kapa=2.0) -> pd.Series:
    """Combo: 9 Donchianovih dolzin na ZAKLJUCKIH, velikost po volatilnosti,
    sledeci stop na sredini Donchiana. Povprecje devetih signalov."""
    c = raw["close"]
    s = sigma60(raw)
    sig = []
    for n in (10, 15, 20, 30, 40, 50, 75, 100, 150):
        hi = c.rolling(n).max().shift(1)
        lo = c.rolling(n).min().shift(1)
        sredina = (hi + lo) / 2
        v = np.zeros(len(c))
        drzim = False
        stop = np.nan
        cv = c.to_numpy(float)
        hv, sv = hi.to_numpy(float), sredina.to_numpy(float)
        for i in range(len(c)):
            if not drzim:
                if np.isfinite(hv[i]) and cv[i] > hv[i]:
                    drzim, stop = True, sv[i]
            else:
                stop = np.nanmax([stop, sv[i]])
                if cv[i] < stop:
                    drzim, stop = False, np.nan
            v[i] = 1.0 if drzim else 0.0
        sig.append(pd.Series(v, index=c.index))
    povp = pd.concat(sig, axis=1).mean(axis=1)
    w = (cilj / s).clip(0, kapa)
    return (povp * w).shift(1).fillna(0.0)


def main() -> int:
    C = cene()
    raw = C["BTC"]
    cena = raw["close"]
    s60 = sigma60(raw)

    osnova = pozicija(raw, None)
    V = {"osnova (danes)": osnova}
    for cilj in CILJI:
        for kapa, ime in ((1.0, "brez vzvoda"), (2.0, "do 2x")):
            sk = (cilj / 100.0 / s60).clip(0, kapa)
            V["ciljanje %d %%, %s" % (cilj, ime)] = (osnova * sk).reindex(
                osnova.index).fillna(0.0)
    V["Zarattini Combo"] = zarattini(raw)

    idx = osnova.index
    for v in V.values():
        idx = idx.intersection(v.dropna().index)
    V = {k: v.reindex(idx) for k, v in V.items()}
    ret = cena.pct_change().reindex(idx).fillna(0.0)
    R = {n: neto(p, ret).to_numpy(float) for n, p in V.items()}

    faze = [(o, d, v) for o, d, v in datiraj(cena)
            if d >= idx[0] and o <= idx[-1]]
    maske = [((idx >= o) & (idx <= d)) for o, d, v in faze]
    vrste = [v for _, _, v in faze]
    osn = R["osnova (danes)"]

    print("BTC, %s do %s, %d dni. %d faz: %d rastocih, %d padajocih."
          % (idx[0].date(), idx[-1].date(), len(idx), len(faze),
             vrste.count("rast"), vrste.count("padec")))
    print("Provizija 0,30 %% na stran. sigma je 60-dnevna, do vceraj.\n")

    # ---- osnovne metrike ----
    print("1) CELA ZGODOVINA")
    print("  %-26s%8s%9s%8s%8s%9s%9s"
          % ("razlicica", "Sharpe", "Sortino", "CAGR", "MaxDD", "izpost", "provizij"))
    out = {}
    for n, p in V.items():
        r = R[n]
        eq = np.cumprod(1 + r)
        dd = eq / np.maximum.accumulate(eq) - 1
        vol = r.std() * np.sqrt(PPY)
        dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
        t = p.diff().abs().fillna(0.0).sum()
        m = {"sharpe": round(float(r.mean() * PPY / vol), 2),
             "sortino": round(float(r.mean() * PPY / dn), 2),
             "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
             "maxdd": round(float(dd.min() * 100), 1),
             "izpost": round(float(p.mean() * 100), 1),
             "provizije": round(float(t * FEE * 100), 1),
             "konec": round(float(eq[-1]), 1)}
        out.setdefault("cela", {})[n] = m
        print("  %-26s%8.2f%9.2f%7.0f%%%7.0f%%%8.0f%%%8.1f%%"
              % (n, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                 m["izpost"], m["provizije"]))

    # ---- C razslojeno ----
    print("\n2) RAZSLOJENO STETJE ZMAG (C1, C2)")
    print("  %-26s%12s%13s" % ("razlicica", "rastoce", "padajoce"))
    for n in V:
        if n == "osnova (danes)":
            continue
        zr = sum(1 for m, v in zip(maske, vrste)
                 if v == "rast" and zlozen(R[n][m]) > zlozen(osn[m]))
        zp = sum(1 for m, v in zip(maske, vrste)
                 if v == "padec" and zlozen(R[n][m]) > zlozen(osn[m]))
        out.setdefault("razslojeno", {})[n] = {"rast": zr, "padec": zp}
        print("  %-26s%7d od %d%8d od %d"
              % (n, zr, vrste.count("rast"), zp, vrste.count("padec")))

    # ---- B kombinatoricno ----
    kombi = list(combinations(range(len(faze)), K_TEST))
    print("\n3) KOMBINATORICNO, %d podmnozic po %d faz (C3)" % (len(kombi), K_TEST))
    print("  %-26s%12s%14s" % ("razlicica", "zmaga v", "mediana d"))
    for n in V:
        if n == "osnova (danes)":
            continue
        d = []
        for kmb in kombi:
            m = np.zeros(len(idx), bool)
            for i in kmb:
                m |= maske[i]
            d.append(zlozen(R[n][m]) - zlozen(osn[m]))
        d = np.array(d)
        out.setdefault("kombi", {})[n] = round(float((d > 0).mean() * 100), 0)
        print("  %-26s%10.0f %%%14.1f" % (n, (d > 0).mean() * 100, np.median(d)))

    # ---- D bootstrap ----
    print("\n4) INTERVAL ZAUPANJA NA CELI ZGODOVINI (C4)")
    print("  %-26s%14s%26s" % ("razlicica", "d zlozen", "95 % interval"))
    for n in V:
        if n == "osnova (danes)":
            continue
        m_, lo, hi, p = boot_zlozen(osn, R[n])
        out.setdefault("boot", {})[n] = {"d": round(m_, 1),
                                         "iz": [round(lo, 1), round(hi, 1)]}
        print("  %-26s%14.0f%13.0f do %-12.0f%s"
              % (n, m_, lo, hi, "  POZITIVNO ZNACILNO" if lo > 0 else
                 ("  NEGATIVNO ZNACILNO" if hi < 0 else "")))

    # ---- sodba ----
    print("\n5) SKUPNA SODBA")
    print("  %-26s%6s%6s%6s%6s%11s" % ("razlicica", "C1", "C2", "C3", "C4", "izid"))
    n_ok = 0
    for n in V:
        if n == "osnova (danes)":
            continue
        z = out["razslojeno"][n]
        c1, c2 = z["rast"] >= 3, z["padec"] >= 3
        c3 = out["kombi"][n] >= 70
        c4 = out["boot"][n]["iz"][0] > 0
        vsi = c1 and c2 and c3 and c4
        n_ok += int(vsi)
        out.setdefault("sodba", {})[n] = {"C1": c1, "C2": c2, "C3": c3,
                                          "C4": c4, "sprejet": vsi}
        print("  %-26s%6s%6s%6s%6s%11s"
              % (n, "DA" if c1 else "ne", "DA" if c2 else "ne",
                 "DA" if c3 else "ne", "DA" if c4 else "ne",
                 "SPREJET" if vsi else "zavrnjen"))
    print("\n  sprejetih: %d od %d" % (n_ok, len(out["sodba"])))

    (ROOT / "testing" / "data" / "profesionalni_protokol.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/profesionalni_protokol.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
