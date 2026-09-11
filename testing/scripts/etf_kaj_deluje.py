"""Kaj na teh dveh knjigah sploh deluje — po tem, ko trendni sloj pade.

    python testing/scripts/etf_kaj_deluje.py

`etf_baseline.py` pokaze, da noben trendni ali rotacijski kandidat ne prestane
protokola. To je koristno, a nepopolno: pove, cesa ne delati. Ta skripta
preveri edino druzino posegov, ki je v altcoinski kampanji dala statisticno
znacilen pozitiven rezultat — **ciljanje volatilnosti na ravni knjige** — in
poleg nje se uteži po obratni volatilnosti.

Metoda je ista kot v `porocilo_nacrt_altcoini.md`, del 1d in 1e:

    p = min( ciljna_volatilnost / sigma60 , kapa )

kjer je sigma60 60-dnevna realizirana volatilnost knjige do vceraj. Brez vzvoda
pomeni kapa = 1, torej se pozicija lahko samo zmanjsa. Uravnava se mesecno,
ostalo je gotovina.

Kaj se meri in zakaj tako:
  - Sharpe in Sortino sta neodvisna od obsega, zato je primerjava razmerij
    postena tudi pri razlicni izpostavljenosti;
  - najhujsi padec ni, zato je povsod naveden ob njem, z intervalom zaupanja;
  - vsaka razlika gre skozi vezani blocni bootstrap. Interval, ki vsebuje
    niclo, ni rezultat.

Izhod: testing/data/etf_kaj_deluje.json
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
for p in (ROOT, ROOT / "etf"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared.etf_data import load_panel                       # noqa: E402
from shared.etf_universe import PORTFOLIOS                   # noqa: E402
from testing.scripts import etf_eval as EV                   # noqa: E402
from testing.scripts import etf_wfo as W                     # noqa: E402

from diversitas.rotation import _drifted, _hold_between_rebalances  # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_kaj_deluje.json"
TD = 252
FEE = 0.20 / 100.0          # na vsak posel; povratni posel torej 0,40 %


def book(name: str, rebalance: int = 63):
    """Kupi in drzi knjigo, uravnavano vsake `rebalance` dni, neto provizij."""
    weights = PORTFOLIOS[name]
    _, frames = load_panel(name)
    px = pd.DataFrame({k: frames[k]["close"] for k in weights}).dropna()
    rets = px.pct_change().fillna(0.0)
    tgt = pd.DataFrame(np.tile([weights[k] for k in weights], (len(px), 1)),
                       index=px.index, columns=list(weights))
    tgt = _hold_between_rebalances(tgt, rebalance)
    held, traded = _drifted(tgt, rets, rebalance)
    return (held * rets).sum(axis=1) - traded * FEE, rets, frames


def vol_target(base: pd.Series, target_pct: float, lookback: int = 60,
               cap: float = 1.0, rebalance: int = 21):
    """Skaliraj celo knjigo na ciljno volatilnost. Odlocitev iz vcerajsnjih
    podatkov (`shift(1)`), sprememba pozicije le ob uravnavanju."""
    vol = base.rolling(lookback).std() * np.sqrt(TD) * 100.0
    scale = (target_pct / vol.clip(lower=1e-9)).clip(upper=cap).shift(1)
    scale = scale.where(np.arange(len(scale)) % rebalance == 0).ffill().fillna(0.0)
    traded = scale.diff().abs().fillna(0.0)
    traded.iloc[0] = 0.0
    return scale * base - traded * FEE, scale


def inverse_vol(rets: pd.DataFrame, keys: list, lookback: int = 120,
                rebalance: int = 21):
    """Uteži po obratni volatilnosti — enak prispevek tveganja, brez korelacij."""
    iv = 1.0 / (rets[keys].rolling(lookback).std() * np.sqrt(TD))
    w = _hold_between_rebalances(iv.div(iv.sum(axis=1), axis=0).shift(1).fillna(0.0),
                                 rebalance)
    held, traded = _drifted(w, rets, rebalance)
    return (held * rets).sum(axis=1) - traded * FEE


def _maxdd(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min() * 100.0)


def main() -> int:
    pd.set_option("display.width", 220)
    out: dict = {"generated": str(pd.Timestamp.utcnow()), "fee_per_side_pct": FEE * 100}

    for name in ("P1", "P2"):
        base, rets, frames = book(name)
        keys = list(PORTFOLIOS[name])
        cands: dict[str, pd.Series] = {}
        rows = [EV.evaluate(base, label=f"{name} kupi in drzi (cetrtletno)")]

        for tv in (6, 8, 10, 12):
            r, sc = vol_target(base, tv)
            cands[f"ciljanje {tv}%, brez vzvoda"] = r
            rows.append(EV.evaluate(r, bench=base, position=sc,
                                    label=f"ciljanje {tv}%, brez vzvoda"))
        for tv in (10, 12):
            r, sc = vol_target(base, tv, cap=1.5)
            cands[f"ciljanje {tv}%, do 1,5x"] = r
            rows.append(EV.evaluate(r, bench=base, position=sc,
                                    label=f"ciljanje {tv}%, do 1,5x"))
        r_iv = inverse_vol(rets, keys)
        cands["uteži po obratni volatilnosti"] = r_iv
        rows.append(EV.evaluate(r_iv, bench=base, label="uteži po obratni volatilnosti"))

        print(f"\n=== {name}  {', '.join(f'{k} {v:.0%}' for k, v in PORTFOLIOS[name].items())} ===")
        print(EV.fmt(EV.compare(rows, sort_by="sortino")))

        world = frames["World"]["close"].reindex(base.index).ffill()
        phases = W.date_phases(world)
        print("\n   protokol faz + vezani blocni bootstrap (osnova = kupi in drzi):")
        detail = {}
        for label, cand in cands.items():
            ph = W.per_phase(cand, base, phases)
            ci_s = W.paired_diff_ci(cand, base, n_boot=2000)
            ci_d = W.paired_diff_ci(cand, base, metric=_maxdd, n_boot=2000)
            up = ph[ph["kind"] == "rast"]
            dn = ph[ph["kind"] == "padec"]
            print(f"      {label:<30} rast {int(up['wins'].sum())}/{len(up)}  "
                  f"padec {int(dn['wins'].sum())}/{len(dn)}   "
                  f"dSortino {ci_s['point']:+.2f} [{ci_s['lo']:+.2f}, {ci_s['hi']:+.2f}] "
                  f"{ci_s['verdict']:<11} dMaxDD {ci_d['point']:+.1f} "
                  f"[{ci_d['lo']:+.1f}, {ci_d['hi']:+.1f}] {ci_d['verdict']}")
            detail[label] = dict(rising=f"{int(up['wins'].sum())}/{len(up)}",
                                 falling=f"{int(dn['wins'].sum())}/{len(dn)}",
                                 ci_sortino=ci_s, ci_maxdd=ci_d)
        out[name] = dict(table=[{k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                                 for k, v in r.items()} for r in rows],
                         protocol=detail,
                         n_phases=len(phases))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
