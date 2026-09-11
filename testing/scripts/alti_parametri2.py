"""Ali si altcoini zasluzijo svoje parametre -- postena razlicica.

    python testing/scripts/alti_parametri2.py

ZAKAJ SE ENKRAT
Prvi test (`alti_parametri.py`) je imel sest pomanjkljivosti, zaradi katerih je
bil odgovor lazje negativen, kot bi smel biti:

  1  SLAMNATI MOZ. Za `prilagajanje po sredstvu` je vzel argmax po mrezi --
     najbolj naivno metodo. Carver priporoca plato in krcenje proti skupni
     vrednosti, ne vrha. Primerjal je torej najslabso obliko prilagajanja.
  2  EN SAM REZ. Ena meja med zasnovo in hold-outom je en zreb, ne dokaz.
  3  NAPACNA MERA. Meril je povprecje Sortinov PO SREDSTVIH. Trguje se knjiga;
     steje njen Sortino in njen padec.
  4  BREZ TESTA ZNACILNOSTI. Razlika 1,41 proti 1,05 je bila predstavljena kot
     ugotovitev, ne da bi kdo preveril, ali je locljiva od suma.
  5  DROBEC PODATKOV. SOL je imel 594 barov zasnove. To meri, da je
     prilagajanje na drobcu slabo, ne da je prilagajanje po sredstvu slabo.
  6  IZHODISCE NI NEPRILAGOJENO. Privzetki so bili izbrani NA BTC. Primerjava
     je bila `dolgo prilagajanje na BTC` proti `kratko prilagajanje po
     sredstvu`, ne prilagajanje proti neprilagajanju.

KAJ JE TU DRUGACE

  * DRSECE OKNO namesto enega reza. Vsakih 180 dni se parametri izberejo na
    VSEH podatkih do tistega dne in uporabijo naslednjih 180 dni. Izven-vzorcni
    donosi se zlepijo v eno serijo. Vsako sredstvo tako prispeva vec neodvisnih
    odlocitev, ne ene.
  * POSTENE METODE IZBIRE. Poleg vrha se preizkusi PLATO (povprecje sosedov v
    prostoru parametrov) in KRCENJE proti skupni izbiri -- torej tisto, kar
    stroka dejansko pocne.
  * KNJIGA. Vse se meri tudi na enako utezeni knjigi sestih sredstev, ker je to
    tisto, kar se trguje.
  * ZNACILNOST. Razlika proti izhodiscu dobi interval zaupanja iz stacionarnega
    bootstrapa po blokih.
  * MINIMUM PODATKOV. Sredstvo se v drsecem oknu upostevata sele, ko ima vsaj
    `MIN_ZASNOVA` barov zgodovine.
  * IZHODISCE JE OZNACENO KOT PRILAGOJENO. Privzetki so nastali na BTC; to je
    tudi razlog, da se poleg njih poroca NAKLJUCNA izbira iz mreze -- kot
    merilo, koliko od `A` je res vescina in koliko lastnost mreze.

Provizija 0,30 % na stran. Izhod: testing/data/alti_parametri2.json
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

OUT = ROOT / "testing" / "data" / "alti_parametri2.json"
FEE = 0.30
PPY = 365
KORAK = 180              # dolzina izven-vzorcnega odseka
MIN_ZASNOVA = 500        # manj kot toliko barov -> sredstvo se ne prilagaja
SEME = 7

VIRI = {"BTC": "coinbase", "ETH": "coinbase", "SOL": "coinbase",
        "LINK": "coinbase", "XRP": "yahoo", "BNB": "yahoo"}

MREZA = dict(trackPeriod=[50, 75, 100], trackBuf=[2.0, 3.0, 5.0],
             donchianPeriod=[15, 20, 30], confirmBars=[2, 3, 4],
             reentryHold=[10, 15, 20])


def sortino(r: np.ndarray) -> float:
    r = np.asarray(r, float)
    if len(r) < 30:
        return np.nan
    dn = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)) * np.sqrt(PPY)
    return float(r.mean() * PPY / dn) if dn > 0 else np.nan


def panel(r: np.ndarray) -> dict:
    r = np.asarray(r, float)
    eq = np.cumprod(1.0 + r)
    dd = eq / np.maximum.accumulate(eq) - 1.0
    v = r.std() * np.sqrt(PPY)
    return dict(cagr=(eq[-1] ** (PPY / len(r)) - 1.0) * 100,
                sharpe=float(r.mean() * PPY / v) if v > 0 else np.nan,
                sortino=sortino(r), maxdd=dd.min() * 100, mult=float(eq[-1]))


def kombinacije():
    k = list(MREZA)
    return [dict(zip(k, v)) for v in itertools.product(*(MREZA[x] for x in k))]


KOMB = kombinacije()
_KLJUCI = list(MREZA)
_P = np.array([[float(c[k]) for k in _KLJUCI] for c in KOMB])
_LO = _P.min(axis=0)
_SPAN = np.where(_P.max(axis=0) - _LO > 0, _P.max(axis=0) - _LO, 1.0)
_PN = (_P - _LO) / _SPAN
_D = np.sqrt(((_PN[:, None, :] - _PN[None, :, :]) ** 2).sum(axis=2))
_SOSEDJE = np.argsort(_D, axis=1)[:, :5]        # vkljucno s sabo


def izbira_vrh(s: np.ndarray) -> int:
    return int(np.nanargmax(s))


def izbira_plato(s: np.ndarray) -> int:
    """Sredina platoja: povprecje petih najblizjih sosedov v prostoru
    parametrov. Nastavitev, ki je dobra samo zato, ker so njeni sosedje slabi,
    tako odpade -- in prav to je podpis prilagajanja sumu."""
    pl = np.nanmean(s[_SOSEDJE], axis=1)
    return int(np.nanargmax(pl))


def izbira_krcena(s_svoj: np.ndarray, s_skupni: np.ndarray,
                  lam: float = 0.5) -> int:
    """Krcenje proti skupni izbiri. Ocena sredstva se utezi z `lam`, skupna z
    ostankom -- Carverjev nasvet, da se loceno nastavlja le tam, kjer se
    sredstvo res razlikuje, v najpreprostejsi obliki."""
    z = lambda x: (x - np.nanmean(x)) / (np.nanstd(x) + 1e-12)
    mesano = lam * z(s_svoj) + (1.0 - lam) * z(s_skupni)
    pl = np.nanmean(mesano[_SOSEDJE], axis=1)
    return int(np.nanargmax(pl))


def blok_bootstrap(d: np.ndarray, n_boot=2000, blok=20, seme=SEME):
    """Stacionarni bootstrap razlike dveh dnevnih serij."""
    rng = np.random.default_rng(seme)
    n = len(d)
    out = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.empty(n, dtype=np.int64)
        i = 0
        while i < n:
            zac = rng.integers(0, n)
            dolz = min(rng.geometric(1.0 / blok), n - i)
            idx[i:i + dolz] = (zac + np.arange(dolz)) % n
            i += dolz
        out[b] = sortino(d[idx])
    return out


def main() -> int:
    p0 = pine_privzetki()
    print(f"provizija {FEE} % na stran   drsece okno {KORAK} dni   "
          f"{len(KOMB)} naborov\n")

    # ── podatki in polna serija donosov za vsak nabor ────────────────────────
    px_all, R = {}, {}
    for sym, vir in VIRI.items():
        try:
            px = fetch_candles(sym, "1d", bars=3000, prefer=vir)
        except Exception as e:                                    # noqa: BLE001
            print(f"   {sym}: vira ni ({type(e).__name__})")
            continue
        px_all[sym] = px
        print(f"   {sym:<5}{px.index[0].date()} -> {px.index[-1].date()}  "
              f"{len(px):>5} barov", flush=True)
    print("\n   racunam mrezo ...", flush=True)
    for sym, px in px_all.items():
        ret = px["close"].pct_change().fillna(0.0).to_numpy(float)
        M = np.empty((len(KOMB), len(px)))
        cache: dict = {}
        for i, c in enumerate(KOMB):
            p = dict(p0)
            p.update(c)
            k = (p["trackPeriod"], p["trackBuf"], p["donchianPeriod"])
            if k not in cache:
                cache[k] = po_pine(px, p)
            sig = avtomat_po_pine(cache[k], p)["signalState"].to_numpy()
            held, traded = pozicija_po_pine(px, sig, p)
            M[i] = held * ret - traded * FEE / 100.0
        R[sym] = M
        print(f"      {sym} koncan", flush=True)

    # indeks privzetkov v mrezi (ce je v njej)
    i_priv = next((i for i, c in enumerate(KOMB)
                   if all(abs(float(c[k]) - float(p0[k])) < 1e-9 for k in _KLJUCI)),
                  None)
    print(f"\n   privzetki so v mrezi: {'da' if i_priv is not None else 'NE'}")

    # ── drsece okno ─────────────────────────────────────────────────────────
    simboli = list(R)
    dolzine = {s: len(px_all[s]) for s in simboli}
    skupni_idx = px_all["BTC"].index
    metode = ["A privzetki", "B vrh", "B plato", "B krcen",
              "C skupni vrh", "C skupni plato", "N nakljucen"]
    oos = {m: {s: [] for s in simboli} for m in metode}
    oos_idx = {s: [] for s in simboli}
    rng = np.random.default_rng(SEME)
    n_odlocitev = 0

    for sym in simboli:
        n = dolzine[sym]
        zac = MIN_ZASNOVA
        while zac + KORAK <= n:
            kon = zac + KORAK
            # ocene na VSEH podatkih do `zac` (za vsa sredstva, za skupno izbiro)
            s_svoj = np.array([sortino(R[sym][i][:zac]) for i in range(len(KOMB))])
            skupni = []
            for o in simboli:
                m = min(zac, dolzine[o])
                if m >= MIN_ZASNOVA:
                    skupni.append([sortino(R[o][i][:m]) for i in range(len(KOMB))])
            s_skup = np.nanmean(np.array(skupni), axis=0)

            izb = {"B vrh": izbira_vrh(s_svoj),
                   "B plato": izbira_plato(s_svoj),
                   "B krcen": izbira_krcena(s_svoj, s_skup),
                   "C skupni vrh": izbira_vrh(s_skup),
                   "C skupni plato": izbira_plato(s_skup),
                   "N nakljucen": int(rng.integers(0, len(KOMB)))}
            if i_priv is not None:
                izb["A privzetki"] = i_priv
            for m, i in izb.items():
                oos[m][sym].append(R[sym][i][zac:kon])
            oos_idx[sym].append(px_all[sym].index[zac:kon])
            n_odlocitev += 1
            zac = kon

    if i_priv is None:      # privzetki niso v mrezi -> odigraj jih posebej
        for sym in simboli:
            px = px_all[sym]
            ret = px["close"].pct_change().fillna(0.0).to_numpy(float)
            f = po_pine(px, p0)
            sig = avtomat_po_pine(f, p0)["signalState"].to_numpy()
            held, traded = pozicija_po_pine(px, sig, p0)
            r = held * ret - traded * FEE / 100.0
            zac, kosi = MIN_ZASNOVA, []
            while zac + KORAK <= dolzine[sym]:
                kosi.append(r[zac:zac + KORAK])
                zac += KORAK
            oos["A privzetki"][sym] = kosi

    print(f"   izven-vzorcnih odlocitev: {n_odlocitev} "
          f"({n_odlocitev // max(len(simboli), 1)} na sredstvo)\n")

    # ── zlepi in izmeri ─────────────────────────────────────────────────────
    ser = {m: {s: np.concatenate(oos[m][s]) for s in simboli if oos[m][s]}
           for m in metode}
    print("=" * 100)
    print("IZVEN VZORCA, SORTINO PO SREDSTVIH  (drsece okno, vse odlocitve zlepljene)")
    print("=" * 100)
    print(f"{'sredstvo':<8}" + "".join(f"{m:>16}" for m in metode))
    for s in simboli:
        print(f"{s:<8}" + "".join(
            f"{sortino(ser[m][s]):>16.2f}" if s in ser[m] else f"{'-':>16}"
            for m in metode))
    print("-" * 100)
    print(f"{'povprecje':<8}" + "".join(
        f"{np.nanmean([sortino(ser[m][s]) for s in ser[m]]):>16.2f}" for m in metode))

    # ── knjiga: enako utezena, dnevno poravnana ─────────────────────────────
    print("\n" + "=" * 100)
    print("KNJIGA (enako utezenih 6 sredstev) -- kar se dejansko trguje")
    print("=" * 100)
    knjiga = {}
    for m in metode:
        sk = {}
        for s in ser[m]:
            idx = np.concatenate(oos_idx[s])[:len(ser[m][s])]
            sk[s] = pd.Series(ser[m][s], index=idx)
        df = pd.DataFrame(sk).sort_index()
        knjiga[m] = df.mean(axis=1).dropna()
    print(f"{'metoda':<18}{'CAGR':>9}{'Sharpe':>9}{'Sortino':>9}{'MaxDD':>9}"
          f"{'1 EUR ->':>10}")
    for m in metode:
        q = panel(knjiga[m].to_numpy())
        print(f"{m:<18}{q['cagr']:>8.2f}%{q['sharpe']:>9.2f}{q['sortino']:>9.2f}"
              f"{q['maxdd']:>8.1f}%{q['mult']:>9.2f}x")

    # ── znacilnost proti izhodiscu ──────────────────────────────────────────
    print("\n" + "=" * 100)
    print("JE RAZLIKA SPLOH LOCLJIVA OD SUMA?  (knjiga, bootstrap po blokih)")
    print("=" * 100)
    osn = knjiga["A privzetki"]
    znac = {}
    for m in metode:
        if m == "A privzetki":
            continue
        sk = pd.concat([knjiga[m], osn], axis=1).dropna()
        d = (sk.iloc[:, 0] - sk.iloc[:, 1]).to_numpy()
        a_s, b_s = sortino(sk.iloc[:, 0].to_numpy()), sortino(sk.iloc[:, 1].to_numpy())
        bs = blok_bootstrap(d)
        lo, hi = np.nanpercentile(bs, [5, 95])
        sodba = ("BOLJSI" if lo > 0 else "SLABSI" if hi < 0 else "nedokazano")
        znac[m] = dict(d_sortino=a_s - b_s, lo=float(lo), hi=float(hi),
                       sodba=sodba)
        print(f"   {m:<18}d Sortino {a_s - b_s:+.2f}   "
              f"[{lo:+.2f}, {hi:+.2f}]   -> {sodba}")

    res = dict(generated=str(pd.Timestamp.utcnow()), fee=FEE, korak=KORAK,
               min_zasnova=MIN_ZASNOVA, n_kombinacij=len(KOMB),
               n_odlocitev=n_odlocitev,
               po_sredstvih={m: {s: float(sortino(ser[m][s])) for s in ser[m]}
                             for m in metode},
               knjiga={m: panel(knjiga[m].to_numpy()) for m in metode},
               znacilnost=znac)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"\nzapisano: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
