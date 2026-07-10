# Zakaj bear-cut tako skače po foldih (diagnostika)

Vprašanje: v nested walk-forwardu je train izbral bear-cut 75/75/0/0/25 — je normalno da tako
skače? Preveril sem tako, da sem fiksiral re-entry=2 in trail=12 ter variiral **samo** bear-cut,
in pogledal train Sortino v vsakem oknu.

## Train Sortino po bear-cut

| Train okno (za test leto) | bear 0 | bear 25 | bear 50 | bear 75 | bear 100 | razpon | najboljši |
|---|---|---|---|---|---|---|---|
| do 2020-12 (2021) | 2.15 | 2.29 | 2.42 | 2.54 | **2.66** | 0.51 | 100 |
| do 2021-12 (2022) | 2.90 | 3.00 | 3.10 | 3.19 | **3.28** | 0.38 | 100 |
| do 2022-12 (2023) | **2.10** | 2.06 | 1.99 | 1.90 | 1.81 | 0.29 | 0 |
| do 2023-12 (2024) | **2.39** | 2.38 | 2.33 | 2.26 | 2.17 | 0.22 | 0 |
| do 2024-12 (2025) | 2.40 | **2.44** | 2.40 | 2.34 | 2.26 | 0.18 | 25 |

## Kaj to pove

**Ni naključni šum.** V vsakem oknu je krivulja gladka in monotona (ne skače gor-dol), razpon je
majhen a realen (0.18–0.51 Sortino). Torej znotraj enega okna je zveza jasna.

**Skače zato ker se predznak naklona obrne:**
- Zgodnja train okna (do 2020-12, do 2021-12) so obvladana z mega-bull trgom 2019–2021. Takrat je
  "bear režim" flag pogosto lažni alarm sredi rasti → več pozicije (bear-cut 100) je pomagalo →
  train reče "drži vse".
- Kasnejša okna vključujejo brutalni 2022 bear. Zdaj je držanje pozicije v bear-flagganih obdobjih
  bolelo → train reče "izstopi (bear-cut 0)".

To je **nestacionarnost, ne napaka**: optimalni bear-cut je resnično odvisen od tega kateri režim
prevladuje v train podatkih — in ta se s časom spreminja. Zato je skakanje pričakovano in
pravzaprav pomembna informacija.

**Dodaten opozorilni znak:** najboljši je skoraj vedno na **robu** (0 ali 100), ne v sredini. Ko
optimum sedi na skrajnem robu razpona, je to tipičen znak da se parameter prilega režimu tega
okna, ne da obstaja prava vmesna vrednost. Edina notranja izbira je bear 25 (2025).

## Zaključek

Skakanje ni bug in ni šum — je dokaz da **bear-cut nima stabilnega optimuma**. Kar izbereš iz
preteklosti bo sistematično napačno za naslednji režim. Zato:

- ne fiksiraj bear-cut na eno ekstremno vrednost iz backtesta,
- obdrži nevtralnih 50 (sredina — ne stavi na noben rob), ali
- naredi bear-cut **odvisen od tekočega režima v živo** namesto ene zamrznjene številke.

Reproducibilno prek `run_aggressive_nested.py` (grid vključuje bear-cut in trailing).
