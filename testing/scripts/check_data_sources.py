"""Why is the dashboard not using Binance?

Run this on the machine where the banner appears. The dashboard can only tell
you that a venue failed; this says what it answered and, when the answer is a
geo-block, names it as one so you stop looking for an outage.

    python testing/scripts/check_data_sources.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "lean"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import requests

from shared.data_source import BINANCE_URL, fetch_candles
from shared.warmup import required_history
from diversitas.config import DEFAULT_CONFIG, LeanConfig

# Binance answers 451 to jurisdictions it does not serve and 418/429 when it is
# rate-limiting a caller. None of those are outages and each wants a different
# response, so they are named rather than lumped into "unreachable".
VERDICT = {
    200: "OK",
    403: "BLOKIRAN IP — Binance zavrača to omrežje (ne gre za izpad)",
    451: "GEO-BLOKADA — Binance ne streže tej jurisdikciji (ne gre za izpad)",
    418: "ZAČASNA PREPOVED — predolgo si presegal omejitev zahtevkov",
    429: "PREKORAČENA OMEJITEV zahtevkov — počakaj in poskusi znova",
}


def probe(name: str, url: str, **kw) -> int | None:
    t = time.time()
    try:
        r = requests.get(url, timeout=15, **kw)
    except Exception as e:
        print(f"  {name:<26} NI ODGOVORA   {type(e).__name__}: {str(e)[:110]}")
        return None
    dt = time.time() - t
    note = VERDICT.get(r.status_code, f"nepričakovan status")
    print(f"  {name:<26} HTTP {r.status_code}  {dt:5.2f}s   {note}")
    if r.status_code != 200:
        print(f"  {'':<26} odgovor: {r.text[:180]}")
    return r.status_code


def main() -> int:
    print("=" * 78)
    print("DOSEGLJIVOST VIROV PODATKOV")
    print("=" * 78)

    print("\n1. Neposredni HTTP klici")
    probe("binance ping", "https://api.binance.com/api/v3/ping")
    probe("binance klines BTCUSDT", BINANCE_URL,
          params={"symbol": "BTCUSDT", "interval": "1d", "limit": 3})
    probe("coinbase BTC-USD", "https://api.exchange.coinbase.com/products/BTC-USD/candles",
          params={"granularity": 86400})
    probe("yahoo BTC-USD",
          "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD",
          params={"range": "5d", "interval": "1d"},
          headers={"User-Agent": "Mozilla/5.0"})

    # The dashboard asks for 2000 bars plus warm-up, which Binance can only serve
    # by paginating. A single-page probe passing does not prove the real call does.
    bars = 2000 + required_history(LeanConfig())
    print(f"\n2. Točno tak klic, kot ga dela dashboard  (bars={bars}, strict=True)")
    worked = []
    for src in ("binance", "coinbase", "yahoo"):
        t = time.time()
        try:
            df = fetch_candles("BTC", "1d", bars=bars, config=DEFAULT_CONFIG,
                               prefer=src, strict=True)
        except Exception as e:
            print(f"  {src:<10} NEUSPEH   {type(e).__name__}: {str(e)[:150]}")
            continue
        worked.append(src)
        print(f"  {src:<10} OK        {len(df)} barov   "
              f"{df.index[0].date()} → {df.index[-1].date()}   "
              f"zadnji close {float(df['close'].iloc[-1]):,.2f}   {time.time() - t:.1f}s")

    print("\n" + "=" * 78)
    if "binance" in worked:
        print("SKLEP: Binance deluje s tega stroja. Če dashboard vseeno kaže opozorilo,")
        print("       je šlo za trenutno napako — od 2026-08-11 banner izpiše razlog.")
    elif worked:
        print(f"SKLEP: Binance NE deluje, delujejo pa: {', '.join(worked)}.")
        print("       Dashboard bo uporabil prvi delujoči vir in to izpisal. Številke")
        print("       NISO primerljive s poročili, računanimi na Binance snapshotu.")
    else:
        print("SKLEP: noben vir ne odgovarja — preveri omrežje oz. požarni zid.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
