"""Koliko se stara in nova Pine skripta dejansko razlikujeta.

    python testing/scripts/pine_stara_nova.py [BTC ETH SOL ...]

Besedilna razlika pove, katere vrstice so se spremenile. Ta skripta pove, kaj
to naredi: koliko dni se signal razhaja, koliko poslov je vec ali manj, in kaj
se zgodi z denarjem.

STARA (pred 2026-08-03 / 08-10 / 08-18, kot je stala v repozitoriju)
    vstop   aboveTL and close > maMed and trackRisingWindow
            and distPct >= trackBuf and regimeOK
    izstop  belowTL (3 bare), blowoff, volShock
    delez   100 * min(1, targetVol / annualVol)   -- skaliran po volatilnosti
    dno     brez

NOVA
    vstop   donchianOK and trackRisingWindow and regimeOK and not blowoff
    izstop  belowTL (3 bare), blowoff
    delez   0 ali 100                             -- binaren
    dno     5 %, ki se nikoli ne uravnava

Provizija 0,30 % na stran, kot povsod v tem projektu.
"""
from __future__ import annotations

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
from testing.scripts.preveri_pine import (                      # noqa: E402
    _rsi, avtomat_po_pine, pine_privzetki, po_pine, pozicija_po_pine)

FEE = 0.30
PPY = 365


