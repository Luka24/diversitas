# Momentum — rezultati tuninga (agresivni tier)

Pripomba je bila: risk management dela (drawdown ~−38 % proti −77 % buy&hold), a exposure je
nizek in preveč zaostajamo v rasti. Testiral sem tri vzvode — trailing stop, re-entry lock,
bear-cut — vsak čez smiseln razpon, pooled čez BTC/ETH/SOL/AVAX/LINK, neto brez fees, ločeno
na starem obdobju (design) in na 2025+ holdoutu ki ga pri nastavljanju nismo videli.

## Slovarček

- **Exposure** — koliko kapitala je v povprečju v coinu (ostalo v cashu).
- **Trailing stop** — stop ki sledi ceni; izstopiš če pade X % z najvišjega vrha od vstopa.
- **Re-entry lock** — koliko dni po izstopu čakaš do novega vstopa (manjši = hitreje nazaj).
- **Bear-cut** — kolikšno pozicijo držiš v medvedjem režimu (50 = pol; nižji = manj izpostavljen).
- **Holdout** — 2025+ obdobje, ki ga nismo videli (test proti overfittingu; bilo je bear, zato negativen — šteje relativna primerjava).
- CAGR = letni donos · Sharpe = donos/vol · Sortino = donos/negativna vol · Calmar = CAGR/drawdown.

Vsaka vrstica = cela baseline strategija, spremenjen **samo navedeni parameter** (razen COMBO).

## Rezultati (pooled median, 5 coinov)

| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar | HO CAGR | HO Sortino |
|---|---|---|---|---|---|---|---|---|
| **Baseline (12/4/50)** | 39 % | 19 % | −38 % | 1.83 | — | 1.02 | −11 % | −0.55 |
| trailing 8 | 33 % | 15 % | −33 % | 1.83 | 1.83 | 1.09 | −7 % | −0.21 |
| trailing 10 | 29 % | 18 % | −37 % | 1.78 | 1.78 | 0.96 | −9 % | −0.42 |
| trailing 15 | 38 % | 21 % | −42 % | 1.87 | 1.87 | 1.00 | −5 % | −0.29 |
| trailing 18 | 40 % | 22 % | −38 % | 1.76 | 1.76 | 1.06 | −5 % | −0.29 |
| trailing 20 | 39 % | 22 % | −38 % | 1.75 | 1.75 | 0.94 | −5 % | −0.29 |
| **re-entry 1** | **45 %** | 20 % | −38 % | 1.88 | 1.88 | **1.23** | −5 % | −0.29 |
| **re-entry 2** | 41 % | 20 % | −38 % | 1.75 | 1.75 | 1.19 | −5 % | −0.29 |
| re-entry 3 | 37 % | 19 % | −38 % | 1.70 | 1.70 | 1.15 | −5 % | −0.29 |
| bear-cut 0 | 37 % | 18 % | −36 % | 1.90 | 1.90 | 1.06 | −5 % | −0.19 |
| **bear-cut 25** | 39 % | 19 % | **−33 %** | **1.93** | 1.93 | 1.08 | −9 % | −0.39 |
| bear-cut 70 | 38 % | 20 % | −38 % | 1.78 | 1.78 | 0.91 | −13 % | −0.64 |
| bear-cut 100 | 36 % | 20 % | −42 % | 1.69 | 1.69 | 0.79 | −16 % | −0.72 |
| **COMBO re-entry2 + bear25** | **43 %** | 19 % | **−33 %** | 1.85 | 1.85 | **1.11** | **−4 %** | **−0.20** |
| COMBO re-entry2+bear25+trail10 | 37 % | 18 % | −32 % | 1.78 | 1.78 | 1.00 | −9 % | −0.42 |
| COMBO trail18 + re-entry2 | 40 % | 22 % | −38 % | 1.68 | 1.68 | 1.08 | −5 % | −0.29 |
| COMBO trail18+re-entry2+bear70 | 38 % | 23 % | −42 % | 1.59 | 1.59 | 1.13 | −7 % | −0.36 |

*(Za primerjavo: BTC buy&hold ima drawdown ~−77 %.)*

## Kaj rezultati pokažejo

**Re-entry lock — najmočnejši vzvod.** Hitreje nazaj v trend = več donosa. re-entry 1 da
najvišji CAGR (45 %) in Calmar (1.23), re-entry 2 tesno za njim (41 % / 1.19), oba brez dodatnega
drawdowna. Baseline (4) je slabši (39 % / 1.02).

**Bear-cut — nižje je bolje.** bear-cut 25 ima najboljši Sharpe/Sortino (1.93) in izboljša
drawdown (−33 % proti −38 %). Višje (70, 100) monotono poslabša — Calmar pade na 0.91 / 0.79,
holdout na −13 % / −16 %. Predlog "višje" je torej narobe: več bear-exposure = večji drawdown.

**Trailing stop — šibek vzvod.** 15/18/20 so blizu baseline-a, nad 20 se nasiti; tesnejši (8/10)
znižajo donos. Ni pravega vzvoda tukaj.

**Najboljša kombinacija — re-entry 2 + bear-cut 25:** CAGR 43 % (baseline 39 %), Calmar 1.11
(1.02), drawdown −33 % (−38 %), in **najboljši holdout** (−4 % / Sortino −0.20 proti −11 % / −0.55).
Dva vzvoda ki delujeta skupaj, in drawdown se celo izboljša.

**Opomba glede Sharpe/Sortino:** dobri vzvodi dvignejo CAGR in Calmar, drawdown držijo ali
znižajo. Sharpe/Sortino se pri več tradanja rahlo premakneta (več izpostavljenosti doda
volatilnost hitreje kot donos) — a pri bear-cut 25 sta celo višja (Sortino 1.93). Za agresivni
tier je menjava smiselna; za maksimiranje Sharpe ne.

Realno: skok je zmeren, ne dramatičen — exposure ostane ~19–22 %. Za bistveno večjo
izpostavljenost bi morali rahljati **entry pogoje** (trackline/momentum), ne le exit in sizing.

*Trenutni 12/4/50 so iz Pine scripta; če sprejmemo, popravim še Pine. Reproducibilno:
`testing/scripts/run_aggressive_tuning.py`.*
