# Momentum z realnimi stroški 0.3 %/stran — Bitcoin

Stroški: **0.30 % na nakup ali prodajo** (fee + slippage skupaj), round-trip 0.60 %. Model zaračuna strošek ob vsaki menjavi signala (opomba: ne ob dnevnem graded rebalansiranju, zato je realni strošek še malenkost višji).

## A) Tuning tabela — zadnja 3 leta (2023-07-04 → 2026-07-04)

Vsaka vrstica = cela baseline strategija, spremenjen samo navedeni parameter. Baseline = trailing 12 / re-entry 4 / bear-cut 50. Vse NETO (0.3 %/stran).

| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar |
|---|---|---|---|---|---|---|
| **Baseline (12/4/50)** | 19% | 42% | -35% | 0.77 | 1.22 | 0.55 |
| trailing 8 | 19% | 40% | -31% | 0.77 | 1.24 | 0.60 |
| trailing 10 | 22% | 42% | -31% | 0.85 | 1.37 | 0.71 |
| trailing 15 | 19% | 42% | -35% | 0.77 | 1.22 | 0.55 |
| trailing 18 | 23% | 43% | -28% | 0.88 | 1.41 | 0.83 |
| trailing 20 | 23% | 43% | -28% | 0.88 | 1.41 | 0.83 |
| re-entry 1 | 23% | 43% | -35% | 0.88 | 1.40 | 0.66 |
| re-entry 2 | 21% | 43% | -35% | 0.82 | 1.29 | 0.60 |
| re-entry 3 | 21% | 42% | -35% | 0.81 | 1.29 | 0.59 |
| bear-cut 0 | 18% | 39% | -38% | 0.74 | 1.17 | 0.48 |
| bear-cut 25 | 20% | 41% | -35% | 0.79 | 1.25 | 0.57 |
| bear-cut 70 | 19% | 43% | -36% | 0.76 | 1.19 | 0.52 |
| bear-cut 100 | 19% | 45% | -39% | 0.73 | 1.15 | 0.48 |
| re-entry2 + bear25 | 21% | 41% | -35% | 0.83 | 1.32 | 0.61 |
| re-entry2 + bear25 + trail10 | 23% | 41% | -31% | 0.90 | 1.45 | 0.75 |
| trail18 + re-entry2 | 25% | 43% | -28% | 0.92 | 1.49 | 0.89 |

## B) Nested walk-forward — iste folde, NETO (0.30 %/stran)

Train se vedno začne 2019-05-23 in raste; med train in test 21-dnevni embargo. V vsakem foldu izberem re-entry×bear-cut×trail SAMO iz train dela (po train Sortino), uporabim na neviden test, zlepim.

| Fold | TRAIN | TEST | izbran iz train (re-entry / bear / trail) | OOS Sortino izbran | OOS Sortino baseline |
|---|---|---|---|---|---|
| bull/top | 2019-05-23 → 2020-12-11 | 2021-01-01 → 2021-12-31 | 3 / 75 / 10 | 1.65 | 1.23 |
| bear | 2019-05-23 → 2021-12-11 | 2022-01-01 → 2022-12-31 | 2 / 75 / 12 | -2.83 | -2.84 |
| recovery | 2019-05-23 → 2022-12-11 | 2023-01-01 → 2023-12-31 | 2 / 0 / 12 | 3.45 | 3.58 |
| bull | 2019-05-23 → 2023-12-11 | 2024-01-01 → 2024-12-31 | 2 / 0 / 12 | 1.81 | 1.86 |
| bear/chop | 2019-05-23 → 2024-12-11 | 2025-01-01 → 2025-12-31 | 2 / 25 / 18 | -0.51 | -0.51 |

**Zlepljen OOS Sortino: izberi-iz-train 0.94 vs fiksni baseline 0.98 (Δ -0.04).** Nevtralna referenca BTC buy&hold: 0.99.

Izbrani re-entry po foldih: [3, 2, 2, 2, 2]. Bear-cut: [75, 75, 0, 0, 25]. Trail: [10, 12, 12, 12, 18].

## Zaključek

Tudi z višjimi stroški (0.3 %/stran) izbira-iz-preteklosti **ne premaga** baseline-a na nevidenih podatkih (Δ -0.04). Izbrani parametri ostajajo nestabilni (bear-cut/trail skačeta po foldih). Zaključek se ne spremeni: tuning teh parametrov ne prinese zanesljive OOS prednosti → ostani pri baseline.