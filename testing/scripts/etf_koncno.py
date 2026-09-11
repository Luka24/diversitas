"""Končni preizkus: vsak portfelj zase, dve stopnji tveganja, s polno zaščito
pred prilagajanjem.

    python testing/scripts/etf_koncno.py

ŠTIRI ODLOČITVE, KI SO DANE IN SE NE ISCEJO
  1  portfelja sta LOČENA — P1 ne sme uporabiti obveznic iz P2
  2  provizija 0,20 % na vsak posel
  3  brez davka
  4  dve stopnji tveganja, obe deklarirani vnaprej, ne izbrani po podatkih

ZAŠČITA PRED PRILAGAJANJEM — pet ravni, vse iz literature

  A  Malo parametrov, logika pred optimizacijo. Vse vrednosti signala so
     privzetki iz objavljenih člankov (Keller, ReSolve, Newfound). Edino, kar je
     naša izbira, je zgornja meja tveganja, in ta je preferenca, ne ocena.

  B  Plato namesto vrha. Namesto najboljše nastavitve se vzame sredina območja,
     kjer sosednje nastavitve dajejo podobno. Če majhna sprememba parametra
     močno premakne rezultat, je to prilagajanje šumu.

  C  Verjetnost prilagajanja (PBO) po Baileyju in Lópezu de Pradu, z metodo
     CSCV. Meri, kako pogosto nastavitev, ki je najboljša na eni polovici
     zgodovine, na drugi polovici pade pod sredino. Ključno opozorilo iz
     članka: PBO se približuje 1, ko raste število preizkušenih nastavitev —
     ne glede na to, ali katera od njih res deluje.

  D  Popravek Sharpa za število poskusov (deflated Sharpe) in Harvey-Liu odbitek.
     Harvey in Liu opozarjata, da je pavšalni 50-odstotni odbitek huda napaka:
     popravek je nelinearen.

  E  Preverjanje na DRUGEM trgu. Ista pravila se poženejo na obeh portfeljih
     neodvisno. Če delujejo samo na enem, je to znak prilagajanja.

MERILA so tista, ki jih poroča stroka za to družino: CAGR, volatilnost,
najhujši padec in čas okrevanja, Ulcerjev indeks, Sharpe, Sortino, najslabši
mesec, delež pozitivnih mesecev, delež časa v trgu, obrat.

Izhod: testing/data/etf_koncno.json
"""
from __future__ import annotations

import json
import sys
import warnings
from itertools import combinations, product
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
from shared.etf_universe import PORTFOLIOS                       # noqa: E402
from testing.scripts import etf_wfo as W                         # noqa: E402
from testing.scripts import stats as ST                          # noqa: E402

NL = chr(10)
OUT = ROOT / "testing" / "data" / "etf_koncno.json"
FEE = 0.20

# Kateri sklad je v kateri vlogi, po portfeljih. P1 nima obrambnega sklada,
# zato je njegovo zavetje gotovina — to je posledica zahteve, da sta portfelja
# ločena, in je za P1 resna omejitev, ne podrobnost.
UNIVERZUM = {
    "P1": dict(tvegana=("World", "EM", "SmallCap", "Quality"),
               obrambna=(), kanarcek=("World", "EM")),
    "P2": dict(tvegana=("World", "EM", "Gold", "Commod"),
               obrambna=("GlobAgg", "InflLink"), kanarcek=("EM", "GlobAgg")),
}

# Dve stopnji tveganja. Obe sta DEKLARIRANI, ne iskani.
STOPNJE = {"previdna": dict(max_tvegano=0.60), "agresivna": dict(max_tvegano=1.00)}


