"""Preizkus taktične razporeditve, zgrajene od začetka.

    python testing/scripts/etf_taa.py

Brez davka, po naročilu. Brez kripto pristopov. Provizija 0,20 % na posel,
gotovina po dejanski meri ECB (kupljiva kot XEON).

DVE OKNI, IN DRUGO JE POMEMBNEJŠE

  pravo      od 2020, ko ima 13612W momentum dovolj zgodovine na vseh osmih.
             Šest let in pol, en resen padec. Premalo za sodbo.
  podaljšano od 2006 prek preverjenih mesečnih nadomestkov. Ti so bili za
             dnevno rabo zavrnjeni, za MESEČNO pa ocenjeni kot uporabni — in ta
             strategija je mesečna, zato je to zdaj legitimna raba, ne bližnjica.
             Zajame 2008.

OVIRE, KI JIH MORA KANDIDAT PRESKOČITI

  1  statični delež z isto povprečno izpostavljenostjo — glavna ovira
  2  kupi in drži obeh knjig
  3  protokol faz in vezani bločni bootstrap
  4  brez nastavitve, izbrane na naših podatkih

Izhod: testing/data/etf_taa.json
"""
from __future__ import annotations

import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "etf"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from diversitas.taa import TAAConfig, run_taa                    # noqa: E402
from shared.etf_data import cash_rate, load                      # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE             # noqa: E402
from testing.scripts import etf_wfo as W                         # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_taa.json"
FEE = 0.20


def _met(r, idx):
    r = np.asarray(r, float)
    ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    v = r.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    c = eq[-1] ** (ppy / len(r)) - 1
    return dict(letno=c * 100, vol=v * 100, sharpe=r.mean() * ppy / v,
                sortino=r.mean() * ppy / dn, maxdd=dd.min() * 100,
                calmar=c / abs(dd.min()) if dd.min() < 0 else np.nan)


def _panel(backfill: bool):
    px = pd.DataFrame({k: load(k, start="1999-01-01", backfill=backfill)["close"]
                       for k in UNIVERSE})
    return px.dropna()


def _bh(px, w):
    cols = [c for c in w if c in px.columns]
    wv = np.array([w[c] for c in cols])
    return (px[cols].pct_change().fillna(0.0) * wv).sum(axis=1)


def _sekcija(px, ime_okna, cr, res):
    idx = px.index
    ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
    cash_d = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0)
              / 100.0 / ppy)
    print(f"\n{'='*100}\n{ime_okna}: {idx[0].date()} -> {idx[-1].date()} "
          f"({len(idx)/ppy:.1f} let, {ppy:.0f} dni/leto)\n{'='*100}")

    kand = {
        "TAA top3, obratna vol, kanarček": TAAConfig(),
        "TAA top3, min. varianca": TAAConfig(utezitev="min_var"),
        "TAA top2, obratna vol": TAAConfig(top_n=2),
        "TAA top4, obratna vol": TAAConfig(top_n=4),
        "TAA top3, BREZ kanarčka": TAAConfig(uporabi_kanarcka=False),
        "TAA top3, 6-mes. momentum (ReSolve)": TAAConfig(momentum="6m"),
        "TAA top3, ena tranša (sreča pri datumu)": TAAConfig(transe=1),
    }
    vrst, serije = [], {}
    print(f"{'kandidat':<40} {'letno':>7} {'vol':>6} {'Sharpe':>7} {'Sortino':>8} "
          f"{'MaxDD':>8} {'Calmar':>7} {'v tveg.':>8} {'obrat':>7}")
    for ime, cfg in kand.items():
        r = run_taa(px, cfg, fee_per_trade_pct=FEE, cash_daily=cash_d)
        m = _met(r.returns, idx)
        serije[ime] = r.returns
        izp = float(r.risk_on.mean())
        obr = float(r.turnover.sum() / (len(idx) / ppy) * 100)
        vrst.append(dict(ime=ime, **m, v_tveganem=izp * 100, obrat=obr))
        print(f"{ime:<40} {m['letno']:6.2f} % {m['vol']:5.1f} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:7.1f} % {m['calmar']:7.2f} "
              f"{izp*100:7.0f} % {obr:6.0f} %")

    print()
    merila = {"P1 kupi in drži": _bh(px, PORTFOLIOS["P1"]),
              "P2 kupi in drži": _bh(px, PORTFOLIOS["P2"]),
              "vseh 8 enako": _bh(px, {k: 1 / 8 for k in UNIVERSE})}
    for ime, r in merila.items():
        m = _met(r, idx)
        serije[ime] = r
        vrst.append(dict(ime=ime, **m, v_tveganem=100.0, obrat=0.0))
        print(f"{ime:<40} {m['letno']:6.2f} % {m['vol']:5.1f} {m['sharpe']:7.2f} "
              f"{m['sortino']:8.2f} {m['maxdd']:7.1f} % {m['calmar']:7.2f} "
              f"{100:7.0f} % {0:6.0f} %")

    # glavna ovira: statični delež z isto izpostavljenostjo, proti P2
    naj = max([v for v in vrst if v["ime"].startswith("TAA")],
              key=lambda v: v["sharpe"])
    r_naj = serije[naj["ime"]]
    print(f"\nGLAVNA OVIRA za najboljšega po Sharpu ({naj['ime']}):")
    for merilo in ("P2 kupi in drži", "vseh 8 enako"):
        izp = naj["v_tveganem"] / 100.0
        r_stat = serije[merilo] * izp + (1 - izp) * cash_d
        ms = _met(r_stat, idx)
        ci = W.paired_diff_ci(pd.Series(np.asarray(r_naj), index=idx),
                              pd.Series(np.asarray(r_stat), index=idx),
                              n_boot=1500, td=int(round(ppy)))
        print(f"   proti statičnim {izp*100:.0f} % od „{merilo}" + "“"
              f" ({ms['letno']:.2f} %, Sh {ms['sharpe']:.2f}): "
              f"d Sortino {ci['point']:+.2f} [{ci['lo']:+.2f}, {ci['hi']:+.2f}] "
              f"{ci['verdict']}")

    # protokol faz
    world = px["World"]
    faze = W.date_phases(world)
    ph = W.per_phase(pd.Series(np.asarray(r_naj), index=idx),
                     serije["P2 kupi in drži"], faze, td=int(round(ppy)))
    if len(ph):
        up = ph[ph["kind"] == "rast"]
        dn = ph[ph["kind"] == "padec"]
        print(f"   protokol faz proti P2: rast {int(up['wins'].sum())}/{len(up)}, "
              f"padec {int(dn['wins'].sum())}/{len(dn)}  (faz skupaj {len(ph)})")

    res[ime_okna] = dict(rows=vrst, best=naj["ime"])
    return serije


def main() -> int:
    pd.set_option("display.width", 220)
    cr = cash_rate()
    res = {"generated": str(pd.Timestamp.utcnow()), "fee_per_trade_pct": FEE,
           "note": "brez davka, po narocilu"}

    px_real = _panel(backfill=False)
    _sekcija(px_real, "PRAVI PODATKI", cr, res)

    px_bf = _panel(backfill=True)
    _sekcija(px_bf, "PODALJSANO Z MESECNIMI NADOMESTKI", cr, res)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
