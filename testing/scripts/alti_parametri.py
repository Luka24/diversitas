"""Ali si altcoini zasluzijo svoje parametre?

    python testing/scripts/alti_parametri.py

VPRASANJE
Trenutno vsa sredstva uporabljajo iste parametre kot BTC. Se splaca vsakemu
nastaviti svoje? Vprasanje je merljivo in odgovor ni stvar okusa.

KAJ PRAVI STROKA
Carver (`Systematic Trading`) je izrecen: podatke je treba ZDRUZITI cez
instrumente in loceno nastavljati samo tam, kjer se statisticno znacilno
razlikujejo. Prilagajanje vsakemu instrumentu posebej je najhitrejsa pot v
prilagajanje preteklosti, ker se stevilo prostih parametrov pomnozi s stevilom
sredstev, kolicina podatkov pa ne.

Kar stroka DA prilagaja po sredstvu, ni signal, ampak VELIKOST POZICIJE --
skaliranje po volatilnosti, tako da vsako sredstvo prispeva podoben delez
tveganja. To je standard pri CTA-jih in Man Group ga opisuje kot
`volatility normalisation`.

ZATO SE TESTIRA TO
  A  skupni privzetki                    -- nic nastavljenega, izhodisce
  B  parametri po sredstvu               -- nastavljeni na oknu zasnove
  C  skupni parametri, zdruzeni podatki  -- en nabor za vsa sredstva
  D  po skupinah (BTC/ETH proti ostalim) -- vmesna moznost
  E  privzetki + skaliranje po vol.      -- Carverjev odgovor
  F  privzetki + BTC filter za alte      -- strukturno, ne nastavljeno
  G  privzetki + prilagodljiv pas        -- sirina po volatilnosti, isto povprecje

MERI SE NA HOLD-OUTU. B bo na oknu zasnove zmagal po definiciji -- vprasanje
je, ali zmaga tudi tam, kjer ni gledal.

Provizija 0,30 % na stran. Izhod: testing/data/alti_parametri.json
"""
from __future__ import annotations

import itertools
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

from shared.data_source import fetch_candles                    # noqa: E402
from testing.scripts.preveri_pine import (                      # noqa: E402
    avtomat_po_pine, pine_privzetki, po_pine, pozicija_po_pine)

OUT = ROOT / "testing" / "data" / "alti_parametri.json"
FEE = 0.30
PPY = 365
MEJA = "2023-09-08"          # zasnova do te meje, hold-out po njej

VIRI = {"BTC": "coinbase", "ETH": "coinbase", "SOL": "coinbase",
        "LINK": "coinbase", "XRP": "yahoo", "BNB": "yahoo"}
MAJORS = ("BTC", "ETH")

MREZA = dict(trackPeriod=[50, 75, 100], trackBuf=[2.0, 3.0, 5.0],
             donchianPeriod=[15, 20, 30], confirmBars=[2, 3, 4],
             reentryHold=[10, 15, 20])


