# Momentum tuning — povzetek za sodelavca

Kratko: preveril sem ali predlagane agresivnejše nastavitve (širši trailing, hitrejši re-entry,
večji bear-cut) dejansko izboljšajo momentum strategijo. **Zaključek: ne zanesljivo. Ostanimo pri
obstoječih Pine vrednostih (trailing 12 / re-entry 4 / bear-cut 50).** Spodaj zakaj.

Vse na BTC, neto **0.3 % na stran** (fee + slippage, round-trip 0.6 %).

## A) Kako parametri zgledajo na zgodovini — zadnja 4 leta (2022-07 → 2026-07)

Vsaka vrstica = baseline, spremenjen samo navedeni parameter.

| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar |
|---|---|---|---|---|---|---|
| **Baseline (12/4/50)** | 17% | 39% | −35% | 0.71 | 1.14 | 0.49 |
| trailing 8 | 14% | 37% | −31% | 0.61 | 0.97 | 0.44 |
| trailing 10 | 19% | 39% | −31% | 0.78 | 1.25 | 0.62 |
| trailing 15 | 17% | 39% | −35% | 0.71 | 1.14 | 0.49 |
| trailing 18 | 20% | 39% | −28% | 0.80 | 1.29 | 0.72 |
| trailing 20 | 20% | 39% | −28% | 0.80 | 1.29 | 0.72 |
| re-entry 1 | 20% | 39% | −35% | 0.79 | 1.27 | 0.57 |
| re-entry 2 | 18% | 39% | −35% | 0.75 | 1.20 | 0.52 |
| re-entry 3 | 18% | 39% | −35% | 0.74 | 1.19 | 0.52 |
| bear-cut 0 | 20% | 36% | −38% | 0.81 | 1.31 | 0.53 |
| bear-cut 25 | 19% | 38% | −35% | 0.78 | 1.27 | 0.56 |
| bear-cut 70 | 16% | 40% | −36% | 0.65 | 1.03 | 0.43 |
| bear-cut 100 | 13% | 41% | −39% | 0.56 | 0.87 | 0.34 |
| re-entry2 + bear25 | 20% | 38% | −35% | 0.82 | 1.33 | 0.59 |
| re-entry2 + bear25 + trail10 | 22% | 38% | −31% | 0.87 | 1.43 | 0.71 |
| trail18 + re-entry2 | 21% | 40% | −28% | 0.83 | 1.34 | 0.76 |

Kaj se vidi:
- **bear-cut naj gre dol, ne gor.** Predlog "60-70 %" je narobe — 70/100 poslabšata vse (Sortino
  1.03/0.87, MaxDD −36/−39 %). Nižji bear-cut (0-25) je boljši.
- **trailing 18/20 in re-entry 1** rahlo pomagajo v tem oknu; trailing 8 škodi.
- Nekaj kombinacij (trail18+re-entry2, re-entry2+bear25+trail10) zgleda najbolje.

**Ampak — to je in-sample.** "Najboljša" vrstica se menja z oknom (na zadnjih 3 letih je zmagal
trail18, na celotni zgodovini re-entry2+bear25). To pomeni izbiro po hindsightu, ne dokaz.

## B) Pošten test brez selection biasa — nested walk-forward

Da izločim selection bias: v vsakem letu parameter izberem **samo iz preteklosti** (train), nato
uporabim na neviden test, zlepim. Iskal sem po re-entry × bear-cut × trailing (80 kombinacij).

| Fold | TRAIN | TEST | izbran iz train (re-entry/bear/trail) | OOS Sortino izbran | baseline |
|---|---|---|---|---|---|
| bull/top | 2019-05-23 → 2020-12-11 | 2021 | 3 / 75 / 10 | 1.65 | 1.23 |
| bear | 2019-05-23 → 2021-12-11 | 2022 | 2 / 75 / 12 | −2.83 | −2.84 |
| recovery | 2019-05-23 → 2022-12-11 | 2023 | 2 / 0 / 12 | 3.45 | 3.58 |
| bull | 2019-05-23 → 2023-12-11 | 2024 | 2 / 0 / 12 | 1.81 | 1.86 |
| bear/chop | 2019-05-23 → 2024-12-11 | 2025 | 2 / 25 / 18 | −0.51 | −0.51 |

**Zlepljen OOS Sortino: izbira-iz-preteklosti 0.94 vs baseline 0.98 (Δ −0.04).** BTC buy&hold = 0.99.

→ Ko izbira **ne vidi** testa, prednost izgine. Lep rezultat na celi zgodovini je bil selection bias.

## Dva ključna opažanja

1. **Več parametrov = slabše OOS.** Ko sem v iskanje dodal še trailing (16 → 80 kombinacij), je
   zlepljeni OOS padel (1.16 → 1.13 bruto). Klasičen podpis overfittinga — več gumbov, več
   priložnosti da nekaj po sreči zgleda dobro na treningu.

2. **bear-cut nima stabilnega optimuma.** Po foldih izbere 75/75/0/0/25. Ni šum — v vsakem oknu
   je krivulja gladka, a naklon se obrne: bull-težka zgodnja okna hočejo visok bear-cut, okna z
   2022 bearom hočejo nizkega. Nestacionaren trg → karkoli fiksiraš iz backtesta bo napačno za
   naslednji režim.

## Priporočilo

- **Ostani pri baseline** (trailing 12 / re-entry 4 / bear-cut 50). Adaptivno re-optimiziranje ga
  ne premaga OOS, niti neto.
- Če hočemo agresivnejši produkt, to **ni** v exit/sizing parametrih (exposure ostaja ~39 %).
  Treba bi rahljati **entry pogoje** (trackline / momentum), ne trailing/re-entry/bear-cut.
- bear-cut naj bo, če že, **odvisen od tekočega režima v živo**, ne ena zamrznjena številka.

*Reproducibilno: `run_costed_3y.py` (tabela + nested), `run_aggressive_nested.py`,
`nested_bearcut_diagnostika.md`. Metodologija: `metodologija_testiranja.md`.*
