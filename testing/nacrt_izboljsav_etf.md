# Kako izboljšati obe knjigi: diagnoza in načrt

Stanje 3. septembra 2026. Podlaga so meritve iz `porocilo_nacrt_etf.md` in
`porocilo_etf_podatki_davek.md` ter pregled strokovne literature.

---

## Del 0: povzetek

**Diagnoza ni v nastavitvah, je v razpršitvi.** Carver poroča, da trendna
knjiga s 100 instrumenti doseže učinek približno **dvajsetih neodvisnih stav**,
dolgo-le postavitev pa le **štirih**. Man Group meri, da se uspešnost trendnega
sledenja izboljšuje do **40–60 trgov** in tam nasiti. Tvoja knjiga ima izmerjeni
IDM 1,04 in 1,53, kar je **1,1 oziroma 2,3 neodvisne stave**. Poskušava
strategijo, ki potrebuje dvajset stav, z eno.

To pojasni vse izmerjeno: strategija izgubi proti statičnemu deležu z isto
izpostavljenostjo, zajem navzgor je nižji od zajema navzdol, in 135 nastavitev
ne da ničesar, kar bi preživelo popravek za število poskusov.

**Zato izboljšava ni v signalu, ampak v sestavi.** Najboljša izmerjena
sprememba tega kroga ne trguje ničesar:

| P1, 7,7 let | IDM | letno | Sharpe | Sortino | MaxDD | Calmar |
|---|---|---|---|---|---|---|
| P1 kot je | 1,04 | 13,91 % | 0,85 | 1,18 | −34,4 % | 0,40 |
| P1 + 10 % zlata | 1,13 | 14,48 % | 0,94 | 1,31 | −31,7 % | 0,46 |
| P1 + 10 % zlata + 5 % blaga | 1,16 | 14,39 % | 0,96 | 1,33 | −31,0 % | 0,46 |
| **P1 + 20 % zlata** | **1,21** | **14,94 %** | **1,03** | **1,43** | **−29,0 %** | **0,51** |

Višji donos, višji Sharpe **in** plitvejši padec. Vsak trendni kandidat doslej
je donos zamenjal za padec; ta ga ne.

**Opozorilo, ki gre zraven in ni formalnost:** zlato je imelo v tem oknu
izjemen tek. Preden to postane priporočilo, mora skozi protokol faz in bločni
bootstrap, tako kot vse drugo. Zaenkrat je to **najbolj obetavna posamična
sprememba, ne ugotovitev**.

---

## Del 1: kaj profesionalci dejansko delajo

### 1a. Trendno sledenje je igra razpršitve, ne igra pravila

