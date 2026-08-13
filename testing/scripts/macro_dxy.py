"""The DXY row looks good. Interrogate it properly.

On BTC from 2020 the dollar filter shows Sortino 1.170 against 1.095 and a
drawdown of -18.9 % against -29.0 %. Read off a table that is a win, and a
confidence interval spanning zero is not an answer anyone outside this file
finds convincing.

Four questions that are convincing:

  1. WHAT DOES IT DO TO THE MONEY? Sortino is a ratio. A filter that cuts time
     in the market improves the ratio while leaving you poorer. Final wealth is
     what a reader actually understands.
  2. DOES IT HOLD ON ETH? Same rule, second asset, no re-fitting.
  3. IS IT CONSISTENT, OR ONE LUCKY STRETCH? Year by year.
  4. WOULD WE HAVE PICKED IT IN TIME? Walk-forward: choose on the past only,
     apply forward, never look ahead.

    python testing/scripts/macro_dxy.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "testing", ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns
from testing.scripts.macro_data import load as load_macro
from testing.scripts.macro_v2 import FEE, PPY, build, maxdd, risk_off, sortino

OUT = ROOT / "testing" / "data" / "macro_dxy.json"
CELLS = ["brez", "DXY", "kredit HY/IG", "VIX ts", "MOVE"]


def flag_for(name, flags, index):
    if name == "brez":
        return pd.Series(False, index=index)
    return flags[name]


def wealth(pos, ret):
    r = net_returns(pos, ret, FEE).to_numpy(float)
    return float(np.cumprod(1 + r)[-1]), r


def main() -> int:
    macro = load_macro()
    out = {}
    for sym, f in (("BTC", "BTC_binance_warmup.parquet"),
                   ("ETH", "ETH_binance.parquet")):
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / f)
        ret = raw["close"].pct_change().fillna(0.0)
        flags = risk_off(macro, raw.index)
        pos = {c: build(raw, flag_for(c, flags, raw.index)) for c in CELLS}
        idx = pos["brez"].index

        print(f"\n{'=' * 88}\n{sym}   {idx[0].date()} -> {idx[-1].date()}\n{'=' * 88}")

        # 1 ─ money, not ratios
        print("\n1. KOLIKO DENARJA OSTANE  (zacetek = 10.000 EUR)")
        print(f"   {'razlicica':<16}{'Sortino':>9}{'konec':>12}{'razlika':>12}{'cas v trgu':>12}")
        base_w, base_r = wealth(pos["brez"], ret)
        for c in CELLS:
            w, r = wealth(pos[c], ret)
            d = (w / base_w - 1) * 100
            print(f"   {c:<16}{sortino(r):>9.3f}{10000*w:>11,.0f}€"
                  f"{'' if c=='brez' else f'{d:>+11.1f}%'}"
                  f"{pos[c].mean()*100:>11.1f}%")

        # 2 ─ year by year
        print("\n2. LETO ZA LETOM  (koncni znesek iz 10.000 EUR v tem letu)")
        years = sorted({d.year for d in idx})
        head = "".join(f"{y:>9}" for y in years)
        print(f"   {'razlicica':<16}{head}")
        yr = {}
        for c in CELLS:
            cells, yv = [], {}
            for y in years:
                m = (idx.year == y)
                w = float(np.cumprod(1 + net_returns(pos[c][m], ret, FEE).to_numpy(float))[-1])
                yv[y] = w
                cells.append(f"{w:>8.2f}x")
            yr[c] = yv
            print(f"   {c:<16}" + "".join(cells))
        wins = {c: sum(1 for y in years if yr[c][y] > yr["brez"][y]) for c in CELLS if c != "brez"}
        print(f"   {'':<16}" + "  boljsi od izhodisca: "
              + ", ".join(f"{c} {v}/{len(years)}" for c, v in wins.items()))

        # 3 ─ walk-forward: pick on the past only
        print("\n3. WALK-FORWARD  (izberi na preteklem, uporabi naprej)")
        for tr, te in ((3, 1), (2, 1)):
            picks, segs, base_segs = [], [], []
            start = idx[0]
            while True:
                tb = start + pd.DateOffset(years=tr)
                eb = tb + pd.DateOffset(years=te)
                if eb > idx[-1]:
                    break
                w_in = idx[(idx >= start) & (idx <= tb)]
                sc = {c: sortino(net_returns(pos[c].reindex(w_in), ret, FEE).to_numpy(float))
                      for c in CELLS}
                pk = max(sc, key=lambda z: sc[z] if np.isfinite(sc[z]) else -9e9)
                w_out = idx[(idx > tb) & (idx <= eb)]
                picks.append(pk)
                segs.append(pos[pk].reindex(w_out))
                base_segs.append(pos["brez"].reindex(w_out))
                start = start + pd.DateOffset(years=te)
            if segs:
                wf, _ = wealth(pd.concat(segs), ret)
                bw, _ = wealth(pd.concat(base_segs), ret)
                print(f"   {tr}y/{te}y  izbrano: {', '.join(picks)}")
                print(f"          {'izbira sproti':<18}{10000*wf:>11,.0f}€"
                      f"      brez varovalke {10000*bw:>11,.0f}€")

        out[sym] = {"wealth": {c: wealth(pos[c], ret)[0] for c in CELLS},
                    "yearly": yr, "wins": wins}

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")
    print(f"\nJSON -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
