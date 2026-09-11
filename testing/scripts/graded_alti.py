"""Stopnjevana velikost pozicije na uporabnikovih sestih sredstvih.

    python testing/scripts/graded_alti.py

Kaj se meri. Danes je vstop binaren: vse stiri vstopne razmere morajo drzati
hkrati, sicer je pozicija nic (oziroma 5 % dno). Stopnjevana razlicica namesto
tega presteje, koliko razmer drzi, in drzi sorazmerni del:

    k = above_tl + track_rising_window + regime_ok + donchian_ok      0..4
    pozicija = k / 4,  vstop ko je k >= prag

Blow-off in BTC filter ostaneta trda, kot sta danes. Vse ostalo je danasnji
motor: potrditev 3 dni, premor 15 dni, izstop tri dni pod pasom, 5 % dno.

Zakaj to. Na BTC je ta poseg edini v celotnem projektu, ki je izboljsal Sortino
BREZ spremembe casa v trgu: 41,9 % proti 41,8 %. Vsi ostali so si rezultat
sposodili tako, da so bili manj v trgu. Nikoli ni bil merjen na altcoinih.

Delitev je ista kot povsod: ucenje do 2023-06, validacija do 2025-03, hold-out
po tem. Provizija in zdrs skupaj 0,30 % na stran.

Izhod: testing/data/graded_alti.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from diversitas.config import LeanConfig
from diversitas.strategy import compute_features
from shared.data_source import DEFAULT_SYMBOL_MAP, fetch_candles
from shared.warmup import trim_warmup

FEE = 0.30 / 100
PPY = 365
SREDSTVA = ("BTC", "ETH", "SOL", "LINK", "BNB", "HYPE")
UTEZI = {"BTC": .50, "ETH": .10, "SOL": .10, "LINK": .10, "BNB": .10, "HYPE": .10}
TERMS = ("above_tl", "track_rising_window", "regime_ok", "donchian_ok")

DELITEV = (
    ("ucenje",    None,         "2023-06-30"),
    ("validacija", "2023-07-01", "2025-03-31"),
    ("hold-out",  "2025-04-01", None),
)

RAZLICICE = {
    "danes (binarno)": None,     # prag 4, brez stopnjevanja
    "stopnje k>=1": 1,
    "stopnje k>=2": 2,
    "stopnje k>=3": 3,
}

PREDPOMNILNIK = ROOT / "testing" / "data" / "cene_alti.pkl"


def _cfg():
    base = LeanConfig()
    sm = dict(DEFAULT_SYMBOL_MAP)
    sm.update(base.symbol_map)          # lean pozna BNB, shared ga ne
    sm.setdefault("BNB", {"coinbase": "BNB-USD"})
    sm["HYPE"] = {"hyperliquid": "HYPE"}
    return replace(base, symbol_map=sm)


def _binance(par: str) -> pd.DataFrame:
    """Coinbase ne kotira BNB, zato gre ta z Binancea, tako kot v dashboardu."""
    import time

    import requests
    out, start = [], 1_500_000_000_000
    while True:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol": par, "interval": "1d",
                                 "startTime": start, "limit": 1000},
                         timeout=30).json()
        if not r:
            break
        out += r
        if len(r) < 1000:
            break
        start = r[-1][0] + 86_400_000
        time.sleep(0.2)
    d = pd.DataFrame(out, columns=["t", "open", "high", "low", "close",
                                   "volume"] + ["x"] * 6)
    d["time"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    return d.set_index("time")[["open", "high", "low", "close",
                                "volume"]].astype(float)


def cene() -> dict:
    if PREDPOMNILNIK.exists():
        return pd.read_pickle(PREDPOMNILNIK)
    cfg = _cfg()
    out = {}
    for s in SREDSTVA:
        if s == "BNB":
            out[s] = _binance("BNBUSDT")
        else:
            vir = "hyperliquid" if s == "HYPE" else "coinbase"
            out[s] = fetch_candles(s, "1d", bars=5000, config=cfg,
                                   prefer=vir, strict=True)
        print("   %-5s %d dni  %s do %s" % (s, len(out[s]),
              out[s].index[0].date(), out[s].index[-1].date()))
    pd.to_pickle(out, PREDPOMNILNIK)
    return out


def pozicija(raw: pd.DataFrame, prag: int | None) -> pd.Series:
    """Danasnji motor. prag=None pomeni danasnje binarno vedenje."""
    cfg = _cfg()
    df = compute_features(raw, None, cfg)
    k = sum(df[t].fillna(False).astype(int) for t in TERMS)
    need = len(TERMS) if prag is None else prag
    df = df.copy()
    df["bull_condition"] = ((k >= need) & df["btc_filter_ok"]
                            & ~df["blowoff"]).fillna(False)

    n = len(df)
    bull = df["bull_condition"].to_numpy()
    below = df["below_tl"].fillna(False).to_numpy()
    blow = df["blowoff"].fillna(False).to_numpy()
    sig = np.full(n, 3, np.int8)
    alloc = np.zeros(n, np.float32)
    cur, bsig, hold, bc = 3, 999, 0, 0
    for i in range(n):
        bsig += 1
        bc = bc + 1 if below[i] else 0
        hold = hold + 1 if bull[i] else 0
        if cur == 1:
            if (below[i] and bc >= cfg.exit_grace_bars) or blow[i]:
                cur, bsig = 3, 0
        elif bull[i] and hold >= cfg.confirm_bars and bsig >= cfg.reentry_hold:
            cur, bsig = 1, 0
        alloc[i] = 100.0 if cur == 1 else 0.0
        sig[i] = cur

    st = trim_warmup(df.assign(signal_state=sig, target_alloc=alloc,
                               display_state=sig, signal_changed=False))
    # dno 5 %, ki drifta, tako kot v produkciji
    dno = cfg.bear_alloc_pct / 100.0
    p = pd.Series(np.where(st["signal_state"].shift(1) == 1, 1.0, dno),
                  index=st.index, dtype=float)
    p.iloc[0] = dno
    if prag is not None:
        stopnja = (k.reindex(st.index).shift(1).fillna(0) / len(TERMS)).clip(0, 1)
        p = np.maximum(p * stopnja, dno)
    return p


def metrike(p: pd.Series, ret: pd.Series, fee=FEE) -> dict:
    t = p.diff().abs().fillna(0.0)
    r = (p.shift(0) * ret - t * fee).fillna(0.0).to_numpy(float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    vol = r.std() * np.sqrt(PPY)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return {
        "sharpe": round(float(r.mean() * PPY / vol), 2) if vol > 0 else np.nan,
        "sortino": round(float(r.mean() * PPY / dn), 2) if dn > 0 else np.nan,
        "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
        "maxdd": round(float(dd.min() * 100), 1),
        "izpost": round(float(p.mean() * 100), 1),
        "obrat": round(float(t.sum()), 1),
        "provizije": round(float(t.sum() * fee * 100), 1),
    }


def rezi(s: pd.Series, a, b) -> pd.Series:
    if a is not None:
        s = s.loc[s.index >= pd.Timestamp(a, tz="UTC")]
    if b is not None:
        s = s.loc[s.index <= pd.Timestamp(b, tz="UTC")]
    return s


def main() -> int:
    print("CENE")
    C = cene()
    RET = {s: C[s]["close"].pct_change().fillna(0.0) for s in SREDSTVA}

    print("\nPOZICIJE")
    POS = {}
    for ime, prag in RAZLICICE.items():
        POS[ime] = {s: pozicija(C[s], prag) for s in SREDSTVA}
        print("   %s" % ime)

    out = {"po_sredstvu": {}, "knjiga": {}}

    for okno, a, b in DELITEV:
        print("\n\n%s  %s do %s" % (okno.upper(), a or "zacetek", b or "danes"))
        print("  %-16s%-6s%8s%9s%8s%9s%9s%9s"
              % ("razlicica", "sred", "Sharpe", "Sortino", "CAGR", "MaxDD",
                 "izpost", "provizij"))
        for ime in RAZLICICE:
            for s in SREDSTVA:
                p = rezi(POS[ime][s], a, b)
                if len(p) < 90:
                    continue
                m = metrike(p, RET[s].reindex(p.index).fillna(0.0))
                out["po_sredstvu"].setdefault(okno, {}).setdefault(ime, {})[s] = m
                print("  %-16s%-6s%8.2f%9.2f%7.0f%%%8.0f%%%8.0f%%%8.1f%%"
                      % (ime, s, m["sharpe"], m["sortino"], m["cagr"],
                         m["maxdd"], m["izpost"], m["provizije"]))
            print()

        # knjiga 50/10/10/10/10/10, mesecno uravnavanje
        print("  %-16s%s" % ("KNJIGA", "50/10/10/10/10/10"))
        for ime in RAZLICICE:
            idx = rezi(POS[ime]["BTC"], a, b).index
            E = {k: 100.0 * w for k, w in UTEZI.items()}
            pot, izp = [], []
            zadnji_mesec = None
            for d in idx:
                skup_pred = sum(E.values())
                delezi = []
                for k, w in UTEZI.items():
                    p = POS[ime][k]
                    if d not in p.index:
                        delezi.append(0.0)
                        continue
                    i = p.index.get_loc(d)
                    pv = float(p.iloc[i])
                    tv = abs(pv - float(p.iloc[i - 1])) if i else 0.0
                    E[k] *= 1 + pv * float(RET[k].loc[d]) - tv * FEE
                    delezi.append(pv * E[k])
                skup = sum(E.values())
                izp.append(sum(delezi) / skup if skup > 0 else 0.0)
                if zadnji_mesec is not None and d.month != zadnji_mesec:
                    cilj = {k: skup * w for k, w in UTEZI.items()}
                    E = {k: v - abs(v - E[k]) * FEE for k, v in cilj.items()}
                zadnji_mesec = d.month
                pot.append(sum(E.values()))
            pot = np.array(pot)
            r = np.diff(pot, prepend=100.0) / np.concatenate([[100.0], pot[:-1]])
            eq = np.cumprod(1 + r)
            dd = eq / np.maximum.accumulate(eq) - 1
            vol = r.std() * np.sqrt(PPY)
            dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
            m = {"sharpe": round(float(r.mean() * PPY / vol), 2),
                 "sortino": round(float(r.mean() * PPY / dn), 2),
                 "cagr": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 1),
                 "maxdd": round(float(dd.min() * 100), 1),
                 "izpost": round(float(np.mean(izp) * 100), 1)}
            out["knjiga"].setdefault(okno, {})[ime] = m
            print("  %-16s%-6s%8.2f%9.2f%7.0f%%%8.0f%%%8.0f%%"
                  % (ime, "", m["sharpe"], m["sortino"], m["cagr"],
                     m["maxdd"], m["izpost"]))

    (ROOT / "testing" / "data" / "graded_alti.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print("\nzapisano v testing/data/graded_alti.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
