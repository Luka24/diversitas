# Pet dni preizkušanja: kaj sem poskusil in kaj je od tega ostalo

Zapisano 1. septembra 2026.

Zadnjih pet dni sem sistematično preizkušal, ali se da lean strategija na
altcoinih izboljšati. Nastalo je štirinajst skript, približno 56 nastavitev in
kakih dvajset ločenih zamisli. Tu je vse na kupu, skupaj z razlago, kako brati
številke v oglatih oklepajih, ker so te pravzaprav najpomembnejši del.

---

## Najprej: kaj pomeni tisto v oglatih oklepajih

Povsod spodaj piše nekaj takega:

```
d Sortino  -0,53  [-1,08, -0,04]
```

Prva številka je razlika, ki sem jo izmeril. Oklepaj je **interval zaupanja**,
in brez njega prva številka ne pove skoraj nič.

### Zakaj sama razlika ne zadošča

Recimo, da neka različica doseže Sortino 2,54, današnja pa 2,20. Razlika je
+0,34 in izgleda lepo. Vprašanje, na katero moraš odgovoriti, preden karkoli
spremeniš, pa je drugo:

> Če bi bili obe različici v resnici enako dobri, kako pogosto bi mi zgodovina
> vseeno postregla z razliko +0,34?

Če je odgovor "pogosto", potem nisi izmeril prednosti, ampak srečo pri tem, kako
so se dobra in slaba obdobja razporedila.

### Zakaj mešanje dni ne bi delovalo

Prva pomisel je, da bi dneve preprosto premešal. Ta pomisel je napačna, in
razlog je vreden razumevanja, ker pojasni, zakaj je postopek tak, kot je.

Poglejmo deset izmišljenih dni, da se da vse prešteti na roko:

```
+2,0   -1,0   +3,0   -4,0   +1,0   +5,0   -2,0   +1,0   -3,0   +4,0   (v %)
```

Formule, ki jih uporabljam povsod:

```
povprecje   m = (r1 + r2 + ... + rn) / n
odklon      s = koren iz povprecja kvadratov odmikov od m
nihanje
navzdol     d = koren iz povprecja od min(ri, 0) na kvadrat    nicle se stejejo
Sharpe        = m * 365 / ( s * koren iz 365 )
Sortino       = m * 365 / ( d * koren iz 365 )
zlozen        = (1+r1)(1+r2)...(1+rn) - 1
MaxDD         = najnizja vrednost od  tekoca / dosedanji vrh - 1
```

Za naših deset dni: vsota je +6,00 %, torej povprečje +0,600 %. Negativni dnevi
so −1,0, −4,0, −2,0 in −3,0. Povprečje kvadratov od `min(ri, 0)`, pri čemer se
ničelni dnevi štejejo zraven, je 0,000300, koren tega je 0,0173.

Zdaj isti dnevi trikrat premešani:

| | povprečje | odklon | navzdol | Sharpe | Sortino | zložen | MaxDD |
|---|---|---|---|---|---|---|---|
| izvirnik | +0,0060 | 0,0287 | 0,0173 | **+3,993** | **+6,618** | **+5,73 %** | −4,00 % |
| premešano 1 | +0,0060 | 0,0287 | 0,0173 | **+3,993** | **+6,618** | **+5,73 %** | −6,86 % |
| premešano 2 | +0,0060 | 0,0287 | 0,0173 | **+3,993** | **+6,618** | **+5,73 %** | −6,88 % |
| premešano 3 | +0,0060 | 0,0287 | 0,0173 | **+3,993** | **+6,618** | **+5,73 %** | −4,12 % |

Šest stolpcev od sedmih je **popolnoma enakih**, in to ni naključje:

- **povprečje** je vsota deljena z n, vsota pa se ob mešanju ne spremeni
- **odklon** in **nihanje navzdol** sta prav tako samo povprečji, in povprečje
  ne ve, v kakšnem vrstnem redu so števila
- **zložen donos** je zmnožek, množenje pa je komutativno

Spremeni se samo **MaxDD**, ker ta edini bere zaporedje. Če vse slabe dneve
postaviš skupaj, dobiš globlji padec, čeprav so dnevi isti.

Preveril sem to tudi na pravih podatkih. Dva tisoč premešanj celotne zgodovine
BTC, 3861 dni:

