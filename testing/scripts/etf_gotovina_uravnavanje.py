"""Dve osnovni postavki, ki ju nisva nikoli izbrala, le podedovala.

    python testing/scripts/etf_gotovina_uravnavanje.py

Vprasanje "je normalno, da se gotovina obrestuje" je pokazalo, da sta v modelu
dve predpostavki, ki nista bili odlocitev. Ta skripta ju obe postavi na test.

────────────────────────────────────────────────────────────────────────────
A  GOTOVINA

Standard v stroki je, da se strategije merijo v **preseznih donosih nad
netvegano mero**. Sharpe je tako definiran, AQR-jev TSMOM tako meri. Pripisati
gotovini nic ni konservativno, je samo druga predpostavka — in v letih 2023-24,
ko je mera ECB znasala 3,2 in 3,6 %, je napacna za nekaj odstotnih tock na leto
pri strategiji, ki je pol casa zunaj trga.

Vendar: kaj je **dejansko dosegljivo**, je odvisno od posrednika.
  - DEGIRO na evrsko gotovino placa 0 %.
  - Interactive Brokers placa, a ne na prvih 10.000 EUR in po nizji stopnji pod
    100.000 EUR premozenja.
  - Denarni sklad se da kupiti: XEON (Xtrackers EUR Overnight Rate Swap, TER
    0,10 %) ali C3M (Amundi). Izmerjeno na teh podatkih XEON sledi meri ECB na
    0,02 do 0,08 odstotne tocke na leto.

Zato se tu racuna vse troje: 0 %, mera ECB, in mera ECB minus TER denarnega
sklada. Razlika med njimi je odgovor na vprasanje, koliko ta predpostavka sploh
premakne sklep.

Pozor na past: **distribucijski** denarni skladi (XEOD, ERNE, PJS1) imajo v
ceni skoraj nicelni donos, ker se donos izplaca. Kdor bi vzel njihovo ceno kot
donos gotovine, bi si pripisal 0 % namesto 3,6 %.

────────────────────────────────────────────────────────────────────────────
B  URAVNAVANJE

Koledarsko uravnavanje je bilo izbrano brez razloga. Stroka priporoca prage:
Swedroejevo pravilo 5/25 (uravnavaj, ko se rokav s ciljem nad 20 % odmakne za 5
odstotnih tock, oziroma rokav pod 20 % za 25 % relativno) in raziskave Vanguarda,
ki meri prednost pragovnega pristopa okoli 15 do 25 bazicnih tock na leto proti
mesecnemu koledarju.

Tu se primerja sedem politik, in vsaka je ocenjena **tudi po davku**, ker je
uravnavanje edino mesto, kjer davek nastane brez vsakega signala.

Izhod: testing/data/etf_gotovina_uravnavanje.json
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

from dataclasses import replace  # noqa: E402

from diversitas.config import LeanConfig                       # noqa: E402
from diversitas.strategy import S_BULL, run_strategy           # noqa: E402
from shared.etf_data import cash_rate, load                    # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE           # noqa: E402
from shared.tax import SLOVENIA_2026, simulate_brokerage, summarise  # noqa: E402
from shared.warmup import trim_warmup                          # noqa: E402

OUT = ROOT / "testing" / "data" / "etf_gotovina_uravnavanje.json"
FEE = 0.20 / 100.0
MM_TER = 0.10               # TER denarnega sklada, odstotek na leto


def _met(r, idx):
    r = np.asarray(r, float)
    ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
    eq = np.cumprod(1 + r)
    dd = eq / np.maximum.accumulate(eq) - 1
    v = r.std() * np.sqrt(ppy)
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(ppy)
    c = eq[-1] ** (ppy / len(r)) - 1
    return dict(letno=c * 100, sharpe=r.mean() * ppy / v,
                sortino=r.mean() * ppy / dn, maxdd=dd.min() * 100,
                calmar=c / abs(dd.min()) if dd.min() < 0 else np.nan)


# ── A: gotovina ───────────────────────────────────────────────────────────────

def _cash_variants(idx, ppy):
    cr = cash_rate()
    ecb = (cr.reindex(idx.union(cr.index)).ffill().reindex(idx).fillna(0.0) / 100.0 / ppy)
    return {
        "0 % (DEGIRO, gotovina lezi)": pd.Series(0.0, index=idx),
        f"mera ECB minus TER {MM_TER} % (denarni sklad)": ecb - MM_TER / 100.0 / ppy,
        "mera ECB (teoreticno)": ecb,
    }


def section_cash(CENE, BULL):
    print("A  GOTOVINA — koliko premakne sklep\n" + "-" * 96)
    out = {}
    for pf in ("P1", "P2"):
        w = PORTFOLIOS[pf]
        idx = None
        for k in w:
            i = CENE[k].index
            idx = i if idx is None else idx.union(i)
        idx = idx[idx >= max(BULL[k].index[0] for k in w)]
        ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
        px = pd.DataFrame({k: CENE[k].reindex(idx).ffill() for k in w})
        R = px.pct_change().fillna(0.0)
        r_bh = (R * np.array([w[k] for k in w])).sum(axis=1)

        # binarno stikalo po vecini signalov — oblika, ki je najbolj v gotovini
        vec = (pd.DataFrame({k: BULL[k].reindex(idx).fillna(False) for k in w})
               .mean(axis=1) >= 0.5).astype(float)
        tr = vec.diff().abs().fillna(0.0)
        izp = float(vec.mean())

        print(f"\n   {pf}  ({idx[0].date()} -> {idx[-1].date()}, v trgu {izp*100:.0f} %)")
        print(f"      {'predpostavka o gotovini':<46} {'strategija':>11} {'staticni':>10} {'razlika':>9}")
        out[pf] = {}
        for ime, cd in _cash_variants(idx, ppy).items():
            r_str = vec * r_bh + (1 - vec) * cd - tr * FEE
            r_stat = izp * r_bh + (1 - izp) * cd
            a, b = _met(r_str, idx), _met(r_stat, idx)
            print(f"      {ime:<46} {a['letno']:10.2f} % {b['letno']:9.2f} % "
                  f"{a['letno']-b['letno']:+8.2f}")
            out[pf][ime] = dict(strategija=a, staticni=b)
        print(f"      {'kupi in drzi (za primerjavo)':<46} {_met(r_bh, idx)['letno']:10.2f} %")
    return out


# ── B: uravnavanje ────────────────────────────────────────────────────────────

def _band_days(px: pd.DataFrame, w: dict, abs_band=0.05, rel_band=0.25) -> pd.Series:
    """Swedroejevo pravilo 5/25: dnevi, na katere bi se dejansko uravnavalo.

    Rokav s ciljem 20 % ali vec sprozi ob odmiku 5 odstotnih tock; rokav pod
    20 % ob odmiku 25 % relativno. Meja je manjsa od obeh, kar je bistvo pravila:
    majhen rokav se sme relativno bolj zaneseti, a ne neomejeno.
    """
    cols = list(w)
    R = px[cols].pct_change().fillna(0.0).to_numpy()
    tgt = np.array([w[c] for c in cols])
    prag = np.where(tgt >= 0.20, abs_band, tgt * rel_band)
    cur = tgt.copy()
    dni = np.zeros(len(px), dtype=bool)
    dni[0] = True
    for i in range(1, len(px)):
        cur = cur * (1.0 + R[i])
        cur = cur / cur.sum()
        if np.any(np.abs(cur - tgt) > prag):
            dni[i] = True
            cur = tgt.copy()
    return pd.Series(dni, index=px.index)


def _cal_days(idx, vsak: int) -> pd.Series:
    m = np.zeros(len(idx), dtype=bool)
    m[::vsak] = True
    return pd.Series(m, index=idx)


def _run_policy(px, w, mask):
    """Odigraj politiko uravnavanja: pot vrednosti, obrat, in dnevi trgovanja."""
    cols = list(w)
    R = px[cols].pct_change().fillna(0.0).to_numpy()
    tgt = np.array([w[c] for c in cols])
    cur = np.zeros(len(cols))
    v = 100.0
    pot = [v]
    obrat = 0.0
    md = mask.to_numpy()
    for i in range(len(px)):
        if i > 0:
            cur = cur * (1.0 + R[i])
            v = cur.sum() if cur.sum() > 0 else v
        if md[i]:
            nova = tgt * (cur.sum() if i > 0 else v)
            t = np.abs(nova - (cur if i > 0 else np.zeros(len(cols)))).sum()
            obrat += t / max(nova.sum(), 1e-9)
            v = (cur.sum() if i > 0 else v) - t * FEE
            cur = tgt * v
        pot.append(cur.sum())
    a = np.array(pot[1:])
    r = np.diff(np.concatenate([[100.0], a])) / np.concatenate([[100.0], a])[:-1]
    return r, obrat


def section_reb(CENE):
    print("\n\nB  URAVNAVANJE — sedem politik, pred davkom in po njem\n" + "-" * 96)
    out = {}
    for pf in ("P1", "P2"):
        w = PORTFOLIOS[pf]
        px = pd.DataFrame({k: CENE[k] for k in w}).dropna()
        idx = px.index
        ppy = len(idx) / ((idx[-1] - idx[0]).days / 365.25)
        politike = {
            "nikoli": pd.Series(np.r_[True, np.zeros(len(idx) - 1, dtype=bool)], index=idx),
            "letno": _cal_days(idx, int(round(ppy))),
            "polletno": _cal_days(idx, int(round(ppy / 2))),
            "cetrtletno": _cal_days(idx, int(round(ppy / 4))),
            "mesecno": _cal_days(idx, int(round(ppy / 12))),
            "pas 5/25 (Swedroe)": _band_days(px, w, 0.05, 0.25),
            "pas 10/50 (ohlapnejsi)": _band_days(px, w, 0.10, 0.50),
        }
        print(f"\n   {pf}  ({idx[0].date()} -> {idx[-1].date()}, {len(idx)/ppy:.1f} let)")
        print(f"      {'politika':<26} {'poslov':>7} {'letno':>8} {'Sharpe':>7} {'MaxDD':>8} "
              f"{'po davku':>9} {'davek EUR':>10}")
        out[pf] = {}
        for ime, mask in politike.items():
            r, obrat = _run_policy(px, w, mask)
            m = _met(r, idx)
            W = pd.DataFrame(np.tile([w[c] for c in w], (len(idx), 1)),
                             index=idx, columns=list(w))
            b = simulate_brokerage(W, px, SLOVENIA_2026, fee_per_side_pct=FEE * 100,
                                   rebalance_mask=mask)
            s = summarise(b)
            print(f"      {ime:<26} {int(mask.sum()):>7} {m['letno']:7.2f} % {m['sharpe']:7.2f} "
                  f"{m['maxdd']:7.1f} % {s['cagr_after_liquidation']*100:8.2f} % "
                  f"{s['tax_paid_during']:9,.0f}")
            out[pf][ime] = dict(pred_davkom=m, po_davku=s['cagr_after_liquidation'] * 100,
                                davek=s['tax_paid_during'], poslov=int(mask.sum()))
    return out


def main() -> int:
    pd.set_option("display.width", 200)
    cfg = replace(LeanConfig(), trading_days=252, bear_alloc_pct=0.0)
    CENE, BULL = {}, {}
    for k in UNIVERSE:
        d = load(k, start=UNIVERSE[k].usable_from)
        df = trim_warmup(run_strategy(d, config=cfg).df)
        CENE[k] = d["close"]
        BULL[k] = (df["signal_state"] == S_BULL).shift(1).fillna(False)

    res = {"generated": str(pd.Timestamp.utcnow()), "fee_per_trade_pct": FEE * 100,
           "mm_ter_pct": MM_TER}
    res["gotovina"] = section_cash(CENE, BULL)
    res["uravnavanje"] = section_reb(CENE)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
