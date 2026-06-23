# Analiza Stroškov Trgovanja — Diversitas Lean Strategy
**Datum analize:** 2026-06-23  
**Strategija:** Diversitas Lean (Kijun trackline + 50/200 MA + ER filter)  
**Podatki:** Binance 1d OHLCV, 2021-01-01 → 2026-06-23 (5.5 let)  
**Borza:** Binance (primarni vir podatkov in predvidena borza za izvajanje)

---

## 1. Zakaj so stroški pomembni — in zakaj so tukaj minimalni

Stroški trgovanja imajo eksponentni vpliv na donose glede na **frekvenco trejdanja**. Dnevna
strategija z 252 round-tripi/leto pri 0.19% strošku/trip porabi **47.9%** letno samo za
provizije — strategija se izniči. Diversitas Lean je na nasprotnem koncu spektra.

**Frekvenca Diversitas Lean po coinu:**

| Coin | Round trips (5.5 let) | Trejdi / leto | Avg. trajanje | Exposure |
|------|----------------------|---------------|---------------|----------|
| BTC  | 11                   | 2.0           | 62 dni        | 34%      |
| ETH  | 9                    | 1.6           | 66 dni        | 30%      |
| BNB  | 12                   | 2.2           | 54 dni        | 33%      |
| SOL  | 17                   | 3.1           | 25 dni        | 21%      |

SOL ima najvišjo frekvenco (3.1/leto) ker je bolj volatilen in sproži več manjših trendnih
oken. BTC/ETH sta izrazito nizkofrekvencna (1.6–2.0/leto).

---

## 2. Struktura feejev na Binance Spot

### 2.1 Standardni tier (VIP 0)

| Tip naročila | Brez BNB | Z BNB popustom (−25%) |
|---|---|---|
| Taker (market order) | 0.1000% | **0.0750%** |
| Maker (limit order)  | 0.1000% | **0.0750%** |

*Opomba: Na VIP 0 sta maker in taker identična (0.10%). BNB popust znižuje oba na 0.075%.*

### 2.2 VIP tieri — za večje kapitale

| Tier | 30d vol zahteva | Maker | Taker | Taker z BNB |
|------|----------------|-------|-------|-------------|
| VIP 0 | —             | 0.100% | 0.100% | **0.075%** |
| VIP 1 | $1M / 25 BNB  | 0.090% | 0.100% | **0.075%** |
| VIP 2 | $5M / 50 BNB  | 0.080% | 0.100% | **0.075%** |
| VIP 3 | $20M / 250 BNB| 0.042% | 0.060% | **0.045%** |
| VIP 5 | $150M / 1k BNB| 0.025% | 0.031% | **0.023%** |

**Praktičen zaključek:** Za retail trader-ja (pod $1M/mesec) je realni taker fee **0.075%
na stran** (z BNB) = **0.15% round trip**.

VIP 1 zahteva samo 25 BNB v holdingih (ne volumna) — dosegljivo za večino resnih traderjev.
Do VIP 3 je potreben mesečni volumen $20M, kar pri 2 trejdih/leto pomeni ~$10M pozicije —
realno samo za institucionalne.

### 2.3 Optimizacija z limit naročili

Z **limit naročili** (vstop npr. pri close ± 0.1%) trader plača maker fee (isti 0.075%) in
ima **nič slippage**. Tveganje: pri hitrem gibu se naročilo morda ne izpolni. Za dnevne
signale je to zanemarljivo — signal se generira na koncu dneva, izvajanje naslednji dan
zjutraj po limitnem naročilu je standardna praksa pri swing tradingu.

---

## 3. Slippage

### 3.1 Bid-ask spread po coinu na Binance

BTC/USDT je **najplikvidnejši trading par na Binance** z dnevnim volumnom 1–5 milijard USD
(kaiko.com data, 2024–2025):