```
razlika Sharpa:  min +0,175613   max +0,175613   razpon 1,1e-15
```

Torej vedno ista številka, do zadnje decimalke, ki jo računalnik še zna
zapisati. **Mešanje o Sharpu ne pove prav ničesar.**

### Kaj torej delam namesto tega

Postopek se imenuje **vezani bločni bootstrap**, in bistvena beseda ni "bločni",
ampak **z vračanjem**.

Zgodovino razrežem na bloke po dvajset dni. Nato naključno izberem začetke
blokov in jih zlagam, dokler ne dobim zgodovine iste dolžine. Ker se začetki
vlečejo neodvisno, se **nekateri bloki pojavijo dvakrat ali trikrat, drugi pa
niti enkrat**.

To ni ista zgodovina v drugem vrstnem redu. To je **drugačna zgodovina,
sestavljena iz istih kosov.**

Isti deset dni, tokrat z bloki po tri in z vračanjem:

| | dnevi | povprečje | Sharpe | Sortino | zložen |
|---|---|---|---|---|---|
| izvirnik | vsak enkrat | +0,0060 | +3,99 | +6,62 | +5,73 % |
| bootstrap 1 | dan 5 vzet 2x, dneva 6 in 7 po 3x, štirje dnevi izpadejo | +0,0150 | **+10,36** | **+26,16** | **+15,62 %** |
| bootstrap 2 | dneva 3 in 5 po 2x, dva dneva izpadeta | +0,0010 | **+0,58** | **+0,89** | **+0,47 %** |
| bootstrap 3 | dan 6 vzet 2x, dan 9 izpade | +0,0000 | **0,00** | **0,00** | **−0,37 %** |
| bootstrap 4 | dan 0 vzet 3x, dneva 1 in 2 po 2x, štirje izpadejo | +0,0120 | **+9,39** | **+17,09** | **+12,34 %** |

Zdaj se spremeni vse. Sharpe skoči med 0,00 in 10,36, zložen donos med −0,37 % in
+15,62 %, in vse to iz istih desetih dni.

Zakaj so bloki in ne posamezni dnevi: donosi trendne strategije se držijo v
nizih, dober teden pride skupaj z dobrim tednom. Če bi vlekel posamezne dni, bi
uničil ravno tisto lastnost, ki jo strategija izkorišča, in dobil bi prelep
rezultat.

Ključno je še, da za obe različici uporabim **iste** bloke. Tako se primerjava
ne pokvari.

Na pravih podatkih: pri enem samem bootstrapu čez 3861 dni

```
dni, ki se sploh ne pojavijo:  1478 od 3861   (38 %)
dni, vzeti enkrat:             1265
dni, vzeti dvakrat:             843
dni, vzeti trikrat ali vec:     275
```

Približno **tretjina zgodovine v vsakem poskusu izpade**. Zato je vsaka od pet
tisoč nadomestnih zgodovin verodostojna, a drugačna.

To ponovim pet tisočkrat, dobim pet tisoč razlik, in odrežem spodnjih ter
zgornjih 2,5 %. Kar ostane vmes, je interval zaupanja.

### Isti primer, do konca

Stopnjevana velikost pozicije proti današnji obliki, na celi zgodovini BTC:

```
izvirni Sharpe:  osnova 1,350,  stopnjevano 1,525,  razlika +0,176

2000 premesanj:  razlika vedno +0,175613, razpon 1,1e-15
2000 bootstrapov: povprecje +0,157, min -0,419, max +0,673
                  95 % interval [-0,128, +0,429]
                  pozitivnih 87 %
```

Beri takole. Izmerjena razlika je +0,176 in izgleda spodobno. Ampak med pet
tisoč verodostojnimi zgodovinami je bilo trinajst odstotkov takih, v katerih je
bilo stopnjevanje **slabše**, v najslabši za 0,419.

Interval vsebuje ničlo, torej razlika **ni dokazana**. Zato stopnjevanja ne
uvajam, čeprav na papirju izgleda dobro.

Vse to se da ponoviti z `testing/scripts/razlaga_bootstrap.py`, ki izpiše ravno
te tabele.

### Kako ga brati

Pravilo je preprosto in ima samo tri primere.