def _plateau(params: list, values: list, space: dict, k: int = 4) -> dict:
    """Sredina najboljšega platoja, ne najboljša posamična nastavitev.

    Za vsako nastavitev se izračuna povprečje njenih k najbližjih sosedov v
    normiranem prostoru parametrov, in izbere se tista z najvišjim povprečjem
    soseščine. Če je nastavitev dobra samo zato, ker so njeni sosedje slabi, jo
    to izloči — in prav to je podpis prilagajanja šumu.

    Ista logika kot `testing/scripts/wfo.plateau_select`; prepisana sem, ker ta
    modul uvozi optuna, ki v tem okolju ni nameščena, in ena funkcija ne
    upravičuje odvisnosti.
    """
    keys = list(space)
    P = np.array([[float(tp[key]) for key in keys] for tp in params], float)
    v = np.array(values, float)
    ok = np.isfinite(v)
    P, v = P[ok], v[ok]
    tp_ok = [t for t, o in zip(params, ok) if o]
    if len(v) == 0:
        return params[0]
    span = np.array([(space[key][1] - space[key][0]) or 1 for key in keys], float)
    lo = np.array([space[key][0] for key in keys], float)
    Pn = (P - lo) / span
    plateau = np.empty(len(v))
    for i in range(len(v)):
        d = np.sqrt(((Pn - Pn[i]) ** 2).sum(axis=1))
        nn = np.argsort(d)[:min(k, len(v))]
        plateau[i] = np.nanmean(v[nn])
    return dict(tp_ok[int(np.argmax(plateau))])


# ── merila, kot jih poroča stroka ─────────────────────────────────────────────

def panel(r: pd.Series, ppy: float, obrat: float = np.nan,
          v_trgu: float = np.nan) -> dict:
    x = np.asarray(r, float)
    eq = np.cumprod(1 + x)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    v = x.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(x, 0.0) ** 2)) * np.sqrt(ppy)
    cagr = eq[-1] ** (ppy / len(x)) - 1
    i = int(np.argmin(dd))
    vrh = int(np.argmax(eq[:i + 1])) if i > 0 else 0
    okrev = np.where(eq[i:] >= eq[vrh])[0]
    mes = pd.Series(x, index=r.index)
    mm = (1 + mes).groupby([mes.index.year, mes.index.month]).prod() - 1
    return dict(
        cagr=cagr * 100, vol=v * 100, sharpe=x.mean() * ppy / v,
        sortino=x.mean() * ppy / dn, maxdd=dd.min() * 100,
        ulcer=float(np.sqrt((dd ** 2).mean())) * 100,
        calmar=cagr / abs(dd.min()) if dd.min() < 0 else np.nan,
        dni_okrevanja=int(okrev[0]) if len(okrev) else -1,
        najslabsi_mesec=float(mm.min()) * 100,
        delez_poz_mesecev=float((mm > 0).mean()) * 100,
        v_trgu=v_trgu, obrat=obrat)


def natisni(ime: str, m: dict) -> None:
    print(f"{ime:<34} {m['cagr']:6.2f} {m['vol']:6.1f} {m['sharpe']:6.2f} "
          f"{m['sortino']:7.2f} {m['maxdd']:7.1f} {m['ulcer']:6.1f} {m['calmar']:6.2f} "
          f"{m['dni_okrevanja']:6d} {m['najslabsi_mesec']:7.1f} "
          f"{m['delez_poz_mesecev']:6.0f} "
          f"{m['v_trgu']:6.0f}" if np.isfinite(m['v_trgu']) else
          f"{ime:<34} {m['cagr']:6.2f} {m['vol']:6.1f} {m['sharpe']:6.2f} "
          f"{m['sortino']:7.2f} {m['maxdd']:7.1f} {m['ulcer']:6.1f} {m['calmar']:6.2f} "
          f"{m['dni_okrevanja']:6d} {m['najslabsi_mesec']:7.1f} "
          f"{m['delez_poz_mesecev']:6.0f}")


GLAVA = (f"{'kandidat':<34} {'CAGR':>6} {'vol':>6} {'Sharp':>6} {'Sortin':>7} "
         f"{'MaxDD':>7} {'Ulcer':>6} {'Calmar':>6} {'okrev':>6} {'najm':>7} "
         f"{'+mes':>6} {'vtrgu':>6}")