| Coin pair   | Avg. bid-ask spread | Dnevni vol (est.) | Likvidnostni rang |
|-------------|---------------------|-------------------|-------------------|
| BTC/USDT    | ~0.001–0.002%       | $1–5B             | #1 globalno       |
| ETH/USDT    | ~0.002–0.005%       | $500M–2B          | Top 3             |
| BNB/USDT    | ~0.003–0.008%       | $200–800M         | Top 10            |
| SOL/USDT    | ~0.005–0.015%       | $100–400M         | Top 15            |

*Vir: Kaiko Research "A Cheatsheet for Bid Ask Spreads", Binance Academy*

### 3.2 Market impact po velikosti pozicije

Slippage pri **market naročilu** je funkcija velikosti naročila relativno na globino order
booka:

| Pozicija     | BTC slip/stran | ETH slip/stran | BNB slip/stran | SOL slip/stran |
|---|---|---|---|---|
| $5k – $50k   | 0.010–0.020%   | 0.015–0.030%   | 0.020–0.040%   | 0.030–0.060%   |
| $50k – $500k | 0.020–0.040%   | 0.030–0.060%   | 0.040–0.080%   | 0.050–0.100%   |
| $500k – $5M  | 0.050–0.150%   | 0.080–0.200%   | 0.100–0.250%   | 0.150–0.400%   |
| $5M+         | 0.150–0.500%   | 0.200–0.600%   | priporočen TWAP| priporočen TWAP|

**Za retail (pod $500k):** slippage je praktično samo bid-ask spread = 0.010–0.050% na stran.

### 3.3 Modelirani slippage za backtest (konservativni)

Za namen kalkulacije stroškov privzamemo **konzervativno oceno za retail ($50k–$500k)**:

| Coin | Slippage / stran | Slippage / round trip |
|------|------------------|-----------------------|
| BTC  | 0.020%           | **0.040%**            |
| ETH  | 0.030%           | **0.060%**            |
| BNB  | 0.030%           | **0.060%**            |
| SOL  | 0.050%           | **0.100%**            |

---

## 4. Skupni stroški na round trip

### Formula:
```
Cost_RT = Fee_RT + Slip_RT
        = (fee_per_side × 2) + (slip_per_side × 2)
```

| Coin | Fee/RT   | Slip/RT  | **Skupaj/RT** |
|------|----------|----------|---------------|
| BTC  | 0.150%   | 0.040%   | **0.190%**    |
| ETH  | 0.150%   | 0.060%   | **0.210%**    |
| BNB  | 0.150%   | 0.060%   | **0.210%**    |
| SOL  | 0.150%   | 0.100%   | **0.250%**    |

---

## 5. Letni vpliv stroškov na CAGR

```
Letni strošek = Trades_per_year × Cost_per_RT
```

| Coin | Trejdi/leto | Cost/RT  | **Letni strošek** |
|------|-------------|----------|-------------------|
| BTC  | 2.01        | 0.190%   | **−0.38%**        |
| ETH  | 1.64        | 0.210%   | **−0.34%**        |
| BNB  | 2.19        | 0.210%   | **−0.46%**        |
| SOL  | 3.10        | 0.250%   | **−0.78%**        |

**Zaključek:** Letni strošek je med **0.34% in 0.78%** — izjemno nizek. Pri strategiji z
CAGR 10–27% je to 1.2%–7.3% relativnega odbitka. BTC je najcenejši (0.38%/leto).

---

## 6. USDT Earn Yield — Pozitivni efekt idle cash-a

Ko je strategija v BEAR (izven pozicije), kapital stoji v USDT. Binance Flexible Savings
oz. Simple Earn ponuja konzervativno **3–5% APY** na USDT (2024–2026 povprečje ~4%).

```
USDT_yield = (1 − exposure) × 4% APY
```

