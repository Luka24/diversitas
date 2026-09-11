"""Davek, izračunan na isti poti kot donos.

    python testing/scripts/etf_davek.py

Trije deli:
  1  primernost osmih skladov za INR, po ZINR in pojasnilih Ministrstva za finance
  2  donos pred davkom, po davku in po unovčenju, za vsakega kandidata
  3  kaj to spremeni pri odločitvi

Metodologija je ameriški standard SEC: troje številk na isti strani — pred
obdavčitvijo, po obdavčitvi pred unovčenjem in po obdavčitvi z unovčenjem — ter
`tax cost ratio` po Morningstarju, torej koliko odstotnih točk letnega donosa
pojé davek. Simulacija je na ravni svežnjev s FIFO, ker je stopnja funkcija
datuma nakupa in nabavne cene, in tega iz serije donosov ni mogoče izpeljati.

Izhod: testing/data/etf_davek.json
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

from shared.etf_data import load_panel                                  # noqa: E402
from shared.etf_universe import PORTFOLIOS, UNIVERSE                    # noqa: E402
from shared.tax import (INR_2026, NO_TAX, SLOVENIA_2026,                # noqa: E402
                        simulate_brokerage, simulate_inr, summarise)

from diversitas.config import DEFAULT_CONFIG                            # noqa: E402
from diversitas.rotation import (_drifted, _hold_between_rebalances,    # noqa: E402
                                 overlay_book, rotate_within, sleeve_positions)

OUT = ROOT / "testing" / "data" / "etf_davek.json"
TD = 252

# ── 1. primernost za INR ──────────────────────────────────────────────────────
# Presoja po ZINR, 7. člen, in pojasnilih MF (posodobljena 14. 5. 2026):
# ETF in KNPVP morajo po svoji naložbeni politiki vlagati v finančne instrumente
# izdajateljev s sedežem v EU, EGP ali OECD; ponudnik preveri tudi dejansko
# sestavo portfelja. To je presoja ponudnika, ne naša — spodnje je razlog, ki mu
# ga je treba predložiti, ne odgovor.
INR_PRESOJA = {
    "World":    ("verjetno sporno",
                 "MSCI World vsebuje Hongkong in Singapur, ki nista clanici OECD. "
                 "Utez je majhna (pod 2 %), a pogoj v zakonu ni izrazen kot prag."),
    "EM":       ("skoraj gotovo neprimeren",
                 "MSCI EM IMI je pretezno zunaj OECD (Kitajska, Indija, Tajvan, Brazilija). "
                 "Pojasnilo MF navaja prav sklad, ki vlaga pretezno v kitajska podjetja, kot primer neprimernega."),
    "SmallCap": ("verjetno sporno",
                 "Ista tezava kot World: MSCI World Small Cap vkljucuje Hongkong in Singapur."),
    "Quality":  ("verjetno sporno",
                 "Ista tezava kot World, izbor iz istega univerzuma."),
    "GlobAgg":  ("verjetno neprimeren",
                 "Bloomberg Global Aggregate vsebuje kitajske drzavne obveznice in druge izdajatelje zunaj OECD."),
    "InflLink": ("primeren",
                 "Evrske drzavne inflacijsko vezane obveznice; vsi izdajatelji so clanice EU."),
    "Gold":     ("verjetno neprimeren",
                 "IE00B4ND3602 je ETC, torej dolznisi vrednostni papir, in ne ETF ali KNPVP. "
                 "Seznam primernih instrumentov v pojasnilih MF nasteva delnice, obveznice, zakladne menice, ETF in KNPVP."),
    "Commod":   ("verjetno neprimeren",
                 "UCITS ETF, a izpostavljenost je prek zamenjav na blagovni indeks, ne prek izdajateljev iz OECD."),
}


def _books():
    out = {}
    for name, w in PORTFOLIOS.items():
        _, frames = load_panel(name)
        px = pd.DataFrame({k: frames[k]["close"] for k in w}).dropna()
        out[name] = (w, frames, px)
    return out


def _weight_paths(name, w, frames, px, cfg):
    """Ciljne uteži za vsakega kandidata, na skupnem indeksu."""
    idx = px.index
    paths = {}

    def mask(every: int) -> pd.Series:
        m = np.zeros(len(idx), dtype=bool)
        m[::every] = True
        return pd.Series(m, index=idx)

    tgt = pd.DataFrame(np.tile([w[k] for k in w], (len(idx), 1)),
                       index=idx, columns=list(w))
    paths["kupi in drzi (letno)"] = (tgt, mask(252))
    paths["kupi in drzi (cetrtletno)"] = (tgt, mask(63))
    paths["kupi in drzi (nikoli)"] = (tgt, pd.Series(False, index=idx))

    pos, _ = sleeve_positions(frames, cfg)
    keys = [k for k in w if k in pos.columns]
    ov = pos[keys].reindex(idx).fillna(0.0).mul(pd.Series({k: w[k] for k in keys}), axis=1)
    paths["trendni sloj (mesecno)"] = (_hold_between_rebalances(ov, 21), mask(21))

    rw = rotate_within(frames, cfg, k=max(2, len(w) // 2), rebalance_every=21)
    paths["rotacija top-k (mesecno)"] = (rw.weights.reindex(idx).fillna(0.0), mask(21))
    return paths


def main() -> int:
    pd.set_option("display.width", 200)
    res = {"generated": str(pd.Timestamp.utcnow()),
           "fee_per_side_pct": DEFAULT_CONFIG.fee_per_side_pct,
           "brokerage": {"brackets": SLOVENIA_2026.brackets, "as_of": SLOVENIA_2026.as_of},
           "inr": {"rate": INR_2026.rate_on_withdrawal, "tax_free_years": INR_2026.tax_free_years,
                   "annual_limit": INR_2026.annual_limit,
                   "lifetime_limit": INR_2026.lifetime_limit, "as_of": INR_2026.as_of}}

    print("1  PRIMERNOST ZA INR  (ZINR 7. clen + pojasnila MF, 14. 5. 2026)\n" + "-" * 100)
    print(f"{'rokav':<9} {'ISIN':<14} {'presoja':<28} razlog")
    for k, (verdict, why) in INR_PRESOJA.items():
        print(f"{k:<9} {UNIVERSE[k].isin:<14} {verdict:<28} {why[:70]}")
    ok = [k for k, (v, _) in INR_PRESOJA.items() if v == "primeren"]
    print(f"\n   nedvoumno primernih: {len(ok)} od 8  ({', '.join(ok)})")
    print("   -> nobene od obeh knjig, kot sta zapisani, ni mogoce v celoti drzati na INR.")
    res["inr_eligibility"] = {k: dict(verdict=v, reason=r) for k, (v, r) in INR_PRESOJA.items()}

    print("\n2  DONOS PRED DAVKOM, PO DAVKU IN PO UNOVCENJU\n" + "-" * 100)
    cfg = DEFAULT_CONFIG
    books = _books()
    rows = []
    for name, (w, frames, px) in books.items():
        paths = _weight_paths(name, w, frames, px, cfg)
        print(f"\n   {name}  ({px.index.min().date()} -> {px.index.max().date()}, "
              f"{round(len(px)/TD,1)} let)")
        print(f"      {'kandidat':<26} {'pred davkom':>12} {'po davku':>10} "
              f"{'po unovcenju':>13} {'zaostanek pp':>13} {'placan davek':>13}")
        for label, (W, msk) in paths.items():
            b = simulate_brokerage(W, px, SLOVENIA_2026, rebalance_mask=msk,
                                   fee_per_side_pct=cfg.fee_per_side_pct)
            sb = summarise(b)
            i = simulate_inr(W, px, INR_2026, rebalance_mask=msk,
                             fee_per_side_pct=cfg.fee_per_side_pct)
            si = summarise(i)
            print(f"      {label:<26} {sb['cagr_pre_tax']*100:>11.2f}% "
                  f"{sb['cagr_after_tax']*100:>9.2f}% {sb['cagr_after_liquidation']*100:>12.2f}% "
                  f"{sb['tax_cost_ratio_pp']:>12.2f} {sb['tax_paid_during']:>12,.0f}")
            rows.append({**sb, "book": name, "candidate": label, "account": "navaden racun"})
            rows.append({**si, "book": name, "candidate": label, "account": "INR"})
        print(f"      {'-- isto na INR --':<26}")
        for label, (W, msk) in paths.items():
            i = simulate_inr(W, px, INR_2026, rebalance_mask=msk,
                             fee_per_side_pct=cfg.fee_per_side_pct)
            si = summarise(i)
            print(f"      {label:<26} {si['cagr_pre_tax']*100:>11.2f}% "
                  f"{'—':>10} {si['cagr_after_liquidation']*100:>12.2f}% "
                  f"{si['tax_cost_ratio_pp']:>12.2f}   {si['note']}")
    res["rows"] = rows

    print("\n3  KAJ TO SPREMENI\n" + "-" * 100)
    df = pd.DataFrame([r for r in rows if r["account"] == "navaden racun"])
    for name in books:
        sub = df[df["book"] == name].set_index("candidate")
        bh = sub.loc["kupi in drzi (letno)"]
        tr = sub.loc["trendni sloj (mesecno)"]
        print(f"   {name}: zaostanek kupi in drzi {bh['tax_cost_ratio_pp']:.2f} pp, "
              f"trendni sloj {tr['tax_cost_ratio_pp']:.2f} pp  -> "
              f"davcna razlika {tr['tax_cost_ratio_pp'] - bh['tax_cost_ratio_pp']:+.2f} pp na leto")
    print("\n   Opozorilo o obzorju: simulacija tece cez razpolozljivo okno (pod 9 let), zato "
          "\n   nobena strategija ne dosezhe niti 10-letnega praga, kaj sele 15-letnega. Prav ta "
          "\n   prag je najvecja prednost kupi in drzi in ga to okno ne more pokazati.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
