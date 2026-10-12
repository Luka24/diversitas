"""Blow-off izstop: ali pomaga, in ali ve kaj o vrhu. Test 1 iz testing/nacrt_word_ideje.md.

    python testing/scripts/blowoff_izstop.py

MERILA, ZAPISANA PRED PRVIM ZAGONOM (nacrt v commitu ba50fda)

Kandidati
    A0  osnova, danasnji lean (blow-off: dist > 25 % in RSI > 80)
    A1  brez blow-offa (blowoff_dist_pct = 999; s tem izgine tudi blokada vstopa)
    A2  blow-off, ko je RSI > 80 in (close - trackline) / ATR(14) presega 97,5.
        percentil iste kolicine na tem kovancu, iz preteklosti (razsirjajoce se
        okno do vceraj, vsaj 365 dni). Dokler zgodovine ni, velja pravilo A0.
Drugih pragov ne poganjamo.

Sredstva. BTC, ETH (z BTC filtrom, kot v produkciji) in knjiga: BTC 50 %, alti po
10 %, normalizirane utezi (popravek mrtve gotovine), mesecno uravnavanje.
Stroski 0,30 % na stran.

Sprejem (vse mora drzati, na BTC IN na knjigi):
    C1  zmaga v vsaj 75 % rastocih faz (3 od 4)
    C2  zmaga v vsaj 60 % padajocih faz (3 od 5)
    C3  zmaga v vsaj 70 % kombinacij treh faz
    C4  98,3 % interval (Bonferroni za 3 kandidate v testih 1 in 2) razlike
        zlozenega donosa na celi zgodovini je nad niclo
    U   na BTC visji Sortino od A0 pri vsaj 16 od 24 ur zakljucka svecke
    DD  najvecji drawdown knjige ni slabsi od A0 za vec kot 5 odstotnih tock
Faze so datirane na ceni BTC (Bry-Boschan, faze_ciklov.datiraj) in se uporabijo
za vsa sredstva. Ce okno sredstva pokrije manj faz, se pragova C1 in C2 vzameta
kot delez.
Ce sprejmeta oba, ima prednost A1 (preprostejsi). Ce noben, ostane 25 %.

Kontrole
    pozitivna  pot s spremenjenim stolpcem `blowoff`, ki ji damo danasnje
               pravilo, mora dati A0 bit za bit
    placebo    blow-off izstope A0 nadomestimo z enakim stevilom izstopov na
               nakljucne dni, ko je lean (brez blow-offa) notri in je cena vsaj
               10 % nad tracklineom. 200 ponovitev, na BTC in ETH. Meri se
               Sortino. Pravi blow-off "ve kaj o vrhu" le, ce je boljsi od vsaj
               80 % placebov.

Diagnostika, ni merilo: Sortino od 2018 naprej, brez parabolicnih let 2016-17.

Produkcija se ne spremeni ne glede na izid.

Izhod: testing/data/blowoff_izstop.json
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from dataclasses import replace
from itertools import combinations
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd

from graded_alti import FEE, PPY, SREDSTVA, UTEZI, _cfg, cene
from fantomska_gotovina import knjiga
from faze_ciklov import datiraj
from ura_zakljucka import dnevne, prenesi_urne
from diversitas.strategy import (compute_features, position, run_state_machine,
                                 traded_fraction)
from shared import indicators as ind
from shared.warmup import trim_warmup

RNG = np.random.default_rng(20261011)
NBOOT, BLOK, ALFA = 2000, 20, 0.05 / 3
N_PLACEBO, PCT = 200, 0.975
IMENA = ("A0 osnova", "A1 brez blow-offa", "A2 ATR-percentil")


# ---------------------------------------------------------------- kandidati
def _znova(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["bull_condition"] = (df["donchian_ok"] & df["track_rising_window"]
                            & df["regime_ok"] & df["btc_filter_ok"]
                            & ~df["blowoff"]).fillna(False)
    return df


def blow_atr(df: pd.DataFrame) -> pd.Series:
    a = ind.atr(df["high"], df["low"], df["close"], 14)
    z = (df["close"] - df["trackline"]) / a
    meja = z.shift(1).expanding(min_periods=365).quantile(PCT)
    novo = (df["rsi"] > 80) & (z > meja)
    staro = (df["dist_pct"] > 25.0) & (df["rsi"] > 80)
    return novo.where(meja.notna(), staro).fillna(False).astype(bool)


def zagon(raw, btc, cfg, kand: str) -> pd.DataFrame:
    if kand == "A1 brez blow-offa":
        cfg = replace(cfg, blowoff_dist_pct=999.0)
    df = compute_features(raw, btc, cfg)
    if kand == "A2 ATR-percentil":
        df["blowoff"] = blow_atr(df)
        df = _znova(df)
    return trim_warmup(run_state_machine(df, cfg))


def neto(df, cfg) -> pd.Series:
    r = df["close"].pct_change().fillna(0.0)
    return position(df, cfg) * r - traded_fraction(df, cfg) * FEE


# ---------------------------------------------------------------- mere
def sortino(x) -> float:
    x = np.asarray(x, float)
    dn = np.sqrt(np.mean(np.minimum(x, 0.0) ** 2)) * np.sqrt(PPY)
    return float(x.mean() * PPY / dn)


def maxdd(x) -> float:
    e = np.cumprod(1 + np.asarray(x, float))
    return float((e / np.maximum.accumulate(e) - 1).min() * 100)


def zlozen(r) -> float:
    return float((np.prod(1 + r) - 1) * 100)


def sodba(ra: np.ndarray, rb: np.ndarray, idx, faze) -> dict:
    faze = [(o, d, v) for o, d, v in faze if d >= idx[0] and o <= idx[-1]]
    maske = [(idx >= o) & (idx <= d) for o, d, _ in faze]
    vrste = [v for *_, v in faze]
    zm = [zlozen(rb[m]) > zlozen(ra[m]) for m in maske]
    nr, nf = vrste.count("rast"), vrste.count("padec")
    zr = sum(z for z, v in zip(zm, vrste) if v == "rast")
    zf = sum(z for z, v in zip(zm, vrste) if v == "padec")
    d = []
    for k in combinations(range(len(faze)), 3):
        m = np.zeros(len(idx), bool)
        for i in k:
            m |= maske[i]
        d.append(zlozen(rb[m]) - zlozen(ra[m]))
    c3 = float((np.array(d) > 0).mean())
    n, nb = len(ra), int(np.ceil(len(ra) / BLOK))
    bd = []
    for _ in range(NBOOT):
        z = RNG.integers(0, n - BLOK, nb)
        i = np.concatenate([np.arange(s, s + BLOK) for s in z])[:n]
        bd.append(zlozen(rb[i]) - zlozen(ra[i]))
    lo, hi = np.percentile(bd, [100 * ALFA / 2, 100 * (1 - ALFA / 2)])
    out = {"rast": [zr, nr], "padec": [zf, nf], "kombinacije": round(c3 * 100),
           "iz": [round(float(lo)), round(float(hi))],
           "C1": zr >= math.ceil(0.75 * nr), "C2": zf >= math.ceil(0.60 * nf),
           "C3": c3 >= 0.70, "C4": bool(lo > 0)}
    out["vsi"] = all(out[c] for c in ("C1", "C2", "C3", "C4"))
    return out


def izpis_sodbe(ime, s):
    print("    %-20s rast %d/%d  padec %d/%d  kombinacije %3d %%  IZ98,3 [%+.0f, %+.0f]  "
          "C1 %s C2 %s C3 %s C4 %s" % (
              ime, *s["rast"], *s["padec"], s["kombinacije"], *s["iz"],
              *["DA" if s[c] else "ne" for c in ("C1", "C2", "C3", "C4")]))


# ---------------------------------------------------------------- placebo
def placebo(raw, btc, cfg, n_izstopov: int) -> list[float]:
    c1 = replace(cfg, blowoff_dist_pct=999.0)
    baza = compute_features(raw, btc, c1)
    a1 = trim_warmup(run_state_machine(baza, c1))
    kand = a1.index[(a1["signal_state"] == 1) & (a1["dist_pct"] > 10.0)]
    out = []
    for _ in range(N_PLACEBO):
        dni = RNG.choice(len(kand), size=min(n_izstopov, len(kand)), replace=False)
        df = baza.copy()
        df["blowoff"] = False
        df.loc[kand[dni], "blowoff"] = True
        df = trim_warmup(run_state_machine(_znova(df), cfg))
        out.append(sortino(neto(df, cfg).to_numpy()))
    return out


def blow_izstopi(df) -> int:
    s = df["signal_state"]
    izs = (s != 1) & (s.shift(1) == 1)
    return int((izs & df["blowoff"].fillna(False)).sum())


# ---------------------------------------------------------------- main
def main() -> int:
    cfg = _cfg()
    C = cene()
    btc = C["BTC"]
    faze = datiraj(btc["close"])
    out = {}

    # pozitivna kontrola
    a0 = zagon(btc, None, cfg, "A0 osnova")
    df = compute_features(btc, None, cfg)
    df["blowoff"] = ((df["dist_pct"] > 25.0) & (df["rsi"] > 80)).fillna(False)
    kontrola = trim_warmup(run_state_machine(_znova(df), cfg))
    ok = kontrola["signal_state"].equals(a0["signal_state"])
    print("Pozitivna kontrola (prepisan blow-off z danasnjim pravilom = A0): %s"
          % ("OK" if ok else "NAPAKA"))
    if not ok:
        return 1

    # posamezna sredstva in pozicije za knjigo
    RUN = {k: {} for k in IMENA}
    for s in SREDSTVA:
        b = None if s == "BTC" else btc
        for k in IMENA:
            RUN[k][s] = zagon(C[s], b, cfg, k)

    print("\nSTEVILO IZSTOPOV ZARADI BLOW-OFFA")
    for s in SREDSTVA:
        print("  %-5s A0 %2d   A2 %2d" % (s, blow_izstopi(RUN["A0 osnova"][s]),
                                         blow_izstopi(RUN["A2 ATR-percentil"][s])))

    print("\nPOSAMEZNA SREDSTVA (Sortino, MaxDD; Sortino od 2018 je diagnostika)")
    R = {}
    for s in ("BTC", "ETH"):
        R[s] = {k: neto(RUN[k][s], cfg) for k in IMENA}
        idx = R[s]["A0 osnova"].index
        for k in IMENA:
            x = R[s][k].reindex(idx).fillna(0.0)
            print("  %-5s %-20s Sortino %.2f  MaxDD %5.1f %%  od 2018 %.2f"
                  % (s, k, sortino(x), maxdd(x), sortino(x[x.index >= "2018-01-01"])))
        out[s] = {}
        for k in IMENA[1:]:
            sd = sodba(R[s]["A0 osnova"].reindex(idx).fillna(0).to_numpy(),
                       R[s][k].reindex(idx).fillna(0).to_numpy(), idx, faze)
            out[s][k] = sd
            izpis_sodbe(k, sd)

    # knjiga
    print("\nKNJIGA (normalizirane utezi, mesecno uravnavanje)")
    idx = RUN["A0 osnova"]["BTC"].index
    RET = {s: C[s]["close"].pct_change() for s in SREDSTVA}
    K = {}
    for k in IMENA:
        POS = {s: position(RUN[k][s], cfg).astype(float) for s in SREDSTVA}
        K[k] = knjiga(idx, POS, RET, UTEZI, True)[0]
        print("  %-20s Sortino %.2f  MaxDD %5.1f %%  od 2018 %.2f"
              % (k, sortino(K[k]), maxdd(K[k]),
                 sortino(K[k][idx >= pd.Timestamp("2018-01-01", tz=idx.tz)])))
    out["knjiga"] = {}
    for k in IMENA[1:]:
        sd = sodba(K["A0 osnova"], K[k], idx, faze)
        sd["dMaxDD"] = round(maxdd(K[k]) - maxdd(K["A0 osnova"]), 1)
        sd["DD"] = sd["dMaxDD"] >= -5.0
        out["knjiga"][k] = sd
        izpis_sodbe(k, sd)
        print("    %-20s sprememba MaxDD %+.1f t.t.  DD %s" % ("", sd["dMaxDD"],
                                                           "DA" if sd["DD"] else "ne"))

    # ura zakljucka
    print("\nURA ZAKLJUCKA (BTC, 24 ur): pri koliko urah kandidat premaga A0 po Sortinu")
    H = prenesi_urne()
    zm = {k: 0 for k in IMENA[1:]}
    for h in range(24):
        d = dnevne(H, h)
        x0 = neto(zagon(d, None, cfg, "A0 osnova"), cfg)
        for k in IMENA[1:]:
            xk = neto(zagon(d, None, cfg, k), cfg).reindex(x0.index).fillna(0.0)
            zm[k] += sortino(xk) > sortino(x0)
    out["ure"] = {}
    for k in IMENA[1:]:
        out["ure"][k] = {"zmag": int(zm[k]), "U": zm[k] >= 16}
        print("  %-20s %2d od 24  U %s" % (k, zm[k], "DA" if zm[k] >= 16 else "ne"))

    # placebo
    print("\nPLACEBO (%d nakljucnih razporedov izstopov)" % N_PLACEBO)
    out["placebo"] = {}
    for s in ("BTC", "ETH"):
        b = None if s == "BTC" else btc
        a0s = RUN["A0 osnova"][s]
        n = blow_izstopi(a0s)
        pl = placebo(C[s], b, cfg, n)
        prav = sortino(neto(a0s, cfg).to_numpy())
        rang = float(np.mean(np.array(pl) < prav))
        out["placebo"][s] = {"izstopov": n, "A0": round(prav, 2),
                             "placebo_mediana": round(float(np.median(pl)), 2),
                             "placebo_5_95": [round(float(np.percentile(pl, 5)), 2),
                                              round(float(np.percentile(pl, 95)), 2)],
                             "A0_boljsi_od": round(rang * 100), "ve_o_vrhu": rang >= 0.80}
        print("  %-5s %2d izstopov  A0 %.2f  placebo mediana %.2f [5-95 %%: %.2f-%.2f]  "
              "A0 boljsi od %3.0f %%  -> %s" % (
                  s, n, prav, np.median(pl), np.percentile(pl, 5), np.percentile(pl, 95),
                  100 * rang, "ve nekaj o vrhu" if rang >= 0.80 else "ne loci se od nakljucja"))

    # skupna sodba
    print("\nSKUPNA SODBA")
    out["sodba"] = {}
    for k in IMENA[1:]:
        sp = (out["BTC"][k]["vsi"] and out["knjiga"][k]["vsi"]
              and out["ure"][k]["U"] and out["knjiga"][k]["DD"])
        out["sodba"][k] = sp
        print("  %-20s BTC %s  knjiga %s  ure %s  DD %s  ->  %s" % (
            k, *["DA" if v else "ne" for v in (out["BTC"][k]["vsi"], out["knjiga"][k]["vsi"],
                                               out["ure"][k]["U"], out["knjiga"][k]["DD"])],
            "SPREJET" if sp else "zavrnjen"))

    pot = ROOT / "testing" / "data" / "blowoff_izstop.json"
    pot.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str),
                   encoding="utf-8")
    print("\nZapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