**Interval vsebuje ničlo.** Recimo `+0,34 [-0,26, +0,91]`. Med nadomestnimi
zgodovinami je bilo dovolj takih, kjer je bila razlika negativna. Razlika ni
dokazana. Ne spreminjaj ničesar.

**Interval je ves nad ničlo.** Recimo `+23,7 [+11,5, +38,5]`. Tudi v najbolj
neugodnih preurejenih zgodovinah je razlika ostala pozitivna. To je dokaz.

**Interval je ves pod ničlo.** Recimo `-0,53 [-1,08, -0,04]`. Prav tako dokaz,
samo da je različica **slabša**. Te so uporabne, ker ti povejo, česa naj ne
delaš.

### Konkretno na primeru iz spodnje tabele

Tedensko ukrepanje namesto dnevnega ima `-0,53 [-1,08, -0,04]`. Beri takole:

> V povprečju je tedensko ukrepanje slabše za 0,53 Sortina. V petindevetdesetih
> odstotkih preurejenih zgodovin je bilo slabše nekje med 0,04 in 1,08. Ni bilo
> niti ene verodostojne različice zgodovine, v kateri bi bilo boljše.

Zato tega ne delam.

Ena past pri branju: **širok interval ni isto kot slab rezultat.** Pomeni le, da
imamo premalo podatkov za sodbo. Pri desetletni zgodovini kripta so intervali
pogosto zelo široki, ker eno samo leto lahko premakne vse.

---

## Kaj sem meril in na čem

Vse na dnevnih svečah, provizija in zdrs skupaj 0,30 % na stran.

BTC posamično: Coinbase, 4. februar 2016 do 30. avgust 2026, 3861 dni.

Knjiga šestih: BTC 50 %, ETH, SOL, LINK, BNB in HYPE po 10 %, mesečno
uravnavanje. Cene s Coinbasea, razen BNB z Binancea, ker ga Coinbase ne kotira,
in HYPE s Hyperliquida, ker ga drugje ni.

Poleg intervalov zaupanja sem uvedel še eno merilo, ki ga prej ni bilo. Hold-out
namreč leži v celoti znotraj padajoče faze, v kateri je BTC izgubil 41 %, zato
pove samo, kako se kandidat obnese v padcu. O rasti ne pove nič.

Zato sem zgodovino razdelil na **datirane faze cikla** po algoritmu Bry in
Boschan v različici Pagan in Sossounov. To je akademski standard: poišče lokalne
vrhove in dna v oknu devetdesetih dni, vsili izmenjavanje, in odvrže faze,
krajše od 120 dni ali manjše od 25 %. Meja ni ročno izbrana.

Dobil sem devet faz, štiri rastoče in pet padajočih:

| vrsta | od | do | dni | BTC |
|---|---|---|---|---|
| padec | 2017-12-16 | 2018-12-15 | 364 | −84 % |
| rast | 2018-12-15 | 2019-06-26 | 193 | +306 % |
| padec | 2019-06-26 | 2020-03-12 | 260 | −62 % |
| rast | 2020-03-12 | 2021-04-13 | 397 | +1209 % |
| padec | 2021-04-13 | 2022-11-21 | 587 | −75 % |
| rast | 2022-11-21 | 2024-03-13 | 478 | +364 % |
| padec | 2024-03-13 | 2024-09-06 | 177 | −26 % |
| rast | 2024-09-06 | 2025-01-21 | 137 | +97 % |
| padec | 2025-01-21 | 2026-02-05 | 380 | −41 % |

Kandidat mora zmagati v večini rastočih **in** v večini padajočih faz. Kdor zmaga
samo v eni vrsti, ni izboljšava, ampak stava na režim.

---

## Kar je preživelo: nič, ampak eno je blizu

Bodimo takoj jasni. Od vseh preizkušenih kandidatov ni **nobeden** prestal
celotnega merila. Vseeno pa nista vsi neuspehi enaki, in troje je vredno
poznati.

### Ciljanje volatilnosti

To je tehnika, ki jo uporabljajo vsi, mi pa je nimamo. Zarattini računa utež kot
`min(0,25 / σ, 200 %)`, Man Group in AQR delata isto. Naš lean je binaren, nič
ali vse.

Ideja je, da se pozicija zmanjša, ko sredstvo divja, in poveča, ko se umiri:

```
pozicija = signal × clip( ciljna_volatilnost / σ60 , 0 , kapa )
```

σ60 je šestdesetdnevna volatilnost do včeraj, torej brez pogleda naprej.

Rezultat me je presenetil po doslednosti. **Vseh šest različic na BTC in vseh
dvanajst na knjigi je dvignilo Sharpe in Sortino.** Nobene izjeme.

Na BTC:

| | Sharpe | Sortino | CAGR | MaxDD | čas v trgu |
|---|---|---|---|---|---|
| danes | 1,35 | 2,20 | 55 % | −45 % | 38 % |
| cilj 30 %, brez vzvoda | 1,49 | 2,50 | 31 % | **−18 %** | 23 % |
| cilj 70 %, do 2x | 1,50 | 2,53 | 76 % | −39 % | 52 % |

Na knjigi:

| | Sharpe | Sortino | CAGR | MaxDD | čas v trgu |
|---|---|---|---|---|---|
| danes | 1,47 | 2,28 | 39 % | −28 % | 21 % |
| hierarhično, brez vzvoda | 1,61 | 2,57 | 26 % | **−16 %** | 13 % |
| hierarhično + IDM, brez vzvoda | 1,67 | 2,68 | **38 %** | −21 % | 16 % |
| hierarhično + IDM, do 2x | 1,68 | 2,74 | 51 % | −26 % | 22 % |

Zdaj pa intervali. Sortino ni dokazan pri nobeni:

| | d Sortino |
|---|---|
| hierarhično + IDM, brez vzvoda | +0,41 **[−0,05, +0,92]** |
| hierarhično + IDM, do 2x | +0,46 [−0,17, +1,12] |

Prva zgreši za pet stotink. Boleče blizu, ampak zgrešeno je zgrešeno.

Najhujši padec pa **je** dokazan:

| | d MaxDD |
|---|---|
| BTC, cilj 30 % | +23,7 **[+11,5, +38,5]** |
| knjiga, hierarhično brez vzvoda | +13,1 **[+5,6, +23,0]** |

To sta edini številki v petih dneh, kjer interval leži ves na pravi strani ničle.

Kaj to pomeni po domače. Ciljanje volatilnosti **ni** izboljšava donosa. Je
dokazan zmanjševalec padca. Kar se natanko ujema s tem, čemu je namenjeno v
literaturi, saj ga AQR in Man Group ne uporabljata za višji donos, ampak za
predvidljivo tveganje.

Ponudba je torej menjava z znanim tečajem, ne izboljšava:

| hierarhično + IDM, brez vzvoda | |
|---|---|
| padec | −28 % postane −21 % |
| letni donos | 39 % ostane 38 % |
| čas v trgu | 21 % postane 16 % |

Skoraj enak donos, sedem točk plitvejši padec, manj časa v trgu. Od vsega
izmerjenega je to najbolj privlačna ponudba.

Ovira je resna: zahteva delne pozicije. Če hočeš ostati pri binarnem, tega ne
moreš imeti.

### Samo tri sredstva namesto šestih

Najbolj zanimiv rezultat, ki je hkrati binaren in ne zahteva ničesar novega.

| | Sharpe | Sortino | CAGR | MaxDD |
|---|---|---|---|---|
| šest, 50/10/10/10/10/10 | 1,47 | 2,28 | 39 % | −28 % |
| tri, enake uteži | **1,53** | **2,48** | 41 % | −28 % |

Interval je +0,19 [−0,37, +0,78], torej ni dokazano. V rastočih fazah zmaga le
1 od 4.

Zakaj ga vseeno omenjam: to je **tretja neodvisna meritev, ki kaže v isto smer.**

Prva je bil test širine univerzuma na 225 kovancih s Coinbasea. Na hold-outu
monotono slabše z vsakim dodanim kovancem: pri treh 0,77, pri desetih 0,12, pri
tridesetih −0,24.

Druga je bila korelacijska matrika tvojih šestih. Povprečna korelacija je 0,73,
in iz nje sledi množitelj razpršitve IDM = 1,09. Carver ga omejuje na 2,5 in
pravi, da prva peščica instrumentov IDM običajno podvoji, torej na okoli 2,0.
Tvojih šest ga dvigne na 1,09. **Razpršitev med njimi je skoraj nična, vedejo se
kot eno sredstvo.**