def main() -> int:
    pd.set_option("display.width", 250)
    cr = cash_rate()
    res: dict = {"generated": str(pd.Timestamp.utcnow()), "fee": FEE,
                 "brez_davka": True, "portfelja_locena": True}

    # mreža za plato in PBO. Namenoma majhna: vsaka dodana nastavitev dvigne PBO.
    # Sest nastavitev, ne dvanajst. Stevilo tranś ni parameter, ki bi ga bilo
    # smiselno iskati — je metoda proti sreci pri datumu in je pripeta na 12.
    # Bailey in Lopez de Prado: PBO raste s stevilom preizkusenih nastavitev, ne
    # glede na to, ali katera od njih res deluje. Manj poskusov je torej boljsi
    # test, ne slabsi.
    MREZA = dict(top_n=[2, 3], delni_premik=[0.34, 0.5, 0.67], transe=[12])

    samo = sys.argv[1] if len(sys.argv) > 1 else None
    for pf, uni in UNIVERZUM.items():
        if samo and pf != samo:
            continue
        w_pf = PORTFOLIOS[pf]
        vsi = sorted(set(uni["tvegana"]) | set(uni["obrambna"]) | set(w_pf))
        px = pd.DataFrame({k: load(k, start="1999-01-01", backfill=True)["close"]
                           for k in vsi}).dropna()
        idx = px.index
        ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
        cash_d = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0)
                  / 100.0 / ppy)
        rets = px.pct_change().fillna(0.0)
        r_bh = (rets[list(w_pf)] * np.array([w_pf[c] for c in w_pf])).sum(axis=1)

        print(f"\n{'='*160}\n{pf}   {idx[0].date()} -> {idx[-1].date()}  "
              f"({len(idx)/ppy:.1f} let)   tvegani: {', '.join(uni['tvegana'])}   "
              f"zavetje: {', '.join(uni['obrambna']) or 'gotovina'}\n{'='*160}")
        print(GLAVA)
        natisni(f"{pf} kupi in drži", panel(r_bh, ppy, 0.0, 100.0))

        res[pf] = {}
        for stopnja, dial in STOPNJE.items():
            base = dict(tvegana=uni["tvegana"], obrambna=uni["obrambna"],
                        kanarcek=uni["kanarcek"], momentum="ansambel",
                        fiksni_obrambni=True, histereza=0.05, **dial)
            # ── mreža ─────────────────────────────────────────────────────────
            imena, serije, izp = [], {}, {}
            for tn, dp, tr in product(MREZA["top_n"], MREZA["delni_premik"],
                                      MREZA["transe"]):
                cfg = TAAConfig(top_n=tn, delni_premik=dp, transe=tr, **base)
                out = run_taa(px, cfg, fee_per_trade_pct=FEE, cash_daily=cash_d)
                key = f"top{tn} prem{dp} tr{tr}"
                imena.append(key)
                serije[key] = out.returns
                izp[key] = (float(out.risk_on.mean()),
                            float(out.turnover.sum() / (len(idx) / ppy) * 100))

            M = pd.DataFrame(serije)
            sr = {k: panel(serije[k], ppy)["sharpe"] for k in imena}

            # ── B: plato namesto vrha ─────────────────────────────────────────
            params = [dict(top_n=int(k.split()[0][3:]),
                           delni_premik=float(k.split()[1][4:]),
                           transe=int(k.split()[2][2:])) for k in imena]
            space = {"top_n": (2, 3, 1), "delni_premik": (0.34, 0.67, 0.01),
                     "transe": (4, 12, 1)}
            p_izbor = _plateau(params, [sr[k] for k in imena], space, k=4)
            p_key = f"top{p_izbor['top_n']} prem{p_izbor['delni_premik']} tr{p_izbor['transe']}"
            vrh_key = max(imena, key=lambda k: sr[k])

            print(f"\n-- {stopnja} (največ {dial['max_tvegano']*100:.0f} % v tveganih) --")
            for naslov, key in (("vrh mreže", vrh_key), ("SREDINA PLATOJA", p_key)):
                m = panel(serije[key], ppy, izp[key][1], izp[key][0] * 100)
                natisni(f"{naslov}: {key}", m)
            r_sel = serije[p_key]
            e = izp[p_key][0]
            r_stat = e * r_bh + (1 - e) * cash_d
            natisni(f"statičnih {e*100:.0f} % (glavna ovira)",
                    panel(r_stat, ppy, 0.0, e * 100))

            ci = W.paired_diff_ci(pd.Series(np.asarray(r_sel), index=idx),
                                  pd.Series(np.asarray(r_stat), index=idx),
                                  n_boot=800, td=int(round(ppy)))
            print(f"    proti statičnemu deležu: d Sortino {ci['point']:+.2f} "
                  f"[{ci['lo']:+.2f}, {ci['hi']:+.2f}]  P(boljši) {ci['p_better']:.0%}"
                  f"  -> {ci['verdict']}")

            # ── C: PBO po CSCV ────────────────────────────────────────────────
            pbo = ST.prob_backtest_overfit(M.to_numpy(), n_splits=10)
            # ── D: deflated Sharpe + Harvey-Liu odbitek ───────────────────────
            sr_arr = np.array(list(sr.values()))
            ds = ST.deflated_sharpe(np.asarray(r_sel), n_trials=len(imena),
                                    trials_sharpe_std=float(np.std(sr_arr)) / np.sqrt(ppy),
                                    td=ppy)
            n = len(r_sel)
            t = panel(r_sel, ppy)["sharpe"] * np.sqrt(len(r_sel) / ppy)
            from scipy import stats as sps
            p_ena = 2 * (1 - sps.norm.cdf(abs(t)))
            p_bonf = min(1.0, p_ena * len(imena))
            t_bonf = sps.norm.ppf(1 - p_bonf / 2) if p_bonf < 1 else 0.0
            odbitek = 1 - (t_bonf / t) if t > 0 else 1.0
            print(f"    PBO (verjetnost prilagajanja): {pbo['pbo']:.1%}   "
                  f"deflated Sharpe: {ds['dsr']:.3f} (prag 0,95)")
            print(f"    Harvey-Liu: t = {t:.2f}, po Bonferroniju za {len(imena)} "
                  f"poskusov t = {t_bonf:.2f}, odbitek Sharpa {odbitek*100:.0f} %"
                  f"  ->  {panel(r_sel, ppy)['sharpe']*(1-odbitek):.2f}")

            res[pf][stopnja] = dict(
                izbrana=p_key, vrh=vrh_key,
                metrike=panel(r_sel, ppy, izp[p_key][1], izp[p_key][0] * 100),
                staticni=panel(r_stat, ppy), vs_static=ci,
                pbo=float(pbo["pbo"]), dsr=float(ds["dsr"]),
                haircut=float(odbitek), sharpe_po_odbitku=float(
                    panel(r_sel, ppy)["sharpe"] * (1 - odbitek)),
                sharpe_mreza=[float(x) for x in sr_arr])

    # ── E: preverjanje na drugem trgu ─────────────────────────────────────────
    if "P1" in res and "P2" in res:
        print(NL + "=" * 160 + NL
              + "E  ALI ISTA NASTAVITEV DELUJE NA OBEH PORTFELJIH" + NL
              + "=" * 160)
        for stopnja in STOPNJE:
            a, b = res["P1"][stopnja], res["P2"][stopnja]
            am = a["metrike"] if isinstance(a.get("metrike"), dict) else a
            bm = b["metrike"] if isinstance(b.get("metrike"), dict) else b
            print(f"   {stopnja:<11} P1 {a['izbrana']:<20} Sharpe {am['sharpe']:.2f}"
                  f"   |   P2 {b['izbrana']:<20} Sharpe {bm['sharpe']:.2f}"
                  f"   {'ISTA' if a['izbrana']==b['izbrana'] else 'razlicna'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if samo and OUT.exists():
        staro = json.loads(OUT.read_text(encoding="utf-8"))
        staro.update({k: v for k, v in res.items() if k in ("P1", "P2")})
        res = staro
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
