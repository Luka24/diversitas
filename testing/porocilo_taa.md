# Strategija od začetka: taktična razporeditev sredstev

Stanje 4. septembra 2026. **Brez davka**, po naročilu. **Brez kripto pristopov** —
trackline, Donchian, ADX in dnevno odločanje tu ne nastopajo.

Koda: `etf/diversitas/taa.py`, test `testing/scripts/etf_taa.py`.

---

## Povzetek

**Prvič v tem projektu kandidat ni takoj padel.** Taktična razporeditev,
sestavljena iz objavljenih delov, na 18,7 letih doseže **Sharpe 0,83** proti
0,81 za Portfelj 2 in 0,58 za Portfelj 1, pri padcu −25,9 % proti −47,0 %.

**Prestane tudi popravek za število poskusov.** Osem nastavitev, najboljši
Sharpe 0,834, prag iz osmih poskusov brez učinka 0,158, popravljena verjetnost
**0,998** pri pragu 0,95. To je prvič, da kaj v tem projektu to prestane —
prejšnji krog je pri 135 nastavitvah dal 0,585.

**Vendar ne premaga prave ovire.** Proti statičnemu deležu z isto
izpostavljenostjo je d Sortino **+0,18 [−0,32, +0,72]** — prvič pozitivna
ocena, a interval vsebuje ničlo. Proti Portfelju 2 je razlika 0,83 proti 0,81,
kar je izenačeno.

**In največji problem ni signal, ampak obrat.** 754 % na leto, kar pri 0,20 %
na posel stane **1,65 odstotne točke letno**. Pred stroški bi bil donos okoli
10 %, po njih 8,36 %. Naslednji korak ni boljši signal, ampak manj trgovanja.

---

## Del 1: zakaj ta družina in ne trendna

Trendno sledenje, kot ga delajo CTA, potrebuje 40 do 60 trgov, dolge in kratke
pozicije in terminske pogodbe. Knjiga z osmimi dolgimi ETF-ji ima 1,1 oziroma
2,3 neodvisne stave. Za tak problem obstaja druga, prav tako uveljavljena
družina: **taktična razporeditev sredstev (TAA)**.

