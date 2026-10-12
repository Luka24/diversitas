"""Ali je rezultat odvisen od tega, ob kateri uri se zapre dnevna svecka?

    python testing/scripts/ura_zakljucka.py

ZAKAJ
Kripto trguje 24 ur na dan, zato je dnevna svecka z zakljuckom ob 00:00 UTC
samo dogovor. Pri ETF-jih je `sreca_datuma.py` pokazal, da je vsa prednost
prihajala iz enega srecnega dne v mesecu. Za kripto isto vprasanje se ni bilo
postavljeno. Concretum (december 2025) poroca, da je trend na BTC najmocnejsi
okoli odprtja azijskih trgov v nedeljo zvecer, kar je blizu nasega zakljucka,
zato obstaja tudi zunanji razlog za sum.

POSTOPEK
Iz urnih svecek Coinbase BTC-USD se sestavi 24 dnevnih serij, vsaka z
zakljuckom ob drugi uri UTC. Na vsaki se pozene nespremenjen lean, privzeti
parametri, 0,30 % na stran, 5 % dno. Nic se ne prilagaja.

POZITIVNA KONTROLA
Serija z zakljuckom ob 00 UTC, sestavljena iz urnih svecek, mora dati skoraj
isto kot uradne dnevne svecke Coinbase na istem oknu. Ce ne, je sestavljanje
narobe in nadaljnje stevilke ne veljajo.

MERILA, ZAPISANA PRED PRVIM ZAGONOM
    V1  robustnost prednosti   lean premaga staticni delez z isto povprecno
                               izpostavljenostjo (Sharpe) pri vsaj 22 od 24 ur
    V2  sreca dogovora         percentil ure 00 UTC v porazdelitvi Sortina cez
                               24 ur. Nad 90. percentilom pomeni, da objavljene
                               stevilke dogovor olepsa, in posteno stevilko je
                               treba brati z mediane. Med 10. in 90. je dogovor
                               nevtralen
    V3  razpon proti sumu      razpon Sortina cez 24 ur se primerja s sirino
                               95 % intervala iz blocnega bootstrapa pri 00 UTC.
                               Ce je razpon ozji, ura ni pomembna nad sumom
    V4  hipoteza Concretum     ure 23, 00 in 01 UTC proti ostalim. Napoved:
                               visje. Samo porocilo, en test, brez posledic

KAJ JE PREPOVEDANO
Izbrati najboljso uro. 24 poskusov na priblizno 27 poslih je ucbeniski primer
prilagajanja sumu, sosednje ure pa so mocno povezane, zato je neodvisnih
poskusov bistveno manj kot 24. Produkcija ostane na 00 UTC ne glede na izid.
Ta test meri, koliko smo imeli srece, ne isce boljse nastavitve.

Izhod: testing/data/ura_zakljucka.json
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean", Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
import pandas as pd
import requests

from graded_alti import FEE, PPY, _cfg, cene
from diversitas.strategy import position, run_strategy, traded_fraction
from shared.warmup import trim_warmup

URNE = ROOT / "testing" / "data" / "sources" / "BTC_coinbase_1h.parquet"
RNG = np.random.default_rng(20261010)
NBOOT, BLOK = 2000, 20
MIN_UR = 20            # dan z manj urnimi sveckami se izpusti
ASIA = (23, 0, 1)


def prenesi_urne() -> pd.DataFrame:
    """Urne svecke po zaporednih oknih po 300 ur, od zacetka do danes.

    Ne uporablja `fetch_candles`, ker ta pri zgodnjih vrzelih Coinbase prekine
    listanje ob prvi nepolni strani.
    """
    if URNE.exists():
        return pd.read_parquet(URNE)
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    t = pd.Timestamp("2015-07-20", tz="UTC")
    konec = pd.Timestamp.now(tz="UTC").floor("h")
    vrst = []
    while t < konec:
        e = min(t + pd.Timedelta(hours=300), konec)
        for poskus in range(5):
            r = requests.get(url, params={"granularity": 3600, "start": t.isoformat(),
                                          "end": e.isoformat()},
                             headers={"User-Agent": "diversitas/1.0"}, timeout=30)
            if r.status_code == 200:
                break
            time.sleep(1 + poskus)
        r.raise_for_status()
        vrst += r.json()
        t = e
        time.sleep(0.12)
    d = pd.DataFrame(vrst, columns=["t", "low", "high", "open", "close", "volume"])
    d["time"] = pd.to_datetime(d["t"], unit="s", utc=True)
    d = (d.drop(columns="t").drop_duplicates("time").set_index("time").sort_index()
         [["open", "high", "low", "close", "volume"]].astype(float))
    URNE.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(URNE)
    return d


def dnevne(h: pd.DataFrame, ura: int) -> pd.DataFrame:
    """Dnevne svecke, ki se zaprejo ob `ura` UTC. Oznaka je zacetek okna."""
    x = h.copy()
    x.index = x.index - pd.Timedelta(hours=ura)
    g = x.resample("1D")
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                      "low": g["low"].min(), "close": g["close"].last(),
                      "volume": g["volume"].sum(), "n": g["close"].count()})
    d = d[d["n"] >= MIN_UR].drop(columns="n")
    d.index = d.index + pd.Timedelta(hours=ura)
    return d


def neto(raw: pd.DataFrame, cfg) -> pd.Series:
    df = trim_warmup(run_strategy(raw, config=cfg).df)
    p = position(df, cfg)
    tr = traded_fraction(df, cfg)
    r = df["close"].pct_change()
    if "prev_close" in df.columns and pd.notna(df["prev_close"].iloc[0]):
        r.iloc[0] = df["close"].iloc[0] / df["prev_close"].iloc[0] - 1.0
    r = r.fillna(0.0)
    return pd.DataFrame({"net": p * r - tr * FEE, "poz": p, "r": r,
                         "posel": (tr > 0.5).astype(int)})


def mere(x: np.ndarray) -> dict:
    eq = np.cumprod(1 + x)
    dd = eq / np.maximum.accumulate(eq) - 1
    dn = np.sqrt(np.mean(np.minimum(x, 0.0) ** 2)) * np.sqrt(PPY)
    return {"sharpe": float(x.mean() * PPY / (x.std() * np.sqrt(PPY))),
            "sortino": float(x.mean() * PPY / dn),
            "cagr": float((eq[-1] ** (PPY / len(x)) - 1) * 100),
            "maxdd": float(dd.min() * 100)}


def sortino(x):
    dn = np.sqrt(np.mean(np.minimum(x, 0.0) ** 2)) * np.sqrt(PPY)
    return float(x.mean() * PPY / dn)


def boot_ci(x: np.ndarray):
    n, nb = len(x), int(np.ceil(len(x) / BLOK))
    v = []
    for _ in range(NBOOT):
        z = RNG.integers(0, n - BLOK, nb)
        i = np.concatenate([np.arange(s, s + BLOK) for s in z])[:n]
        v.append(sortino(x[i]))
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def main() -> int:
    cfg = _cfg()
    h = prenesi_urne()
    print("Urne svecke Coinbase BTC-USD: %s do %s, %d ur."
          % (h.index[0], h.index[-1], len(h)))

    # ── pozitivna kontrola ───────────────────────────────────────────────
    uradne = cene()["BTC"]
    sest0 = dnevne(h, 0)
    sk = uradne.index.intersection(sest0.index)
    odst = (sest0.loc[sk, "close"] / uradne.loc[sk, "close"] - 1).abs()
    print("\nKONTROLA  00 UTC iz urnih proti uradnim dnevnim, %d skupnih dni" % len(sk))
    print("  zakljucek se razlikuje za vec kot 0,1 %% na %d dneh, najvec %.2f %%"
          % (int((odst > 0.001).sum()), 100 * odst.max()))
    a, b = neto(uradne, cfg), neto(sest0, cfg)
    ok = a.index.intersection(b.index)
    ma, mb = mere(a.loc[ok, "net"].to_numpy()), mere(b.loc[ok, "net"].to_numpy())
    print("  uradne:      Sharpe %.3f  Sortino %.3f  CAGR %.1f %%  posli %d"
          % (ma["sharpe"], ma["sortino"], ma["cagr"], a.loc[ok, "posel"].sum()))
    print("  iz urnih:    Sharpe %.3f  Sortino %.3f  CAGR %.1f %%  posli %d"
          % (mb["sharpe"], mb["sortino"], mb["cagr"], b.loc[ok, "posel"].sum()))
    kontrola_ok = abs(ma["sortino"] - mb["sortino"]) < 0.10
    print("  kontrola %s" % ("PRESTANA" if kontrola_ok else "NI PRESTANA"))
    if not kontrola_ok:
        print("  Sestavljanje dnevnih svecek se ne ujema. Ustavljam.")
        return 1

    # ── 24 ur, skupno okno ───────────────────────────────────────────────
    N = {u: neto(dnevne(h, u), cfg) for u in range(24)}
    zac = max(n.index[0] for n in N.values()).normalize() + pd.Timedelta(days=1)
    kon = min(n.index[-1] for n in N.values()).normalize()
    print("\nSKUPNO OKNO %s do %s" % (zac.date(), kon.date()))
    print("\n  %-5s%8s%9s%8s%8s%7s%9s%9s"
          % ("ura", "Sharpe", "Sortino", "CAGR", "MaxDD", "posli", "staticno", "prednost"))
    vrst = {}
    for u, n in N.items():
        m_ = (n.index >= zac + pd.Timedelta(hours=u)) & (n.index < kon + pd.Timedelta(hours=u))
        n = n.loc[m_]
        m = mere(n["net"].to_numpy())
        s = float(n["poz"].mean())
        st = mere((s * n["r"]).to_numpy())
        m.update({"posli": int(n["posel"].sum()), "izpost": s * 100,
                  "staticno_sharpe": st["sharpe"],
                  "prednost": m["sharpe"] - st["sharpe"], "dni": len(n)})
        vrst[u] = m
        print("  %02d   %8.2f%9.2f%7.1f%%%7.0f%%%7d%9.2f%+9.2f"
              % (u, m["sharpe"], m["sortino"], m["cagr"], m["maxdd"], m["posli"],
                 st["sharpe"], m["prednost"]))

    so = np.array([vrst[u]["sortino"] for u in range(24)])
    pr = np.array([vrst[u]["prednost"] for u in range(24)])

    # V1
    zm = int((pr > 0).sum())
    v1 = zm >= 22
    # V2
    pct = float((so < so[0]).mean() * 100 + (so == so[0]).mean() * 50)
    v2 = "olepsa" if pct > 90 else ("podcenjuje" if pct < 10 else "nevtralen")
    # V3
    n0 = N[0]
    n0 = n0.loc[(n0.index >= zac) & (n0.index < kon)]
    lo, hi = boot_ci(n0["net"].to_numpy())
    razpon = float(so.max() - so.min())
    v3 = razpon < (hi - lo)
    # V4
    asia = so[list(ASIA)].mean()
    ostale = so[[u for u in range(24) if u not in ASIA]].mean()

    print("\nMERILA")
    print("  V1  prednost pred staticnim pri %d od 24 ur   -> %s"
          % (zm, "DRZI" if v1 else "NE DRZI"))
    print("  V2  Sortino ob 00 UTC %.2f, %.0f. percentil, mediana %.2f   -> dogovor je %s"
          % (so[0], pct, np.median(so), v2))
    print("  V3  razpon cez ure %.2f (%.2f do %.2f), 95 %% interval pri 00 UTC %.2f do %.2f, sirina %.2f"
          % (razpon, so.min(), so.max(), lo, hi, hi - lo))
    print("      -> ura %s" % ("NI pomembna nad sumom" if v3 else "JE pomembna nad sumom"))
    print("  V4  Sortino ob 23/00/01 UTC %.2f, ostale ure %.2f   -> napoved Concretum %s"
          % (asia, ostale, "se ujema" if asia > ostale else "se ne ujema"))
    print("\nProdukcija ostane na 00 UTC ne glede na izid.")

    out = {"kontrola": {"uradne": ma, "iz_urnih": mb},
           "okno": [str(zac.date()), str(kon.date())],
           "ure": {str(u): {k: round(v, 3) if isinstance(v, float) else v
                            for k, v in m.items()} for u, m in vrst.items()},
           "V1": {"zmag": zm, "drzi": v1},
           "V2": {"sortino_00": round(float(so[0]), 3), "percentil": round(pct, 0),
                  "mediana": round(float(np.median(so)), 3), "sodba": v2},
           "V3": {"razpon": round(razpon, 3), "ci": [round(lo, 3), round(hi, 3)],
                  "ura_nepomembna": v3},
           "V4": {"asia": round(float(asia), 3), "ostale": round(float(ostale), 3)}}
    pot = ROOT / "testing" / "data" / "ura_zakljucka.json"
    pot.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Zapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
