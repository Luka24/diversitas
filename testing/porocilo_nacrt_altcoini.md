# Kako izboljšati lean na altcoinih

Stanje 31. avgusta 2026.

---

## Povzetek

Dve ločeni ugotovitvi, ki sem ju prej mešal.

**Strategija dela.** Proti statičnemu deležu BTC z isto povprečno
izpostavljenostjo, 38,4 %, je lean boljši na vsaki osi: Sharpe 1,35 proti 1,09,
Sortino 2,20 proti 1,63, končna vrednost 101x proti 14x, pri praktično enakem
najhujšem padcu. Po datiranih fazah zajame 34 % rasti BTC in samo 32 % padcev,
statični delež pa 23 % rasti in 45 % padcev. To je merljiva veščina izbire
trenutka, ne le manj izpostavljenosti.

**Izboljšati je ne znam.** Preizkusil sem devetnajst kandidatov skozi protokol,
ki zahteva zmago v rastočih **in** padajočih fazah. Sprejet ni bil noben.

**Ena stvar ima dokaz, in ni izboljšava, ampak menjava.** Ciljanje volatilnosti,
ki ga uporabljajo vsi profesionalci in ga mi nimamo, edino doseže interval, ki
izključuje ničlo v pravo smer. Ne pri donosu, pri **najhujšem padcu**. Zahteva
pa nebinarne pozicije, kar je proti tvoji zahtevi. Deli 1d in 1e.

**Znotraj binarne omejitve ni ostalo nič.** Deset binarnih kandidatov, nič
sprejetih. Dva sta značilno **slabša** in ju velja poznati: tedensko namesto
dnevnega ukrepanja (−0,53 Sortina, padec −44 % namesto −28 %) in prelivanje
denarja v BTC ob izstopu (padec značilno globlji za 15,5 točke). Del 1f.

To vključuje uteži po tveganju, ki sem jih v prejšnji različici tega poročila
priporočil. Ko sem jih preveril z bootstrapom, se je pokazalo, da razlika ni
ločljiva od šuma. Priporočilo umikam, razlogi so v delu 3.

Pomembnejše od tega je pojasnilo, ki se je izluščilo iz literature. Verjetno
ne gre za to, da še nismo našli pravega pravila. Gre za dvoje, česar noben
poseg v pravila ne more popraviti:

**Volatilnost BTC se je prepolovila.** V treningu 70 % letno, danes 38 %.
Trendna strategija na sredstvu, ki niha polovico manj, ne more dati istega,
kar je dajala prej. To je aritmetika, ne odpoved.

**Celotna trendna panoga je imela najslabše obdobje v 25 letih.** SG Trend
Index je od maja 2024 do maja 2025 padel za 20,4 %, kar je njegov drugi
najhujši padec od začetka leta 2000. Naš hold-out se začne aprila 2025, torej
sredi tega.

Načrt se zato preusmeri od iskanja boljšega pravila k merjenju dveh stvari v
živo, ki ju danes ugibamo.

---

## Del 0: vse preizkušeno na enem mestu

Približno 56 nastavitev, 20 ločenih zamisli. Razvrščeno po tem, kako trden je
dokaz, ne po vrstnem redu preizkušanja.

### Dokazano boljše, a le pri padcu, in zahteva nebinarne pozicije

| zamisel | najboljša številka | dokaz |
|---|---|---|
| ciljanje volatilnosti, BTC, cilj 30 % | padec −45 % postane −18 % | **d MaxDD +23,7 [+11,5, +38,5]** |
| ciljanje volatilnosti, knjiga, hierarhično | padec −28 % postane −16 % | **d MaxDD +13,1 [+5,6, +23,0]** |
| hierarhično + IDM, brez vzvoda | padec −28 % postane −21 % pri enakem donosu | d Sortino +0,41 [−0,05, +0,92], za las ne |

Nobena ne prestane protokola faz, ker v rastočih fazah izgubijo. Vse zahtevajo
delne pozicije.

### Zanimivo, a nedokazano

| zamisel | številka | zakaj ne |
|---|---|---|
| samo tri sredstva, enake uteži | Sharpe 1,53 proti 1,47, Sortino 2,48 proti 2,28 | C1 le 1 od 4, interval +0,19 [−0,37, +0,78] |
| stopnjevana velikost k≥2, BTC | Sortino 2,54 proti 2,20, konec 123x proti 101x | interval [−0,26, +0,91], brez leta 2020 ostane +0,10, na validaciji ničelno **že pred stroški** |
| večinsko glasovanje ≥3 od 5 | 4 od 4 rastočih faz | Sharpe 1,43 proti 1,47, skupno nevtralno |

### Nevtralno, potrjeno kot že pravilno

| zamisel | ugotovitev |
|---|---|
| hitrost izstopa | 1 do 5 dni da 2,01 / 2,08 / **2,22** / 2,16 / 1,77. Današnja 3 je vrh platoja |
| trajno dno 0, 5, 10 % | 2,20 / 2,22 / 2,24, po oknih izenačeno. Deluje kot gumb proti kupi in drži |
| ansambel Donchianov | validacija 2,49 proti 2,47, hold-out izenačen. Petkratna zapletenost za nič |
| pas brez trgovanja | na validaciji vrh 1,78, na hold-outu 0,20. Past |

### Zavrnjeno z dokazom, da je slabše

| zamisel | dokaz |
|---|---|
| **ukrepaj tedensko namesto dnevno** | d Sortino **−0,53 [−1,08, −0,04]**, padec −44 % namesto −28 % |
| **denar ob izstopu v BTC** | d MaxDD **−15,5 [−24,7, −6,8]**, izpostavljenost se podvoji |
| **glasovanje s soglasjem vseh petih** | d Sortino **−0,51 [−1,01, −0,04]** |
| **ansambel obojega, 25 specifikacij** | d zložen [−100918, −144], v celoti negativen |
| Zarattini Combo kot celota | d zložen [−154558, −178], v celoti negativen |

### Zavrnjeno, ker ne prenese na naše podatke

| zamisel | številka |
|---|---|
| širina univerzuma | hold-out 3 kovanci 0,77, 30 kovancev **−0,24**, monotono slabše |
| uteži po tveganju | vsi intervali vsebujejo ničlo, drseče leto 38 / 43 / 50 % |
| statične uteži po tveganju | hold-out P(boljši) 22 % |
| enake uteži namesto 50/10 | Sharpe 1,25 proti 1,47 |
| ukrepaj mesečno | Sharpe 1,07 proti 1,47 |
| knjižno stikalo po BTC | 0 od 4 rastočih faz |
| ansambel tracklinov | knjiga hold-out 0,55 proti 0,75 |
| nadaljnje prilagajanje parametrov | gnezdeni walk-forward: razlika **točno 0,00** |
| zunanji podatkovni viri | makro vrata se sprožijo na 11 od 2600 dni |

---

## Del 1: kako berem te tabele

Preskoči, če ti je znano.

### Tri okna

| okno | obdobje | čemu služi |
|---|---|---|
| **trening** | do 30. 6. 2023 | tu se ideja rodi. Dober rezultat tukaj ne pomeni skoraj nič |
| **validacija** | 1. 7. 2023 do 31. 3. 2025 | tu se **odloči**. Edino okno, na katerem se sme izbirati |
| **hold-out** | od 1. 4. 2025 | pogleda se enkrat, kot potrditev |

### Interval zaupanja, in zakaj je odslej povsod

To je najpomembnejša sprememba v tem poročilu.

Če eno različico premaga druga za 0,3 Sortina, to samo po sebi ne pove nič.
Vprašanje je, ali bi se ista razlika pojavila tudi, če bi bili obe enako dobri
in bi šlo le za srečo pri razporeditvi dobrih in slabih obdobij.

**Vezani bločni bootstrap** to odgovori. Iz zgodovine se 5000-krat naključno
sestavi nadomestna zgodovina, v blokih po 20 dni, da se ohrani zaporedje, in za
vsako se izračuna razlika. Iz porazdelitve teh 5000 razlik se dobi interval.

Pravilo branja je preprosto:

> **Če interval vsebuje ničlo, razlika ni dokazana.**

