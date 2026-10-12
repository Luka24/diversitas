"""Koliko knjige sestih je v resnici mrtva gotovina.

    python testing/scripts/fantomska_gotovina.py

Knjiga v graded_alti.py in knjiga_profesionalno.py sredstvu, ki se nima
podatkov, dodeli pozicijo 0, mesecno uravnavanje pa kapital VSEENO natoci v ta
rukav. SOL ima pozicijo sele od 2022, HYPE od 2025, zato je velik del knjige
leta in leta v gotovini z nicelnim donosom, ki je nihce ne bi drzal.

Dve konvenciji:

  A  kot danes       manjkajoce sredstvo ima pozicijo 0, rukav se dopolnjuje
  B  normalizirano   utez manjkajocega se sorazmerno razdeli med razpolozljiva

B ne gleda naprej. "Ima to sredstvo danes dovolj zgodovine za signal" je znano
v realnem casu.

Isto za knjigo treh (BTC, ETH, SOL, enake utezi), ker je bila primerjava tri
proti sest merjena pri konvenciji A. Interval iz blocnega bootstrapa, bloki po
20 dni, 2000 ponovitev.

Izhod: testing/data/fantomska_gotovina.json
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

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, cene, pozicija

RNG = np.random.default_rng(20261008)
NBOOT, BLOK = 2000, 20
TRI = {"BTC": 1 / 3, "ETH": 1 / 3, "SOL": 1 / 3}


def knjiga(idx, POS, RET, utezi: dict, norm: bool):
    sred = list(utezi)
    ziv = {s: pd.Series(True, index=POS[s].index).reindex(idx)
           .fillna(False).to_numpy() for s in sred}
    PV = {s: POS[s].reindex(idx).fillna(0.0).to_numpy(float) for s in sred}
    RV = {s: RET[s].reindex(idx).fillna(0.0).to_numpy(float) for s in sred}

    def w(j):
        if not norm:
            return dict(utezi)
        z = {s: utezi[s] for s in sred if ziv[s][j]}
        t = sum(z.values()) or 1.0
        return {s: z.get(s, 0.0) / t for s in sred}

    E = {k: 100.0 * v for k, v in w(0).items()}
    pot, izp, zm = [], [], None
    for j, d in enumerate(idx):
        for k in sred:
            pv = PV[k][j]
            tv = abs(pv - PV[k][j - 1]) if j else 0.0
            E[k] *= 1 + pv * RV[k][j] - tv * FEE
        sk = sum(E.values())
        izp.append(sum(PV[k][j] * E[k] for k in sred) / sk if sk > 0 else 0.0)
        if zm is not None and d.month != zm:
            ww = w(j)
            c = {k: sk * ww[k] for k in sred}
            E = {k: v - abs(v - E[k]) * FEE for k, v in c.items()}
        zm = d.month
        pot.append(sum(E.values()))
    pot = np.array(pot)
    r = np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])
    fantom = np.array([sum(utezi[s] for s in sred if not ziv[s][j])
                       for j in range(len(idx))])
    return r, float(np.mean(izp)), fantom


def sortino(r):
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / dn)


def mere(r, izp) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    return {"sharpe": round(float(r.mean() * PPY / (r.std() * np.sqrt(PPY))), 2),
            "sortino": round(sortino(r), 2),
            "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(float(dd.min() * 100), 1),
            "izpost": round(izp * 100, 1),
            "konec": round(float(eq[-1]), 1)}


def boot(ra, rb):
    n, nb = len(ra), int(np.ceil(len(ra) / BLOK))
    d = []
    for _ in range(NBOOT):
        z = RNG.integers(0, n - BLOK, nb)
        i = np.concatenate([np.arange(s, s + BLOK) for s in z])[:n]
        d.append(sortino(rb[i]) - sortino(ra[i]))
    d = np.array(d)
    return [round(float(d.mean()), 2), round(float(np.percentile(d, 2.5)), 2),
            round(float(np.percentile(d, 97.5)), 2), round(float((d > 0).mean()), 2)]


def main() -> int:
    C = cene()
    POS = {s: pozicija(C[s], None) for s in SREDSTVA}
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}
    idx = POS["BTC"].index
    print("Knjiga %s do %s, %d dni.\n" % (idx[0].date(), idx[-1].date(), len(idx)))

    out = {"pokritost": {}, "knjige": {}, "tri_proti_sest": {}}
    for s in SREDSTVA:
        delez = 100 * POS[s].index.isin(idx).sum() / len(idx)
        out["pokritost"][s] = {"od": str(POS[s].index[0].date()),
                               "delez_dni": round(float(delez), 1)}
        print("  %-5s pozicija od %s   %5.1f %% dni knjige"
              % (s, POS[s].index[0].date(), delez))

    R = {}
    print("\n  %-28s%8s%9s%8s%9s%9s%8s"
          % ("", "Sharpe", "Sortino", "CAGR", "MaxDD", "izpost", "konec"))
    for ime, u in (("sest 50/10", UTEZI), ("tri enake", TRI)):
        for norm in (False, True):
            r, izp, fantom = knjiga(idx, POS, RET, u, norm)
            kljuc = "%s, %s" % (ime, "normalizirano" if norm else "kot danes")
            R[kljuc] = r
            m = mere(r, izp)
            if not norm:
                m["fantom_povp"] = round(float(fantom.mean() * 100), 1)
            out["knjige"][kljuc] = m
            print("  %-28s%8.2f%9.2f%7.0f%%%8.0f%%%8.0f%%%7.0fx"
                  % (kljuc, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                     m["izpost"], m["konec"]))
            if not norm:
                print("  %-28s povprecna utez brez podatkov %.1f %%"
                      % ("", fantom.mean() * 100))

    print("\n  d Sortino, tri minus sest:")
    for k in ("kot danes", "normalizirano"):
        b = boot(R["sest 50/10, " + k], R["tri enake, " + k])
        out["tri_proti_sest"][k] = b
        print("    %-14s %+.2f  [%+.2f, %+.2f]   pozitivnih %.0f %%"
              % (k, b[0], b[1], b[2], b[3] * 100))

    pot = ROOT / "testing" / "data" / "fantomska_gotovina.json"
    pot.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nZapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
