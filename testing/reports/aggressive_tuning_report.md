# Momentum — rezultati tuninga (agresivni tier)

Pooled median čez BTC/ETH/SOL/AVAX/LINK, neto brez fees. Ločeno na starem obdobju (design) in na 2025+ holdoutu ki ga pri nastavljanju nismo videli. Vsaka vrstica = cela baseline strategija, spremenjen samo navedeni parameter (razen COMBO vrstic).

Za primerjavo: BTC buy&hold ima drawdown ~−77 %, torej so vse variante še vedno pol nižje.

| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar | HO CAGR | HO Sortino |
|---|---|---|---|---|---|---|---|---|
| BASELINE (trail12/reentry4/bear50) | 39% | 19% | -38% | 1.13 | 1.83 | 1.02 | -11% | -0.55 |
| trail=8 | 33% | 15% | -33% | 1.09 | 1.83 | 1.09 | -7% | -0.21 |
| trail=10 | 29% | 18% | -37% | 0.96 | 1.78 | 0.96 | -9% | -0.42 |
| trail=15 | 38% | 21% | -42% | 1.10 | 1.87 | 1.00 | -5% | -0.29 |
| trail=18 | 40% | 22% | -38% | 1.11 | 1.76 | 1.06 | -5% | -0.29 |
| trail=20 | 39% | 22% | -38% | 1.04 | 1.75 | 0.94 | -5% | -0.29 |
| reentry=1 | 45% | 20% | -38% | 1.17 | 1.88 | 1.23 | -5% | -0.29 |
| reentry=2 | 41% | 20% | -38% | 1.10 | 1.75 | 1.19 | -5% | -0.29 |
| reentry=3 | 37% | 19% | -38% | 1.04 | 1.70 | 1.15 | -5% | -0.29 |
| bear_cut=0 | 37% | 18% | -36% | 1.08 | 1.90 | 1.06 | -5% | -0.19 |
| bear_cut=25 | 39% | 19% | -33% | 1.16 | 1.93 | 1.08 | -9% | -0.39 |
| bear_cut=70 | 38% | 20% | -38% | 1.08 | 1.78 | 0.91 | -13% | -0.64 |
| bear_cut=100 | 36% | 20% | -42% | 1.01 | 1.69 | 0.79 | -16% | -0.72 |
| COMBO reentry2+bear25 | 43% | 19% | -33% | 1.16 | 1.85 | 1.11 | -4% | -0.20 |
| COMBO reentry2+bear25+trail10 | 37% | 18% | -32% | 1.10 | 1.78 | 1.00 | -9% | -0.42 |
| COMBO trail18+reentry2 (bear50) | 40% | 22% | -38% | 1.07 | 1.68 | 1.08 | -5% | -0.29 |
| COMBO trail18+reentry2+bear70 | 38% | 23% | -42% | 1.03 | 1.59 | 1.13 | -7% | -0.36 |

## Kaj rezultati pokažejo

**Baseline (12/4/50):** CAGR 39%, exposure 19%, MaxDD -38%, Sharpe 1.13, Sortino 1.83, Calmar 1.02; holdout CAGR -11%.

**Trailing stop** — malo premika in se nad 20 nasiti (18 in 20 skoraj enaka baseline-u). Tesnejši (8–10) niža drawdown a tudi donos. Šibek vzvod.
**Re-entry lock** — najmočnejši vzvod. reentry=2: Calmar 1.19 (baseline 1.02), CAGR 41%. reentry=1 podoben, reentry=3 vmes. Nad 4 (baseline) slabše.
**Bear-cut** — nižje je bolje: bear=25 ima Calmar 1.08 in boljši drawdown (-33%), bear=70 in bear=100 monotono slabše (Calmar 0.91 / 0.79, MaxDD -42%). bear=0 (poln blok) je vmes.
**Najboljša kombinacija — reentry2+bear25:** CAGR 43%, Calmar 1.11, MaxDD -33%, holdout Sortino -0.20. Dva vzvoda ki delujeta skupaj.

**Opomba glede Sharpe/Sortino:** dobri vzvodi dvignejo CAGR in Calmar, drawdown držijo ali znižajo, Sharpe in Sortino pa se malo premakneta (več tradanja doda volatilnost hitreje kot donos). Za agresivni tier smiselna menjava; za maksimiranje Sharpe ne.
