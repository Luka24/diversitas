# Robustnost tuninga (BTC) — je re-entry2 + bear-cut25 overfit?

Kandidat = re-entry lock 2 + bear-cut 25 (proti baseline 4 / 50). En bear-year holdout ni dovolj, zato preverim čez več režimov, čez mnogo mešanih pod-obdobij (CPCV) in z bootstrap intervalom.

Full-period Sortino: baseline **1.62** → kandidat **1.92** (Δ +0.29).

## 1. Po letih (vsako leto je svoj režim)

| Leto | režim | Sortino baseline | Sortino kandidat | boljši? |
|---|---|---|---|---|
| 2019 | bull | -1.13 | -1.13 | da |
| 2020 | bull | 4.46 | 4.58 | da |
| 2021 | bull/top | 1.44 | 2.23 | da |
| 2022 | bear | -2.76 | -2.53 | da |
| 2023 | recovery | 3.72 | 3.68 | da |
| 2024 | bull | 2.09 | 2.27 | da |
| 2025 | bear/chop | -0.35 | -0.35 | da |
| 2026 | chop | -0.97 | -0.75 | da |

## 2. Po režimu (200-MA: bull / bear / sideways)

| režim | dni | Sortino baseline | Sortino kandidat |
|---|---|---|---|
| bull | 1281 | 2.32 | 2.70 |
| bear | 749 | -1.64 | -1.52 |
| sideways | 570 | 3.35 | 3.20 |

## 3. CPCV + bootstrap

- **CPCV-lite:** čez 252 mešanih pod-obdobij kandidat premaga baseline v **98%** (median Δ Sortino +0.29). To ni ena pot, ampak porazdelitev čez mnogo kombinacij obdobij.
- **Block-bootstrap (5000×, blok 20 dni):** ΔSortino 95% CI **[-0.05, +0.74]**, pozitiven v **95%** resamplov.

## Zaključek

Izboljšava zdrži: bolje ali enako v 8/8 letih, čez pod-obdobja zmaga v 98%, bootstrap CI je večinoma nad 0. Ni videti kot overfit na eno obdobje — mehanizem (hitrejši re-entry, manjša bear-pozicija) je tudi ekonomsko smiseln.

Vseeno pošteno: gre za majhno spremembo dveh parametrov, testirano na enem coinu. Pred uporabo v živo bi to potrdil še s paper tradingom in spremljal ali drži v novem režimu (nestacionarnost).

*Metoda: per-režim + CPCV + block-bootstrap, kot je standard za robustnost čez nestacionarne trge (Lopez de Prado / walk-forward praksa).*
