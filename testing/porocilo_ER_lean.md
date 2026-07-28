# ER filter v Lean — predlog za odstranitev

*27. 7. 2026, BTC in ETH, varianta lean*

ER (Kaufman Efficiency Ratio) meri, kako raven je bil premik cene v zadnjih desetih
dneh. Neto premik deliš z vsoto vseh dnevnih premikov v istem obdobju:

$$ER_t = \frac{|C_t - C_{t-10}|}{\sum_{i=0}^{9} |C_{t-i} - C_{t-1-i}|}$$

V kodi je osmi pogoj za vstop: če je ER pod 0,30, se vstop blokira. Na izhode nima
vpliva.

| primer | pot cene v 10 dneh | števec | imenovalec | ER | vstop |
|---|---|---|---|---|---|
| čist trend | 100 → 110, +1 na dan | 10 | 10 | 1,00 | dovoljen |
| nihanje | 100 → 110 → 100 → 110 | 10 | 50 | 0,20 | blokiran |

Testiral sem na zamrznjenih posnetkih z **enega samega vira — Binance** (`testing/data/sources/`, zajeto 27. 7. 2026, z zavrženo nedokončano svečko); vir in čas zajema sta zapisana v manifestu, zato je vsak zagon ponovljiv in primerljiv z dashboardom, ki bere isti vir. Pozicija je vedno včerajšnji signal, zato pogleda naprej ni. **Vse
številke so neto stroškov pri 0,30 % na stran** po modelu `strošek = |sprememba
pozicije| × 0,30 %`; to je približno trikratnik ocene iz `fees_slippage_analysis.md`
in je izbrano namenoma konservativno. Za intervale zaupanja uporabljam parni block
bootstrap: donose mešam v blokih po dvajset dni (v kriptu se volatilnost lepi,
mešanje posameznih dni bi dalo umetno ozke intervale), isti premešani vrstni red
uporabim na obeh varianti hkrati, 2000 ponovitev, interval od 2,5. do 97,5.
percentila. Sklep se ne spremeni pri blokih od 5 do 120 dni.

| asset | okno | od | do | dni |
|---|---|---|---|---|
| BTC | vse | 2019-12-31 | 2026-07-26 | 2400 |
| BTC | 5 let | 2021-07-27 | 2026-07-26 | 1826 |
| BTC | 3 leta | 2023-07-27 | 2026-07-26 | 1096 |
| ETH | vse | 2020-01-01 | 2026-07-27 | 2400 |
| ETH | 5 let | 2021-07-28 | 2026-07-27 | 1826 |
| ETH | 3 leta | 2023-07-28 | 2026-07-27 | 1096 |

## Rezultati (neto 0,30 % na stran)

| asset | okno (od → do) | | CAGR % | Sortino | MaxDD % | Ulcer | izpost. % | obrat/leto | strošek %/leto |
|---|---|---|---|---|---|---|---|---|---|
| BTC | vse<br>2019-12-31 → 2026-07-26 | ER on | 28,2 | 1,46 | −39,8 | 20,1 | 36,0 | 4,9 | 1,46 |
|  |  | ER off | 33,9 | 1,55 | −39,8 | 19,9 | 43,5 | 5,2 | 1,55 |
| BTC | 5 let<br>2021-07-27 → 2026-07-26 | ER on | 19,5 | 1,17 | −39,8 | 20,3 | 35,7 | 4,0 | 1,20 |
|  |  | ER off | 21,6 | 1,22 | −39,8 | 20,6 | 39,9 | 4,4 | 1,32 |
| BTC | 3 leta<br>2023-07-27 → 2026-07-26 | ER on | 27,0 | 1,89 | −15,7 | 8,5 | 31,8 | 4,3 | 1,30 |
|  |  | ER off | 30,8 | 1,82 | −18,5 | 10,0 | 38,9 | 5,0 | 1,50 |
| ETH | vse<br>2020-01-01 → 2026-07-27 | ER on | 27,0 | 1,10 | −61,1 | 26,2 | 31,1 | 4,6 | 1,37 |
|  |  | ER off | 25,2 | 1,00 | −65,3 | 29,9 | 36,2 | 5,2 | 1,55 |
| ETH | 5 let<br>2021-07-28 → 2026-07-27 | ER on | 15,8 | 0,87 | −38,7 | 21,6 | 30,8 | 3,2 | 0,96 |
|  |  | ER off | 17,2 | 0,91 | −42,8 | 23,6 | 34,6 | 3,6 | 1,08 |
| ETH | 3 leta<br>2023-07-28 → 2026-07-27 | ER on | 21,6 | 1,17 | −22,5 | 16,0 | 26,6 | 3,3 | 1,00 |
|  |  | ER off | 28,4 | 1,40 | −22,5 | 16,2 | 30,1 | 3,7 | 1,10 |

