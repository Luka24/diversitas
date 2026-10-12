"""MVRV kot varovalka pred vstopom na BTC. Test 3 iz testing/nacrt_word_ideje.md.

    python testing/scripts/mvrv_varovalka.py

MERILA, ZAPISANA PRED PRVIM ZAGONOM (commit ba50fda)

Pravilo. Lean na BTC ne vstopi na novo, ko je MVRV nad 95. percentilom lastnih
zadnjih 1460 dni (en cikel). MVRV je zamaknjen za en dan, ker ga CoinMetrics
objavi za nazaj, percentil pa je izracunan brez danasnje vrednosti. Odprte
pozicije ostanejo. Fiksni prag (3,5 ali 3,0) se ne testira, ker je bil izbran z
vedenjem o preteklih vrhovih.

Korak 1, stetje. Kolikokrat se pravilo sprozi in koliko vstopov osnove pade na
dan, ko je pravilo aktivno. Ce je takih vstopov manj kot 5, se test tu ustavi z
zakljuckom "premalo opazovanj, ni preverljivo". Donosov v tem primeru ne
racunamo, da izid ne bi vplival na odlocitev.

Korak 2, samo ce je vstopov vsaj 5: fazni protokol na BTC in robustnost na uri.

Pozitivna kontrola. Pravilo, ki se nikoli ne sprozi, mora dati osnovo bit za bit.

Omejitev podatkov. CoinMetrics realizirano kapitalizacijo popravlja za nazaj,
zato zgodovina ni nujno taka, kot je bila tisti dan na voljo.

Izhod: testing/data/mvrv_varovalka.json
"""
from __future__ import annotations

import json
import sys
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

from graded_alti import _cfg, cene
from diversitas.strategy import compute_features, position, run_state_machine
from shared.warmup import trim_warmup

OKNO, PCT, MIN_VSTOPOV = 1460, 0.95, 5
VIR = ROOT / "testing" / "data" / "sources" / "mvrv_btc.parquet"
URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"


def mvrv() -> pd.Series:
    if VIR.exists():
        return pd.read_parquet(VIR)["mvrv"]
    r = requests.get(URL, params={"assets": "btc", "metrics": "CapMVRVCur",
                                  "frequency": "1d", "page_size": 10000,
                                  "start_time": "2010-07-18"}, timeout=60).json()
    s = pd.Series({pd.Timestamp(x["time"]): float(x["CapMVRVCur"])
                   for x in r["data"]}).sort_index()
    s.index = s.index.normalize()
    VIR.parent.mkdir(parents=True, exist_ok=True)
    s.rename("mvrv").to_frame().to_parquet(VIR)
    return s


def blokada(m: pd.Series, pct: float) -> pd.Series:
    vcerajsnji = m.shift(1)
    meja = vcerajsnji.shift(1).rolling(OKNO, min_periods=OKNO).quantile(pct)
    return (vcerajsnji > meja).fillna(False)


def zagon(raw: pd.DataFrame, blok: pd.Series | None, cfg) -> pd.DataFrame:
    df = compute_features(raw, None, cfg)
    if blok is not None:
        b = blok.reindex(df.index.normalize()).fillna(False).to_numpy()
        df["bull_condition"] = df["bull_condition"] & ~b
    return trim_warmup(run_state_machine(df, cfg))


def vstopi(df: pd.DataFrame) -> pd.DatetimeIndex:
    s = df["signal_state"]
    return df.index[(s == 1) & (s.shift(1) != 1)]


def main() -> int:
    cfg = _cfg()
    raw = cene()["BTC"]
    m = mvrv()
    print("MVRV BTC %s do %s, %d dni" % (m.index[0].date(), m.index[-1].date(), len(m)))

    osnova = zagon(raw, None, cfg)

    # pozitivna kontrola: pravilo, ki se nikoli ne sprozi
    nikoli = zagon(raw, pd.Series(False, index=m.index), cfg)
    ok = (nikoli["signal_state"].equals(osnova["signal_state"])
          and position(nikoli, cfg).equals(position(osnova, cfg)))
    print("Pozitivna kontrola (pravilo se nikoli ne sprozi = osnova): %s"
          % ("OK" if ok else "NAPAKA"))
    if not ok:
        return 1

    blok = blokada(m, PCT)
    okno = osnova.index.normalize()
    b = blok.reindex(okno).fillna(False)
    print("\nOkno lean %s do %s" % (okno[0].date(), okno[-1].date()))
    print("Pravilo aktivno %d od %d dni (%.1f %%)" % (b.sum(), len(b), 100 * b.mean()))

    epizode = []
    if b.any():
        dni = b[b].index.to_series()
        skupina = (dni.diff().dt.days > 30).cumsum()
        for _, e in dni.groupby(skupina):
            epizode.append({"od": str(e.iloc[0].date()), "do": str(e.iloc[-1].date()),
                            "dni": int(len(e)),
                            "mvrv_max": round(float(m.reindex(e.index).max()), 2)})
    print("\nEpizode (presledek > 30 dni loci epizodi):")
    for e in epizode:
        print("   %s do %s  %4d dni  MVRV do %.2f" % (e["od"], e["do"], e["dni"], e["mvrv_max"]))

    v = vstopi(osnova)
    zadeti = [t for t in v if b.get(t.normalize(), False)]
    print("\nVstopov osnove: %d, od tega na dan, ko je pravilo aktivno: %d"
          % (len(v), len(zadeti)))
    for t in zadeti:
        print("   %s" % t.date())
    po2021 = [e for e in epizode if e["od"] >= "2021-06-01"]
    print("Epizod po juniju 2021: %d" % len(po2021))

    out = {"okno": [str(okno[0].date()), str(okno[-1].date())],
           "pravilo": "MVRV(t-1) > %d. percentil zadnjih %d dni" % (round(100 * PCT), OKNO),
           "kontrola": ok, "dni_aktivno": int(b.sum()), "epizode": epizode,
           "vstopov_osnove": len(v), "vstopov_blokiranih": len(zadeti),
           "blokirani": [str(t.date()) for t in zadeti]}

    if len(zadeti) < MIN_VSTOPOV:
        out["sodba"] = "premalo opazovanj, ni preverljivo"
        print("\nSODBA: %d < %d vstopov. Premalo opazovanj, ni preverljivo. "
              "Donosov ne racunam, test se tu ustavi." % (len(zadeti), MIN_VSTOPOV))
    else:
        out["sodba"] = "dovolj opazovanj, sledi korak 2"
        print("\nSODBA: %d vstopov, dovolj za korak 2 (fazni protokol)." % len(zadeti))

    pot = ROOT / "testing" / "data" / "mvrv_varovalka.json"
    pot.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Zapisano: %s" % pot.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
