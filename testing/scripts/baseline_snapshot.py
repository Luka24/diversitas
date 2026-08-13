"""Zamrzne trenutno vedenje Lean strategije za BTC in ETH.

To je slika stanja PRED prepakiranjem za produkcijo. Po njem se pozene se enkrat
in oba izpisa se morata ujemati do zadnje decimalke. Ce se ne, je prepakiranje
nekaj spremenilo in vemo tocno kaj.

Racuna se iz zamrznjenih posnetkov v testing/data/sources/, ne iz omrezja, zato
je izid vedno enak ne glede na to, kdaj se pozene in ali je Binance dosegljiv.

    python testing/scripts/baseline_snapshot.py            zapisi
    python testing/scripts/baseline_snapshot.py --preveri  primerjaj z zapisanim
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from shared.costs import net_returns, turnover
from shared.warmup import trim_warmup
from diversitas.config import LeanConfig
from diversitas.strategy import run_strategy, S_BULL

FEE, PPY = 0.30, 365          # odstotek na stran
OUT_JSON = ROOT / "testing" / "data" / "baseline_lean.json"
OUT_TXT = ROOT / "testing" / "data" / "baseline_lean.txt"
ASSETS = (("BTC", "BTC_binance_warmup.parquet"), ("ETH", "ETH_binance.parquet"))


def trades(df: pd.DataFrame, pos: pd.Series, close: pd.Series) -> list:
    """Vsak posel posebej: vstop, izstop, cena, donos, razlog izstopa."""
    out = []
    chg = pos.diff().fillna(pos.iloc[0])
    starts = list(pos.index[chg > 0])
    ends = list(pos.index[chg < 0])
    if pos.iloc[0] > 0:
        starts.insert(0, pos.index[0])
    for i, s in enumerate(starts):
        e = next((x for x in ends if x > s), None)
        p_in = float(close.loc[s])
        p_out = float(close.loc[e]) if e is not None else float(close.iloc[-1])
        gross = p_out / p_in - 1.0
        net = (1 + gross) * (1 - FEE / 100) ** 2 - 1.0
        row = df.loc[e] if e is not None else df.iloc[-1]
        out.append({
            "st": i + 1,
            "vstop": str(s.date()),
            "izstop": str(e.date()) if e is not None else "odprt",
            "dni": int((e - s).days) if e is not None else int((pos.index[-1] - s).days),
            "cena_vstop": round(p_in, 2),
            "cena_izstop": round(p_out, 2),
            "bruto_pct": round(gross * 100, 2),
            "neto_pct": round(net * 100, 2),
            "razlog": ("pregretje" if bool(row.get("blowoff", False))
                       else "prelom trenda" if e is not None else "se odprt"),
        })
    return out


def metrics(pos: pd.Series, ret: pd.Series) -> dict:
    r = net_returns(pos, ret, FEE).to_numpy(float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    neg = r[r < 0]
    return {
        "dni": int(len(r)),
        "sortino": round(float(r.mean() / neg.std() * np.sqrt(PPY)), 6),
        "cagr_pct": round(float((eq[-1] ** (PPY / len(r)) - 1) * 100), 4),
        "maxdd_pct": round(float(dd.min() * 100), 4),
        "koncni_mnozitelj": round(float(eq[-1]), 6),
        "izpostavljenost_pct": round(float(pos.mean() * 100), 4),
        "poslov": int((np.diff(pos.to_numpy(), prepend=pos.iloc[0]) > 0).sum()),
        "promet": round(float(turnover(pos).sum()), 6),
    }


def build() -> dict:
    cfg = LeanConfig()
    snap = {"provizija_na_stran_pct": FEE, "vir": "zamrznjen posnetek Binance",
            "config": {k: v for k, v in vars(cfg).items() if k != "symbol_map"},
            "sredstva": {}}
    for sym, fname in ASSETS:
        raw = pd.read_parquet(ROOT / "testing" / "data" / "sources" / fname)
        df = trim_warmup(run_strategy(raw, config=cfg).df)
        pos = (df["signal_state"] == S_BULL).astype(float)
        close = raw["close"].reindex(df.index)
        ret = close.pct_change().fillna(0.0)
        snap["sredstva"][sym] = {
            "od": str(df.index[0].date()), "do": str(df.index[-1].date()),
            "metrike": metrics(pos, ret),
            "posli": trades(df, pos, close),
        }
    return snap


def to_text(snap: dict) -> str:
    L = []
    L.append("POSNETEK LEAN STRATEGIJE")
    L.append(f"provizija {snap['provizija_na_stran_pct']} % na stran, {snap['vir']}")
    for sym, d in snap["sredstva"].items():
        m = d["metrike"]
        L.append("")
        L.append("=" * 78)
        L.append(f"{sym}   {d['od']} do {d['do']}   {m['dni']} dni")
        L.append("=" * 78)
        L.append(f"  Sortino {m['sortino']:.6f}    CAGR {m['cagr_pct']:.4f} %"
                 f"    MaxDD {m['maxdd_pct']:.4f} %")
        L.append(f"  koncni mnozitelj {m['koncni_mnozitelj']:.6f}x"
                 f"    v trgu {m['izpostavljenost_pct']:.4f} %"
                 f"    poslov {m['poslov']}")
        L.append("")
        L.append(f"  {'st':>3}  {'vstop':<11}{'izstop':<11}{'dni':>5}"
                 f"{'cena vstop':>12}{'cena izstop':>13}{'bruto':>9}{'neto':>9}  razlog")
        for t in d["posli"]:
            L.append(f"  {t['st']:>3}  {t['vstop']:<11}{t['izstop']:<11}{t['dni']:>5}"
                     f"{t['cena_vstop']:>12,.2f}{t['cena_izstop']:>13,.2f}"
                     f"{t['bruto_pct']:>8.2f}%{t['neto_pct']:>8.2f}%  {t['razlog']}")
    return "\n".join(L) + "\n"


def main() -> int:
    snap = build()
    if "--preveri" in sys.argv:
        if not OUT_JSON.exists():
            print("Posnetka se ni. Pozeni brez --preveri.")
            return 2
        old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        if old == snap:
            print("Ujema se popolnoma. Vedenje strategije je nespremenjeno.")
            for sym, d in snap["sredstva"].items():
                m = d["metrike"]
                print(f"  {sym}: Sortino {m['sortino']:.6f}, {m['poslov']} poslov, "
                      f"koncni mnozitelj {m['koncni_mnozitelj']:.6f}x")
            return 0
        print("RAZLIKA. Prepakiranje je nekaj spremenilo:")
        for sym in snap["sredstva"]:
            a = old["sredstva"].get(sym, {}).get("metrike", {})
            b = snap["sredstva"][sym]["metrike"]
            for k in b:
                if a.get(k) != b[k]:
                    print(f"  {sym}.{k}: bilo {a.get(k)}  zdaj {b[k]}")
            pa = old["sredstva"].get(sym, {}).get("posli", [])
            pb = snap["sredstva"][sym]["posli"]
            if pa != pb:
                print(f"  {sym}: posli se razlikujejo ({len(pa)} proti {len(pb)})")
        return 1

    OUT_JSON.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_TXT.write_text(to_text(snap), encoding="utf-8")
    print(to_text(snap))
    print(f"zapisano v {OUT_JSON.name} in {OUT_TXT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
