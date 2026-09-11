"""Samo BINARNI kandidati na knjigi sestih, skozi protokol faz.

    python testing/scripts/knjiga_binarno.py

OMEJITEV
Uporabnik zeli binarne signale. Pozicija je torej 1 ali 5-odstotno dno, nikoli
vmes. To izkljuci ciljanje volatilnosti, stopnjevanje in povprecenje pozicij,
torej vse, kar je v prejsnjem krogu pokazalo ucinek.

Vprasanje tega skripta: kaj profesionalnega ostane ZNOTRAJ te omejitve.

NABOR, izpeljan iz literature
  1  vecinsko glasovanje     namesto povprecenja pozicij se steje, koliko
                             specifikacij pravi "drzi", in se drzi ce jih je
                             vsaj toliko. Izhod ostane binaren. Declerck in Vy
                             (SSRN 5032806) porocata, da je v variabilnosti
                             binarnih signalov informacija
  2  tedenski signal         strategija se racuna na tedenskih svecah, pozicija
                             se prenese na dneve. Literatura: visji casovni
                             okvir zmanjsa zaporedne lazne signale, tipicno
                             4 do 8 signalov letno namesto desetin
  3  knjizno stikalo         ce je BTC zunaj, gre cela knjiga v gotovino.
                             Binarno na ravni portfelja
  4  denar ob izstopu        sredstvo brez signala ne caka v gotovini, ampak
                             se prelije v BTC, ce ima BTC signal
  5  enake utezi             brez prevlade BTC, 6 x 16,7 %
  6  samo tri sredstva       BTC, ETH, SOL, enake utezi

Vse pozicije so strogo binarne. Dno 5 % ostane, kot je danes.

MERILO je protokol faz:
  C1 zmaga v vsaj 3 od 4 rastocih faz     C3 zmaga v vsaj 70 % od 84 podmnozic
  C2 zmaga v vsaj 3 od 5 padajocih faz    C4 interval Sortina izkljucuje niclo

Izhod: testing/data/knjiga_binarno.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from itertools import combinations
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, _cfg, cene, pozicija
from ansambel import DC_MREZA, OSNOVA, TL_MREZA
from faze_ciklov import datiraj
from knjiga_profesionalno import boot, knjiga, mdd, sharpe, sortino, zlozen
from diversitas.strategy import position, run_strategy
from shared.warmup import trim_warmup

K_TEST = 3
DNO = 0.05


def _poz(raw, **kw) -> pd.Series:
    cfg = replace(_cfg(), **kw)
    return position(trim_warmup(run_strategy(raw, config=cfg).df), cfg).astype(float)


def glasovanje(raw, mreza, polje: str, prag: int) -> pd.Series:
    """Vecinsko glasovanje. Izhod je BINAREN: 1 ali dno."""
    g = [(_poz(raw, **{polje: v}) > 0.5).astype(int) for v in mreza]
    sk = pd.concat(g, axis=1).sum(axis=1)
    return pd.Series(np.where(sk >= prag, 1.0, DNO), index=sk.index)


def redkeje(p: pd.Series, pravilo: str) -> pd.Series:
    """Isti dnevni signal, a pozicija se sme spremeniti le ob dolocenih dnevih.

    Tedenske svece niso uporabne, ker MA200 na tedenskih zahteva stiri leta in
    HYPE jih nima. Ta oblika zastavi isto vprasanje ciste: signal ostane
    nespremenjen, spremeni se le, kako pogosto se sme po njem ukrepati.
    Literatura pravi, da nizja frekvenca odlocanja zmanjsa zaporedne lazne
    signale. Tu se to preveri brez spreminjanja enega samega parametra.
    """
    mej = p.index.to_period(pravilo)
    prvi = ~mej.duplicated()
    v = p.to_numpy(float).copy()
    drzi = v[0]
    for i in range(len(v)):
        if prvi[i]:
            drzi = v[i]
        v[i] = drzi
    return pd.Series(v, index=p.index)


def main() -> int:
    C = cene()
    P0 = {s: pozicija(C[s], None) for s in SREDSTVA}
    idx = P0["BTC"].index
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}

    print("KNJIGA SESTIH, %s do %s, %d dni, 0,30 %% na stran"
          % (idx[0].date(), idx[-1].date(), len(idx)))
    print("vse pozicije so strogo binarne, dno 5 %\n")
    print("sestavljam kandidate ...")

    V = {"0 danes": (P0, dict(UTEZI))}

    for prag in (2, 3, 4):
        V["1 glasovanje TL, >=%d od 5" % prag] = (
            {s: glasovanje(C[s], TL_MREZA, "track_period", prag)
             for s in SREDSTVA}, dict(UTEZI))
    V["1 glasovanje DC, >=3 od 5"] = (
        {s: glasovanje(C[s], DC_MREZA, "donchian_period", 3) for s in SREDSTVA},
        dict(UTEZI))

    V["2 ukrepaj tedensko"] = ({s: redkeje(P0[s], "W") for s in SREDSTVA}, dict(UTEZI))
    V["2 ukrepaj mesecno"] = ({s: redkeje(P0[s], "M") for s in SREDSTVA}, dict(UTEZI))

    # 3 knjizno stikalo: ce je BTC zunaj, gre vse v gotovino
    btc_v = (P0["BTC"] > 0.5).reindex(idx).fillna(False)
    V["3 knjizno stikalo (BTC)"] = (
        {s: pd.Series(np.where(btc_v.reindex(P0[s].index).fillna(False),
                               P0[s], DNO), index=P0[s].index)
         for s in SREDSTVA}, dict(UTEZI))

    # 5 in 6: druge utezi, isti signal
    V["5 enake utezi"] = (P0, {s: 1 / 6 for s in SREDSTVA})
    V["6 samo tri, enake utezi"] = (
        {s: P0[s] for s in SREDSTVA},
        {"BTC": 1 / 3, "ETH": 1 / 3, "SOL": 1 / 3, "LINK": 0.0,
         "BNB": 0.0, "HYPE": 0.0})

    # 4 denar ob izstopu gre v BTC: obravnavano posebej spodaj
    R, IZP = {}, {}
    for n, (POS, W) in V.items():
        stara = dict(UTEZI)
        UTEZI.clear()
        UTEZI.update({k: v for k, v in W.items() if v > 0})
        R[n] = knjiga(idx, POS, RET)
        IZP[n] = float(np.mean([POS[s].reindex(idx).fillna(0).mean()
                                for s in UTEZI]))
        UTEZI.clear()
        UTEZI.update(stara)

    # 4 denar ob izstopu v BTC, rocno: altcoin brez signala doda svojo utez BTC
    E = {k: 100.0 * w for k, w in UTEZI.items()}
    PV = {k: (P0[k].reindex(idx).fillna(DNO) > 0.5).to_numpy() for k in UTEZI}
    RV = {k: RET[k].reindex(idx).fillna(0.0).to_numpy(float) for k in UTEZI}
    prej = {k: 0.0 for k in UTEZI}
    pot, izp4, zm = [], [], None
    for j, d in enumerate(idx):
        for k in UTEZI:
            # alt brez signala se prelije v BTC, ce ima BTC signal
            if k != "BTC" and not PV[k][j] and PV["BTC"][j]:
                p = 1.0
                r = RV["BTC"][j]
            else:
                p = 1.0 if PV[k][j] else DNO
                r = RV[k][j]
            tv = abs(p - prej[k])
            E[k] *= 1 + p * r - tv * FEE
            prej[k] = p
        izp4.append(float(np.mean([prej[k] for k in UTEZI])))
        sk = sum(E.values())
        if zm is not None and d.month != zm:
            c = {k: sk * w for k, w in UTEZI.items()}
            E = {k: v - abs(v - E[k]) * FEE for k, v in c.items()}
        zm = d.month
        pot.append(sum(E.values()))
    pot = np.array(pot)
    R["4 denar ob izstopu v BTC"] = np.diff(pot, prepend=100.0) / \
        np.concatenate([[100.0], pot[:-1]])
    IZP["4 denar ob izstopu v BTC"] = float(np.mean(izp4))

    print("\n1) CELA ZGODOVINA")
    print("  %-30s%8s%9s%8s%8s%9s%9s"
          % ("kandidat", "Sharpe", "Sortino", "CAGR", "MaxDD", "izpost", "konec"))
    out = {}
    for n, r in R.items():
        eq = np.cumprod(1 + r)
        m = {"sharpe": round(sharpe(r), 2), "sortino": round(sortino(r), 2),
             "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
             "maxdd": round(mdd(r), 1), "izpost": round(IZP[n] * 100, 1),
             "konec": round(float(eq[-1]), 1)}
        out.setdefault("cela", {})[n] = m
        print("  %-30s%8.2f%9.2f%7.0f%%%7.0f%%%8.0f%%%8.0fx"
              % (n, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                 m["izpost"], m["konec"]))

    faze = [(o, d, v) for o, d, v in datiraj(C["BTC"]["close"])
            if d >= idx[0] and o <= idx[-1]]
    maske = [((idx >= o) & (idx <= d)) for o, d, v in faze]
    vrste = [v for _, _, v in faze]
    osn = R["0 danes"]
    kombi = list(combinations(range(len(faze)), K_TEST))

    print("\n2) PROTOKOL FAZ")
    print("  %-30s%9s%10s%9s%24s%22s"
          % ("kandidat", "rast", "padec", "kombi", "d Sortino [95 % IZ]",
             "d MaxDD [95 % IZ]"))
    for n, r in R.items():
        if n == "0 danes":
            continue
        zr = sum(1 for m, v in zip(maske, vrste)
                 if v == "rast" and sortino(r[m]) > sortino(osn[m]))
        zp = sum(1 for m, v in zip(maske, vrste)
                 if v == "padec" and zlozen(r[m]) > zlozen(osn[m]))
        dd = []
        for k in kombi:
            m = np.zeros(len(idx), bool)
            for i in k:
                m |= maske[i]
            dd.append(sortino(r[m]) - sortino(osn[m]))
        c3 = float((np.array(dd) > 0).mean())
        m1, l1, h1 = boot(osn, r, sortino)
        m2, l2, h2 = boot(osn, r, mdd)
        out.setdefault("protokol", {})[n] = {
            "rast": zr, "padec": zp, "kombi": round(c3 * 100, 0),
            "dsortino": round(m1, 2), "iz_s": [round(l1, 2), round(h1, 2)],
            "dmaxdd": round(m2, 1), "iz_m": [round(l2, 1), round(h2, 1)],
            "C1": zr >= 3, "C2": zp >= 3, "C3": c3 >= 0.70, "C4": l1 > 0}
        print("  %-30s%6d od %d%7d od %d%7.0f %%%9.2f [%+.2f,%+.2f]%9.1f [%+.1f,%+.1f]"
              % (n, zr, vrste.count("rast"), zp, vrste.count("padec"),
                 c3 * 100, m1, l1, h1, m2, l2, h2))

    print("\n3) SODBA")
    print("  %-30s%6s%6s%6s%6s%11s" % ("kandidat", "C1", "C2", "C3", "C4", "izid"))
    n_ok = 0
    for n in R:
        if n == "0 danes":
            continue
        z = out["protokol"][n]
        vsi = z["C1"] and z["C2"] and z["C3"] and z["C4"]
        n_ok += int(vsi)
        print("  %-30s%6s%6s%6s%6s%11s"
              % (n, *["DA" if z[c] else "ne" for c in ("C1", "C2", "C3", "C4")],
                 "SPREJET" if vsi else "zavrnjen"))
    print("\n  sprejetih: %d od %d" % (n_ok, len(R) - 1))

    (ROOT / "testing" / "data" / "knjiga_binarno.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/knjiga_binarno.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
