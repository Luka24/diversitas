> **OPOMBA (2026-06-11):** Dele tega dokumenta je nadomestil novejši
> `API_REPORT.md`, ki vsebuje rezultate dejanskih live probe testov.
> Dva starejša priporočila iz spodnjega so zdaj neaktualna:
> - **CryptoCompare** ZDAJ zahteva API ključ (HTTP 401 brez njega) —
>   pred letom ni bilo tako.
> - **CoinGecko free** ima v praksi **50 % fail rate** pod burstom (5–15
>   calls/min limit). NE priporočamo za live dashboard.
>
> Za posodobljen ranking glej `API_REPORT.md`.

# Crypto market-data API research

For Diversitas Pro v3 we need:
- **Daily OHLCV** for primary asset (BTC, ETH, …) — at least 400 bars (200MA + 100-bar ADX mean + warmup ≈ 350).
- **Daily OHLCV for BTC** as cross-asset filter on altcoins.
- Fresh "today" candle (live or 5-min-stale acceptable).
- No paywall, no mandatory key for the primary path.

## Candidates

### 1. Binance Spot — **PRIMARY**
- Endpoint: `GET https://api.binance.com/api/v3/klines`
- Params: `symbol` (e.g. `BTCUSDT`), `interval` (`1d`, `1w`, `4h`, …), optional `startTime`, `endTime`, `limit` (max **1000**).
- No auth, no API key for market data.
- Rate limit: **6000 weight / minute / IP**, klines = 2 weight (≤500 bars) or 5 weight (≤1000). → ~1200 calls/min easily.
- Response: array of `[openTime, open, high, low, close, volume, closeTime, …]`. Open prices are strings, parse to float.
- WebSocket: `wss://stream.binance.com:9443/ws/btcusdt@kline_1d` for live tick.
- Coverage: BTCUSDT goes back to 2017-08-17. All major alts present.
- Pros: huge rate budget, no key, sub-second latency, well-documented, used everywhere.
- Cons: in some jurisdictions Binance.com is geo-blocked → fallback path needed.
  ([API docs](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints))

### 2. CoinGecko — **FALLBACK #1**
- Endpoint: `GET https://api.coingecko.com/api/v3/coins/{id}/ohlc?vs_currency=usd&days=N`
- No auth on free Public tier, but rate limit **5–15 calls/min** (degrades under load). Demo plan (free, requires sign-up) = **30 calls/min**.
- Returns 4-hourly OHLC for `days=1..90`, daily OHLC for `days=180/365/max`.
- **Important:** no volume on the `/ohlc` endpoint. Volume requires `/market_chart` (`prices`, `market_caps`, `total_volumes` arrays). For our strategy we need volume, so we'd combine both — extra calls.
- Pros: huge coverage, exchange-aggregated price, no key.
- Cons: tight rate limit, volume needs second call, sometimes flaky under load.
  ([Pricing & limits](https://www.coingecko.com/en/api/pricing))

### 3. Yahoo Finance via `yfinance` — **FALLBACK #2**
- `yf.download("BTC-USD", period="2y", interval="1d")` returns OHLCV.
- No auth, no rate limit (unofficial — Yahoo can throttle).
- Daily history goes back to 2014 for BTC-USD.
- Pros: zero setup, very stable for daily, well-known in research community.
- Cons: not real-time (latest bar lags ~15 min), Yahoo's API is unofficial and can break (it broke twice in 2023). Intraday limited to ~60 days.
  ([yfinance GitHub](https://github.com/ranaroussi/yfinance))

### 4. Kraken — considered, not chosen
- `GET https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1440`
- ~1 req/sec/IP, no auth. Solid, but smaller history depth than Binance and odd pair naming (`XBT` not `BTC`).
  ([Rate limits](https://docs.kraken.com/api/docs/guides/spot-rest-ratelimits/))

### 5. Coinbase Advanced Trade — considered, not chosen
- `GET https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400`
- Max 300 candles per call → multiple requests for 400-bar window. Doable but klunkier than Binance.

### 6. CryptoCompare — considered, not chosen
- `GET https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=2000`
- Free tier 250k calls/month. Solid, but requires registration for any sustained use.

---

## Decision matrix

| API | Free without key | Daily candles | Volume | History depth | Rate limit | Latency | Choice |
|---|---|---|---|---|---|---|---|
| Binance | ✅ | ✅ 1000/call | ✅ | 2017+ | Excellent (6000 w/min) | sub-second | **PRIMARY** |
| CoinGecko | ✅ (5-15/min) | ✅ (no vol) | ❌ separate call | All | Tight | Few minutes | Fallback #1 |
| yfinance | ✅ | ✅ | ✅ | 2014+ | OK (unofficial) | ~15 min | Fallback #2 |
| Kraken | ✅ | ✅ | ✅ | 2013+ | 1/sec | ~1 min | Skip |
| Coinbase | ✅ | ✅ (300/call) | ✅ | 2015+ | OK | sub-second | Skip |
| CryptoCompare | needs key | ✅ | ✅ | All | 250k/mo | OK | Skip |

---

## Plan for `data_source.py`

```python
class CandleSource:
    def fetch(symbol: str, interval: str = "1d", bars: int = 500) -> pd.DataFrame
        """Returns DataFrame indexed by UTC timestamp with columns
        [open, high, low, close, volume]. Tries Binance, then CoinGecko,
        then yfinance."""
```

Symbol mapping:
| Logical | Binance | CoinGecko ID | yfinance |
|---|---|---|---|
| BTC | BTCUSDT | bitcoin | BTC-USD |
| ETH | ETHUSDT | ethereum | ETH-USD |
| SOL | SOLUSDT | solana | SOL-USD |
| BNB | BNBUSDT | binancecoin | BNB-USD |

Caching: in-memory dict keyed by `(symbol, interval)` with TTL = 60 s for live dashboard refresh. Force refresh on user click.

WebSocket for "true live" can be added later (Binance kline stream). For v1 a 30-second poll of the latest closed daily bar is plenty — daily candles barely move within seconds.

---

## Sources

- [Binance Klines endpoint](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints)
- [Binance rate limits](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits)
- [CoinGecko free API rate limit](https://support.coingecko.com/hc/en-us/articles/4538771776153-What-is-the-rate-limit-for-CoinGecko-API-public-plan)
- [Kraken spot REST rate limits](https://docs.kraken.com/api/docs/guides/spot-rest-ratelimits/)
- [Kraken OHLC endpoint](https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/)
- [yfinance GitHub](https://github.com/ranaroussi/yfinance)
