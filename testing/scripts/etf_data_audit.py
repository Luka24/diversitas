"""Podatkovna revizija: kaj imamo, kaj manjka, in kateri nadomestek je uporaben.

    python testing/scripts/etf_data_audit.py

To je edino mesto, kjer se odloči, ali je nadomestna serija dovolj dobra, da se
sme prilepiti pred pravo. Odločitev je meritev, ne presoja, in se zapiše v
`testing/data/etf_proxy_quality.json`, od koder jo prebere `shared/etf_data`.

KAJ SE MERI IN ZAKAJ RAVNO TO

Za vsak par (rokav, kandidat) se na prekrivnem oknu izračuna korelacija dnevnih,
tedenskih in mesečnih donosov, sledilna napaka in razlika v CAGR. Zadnji dve sta
znani, prvi dve pa sta tisti, ki povesta, *kakšna* je napaka:

  corr_1d nizka, corr_1m visoka
      Serija je prava, poravnava dni ni. Ameriški sklad se zapre ob 22.00 po
      srednjeevropskem času, londonska vrstica ob 17.30, zato se ne strinjata,
      kateremu dnevu pripada gibanje — nesoglasje pa se čez mesec izniči.
      Uporabno mesečno, prepovedano dnevno.

  obe nizki
      Ni ista stvar. To ni napaka poravnave, ampak drugo sredstvo.

Meritev je to razliko dejansko pokazala. MSCI World gre z 0,79 dnevno na 0,98
mesečno, zlato z 0,91 na 0,98, Bloombergov blagovni indeks z 0,88 na 0,99 —
vsi so torej v redu in samo neporavnani. Ameriški agregat AGG proti evrski
zavarovani knjigi gre z 0,39 na 0,41, ameriški TIP proti evrskim indeksiranim
obveznicam z 0,16 na 0,18. Ta dva se ne popravita pri nobeni frekvenci, ker
gre za drugo valuto, drugo krivuljo in drugo inflacijo.

MERILA, DOLOČENA VNAPREJ

    zavrni    corr_1m < 0,85               drugo sredstvo
    mesecno   corr_1m >= 0,85, corr_1d < 0,90
    dnevno    corr_1d >= 0,90

Poleg tega se posebej označi `drift_pp`, razlika v CAGR. Ta ni razlog za
zavrnitev, je pa razlog za popravek: cenovni indeks brez dividend zaostaja za
skladom natanko za dividendni donos, kar se na MSCI World meri kot +2,0 točke
na leto. Prilepiti tak indeks brez popravka pomeni podceniti donos pred 2013 za
dve točki letno, sestavljeno.

Izhod:
    testing/data/etf_proxy_quality.json   ocene, ki jih bere nalagalnik
    testing/data/etf_data_audit.json      cela slika pokritosti
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.etf_data import (ETFDataError, cash_rate, fetch_yahoo, fx_series,  # noqa: E402
                             load, quality_report)
from shared.etf_universe import PORTFOLIOS, UNIVERSE, usable_start  # noqa: E402

TD = 252
OUT_Q = ROOT / "testing" / "data" / "etf_proxy_quality.json"
OUT_A = ROOT / "testing" / "data" / "etf_data_audit.json"

MIN_CORR_1M = 0.85
MIN_CORR_1D = 0.90
DRIFT_WARN_PP = 1.0


def _eur(ticker: str, ccy_hint: str) -> pd.Series:
    """Proxy price series in EUR, total return where the source provides it.

    `adjclose` matters more here than for the sleeves themselves: several of the
    longest-history candidates are distributing funds (IEAG.AS, IBGM.AS) or
    Vanguard mutual funds (VBMFX, VIPSX, VEIEX, NAESX), whose `close` is a bare
    NAV. Using it would silently drop every distribution — on a bond fund that is
    almost the entire return.
    """
    last: Exception | None = None
    for attempt in range(3):
        try:
            d = fetch_yahoo(ticker, start="1985-01-01")
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5)
    else:
        raise ETFDataError(f"{ticker}: {last}")
    px = d["adjclose"].where(d["adjclose"].notna(), d["close"]).dropna()
    rep = (d.attrs.get("currency") or ccy_hint or "USD").upper()
    if rep == "GBP" or rep == "GBp":
        raise ETFDataError(f"{ticker}: GBP/GBp line, skipped to avoid a 100x unit trap")
    if rep != "EUR":
        fx = fx_series(rep, "EUR", start="1999-01-01")
        px = (px * fx.reindex(px.index.union(fx.index)).ffill().reindex(px.index)).dropna()
    px.attrs["ccy"] = rep
    return px


def _compare(real: pd.Series, proxy: pd.Series) -> dict | None:
    idx = real.index.intersection(proxy.index)
    if len(idx) < 250:
        return None
    a, b = real.reindex(idx), proxy.reindex(idx)
    cors = {}
    for lab, rule in (("corr_1d", None), ("corr_1w", "W-FRI"), ("corr_1m", "ME")):
        ra, rb = ((a.pct_change(), b.pct_change()) if rule is None
                  else (a.resample(rule).last().pct_change(),
                        b.resample(rule).last().pct_change()))
        j = ra.dropna().index.intersection(rb.dropna().index)
        cors[lab] = float(ra[j].corr(rb[j])) if len(j) > 20 else float("nan")
    ra, rb = a.pct_change().dropna(), b.pct_change().dropna()
    j = ra.index.intersection(rb.index)
    te = float((ra[j] - rb[j]).std() * np.sqrt(TD) * 100)
    ca = float((1 + ra[j]).prod() ** (TD / len(j)) - 1)
    cb = float((1 + rb[j]).prod() ** (TD / len(j)) - 1)
    return dict(n_overlap=int(len(j)), first=str(proxy.index.min().date()),
                drift_pp=round((ca - cb) * 100, 2), te_ann_pct=round(te, 2),
                **{k: round(v, 3) for k, v in cors.items()})


def _grade(m: dict) -> str:
    if not np.isfinite(m.get("corr_1m", np.nan)) or m["corr_1m"] < MIN_CORR_1M:
        return "zavrni"
    if np.isfinite(m.get("corr_1d", np.nan)) and m["corr_1d"] >= MIN_CORR_1D:
        return "dnevno"
    return "mesecno"


def main() -> int:
    pd.set_option("display.width", 240)
    result: dict = {"generated": str(pd.Timestamp.utcnow()),
                    "thresholds": dict(min_corr_1m=MIN_CORR_1M, min_corr_1d=MIN_CORR_1D)}

    # ── 1. kaj imamo ──────────────────────────────────────────────────────────
    frames = {k: load(k, start=UNIVERSE[k].usable_from) for k in UNIVERSE}
    q = quality_report(frames)
    print("1  PRAVI PODATKI\n" + "-" * 118)
    print(q.to_string())
    result["sleeves"] = json.loads(q.reset_index().to_json(orient="records"))

    print("\n   skupno okno knjige:")
    for pf in PORTFOLIOS:
        st = usable_start(pf)
        lim = [k for k in PORTFOLIOS[pf] if UNIVERSE[k].usable_from == st]
        yrs = (pd.Timestamp.utcnow().tz_localize(None) - pd.Timestamp(st)).days / 365.25
        print(f"      {pf}  od {st}  ({yrs:.1f} let)  omejuje ga {', '.join(lim)}")

    # ── 2. obrestna mera gotovine ─────────────────────────────────────────────
    cr = cash_rate()
    print(f"\n2  GOTOVINA  vir {cr.attrs['source']}  {cr.index.min().date()} -> "
          f"{cr.index.max().date()}  ({len(cr)} opazovanj)\n" + "-" * 118)
    yearly = cr.resample("YE").mean().round(2)
    print("   povprecna letna mera: " +
          "  ".join(f"{i.year} {v:+.2f}" for i, v in yearly.tail(12).items()))
    print("   To je razlog, zakaj 0 % ni nevtralna predpostavka: razpon v vzorcu je "
          f"{cr.min():.2f} do {cr.max():.2f} %.")
    result["cash_rate"] = dict(source=cr.attrs["source"], first=str(cr.index.min().date()),
                               last=str(cr.index.max().date()), n=len(cr),
                               yearly_mean={str(i.year): float(v) for i, v in yearly.items()})

    # ── 3. nadomestki ─────────────────────────────────────────────────────────
    print("\n3  NADOMESTKI — izmerjeno prekrivanje\n" + "-" * 118)
    print(f"{'rokav':<9} {'kandidat':<20} {'od':<11} {'n':<6} {'1d':<7} {'1w':<7} "
          f"{'1m':<7} {'TE %/l':<8} {'drift pp':<9} {'ocena'}")
    grades: dict = {}
    for key, inst in UNIVERSE.items():
        real = frames[key]["close"]
        for pr in inst.proxies:
            try:
                px = _eur(pr.ticker, pr.ccy)
            except Exception as e:  # noqa: BLE001
                print(f"{key:<9} {pr.ticker:<20} NAPAKA {str(e)[:60]}")
                continue
            m = _compare(real, px)
            if m is None:
                print(f"{key:<9} {pr.ticker:<20} premalo prekrivanja")
                continue
            m["grade"] = _grade(m)
            m["note"] = pr.note
            m["ccy"] = px.attrs["ccy"]
            grades[f"{key}|{pr.ticker}"] = m
            print(f"{key:<9} {pr.ticker:<20} {m['first']:<11} {m['n_overlap']:<6} "
                  f"{m['corr_1d']:<7.3f} {m['corr_1w']:<7.3f} {m['corr_1m']:<7.3f} "
                  f"{m['te_ann_pct']:<8.2f} {m['drift_pp']:<+9.2f} {m['grade']}")
            time.sleep(0.2)
    result["proxies"] = grades

    # ── 4. koliko zgodovine kupimo ────────────────────────────────────────────
    print("\n4  KOLIKO ZGODOVINE KUPIMO\n" + "-" * 118)
    print(f"{'rokav':<9} {'pravi od':<11} {'najboljsi sprejeti':<22} {'ocena':<9} "
          f"{'seze do':<11} {'pridobimo'}")
    coverage = {}
    for key, inst in UNIVERSE.items():
        acc = [(t.split("|")[1], m) for t, m in grades.items()
               if t.startswith(key + "|") and m["grade"] != "zavrni"]
        if not acc:
            print(f"{key:<9} {inst.usable_from:<11} {'—':<22} {'—':<9} {'—':<11} "
                  f"nic, vsi kandidati zavrnjeni")
            coverage[key] = dict(best=None, reaches=inst.usable_from, gain_years=0.0)
            continue
        best_t, best_m = min(acc, key=lambda x: x[1]["first"])
        gain = (pd.Timestamp(inst.usable_from) - pd.Timestamp(best_m["first"])).days / 365.25
        print(f"{key:<9} {inst.usable_from:<11} {best_t:<22} {best_m['grade']:<9} "
              f"{best_m['first']:<11} +{gain:.1f} let"
              + (f"   (drift {best_m['drift_pp']:+.2f} pp — potreben popravek)"
                 if abs(best_m["drift_pp"]) > DRIFT_WARN_PP else ""))
        coverage[key] = dict(best=best_t, grade=best_m["grade"], reaches=best_m["first"],
                             gain_years=round(gain, 1), drift_pp=best_m["drift_pp"])
    result["coverage"] = coverage

    print("\n   knjiga z nadomestki:")
    for pf in PORTFOLIOS:
        reach = max(coverage[k]["reaches"] for k in PORTFOLIOS[pf])
        lim = [k for k in PORTFOLIOS[pf] if coverage[k]["reaches"] == reach]
        yrs = (pd.Timestamp.utcnow().tz_localize(None) - pd.Timestamp(reach)).days / 365.25
        print(f"      {pf}  od {reach}  ({yrs:.1f} let)  omejuje ga {', '.join(lim)}")

    # ── 5. kaj ostane luknja ──────────────────────────────────────────────────
    print("\n5  KAR OSTANE LUKNJA\n" + "-" * 118)
    holes = []
    for key, inst in UNIVERSE.items():
        rejected = [t.split("|")[1] for t, m in grades.items()
                    if t.startswith(key + "|") and m["grade"] == "zavrni"]
        c = coverage[key]
        if c["best"] is None:
            holes.append(f"{key}: brez uporabnega nadomestka. Zavrnjeni: {', '.join(rejected)}. "
                         f"Zgodovina ostane {inst.usable_from}.")
        elif c["grade"] == "mesecno":
            holes.append(f"{key}: nadomestek {c['best']} je uporaben samo mesecno "
                         f"(dnevna poravnava je pokvarjena). Dnevni testi ostanejo "
                         f"omejeni na {inst.usable_from}.")
        if abs(c.get("drift_pp", 0.0)) > DRIFT_WARN_PP:
            holes.append(f"{key}: {c['best']} zaostaja za {c['drift_pp']:+.2f} pp na leto — "
                         f"brez popravka je spojena serija pristranska.")
    for h in holes:
        print("   - " + h)
    result["gaps"] = holes

    OUT_Q.parent.mkdir(parents=True, exist_ok=True)
    OUT_Q.write_text(json.dumps({"generated": result["generated"],
                                 "thresholds": result["thresholds"],
                                 "proxies": grades}, indent=2), encoding="utf-8")
    OUT_A.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT_Q.relative_to(ROOT)}  in  {OUT_A.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