| vir | kaj pravi | kaj to pomeni za nas |
|---|---|---|
| [AQR, Time Series Momentum](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum) | Dolgo/kratko na **58 terminskih pogodbah** — delniški indeksi, valute, blago, državne obveznice — velikost pozicije obratno sorazmerna z volatilnostjo | Mi imamo 4 do 6 močno koreliranih delniških skladov, samo dolgo, brez terminskih pogodb |
| [AQR, Trends Everywhere](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-Trends-Everywhere_JOIM.pdf) | Razpršena 12-mesečna TSMOM z več instrumenti da bruto Sharpe okoli 1,6 | Naša najboljša različica na World da 0,53 |
| [Carver](https://qoppac.blogspot.com/2023/03/i-got-more-than-99-instruments-in-my.html) | 100 instrumentov ≈ 20 neodvisnih stav, dolgo-le ≈ 4. Sam trguje 35 pogodb iz univerzuma 250 | Naši knjigi imata 1,1 in 2,3 |
| [Man Group](https://www.man.com/insights/trend-following-optimal-market-mix) | Uspešnost raste do 40–60 trgov in se tam nasiti | Pod tem je razlika večinoma šum |
| [Man Group, vpliv ciljanja volatilnosti](https://www.man.com/insights/the-impact-of-volatility-targeting) | Ciljanje volatilnosti dvigne Sharpe pri **tveganih sredstvih** (delnice, krediti) prek učinka finančnega vzvoda; pri obveznicah, valutah in blagu je učinek **zanemarljiv** | Natanko naša meritev: P1 dokazan učinek na padec, P2 d MaxDD **+0,0** |

Zadnja vrstica je vredna pozornosti. Moja meritev, da ciljanje volatilnosti na
P2 ne naredi ničesar, ni bila naključje niti napaka — je točno tisto, kar
literatura napove za obvezniško knjigo.

### 1b. Trend deluje v dolgih krizah, ne v hitrih popravkih

[Raziskava o kriznem alfi](https://www.sciencedirect.com/science/article/abs/pii/S1057521922000242)
in [praktiki](https://www.returnstacked.com/managed-futures-trend-following/):
trendno sledenje je najbolj zanesljivo v **dolgotrajnih krizah**, mešano pri
delniških popravkih in praviloma negativno pri obvezniških.

Naše okno 2019–2026 je imelo hitre padce v obliki črke V (covid: −34 % v 33
dneh) in en obvezniški padec (2022). To je najslabša možna kombinacija za
trend, in razlaga, zakaj je v mojem 27-letnem testu pravilo zmagalo v 18 od 18
padajočih faz, a v 0 od 19 rastočih.

### 1c. Dvojni momentum ni izhod

[Antonaccijev GEM](https://quant4free.com/analysis/dual-momentum/) po objavi
zaostaja za navadnim 60/40, prednost pri padcu je bila v veliki meri zgodba
leta 2008, in ker gre za 100 % v eno sredstvo, je izjemno občutljiv na
specifikacijo. Kodo za `dual_book` sem napisal in je namenoma nisem pognal kot
rezultat; ta literatura je razlog, da naj ostane tako.

### 1d. Uravnavanje ima izmerljivo premijo, a le pri nizki korelaciji

[ReSolve](https://investresolve.com/maximizing-the-rebalancing-premium/) meri
premijo uravnavanja 1,2 % do 2,3 % na leto, in navaja pravilo, ki je za nas
odločilno: **večja kot je korelacija med sredstvi, manjša je premija.** Pri
IDM 1,04 v P1 premije skoraj ni. Pri P2 je.

Isti vir: **sprožilno uravnavanje (pasovi) je učinkovitejše od koledarskega in
ima nižje stroške.** Tvoja altcoinska kampanja je pas zavrnila, a to je bilo na
kriptu in brez davka.

---

## Del 2: kaj izboljšati, po vrsti

### Stopnja 1 — sestava knjige. Brez trgovanja, največji izmerjen učinek.

**1.1 Dodaj pravi razpršilec v Portfelj 1.**
Meritev je v povzetku. IDM 1,04 → 1,21, Sharpe 0,85 → 1,03, padec −34,4 % →
−29,0 %, donos gor. Vzrok je preprost: korelacija World–Quality je 0,98,
World–SmallCap 0,92, zato četrti delniški rokav ne doda ničesar, zlato pa
korelira 0,17.

*Kaj je treba narediti, preden to postane priporočilo:* protokol faz, bločni
bootstrap proti sedanjemu P1, in test brez leta 2024–2025, ker je zlato takrat
imelo izjemen tek. Če prednost izgine brez enega obdobja, je to isto kot
stopnjevanje pri altcoinih, ki je izginilo brez leta 2020.

**1.2 Vprašanje, ki ga je treba postaviti P1.** Če je P2 boljši izdelek na vseh
merah — Sharpe 0,99 proti 0,77, Calmar 0,46 proti 0,36 — potem P1 ni "bolj
agresivna različica", ampak **slabše sestavljena knjiga**. Prava izbira med
njima ni po tveganju, ampak po tem, ali je P1 sploh smiseln, ko obstaja P2 z
vzvodom ali brez.

### Stopnja 2 — kupi profesionalno različico, namesto da jo posnemava

**2.1 Sklad, ki dela to, kar mi ne moremo.** V Evropi so od 2025 na voljo
UCITS ETF-ji za upravljane terminske posle:
[iMGP DBi Managed Futures UCITS ETF](https://hedgenordic.com/2025/03/europe-gets-its-managed-futures-ucits-etf-with-imgp-dbi-launch/)
na Xetri, Euronextu in LSE, TER 0,75 %; Man Group je registriral
[Man Active Trend UCITS ETF](https://www.etfstream.com/articles/hedge-fund-man-group-registers-signature-trend-following-etf-in-europe).

To je trendno sledenje na 40+ trgih, dolgo in kratko, z vzvodom prek terminskih
pogodb — torej natanko tisto, česar s štirimi delniškimi ETF-ji ni mogoče
sestaviti. 5 do 15 % knjige tam da krizni alfa, ki ga naš sloj ne more.

*Pošteni ugovori, ki gredo zraven:* TER 0,75 % je desetkratnik IWDA; DBi
posnema donose sklada skladov, torej je drugoreden; zgodovina v UCITS obliki je
kratka; in za INR skoraj gotovo ni primeren. Preveriti je treba tudi, ali je
sploh dostopen prek tvojega posrednika.

**2.2 Kako bi to sodil.** Ne po zaledju sklada, ampak po tem, kaj naredi tvoji
knjigi: IDM pred in po, padec v 2020 in 2022, in ali prestane protokol faz kot
dodatek k P2.

### Stopnja 3 — politika uravnavanja, kjer je davek največji

**3.1 Uravnavaj z novimi vplačili, ne s prodajami.** Izmerjeno: 0 € proti
1.742 € (letno) in 2.208 € (četrtletno) davka v tem oknu. Vsaka prodaja poleg
tega ponastavi uro dobe imetja.

**3.2 Sprožilni pasovi namesto koledarja.** Literatura pravi, da so
učinkovitejši in cenejši. Test: pas 20 % relativno od cilja proti mesečnemu,
četrtletnemu in letnemu koledarju, ocenjen **po davku**, ne pred njim.

**3.3 Premijo uravnavanja izmeri, ne predpostavi.** V tem oknu je uravnavanje
P2 **škodilo** (8,06 % brez proti 6,76 % letno), ker so delnice zanesle navzgor.
To je nasprotno od tega, kar napove teorija, in razlog je smer okna. Meritev
mora teči na podaljšani mesečni zgodovini do 2008.

### Stopnja 4 — obvladovanje tveganja, ki je dokazano, a je gumb in ne izboljšava

**4.1 Ciljanje volatilnosti samo na delniškem delu, ne na celi knjigi.**
Literatura in meritev se ujemata. Novo izmerjeno na delniškem delu P2:

| različica | letno | Sharpe | MaxDD | d MaxDD |
|---|---|---|---|---|
| P2 kot je | 7,01 % | 0,99 | −16,0 % | referenca |
| ciljanje 10 % samo na delnicah | 5,11 % | 0,90 | −13,1 % | **+2,9 dokazano** |
| ciljanje 12 % samo na delnicah | 5,53 % | 0,91 | −14,4 % | +1,6 nedokazano |
| ciljanje 15 % samo na delnicah | 5,78 % | 0,88 | −16,0 % | +0,0 |

Padec dokazano plitvejši pri 10 %, Sortino nedokazan pri vseh. Isti vzorec kot
povsod: **dokazan zmanjševalec padca, nedokazan izboljševalec donosa.**

---

## Del 3: česa NE delati, in zakaj

| ne to | dokaz |
|---|---|
| **prilagajati parametre trendne strategije** | 135 nastavitev, najboljši Sharpe 0,529, pričakovani največji iz 135 poskusov brez učinka 0,471, popravljena verjetnost 0,585 pri pragu 0,95 |
| **iskati boljše merilo (Sortino namesto Sharpa)** | povprečni prenos razvrstitve +0,216 proti +0,219, razlika v tretji decimalki |
| **dvojni momentum med knjigama** | po objavi zaostane za 60/40, prednost je zgodba leta 2008 |
| **ciljanje volatilnosti na celi knjigi P2** | d MaxDD +0,0 pri vsaki nastavitvi brez vzvoda; z vzvodom značilno slabše |
| **uteži po obratni volatilnosti na P2** | d Sortino −0,40 [−0,75, −0,11], značilno slabše |
| **dodajati četrti delniški rokav v P1** | korelacija z World je 0,92 do 0,98, IDM se ne premakne |
| **pogosteje uravnavati** | vsaka prodaja je davčni dogodek in ponastavi uro dobe imetja |

---

## Del 4: kako bi vsako od tega sodil

Merilo ostane isto in je strožje od običajnega:

1. **Statični delež z isto izpostavljenostjo** kot glavna ovira. To je test, ki
   ga je sedanja strategija padla, in noben kandidat ga ne sme obiti.
2. **Protokol faz**: zmaga v večini rastočih **in** padajočih faz.
3. **Vezani bločni bootstrap**, isti bloki iz obeh serij. Interval z ničlo ni
   rezultat.
4. **Po davku in po unovčenju**, ne le pred njim.
5. **Odstranitev enega obdobja**: če prednost izgine brez enega leta, je krhka.
6. **Popravek za število poskusov**, če se preizkuša več kot ena različica.

---

## Del 5: kaj rabim od tebe

| vprašanje | zakaj je moje ni | posledica |
|---|---|---|
| **Ali smeš spremeniti sestavo knjige?** | dodajanje zlata v P1 je odločitev o naložbi, ne o signalu | brez tega ostane samo stopnja 3 in 4, torej robovi |
| **Ali je P1 sploh potreben, če obstaja P2?** | P2 je boljši na vseh merah v tem oknu | če je P1 tam zaradi višjega pričakovanega donosa, je pravi pogovor o vzvodu in ne o časovni izbiri |
| **Je posrednik dostopen za UCITS CTA sklad?** | ne vem, kaj ti je na voljo | odloči, ali je stopnja 2 sploh izvedljiva |
| **Ali redno dodajaš kapital?** | od tega je odvisna celotna davčna politika uravnavanja | z vplačili je davek uravnavanja nič |
| **Kakšno je obzorje?** | pod 5 let in nad 15 let sta drugačna izdelka | spremeni, katera stopnja je sploh smiselna |

---

## Del 6: vrstni red, če bi delal jaz

1. **Zlato v P1 skozi protokol.** Največji izmerjen učinek, nič trgovanja, en
   dan dela. Če pade na protokolu, pade pošteno.
2. **Uravnavanje z vplačili in sprožilni pasovi, ocenjeno po davku.** Drugi
   največji učinek, in edini, ki je gotov, ker je davek aritmetika in ne napoved.
3. **Premija uravnavanja na podaljšani zgodovini do 2008.** Odgovori, ali je
   letno uravnavanje v tem oknu škodilo iz strukturnega razloga ali zaradi smeri.
4. **UCITS CTA sklad kot dodatek k P2**, če je dostopen. Edini način, da v
   knjigo pride razpršitev, ki jo trend zares potrebuje.
5. **Ciljanje volatilnosti na delniškem delu, kot gumb** — samo če se odločiš,
   da hočeš plitvejši padec in veš, koliko donosa to stane.
6. **Trendne strategije ne pilim več.** Ni napačna nastavitev, je napačna
   družina za to število instrumentov.

---

# Dodatek, 4. september 2026: dve osnovni postavki, ki nista bili izbrani

Vprašanje „je normalno, da se gotovina obrestuje?" je odkrilo, da sta v modelu
dve predpostavki, ki nista bili odločitev, ampak dediščina. Obe sta zdaj
preizkušeni: `testing/scripts/etf_gotovina_uravnavanje.py`.

## A. Gotovina

### Kaj je standard

Stroka meri strategije v **presežnih donosih nad netvegano mero**. Sharpe je
tako definiran, AQR-jev TSMOM tako meri, in netvegana mera se v praksi
nadomesti z donosom kratkoročnih državnih papirjev. Pripisati gotovini nič torej
**ni konservativno**, je samo druga predpostavka.

### Kaj je dejansko dosegljivo

Tu si imel prav, da si podvomil. Odvisno je od posrednika:

| kje | kaj plača |
|---|---|
| DEGIRO | **0 %** na evrsko gotovino |
| Interactive Brokers | plača, a **ne na prvih 10.000 EUR**, in po nižji stopnji pod 100.000 EUR premoženja |
| denarni sklad (XEON, C3M) | mero ECB minus TER 0,10 % |

### Izmerjeno: denarni sklad res dela to, kar obljublja

| leto | XEON | mera ECB | razlika |
|---|---|---|---|
| 2021 | −0,59 % | −0,57 % | −0,02 pp |
| 2023 | +3,28 % | +3,21 % | +0,08 pp |
| 2024 | +3,72 % | +3,64 % | +0,07 pp |
| 2025 | +2,21 % | +2,18 % | +0,03 pp |

**Past, ki jo je vredno poznati:** distribucijski denarni skladi (XEOD, ERNE,
PJS1) imajo v ceni skoraj ničelni donos, ker se donos izplača. XEOD je v 2024
po ceni naredil −0,02 % namesto +3,64 %. Kdor bi vzel njihovo ceno kot donos
gotovine, bi si pripisal nič.

### In odgovor, ki šteje: na sklep to ne vpliva

| P1, v trgu 73 % | strategija | statični delež | razlika |
|---|---|---|---|
| gotovina 0 % | 7,17 % | 10,03 % | **−2,86** |
| mera ECB minus TER | 7,37 % | 10,34 % | **−2,97** |
| mera ECB | 7,40 % | 10,38 % | **−2,97** |

Ker **tudi merilo drži gotovino**, se obe strani premakneta enako. Razlika ostane
skoraj nespremenjena. Isto na P2 (−0,71 proti −0,82).

**Sklep:** obrestovanje gotovine je standard, upravičeno je, če gotovino
dejansko kupiš kot XEON, in **na nobeno dosedanjo sodbo ne vpliva**. Vprašanje
je bilo pravo, odgovor pa je, da je ta vzvod majhen.

## B. Uravnavanje

Koledar je bil izbran brez razloga. Stroka priporoča prage: Swedroejevo pravilo
**5/25** (rokav s ciljem nad 20 % sproži ob odmiku 5 odstotnih točk, rokav pod
20 % ob 25 % relativno), Vanguard meri prednost pragovnega pristopa okoli
**15 do 25 bazičnih točk na leto** proti mesečnemu koledarju.

### Portfelj 1, 8,4 leta

| politika | poslov | letno | MaxDD | **po davku** | davek |
|---|---|---|---|---|---|
| **nikoli** | 1 | 12,24 % | −34,4 % | **10,31 %** | **0 €** |
| **pas 5/25** | **2** | 12,19 % | −34,4 % | **10,21 %** | 759 € |
| letno | 9 | 12,22 % | −34,4 % | 10,16 % | 1.573 € |
| četrtletno | 34 | 12,17 % | −34,4 % | 10,13 % | 2.104 € |
| mesečno | 103 | 12,18 % | −34,4 % | 10,08 % | 3.718 € |

### Portfelj 2, 7,7 leta

| politika | poslov | letno | MaxDD | **po davku** | davek |
|---|---|---|---|---|---|
| **nikoli** | 1 | 8,22 % | −16,6 % | **6,77 %** | **0 €** |
| **pas 10/50** | 3 | 7,31 % | −16,6 % | **5,94 %** | 3.730 € |
| pas 5/25 | 8 | 7,12 % | −16,6 % | 5,63 % | 2.499 € |
| letno | 8 | 6,94 % | −15,6 % | 5,57 % | 3.479 € |
| mesečno | 94 | 6,78 % | −15,7 % | 5,28 % | 5.097 € |

### Tri ugotovitve

**1. Pragovi premagajo koledar, in Vanguardova številka se potrdi.** Na P1 da
pas 5/25 po davku 10,21 % proti 10,08 % za mesečno, torej **13 bazičnih točk**;
na P2 5,63 % proti 5,28 %, torej **35 bazičnih točk**. Vanguard napove 15 do 25.
Pri tem pas na P1 potrebuje **2 posla namesto 103**.

**2. Mesečno uravnavanje je najslabše povsod.** Največ davka, nič koristi.
Če se ena stvar spremeni takoj, naj bo to.

**3. Neuravnavanje je v tem oknu zmagalo — a to je past.** Delnice so zanesle
navzgor, zato je drift plačal. Dvoje govori proti temu, da bi to postalo
pravilo:

- Knjiga brez uravnavanja se počasi spremeni v 100 % tistega, kar je zmagalo,
  in s tem izgine razlog, zakaj si si razporeditev sploh izbral. Na P2 se je
  padec poglobil s −15,6 % na −16,6 %.
- Premija uravnavanja je po literaturi realna (1,2 do 2,3 % na leto), a je
  **odvisna od nizke korelacije** — in nastane v obdobjih, ko se sredstva
  izmenjujejo, ne v enosmernem oknu. 7,7 leta z eno smerjo tega ne more pokazati.

**Kar iz tega sledi:** pas 5/25 ali 10/50 je pravi kompromis. Ohrani
razporeditev, ki si jo izbral, stane bistveno manj davka od koledarja, in ne
stavi na to, da bo drift plačal tudi naslednjič.

## C. Kaj bi torej spremenil takoj

| sprememba | učinek | koliko dela |
|---|---|---|
| mesečno → pas 5/25 | +13 do +35 bazičnih točk po davku, 2 posla namesto 103 | ena vrstica |
| gotovina → XEON | +0,2 do +0,3 pp na strategijo, nič na sodbo | en nakup |
| uravnavaj z vplačili | davek uravnavanja na nič | politika, ne koda |

Nobena od teh ni strategija. Vse tri so nastavitve, ki so bile podedovane in ne
izbrane, in skupaj so vredne več kot vse, kar je trendni sloj v tem projektu
prinesel.