| Coin | Exposure | Idle cash | USDT yield/leto |
|------|----------|-----------|-----------------|
| BTC  | 34%      | 66%       | **+2.64%**      |
| ETH  | 30%      | 70%       | **+2.80%**      |
| BNB  | 33%      | 67%       | **+2.68%**      |
| SOL  | 21%      | 79%       | **+3.17%**      |

*Opomba: USDT yield ni zagotovljen in se spreminja. Konzervativna ocena 4% APY je realna
za Binance Earn 2024–2026. V bear trgih (2022) je bil yield nižji (~2%), v bull trgih
(2023–2024) višji (~5–6%).*

---

## 7. Neto prilagoditev — skupna slika

| Coin | CAGR (backtest) | Letni stroški | USDT yield | **Neto adj.** | **Adj. CAGR** |
|------|----------------|---------------|------------|---------------|---------------|
| BTC  | +13.90%        | −0.38%        | +2.64%     | **+2.26%**    | **+16.15%**   |
| ETH  | +27.19%        | −0.34%        | +2.80%     | **+2.47%**    | **+29.66%**   |
| BNB  | +11.80%        | −0.46%        | +2.68%     | **+2.23%**    | **+14.04%**   |
| SOL  | +10.69%        | −0.78%        | +3.17%     | **+2.39%**    | **+13.08%**   |

**Ključno spoznanje:** USDT yield presega stroške pri vseh coinih. Realni prilagojeni CAGR
je višji od backtesta, ne nižji — zahvaljujoč idle cash yield-u.

---

## 8. Primerjava z drugimi strategijami (frekvenčni kontekst)

| Tip strategije           | Trejdi/leto | Letni strošek | Opomba |
|--------------------------|-------------|---------------|--------|
| **Diversitas Lean (BTC)**| **2.0**     | **0.38%**     | **Ta strategija** |
| Swing weekly             | ~52         | ~9.9%         | Tipičen retail swing |
| Daily momentum           | ~100        | ~19%          | Agresivni dnevni |
| Mean reversion daily     | ~252        | ~47.9%        | Nerealno brez HFT |
| Buy & Hold               | 0           | 0%            | Brez transakcij |

---

## 9. Skrite stroške in opomini

### 9.1 Davčni vidik (KRITIČEN za realne trejderje)
Vsak round trip = **2 davčna eventi** (prodaja + nakup). V večini jurisdikcij:
- **Slovenija:** 25% kapitalski dobiček na realizirani dobiček
- **Avstrija:** 27.5% KESt
- **ZDA:** kratkoročni kapitalski dobiček (do 37% za pozicije < 1 leto)

Ker so trejdi pogosto krajši od 1 leta, je davčni strošek **potencialno večji od vseh ostalih
stroškov skupaj**. Pri CAGR +27% (ETH) in 25% davku → efektivni CAGR ≈ +20%.

*Strategija z dolgimi holding periodi (avg 62 dni BTC) je bolj ugodna kot daily strategije,
ampak ne dosega long-term kapitalski dobiček threshold-a (1 leto) pri večini trejdov.*

### 9.2 Stablecoin tveganje
USDT yield predpostavlja da USDT ostane stabilen. De-peg tveganje (USDC/USDT kriza 2023)
je realno ampak kratkotraven. Alternativa: USDC ali FDUSD pri podobnih yieldsih.

### 9.3 Funding rate (futures)
Za **spot** strategijo: N/A. Če bi se strategija izvajala na perpetual futures (ne spot),
bi funding rate dodal ±0.01%/8h (±0.03%/dan) strošek/prihodek. Pri 34% exposure (BTC) in
nevtralnem funding rate bi bil letni vpliv minimalen.

### 9.4 Likvidnostni šoki
V ekstremlih (flash crash, exchange downtime) se spread razširi na 0.5–2%. To se zgodi
redko in pri dnevnih signalih ni sistematičen problem.

### 9.5 Withdrawal in custody stroški
- Hardware wallet transfer: flat ~$5–20 (enkraten strošek)
- Binance withdrawal: ~0.0002 BTC (~$20 pri $100k BTC) za on-chain

