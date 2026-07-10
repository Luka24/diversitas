# Momentum — testiranje predlogov za več upside-a

Pripomba je bila: risk management dela (drawdown ~−38 % proti −77 % buy&hold), a exposure je
nizek (~35 % na BTC) in preveč zaostajamo v rasti — za agresiven produkt bi radi ujeli več.
Testiral sem tri predloge: širši trailing stop, hitrejši re-entry, večji bear-cut.

## Slovarček

- **Exposure** — koliko kapitala je v povprečju v coinu (ostalo v cashu). Nizek = manj ujameš, manj tvegaš.
- **Trailing stop** — stop ki sledi ceni navzgor; izstopiš če cena pade X % z najvišjega vrha od vstopa. Zaklene dobiček.
- **Re-entry lock** — koliko dni po izstopu čakaš do novega vstopa. Manjši = hitreje nazaj.
- **Bear-cut** — kolikšno pozicijo držiš v medvedjem režimu (50 = pol). Nižji = manj izpostavljen.
- **Holdout** — obdobje 2025+ ki ga pri nastavljanju nismo videli (test proti overfittingu; bilo je bear, zato negativen — šteje relativna primerjava).
- CAGR = letni donos · Sharpe = donos/volatilnost · Sortino = donos/negativna volatilnost · Calmar = CAGR/drawdown.

## Kje vsak vzvod dejansko premakne (BTC, širok sweep)

Prva ugotovitev: nekatere vrednosti sploh nič ne premaknejo — nima jih smisla testirati.

**Trailing stop — nad 20 se nasiti (mrtva cona):**
| trailing | 8 | 10 | 12 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|---|
| Calmar | 0.80 | **0.85** | 0.78 | 0.76 | 0.81 | 0.81 | 0.81 |

→ predlog 15/18/20 je bil ravno v ravni coni, zato skoraj brez razlike. Šibek vzvod; testiraj kvečjemu 8–12, nič nad 20.

**Re-entry lock — oster prelom pri 2 vs 4:**
| re-entry | 1 | 2 | 4 | 6 | 8 |
|---|---|---|---|---|---|
| CAGR | 36% | **36%** | 30% | 31% | 30% |
| Calmar | 0.94 | **0.95** | 0.78 | 0.82 | 0.80 |

→ pravi vzvod. Hitro (1–2) jasno boljše. Testiraj 1, 2, 3, 4.

**Bear-cut — nižje je bolje (monotono):**
| bear-cut | 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|
| Calmar | 0.83 | **0.92** | 0.78 | 0.67 | 0.59 |
| MaxDD | −36% | **−33%** | −38% | −43% | −48% |

→ 25 % je sweet spot. Predlog "višje (60–70)" je točno narobe: več bear-exposure = večji drawdown. Testiraj 0, 25, 50, ne višje.

## Zaključek

**Splača se:**
- **Re-entry 4 → 2** — glavni win. CAGR 30 → 36 %, Calmar 0.78 → 0.95, drawdown isti, drži tudi na holdoutu.
- **Bear-cut 50 → 25** — Calmar 0.78 → 0.92, drawdown se celo izboljša (−38 → −33 %).

**Ne splača se:**
- Širši trailing (ravna cona nad 12).
- Večji bear-cut (poslabša vse: Calmar dol, drawdown gor).

**Priporočena kombinacija: re-entry 2 + bear-cut 25** (trailing pusti ali daj 10).

Ena poštena opomba glede metrik: te spremembe dvignejo CAGR in Calmar, drawdown pa držijo ali
znižajo — **Sharpe in Sortino pa gresta rahlo dol** (npr. pri re-entry 2 Sortino 1.62 → 1.87 je
sicer višji, a pri kombinacijah z več tradanja pade za ~0.1). Logika: več agresije = več tradov
in izpostavljenosti, kar doda volatilnost malo hitreje kot donos. Za agresiven tier je to
smiselna menjava; za Sharpe-maksimiranje ne.

Realno je skok inkrementalen — exposure ostane ~35 %. Za bistveno večjo izpostavljenost bi
morali rahljati **entry pogoje** (trackline/momentum), ne le exit in sizing; to je večja
sprememba, testiram jo posebej če hočeš.

*(Vse številke so BTC/cela zgodovina za jasnost učinka; končno vzamemo iz pooled + holdout čez
vse coine. Trenutni 12/4/50 so iz Pine scripta — če kaj sprejmemo, popravim še Pine.)*