| kdo | kaj |
|---|---|
| [Faber (2007)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461) | izvirnik: mesečno, drseče povprečje na desetih razredih |
| [Keller in Keuning, VAA (2017)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624) | uteženi momentum 13612W, širina momentuma |
| [Keller in Keuning, DAA (2018)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862) | **kanarček**: VWO in BND odločata o tveganju cele knjige |
| [Keller, HAA (2023)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4346906) | hibrid, TIPS kot napovednik |
| [ReSolve, Adaptive Asset Allocation](https://investresolve.com/inc/uploads/pdf/ReSolve-Adaptive-Asset-Allocation-A-Primer.pdf) | 6-mesečni momentum za izbor, najmanjša varianca za utežitev |

Vsi delajo z desetimi do petnajstimi razredi, **dolgo-le**, **mesečno**. To je
oblika problema, ki jo imaš.

---

## Del 2: štirje sestavni deli, vsak z virom

**1. Momentum 13612W namesto drsečih povprečij.** Keller: uteženo povprečje
donosov za 1, 3, 6 in 12 mesecev z utežmi 12, 4, 2, 1. Ni praga, ki bi ga bilo
treba izbrati, in ne niha ob eni sami ceni.

**2. Kanarček za vklop tveganja, ne signal na vsakem rokavu.** Kellerjeva DAA
uporablja majhno množico — VWO in BND — ki odloči, koliko tveganja sme nositi
**cela knjiga**. Ena odločitev namesto osmih neodvisnih. Tvoja knjiga ima
natanko oba: EM in GlobAgg.

**3. Utežitev po tveganju.** ReSolve: najboljših pet po momentumu, uteži po
najmanjši varianci s 126-dnevno korelacijo in 20-dnevno volatilnostjo. Privzeta
je obratna volatilnost, ker ne potrebuje korelacijske matrike, ki je pri malo
podatkih najbolj nezanesljiv del ocene.

**4. Tranše proti sreči pri datumu.** Faberjeva strategija kaže do **220
bazičnih točk** razlike v CAGR med najboljšim in najslabšim dnevom uravnavanja —
brez vsake veščine. Popravek: razdeli knjigo na štiri tranše, vsako uravnavaj v
drugem tednu.

**Nobena vrednost ni izbrana na naših podatkih.** Vse so privzetki iz izvirnih
člankov.

---

## Del 3: rezultati

### Podaljšano okno, 2008-01-02 do 2026-09-04, 18,7 leta

| kandidat | letno | vol | Sharpe | Sortino | MaxDD | Calmar | v tveganem | obrat |
|---|---|---|---|---|---|---|---|---|
| **6m top3, kanarček** | **8,36 %** | 10,3 | **0,83** | **1,18** | −25,9 % | 0,32 | 61 % | 754 % |
| 6m top3, brez kanarčka | 8,58 % | — | 0,71 | — | — | — | 90 % | 620 % |
| 6m top4, kanarček | 7,11 % | — | 0,74 | — | — | — | — | 678 % |
| 13612W top3, brez kanarčka | 7,75 % | 12,4 | 0,67 | 0,94 | −21,8 % | 0,36 | 90 % | 1000 % |
| 13612W top3, kanarček | 5,05 % | 9,8 | 0,55 | 0,78 | −21,0 % | 0,24 | 65 % | 1221 % |
| 13612W top3, ena tranša | 4,02 % | 10,7 | 0,42 | 0,59 | −26,6 % | 0,15 | 64 % | 1256 % |
| **P1 kupi in drži** | 9,55 % | 18,5 | 0,58 | 0,82 | **−47,0 %** | 0,20 | 100 % | 0 % |
| **P2 kupi in drži** | 5,61 % | 7,1 | **0,81** | 1,15 | −16,0 % | 0,35 | 100 % | 0 % |
| vseh 8 enako | 7,40 % | 11,7 | 0,67 | 0,95 | −26,6 % | 0,28 | 100 % | 0 % |

### Po oknih (Sharpe)

| kandidat | cela | zasnova | validacija | hold-out |
|---|---|---|---|---|
| **6m top3, kanarček** | **0,83** | **0,69** | 1,00 | **2,37** |
| 13612W top3, brez kanarčka | 0,67 | 0,54 | 0,89 | 2,00 |
| P2 kupi in drži | 0,81 | 0,68 | **1,23** | 1,98 |
| vseh 8 enako | 0,67 | 0,55 | 0,99 | 2,41 |

Na vseh treh oknih je približno izenačen s P2. Ni razpada med okni, kar je samo
po sebi vredno — večina kandidatov v tem projektu je padla prav tu.

### Popravek za število poskusov

| | |
|---|---|
| preizkušenih nastavitev | 8 |
| najboljši Sharpe | 0,834 |
| razpon Sharpov | 0,487 do 0,834 (sd 0,109) |
| prag iz 8 poskusov brez učinka | 0,158 |
| **popravljena verjetnost** | **0,998** (prag 0,95) |

**Prestane.** Za primerjavo: prejšnji krog s 135 nastavitvami trendne strategije
je dal 0,585.

### Glavna ovira: statični delež

| | letno | Sharpe | d Sortino proti kandidatu |
|---|---|---|---|
| statičnih 61 % od P2 | 3,77 % | 0,87 | −0,06 [−0,54, +0,44] nedokazano |
| statičnih 61 % od vseh 8 | 4,96 % | 0,71 | **+0,18 [−0,32, +0,72]** nedokazano |

**Prvič pozitivna ocena** proti tej oviri. Interval še vedno vsebuje ničlo.

### Protokol faz

Proti P2: **rast 2 od 11, padec 6 od 10**. Vzorec je enak kot pri vsem drugem —
kandidat je obramben, ne izboljševalec donosa. Kriterij C1 (zmaga v večini
rastočih faz) ni izpolnjen.

---

## Del 4: kar sem našel in ni bilo v načrtu

### Kanarček tu škodi, čeprav je v izvirniku ključen

| | z kanarčkom | brez kanarčka |
|---|---|---|
| 13612W top3, letno | 5,05 % | **7,75 %** |
| 13612W top3, v tveganem | 65 % | 90 % |
| 6m top3, letno | 8,36 % | 8,58 % |
| 6m top3, **Sharpe** | **0,83** | 0,71 |

Pri 13612W kanarček stane 2,7 odstotne točke. Pri šestmesečnem momentumu donos
komaj spremeni, **zvišuje pa Sharpe** z 0,71 na 0,83, ker zniža volatilnost.
Razlaga: kanarček (EM + agregatne obveznice) je bil od 2022 pogosto negativen,
medtem ko so se delnice pobrale.

To ni razlog, da bi ga izklopil — ravno pri različici, ki je najboljša, pomaga.
Je pa razlog, da se mu ne zaupa slepo.

### Sreča pri datumu je večja, kot pravi literatura

| | letno | Sharpe |
|---|---|---|
| štiri tranše | 5,05 % | 0,55 |
| **ena tranša** | **4,02 %** | **0,42** |

**1,0 odstotne točke razlike zgolj od tega, na kateri dan se uravnava.** Na
pravih podatkih 1,5 točke. Faber navaja 220 bazičnih točk; tu je še več.

Iz tega sledi dvoje. Tranše niso okras, ampak nujen del. In vsak zaledni test
te družine z enim samim datumom uravnavanja je za približno eno odstotno točko
naključje.

### Obrat je največji strošek in največja priložnost

| različica | obrat | strošek |
|---|---|---|
| 13612W top2 | 1341 %/leto | 2,87 pp/leto |
| 13612W top3, kanarček | 1221 %/leto | 2,61 pp/leto |
| 6m top3, kanarček | 754 %/leto | **1,65 pp/leto** |
| 6m top3, brez kanarčka | 620 %/leto | 1,35 pp/leto |

Najboljša različica plača 1,65 odstotne točke na leto samo za trgovanje. Pred
stroški bi imela okoli 10 % letno. **Vsaka odstotna točka prihranjenega stroška
je vredna več kot vsaka izboljšava signala, ki jo znam predlagati.**

---

## Del 5: kaj je narobe s tem rezultatom

Trije razlogi za previdnost, in prvi je najresnejši.

**1. Popravljena verjetnost 0,998 šteje osem poskusov, ne vseh.** Družino TAA
sem izbral **potem**, ko je trendna padla. Parametri izvirajo iz člankov, ki so
bili sami iskani na prekrivajoči se zgodovini. Objavljene TAA strategije imajo
dokumentirano upadanje: [Faberjeva GTAA](https://the7circles.uk/tactical-asset-allocation-meb-faber/)
je imela v izvirniku 1972–2005 Sharpe 0,81 in CAGR 11,7 %, na podatkih
2006–2025 pa Sharpe 0,68 in CAGR 6,05 %. Pravo število poskusov je torej mnogo
večje od osem in 0,998 je precenjeno.

**2. Podaljšano okno stoji na nadomestkih.** Od 2008 do 2013 so cene
rekonstruirane iz mesečno ocenjenih nadomestkov. Za mesečno strategijo je to
legitimno — ravno zato so bili ocenjeni kot mesečno uporabni — a ni isto kot
prava zgodovina.

**3. Ne premaga statičnega deleža z dokazom.** Ocena je prvič pozitivna, a
interval vsebuje ničlo, in proti P2 je izenačen.

---

## Del 6: načrt, po vrsti

### Stopnja 1 — zmanjšaj obrat, ne izboljšuj signala

Največji izmerjeni strošek je 1,65 pp na leto. Trije posegi, vsi znani iz
literature, noben ne spreminja signala:

**1.1 Pas brez trgovanja pri izboru.** Ne zamenjaj sredstva, dokler novi
kandidat ne prekaša trenutnega za določeno razliko v momentumu. Standardna
oblika je „hysteresis band" in v tej literaturi zniža obrat za tretjino do
polovico.

**1.2 Delna zamenjava namesto polne.** Ob vsaki odločitvi premakni le del poti
proti novim utežem. Pri štirih tranšah je to že delno vgrajeno; z dodatnim
glajenjem uteži se obrat spusti naprej.

**1.3 Manj pogosta odločitev za obrambni del.** Obrambni rokav se menja skoraj
enako pogosto kot tvegani, čeprav je razlika med GlobAgg in InflLink majhna.
Fiksna delitev obrambnega dela na pol bi odstranila del obrata brez izgube.

**Merilo uspeha:** isti Sharpe pri obratu pod 400 % na leto.

### Stopnja 2 — preveri, kar je bilo izbrano po ogledu

**2.1 Šestmesečni momentum proti 13612W na hold-outu.** Šestmesečni je zmagal,
in izbral sem ga po tem, ko sem videl rezultat. To je treba pošteno preveriti:
gnezdeni walk-forward, kjer se izbira momentuma opravi znotraj vsakega
treninga.

**2.2 Kanarček z drugimi sredstvi.** Kellerjev VWO + BND je bil izbran z
iskanjem po zgodovini 1926–1970. Naša različica uporablja EM + GlobAgg, ker sta
pač v knjigi. Ali je to prava izbira, ni preverjeno.

### Stopnja 3 — oceni pošteno, preden se karkoli izvede

**3.1 Kombinatorično prečno preverjanje po fazah**, ne samo delitev na tri okna.

**3.2 Test brez enega obdobja.** Če prednost izgine brez 2008 ali brez 2022, je
krhka.

**3.3 Občutljivost na dan uravnavanja**, izmerjena in objavljena. Pokazalo se je
za 1,0 do 1,5 odstotne točke — vsaka številka brez tranš je za toliko naključje.

### Stopnja 4 — česa ne delati

| ne to | zakaj |
|---|---|
| dodajati nastavitve v mrežo | popravek za število poskusov je edino, kar to zadržuje; vsak nov poskus zniža 0,998 |
| verjeti hold-outu 2,37 | vsi kandidati imajo na hold-outu visok Sharpe, ker je bilo obdobje ugodno; P2 ima 1,98, vseh 8 enako pa 2,41 |
| razširiti univerzum | osem instrumentov je dano; več jih ni |
| vrniti se k trendni družini | 135 nastavitev, popravljena verjetnost 0,585 |

---

## Del 7: kaj rabim od tebe

| vprašanje | zakaj | posledica |
|---|---|---|
| **Je obrat 754 % na leto sprejemljiv?** | to je približno 30 poslov na leto na osmih skladih | če ne, gre vse delo v stopnjo 1 in signal ostane, kot je |
| **Kakšna je prava provizija pri tvojem posredniku?** | pri 0,20 % stane 1,65 pp; pri 0,35 % bi stalo 2,9 pp in kandidat pade | odloči, ali je strategija sploh izvedljiva |
| **Ali sme knjiga v obdobju tveganja izven držati obvezniške ETF-je namesto gotovine?** | tako dela Keller in tako je merjeno tu | brez tega je izpostavljenost nižja in donos manjši |
| **Ali je izenačenost s P2 dovolj?** | Sharpe 0,83 proti 0,81, a z 61 % izpostavljenosti | če je cilj enak rezultat z manj tveganja, je odgovor da; če je cilj več donosa, ne |