Vse do zdaj v tem projektu je bilo primerjano brez tega. Zato sta v tem krogu
padla dva kandidata, ki sta prej izgledala dobro.

### Številke

| oznaka | pomen |
|---|---|
| Sharpe | donos na enoto nihanja |
| Sortino | isto, a šteje le nihanje navzdol |
| MaxDD | najhujši padec od vrha do dna |
| izpostavljenost | delež časa v trgu |

Past: vsaka sprememba, ki te manj časa drži v trgu, sama po sebi polepša MaxDD
in Sortino. Zato je izpostavljenost povsod navedena.

**In druga past, ki jo je odkril ta krog:** ko je povprečen donos negativen, se
Sortino obrne. Pri isti izgubi dobiš **manj** negativno številko, če bolj niha.
Zato se v obdobjih, kjer se izgublja, primerja zložena izguba, nikoli razmerja.

---

## Del 1b: ocena po fazah cikla, ne le na hold-outu

Trojna delitev odgovarja na vprašanje "ali sem izbiral pošteno". **Ne** odgovarja
na vprašanje "ali to dela tudi v padcu", ker vsako od treh oken vsebuje mešanico
faz.

Delitev po 200-dnevnem povprečju, ki sem jo uporabljal doslej, je za to
premalo: meja se križa sem in tja, faze so razdrobljene, in kratek prehod se
šteje enako kot dvoletni medvedji trg.

### Kako to delajo profesionalci

Akademski standard je algoritem **Bry in Boschan (1971)** v različici **Pagan in
Sossounov** za finančne trge:

1. najdi lokalne vrhove in dna v oknu ± K dni
2. vsili izmenjavanje: za vrhom mora priti dno
3. vsili najkrajšo dolžino faze, da se odstrani šum
4. vsili najmanjšo amplitudo, da se odstranijo nepomembni premiki

Nastavitve, prilagojene kriptu: K = 90 dni, najkrajša faza 120 dni, najmanjša
amplituda 25 %. Meja ni ročno izbrana in je ponovljiva.

### Datirane faze BTC

| vrsta | od | do | dni | BTC |
|---|---|---|---|---|
| padec | 2017-12-16 | 2018-12-15 | 364 | **−84 %** |
| **rast** | 2018-12-15 | 2019-06-26 | 193 | **+306 %** |
| padec | 2019-06-26 | 2020-03-12 | 260 | −62 % |
| **rast** | 2020-03-12 | 2021-04-13 | 397 | **+1209 %** |
| padec | 2021-04-13 | 2022-11-21 | 587 | −75 % |
| **rast** | 2022-11-21 | 2024-03-13 | 478 | **+364 %** |
| padec | 2024-03-13 | 2024-09-06 | 177 | −26 % |
| **rast** | 2024-09-06 | 2025-01-21 | 137 | **+97 %** |
| padec | 2025-01-21 | 2026-02-05 | 380 | **−41 %** |

Štiri rastoče faze, 1205 dni. Pet padajočih, 1768 dni.

### Prva ugotovitev: hold-out je bil padajoča faza

Hold-out se začne 1. aprila 2025 in leži **v celoti znotraj zadnje padajoče
faze**, v kateri je BTC izgubil 41 %.

Šibki hold-out torej ni dokaz, da je s strategijo nekaj narobe. V tej fazi je
lean izgubil **5 %, medtem ko je BTC izgubil 41 %.** To ni odpoved, to je
opravljena naloga.

Nizek Sharpe v padajoči fazi je pričakovan, ker ni česa zajeti.

### Druga ugotovitev: proti statičnemu deležu

Najbolj pošteno merilo, ki ga doslej nisem naredil. Lean je v povprečju v trgu
38,4 % časa. Kaj bi dobil, če bi preprosto ves čas držal 38 % v BTC in ostalo v
gotovini, brez signala in brez trgovanja?

| cela zgodovina | Sharpe | Sortino | CAGR | MaxDD | konec |
|---|---|---|---|---|---|
| **lean, danes** | **1,35** | **2,20** | **55 %** | −45 % | **101x** |
| statično 38 % BTC | 1,09 | 1,63 | 28 % | −46 % | 14x |
| BTC kupi in drži | 1,09 | 1,63 | 66 % | −84 % | 212x |

Pri **enakem najhujšem padcu** je lean 101x proti 14x. To je prava veščina, ne
posledica manjše izpostavljenosti.

Po datiranih fazah, povprečen donos na fazo:

| | rastoče faze | padajoče faze |
|---|---|---|
| **lean, danes** | **+122 %** | **−18 %** |
| statično 38 % BTC | +83 % | −25 % |
| BTC kupi in drži | +361 % | −55 % |

Ta primerjava ne potrebuje nobenega imenovalca: **lean dobi več v rasti in izgubi
manj v padcu** kot statični delež z isto povprečno izpostavljenostjo.

Če to prevedeš v deleže zajema, merjeno proti kupi in drži na istem indeksu:

| | zajame rasti | zajame padcev |
|---|---|---|
| **lean** | **34 %** | **32 %** |
| statično 38 % | 23 % | 45 % |

**To je izdelek, in ta del deluje.** Kar ne deluje, je vsak poskus, da bi ga
izboljšal.

### Tretja ugotovitev: kje se plačajo provizije

To v dashboardu doslej ni bilo razčlenjeno. Povprečne provizije na fazo,
odstotek kapitala:

| kandidat | rastoča faza | padajoča faza | razmerje |
|---|---|---|---|
| **osnova, danes** | 1,71 % | **0,74 %** | **0,43** |
| ansambel tracklinov | 1,71 % | 0,96 % | 0,56 |
| ansambel Donchianov | 1,75 % | 1,04 % | 0,60 |
| **stopnjevanje k≥2** | 4,65 % | **3,51 %** | **0,75** |

Današnja oblika v padajočih fazah trguje **manj kot polovico** tega, kar trguje
v rastočih. To je pravilno vedenje: izstopi in ostane zunaj.

Stopnjevanje plača v padajoči fazi 3,51 %, torej skoraj petkrat več od osnove.
Tam ni donosa, ki bi to pokril. **To je najbolj neposredna razlaga, zakaj
stopnjevanje pade**, in je jasnejša od vsega, kar sem navedel prej.

### Kolikokrat kandidat premaga osnovo, po fazah

| kandidat | rastoče faze | padajoče faze | skupaj |
|---|---|---|---|
| stopnjevanje k≥2 | 3 od 4 | 2 od 5 | 5 od 9 |
| ansambel Donchianov | 3 od 4 | 2 od 5 | 5 od 9 |
| dno 0 % | 2 od 4 | 3 od 5 | 5 od 9 |
| dno 10 % | **4 od 4** | **0 od 5** | 4 od 9 |
| ansambel tracklinov | 2 od 4 | 1 od 5 | 3 od 9 |
| BTC kupi in drži | **4 od 4** | **0 od 5** | 4 od 9 |

Noben kandidat ne premaga osnove v večini obeh vrst faz. Najboljši je 5 od 9,
kar je met kovanca.

Opazi zadnji dve vrstici: **dno 10 % se obnaša natanko kot kupi in drži**, zmaga
v vseh rasteh in izgubi v vseh padcih. To potrjuje, da je trajno dno preprosto
gumb proti kupi in drži, ne izboljšava.

---

## Del 1c: protokol, ki zamenja en sam hold-out

Zgornje faze so podlaga. Zdaj protokol, ki iz njih naredi merilo.

### Zakaj en hold-out ne zadošča

Naš hold-out je v celoti padajoča faza. Kar smo tam izmerili, odgovarja na eno
samo vprašanje: kako se kandidat obnese v padcu. O rasti ne pove nič.

To ni napaka delitve, je njena meja. Trojna delitev služi **poštenosti izbire**,
ne **pokritosti režimov**. Za drugo je potreben drug postopek.

### Kaj priporočajo

**López de Prado, kombinatorično prečno preverjanje.** Namesto ene delitve
razreži podatke na N skupin, za testno množico vzemi vsako kombinacijo k skupin,
in dobiš C(N,k) ocen namesto ene. Vsaka skupina je testna večkrat.

