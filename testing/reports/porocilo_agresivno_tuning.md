# Momentum — testiranje predlogov za več upside-a

Pogledal sem tvoje tri predloge. Testiral na BTC/ETH/SOL/AVAX/LINK, ločeno na starem
obdobju in na 2025+ holdoutu (da ne fitam samo na preteklost).

**Kratek zaključek: dva predloga delujeta, tretji se izjalovi.**

- **Trailing stop 12 → 18: da.** Imel si prav, 12 % je bil malo pretesen — metal nas je
  ven iz runov ki so se nadaljevali. Exposure gre z ~19 na ~22 %, drawdown enak, holdout
  se opazno izboljša. 15–20 so vsi podobni, 18 vzamem kot sredino. 20 je že malo preširok.

- **Re-entry lock 4 → 2: da, najboljši vzvod.** Hitreje nazaj v trend. CAGR 39 → 41 %,
  Calmar 1.02 → 1.19, drawdown enak. Confirmation je že na 1, tam ni kaj rahljati.

- **Bear-regime size 50 → 60/70/80: NE, poslabša.** Tu je logika obrnjena — drawdown je
  dobro kontroliran *zato ker* v bear trgu zmanjšamo pozicijo. Če to rahljamo, večamo
  izpostavljenost točno takrat ko ne smemo: Calmar pade (1.02 → 0.87) in holdout (ki je
  bear market) se poslabša. Pusti na 50.

**Priporočam: trail 18, re-entry 2, bear-cut ostane 50.**

## Kako se odzovejo metrike

| | CAGR | Sharpe | Sortino | Calmar | MaxDD |
|---|---|---|---|---|---|
| Zdaj (12/4/50) | 39 % | 1.13 | 1.83 | 1.02 | −38 % |
| Priporočeno (18/2/50) | 40 % | 1.07 | 1.68 | 1.08 | −38 % |

CAGR gor, Calmar gor, drawdown isti, holdout boljši. **Sharpe in Sortino pa gresta malo dol**
(−0.06 oz. −0.15) — to je pričakovano: več agresije pomeni več tradov in izpostavljenosti,
kar doda volatilnost malo hitreje kot donos. Torej žrtvuješ malo "učinkovitosti na enoto
volatilnosti" za več surovega donosa in nižji drawdown-adjusted. Za agresivni tier je to
smiselna menjava; če bi optimizirali Sharpe, ne bi.

Realno: dobiček je inkrementalen, ne velik skok — strategija je po zasnovi večino časa iz
trga (exposure ostane ~20 %). Za res bistveno večjo izpostavljenost bi morali rahljati
**entry pogoje** (trackline / momentum), ne le exit in sizing — to je večja sprememba, jo
testiram posebej če hočeš.

Opomba: 12 in 4 sta iz Pine scripta, tako da če to sprejmemo, popravim še Pine da se ujemata.
