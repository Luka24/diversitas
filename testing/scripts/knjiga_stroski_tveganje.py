"""Dva vzvoda na ravni knjige, ki v tem projektu se nista bila merjena.

    python testing/scripts/knjiga_stroski_tveganje.py

Vsi dosedanji poskusi so spreminjali SIGNAL in strosek jemali kot fiksen davek.
Tu se signal ne dotakne. Spremeni se samo, kako se knjiga vzdrzuje.

VZVOD 1  pas brez trgovanja
    Danes se knjiga vsak mesec vrne na 50/10/10/10/10/10, ne glede na to, kako
    malo je zanesla. Namesto tega se rokav uravnava samo, ce je zanesel za vec
    kot T od svoje ciljne utezi:

        |delez_k / cilj_k - 1|  >  T          T = 0 %, 10 %, 20 %, 30 %, nikoli

    T = 0 % je danasnje vedenje. Podlaga: Davis in Norman (1990), NBIM (2018),
    Zarattini uporablja 20 %.

VZVOD 2  utezi po tveganju namesto po kapitalu
    50 % kapitala v BTC ni 50 % tveganja. BTC niha okoli 50 % letno, SOL in HYPE
    okoli 90 do 100 %. Pri enakem kapitalu torej altcoini nosijo bistveno vec
    tveganja, kot je bil namen. Razlicica utezi popravi tako, da je ciljno
    razmerje TVEGANJA 50/10/10/10/10/10:

        utez_k  ~  cilj_k / sigma_k(60 dni),   normalizirano na 1

    Sigma se racuna na 60 dneh do vceraj, torej brez pogleda naprej.

Delitev in stroski so isti kot povsod: ucenje do 2023-06, validacija do
2025-03, hold-out po tem, 0,30 % na stran.

Izhod: testing/data/knjiga_stroski_tveganje.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import DELITEV, FEE, PPY, SREDSTVA, UTEZI, cene, pozicija

PRAGOVI = {"0 % (danes)": 0.0, "10 %": 0.10, "20 %": 0.20, "30 %": 0.30,
           "nikoli": float("inf")}


def sigme(C: dict, idx) -> pd.DataFrame:
    """60-dnevna realizirana volatilnost do vceraj, brez pogleda naprej."""
    out = {}
    for s in SREDSTVA:
        r = C[s]["close"].pct_change()
        out[s] = (r.rolling(60).std() * np.sqrt(PPY)).shift(1).reindex(idx)
    return pd.DataFrame(out).ffill()


def knjiga(idx, POS, RET, prag: float, po_tveganju: bool, SIG=None):
    """Vrne dnevne donose, razclenitev provizij in povprecne utezi."""
    E = {k: 100.0 * w for k, w in UTEZI.items()}
    prov = {"signali": 0.0, "uravnavanje": 0.0}
    pot, izp, utezi_log = [], [], []
    zadnji_mesec = None

    for d in idx:
        delez_v_trgu = 0.0
        for k in UTEZI:
            p = POS[k]
            if d not in p.index:
                continue
            i = p.index.get_loc(d)
            pv = float(p.iloc[i])
            tv = abs(pv - float(p.iloc[i - 1])) if i else 0.0
            prov["signali"] += E[k] * tv * FEE
            E[k] *= 1 + pv * float(RET[k].loc[d]) - tv * FEE
            delez_v_trgu += pv * E[k]

        skup = sum(E.values())
        izp.append(delez_v_trgu / skup if skup > 0 else 0.0)

        if zadnji_mesec is not None and d.month != zadnji_mesec:
            if po_tveganju:
                s = SIG.loc[d]
                surove = {k: UTEZI[k] / s[k] if np.isfinite(s.get(k, np.nan))
                          and s[k] > 0 else UTEZI[k] for k in UTEZI}
                vs = sum(surove.values())
                cilj_w = {k: v / vs for k, v in surove.items()}
            else:
                cilj_w = dict(UTEZI)
            utezi_log.append(cilj_w)

            for k in UTEZI:
                cilj = skup * cilj_w[k]
                odmik = abs(E[k] / cilj - 1.0) if cilj > 0 else 0.0
                if odmik > prag:
                    prov["uravnavanje"] += abs(cilj - E[k]) * FEE
                    E[k] = cilj - abs(cilj - E[k]) * FEE
        zadnji_mesec = d.month
        pot.append(sum(E.values()))

    pot = np.array(pot)
    r = np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])
    return r, prov, float(np.mean(izp)), utezi_log


def met(r: np.ndarray) -> dict:
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(PPY)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {"sharpe": round(float(r.mean() * PPY / vol), 2),
            "sortino": round(float(r.mean() * PPY / dn), 2),
            "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
            "maxdd": round(float(dd.min() * 100), 1)}


def main() -> int:
    C = cene()
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}
    POS = {s: pozicija(C[s], None) for s in SREDSTVA}      # danasnji binarni signal
    SIG = sigme(C, POS["BTC"].index)
    out = {}

    print("VOLATILNOST, povprecje celotnega vzorca, letno")
    for s in SREDSTVA:
        print("   %-5s %5.0f %%" % (s, float(SIG[s].mean() * 100)))

    for okno, a, b in DELITEV:
        idx = POS["BTC"].index
        if a:
            idx = idx[idx >= pd.Timestamp(a, tz="UTC")]
        if b:
            idx = idx[idx <= pd.Timestamp(b, tz="UTC")]
        print("\n\n%s  %s do %s, %d dni" % (okno.upper(), a or "zacetek",
                                            b or "danes", len(idx)))

        print("\n  VZVOD 1  pas brez trgovanja, utezi po kapitalu")
        print("  %-14s%8s%9s%8s%9s%12s%12s"
              % ("prag", "Sharpe", "Sortino", "CAGR", "MaxDD",
                 "prov signal", "prov uravn"))
        for ime, T in PRAGOVI.items():
            r, prov, izp, _ = knjiga(idx, POS, RET, T, False)
            m = met(r)
            m["prov_signali"] = round(prov["signali"], 2)
            m["prov_uravnavanje"] = round(prov["uravnavanje"], 2)
            m["izpost"] = round(izp * 100, 1)
            out.setdefault(okno, {}).setdefault("pas", {})[ime] = m
            print("  %-14s%8.2f%9.2f%7.0f%%%8.0f%%%12.2f%12.2f"
                  % (ime, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                     prov["signali"], prov["uravnavanje"]))

        print("\n  VZVOD 2  utezi po tveganju, prag 0 % in 20 %")
        print("  %-14s%8s%9s%8s%9s%12s%12s"
              % ("prag", "Sharpe", "Sortino", "CAGR", "MaxDD",
                 "prov signal", "prov uravn"))
        for ime, T in (("0 %", 0.0), ("20 %", 0.20)):
            r, prov, izp, wl = knjiga(idx, POS, RET, T, True, SIG)
            m = met(r)
            m["izpost"] = round(izp * 100, 1)
            out.setdefault(okno, {}).setdefault("tveganje", {})[ime] = m
            print("  %-14s%8.2f%9.2f%7.0f%%%8.0f%%%12.2f%12.2f"
                  % (ime, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                     prov["signali"], prov["uravnavanje"]))
            if wl and T == 0.0:
                z = pd.DataFrame(wl).mean()
                out.setdefault(okno, {})["utezi_po_tveganju"] = {
                    k: round(float(v * 100), 1) for k, v in z.items()}
                print("     povprecne utezi: " + "  ".join(
                    "%s %.0f %%" % (k, v * 100) for k, v in z.items()))

    (ROOT / "testing" / "data" / "knjiga_stroski_tveganje.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print("\nzapisano v testing/data/knjiga_stroski_tveganje.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