---

## 10. Priporočila za implementacijo

### Prioriteta 1 — Aktiviraj BNB plačilo feejev
→ 25% nižji fee (0.075% namesto 0.10%)
→ Na VIP 0 ne potrebuješ nič drugega

### Prioriteta 2 — Limit naročila za vstop/izstop
→ Eliminiraš slippage
→ Signal pride na koncu dneva, vstopi z limitnim naročilom naslednje jutro (close ± 0.1–0.2%)
→ Tveganje neizpolnitve je minimalno pri dnevnih signalih

### Prioriteta 3 — USDT Earn / Simple Earn za idle cash
→ +2.6–3.2%/leto na idle kapital
→ Binance Flexible Savings: instant likvidnost, ni lock-upa
→ Presega vse trading stroške skupaj

### Prioriteta 4 — Izbira coina glede na stroške
→ BTC: najnižji letni strošek (0.38%), najgloblja likvidnost
→ ETH: nizek strošek (0.34%), visoka likvidnost
→ SOL: višji strošek (0.78%) + višja volatilnost signala (3.1 RT/leto)

### Prioriteta 5 — Davčna optimizacija
→ Razmisli o davčno ugodnih wrapper-jih (ETF, strukturirani produkti)
→ Konsultacija z davčnim svetovalcem za jurisdiction-specific strategijo

---

## 11. Povzetek

| | BTC | ETH | BNB | SOL |
|---|---|---|---|---|
| **Letni fee + slip strošek** | **−0.38%** | **−0.34%** | **−0.46%** | **−0.78%** |
| **USDT yield (4% APY)** | **+2.64%** | **+2.80%** | **+2.68%** | **+3.17%** |
| **Neto prilagoditev** | **+2.26%** | **+2.47%** | **+2.23%** | **+2.39%** |
| Backtest CAGR | +13.90% | +27.19% | +11.80% | +10.69% |
| **Prilagojeni CAGR** | **+16.15%** | **+29.66%** | **+14.04%** | **+13.08%** |

**Diversitas Lean ima izjemno nizke transakcijske stroške zahvaljujoč nizki frekvenci
(1.6–3.1 trejdov/leto). Stroški feejev + slippage so 0.34–0.78%/leto — popolnoma
zanemarljivi glede na dosežene donose. Idle cash USDT yield jih dejansko
presega za ~2.2–2.5% letno, kar pomeni da so realni prilagojeni donosi višji
od backtesta.**

---

## 12. Metodološke opombe

- Fee model: Binance VIP 0 z BNB popustom (0.075%/stran)
- Slippage model: konzervativna ocena za retail pozicije $50k–$500k
- USDT yield: 4% APY (konzervativno; realno 3–6% glede na tržne pogoje)
- Backtest period: 2021-01-01 → 2026-06-23 (5.5 let, vključuje bull in bear cikle)
- Ni upoštevano: davki, funding rate (spot strategija), withdrawal fees

---

*Viri:*
- *[Binance Spot Fee Rate](https://www.binance.com/en/fee/spotMaker)*
- *[Binance Fees 2026 — BitDegree](https://www.bitdegree.org/crypto/tutorials/binance-fees)*
- *[Kaiko: A Cheatsheet for Bid Ask Spreads](https://research.kaiko.com/insights/a-cheatsheet-for-bid-ask-spreads)*
- *[Slippage, Benchmarks & TCA in Crypto — Anboto Labs](https://medium.com/@anboto_labs/slippage-benchmarks-and-beyond-transaction-cost-analysis-tca-in-crypto-trading-2f0b0186980e)*
- *[Systematic Trend-Following with Adaptive Portfolio Construction (arXiv 2025)](https://arxiv.org/pdf/2602.11708)*
- *[Bid-Ask Spread and Slippage — Binance Academy](https://www.binance.com/en/academy/articles/bid-ask-spread-and-slippage-explained)*