95 % intervali zaupanja za razliko (ER on minus ER off), prav tako neto:

| asset | okno | ΔSortino | ΔCAGR (o. t.) | ΔMaxDD (o. t.) | značilno |
|---|---|---|---|---|---|
| BTC | vse | [−0,59, +0,51] | [−15,6, +4,1] | [−10,4, +12,7] | ne |
| BTC | 5 let | [−0,38, +0,35] | [−9,0, +3,3] | [−8,6, +8,9] | ne |
| BTC | 3 leta | [−0,66, +1,08] | [−14,5, +5,9] | [−8,5, +13,2] | ne |
| ETH | vse | [−0,38, +0,75] | [−18,0, +14,5] | [−4,5, +21,3] | ne |
| ETH | 5 let | [−0,47, +0,34] | [−13,1, +7,5] | [−5,9, +12,5] | ne |
| ETH | 3 leta | [−0,96, +0,44] | [−22,5, +7,1] | [−6,2, +12,3] | ne |

### Zakaj stroški ničesar ne premaknejo

Strategija naredi **dva do tri posle na leto**, obrat kapitala je 3,2 do 5,2 enote
letno. Pri 0,30 % na stran to pomeni letni strošek okoli 1 do 1,6 %. Ker obe
varianti trgujeta enako redko, se **razmik med njima ne spremeni**: ΔSortino se od
bruto do 0,50 % na stran premakne za največ 0,01. ER celo rahlo pridobi, ker
zmanjša obrat (BTC 4,9 proti 5,2 enote na leto, ETH 4,6 proti 5,2) — a je učinek
tako majhen, da se izgubi v zaokroževanju.

Brez mešanja, na resničnih neprekinjenih enoletnih obdobjih (korak 7 dni), delež
oken, v katerih je ER boljši oziroma slabši:

| asset | okno | metrika | ER boljši | enako | ER slabši | oken |
|---|---|---|---|---|---|---|
| BTC | vse | CAGR | 3 % | 43 % | 53 % | 291 |
| BTC | vse | MaxDD | 27 % | 70 % | 3 % | 291 |
| BTC | 5 let | CAGR | 2 % | 51 % | 46 % | 209 |
| BTC | 5 let | MaxDD | 23 % | 77 % | 0 % | 209 |
| BTC | 3 leta | CAGR | 5 % | 31 % | 64 % | 105 |
| BTC | 3 leta | MaxDD | 36 % | 64 % | 0 % | 105 |
| ETH | vse | CAGR | 41 % | 18 % | 41 % | 291 |
| ETH | vse | MaxDD | 34 % | 59 % | 8 % | 291 |
| ETH | 5 let | CAGR | 47 % | 20 % | 33 % | 209 |
| ETH | 5 let | MaxDD | 24 % | 76 % | 0 % | 209 |
| ETH | 3 leta | CAGR | 22 % | 14 % | 64 % | 105 |
| ETH | 3 leta | MaxDD | 0 % | 100 % | 0 % | 105 |

## Odločilni preizkus