Edina izjema je HYPE, ki korelira 0,42 do 0,52 z ostalimi. Vsi drugi pari so med
0,80 in 0,91.

### Stopnjevana velikost pozicije

Namesto vsega ali nič drži toliko, kolikor od štirih vstopnih pogojev drži. Na
celi zgodovini BTC izgleda odlično:

| | Sortino | CAGR | konec | provizije |
|---|---|---|---|---|
| danes, binarno | 2,20 | 55 % | 101x | 15,7 % |
| stopnjevano k≥2 | **2,54** | 58 % | **123x** | **49,3 %** |

Tri stvari so proti, in vsaka bi zadoščala sama.

Prvič, interval je [−0,26, +0,91]. Ni dokazano.

Drugič, skoraj vsa prednost pride iz enega leta. Leto 2020 prispeva +2,42,
leto 2024 odnese −1,44. Brez leta 2020 ostane od razlike +0,33 samo +0,10.

Tretjič, in to je najbolj poveden podatek. Poglej razliko pri različnih
stopnjah provizije:

| okno | 0,00 % | 0,30 % | 1,00 % |
|---|---|---|---|
| cela zgodovina | +0,52 | +0,33 | −0,09 |
| **validacija** | **+0,00** | −0,28 | −0,91 |
| hold-out | +0,76 | +0,43 | −0,27 |

Na validacijskem oknu je razlika **ničelna že pri ničelni proviziji**. Ni tako,
da bi imelo prednost, ki jo stroški pojedo. Prednosti tam preprosto ni.

Zraven še cena: 58 vstopov namesto 28, povprečna pozicija 34 dni namesto 48,5,
in v desetih letih in pol polovica kapitala v provizijah.

---

## Kar sem dokazal, da je slabše

Te so v nekem smislu najbolj uporabne, ker ti prihranijo čas.

### Tedensko ukrepanje namesto dnevnega

`d Sortino -0,53 [-1,08, -0,04]`

Preizkusil sem to, ker literatura o višjih časovnih okvirih pravi, da zmanjšajo
zaporedne lažne signale. Nastavitve, ki dajo štiri do osem signalov letno, naj
bi ujele resnične spremembe trenda.

Da bi bil test čist, nisem spreminjal nobenega parametra. Signal ostane
popolnoma isti dnevni signal, spremeni se le, kako pogosto se sme po njem
ukrepati.

Rezultat je nedvoumen. Sharpe pade s 1,47 na 1,18, najhujši padec pa se poglobi
z −28 % na **−44 %**. Mesečno je še slabše, Sharpe 1,07.

Razlog je očiten, ko pomisliš, kje lean zasluži. Njegova vrednost je pravočasen
izstop. Če izstop zamakneš za do teden dni, sediš v padcu, ki se mu je hotel
izogniti. Signal je isti, vsa škoda pride iz zamude.

**Dnevna odločitev je nosilna. Ne redči je.**

### Denar ob izstopu preliti v BTC

`d MaxDD -15,5 [-24,7, -6,8]`

Zamisel: sredstvo brez signala naj ne čaka v gotovini, ampak naj gre v BTC, če
ima BTC signal.

Končna vrednost izgleda spektakularno, 165x proti 34x, in letni donos 62 %
namesto 39 %. Ampak izpostavljenost se podvoji, s 21 % na 43 %, in najhujši
padec je statistično značilno globlji.

To ni izboljšava. Je odločitev, da hočeš biti bolj v BTC. Če to hočeš, jo lahko
sprejmeš, samo ne pod pretvezo, da si nekaj izboljšal.

### Glasovanje, ki zahteva soglasje vseh petih

`d Sortino -0,51 [-1,01, -0,04]`

Namesto ene periode trackline sem jih vzel pet in glasoval. Pri pragu dveh ali
treh je rezultat praktično nespremenjen, Sharpe 1,48 oziroma 1,43 proti 1,47.
Šele zahteva po soglasju vseh petih značilno škodi.

Zanimivo ob tem: v zvezni obliki, kjer se pozicije povprečijo namesto glasujejo,
povprečenje škodi. V binarni obliki glasovanje ne škodi, a tudi ne pomaga.
**Perioda trackline torej ni posebej pomembna, dokler ne zahtevaš soglasja.**

