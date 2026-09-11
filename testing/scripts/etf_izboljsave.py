"""Vse ideje za izboljšavo, preizkušene po istem postopku.

    python testing/scripts/etf_izboljsave.py

Brez davka. Provizija 0,20 % na posel. Gotovina po dejanski meri ECB.

POSTOPEK, KI GA VSAK KANDIDAT PREJDE

  1  cela zgodovina (podaljšana z mesečno ocenjenimi nadomestki, 18,7 leta)
  2  po oknih: zasnova, validacija, hold-out
  3  obrat in koliko stane
  4  proti statičnemu deležu z ISTO povprečno izpostavljenostjo — glavna ovira
  5  protokol faz proti najboljšemu pasivnemu merilu
  6  popravek za število poskusov, štet čez VSE preizkušene nastavitve

NAPREDOVANJE, NE MREŽA

Kandidati niso naključna mreža, ampak zaporedje: vsak korak doda eno idejo iz
literature k prejšnjemu najboljšemu. Tako je vidno, katera ideja kaj prispeva, in
število poskusov ostane majhno — kar je edino, kar rezultat zadržuje pred
popravkom za mnogokratno testiranje.

Izhod: testing/data/etf_izboljsave.json
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

from diversitas.taa import TAAConfig, run_taa                    # noqa: E402
from shared.etf_data import cash_rate, load                      # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE             # noqa: E402
from testing.scripts import etf_wfo as W                         # noqa: E402
from testing.scripts import stats as ST                          # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_izboljsave.json"
FEE = 0.20


def met(r, ppy):
    r = np.asarray(r, float)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    v = r.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    c = eq[-1] ** (ppy / len(r)) - 1
    return dict(letno=c * 100, vol=v * 100, sharpe=r.mean() * ppy / v,
                sortino=r.mean() * ppy / dn, maxdd=dd.min() * 100,
                calmar=c / abs(dd.min()) if dd.min() < 0 else np.nan)


def main() -> int:
    pd.set_option("display.width", 240)
    px = pd.DataFrame({k: load(k, start="1999-01-01", backfill=True)["close"]
                       for k in UNIVERSE}).dropna()
    idx = px.index
    ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
    cr = cash_rate()
    cash_d = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0)
              / 100.0 / ppy)
    print(f"okno {idx[0].date()} -> {idx[-1].date()}  ({len(idx)/ppy:.1f} let, "
          f"{ppy:.0f} dni/leto)  provizija {FEE} %/posel\n")

    def bh(w):
        cols = [c for c in w if c in px.columns]
        wv = np.array([w[c] for c in cols])
        return (px[cols].pct_change().fillna(0.0) * wv).sum(axis=1)

    # ── pasivna merila ────────────────────────────────────────────────────────
    merila = {"P1 kupi in drži": bh(PORTFOLIOS["P1"]),
              "P2 kupi in drži": bh(PORTFOLIOS["P2"]),
              "vseh 8 enako": bh({k: 1 / 8 for k in UNIVERSE})}

    # ── napredovanje kandidatov ───────────────────────────────────────────────
    KAND = {
        "A1 osnova (13612W, top3, obr.vol, kanarček)": TAAConfig(),
        "A2 + ansambel hitrosti": TAAConfig(momentum="ansambel"),
        "A3 + delni premik 0,5": TAAConfig(momentum="ansambel", delni_premik=0.5),
        "A4 + fiksni obrambni del": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                              fiksni_obrambni=True),
        "A5 + histereza 0,05": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                         fiksni_obrambni=True, histereza=0.05),
        "A6 A5 z utežmi HRP": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                        fiksni_obrambni=True, histereza=0.05,
                                        utezitev="hrp"),
        "A7 A5 z enakimi utežmi": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                            fiksni_obrambni=True, histereza=0.05,
                                            utezitev="enake"),
        "A8 A5 brez kanarčka": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                         fiksni_obrambni=True, histereza=0.05,
                                         uporabi_kanarcka=False),
        "A9 A5 s top4": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                  fiksni_obrambni=True, histereza=0.05, top_n=4),
        "A10 A5 z 12 tranšami": TAAConfig(momentum="ansambel", delni_premik=0.5,
                                          fiksni_obrambni=True, histereza=0.05,
                                          transe=12),
    }

    serije, vrst = {}, []
    print(f"{'kandidat':<44} {'letno':>7} {'Sharpe':>7} {'Sortino':>8} {'MaxDD':>8} "
          f"{'Calmar':>7} {'v tveg':>7} {'obrat':>7} {'strošek':>8}")
    for ime, cfg in KAND.items():
        r = run_taa(px, cfg, fee_per_trade_pct=FEE, cash_daily=cash_d)
        r0 = run_taa(px, cfg, fee_per_trade_pct=0.0, cash_daily=cash_d)
        m = met(r.returns, ppy)
        m0 = met(r0.returns, ppy)
        serije[ime] = r.returns
        obr = float(r.turnover.sum() / (len(idx) / ppy) * 100)
        vrst.append(dict(ime=ime, **m, v_tveganem=float(r.risk_on.mean()) * 100,
                         obrat=obr, strosek=m0["letno"] - m["letno"]))
        print(f"{ime:<44} {m['letno']:6.2f} % {m['sharpe']:7.2f} {m['sortino']:8.2f} "
              f"{m['maxdd']:7.1f} % {m['calmar']:7.2f} "
              f"{float(r.risk_on.mean())*100:6.0f} % {obr:6.0f} % "
              f"{m0['letno']-m['letno']:7.2f}")

    # ansambel strategij: povprečje petih najrazličnejših
    izbor = ["A2 + ansambel hitrosti", "A5 + histereza 0,05", "A6 A5 z utežmi HRP",
             "A8 A5 brez kanarčka", "A9 A5 s top4"]
    r_ans = sum(serije[k] for k in izbor) / len(izbor)
    serije["A11 ansambel petih strategij"] = r_ans
    m = met(r_ans, ppy)
    vrst.append(dict(ime="A11 ansambel petih strategij", **m,
                     v_tveganem=np.nan, obrat=np.nan, strosek=np.nan))
    print(f"{'A11 ansambel petih strategij':<44} {m['letno']:6.2f} % {m['sharpe']:7.2f} "
          f"{m['sortino']:8.2f} {m['maxdd']:7.1f} % {m['calmar']:7.2f}")

    print()
    for ime, r in merila.items():
        m = met(r, ppy)
        serije[ime] = r
        print(f"{ime:<44} {m['letno']:6.2f} % {m['sharpe']:7.2f} {m['sortino']:8.2f} "
              f"{m['maxdd']:7.1f} % {m['calmar']:7.2f} {100:6.0f} % {0:6.0f} %")

    # ── po oknih ──────────────────────────────────────────────────────────────
    print("\nPO OKNIH (Sharpe)")
    print(f"{'kandidat':<44} {'cela':>7} {'zasnova':>9} {'validacija':>11} {'hold-out':>9}")
    po_oknih = {}
    for ime in list(serije):
        r = serije[ime]
        vals = [met(r, ppy)["sharpe"]]
        for sp in ("design", "validation", "holdout"):
            x = W.split(r, sp)
            vals.append(met(x, ppy)["sharpe"] if len(x) > 60 else np.nan)
        po_oknih[ime] = vals
        print(f"{ime:<44} " + "".join(f"{v:>9.2f}" if np.isfinite(v) else f"{'-':>9}"
                                      for v in vals))

    # ── glavna ovira + protokol faz za najboljšega ────────────────────────────
    taa_imena = [v["ime"] for v in vrst]
    naj = max(taa_imena, key=lambda k: met(serije[k], ppy)["sharpe"])
    print(f"\nGLAVNA OVIRA za {naj}")
    izp = next((v["v_tveganem"] for v in vrst if v["ime"] == naj), np.nan)
    if not np.isfinite(izp):
        izp = float(np.nanmean([v["v_tveganem"] for v in vrst
                                if v["ime"] in izbor]))
    izp /= 100.0
    for mer in ("P2 kupi in drži", "vseh 8 enako"):
        r_stat = serije[mer] * izp + (1 - izp) * cash_d
        ms = met(r_stat, ppy)
        ci = W.paired_diff_ci(pd.Series(np.asarray(serije[naj]), index=idx),
                              pd.Series(np.asarray(r_stat), index=idx),
                              n_boot=1500, td=int(round(ppy)))
        print(f"   proti statičnim {izp*100:.0f} % od {mer:<20} "
              f"({ms['letno']:5.2f} %, Sh {ms['sharpe']:.2f}): "
              f"d Sortino {ci['point']:+.2f} [{ci['lo']:+.2f}, {ci['hi']:+.2f}] "
              f"{ci['verdict']}")
    faze = W.date_phases(px["World"])
    ph = W.per_phase(pd.Series(np.asarray(serije[naj]), index=idx),
                     serije["P2 kupi in drži"], faze, td=int(round(ppy)))
    if len(ph):
        up, dn = ph[ph["kind"] == "rast"], ph[ph["kind"] == "padec"]
        print(f"   protokol faz proti P2: rast {int(up['wins'].sum())}/{len(up)}, "
              f"padec {int(dn['wins'].sum())}/{len(dn)}")

    # ── popravek za število poskusov ──────────────────────────────────────────
    print("\nPOPRAVEK ZA ŠTEVILO POSKUSOV")
    vsi_sr = np.array([met(serije[k], ppy)["sharpe"] for k in taa_imena])
    n_prej = 8      # nastavitve iz prejšnjega kroga, ki jih je treba prišteti
    n_skupaj = len(taa_imena) + n_prej
    ds = ST.deflated_sharpe(np.asarray(serije[naj]), n_trials=n_skupaj,
                            trials_sharpe_std=float(np.std(vsi_sr)) / np.sqrt(ppy),
                            td=ppy)
    print(f"   preizkušenih tu {len(taa_imena)}, prejšnji krog {n_prej}, skupaj {n_skupaj}")
    print(f"   najboljši {naj}: Sharpe {met(serije[naj], ppy)['sharpe']:.3f}")
    print(f"   prag iz {n_skupaj} poskusov brez učinka: {ds['sr0_ann']:.3f}")
    print(f"   popravljena verjetnost: {ds['dsr']:.3f}   (prag 0,95)")

    res = dict(generated=str(pd.Timestamp.utcnow()), fee=FEE, ppy=ppy,
               rows=vrst, po_oknih=po_oknih, best=naj,
               deflated={k: float(v) for k, v in ds.items() if isinstance(v, (int, float))})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
