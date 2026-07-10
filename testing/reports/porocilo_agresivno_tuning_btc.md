# Momentum tuning — samo Bitcoin

Ista stvar kot prej, samo da sem tokrat testiral čisto na BTC (ne povprečje čez več coinov).
Pripomba je bila da drawdown sicer dobro držimo (−38 % proti −77 % za buy&hold), ampak da smo
za agresiven produkt premalo v trgu in preveč zaostajamo v rasti. Pogledal sem tri stvari:
trailing stop, re-entry lock in bear-cut.

Nekaj pojmov na hitro, če jih rabiš: exposure = koliko časa/kapitala smo dejansko v BTC (ostalo
v stablecoinu). Trailing stop = stop ki sledi ceni gor in te vrže ven, ko cena pade X % z vrha.
Re-entry lock = koliko dni po izstopu moraš počakati preden lahko spet vstopiš. Bear-cut =
kolikšno pozicijo držimo, ko je trg pod padajočo 200-dnevno (50 = pol). Holdout je 2025+
obdobje, ki ga pri nastavljanju nisem gledal — ločen test na svežih podatkih.

Vsaka vrstica je cela baseline strategija, spremenjen samo tisti parameter (razen COMBO, kjer
sta dva-trije). Baseline je trailing 12, re-entry 4, bear-cut 50 — tako kot v Pine.

| Nastavitev | CAGR | Exp | MaxDD | Sharpe | Sortino | Calmar | holdout CAGR / Sortino |
|---|---|---|---|---|---|---|---|
| Baseline (12/4/50) | 39% | 35% | −38% | 1.18 | 1.92 | 1.02 | −5% / −0.29 |
| trailing 8 | 36% | 31% | −33% | 1.17 | 1.92 | 1.09 | −10% / −0.69 |
| trailing 10 | 41% | 34% | −37% | 1.24 | 2.04 | 1.10 | −5% / −0.29 |
| trailing 15 | 38% | 35% | −38% | 1.16 | 1.87 | 1.00 | −5% / −0.29 |
| trailing 18 | 40% | 35% | −38% | 1.20 | 1.95 | 1.06 | −5% / −0.29 |
| trailing 20 | 40% | 35% | −38% | 1.20 | 1.95 | 1.06 | −5% / −0.29 |
| re-entry 1 | 47% | 36% | −38% | 1.31 | 2.13 | 1.23 | −5% / −0.29 |
| re-entry 2 | 47% | 35% | −38% | 1.34 | 2.20 | 1.24 | −5% / −0.29 |
| re-entry 3 | 44% | 34% | −38% | 1.29 | 2.12 | 1.15 | −5% / −0.29 |
| bear-cut 0 | 38% | 33% | −36% | 1.18 | 1.91 | 1.06 | −3% / −0.10 |
| bear-cut 25 | 39% | 34% | −33% | 1.20 | 1.95 | 1.19 | −4% / −0.20 |
| bear-cut 70 | 38% | 35% | −42% | 1.16 | 1.88 | 0.91 | −7% / −0.36 |
| bear-cut 100 | 38% | 36% | −48% | 1.12 | 1.81 | 0.79 | −8% / −0.44 |
| COMBO re-entry2 + bear25 | 47% | 35% | −33% | 1.35 | 2.24 | 1.44 | −4% / −0.20 |
| COMBO re-entry2+bear25+trail10 | 46% | 33% | −32% | 1.35 | 2.24 | 1.45 | −4% / −0.20 |
| COMBO trail18 + re-entry2 | 48% | 36% | −38% | 1.35 | 2.24 | 1.27 | −5% / −0.29 |
| COMBO trail18+re-entry2+bear70 | 48% | 37% | −42% | 1.33 | 2.19 | 1.14 | −7% / −0.36 |

## Kaj se vidi

Re-entry lock je daleč najboljši vzvod. Ko ga spustimo s 4 na 2, gre CAGR z 39 na 47 %, Sortino
z 1.92 na 2.20, Calmar z 1.02 na 1.24, in drawdown ostane isti. Re-entry 1 je praktično enak kot
2. Logika je enostavna: po izstopu se hitreje vrnemo v trend in ne zamudimo nadaljevanja. Nad 4
(baseline) je slabše.

Bear-cut naj gre navzdol, ne navzgor. Pri 25 je drawdown boljši (−33 % namesto −38 %) in Calmar
gre na 1.19. Pri 70 in 100 pa vse pade — Calmar 0.91 oz. 0.79, drawdown −42 oz. −48 %, in holdout
se pokvari. Torej predlog "daj bear-cut višje, ker DD dobro držimo" je ravno narobe: DD držimo
prav zato, ker v bear trgu zmanjšamo pozicijo. Če to odpremo, večamo izpostavljenost točno ko ne
smemo. Bear-cut 0 (poln blok) ima celo najboljši holdout.

Trailing stop tu ni pravi vzvod. 15/18/20 so bolj ali manj isti kot baseline, nad 20 se nasiti
(stop tako širok itak ne sproži). Edino trailing 10 malo pomaga (CAGR 41 %, Sortino 2.04),
tesnejši (8) pa poreže donos in pokvari holdout.

Najboljša kombinacija je re-entry 2 + bear-cut 25. CAGR 47 %, Sharpe 1.35, Sortino 2.24, Calmar
1.44, drawdown pa se celo izboljša na −33 %. Holdout je tudi boljši (−4 % / −0.20 proti −5 % /
−0.29 pri baseline). Če dodaš še tesnejši trailing (10), je skoraj isto (Calmar 1.45, DD −32 %),
tako da to ni nujno.

Ena stvar za omeniti: pri poolu čez več coinov sta Sharpe in Sortino pri teh spremembah malo
padla, tu na BTC pa gresta gor. Razlog je da BTC bolje sledi trendu kot altcoini, tako da
hitrejši re-entry na BTC ne prinese toliko lažnih vstopov. Skratka na BTC je to čist win po vseh
metrikah, ne kompromis.

Realno gledano exposure ostane okrog 35 % — te spremembe ga skoraj ne dvignejo, dvignejo pa
donos znotraj tega časa. Če bi hoteli res več biti v trgu, bi morali odpreti entry pogoje
(trackline, momentum), ne exit in sizing. To je večja sprememba, jo lahko pogledam posebej.

Trenutni 12/4/50 so iz Pine scripta, tako da če to vzamemo, popravim še Pine da se ujemata.