### Ansambel petindvajsetih specifikacij

`d zložen [-100918, -144]`

Interval je v celoti negativen, torej dokazano slabše.

Ta neuspeh je poučen. Ansambel je naredil točno to, kar obljublja: premagal je
**povprečnega** člana za +0,18. Padel je zato, ker je naša obstoječa perioda 75
najboljši član v mreži, in ansambel jo zamenja s povprečno.

Perioda 75 ni bila izbrana na teh podatkih, prišla je iz Pine skripte.

### Zarattinijeva strategija kot celota

`d zložen [-154558, -178]`

Ker sem njihov Combo že prej reproduciral, sem ga peljal skozi isto merilo.

| | Sharpe | CAGR | MaxDD | čas v trgu |
|---|---|---|---|---|
| naš lean | 1,35 | **55 %** | −45 % | 38 % |
| Zarattini Combo | 1,40 | 25 % | −20 % | 20 % |

Razmerja so podobna, donos pa je manj kot polovica, ker je v trgu skoraj
polovico manj časa. Njihova strategija na naših podatkih ni boljša od naše. Je
bolj zadržana različica iste ideje.

---

## Kar ne prenese na naše podatke

Brez posebne razlage, ker so vsi padli na isti način.

| zamisel | številka |
|---|---|
| širina univerzuma | hold-out: 3 kovanci 0,77, 30 kovancev −0,24 |
| uteži po tveganju | vsi intervali vsebujejo ničlo, drseče leto 38 / 43 / 50 % |
| statične uteži po tveganju | hold-out P(boljši) 22 % |
| enake uteži namesto 50/10 | Sharpe 1,25 proti 1,47 |
| mesečno ukrepanje | Sharpe 1,07 proti 1,47 |
| knjižno stikalo po BTC | 0 od 4 rastočih faz |
| pas brez trgovanja | validacija 1,78, hold-out 0,20 |
| nadaljnje prilagajanje parametrov | gnezdeni walk-forward: razlika točno 0,00 |
| zunanji podatkovni viri | makro vrata se sprožijo na 11 od 2600 dni |

Pas brez trgovanja je vreden dveh stavkov, ker je učbeniška past. Na validaciji
kaže lep vrh pri 1,78 proti 1,59, na hold-outu pa pade na 0,20.

Da bi jo prepoznal brez hold-outa, poglej, kaj pas sploh prihrani. Uravnavanje
stane 0,37 enote od 100 v enaindvajsetih mesecih, pas ga zbije na 0,09.
Prihranek je torej 0,28 enote, Sharpe pa se premakne za 0,19. Vzrok in učinek
nista istega reda velikosti.

**Če je učinek veliko večji od svojega razloga, je to sreča.**

---

## Kar je potrjeno kot že pravilno

Preveril sem tudi nasprotno smer, torej ali bi bilo bolje kaj **zaostriti**.

Hitrost izstopa, Sortino na celi zgodovini BTC:

| izstop po | 1 dnevu | 2 dneh | **3 dneh, danes** | 4 dneh | 5 dneh |
|---|---|---|---|---|---|
| | 2,01 | 2,08 | **2,22** | 2,16 | 1,77 |

Današnja nastavitev je vrh, štirje dnevi so tik za njo. To je plato, ne konica,
kar je dobra oblika. Ne premikaj v nobeno smer.

Trajno dno pri 0, 5 in 10 % da 2,20, 2,22 in 2,24 na celi zgodovini, po oknih pa
se izenači. Zanimivo je, kako se dno obnaša po fazah: pri desetih odstotkih
zmaga v **vseh štirih** rastočih fazah in v **nobeni** padajoči. To je natanko
vedenje kupi in drži. Dno torej ni izboljšava, je gumb proti kupi in drži.

---

## Dve stvari, ki sem ju sam zamešal

### Razvrščanje po negativnem Sortinu

Trdil sem, da vsi kandidati padejo iz istega razloga, in to podprl s Sortini v
padajočih fazah. Luka je opozoril, da je to sumljivo, in imel je prav.

Ko je povprečen donos negativen, se razmerje obrne. Pri isti izgubi dobiš **manj**
negativno številko, če bolj niha:

| povprečen donos | nihanje navzdol | Sortino |
|---|---|---|
| −5 % | 10 % | −0,50 |
| −5 % | 20 % | −0,25 |

