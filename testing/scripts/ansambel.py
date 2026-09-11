"""Parametrski ansambel na lean: nehaj izbirati periodo, povpreci cez vec.

    python testing/scripts/ansambel.py

IZHODISCE
Ta projekt je ze sam ugotovil, da se optimalne periode ne da izbrati: gnezdeni
walk-forward je dal razliko tocno 0,00, train-optimalna perioda se z
test-optimalno ujame v 1 od 5 oken, in Optuna je na OOS propadla.

Literatura pride do iste negativne ugotovitve in naredi korak naprej, ki ga mi
nismo. ReSolve (From Fragility to Robustness) zmesa 57 specifikacij z enakimi
utezmi in s tem premaga VSAKO metodo izbiranja: Sharpe 0,90 proti 0,87, najhujsi
padec -14,9 % proti -16,4 %. Newfound pride do istega. AQR (Hurst, Ooi,
Pedersen) uporablja 1, 3 in 12 mesecev hkrati. Zarattini povpreci 9 Donchianov.

Ce parametra ni mogoce izbrati, je pravi odgovor ne izbrati ga.

KAJ SE MERI
Namesto ene trackline periode 75 se pozene CELA strategija pri vec periodah in
drzi se POVPRECJE pozicij. Enake utezi, brez optimizacije.

Mreze so preregistrirane, geometricno okoli obstojecih privzetkov, da centra ne
izbiram jaz:

    track_period     40, 55, 75, 100, 135      privzetek 75 je v sredini
    donchian_period  10, 14, 20,  28,  40      privzetek 20 je v sredini

Razlicice:
    osnova     danes, ena sama specifikacija (75, 20)
    ans-TL     povprecje 5 pozicij cez track_period
    ans-DC     povprecje 5 pozicij cez donchian_period
    ans-oba    povprecje 25 pozicij cez obe mrezi

Strosek se zaracuna na spremembi NETO pozicije, ker se notranji nasprotni posli
med clani iztecejo in se jih ne trguje.

Provizija in zdrs 0,30 % na stran. Delitev: trening do 2023-06-30, validacija do
2025-03-31, hold-out po tem.

Izhod: testing/data/ansambel.json
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

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, _cfg, cene
from diversitas.strategy import position, run_strategy
from shared.warmup import trim_warmup

TL_MREZA = (40, 55, 75, 100, 135)
DC_MREZA = (10, 14, 20, 28, 40)
OSNOVA = (75, 20)

OKNA = (("trening", None, "2023-06-30"),
        ("validacija", "2023-07-01", "2025-03-31"),
        ("hold-out", "2025-04-01", None))


def ena_pozicija(raw: pd.DataFrame, tl: int, dc: int) -> pd.Series:
    """Prava produkcijska pot, ne rocno prepisan avtomat."""
    cfg = replace(_cfg(), track_period=tl, donchian_period=dc)
    df = trim_warmup(run_strategy(raw, config=cfg).df)
    return position(df, cfg).astype(float)


def sestavi(raw: pd.DataFrame) -> dict[str, pd.Series]:
    """Vrne vse razlicice, poravnane na skupen indeks."""
    kombinacije = {OSNOVA} | {(t, OSNOVA[1]) for t in TL_MREZA} \
        | {(OSNOVA[0], d) for d in DC_MREZA} | set(product(TL_MREZA, DC_MREZA))
    P = {k: ena_pozicija(raw, *k) for k in sorted(kombinacije)}
    zac = max(s.index[0] for s in P.values())
    idx = P[OSNOVA].loc[zac:].index
    P = {k: v.reindex(idx) for k, v in P.items()}

    def povp(kljuci):
        return pd.concat([P[k] for k in kljuci], axis=1).mean(axis=1)

    return {
        "osnova (75,20)": P[OSNOVA],
        "ans-TL (5)": povp([(t, OSNOVA[1]) for t in TL_MREZA]),
        "ans-DC (5)": povp([(OSNOVA[0], d) for d in DC_MREZA]),
        "ans-oba (25)": povp(list(product(TL_MREZA, DC_MREZA))),
    }, P, idx


def metrike(p: pd.Series, ret: pd.Series, fee=FEE) -> dict:
    t = p.diff().abs().fillna(0.0)
    r = (p * ret - t * fee).fillna(0.0).to_numpy(float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(PPY)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    cagr = float((eq[-1] ** (PPY / len(r)) - 1) * 100)
    mdd = float(dd.min() * 100)
    return {"sharpe": round(float(r.mean() * PPY / vol), 2) if vol > 0 else np.nan,
            "sortino": round(float(r.mean() * PPY / dn), 2) if dn > 0 else np.nan,
            "cagr": round(cagr, 1), "maxdd": round(mdd, 1),
            "calmar": round(cagr / abs(mdd), 2) if mdd < 0 else np.nan,
            "izpost": round(float(p.mean() * 100), 1),
            "obrat": round(float(t.sum()), 1),
            "provizije": round(float(t.sum() * fee * 100), 1),
            "konec": round(float(eq[-1]), 1), "dni": len(r)}


def izpis(naslov, vrstice):
    print("\n%s" % naslov)
    print("  %-16s%8s%9s%8s%8s%8s%9s%8s%10s"
          % ("razlicica", "Sharpe", "Sortino", "CAGR", "MaxDD", "Calmar",
             "izpost", "obrat", "provizije"))
    for ime, m in vrstice:
        print("  %-16s%8.2f%9.2f%7.0f%%%7.0f%%%8.2f%8.0f%%%8.1f%9.1f%%"
              % (ime, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"],
                 m["calmar"], m["izpost"], m["obrat"], m["provizije"]))


def rezi(s, a, b):
    if a is not None:
        s = s.loc[s.index >= pd.Timestamp(a, tz="UTC")]
    if b is not None:
        s = s.loc[s.index <= pd.Timestamp(b, tz="UTC")]
    return s


def main() -> int:
    C = cene()
    out = {}
    print("mreze: track_period %s, donchian_period %s" % (TL_MREZA, DC_MREZA))

    # ================= BTC podrobno =================
    raw = C["BTC"]
    V, P, idx = sestavi(raw)
    ret = raw["close"].pct_change().reindex(idx).fillna(0.0)
    print("\nBTC, %s do %s, %d dni, 0,30 %% na stran"
          % (idx[0].date(), idx[-1].date(), len(idx)))

    izpis("1) BTC, CELA ZGODOVINA",
          [(n, metrike(v, ret)) for n, v in V.items()])
    out["btc_cela"] = {n: metrike(v, ret) for n, v in V.items()}

    # posamezni clani, da se vidi razpon
    print("\n  posamezni clani ans-TL, da se vidi razpon specifikacij")
    print("  %-16s%9s%8s%8s%9s" % ("track_period", "Sortino", "CAGR", "MaxDD",
                                   "izpost"))
    clani = []
    for t in TL_MREZA:
        m = metrike(P[(t, OSNOVA[1])], ret)
        clani.append(m["sortino"])
        print("  %-16d%9.2f%7.0f%%%7.0f%%%8.0f%%"
              % (t, m["sortino"], m["cagr"], m["maxdd"], m["izpost"]))
    ans = out["btc_cela"]["ans-TL (5)"]["sortino"]
    print("  %-16s%9.2f    <- povprecje clanov" % ("", float(np.mean(clani))))
    print("  %-16s%9.2f    <- ANSAMBEL" % ("", ans))
    print("  ansambel presega povprecje clana za %.2f, najboljsega clana za %.2f"
          % (ans - float(np.mean(clani)), ans - max(clani)))
    out["clani_TL"] = {str(t): metrike(P[(t, OSNOVA[1])], ret)
                       for t in TL_MREZA}

    # po letih
    print("\n\n2) BTC PO LETIH, Sortino")
    leta = sorted({d.year for d in idx})
    print("  %-16s" % "razlicica" + "".join("%8d" % l for l in leta))
    tab = {}
    for n, v in V.items():
        vrsta = [metrike(v.reindex(idx[idx.year == l]),
                         ret.reindex(idx[idx.year == l]))["sortino"]
                 if (idx.year == l).sum() > 60 else np.nan for l in leta]
        tab[n] = vrsta
        print("  %-16s" % n + "".join(
            "%8s" % ("%.2f" % x if np.isfinite(x) else "-") for x in vrsta))
    out["btc_po_letih"] = {"leta": leta, "sortino": tab}
    for n in ("ans-TL (5)", "ans-oba (25)"):
        z = sum(1 for i in range(len(leta))
                if np.isfinite(tab[n][i]) and tab[n][i] > tab["osnova (75,20)"][i])
        v = sum(1 for i in range(len(leta)) if np.isfinite(tab[n][i]))
        print("  %s premaga osnovo v %d od %d let" % (n, z, v))

    # po rezimu
    ma200 = raw["close"].rolling(200).mean().reindex(idx)
    bik = (raw["close"].reindex(idx) > ma200).fillna(False)
    print("\n\n3) BTC PO REZIMU, Sortino")
    print("  %-16s%12s%12s" % ("razlicica", "bikovski", "medvedji"))
    rz = {}
    for n, v in V.items():
        a = metrike(v[bik], ret[bik])["sortino"]
        b = metrike(v[~bik], ret[~bik])["sortino"]
        rz[n] = {"bik": a, "medved": b}
        print("  %-16s%12.2f%12.2f" % (n, a, b))
    out["btc_po_rezimu"] = rz

    # tri okna
    print("\n\n4) BTC, TRI OKNA")
    for okno, a, b in OKNA:
        vr = [(n, metrike(rezi(v, a, b), rezi(ret, a, b))) for n, v in V.items()]
        out.setdefault("btc_okna", {})[okno] = {n: m for n, m in vr}
        izpis("  %s, %s do %s" % (okno.upper(), a or "zacetek", b or "danes"), vr)

    # provizije
    print("\n\n5) BTC, OBCUTLJIVOST NA PROVIZIJO, Sortino cela zgodovina")
    st = (0.0, 0.001, 0.002, 0.003, 0.005, 0.0075, 0.010)
    print("  %-16s" % "razlicica" + "".join("%9s" % ("%.2f %%" % (f * 100))
                                            for f in st))
    for n, v in V.items():
        vrsta = [metrike(v, ret, f)["sortino"] for f in st]
        out.setdefault("btc_provizije", {})[n] = vrsta
        print("  %-16s" % n + "".join("%9.2f" % x for x in vrsta))

    # ================= knjiga sestih =================
    print("\n\n6) KNJIGA 50/10/10/10/10/10, mesecno uravnavanje")
    VS = {}
    for s in SREDSTVA:
        VS[s] = sestavi(C[s])[0]
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}

    for okno, a, b in OKNA:
        idxb = rezi(VS["BTC"]["osnova (75,20)"], a, b).index
        vr = []
        for n in V:
            E = {k: 100.0 * w for k, w in UTEZI.items()}
            pot, izp, zm = [], [], None
            for d in idxb:
                dv = 0.0
                for k in UTEZI:
                    p = VS[k][n]
                    if d not in p.index:
                        continue
                    i = p.index.get_loc(d)
                    pv = float(p.iloc[i])
                    tv = abs(pv - float(p.iloc[i - 1])) if i else 0.0
                    E[k] *= 1 + pv * float(RET[k].loc[d]) - tv * FEE
                    dv += pv * E[k]
                sk = sum(E.values())
                izp.append(dv / sk if sk > 0 else 0.0)
                if zm is not None and d.month != zm:
                    c = {k: sk * w for k, w in UTEZI.items()}
                    E = {k: v2 - abs(v2 - E[k]) * FEE for k, v2 in c.items()}
                zm = d.month
                pot.append(sum(E.values()))
            pot = np.array(pot)
            r = np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])
            eq = np.cumprod(1 + r)
            dd = eq / np.maximum.accumulate(eq) - 1
            vol = r.std() * np.sqrt(PPY)
            dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
            cg = float((eq[-1] ** (PPY / len(r)) - 1) * 100)
            md = float(dd.min() * 100)
            vr.append((n, {"sharpe": round(float(r.mean() * PPY / vol), 2),
                           "sortino": round(float(r.mean() * PPY / dn), 2),
                           "cagr": round(cg, 1), "maxdd": round(md, 1),
                           "calmar": round(cg / abs(md), 2),
                           "izpost": round(float(np.mean(izp) * 100), 1),
                           "obrat": 0.0, "provizije": 0.0}))
        out.setdefault("knjiga", {})[okno] = {n: m for n, m in vr}
        izpis("  %s, %s do %s, %d dni"
              % (okno.upper(), a or "zacetek", b or "danes", len(idxb)), vr)

    (ROOT / "testing" / "data" / "ansambel.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("\nzapisano v testing/data/ansambel.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