ER zniža povprečno izpostavljenost za 11 do 17 odstotkov. Če ga izklopim in namesto
tega vse pozicije pomnožim s konstanto do enake povprečne izpostavljenosti, dobim
naslednje. Ključ do razlage je v zadnji tabeli: povprečen ER je v dobrih in slabih
obdobjih tako rekoč enak, na ETH je v slabih celo višji, prag 0,30 pa leži točno na
mediani porazdelitve in tako reže polovico dni ne glede na dogajanje na trgu.

| asset | okno (od → do) | faktor | | CAGR % | Sortino | MaxDD % | Ulcer |
|---|---|---|---|---|---|---|---|
| BTC | vse · 2019-12-31 → 2026-07-26 | ×0,83 | ER on | 28,2 | 1,46 | −39,8 | 20,1 |
| | | | skalirano | 28,6 | 1,55 | −33,9 | 16,6 |
| BTC | 5 let · 2021-07-27 → 2026-07-26 | ×0,89 | ER on | 19,5 | 1,17 | −39,8 | 20,3 |
| | | | skalirano | 19,7 | 1,22 | −36,2 | 18,6 |
| BTC | 3 leta · 2023-07-27 → 2026-07-26 | ×0,82 | ER on | 27,0 | 1,89 | −15,7 | 8,5 |
| | | | skalirano | 25,2 | 1,82 | −15,3 | 8,2 |
| ETH | vse · 2020-01-01 → 2026-07-27 | ×0,86 | ER on | 27,0 | 1,10 | −61,1 | 26,2 |
| | | | skalirano | 23,5 | 1,00 | −58,4 | 26,0 |
| ETH | 5 let · 2021-07-28 → 2026-07-27 | ×0,89 | ER on | 15,8 | 0,87 | −38,7 | 21,6 |
| | | | skalirano | 16,0 | 0,91 | −38,7 | 21,1 |
| ETH | 3 leta · 2023-07-28 → 2026-07-27 | ×0,88 | ER on | 21,6 | 1,17 | −22,5 | 16,0 |
| | | | skalirano | 25,5 | 1,40 | −19,8 | 14,3 |

| izid pri enaki izpostavljenosti | skaliranje zmaga | izenačeno | ER zmaga |
|---|---|---|---|
| Ulcer | **6** | 0 | 0 |
| MaxDD | **5** | 1 | 0 |
| Sortino | 2 | 2 | 2 |

| asset | p5 | p25 | mediana | p75 | p95 | dni pod 0,30 | povpr. ER v BULL | povpr. ER v BEAR |
|---|---|---|---|---|---|---|---|---|
| BTC | 0,03 | 0,13 | **0,29** | 0,49 | 0,76 | 52 % | 0,35 | 0,32 |
| ETH | 0,03 | 0,15 | **0,30** | 0,47 | 0,75 | 50 % | 0,32 | 0,34 |

## Sklep

Predlagam odstranitev `use_er` in `er_thresh`. Argument ni, da ER škodi, ampak da se
ne izplača: prinese dva parametra, v zameno pa nič merljivega. Poštena omejitev je,
da je statistična moč majhna, pet do šest poslov na sredstvo v zadnjih treh letih,
zato bi bilo mogoče zaznati šele razliko okoli pol Sortino točke. Prav zato sklep
naslanjam na mehanizem in na preizkus s skaliranjem, ne na uspešnost v posameznem
obdobju.

| # | argument | dokaz |
|---|---|---|
| 1 | ne meri tega, kar trdi | povprečen ER v BULL 0,35 proti 0,32 v BEAR (BTC); 0,32 proti 0,34 (ETH) |
| 2 | prag je poljuben | 0,30 je mediana porazdelitve, reže 51–52 % dni |
| 3 | koristi ni mogoče izmeriti | vseh 18 intervalov zaupanja vsebuje ničlo |
| 4 | preprostejša rešitev je boljša | pri enaki izpostavljenosti skaliranje zmaga na Ulcerju 6 : 0 in na MaxDD 5 : 0 (enkrat izenačeno) |
| 5 | stane donos | na BTC boljši le v 3–5 % resničnih letnih oken, slabši v 46–65 % |
| 6 | dva odvečna parametra | večja prostost prilagajanja brez merljivega donosa |