def stara_pravila(px: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Pogoji stare skripte, prepisani iz razlicice pred spremembami."""
    high, low, close = px["high"], px["low"], px["close"]
    n = p["trackPeriod"]
    trackline = (high.rolling(n, min_periods=n).max()
                 + low.rolling(n, min_periods=n).min()) / 2.0
    buf = trackline * (p["trackBuf"] / 100.0)
    aboveTL = close > (trackline + buf)
    belowTL = close < (trackline - buf)
    distPct = (close - trackline) / trackline * 100.0
    trackRisingWindow = trackline > trackline.shift(p["trackSlopeBars"])

    maMed = close.rolling(50, min_periods=50).mean()             # maMedLen
    ml = p["maLongLen"]
    maLong = close.rolling(ml, min_periods=ml).mean()
    bearRegime = (~(close > maLong)) & (maLong < maLong.shift(p["maSlope"]))
    regimeOK = ~bearRegime

    rsiVal = _rsi(close, p["rsiLen"])
    blowoff = (distPct > p["blowoffDist"]) & (rsiVal > 80)

    logRet = np.log(close / close.shift(1))
    annualVol = logRet.rolling(20, min_periods=20).std(ddof=0) * np.sqrt(365) * 100
    volShock = (annualVol > annualVol.rolling(50, min_periods=50).mean() * 1.5) & belowTL

    distEntryOK = distPct >= p["trackBuf"]        # minDistEntry = 0
    bull = (aboveTL & (close > maMed) & trackRisingWindow
            & distEntryOK & regimeOK).fillna(False)
    return pd.DataFrame(dict(belowTL=belowTL.fillna(False),
                             bullCondition=bull,
                             blowoff=blowoff.fillna(False),
                             volShock=volShock.fillna(False),
                             annualVol=annualVol), index=px.index)


def avtomat_stari(f: pd.DataFrame, p: dict) -> np.ndarray:
    below = f["belowTL"].to_numpy()
    bull = f["bullCondition"].to_numpy()
    blow = f["blowoff"].to_numpy()
    shock = f["volShock"].to_numpy()
    n = len(f)
    sig = np.full(n, 3, dtype=np.int8)
    st, since, below_c, hold_c = 3, 999, 0, 0
    for i in range(n):
        since += 1
        below_c = below_c + 1 if below[i] else 0
        hold_c = hold_c + 1 if bull[i] else 0
        if st == 1:
            if below[i] and below_c >= p["exitGraceBars"]:
                st, since = 3, 0
            elif blow[i]:
                st, since = 3, 0
            elif shock[i]:                       # tretji izstop, odstranjen
                st, since = 3, 0
        elif st == 3:
            if (bull[i] and hold_c >= p["confirmBars"]
                    and since >= p["reentryHold"]):
                st, since = 1, 0
        sig[i] = st
    return sig


def met(r: np.ndarray) -> dict:
    eq = np.cumprod(1.0 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return dict(cagr=(eq[-1] ** (PPY / len(r)) - 1.0) * 100,
                sortino=r.mean() * PPY / dn if dn > 0 else np.nan,
                maxdd=dd.min() * 100, mult=eq[-1])


def donos(px, pos, traded, fee=FEE):
    ret = px["close"].pct_change().fillna(0.0).to_numpy(float)
    return pos * ret - traded * fee / 100.0


def main() -> int:
    args = sys.argv[1:]
    let = None
    if "--let" in args:
        i = args.index("--let")
        let = float(args[i + 1])
        del args[i:i + 2]
    simboli = args or ["BTC", "ETH", "SOL"]
    p = pine_privzetki()
    print(f"provizija {FEE} % na stran"
          + (f", okno zadnjih {let:g} let" if let else "") + "\n")
    for s in simboli:
        px = fetch_candles(s, "1d", bars=3000, prefer="coinbase")
        # ── nova ────────────────────────────────────────────────────────────
        fn = po_pine(px, p)
        sn = avtomat_po_pine(fn, p)["signalState"].to_numpy()
        held_n, trad_n = pozicija_po_pine(px, sn, p)
        # ── stara ───────────────────────────────────────────────────────────
        fs = stara_pravila(px, p)
        ss = avtomat_stari(fs, p)
        volScale = np.minimum(1.0, 50.0 / fs["annualVol"].to_numpy())
        alloc_s = np.where(ss == 1, np.nan_to_num(volScale, nan=0.0), 0.0)
        held_s = np.concatenate([[0.0], alloc_s[:-1]])          # velja naslednji bar
        trad_s = np.abs(np.diff(np.concatenate([[0.0], held_s])))

        # skupno okno: obe pravili potrebujeta 200 SMA + 20 vol
        m = ~np.isnan(fs["annualVol"].to_numpy())
        m &= np.arange(len(px)) >= 220
        if let:
            # Okno zadnjih N let. Ogrevanje se zgodi PRED njim, ne v njem:
            # signal na prvi dan okna ze tece, kot bi na TradingView.
            zac = px.index[-1] - pd.Timedelta(days=int(round(let * 365.25)))
            m &= np.asarray(px.index >= zac)
        rn, rs = donos(px, held_n, trad_n)[m], donos(px, held_s, trad_s)[m]
        mn, ms = met(rn), met(rs)
        rb = px["close"].pct_change().fillna(0.0).to_numpy(float)[m]
        mb = met(rb)
        razh = int((sn[m] != ss[m]).sum())
        pn = int((np.diff(sn[m]) != 0).sum())
        ps = int((np.diff(ss[m]) != 0).sum())

        print("=" * 86)
        print(f"{s}   {px.index[m][0].date()} -> {px.index[-1].date()}   "
              f"{int(m.sum())} barov")
        print("=" * 86)
        print(f"{'':<26}{'STARA':>14}{'NOVA':>14}{'razlika':>14}")
        vrst = [("signal BULL, delez dni", (ss[m] == 1).mean() * 100,
                 (sn[m] == 1).mean() * 100, "%"),
                ("povprecna pozicija", held_s[m].mean() * 100,
                 held_n[m].mean() * 100, "%"),
                ("preklopov", ps, pn, ""),
                ("obrat na leto", trad_s[m].sum() / (m.sum() / PPY) * 100,
                 trad_n[m].sum() / (m.sum() / PPY) * 100, "%"),
                ("CAGR", ms["cagr"], mn["cagr"], "%"),
                ("Sortino", ms["sortino"], mn["sortino"], ""),
                ("MaxDD", ms["maxdd"], mn["maxdd"], "%"),
                ("1 EUR -> ", ms["mult"], mn["mult"], "x")]
        for ime, a, b, e in vrst:
            print(f"{ime:<26}{a:>13.2f}{e:<1}{b:>13.2f}{e:<1}{b - a:>+13.2f}{e:<1}")
        print(f"{'signal se razhaja':<26}{razh:>13} dni  "
              f"({razh / m.sum() * 100:.1f} % vseh barov)")
        print(f"{'-- kupi in drzi':<26}{'CAGR ' + format(mb['cagr'], '.2f') + ' %':>13}"
              f"{'  Sortino ' + format(mb['sortino'], '.2f'):>16}"
              f"{'  MaxDD ' + format(mb['maxdd'], '.1f') + ' %':>16}"
              f"{'  1 EUR -> ' + format(mb['mult'], '.2f') + 'x':>18}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
