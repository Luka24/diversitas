# Revizija: so bile formule, datumi in izvedba pravilne?

Ponovni podroben pregled celotne analize momentum tuninga, + odgovor na skrb da je baseline
morda overfit in zato slab anker.

## 1. Formule — preverjene, pravilne

- **Pozicija (kavzalna):** `alloc = target_alloc.shift(1)` — pozicija na dan t uporablja odločitev
  iz t-1. Donos = `alloc_{t-1} × (close_t/close_{t-1} − 1)`. Ni look-ahead.
- **Sortino:** letni donos / letni downside-deviation = `mean·365 / (√(mean(min(r,0)²))·√365)`. Standard.
- **CAGR:** `eq[-1]^(365/n) − 1` na `eq = ∏(1+r)`. **Sharpe:** `mean/std·√365`.
  **MaxDD:** `min(eq/cummax(eq) − 1)`. **Calmar:** `CAGR/|MaxDD|`. **Exposure:** povprečje graded alokacije.
- **Buy&hold referenca:** `close.pct_change()` reindexirana na ista OOS okna. Pravilno.

## 2. Datumi — preverjeni, pravilni

- BTC podatki: **2019-05-23 → 2026-07-04**.
- Nested foldi: train od začetka podatkov, **21-dnevni embargo**, test = koledarsko leto
  (train_end = 1. jan − 21 dni = ~11. dec prejšnjega leta). Pravilno.
- Tuning tabela (sodelavcu): zadnja 4 leta = **2022-07-04 → 2026-07-04**.

## 3. Kavzalnost — dokazana empirično

Primerjal sem donose izračunane na **polni** seriji proti donosom na seriji **skrajšani** na
2023-12-31 (strategija vidi le podatke do reza). Prekrivajočih 1684 dni:
**max |razlika| = 0.00e+00 (bit-identično).** Strategija je popolnoma kavzalna → predizračun
donosov na celi seriji in kasnejše rezanje po datumu ne skriva nobenega look-ahead.

## 4. Je baseline overfit? — NE (preverjeno)

Skrb: baseline (12/4/50) je bil menda nastavljen tako, da je na grafu izgledal lepo → morda overfit.

Preveril sem **plato vs konica** na poštenem OOS (stitched 2021-2025, neto 0.3 %/stran):

| Config | Sortino | MaxDD |
|---|---|---|
| **12/4/50 BASELINE** | 0.98 | −40% |
| 10/4/50 | 1.09 | −39% |
| 15/4/50 | 0.93 | −40% |
| 18/4/50 | 1.04 | −40% |
| 12/3/50 | 1.15 | −40% |
| 12/5/50 | 0.99 | −40% |
| 12/4/25 | 1.05 | −35% |
| 12/4/75 | 0.90 | −45% |
| 12/4/0 | 1.06 | −38% |

Baseline **ni osamljena konica** — je celo rahlo **pod** več sosedi, vsi so v ozkem pasu 0.90–1.15.
Overfitan config bi bil vrh visoko nad okolico; tukaj je obratno. Če je "na grafu izgledal
overfitano", je bil to najverjetneje **in-sample bruto equity curve** (cela zgodovina, brez
stroškov), ne poštena OOS površina. Na pošteni površini je 12/4/50 povsem navaden, rahlo
konservativen plato-točka.

## 5. Ključni reframe — vrednost proti pasivnemu

| | Sortino | MaxDD |
|---|---|---|
| BTC buy&hold | 0.99 | **−77%** |
| strategija 12/4/50 | 0.98 | **−40%** |

Na Sortinu sta skoraj enaka, a strategija ima **pol manjši drawdown**. Prava vrednost strategije
je **kontrola drawdowna**, ne višji risk-adjusted donos. Sortino to podceni. In ker je celotna
parametrska površina ravna (0.90–1.15), noben tuning tega ne izboljša zanesljivo.

## 6. Edina realna omejitev (ne bug, razkrita)

Fee model zaračuna strošek le ob **menjavi signala** (binarni vstop/izstop), ne ob dnevnem
**graded rebalansiranju** (vol-targeting spreminja velikost pozicije dnevno). Realni obrat in
stroški so zato nekoliko višji — kar bolj obremeni aktivnejše (agresivne) confige, torej deluje
v smeri "ostani pri baseline", ne proti njej. Za produkcijo bi bilo vredno dodati proporcionalen
strošek na `|Δpozicija|` dnevno.

## Zaključek revizije

Formule, datumi in izvedba so pravilni; kavzalnost je dokazana (0.00 razlike). Baseline **ni**
overfit — na pošteni OOS površini je navadna plato-točka. Zaključek ostane: **tuning teh
parametrov ne prinese zanesljive OOS prednosti; površina je ravna; obdrži baseline (ali katerokoli
sosednjo vrednost — vseeno je).** Prava vrednost strategije je prepolovljen drawdown proti buy&hold.