Druga vrstica izgleda boljše, čeprav je izguba enaka in tveganje dvakrat večje.

Ponovil sem z zloženo izgubo in lestvica ni bila ista. Ansambel tracklinov je
bil po Sortinu peti, po pravem merilu pa prvi. Natančen vrstni red sem umaknil.

Ostane groba povezava: korelacija med izpostavljenostjo v padcu in zloženo
izgubo je −0,82.

**Pravilo za naprej: v obdobjih, kjer se izgublja, primerjaj zloženo izgubo, ne
razmerij.** To velja tudi za starejše zapise v `TESTING_LOG.md`.

### Priporočilo uteži po tveganju

V eni od prejšnjih različic poročila sem priporočil uteži po tveganju, ker se je
najhujši padec na hold-outu skrajšal s −16 % na −12 %.

Luka je podvomil, da je razlika premajhna za dodano zapletenost. Preveril sem z
bootstrapom in imel je prav. Vsi trije intervali vsebujejo ničlo, verjetnost, da
je boljši, je 49 % na validaciji in 50 % na hold-outu, torej met kovanca. Tudi
tisti štiritočkovni prihranek pri padcu ima interval [−1,6, +6,4].

Priporočilo sem umaknil.

---

## Kaj bi torej naredil

**Ne bi spreminjal ničesar.** To ni privzeta izbira iz lenobe. Je edino, kar
podatki podpirajo, potem ko je dvajset zamisli padlo.

**Bi pa resno premislil zmanjšanje na tri ali štiri sredstva.** Ne zato, ker je
dokazano, ampak zato, ker isto smer kažejo tri neodvisne meritve: test širine na
225 kovancih, IDM 1,09, in neposredna primerjava treh proti šestim.

**Če bi kdaj popustil pri binarnem**, bi vzel ciljanje volatilnosti kot obrambni
sloj, ker je edino z dokazom. Vendar kot izrecno menjavo, ne kot izboljšavo.

**Vsak prihodnji kandidat gre skozi isti postopek.** Interval zaupanja mora
izključevati ničlo, in zmagati mora v večini rastočih in v večini padajočih faz.
Ta postopek bi v teh petih dneh ustavil vse kandidate, preden bi karkoli
spremenil, in bi mi prihranil dva napačna zaključka.

**In nazadnje tisto, kar še vedno ugibamo.** Provizija 0,30 % na stran je
predpostavka, ne meritev. Je edini vhod v celoten backtest, ki ga ne poznamo. Pri
0,10 % postane stopnjevanje spet zanimivo, pri 0,60 % je celo današnja oblika
preveč aktivna. Ta ena meritev odloči več kot vseh dvajset preizkusov skupaj,
stane pa dve zapisani številki na dan.

---

## Kje so skripte

| kaj | datoteka |
|---|---|
| datiranje faz cikla | `testing/scripts/faze_ciklov.py` |
| protokol faz, 12 kandidatov | `testing/scripts/protokol_faze.py` |
| ciljanje volatilnosti in Zarattini na BTC | `testing/scripts/profesionalni_protokol.py` |
| hierarhična konstrukcija na knjigi | `testing/scripts/knjiga_profesionalno.py` |
| samo binarni kandidati na knjigi | `testing/scripts/knjiga_binarno.py` |
| stopnjevanje, bootstrap in razčlenitev po letih | `testing/scripts/stopnjevanje_globinsko.py` |
| stopnjevanje na BTC, cela baterija | `testing/scripts/graded_btc_podrobno.py` |
| stopnjevanje na šestih sredstvih | `testing/scripts/graded_alti.py` |
| uteži po tveganju, bootstrap in statična pot | `testing/scripts/utezi_ali_se_splaca.py` |
| parametrski ansambel | `testing/scripts/ansambel.py` |
| hitrost izstopa in dno | `testing/scripts/ostrina_izstopa.py` |
| preverba brez patologije Sortina | `testing/scripts/preveri_mehanizem.py` |
| pas brez trgovanja | `testing/scripts/knjiga_stroski_tveganje.py` |
| širina univerzuma | `testing/scripts/sirina2.py` |

Podrobno poročilo z vsemi tabelami je v `testing/porocilo_nacrt_altcoini.md`.
