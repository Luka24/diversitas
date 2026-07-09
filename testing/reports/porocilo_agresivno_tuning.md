# Momentum — testiranje predlogov za več upside-a

Pogledal sem tvoje tri predloge. Vsakega testiral posebej + kombinacijo, na
BTC/ETH/SOL/AVAX/LINK (pooled median), ločeno na starem obdobju (design) in na
2025+ holdoutu ki ga nismo videli — da vidim ali kaj drži tudi izven fita.

Vse številke so povprečje čez 5 coinov, neto brez fees. MaxDD za primerjavo: BTC
buy&hold je ~−77 %, tako da smo pri vseh variantah še vedno pol nižje.

## Kaj smo testirali in kaj je prišlo ven

**Baseline = trailing 12 %, re-entry lock 4, bear-cut 50 % (kot v Pine)**

| Varianta | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar | Holdout CAGR / Sortino |
|---|---|---|---|---|---|---|---|
| **Baseline (12/4/50)** | 39 % | 19 % | −38 % | 1.13 | 1.83 | 1.02 | −11 % / −0.55 |
| trailing 15 | 38 % | 21 % | −42 % | 1.10 | 1.87 | 1.00 | −5 % / −0.29 |
| **trailing 18** | 40 % | 22 % | −38 % | 1.11 | 1.76 | 1.06 | −5 % / −0.29 |
| trailing 20 | 39 % | 22 % | −38 % | 1.04 | 1.75 | 0.94 | −5 % / −0.29 |
| re-entry 3 | 37 % | 19 % | −38 % | 1.04 | 1.70 | 1.15 | −5 % / −0.29 |
| **re-entry 2** | 41 % | 20 % | −38 % | 1.10 | 1.75 | 1.19 | −5 % / −0.29 |
| bear-cut 60 | 39 % | 19 % | −38 % | 1.11 | 1.80 | 0.96 | −12 % / −0.61 |
| bear-cut 70 | 38 % | 20 % | −38 % | 1.08 | 1.78 | 0.91 | −13 % / −0.64 |
| bear-cut 80 | 38 % | 20 % | −39 % | 1.06 | 1.75 | 0.87 | −14 % / −0.68 |
| Agresivno (18/2/**70**) | 38 % | 23 % | −42 % | 1.03 | 1.59 | 1.13 | −7 % / −0.36 |
| **Priporočeno (18/2/50)** | **40 %** | **22 %** | **−38 %** | 1.07 | 1.68 | **1.08** | **−5 % / −0.29** |

## Kaj se je splačalo

**Trailing stop 12 → 18 (splača se).** Imel si prav, 12 % je bil malo pretesen. Exposure
19 → 22 %, drawdown enak (−38 %), holdout se opazno popravi (Sortino −0.55 → −0.29). 15–20
so vsi podobni, 18 je sredina; 20 je že malo preširok (Sharpe pade na 1.04, Calmar 0.94).

**Re-entry lock 4 → 2 (najboljši vzvod).** Hitreje nazaj v trend po izstopu. CAGR 39 → 41 %,
Calmar 1.02 → **1.19**, drawdown enak. Re-entry 3 je vmesni in slabši od obeh — kar 2 ali
pusti 4. Confirmation je že na 1, tam ni kaj rahljati.

## Kaj se NI splačalo

**Bear-regime size 50 → 60/70/80 (poslabša, ne rabimo).** Logika je obrnjena: drawdown je
kontroliran *ravno zato ker* v bear trgu zmanjšamo pozicijo. Če to rahljamo, večamo
izpostavljenost točno takrat ko ne smemo. Calmar monotono pada (1.02 → 0.96 → 0.91 → 0.87)
in holdout (ki JE bear market) gre navzdol (Sortino −0.55 → −0.68). Pusti na 50.

To se vidi tudi pri kombinaciji: "Agresivno" z bear=70 potisne MaxDD na −42 % in Sharpe na
1.03, medtem ko "Priporočeno" (isto ampak bear ostane 50) drži MaxDD −38 % in je boljše.

## Priporočilo: trailing 18, re-entry 2, bear-cut ostane 50

CAGR 39 → 40 %, Calmar 1.02 → 1.08, drawdown isti −38 %, holdout jasno boljši.

Ena poštena stvar: **Sharpe in Sortino gresta malo dol** (1.13 → 1.07 in 1.83 → 1.68). To je
pričakovano — več agresije = več tradov in izpostavljenosti, kar doda volatilnost malo
hitreje kot donos. Torej žrtvuješ malo "donosa na enoto volatilnosti" za več surovega CAGR-a
in boljši drawdown-adjusted. Za agresivni tier je to smiselno; če bi ciljali maksimalen
Sharpe, ne bi.

Realno: skok je majhen, ne dramatičen — exposure ostane ~22 %. Strategija je po zasnovi
večino časa iz trga. Za bistveno večjo izpostavljenost bi morali rahljati **entry pogoje**
(trackline / momentum), ne le exit in sizing. To je večja sprememba, jo lahko testiram
posebej.

Opomba: 12 in 4 sta iz Pine scripta, tako da če to sprejmemo, popravim še Pine da se ujemata.
