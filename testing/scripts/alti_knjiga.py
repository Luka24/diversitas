"""Kje je se prostor, ko se je izkazalo, da parametri niso.

    python testing/scripts/alti_knjiga.py

Prilagajanje parametrov po sredstvu izven vzorca izgublja, in kar je huje --
NAKLJUCNA izbira iz mreze prekasa vsako prilagojeno. Mreza je torej ravna in
prilagajanje pobira sum. Ce tam prostora ni, kje je?

Preostale proste izbire niso v signalu, ampak v KNJIGI. Te se preizkusijo tu,
vse na istih privzetih parametrih, da razlika ne more priti iz nastavitev:

  1  enako utezena sest              -- izhodisce, kar se trguje danes
  2  samo BTC + ETH                  -- ali alti sploh kaj prispevajo
  3  brez najsibkejsih dveh          -- izbira nabora namesto parametrov
  4  utezi po obratni volatilnosti   -- vsak prispeva podoben delez tveganja
  5  knjizno stikalo na BTC          -- ce BTC ni v trendu, cela knjiga ven
  6  samo BTC                        -- ali je razprsitev sploh kaj vredna

Vsaka mera je izracunana iz DENARJA po nalozbah, ne iz povprecja donosov.
Provizija 0,30 % na stran. Izhod: testing/data/alti_knjiga.json
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.data_source import fetch_candles                    # noqa: E402
from testing.scripts.alti_parametri2 import (                   # noqa: E402
    FEE, PPY, VIRI, blok_bootstrap, panel, sortino)
from testing.scripts.preveri_pine import (                      # noqa: E402
    avtomat_po_pine, pine_privzetki, po_pine, pozicija_po_pine)

OUT = ROOT / "testing" / "data" / "alti_knjiga.json"
OD = "2021-09-09"        # zadnjih pet let


def main() -> int:
    p0 = pine_privzetki()
    r_sym, pos_sym, vol_sym = {}, {}, {}
    print(f"provizija {FEE} % na stran, od {OD}\n")
    for sym, vir in VIRI.items():
        try:
            px = fetch_candles(sym, "1d", bars=3000, prefer=vir)
        except Exception as e:                                    # noqa: BLE001
            print(f"   {sym}: vira ni ({type(e).__name__})")
            continue
        ret = px["close"].pct_change().fillna(0.0)
        f = po_pine(px, p0)
        sig = avtomat_po_pine(f, p0)["signalState"].to_numpy()
        held, traded = pozicija_po_pine(px, sig, p0)
        r = held * ret.to_numpy(float) - traded * FEE / 100.0
        r_sym[sym] = pd.Series(r, index=px.index)
        pos_sym[sym] = pd.Series(held, index=px.index)
        lr = np.log(px["close"] / px["close"].shift(1))
        vol_sym[sym] = (lr.rolling(60, min_periods=60).std(ddof=0)
                        * np.sqrt(PPY))
        print(f"   {sym:<5}{px.index[0].date()} -> {px.index[-1].date()}")

    R = pd.DataFrame(r_sym).loc[OD:].dropna(how="all")
    V = pd.DataFrame(vol_sym).reindex(R.index)
    P = pd.DataFrame(pos_sym).reindex(R.index)
    simboli = list(R.columns)
    print(f"\n   skupno okno {R.index[0].date()} -> {R.index[-1].date()}  "
          f"({len(R)} barov, {len(simboli)} sredstev)\n")

    # BTC v trendu = njegov signal je BULL (pozicija nad dnom)
    btc_v_trendu = (P["BTC"] > 0.5) if "BTC" in P else pd.Series(True, index=R.index)

    # najsibkejsa dva po Sortinu na PRVI polovici okna -- izbrana vnaprej,
    # ne po ogledu celote
    pol = len(R) // 2
    moc = {s: sortino(R[s].iloc[:pol].dropna().to_numpy()) for s in simboli}
    najsibkejsa = sorted(moc, key=lambda s: moc[s])[:2]
    print(f"   najsibkejsa dva na prvi polovici: {', '.join(najsibkejsa)}"
          f"   (Sortino {', '.join(f'{moc[s]:.2f}' for s in najsibkejsa)})\n")

    knjige = {}
    knjige["1 enako utezenih 6"] = R.mean(axis=1)
    knjige["2 samo BTC + ETH"] = R[[s for s in ("BTC", "ETH") if s in R]].mean(axis=1)
    ostanek = [s for s in simboli if s not in najsibkejsa]
    knjige["3 brez najsibkejsih 2"] = R[ostanek].mean(axis=1)
    w = (1.0 / V).replace([np.inf, -np.inf], np.nan)
    w = w.div(w.sum(axis=1), axis=0)
    knjige["4 obratna volatilnost"] = (R * w).sum(axis=1).where(w.notna().any(axis=1))
    knjige["5 knjizno stikalo BTC"] = R.mean(axis=1).where(btc_v_trendu, 0.0)
    knjige["6 samo BTC"] = R["BTC"] if "BTC" in R else R.mean(axis=1)

    print("=" * 92)
    print("SESTAVA KNJIGE, vsi na istih privzetih parametrih")
    print("=" * 92)
    print(f"{'knjiga':<26}{'CAGR':>9}{'Sharpe':>9}{'Sortino':>9}{'MaxDD':>9}"
          f"{'1 EUR ->':>10}{'v trgu':>9}")
    izpis = {}
    for ime, s in knjige.items():
        s = s.dropna()
        q = panel(s.to_numpy())
        izp = float(P.reindex(s.index).mean(axis=1).mean() * 100)
        izpis[ime] = q
        print(f"{ime:<26}{q['cagr']:>8.2f}%{q['sharpe']:>9.2f}{q['sortino']:>9.2f}"
              f"{q['maxdd']:>8.1f}%{q['mult']:>9.2f}x{izp:>8.0f}%")

    print("\n" + "=" * 92)
    print("PROTI IZHODISCU (enako utezenih 6), bootstrap po blokih")
    print("=" * 92)
    osn = knjige["1 enako utezenih 6"].dropna()
    znac = {}
    for ime, s in knjige.items():
        if ime.startswith("1 "):
            continue
        sk = pd.concat([s, osn], axis=1).dropna()
        d = (sk.iloc[:, 0] - sk.iloc[:, 1]).to_numpy()
        a, b = sortino(sk.iloc[:, 0].to_numpy()), sortino(sk.iloc[:, 1].to_numpy())
        bs = blok_bootstrap(d)
        lo, hi = np.nanpercentile(bs, [5, 95])
        sodba = "BOLJSI" if lo > 0 else "SLABSI" if hi < 0 else "nedokazano"
        znac[ime] = dict(d=a - b, lo=float(lo), hi=float(hi), sodba=sodba)
        print(f"   {ime:<26}d Sortino {a - b:+.2f}   [{lo:+.2f}, {hi:+.2f}]"
              f"   -> {sodba}")

    res = dict(generated=str(pd.Timestamp.utcnow()), od=OD, fee=FEE,
               najsibkejsa=najsibkejsa,
               moc_prva_polovica={k: float(v) for k, v in moc.items()},
               knjige=izpis, znacilnost=znac)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
