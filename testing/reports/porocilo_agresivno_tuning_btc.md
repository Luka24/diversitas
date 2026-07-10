# Momentum tuning — Bitcoin

Cilj: za agresiven produkt ujeti več rasti, ne da razbijemo drawdown. Testirano na BTC,
ločeno na starem obdobju in na 2025+ (sveži podatki ki jih nisem gledal pri nastavljanju).
Vsaka vrstica = baseline strategija, spremenjen samo tisti parameter. Baseline = trailing 12,
re-entry lock 4, bear-cut 50.

Pojmi:
- **exposure** — koliko časa/kapitala smo v BTC (ostalo v stablecoinu)
- **trailing stop** — te vrže ven ko cena pade X % z vrha
- **re-entry lock** — koliko dni po izstopu čakaš do novega vstopa
- **bear-cut** — kolikšno pozicijo držiš v medvedjem trgu (50 = pol)
- **holdout** — 2025+ test, bear obdobje, zato negativen; šteje razlika med vrsticami

| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar | holdout |
|---|---|---|---|---|---|---|---|
| Baseline (12/4/50) | 39% | 35% | −38% | 1.18 | 1.92 | 1.02 | −5% |
| trailing 8 | 36% | 31% | −33% | 1.17 | 1.92 | 1.09 | −10% |
| trailing 10 | 41% | 34% | −37% | 1.24 | 2.04 | 1.10 | −5% |
| trailing 15 | 38% | 35% | −38% | 1.16 | 1.87 | 1.00 | −5% |
| trailing 18 | 40% | 35% | −38% | 1.20 | 1.95 | 1.06 | −5% |
| trailing 20 | 40% | 35% | −38% | 1.20 | 1.95 | 1.06 | −5% |
| re-entry 1 | 47% | 36% | −38% | 1.31 | 2.13 | 1.23 | −5% |
| re-entry 2 | 47% | 35% | −38% | 1.34 | 2.20 | 1.24 | −5% |
| re-entry 3 | 44% | 34% | −38% | 1.29 | 2.12 | 1.15 | −5% |
| bear-cut 0 | 38% | 33% | −36% | 1.18 | 1.91 | 1.06 | −3% |
| bear-cut 25 | 39% | 34% | −33% | 1.20 | 1.95 | 1.19 | −4% |
| bear-cut 70 | 38% | 35% | −42% | 1.16 | 1.88 | 0.91 | −7% |
| bear-cut 100 | 38% | 36% | −48% | 1.12 | 1.81 | 0.79 | −8% |
| **re-entry2 + bear25** | **47%** | 35% | **−33%** | **1.35** | **2.24** | **1.44** | **−4%** |
| re-entry2 + bear25 + trail10 | 46% | 33% | −32% | 1.35 | 2.24 | 1.45 | −4% |
| trail18 + re-entry2 | 48% | 36% | −38% | 1.35 | 2.24 | 1.27 | −5% |

(BTC buy&hold ima drawdown ~−77 %, torej smo povsod pol nižje.)

Ugotovitve:

- **Re-entry lock je najmočnejši vzvod.** 4 → 2: CAGR 39 → 47 %, Sortino 1.92 → 2.20, Calmar
  1.02 → 1.24, drawdown isti. Re-entry 1 je enak. Nad 4 slabše.
- **Bear-cut naj gre dol, ne gor.** 25 % zniža drawdown (−38 → −33 %) in dvigne Calmar na 1.19.
  Pri 70/100 vse pade (Calmar 0.91 / 0.79, drawdown −42 / −48 %) in holdout se pokvari. Več
  bear-exposure = večji drawdown.
- **Trailing stop ni pravi vzvod.** 15/18/20 so kot baseline, nad 20 se nasiti. Le trailing 10
  malo pomaga, 8 poreže donos.
- **Najboljša kombinacija: re-entry 2 + bear-cut 25.** CAGR 47 %, Sharpe 1.35, Sortino 2.24,
  Calmar 1.44, drawdown −33 % (boljši od baseline), holdout tudi boljši. Vse metrike v pravo smer.
- Exposure ostane ~35 % — te spremembe ga skoraj ne dvignejo, dvignejo pa donos znotraj tega
  časa. Za več izpostavljenosti bi bilo treba odpreti entry pogoje (trackline / momentum).

Trenutni 12/4/50 so iz Pine scripta — če vzamemo re-entry 2 + bear-cut 25, popravim še Pine.