def met(r: np.ndarray) -> dict:
    r = np.asarray(r, float)
    if len(r) < 30:
        return dict(cagr=np.nan, sortino=np.nan, maxdd=np.nan, mult=np.nan)
    eq = np.cumprod(1.0 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return dict(cagr=(eq[-1] ** (PPY / len(r)) - 1.0) * 100,
                sortino=float(r.mean() * PPY / dn) if dn > 0 else np.nan,
                maxdd=dd.min() * 100, mult=float(eq[-1]))


class Sredstvo:
    """Cene enega sredstva plus predpomnilnik znacilk po (tp, tb, dp)."""

    def __init__(self, sym: str, px: pd.DataFrame):
        self.sym, self.px = sym, px
        self.ret = px["close"].pct_change().fillna(0.0).to_numpy(float)
        lr = np.log(px["close"] / px["close"].shift(1))
        self.vol = (lr.rolling(20, min_periods=20).std(ddof=0)
                    * np.sqrt(PPY) * 100).to_numpy(float)
        self._f: dict = {}
        idx = px.index
        self.m_zas = np.asarray(idx <= MEJA) & (np.arange(len(idx)) >= 220)
        self.m_hol = np.asarray(idx > MEJA)

    def znacilke(self, p: dict):
        k = (p["trackPeriod"], p["trackBuf"], p["donchianPeriod"],
             p["useDonchian"])
        if k not in self._f:
            self._f[k] = po_pine(self.px, p)
        return self._f[k]

    def odigraj(self, p: dict, sizing=None, filter_ok=None, band=None):
        f = self.znacilke(p)
        if filter_ok is not None:
            f = f.copy()
            f["bullCondition"] = f["bullCondition"] & filter_ok
        sig = avtomat_po_pine(f, p)["signalState"].to_numpy()
        held, traded = pozicija_po_pine(self.px, sig, p)
        if sizing is not None:
            skala = np.nan_to_num(sizing, nan=1.0)
            held = held * skala
            traded = np.abs(np.diff(np.concatenate([[0.0], held])))
        return held * self.ret - traded * FEE / 100.0, sig


def kombinacije():
    kljuci = list(MREZA)
    for vals in itertools.product(*(MREZA[k] for k in kljuci)):
        yield dict(zip(kljuci, vals))


def main() -> int:
    p0 = pine_privzetki()
    print(f"provizija {FEE} % na stran   zasnova do {MEJA}, hold-out po njej\n")

    S = {}
    for sym, vir in VIRI.items():
        try:
            px = fetch_candles(sym, "1d", bars=3000, prefer=vir)
        except Exception as e:                                    # noqa: BLE001
            print(f"   {sym}: vira ni ({type(e).__name__}), izpuscam")
            continue
        S[sym] = Sredstvo(sym, px)
        n_z, n_h = int(S[sym].m_zas.sum()), int(S[sym].m_hol.sum())
        print(f"   {sym:<5}{px.index[0].date()} -> {px.index[-1].date()}   "
              f"zasnova {n_z:>5} barov   hold-out {n_h:>5}")
    print()

    # ── A: skupni privzetki ──────────────────────────────────────────────────
    A = {}
    for sym, s in S.items():
        r, _ = s.odigraj(p0)
        A[sym] = dict(zasnova=met(r[s.m_zas]), holdout=met(r[s.m_hol]))

    # ── mreza: vsak nabor na vsakem sredstvu ────────────────────────────────
    komb = list(kombinacije())
    print(f"preizkusam {len(komb)} naborov parametrov na {len(S)} sredstvih "
          f"({len(komb) * len(S)} zagonov) ...")
    sortino_z = {sym: np.full(len(komb), np.nan) for sym in S}
    sortino_h = {sym: np.full(len(komb), np.nan) for sym in S}
    for i, sprem in enumerate(komb):
        p = dict(p0)
        p.update(sprem)
        for sym, s in S.items():
            r, _ = s.odigraj(p)
            sortino_z[sym][i] = met(r[s.m_zas])["sortino"]
            sortino_h[sym][i] = met(r[s.m_hol])["sortino"]
    print("   koncano\n")

    # ── B: najboljsi po sredstvu (izbran na zasnovi) ────────────────────────
    B = {}
    for sym in S:
        i = int(np.nanargmax(sortino_z[sym]))
        B[sym] = dict(params=komb[i], zasnova=float(sortino_z[sym][i]),
                      holdout=float(sortino_h[sym][i]))

    # ── C: en skupen nabor, izbran na zdruzenih podatkih ────────────────────
    povp_z = np.nanmean(np.vstack([sortino_z[s] for s in S]), axis=0)
    i_c = int(np.nanargmax(povp_z))
    C = dict(params=komb[i_c],
             holdout={sym: float(sortino_h[sym][i_c]) for sym in S})

    # ── D: po skupinah ──────────────────────────────────────────────────────
    D = {}
    for ime, skupina in (("majors", [s for s in S if s in MAJORS]),
                         ("alti", [s for s in S if s not in MAJORS])):
        if not skupina:
            continue
        pv = np.nanmean(np.vstack([sortino_z[s] for s in skupina]), axis=0)
        j = int(np.nanargmax(pv))
        D[ime] = dict(params=komb[j],
                      holdout={sym: float(sortino_h[sym][j]) for sym in skupina})

    # ── E, F, G: strukturne ideje na privzetkih ─────────────────────────────
    btc = S.get("BTC")
    btc_ok = None
    if btc is not None:
        ema = btc.px["close"].ewm(span=50, adjust=False).mean()
        btc_ok = (btc.px["close"] > ema)

    E, F, G = {}, {}, {}
    for sym, s in S.items():
        # E: skaliranje po volatilnosti, cilj 50 % letno, brez vzvoda
        skala = np.minimum(1.0, 50.0 / s.vol)
        r, _ = s.odigraj(p0, sizing=skala)
        E[sym] = dict(holdout=met(r[s.m_hol]), zasnova=met(r[s.m_zas]))
        # F: BTC filter za alte
        if sym not in MAJORS and btc_ok is not None:
            fo = btc_ok.reindex(s.px.index).ffill().fillna(False)
            r, _ = s.odigraj(p0, filter_ok=fo.to_numpy())
            F[sym] = dict(holdout=met(r[s.m_hol]), zasnova=met(r[s.m_zas]))
        # G: prilagodljiv pas -- ista povprecna sirina, drugacna oblika
        med = np.nanmedian(s.vol)
        sirine = p0["trackBuf"] * s.vol / med
        pg = dict(p0)
        # priblizek: uporabi mediansko sirino v pasovih po kvartilih volatilnosti
        r_g = np.zeros(len(s.ret))
        for lo, hi, mult in ((0, 33, 0.7), (33, 66, 1.0), (66, 100, 1.4)):
            spodaj, zgoraj = np.nanpercentile(s.vol, [lo, hi])
            pg["trackBuf"] = float(p0["trackBuf"] * mult)
            rr, _ = s.odigraj(pg)
            maska = (s.vol >= spodaj) & (s.vol <= zgoraj if hi == 100
                                          else s.vol < zgoraj)
            r_g[maska] = rr[maska]
        G[sym] = dict(holdout=met(r_g[s.m_hol]), zasnova=met(r_g[s.m_zas]))

    # ── izpis ────────────────────────────────────────────────────────────────
    print("=" * 96)
    print("GLAVNI TEST: ali parametri po sredstvu zdrzijo izven okna zasnove")
    print("=" * 96)
    print(f"{'sredstvo':<8}{'A skupni':>10}{'B po sredstvu':>15}"
          f"{'C zdruzeni':>13}{'D skupine':>12}   izbrani parametri (B)")
    d_map = {}
    for ime, d in D.items():
        for sym in d["holdout"]:
            d_map[sym] = d["holdout"][sym]
    for sym in S:
        a = A[sym]["holdout"]["sortino"]
        b = B[sym]["holdout"]
        c = C["holdout"][sym]
        dd = d_map.get(sym, np.nan)
        pb = B[sym]["params"]
        print(f"{sym:<8}{a:>10.2f}{b:>15.2f}{c:>13.2f}{dd:>12.2f}   "
              f"tp{pb['trackPeriod']} buf{pb['trackBuf']:g} dc{pb['donchianPeriod']} "
              f"conf{pb['confirmBars']} hold{pb['reentryHold']}")
    povp = lambda f: np.nanmean([f(s) for s in S])
    print("-" * 96)
    print(f"{'POVPRECJE':<8}{povp(lambda s: A[s]['holdout']['sortino']):>10.2f}"
          f"{povp(lambda s: B[s]['holdout']):>15.2f}"
          f"{povp(lambda s: C['holdout'][s]):>13.2f}"
          f"{povp(lambda s: d_map.get(s, np.nan)):>12.2f}")
    print(f"{'na zasnovi':<8}{povp(lambda s: A[s]['zasnova']['sortino']):>10.2f}"
          f"{povp(lambda s: B[s]['zasnova']):>15.2f}")
    print(f"\nC (en nabor za vsa): tp{C['params']['trackPeriod']} "
          f"buf{C['params']['trackBuf']:g} dc{C['params']['donchianPeriod']} "
          f"conf{C['params']['confirmBars']} hold{C['params']['reentryHold']}")
    for ime, d in D.items():
        q = d["params"]
        print(f"D {ime:<8}: tp{q['trackPeriod']} buf{q['trackBuf']:g} "
              f"dc{q['donchianPeriod']} conf{q['confirmBars']} hold{q['reentryHold']}")

    print("\n" + "=" * 96)
    print("STRUKTURNE IDEJE (nic nastavljenega), Sortino na hold-outu")
    print("=" * 96)
    print(f"{'sredstvo':<8}{'A privzetki':>13}{'E vol. skala':>14}"
          f"{'F BTC filter':>14}{'G prilag. pas':>15}")
    for sym in S:
        a = A[sym]["holdout"]["sortino"]
        e = E[sym]["holdout"]["sortino"]
        f_ = F.get(sym, {}).get("holdout", {}).get("sortino", np.nan)
        g = G[sym]["holdout"]["sortino"]
        print(f"{sym:<8}{a:>13.2f}{e:>14.2f}"
              + (f"{f_:>14.2f}" if np.isfinite(f_) else f"{'-':>14}")
              + f"{g:>15.2f}")
    print("-" * 96)
    print(f"{'POVPRECJE':<8}{povp(lambda s: A[s]['holdout']['sortino']):>13.2f}"
          f"{povp(lambda s: E[s]['holdout']['sortino']):>14.2f}"
          f"{np.nanmean([F[s]['holdout']['sortino'] for s in F]):>14.2f}"
          f"{povp(lambda s: G[s]['holdout']['sortino']):>15.2f}")

    res = dict(generated=str(pd.Timestamp.utcnow()), fee=FEE, meja=MEJA,
               n_kombinacij=len(komb), A=A, B=B, C=C, D=D,
               E={k: v for k, v in E.items()}, F=F, G=G)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