**CTA panoga.** Ločeno merjenje zajema navzgor in navzdol, in zahteva, da
kandidat ni odvisen od enega režima. [CME](https://www.cmegroup.com/education/courses/managed-futures/evaluating-ctas-quantitative-and-qualitative-factors)
navaja odvisnost od režima in strukturne prelome kot glavna merila presoje.

### Protokol, ki sem ga sestavil

Skupine niso poljubni bloki, ampak **datirane faze**. To je boljše od enakih
blokov, ker vsaka skupina ustreza resničnemu stanju trga, ne koledarju. Devet
faz, štiri rastoče in pet padajočih.

| del | kaj naredi |
|---|---|
| **A, po fazah** | kandidat proti osnovi na vsaki fazi posebej |
| **B, kombinatorično** | vseh **C(9,3) = 84** podmnožic po tri faze. Porazdelitev pove, kako pogosto kandidat zmaga na naključni tretjini zgodovine |
| **C, razslojeno** | zmaga v večini **rastočih** IN v večini **padajočih** faz. Kandidat, ki zmaga le v eni vrsti, je stava na režim |
| **D, zajem** | delež rasti in delež padca BTC, ki ju kandidat zajame |

### Merilo za sprejem, določeno vnaprej

| | pogoj |
|---|---|
| C1 | zmaga v vsaj **3 od 4** rastočih faz |
| C2 | zmaga v vsaj **3 od 5** padajočih faz |
| C3 | zmaga v vsaj **70 %** od 84 podmnožic |
| C4 | 95 % interval zaupanja na celi zgodovini izključuje ničlo **navzgor** |

Sprejme se le kandidat, ki izpolni vse štiri. V padajočih fazah se primerja
zložen donos, ne razmerja.

### Rezultat: 0 od 12

**C, razslojeno štetje:**

| kandidat | rastoče | padajoče |
|---|---|---|
| stopnjevanje k≥2 | **3 od 4** | 2 od 5 |
| ansambel Donchianov | **3 od 4** | 2 od 5 |
| dno 0 % | 2 od 4 | **3 od 5** |
| **dno 10 %** | **4 od 4** | **0 od 5** |
| ansambel tracklinov | 2 od 4 | 1 od 5 |
| izstop po 1 dnevu | 2 od 4 | 1 od 5 |
| izstop po 5 dneh | 1 od 4 | 0 od 5 |

**Noben kandidat ne zmaga v večini obeh vrst faz.** Vsak, ki je dober v rasti, je
slab v padcu, in obratno.

Vrstica dno 10 % je najbolj poučna: zmaga v **vseh štirih** rastočih in v
**nobeni** padajoči. To je natanko vedenje kupi in drži. Trajno dno torej ni
izboljšava, je gumb proti kupi in drži.

**B, kombinatorično, delež zmag od 84 podmnožic:**

| kandidat | zmaga v | mediana razlike |
|---|---|---|
| stopnjevanje k≥2 | **55 %** | +2,9 |
| dno 0 % | 51 % | +0,1 |
| dno 10 % | 45 % | −3,6 |
| izstop po 1 dnevu | 44 % | −3,6 |
| ansambel Donchianov | 42 % | −4,0 |
| ansambel tracklinov | 33 % | −7,8 |
| **izstop po 5 dneh** | **8 %** | −35,3 |

Prag je bil 70 %. Najboljši kandidat doseže 55 %, kar je met kovanca. Nič ni
blizu.

**D, zajem:**

| kandidat | zajem rasti | zajem padca |
|---|---|---|
| osnova, danes | 25 % | 31 % |
| stopnjevanje k≥2 | 33 % | 37 % |
| dno 0 % | 27 % | 33 % |
| izstop po 5 dneh | 24 % | **53 %** |

Stopnjevanje ima najboljše razmerje zajema, 0,89 proti osnovnim 0,79. To je
edina os, na kateri je kandidat boljši, in ne zadošča.

**Skupna sodba: sprejetih 0 od 12.**

### Eno opozorilo pri branju

Ena različica, ansambel obojega, ima interval zaupanja, ki **izključuje ničlo**,
in sicer [−100918, −144]. To ni uspeh. Interval je v celoti **negativen**,
torej je edini statistično značilen rezultat v vsej tabeli dokaz, da je ta
kandidat **slabši**.

---

## Del 1d: ciljanje volatilnosti, prvi značilen rezultat

### Kaj je to in zakaj sem ga spregledal

Najbolj univerzalna profesionalna tehnika, ki je nismo imeli. Vsi jo uporabljajo:

| kdo | kako |
|---|---|
| Zarattini | `w = min(0,25 / σ, 200 %)` |
| Man Group | velikost pozicije po volatilnosti |
| AQR | skaliranje na stalno ciljno volatilnost |
| Monash | isto |

Naš lean je binaren, nič ali vse. Dnevnik projekta je `target_vol_pct` označil
kot brez učinka, ampak to je zato, ker je **vgrajena** pot pri binarnem
`target_alloc` izklopljena. Kot **prekrivni sloj** čez že izračunano pozicijo ni
bila nikoli merjena, in to je nekaj drugega.

```
p = p_lean × clip( ciljna_volatilnost / σ60 , 0 , kapa )
```

σ60 je 60-dnevna realizirana volatilnost do včeraj. Brez vzvoda pomeni kapa = 1,
torej se pozicija lahko samo zmanjša.

### Rezultat na celi zgodovini BTC

| različica | Sharpe | Sortino | CAGR | MaxDD | izpost |
|---|---|---|---|---|---|
| **osnova, danes** | 1,35 | 2,20 | **55 %** | −45 % | 38 % |
| ciljanje 30 %, brez vzvoda | **1,49** | **2,50** | 31 % | **−18 %** | 23 % |
| ciljanje 50 %, brez vzvoda | 1,46 | 2,40 | 45 % | −28 % | 32 % |
| ciljanje 50 %, do 2x | 1,48 | 2,48 | 54 % | −29 % | 39 % |
| ciljanje 70 %, brez vzvoda | 1,44 | 2,35 | 52 % | −33 % | 36 % |
| ciljanje 70 %, do 2x | **1,50** | **2,53** | **76 %** | −39 % | 52 % |
| Zarattini Combo | 1,40 | 2,33 | 25 % | −20 % | 20 % |

**Vseh šest različic dvigne Sharpe in Sortino.** To je edina družina posegov v
vsej preiskavi, kjer je učinek v isto smer pri vsaki nastavitvi.

### Kaj pove protokol faz

| različica | rastoče faze | padajoče faze | izpostavljenost |
|---|---|---|---|
| ciljanje 30 %, brez vzvoda | **0 od 4** | **5 od 5** | 23 % |
| ciljanje 50 %, brez vzvoda | 1 od 4 | 4 od 5 | 32 % |
| ciljanje 50 %, do 2x | 2 od 4 | 3 od 5 | 39 % |
| ciljanje 70 %, do 2x | **4 od 4** | **1 od 5** | 52 % |

**Popolnoma monotono z izpostavljenostjo.** Manjši cilj pomeni več zmag v padcih
in manj v rasteh, večji cilj obratno.

To ni prednost, je **gumb na osi tveganja**. Prav zato je protokol koristen: en
sam hold-out bi pokazal samo eno stran te izmenjave.

Skupna sodba: **0 od 7 sprejetih.**

### Ampak eno stvar je treba izmeriti posebej

Sharpe in Sortino sta neodvisna od obsega. Če pozicijo pomnožiš s konstanto, se
ne spremenita. Zato je primerjava razmerij poštena tudi pri različni
izpostavljenosti.

Bootstrap proti osnovi, 5000 vzorcev:

| različica | d Sortino [95 % IZ] | **d MaxDD [95 % IZ]** |
|---|---|---|
| ciljanje 30 %, brez vzvoda | +0,28 [−0,33, +0,87] | **+23,7 [+11,5, +38,5]** |
| ciljanje 50 %, brez vzvoda | +0,19 [−0,27, +0,66] | **+12,9 [+2,6, +25,5]** |
| ciljanje 50 %, do 2x | +0,27 [−0,36, +0,88] | +10,0 [−3,1, +24,7] |
| ciljanje 70 %, do 2x | +0,32 [−0,24, +0,92] | −0,4 [−13,7, +14,0] |

Sortino ni dokazan pri nobeni. **Najhujši padec pa je.** Pri cilju 30 % in 50 %
brez vzvoda interval **izključuje ničlo navzgor**.

To je prvi statistično značilen pozitiven rezultat v celotni preiskavi.

### Poštena primerjava pri isti izpostavljenosti

Da izključim možnost, da gre le za manj izpostavljenosti. Primerjam različico
70 % z vzvodom (izpostavljenost 52 %) proti osnovi, pomnoženi s 1,35, kar da
isto izpostavljenost:

| pri 52 % izpostavljenosti | Sharpe | CAGR | MaxDD | konec |
|---|---|---|---|---|
| osnova × 1,35 | 1,35 | 75 % | **−57 %** | 366x |
| ciljanje 70 %, do 2x | **1,50** | 76 % | **−39 %** | 385x |
| statično 52 % BTC | 1,09 | 38 % | −58 % | 29x |

**Enak donos, osemnajst točk manj padca, pri isti izpostavljenosti.** To ni
artefakt.

Vendar: proti tako skalirani osnovi po fazah zmaga le 2 od 4 v rasteh in 3 od 5
v padcih, interval zaupanja pa vsebuje ničlo. Torej ni dokazano.

### Kaj iz tega sledi

**Ciljanje volatilnosti ni izboljšava donosa. Je dokazan zmanjševalec padca.**

To se natanko ujema s tem, čemu je namenjeno v literaturi. AQR in Man Group ga
ne uporabljata za višji donos, ampak za **predvidljivo tveganje**. Naša meritev
pove isto.

Ponudba je zato poštena menjava z znanim tečajem, ne izboljšava:

| če vzameš ciljanje 30 % | dobiš | plačaš |
|---|---|---|
| najhujši padec | −45 % postane **−18 %** | |
| letni donos | | 55 % postane **31 %** |
| čas v trgu | | 38 % postane 23 % |

Ali je to dobra menjava, ni statistično vprašanje. Je tvoja odločitev o tem,
koliko tveganja hočeš.

### Zarattini Combo kot celota

Ker sem ga že reproduciral, sem ga peljal skozi isti protokol.

| | Sharpe | Sortino | CAGR | MaxDD | izpost |
|---|---|---|---|---|---|
| naš lean | 1,35 | 2,20 | **55 %** | −45 % | 38 % |
| Zarattini Combo | 1,40 | 2,33 | **25 %** | −20 % | 20 % |

Razmerja so podobna, donos pa je manj kot polovica, ker je v trgu skoraj
polovico manj časa. Zložena razlika je **statistično značilno negativna**,
interval [−154558, −178].

Njihova strategija na naših podatkih torej ni boljša od naše. Je bolj
zadržana različica iste ideje.

---

## Del 1e: profesionalna konstrukcija na knjigi šestih

Del 1d je bil na BTC. Tu je isto na tvoji knjigi, in slika je bogatejša.

### Načrt, izpeljan iz literature

Man Group in [Carver](https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html)
opisujeta **hierarhično zaporedje**, ne enega posega:

| korak | kaj naredi |
|---|---|
| 1, skaliranje po sredstvu | vsako sredstvo se skalira po **svoji** volatilnosti |
| 2, množitelj razpršitve | ker se tveganja delno iztečejo, se knjiga lahko poveča. `IDM = 1 / sqrt(w' C w)`, Carver ga omeji na 2,5 |
| 3, ciljanje na ravni knjige | cela knjiga se skalira na ciljno volatilnost portfelja |

Man Group izrecno: po skaliranju po sredstvu se uporabi ciljanje na ravni
portfelja, ki zmanjša izpostavljenost, ko korelacije narastejo.

### Prva ugotovitev, in sama po sebi je pomembna

Korelacije med tvojimi šestimi, zadnjih 250 dni:

| | BTC | ETH | SOL | LINK | BNB | HYPE |
|---|---|---|---|---|---|---|
| **BTC** | 1,00 | 0,91 | 0,88 | 0,87 | 0,84 | **0,45** |
| **ETH** | 0,91 | 1,00 | 0,88 | 0,91 | 0,80 | **0,52** |
| **SOL** | 0,88 | 0,88 | 1,00 | 0,89 | 0,82 | 0,49 |
| **LINK** | 0,87 | 0,91 | 0,89 | 1,00 | 0,82 | 0,48 |
| **BNB** | 0,84 | 0,80 | 0,82 | 0,82 | 1,00 | 0,42 |
| **HYPE** | 0,45 | 0,52 | 0,49 | 0,48 | 0,42 | 1,00 |

Povprečna korelacija **0,73**. Iz tega sledi:

| | vrednost |
|---|---|
| IDM danes | **1,09** |
| IDM povprečje | 1,32 |
| Carverjeva zgornja meja | 2,5 |

Carver pravi, da prva peščica instrumentov IDM približno **podvoji**, torej na
okoli 2,0. Tvojih šest kripto sredstev ga dvigne na **1,09**.

**Razpršitev med njimi je skoraj nična. Vedejo se kot eno sredstvo.** To
količinsko pojasni, zakaj je test širine univerzuma padel, in ni več stvar
ugibanja.

Edina izjema je **HYPE**, ki korelira 0,42 do 0,52, medtem ko so vsi drugi pari
med 0,80 in 0,91.

### Rezultat na celi zgodovini knjige

| različica | Sharpe | Sortino | CAGR | MaxDD | izpost |
|---|---|---|---|---|---|
| **0 danes** | 1,47 | 2,28 | 39 % | −28 % | 21 % |
| 1 po sredstvu 50 %, brez vzvoda | 1,54 | 2,42 | 30 % | −22 % | 15 % |
| 1 po sredstvu 70 %, do 2x | 1,57 | 2,53 | 49 % | −29 % | 23 % |
| 2 knjiga 20 %, brez vzvoda | 1,64 | 2,62 | 30 % | **−18 %** | 15 % |
| 2 knjiga 30 %, do 2x | **1,68** | 2,72 | **54 %** | −29 % | 26 % |
| 3 hierarhično, brez vzvoda | 1,61 | 2,57 | 26 % | **−16 %** | 13 % |
| 4 hierarhično + IDM, brez vzvoda | **1,67** | 2,68 | 38 % | −21 % | 16 % |
| **4 hierarhično + IDM, do 2x** | **1,68** | **2,74** | **51 %** | −26 % | 22 % |

**Vseh dvanajst različic dvigne Sharpe in Sortino.** Nobena izjema.

### Dve vrstici sta vredni posebne pozornosti

**4 hierarhično + IDM, do 2x** ima izpostavljenost 22 % proti osnovnim 21 %,
torej praktično enako, pri tem pa CAGR 51 % proti 39 % in padec −26 % proti
−28 %. **To ni artefakt izpostavljenosti.**

**4 hierarhično + IDM, brez vzvoda** ima enak CAGR kot osnova, 38 proti 39 %,
pri padcu −21 % proti −28 % in **nižji** izpostavljenosti, 16 proti 21 %.

### Kaj pove protokol faz

| različica | rast | padec | kombi | d Sortino [95 % IZ] | d MaxDD [95 % IZ] |
|---|---|---|---|---|---|
| 1 po sredstvu 50 %, brez vzvoda | 1 od 4 | **5 od 5** | 64 % | +0,14 [−0,22, +0,50] | **+9,4 [+3,0, +17,9]** |
| 1 po sredstvu 70 %, brez vzvoda | 2 od 4 | **5 od 5** | 79 % | +0,11 [−0,13, +0,35] | **+5,0 [+0,5, +11,2]** |
| 2 knjiga 20 %, brez vzvoda | 1 od 4 | **5 od 5** | 75 % | +0,34 [−0,08, +0,79] | **+10,5 [+3,6, +20,0]** |
| **3 hierarhično, brez vzvoda** | 1 od 4 | **5 od 5** | 74 % | +0,29 [−0,16, +0,75] | **+13,1 [+5,6, +23,0]** |
| 4 hierarhično + IDM, brez vzvoda | 1 od 4 | 4 od 5 | 77 % | +0,41 [**−0,05**, +0,92] | +6,8 [−0,4, +15,3] |
| 4 hierarhično + IDM, do 2x | 2 od 4 | 2 od 5 | 75 % | +0,46 [−0,17, +1,12] | +2,1 [−8,4, +12,6] |

**Sodba: 0 od 12 sprejetih.** Vzorec je enak kot na BTC.

**C1 pade povsod.** Najboljši doseže 2 od 4 rastočih faz. Vse te tehnike so
obrambne.

**C2 je skoraj povsod izpolnjen**, pri več različicah 5 od 5. To je logično: v
padajočih fazah je volatilnost visoka, torej ciljanje zmanjša pozicijo natanko
tam.

**Najhujši padec je dokazano manjši** pri petih različicah. Največji učinek ima
hierarhično brez vzvoda: **+13,1 točke, interval [+5,6, +23,0]**.

**Sortino ni dokazan pri nobeni.** Najbližje je hierarhično z IDM brez vzvoda,
+0,41 z intervalom [−0,05, +0,92]. Za las.

### Sklep za knjigo

Isti kot za BTC, samo z večjim učinkom: **ciljanje volatilnosti je dokazan
zmanjševalec padca in nedokazan izboljševalec donosa.**

Menjava, ki jo lahko ponudim s številkami:

| hierarhično brez vzvoda | dobiš | plačaš |
|---|---|---|
| najhujši padec | −28 % postane **−16 %** | |
| letni donos | | 39 % postane **26 %** |
| čas v trgu | | 21 % postane 13 % |

| hierarhično + IDM, brez vzvoda | dobiš | plačaš |
|---|---|---|
| najhujši padec | −28 % postane **−21 %** | |
| letni donos | 39 % ostane **38 %** | |
| čas v trgu | | 21 % postane 16 % |

Druga vrstica je zanimivejša: **skoraj enak donos, sedem točk plitvejši padec,
manj časa v trgu.** Formalno ne prestane protokola, ker interval Sortina za las
vsebuje ničlo in ker v rasteh zmaga le 1 od 4. Ampak od vsega, kar sem v tej
preiskavi izmeril, je to najbolj privlačna ponudba.

---

## Del 1f: samo binarni kandidati na knjigi

Omejitev: pozicija je 1 ali 5-odstotno dno, nikoli vmes. To izključi ciljanje
volatilnosti, stopnjevanje in povprečenje pozicij, torej vse, kar je v delih 1d
in 1e pokazalo učinek.

Vprašanje: kaj profesionalnega ostane **znotraj** te omejitve.

### Nabor, izpeljan iz literature

| kandidat | podlaga |
|---|---|
| **večinsko glasovanje** | namesto povprečenja pozicij se šteje, koliko specifikacij pravi drži. Izhod ostane binaren. [Declerck in Vy](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5032806) poročata, da je v variabilnosti binarnih signalov informacija |
| **ukrepaj redkeje** | višji časovni okvir naj bi zmanjšal zaporedne lažne signale. Tu isti dnevni signal, a pozicija se sme spremeniti le enkrat na teden ali mesec. To izolira učinek brez spreminjanja parametra |
| **knjižno stikalo** | če je BTC zunaj, gre cela knjiga v gotovino |
| **denar ob izstopu** | sredstvo brez signala se prelije v BTC namesto v gotovino |
| **druge uteži** | enake uteži, ali samo tri sredstva |

### Rezultat na celi zgodovini

| kandidat | Sharpe | Sortino | CAGR | MaxDD | izpost | konec |
|---|---|---|---|---|---|---|
| **0 danes** | 1,47 | 2,28 | 39 % | −28 % | 21 % | 34x |
| glasovanje TL, ≥2 od 5 | 1,48 | 2,28 | 45 % | −31 % | 25 % | 50x |
| glasovanje TL, ≥3 od 5 | 1,43 | 2,20 | 38 % | −28 % | 21 % | 30x |
| glasovanje TL, ≥4 od 5 | 1,18 | 1,77 | 25 % | −29 % | 16 % | 10x |
| glasovanje DC, ≥3 od 5 | 1,46 | 2,26 | 40 % | −29 % | 21 % | 36x |
| **ukrepaj tedensko** | **1,18** | 1,73 | 32 % | **−44 %** | 21 % | 19x |
| **ukrepaj mesečno** | **1,07** | 1,61 | 31 % | −37 % | 20 % | 18x |
| knjižno stikalo (BTC) | 1,45 | 2,29 | 37 % | **−24 %** | 16 % | 27x |
| enake uteži | 1,25 | 1,84 | 27 % | −27 % | 21 % | 13x |
| **samo tri, enake uteži** | **1,53** | **2,48** | 41 % | −28 % | 25 % | 37x |
| denar ob izstopu v BTC | 1,45 | 2,31 | **62 %** | **−45 %** | 43 % | **165x** |

### Prva ugotovitev: redkejše ukrepanje škodi, in to dokazano

To je najbolj uporaben izid tega kroga, ker nasprotuje pogostemu nasvetu.

| kandidat | d Sortino [95 % IZ] |
|---|---|
| ukrepaj tedensko | **−0,53 [−1,08, −0,04]** |
| ukrepaj mesečno | −0,66 [−1,38, +0,02] |

Tedensko ukrepanje je **statistično značilno slabše**, interval izključuje ničlo
navzdol. Najhujši padec se poglobi z −28 % na −44 %.

Razlog je viden takoj, ko pomisliš, kje lean zasluži. Njegova vrednost je
**pravočasen izstop**. Če izstop zamakneš za do teden dni, sediš v padcu, ki se
mu je hotel izogniti. Signal ostane isti, škoda pride izključno iz zamude.

**Dnevna odločitev je nosilna. Ne redči je.**

### Druga ugotovitev: glasovanje je nevtralno, ne škodljivo

| glasovanje | Sharpe | rastoče faze | d Sortino |
|---|---|---|---|
| ≥2 od 5 | 1,48 | **3 od 4** | −0,01 |
| ≥3 od 5 | 1,43 | **4 od 4** | −0,08 |
| ≥3 od 5, Donchian | 1,46 | **4 od 4** | −0,02 |
| ≥4 od 5 | 1,18 | 0 od 4 | **−0,51 [−1,01, −0,04]** |

Pri pragu 2 in 3 je rezultat praktično nespremenjen. Šele zahteva, da se strinja
**vseh pet**, značilno škodi.

To je zanimivo v luči dela 1c. Tam je zvezno povprečenje periode škodilo, ker je
zamenjalo periodo 75 s povprečno. V binarni obliki glasovanje ne škodi, a tudi
ne pomaga. **Perioda trackline torej ni posebej pomembna, dokler ne zahtevaš
soglasja.**

### Tretja ugotovitev: denar v BTC ni zastonj

| | CAGR | MaxDD | izpost | d MaxDD [95 % IZ] |
|---|---|---|---|---|
| 0 danes | 39 % | −28 % | 21 % | referenca |
| denar ob izstopu v BTC | **62 %** | **−45 %** | 43 % | **−15,5 [−24,7, −6,8]** |

Končna vrednost 165x proti 34x izgleda spektakularno, ampak izpostavljenost se
podvoji, in najhujši padec je **statistično značilno globlji**. To ni izboljšava,
je odločitev, da hočeš biti bolj v BTC.

### Četrta ugotovitev: tri sredstva namesto šestih

| | Sharpe | Sortino | CAGR | MaxDD |
|---|---|---|---|---|
| šest, 50/10/10/10/10/10 | 1,47 | 2,28 | 39 % | −28 % |
| **tri, enake uteži** | **1,53** | **2,48** | 41 % | −28 % |

Izpolni C2 (4 od 5 padajočih) in C3 (71 %), pade pa na C1 (1 od 4 rastočih) in
C4, ker interval Sortina vsebuje ničlo, +0,19 [−0,37, +0,78].

Ni dokazano, je pa še ena meritev v isto smer kot test širine in kot IDM 1,09.

### Sodba

**Sprejetih 0 od 10.**

---

## Del 2: na čem je vse merjeno

BTC posamično: Coinbase, 4. 2. 2016 do 30. 8. 2026, 3861 dni.

Košarica: BTC 50 %, ETH, SOL, LINK, BNB, HYPE po 10 %, mesečno uravnavanje.
Cene s Coinbasea, razen BNB z Binancea in HYPE s Hyperliquida.

Povsod provizija in zdrs skupaj **0,30 % na stran**.

---

## Del 3: umik priporočila o utežeh po tveganju

### Kaj sem priporočil

50 % kapitala v BTC ni 50 % tveganja, ker altcoini nihajo bistveno bolj.
Izmerjeno: BTC danes prispeva 40,5 % tveganja, HYPE pa 16,6 % namesto 10 %.
Popravek `utež = cilj / sigma(60 dni)`, mesečno.

Številke so izgledale takole:

| okno | Sharpe danes | po tveganju | MaxDD danes | po tveganju |
|---|---|---|---|---|
| trening | 1,56 | 1,61 | −28 % | −30 % |
| validacija | 1,59 | 1,58 | −14 % | −13 % |
| hold-out | 0,73 | 0,73 | −16 % | **−12 %** |

Argument je bil: ne zmaga, a tudi ne izgubi na nobenem oknu, in skrajša padec
za štiri točke.

### Kaj pokaže bootstrap

| okno | d Sharpe | 95 % interval | P(boljši) |
|---|---|---|---|
| trening | +0,048 | [−0,07, +0,17] | 79 % |
| validacija | −0,005 | [−0,19, +0,16] | **49 %** |
| hold-out | +0,005 | [−0,26, +0,30] | **50 %** |

**Vsi trije intervali vsebujejo ničlo.** Na validaciji in hold-outu je
verjetnost, da je boljši, 49 % oziroma 50 %, torej met kovanca.

Tudi tisti štiritočkovni prihranek pri padcu:

| okno | d MaxDD | 95 % interval |
|---|---|---|
| hold-out | +2,16 | **[−1,6, +6,4]** |

Vsebuje ničlo. Lahko je štiri točke, lahko je nič, lahko je narobe obrnjeno.

### Drseče leto

Delež 365-dnevnih oken, v katerih so uteži po tveganju boljše:

| trening | validacija | hold-out |
|---|---|---|
| 38 % | 43 % | 50 % |

**Pod metom kovanca na dveh od treh oken.**

### Preveril sem tudi enostavnejšo pot

Če bi bila korist prava, bi jo morda dale tudi **statične** uteži, izračunane
enkrat iz treninga in zamrznjene, brez mesečnega računanja volatilnosti. To bi
odpravilo vso zapletenost.

Statične uteži iz treninga: BTC 59,8 %, ETH 8,6 %, BNB 8,5 %, HYPE 8,0 %,
LINK 7,7 %, SOL 7,4 %.

| okno | d Sharpe | 95 % interval | P(boljši) |
|---|---|---|---|
| trening | −0,002 | [−0,08, +0,08] | 48 % |
| validacija | +0,034 | [−0,09, +0,15] | 71 % |
| hold-out | −0,053 | [−0,18, +0,09] | **22 %** |

Prav tako nič. Na hold-outu celo slabše.

### Sklep

**Priporočilo umikam. Imel si prav.**

Opažanje samo ostane resnično: v košarici res imaš 40 % tveganja v BTC in ne
50 %. Ampak popravek te napake se v rezultatu ne pozna dovolj, da bi upravičil
mesečno računanje volatilnosti in nov vir napake.

Če te razporeditev tveganja moti kot vprašanje zasnove, je poštena pot
**enkratna odločitev**: ali hočeš 50 % kapitala ali 50 % tveganja v BTC. Drugo
pomeni približno BTC 60 % in altcoine po 8 %. To je ena vrstica v nastavitvah,
brez mehanike. Ampak ne pričakuj boljšega rezultata, ker ga podatki ne
obljubljajo.

---

## Del 4: stopnjevana velikost pozicije, podrobno

To je edini zavrnjeni kandidat z opazno prednostjo, zato si zasluži več od
enega stavka.

### Kaj to je

Lean ima štiri vstopne pogoje. Danes morajo držati **vsi štirje**, sicer si
zunaj. Stopnjevana različica drži toliko, kolikor jih drži:

```
k = koliko od štirih pogojev drži danes      od 0 do 4
pozicija = k / 4,   vstop pri k >= 2
```

Kako pogosto drži koliko, na BTC čez celo zgodovino:

| k | delež dni |
|---|---|
| 0 | 18,2 % |
| 1 | 21,6 % |
| 2 | 18,0 % |
| 3 | 21,7 % |
| **4, danes edini vstop** | **20,6 %** |

Vsi štirje hkrati držijo le vsak peti dan. Vmesnih stanj je ogromno in danes so
vsa obravnavana enako kot nič.

### Zakaj izgleda dobro

BTC, cela zgodovina:

| | Sharpe | Sortino | CAGR | MaxDD | konec | provizije |
|---|---|---|---|---|---|---|
| danes, binarno | 1,35 | 2,20 | 55 % | −45 % | 101x | **15,7 %** |
| k≥2 | **1,53** | **2,54** | **58 %** | −46 % | **123x** | **49,3 %** |

Sortino +0,34 in končni mnogokratnik 123 proti 101. To ni malo.

### Prvi razlog proti: razlika ni dokazana

Vezani bločni bootstrap, 5000 vzorcev, blok 20 dni:

| | razlika | 95 % interval | P(boljši) |
|---|---|---|---|
| Sortino | +0,310 | **[−0,260, +0,910]** | 85 % |
| Sharpe | +0,160 | **[−0,133, +0,448]** | 87 % |

Oba intervala vsebujeta ničlo. Prednost na celi zgodovini torej **ni
statistično dokazana**, čeprav izgleda velika.

### Drugi razlog: vse pride iz enega leta

Razlika v Sortinu po letih:

| leto | binarno | k≥2 | razlika |
|---|---|---|---|
| 2016 | 7,13 | 6,37 | −0,76 |
| 2017 | 4,19 | 5,16 | +0,97 |
| 2018 | −0,97 | −1,42 | −0,45 |
| 2019 | 2,59 | 2,29 | −0,30 |
| **2020** | 2,51 | 4,93 | **+2,42** |
| 2021 | 1,52 | 1,56 | +0,04 |
| 2022 | −1,69 | −1,27 | +0,42 |
| 2023 | 2,35 | 2,67 | +0,32 |
| **2024** | 4,05 | 2,62 | **−1,44** |
| 2025 | 0,53 | 0,94 | +0,42 |
| 2026 | 0,05 | 0,15 | +0,11 |

Odstrani eno samo leto, 2020, in prednost skoraj izgine:

| | binarno | k≥2 | razlika |
|---|---|---|---|
| cela zgodovina | 2,20 | 2,54 | **+0,33** |
| brez 2020 | 2,17 | 2,27 | **+0,10** |

Bootstrap brez 2020: +0,072, interval [−0,512, +0,669], P(boljši) 59 %.

Ena sama letnica torej nosi tri četrtine prednosti. To je krhko.

### Tretji razlog, in ta je najbolj poveden

Razlika v Sortinu pri različnih stopnjah provizije, po oknih:

| okno | 0,00 % | 0,10 % | **0,30 %** | 0,50 % | 1,00 % |
|---|---|---|---|---|---|
| cela zgodovina | +0,52 | +0,46 | +0,33 | +0,21 | −0,09 |
| trening | +0,59 | +0,53 | +0,43 | +0,32 | +0,06 |
| **validacija** | **+0,00** | −0,09 | −0,28 | −0,46 | −0,91 |
| hold-out | +0,76 | +0,65 | +0,43 | +0,23 | −0,27 |

Poglej vrstico validacije pri ničelni proviziji: **+0,00**.

Na validacijskem oknu stopnjevanje ni boljše **niti pred stroški**. Ni tako, da
bi imelo prednost, ki jo provizije pojedo. Prednosti tam preprosto ni.

### Zakaj je to drago

| | vstopov | povprečno trajanje | obrat | provizije |
|---|---|---|---|---|
| binarno | 28 | 48,5 dni | 52,2 | 15,7 % |
| k≥2 | **58** | **34,0 dni** | **164,2** | **49,3 %** |

Dvakrat več vstopov, tretjina krajše pozicije, trikratni obrat. V desetih letih
in pol polovica kapitala odide v provizije.

### Na košarici

| okno | binarno | k≥2 | d Sharpe [95 % IZ] | P(boljši) |
|---|---|---|---|---|
| trening | 1,56 | 1,66 | +0,090 [−0,19, +0,37] | 73 % |
| validacija | 1,59 | 1,46 | −0,149 [−0,83, +0,47] | 33 % |
| hold-out | 0,73 | 0,87 | −0,023 [−0,70, +0,72] | 46 % |

Vsi intervali vsebujejo ničlo.

### Sklep

**Zavrnjeno, in razlog je zdaj močnejši kot prej.** Ne gre le za to, da pade na
validaciji. Gre za to, da zmaga na celi zgodovini ni dokazana, izgine brez enega
leta, in na validaciji je ničelna že pred stroški.

Kar bi ga oživilo: izmerjen zdrs bistveno pod 0,30 %. Pri 0,10 % je razlika na
celi zgodovini +0,46 namesto +0,33. Še vedno pa ostane odvisnost od leta 2020.

---

## Del 5: ostali kandidati, na kratko

### Parametrski ansambel

**Zakaj sem ga vzel resno.** Ta projekt je sam ugotovil, da se optimalne periode
ne da izbrati: gnezdeni walk-forward je dal razliko točno 0,00, train-optimalna
perioda se z test-optimalno ujame v 1 od 5 oken.

[ReSolve](https://investresolve.com/from-fragility-to-robustness-the-value-of-ensembles/)
pride do iste ugotovitve in naredi korak naprej: zmeša 57 specifikacij z enakimi
utežmi in s tem premaga **vsako** metodo izbiranja, Sharpe 0,90 proti 0,87,
padec −14,9 % proti −16,4 %. Isto
[Newfound](https://blog.thinknewfound.com/2019/01/tightening-the-uncertain-payout-of-trend-following/),
[AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
in [Zarattini](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907).

Mreži sem preregistriral geometrijsko okoli obstoječih privzetkov:
track_period 40, 55, 75, 100, 135 in donchian_period 10, 14, 20, 28, 40.

**Rezultat, BTC cela zgodovina, Sortino:**

| osnova (75, 20) | ans. tracklinov | ans. Donchianov | ans. obojega (25) |
|---|---|---|---|
| **2,22** | 2,05 | 2,15 | 1,95 |

**Zakaj je padel, in to je zanimivo.** Posamezni člani:

| track_period | 40 | 55 | **75** | 100 | 135 |
|---|---|---|---|---|---|
| Sortino | 2,00 | 1,81 | **2,22** | 1,90 | 1,44 |

Povprečje članov je 1,87, ansambel 2,05. **Ansambel je torej naredil točno to,
kar obljublja: premagal je povprečnega člana za +0,18.** Padel je zato, ker je
naša obstoječa perioda 75 najboljši član v mreži, in ansambel jo zamenja s
povprečno.

Perioda 75 ni bila izbrana na teh podatkih, prišla je iz Pine skripte.

**Zavrnjeno.** Ansambel Donchianov je izenačen (validacija 2,49 proti 2,47,
hold-out 0,37 proti 0,37), kar ni razlog za petkratno zapletenost.

### Pas brez trgovanja

Uravnavaj le, če je rokav zanesel za več kot T od cilja. Podlaga
[NBIM](https://www.nbim.no/contentassets/8cb41f89dce345f5a6a295238f7872fb/no-trade-band-rebalancing-rules-expected-returns-and-transaction-costs.pdf)
in Davis in Norman 1990.

| prag | validacija | hold-out |
|---|---|---|
| **0 %, danes** | 1,59 | **0,73** |
| 20 % | **1,78** | **0,20** |

**Kako se past prepozna brez hold-outa.** Pas prihrani 0,28 enote od 100 v 21
mesecih, Sharpe pa premakne za 0,19. Vzrok in učinek nista istega reda
velikosti.

**Pravilo za naprej: če je učinek veliko večji od svojega razloga, je to sreča.**

Na validaciji gre 3,53 enote za signale in 0,37 za uravnavanje. Uravnavanje je
9 % stroška, torej ni problem, ki bi ga bilo vredno reševati.

**Zavrnjeno.**

### Širina univerzuma

225 kovancev s Coinbasea, mesečni izbor po 90-dnevnem prometu:

| kovancev | 3 | 6 | 10 | 20 | 30 |
|---|---|---|---|---|---|
| validacija | 1,58 | 0,90 | 0,43 | 0,94 | 0,93 |
| hold-out | **0,77** | 0,16 | 0,12 | −0,01 | **−0,24** |

Monotono slabše z vsakim dodanim kovancem, nasprotno od
[Man Group](https://www.man.com/insights/in-crypto-we-trend), ki pravi 10 do 15.
Razlika: njihovo obdobje je desetletno, njihova baza vsebuje odkotirane kovance,
in imajo velikost pozicije po volatilnosti.

**Zavrnjeno. Ostani pri 5 ali 6.**

### Hitrost izstopa in trajno dno

Preveril sem tudi nasprotno smer, torej ali **ostrenje** pomaga.

BTC cela zgodovina, Sortino:

| izstop po | 1 dnevu | 2 dneh | **3 dneh, danes** | 4 dneh | 5 dneh |
|---|---|---|---|---|---|
| | 2,01 | 2,08 | **2,22** | 2,16 | 1,77 |

Današnja nastavitev je vrh, 4 je tik za njo. **Plato, ne konica.** Ne premikaj.

Dno 0 / 5 / 10 % da 2,20 / 2,22 / 2,24 na celi zgodovini, po oknih pa pomaga v
treningu in validaciji ter škodi na hold-outu. Izenačeno, ostane kot je.

---

## Del 6: kar sem se v tem krogu zmotil

### Lestvica mehanizma

Trdil sem, da vsi kandidati padejo iz istega razloga, in to podprl z medvedjimi
Sortini. Ti so pri negativnem števcu obrnjeni.

Ponovljeno z zloženo izgubo, BTC, 1500 medvedjih dni od 3861:

| različica | zložena izguba | izpostavljenost | izguba na enoto |
|---|---|---|---|
| ansambel tracklinov | **−40,2 %** | 5,4 % | −7,41 |
| dno 0 % | −43,8 % | 3,0 % | **−14,60** |
| **dno 5 %, danes** | −49,7 % | 6,4 % | −7,77 |
| stopnjevanje k≥2 | −50,5 % | 10,3 % | **−4,90** |
| dno 10 % | −55,1 % | 9,9 % | −5,58 |
| stopnjevanje k≥1 | −57,5 % | 11,7 % | −4,91 |

**Lestvica ni ista kot po Sortinu.** Ansambel tracklinov je bil po Sortinu peti,
po pravem merilu je prvi.

**Umikam:** natančen vrstni red in trditev, da je bil popoln brez izjem.

**Preživi:** groba povezava, korelacija med izpostavljenostjo v padcu in zloženo
izgubo **−0,824**.

**Novo:** izguba na enoto izpostavljenosti se giblje od −4,90 do −14,60,
trikratni razpon. Najdražja je **brezpogojna** izpostavljenost, torej trajno
dno. Torej ni pomembno samo, koliko držiš, ampak zakaj.

### Stopnjevanje v padajočem trgu

Prej sem napisal, da je katastrofa. Ni. Po zloženi izgubi je −50,5 % proti
−49,7 %, torej skoraj enako, in v rastočem trgu je boljše.

---

## Del 7: kaj pravzaprav pojasni deset neuspehov

Poštena možnost, ki se ji je treba pogledati v oči: morda ne gre za to, da še
nismo našli pravega pravila.

### Volatilnost se je prepolovila

Povprečna letna volatilnost BTC:

| v treningu, do sredine 2023 | danes, 60 dni |
|---|---|
| **70 %** | **38 %** |

Trendna strategija zasluži iz gibanja. Na sredstvu, ki niha polovico manj, ne
more dati istega, kar je dajala prej, ne glede na pravila.

To ni ugibanje. Institucionalni viri to potrjujejo: ETF-i in podjetja držijo
okoli 12 % obtoka bitcoinov, kar zmanjšuje prosto plavajočo ponudbo in duši
nihanje na prodajni strani. Volatilnost BTC je padla s trimestnih vrednosti na
pod 50 %.

Naš hold-out ima CAGR 3 % namesto validacijskih 57 %. Del tega je preprosto to.

### Cela panoga je imela najslabše obdobje v 25 letih

SG Trend Index, referenčni indeks trendnih skladov, je od maja 2024 do maja 2025
padel za **20,4 %**, kar je njegov drugi najhujši padec od začetka leta 2000.

Naš hold-out se začne 1. aprila 2025, torej v zaključku tega obdobja.

To pomeni, da šibkega hold-outa ne smemo brati kot dokaz, da je z našo
strategijo nekaj narobe. Vsi so imeli isto.

### In obstaja dokumentiran mehanizem propadanja

[Raziskava o zatonu kratkoročnega sledenja trendu](https://quantpedia.com/is-trend-still-your-friend-a-microstructural-account-of-the-demise-of-short-term-trend-following/)
pokaže, da so se po letu 2008 dobički sledenja trendu skoraj popolnoma sesuli na
pogodbah z majhnim korakom, medtem ko so na tistih z velikim korakom ostali
nedotaknjeni. Vzrok je vzpon visokofrekvenčnega ustvarjanja trga: ponudniki
likvidnosti jo umaknejo, ko zaznajo predvidljiv usmerjen tok naročil.

Kripto še ni tam, je pa smer ista.

### Kaj iz tega sledi

Vprašanje ni več **kako izboljšati pravila**. Je:

> **Ali se prednost izteka, in kako bi to pravočasno vedel?**

Na to se z backtestom ne da odgovoriti, ker bi vsak odgovor prišel prepozno.

---

## Del 8: načrt

### Ukrep 1: ne spreminjaj ničesar

Deset kandidatov, nič sprejetih. Uteži po tveganju so bile najbližje in tudi
tiste ne prestanejo bootstrapa.

Nespremenjena oblika ni privzeta izbira iz lenobe. Je edina možnost, ki jo
podatki podpirajo.

### Ukrep 2: uvedi protokol faz kot obvezni prehod

Odslej noben kandidat ne gre naprej brez vseh štirih pogojev iz dela 1c:

| | pogoj |
|---|---|
| C1 | zmaga v vsaj 3 od 4 rastočih faz |
| C2 | zmaga v vsaj 3 od 5 padajočih faz |
| C3 | zmaga v vsaj 70 % od 84 kombinatoričnih podmnožic |
| C4 | 95 % interval zaupanja izključuje ničlo navzgor |

Pogoja C1 in C2 sta ključna in ju en sam hold-out ne more nadomestiti. Kandidat,
ki zmaga samo v eni vrsti faz, je stava na režim in ne izboljšava.

Ta protokol bi v tem krogu ustavil vseh dvanajst kandidatov, preden bi karkoli
spremenil. Poganja se z `testing/scripts/protokol_faze.py` in traja nekaj minut.

Podobno velja za nazaj: primerjave v `TESTING_LOG.md` so večinoma brez
intervalov in brez razslojitve po fazah, zato jih je treba brati previdno. Isto
velja za medvedje Sortine.

### Ukrep 3: meri zdrs

**To je zdaj najpomembnejša neznanka v projektu.**

0,30 % na stran je predpostavka, ne meritev. Je edini vhod v celoten backtest,
ki ga ugibamo, in od nje je odvisen odgovor:

- pri **0,10 %** postane stopnjevanje spet zanimivo, razlika na celi zgodovini
  zraste s +0,33 na +0,46
- pri **0,60 %** je treba obračanje zmanjšati, in celo današnja oblika je
  preveč aktivna

Kako: vsak dan zapiši ceno, ki jo je videla strategija, in ceno, po kateri se je
dejansko izvedlo. Po treh mesecih imaš razpored, ne ugibanja.

### Ukrep 4: postavi merilo za propadanje prednosti, vnaprej

Ker je propadanje realna možnost, potrebuješ vnaprejšnjo črto, ne naknadne
presoje.

Zapiši danes, preden se karkoli požene:

| kaj | pričakovano na hold-outu |
|---|---|
| Sharpe | 0,7 do 1,1 |
| najhujši padec | 15 do 25 % |
| čas v trgu | okoli 30 % |
| CAGR | 10 do 15 % |

In pravilo, kdaj se vprašaš, ali je konec:

> **Če v 18 mesecih živega delovanja Sharpe ostane pod 0,3 IN je BTC v tem času
> zrasel, prednosti ni več.**

Drugi del pogoja je bistven. Slab rezultat med padajočim BTC je pričakovan in
ni dokaz o ničemer. Slab rezultat med rastočim BTC pa je.

### Ukrep 5: spremljaj volatilnost sredstva kot vhod

Če BTC niha 38 % namesto 70 %, pričakuj približno polovico donosa. To ni
odpoved strategije.

Predlagam preprosto: v dashboard dodaj 60-dnevno volatilnost vsakega sredstva.
Ena vrstica, ki naredi razliko med "strategija ne dela" in "trg se ne premika".

### Ukrep 6: česa ne delati

| ne delaj | razlog, izmerjen |
|---|---|
| uteži po tveganju | vsi intervali vsebujejo ničlo, drseče leto 38/43/50 % |
| stopnjevanja velikosti | interval [−0,26, +0,91], brez 2020 ostane +0,10, na validaciji ničelno že pred stroški |
| parametrskega ansambla | BTC 2,22 na 2,05, košarica hold-out 0,75 na 0,55 |
| pasu brez trgovanja | hold-out 0,73 na 0,20 |
| premikanja hitrosti izstopa ali dna | plato, današnja nastavitev na vrhu |
| nadaljnjega prilagajanja parametrov | gnezdeni walk-forward: razlika točno 0,00 |
| zunanjih podatkovnih virov | makro vrata so se sprožila na 11 od 2600 dni |

---

## Del 9: kaj bi me premislilo

**Izmerjen zdrs bistveno pod 0,30 %.** Oživi stopnjevanje in več kovancev
hkrati. Zato je ukrep 3 prvi po vrsti.

**Daljša zgodovina brez preživetvene pristranskosti.** Vse, kar imamo, so
kovanci, ki jih Coinbase kotira danes. Z odkotiranimi se test širine postavi na
novo.

**Perioda 75, ki bi se izkazala za srečo.** Ansambel je padel samo zato, ker je
75 najboljši član v mreži. Če bi se na neodvisnem obdobju izkazalo, da ni
poseben, ansambel takoj postane pravilna izbira, ker ščiti pred napačno periodo.

**Vrnitev volatilnosti nad 60 %.** Če se nihanje vrne, se vrne tudi merilo, na
katerem so bili prvotni rezultati doseženi, in vse te primerjave je treba
ponoviti.

---

## Del 10: kje so številke

| kaj | datoteka |
|---|---|
| uteži po tveganju, bootstrap in statična pot | `testing/scripts/utezi_ali_se_splaca.py` |
| stopnjevanje, bootstrap in razčlenitev po letih | `testing/scripts/stopnjevanje_globinsko.py` |
| stopnjevanje na BTC, cela baterija | `testing/scripts/graded_btc_podrobno.py` |
| stopnjevanje na šestih sredstvih | `testing/scripts/graded_alti.py` |
| parametrski ansambel | `testing/scripts/ansambel.py` |
| hitrost izstopa in dno | `testing/scripts/ostrina_izstopa.py` |
| preverba mehanizma brez patologije Sortina | `testing/scripts/preveri_mehanizem.py` |
| pas brez trgovanja | `testing/scripts/knjiga_stroski_tveganje.py` |
| širina univerzuma | `testing/scripts/sirina2.py` |
| vse prejšnje faze projekta | `testing/TESTING_LOG.md` |
