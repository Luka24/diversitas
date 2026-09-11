# ETF, drugi krog: podatkovne luknje in davek

Stanje 1. septembra 2026. Nadaljevanje `porocilo_nacrt_etf.md`.

> **Številke v prvem poročilu so presežene.** Provizija je bila tam 0,10 % na
> stran, tu je **0,20 % na vsak posel** (povratni posel torej 0,40 %). Vse je
> preračunano. Poleg tega je bila v nalagalniku napaka, ki je tiho skrajšala
> zgodovino; opisana je v delu 1e.

---

## Povzetek

**Zgodovina se je podaljšala z osmih na dvajset let, a le mesečno.** Za vsak
rokav sem izmeril vse razpoložljive daljše serije. Sedem od osmih verig je
uporabnih samo na mesečni frekvenci, ker se ameriški sklad zapre ob 22.00 po
srednjeevropskem času, londonska vrstica pa ob 17.30. Portfelj 1 je zdaj
mesečno uporaben od **2005-12-06** in Portfelj 2 od **2008-01-02**, kar prvič
zajame leto 2008. Dnevni testi ostanejo pri 2018 oziroma 2019.

**Evrskih obveznic z ameriškimi ni mogoče nadomestiti, in to je izmerjeno.**
AGG proti evrski zavarovani knjigi gre z dnevne korelacije 0,39 na mesečno 0,41;
TIP proti evrskim indeksiranim obveznicam z 0,16 na 0,18. Pri vseh drugih parih
skok z dnevne na mesečno korelacijo pokaže, da gre za uro zaprtja. Tu se ne
popravi pri nobeni frekvenci. Oba sta zavrnjena.

**Manjkal je cel podatek, ne le zgodovina: obrestna mera gotovine.** Zdaj je v
sistemu ECB-jeva serija, EONIA od 1999 in €STR od oktobra 2019, 7082 opazovanj.
Razpon v vzorcu je od −0,59 % do +5,75 %. Pripisovati gotovini 0 % ni nevtralno,
ampak je datirana predpostavka, ki je bila napačna v obe smeri.

**Davčna ovojnica, ki bi visok obrat rešila, tem skladom skoraj gotovo ni na
voljo.** INR zahteva, da sklad po naložbeni politiki vlaga v izdajatelje iz
EU, EGP ali OECD. Od osmih je nedvoumno primeren **eden** — evrske indeksirane
obveznice. MSCI World vsebuje Hongkong in Singapur, EM je pretežno zunaj OECD,
zlati ETC sploh ni na seznamu primernih instrumentov.

**Po davku je razlika večja, ne manjša.** Portfelj 1: kupi in drži brez
uravnavanja da 12,01 % pred davkom in **10,29 %** po unovčenju; trendni sloj
−0,21 % in **−1,04 %**. Trendni sloj pri tem plača **5.701 EUR** davka, čeprav
pred davkom izgublja — FIFO realizira dobičke na posameznih poslih, pobot izgub
pa je omejen na koledarsko leto.

**Uporabna ugotovitev, ki ne zahteva nobene strategije:** uravnavanje samo po
sebi stane davek. Brez uravnavanja 0 EUR, z letnim 1.742 EUR, s četrtletnim
2.208 EUR. Vsaka prodaja ponastavi uro dobe imetja in odmakne prag, po katerem
je stopnja nič. Uravnavanje z novimi vplačili ta strošek odpravi v celoti.

---

## Del 1: podatki

### 1a. Kaj je manjkalo

| rokav | pravi podatki od | manjka do 2000 | zavrženo zaradi zamrznjenih cen |
|---|---|---|---|
| World | 2013-01-01 | 13,0 let | 3,3 leta |
| EM | 2014-05-30 | 14,4 let | — |
| SmallCap | 2018-03-27 | 18,2 let | — |
| Quality | 2014-10-06 | 14,8 let | — |
| GlobAgg | 2019-01-01 | 19,0 let | 1,1 leta |
| InflLink | 2008-01-02 | 8,0 let | — |
| Gold | 2011-04-08 | 11,3 let | — |
| Commod | 2017-01-09 | 17,0 let | — |

Portfelj 1 je omejeval SmallCap, Portfelj 2 pa GlobAgg.

### 1b. Merilo, ki je odločilo

Za vsak par (rokav, kandidat) se na prekrivnem oknu izračuna korelacija dnevnih,
tedenskih in mesečnih donosov, sledilna napaka in razlika v CAGR. Razlika med
dnevno in mesečno korelacijo pove, **kakšna** je napaka:

| vzorec | pomen | ocena |
|---|---|---|
| dnevna nizka, mesečna visoka | serija je prava, poravnava dni ni | uporabno mesečno |
| obe nizki | drugo sredstvo | zavrni |

Meritev je to razliko dejansko pokazala:

| rokav | kandidat | 1d | 1w | 1m | TE %/leto | zamik pp | ocena |
|---|---|---|---|---|---|---|---|
| World | `^990100-USD-STRD` | 0,788 | 0,958 | **0,983** | 10,28 | +2,03 | mesečno |
| World | SPY | 0,651 | 0,906 | 0,964 | 14,38 | −3,00 | mesečno |
| EM | EEM | 0,811 | 0,959 | 0,975 | 12,64 | +0,63 | mesečno |
| EM | VEIEX | 0,828 | 0,950 | 0,948 | 10,98 | +1,11 | mesečno |
| SmallCap | NAESX | 0,659 | 0,917 | 0,971 | 18,05 | −1,07 | mesečno |
| Quality | SPHQ | 0,634 | 0,875 | 0,926 | 15,09 | −2,71 | mesečno |
| GlobAgg | IBGM.AS | 0,753 | 0,828 | 0,891 | 4,45 | +0,55 | mesečno |
| GlobAgg | **AGG** | 0,394 | 0,461 | **0,411** | 8,52 | −1,65 | **zavrni** |
| GlobAgg | **VBMFX** | 0,366 | 0,424 | **0,399** | 8,34 | −1,52 | **zavrni** |
| InflLink | **TIP** | 0,160 | 0,257 | **0,184** | 11,53 | −2,21 | **zavrni** |
| InflLink | **VIPSX** | 0,146 | 0,245 | **0,173** | 11,42 | −2,01 | **zavrni** |
| Gold | GC=F | **0,912** | 0,965 | 0,979 | 7,28 | −0,24 | **dnevno** |
| Commod | `^BCOM` | 0,879 | 0,974 | 0,986 | 7,83 | +2,21 | mesečno |
| Commod | GSG | 0,744 | 0,867 | 0,848 | 15,67 | −1,37 | zavrni |

Prage sem določil vnaprej: zavrni pri mesečni korelaciji pod 0,85, dnevno pri
dnevni nad 0,90, sicer mesečno.

### 1c. Zakaj najgloblja serija ni najboljša

SPY in indeks MSCI World oba sežeta do 1999. Prvi ima mesečno korelacijo 0,964
in prehiteva rokav za 3,00 točke na leto, ker so ameriške delnice premagale
svetovne — ta razlika je resnična in je popravljati ne smem. Drugi ima 0,983 in
zaostaja za 2,03 točke, ker je to **cenovni** indeks in razlika je dividendni
donos. Enak doseg, nasprotna kakovost.

Izbirno pravilo je zato: med kandidati, ki podaljšajo okno, obdrži tiste znotraj
0,03 od najboljše mesečne korelacije, nato vzemi najglobljega. Postopek se
ponovi, zato je EM sestavljen iz EEM do 2003 in VEIEX do 1999.

Zamik ravni se popravi **le, kadar ima mehanski vzrok**, in ta je zapisan v
registru, ne izpeljan iz velikosti zamika:

| oznaka | kdaj | popravek |
|---|---|---|
| `measured` | cenovni indeks lastnega merila | izmerjeni zamik na prekrivanju |
| `cash` | blagovni indeks tipa excess return | dejanska obrestna mera gotovine |
| brez | sklad drži druge stvari | nobenega |

### 1d. Izbrane verige in kaj se pridobi

| rokav | veriga | seže do | dnevno veljavno od |
|---|---|---|---|
| World | `^990100-USD-STRD` | 1999-01-04 | 2013-01-02 |
| EM | EEM → VEIEX | 1999-01-04 | 2003-04-14 |
| SmallCap | NAESX | 1999-01-04 | 2018-03-27 |
| Quality | QUAL → SPHQ | 2005-12-06 | 2013-07-18 |
| GlobAgg | IBGM.AS | 2008-01-02 | 2019-01-02 |
| InflLink | brez | 2008-01-02 | 2008-01-02 |
| Gold | GC=F | 2000-08-30 | 2000-08-30 |
| Commod | `^BCOM` | 1999-01-04 | 2017-01-09 |

| knjiga | dnevno uporabno | mesečno uporabno | pridobljeno |
|---|---|---|---|
| Portfelj 1 | 2018-03-27 | **2005-12-06** | +12,3 let |
| Portfelj 2 | 2019-01-02 | **2008-01-02** | +10,9 let |

Spojeni okvir nosi `daily_valid_from`. Kdor požene dnevno strategijo čez spojeni
del, meri razliko v uri zaprtja, ne strategije.

### 1e. Napaka, ki jo je ta krog razkril

Predpomnilnik ni imel začetnega datuma v ključu. Prvi klic je bil
`load_panel("P1")`, ki zaradi `min_quality` zahteva podatke od 2018-03-27, in
posnetek se je shranil od tam. Naslednji klic, ki je zahteval od 2013, je dobil
nazaj 2018 — brez napake, brez opozorila. Ablacija je zato tekla na 8,6 leta
namesto 13,9. Popravek: posnetek je vedno polna zgodovina, `start` samo reže,
kar se vrne. Regresijski test je dodan.

### 1f. Kar ostane luknja

- **Dnevni testi se ne podaljšajo.** Obdobje 2000–2018 odgovarja na vprašanje o
  režimih, ne na vprašanje o dnevnem pravilu.
- **Evrske indeksirane obveznice nimajo podaljška.** Zgodovina ostane 2008.
- **Neodvisnega drugega vira še ni.** Stooq zavrača avtomatske zahtevke, poti do
  CSV izdajatelja nisem mogel preveriti; ne bom je priporočil, dokler je ne
  vidim delovati. Vse cene so zaenkrat en sam vir.
- **Približno 1,5 % dni na leto je prenesenih**, večinoma britanski bančni
  prazniki, ki so delovni dnevi TARGET. Označeno, ne zglajeno.
- **`^BCOM` zaostaja za približno šest tednov** za tekočim dnem.

### 1g. Obrestna mera gotovine

| leto | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| povprečje | −0,55 % | −0,57 % | −0,01 % | **+3,21 %** | **+3,64 %** | +2,18 % | +2,01 % |

Strategija, ki leto dni sedi zunaj trga in se ji prizna nič, je v letih 2023–2024
podcenjena za več kot tri točke.

---

## Del 2: davek

### 2a. Kako to delajo drugi

Ameriški SEC od skladov zahteva troje številk na isti strani: pred obdavčitvijo,
po obdavčitvi pred unovčenjem in po obdavčitvi z unovčenjem. Morningstar iz
tega izpelje `tax cost ratio`, Russell Investments isto imenuje `tax drag` in
opozarja, da je pri visokem obratu to največja posamična postavka. `shared/tax.py`
vrne isto troje.

### 2b. INR: pogoj, ki ga ta univerzum ne izpolni

Pojasnila Ministrstva za finance k 7. členu ZINR, posodobljena 14. 5. 2026:
ETF in KNPVP morajo po svoji naložbeni politiki vlagati v finančne instrumente
izdajateljev s sedežem v EU, EGP ali OECD; ponudnik preveri tudi dejansko
sestavo portfelja.

| rokav | presoja | razlog |
|---|---|---|
| **InflLink** | **primeren** | evrske državne indeksirane obveznice, vsi izdajatelji so EU |
| World | sporno | MSCI World vsebuje Hongkong in Singapur, ki nista v OECD |
| SmallCap | sporno | ista težava, isti univerzum |
| Quality | sporno | ista težava, izbor iz istega univerzuma |
| EM | skoraj gotovo ne | pretežno zunaj OECD; pojasnilo MF navaja prav tak primer |
| GlobAgg | verjetno ne | Global Aggregate vsebuje kitajske državne obveznice |
| Gold | verjetno ne | ETC je dolžniški papir, ne ETF ali KNPVP; ni na seznamu |
| Commod | verjetno ne | izpostavljenost prek zamenjav, ne prek izdajateljev iz OECD |

Presoja je ponudnikova, ne moja. Zgornje je argument, ki mu ga je treba
predložiti.

Ostalo o INR: davčni dogodek šele ob izplačilu, stopnja 15 %, po petnajstih
letih brez izplačil 0 %. Vplačila 20.000 EUR prvo leto, nato 5.000 EUR letno,
skupno 150.000 EUR. Ponudniki objavljajo provizijo 0,30 % na posel z minimumom
1 do 4 EUR.

### 2c. Izračun na navadnem računu

Stopnja pada z dobo imetja (25 / 20 / 15 / 0 % pri 0, 5, 10, 15 letih), FIFO,
pobot izgub znotraj koledarskega leta, davek plačan naslednje leto.

**Portfelj 1, 2018-03-27 do 2026-09-01:**

| kandidat | pred davkom | po davku | po unovčenju | zaostanek | plačan davek |
|---|---|---|---|---|---|
| **kupi in drži, brez uravnavanja** | **12,01 %** | 12,01 % | **10,29 %** | 1,72 pp | **0 EUR** |
| kupi in drži, letno | 11,93 % | 11,81 % | 10,15 % | 1,77 pp | 1.742 EUR |
| kupi in drži, četrtletno | 11,91 % | 11,75 % | 10,11 % | 1,80 pp | 2.208 EUR |
| trendni sloj, mesečno | −0,21 % | −0,97 % | **−1,04 %** | 0,83 pp | **5.701 EUR** |
| rotacija top-k, mesečno | −0,68 % | −1,63 % | −1,78 % | 1,11 pp | 6.654 EUR |

**Portfelj 2, 2019-01-02 do 2026-09-01:**

| kandidat | pred davkom | po davku | po unovčenju | zaostanek | plačan davek |
|---|---|---|---|---|---|
| **kupi in drži, brez uravnavanja** | **8,06 %** | 8,06 % | **6,75 %** | 1,31 pp | **0 EUR** |
| kupi in drži, letno | 6,76 % | 6,44 % | 5,55 % | 1,21 pp | 3.216 EUR |
| rotacija top-k, mesečno | 2,79 % | 1,66 % | 1,58 % | 1,21 pp | 9.899 EUR |
| trendni sloj, mesečno | 1,02 % | 0,61 % | 0,61 % | 0,41 pp | 3.325 EUR |

### 2d. Past pri branju

Nižji davčni zaostanek pri trendnem sloju **ni prednost**. 0,83 točke proti 1,77
pomeni samo, da je manj dobička za obdavčiti. Prava primerjava je stolpec po
unovčenju: 10,29 % proti −1,04 %.

### 2e. Kaj model ne pozna

Drugih dobičkov in izgub, prenosa izgube v naslednje leto, dedovanja, spremembe
rezidentstva. Stopnje so parameter in jih je treba potrditi pri svetovalcu.
Obzorje simulacije je pod devet let, zato noben sveženj ne doseže niti
10-letnega praga — prav 15-letni prag pa je največja prednost kupi in drži in ga
to okno ne more pokazati. Če ga upoštevaš, se razlika v korist kupi in drži samo
poveča.

---

## Del 3: kaj se je spremenilo pri 0,20 % na posel

| meritev | pri 0,10 % | pri 0,20 % |
|---|---|---|
| prenesen sklop na World, CAGR | +0,11 % | **−0,42 %** |
| P1 trendni sloj mesečno, CAGR | +0,23 % | **−0,08 %** |
| P1 rotacija, CAGR | +0,13 % | **−0,38 %** |
| P1 kupi in drži četrtletno, CAGR | 11,91 % | 11,89 % |
| P1 trendni sloj, d Sortino | −0,97 [−1,52, −0,35] | **−1,02 [−1,57, −0,40]** |

Kupi in drži se skoraj ne premakne, ker malo trguje. Vse aktivne različice
padejo pod ničlo. Sodba protokola ostane **0 od 4 sprejetih**.

---

## Del 4: kaj rabim za odločitev

| vprašanje | zakaj ga ne morem odgovoriti sam | kaj se spremeni |
|---|---|---|
| **donos ali plitvejši padec** | ni statistično vprašanje; ciljanje volatilnosti je gumb z znanim tečajem | ali sploh predlagam ciljanje 6–10 % na P1 |
| **obzorje in vmesna izplačila** | pri 15 letih brez prodaj je stopnja 0 %, sicer 25 % | pri obzorju pod 5 let se davčni strošek aktivne strategije skoraj podvoji |
| **koliko kapitala, ali je INR v igri** | limiti 5.000 / 150.000 EUR, primeren en rokav od osmih | ali se sploh splača vprašati ponudnika za njegov seznam |
| **zamenjava skladov za davčno primerne** | obstajajo skladi brez izpostavljenosti zunaj OECD, a to ni ista naložba | odpre INR, spremeni sestavo knjige |
| **posrednik in resnični razmiki** | 0,20 % je navodilo; INR ponudniki objavljajo 0,30 % z minimumom | pri majhnih zneskih minimum prevlada nad odstotkom |
| **uravnavanje s prodajo ali z vplačili** | odvisno od tega, ali redno dodajaš kapital | davčni strošek uravnavanja 0 namesto 1.742–2.208 EUR |

Česa ne rabim: novih parametrov za trendno strategijo. Ablacija in
sedemindvajsetletni vzorec kažeta v isto smer, in to ni vprašanje nastavitve.

---

## Del 5: nove datoteke

| datoteka | kaj je |
|---|---|
| `shared/tax.py` | svežnji, FIFO, stopnja po dobi imetja, pobot izgub, INR |
| `shared/etf_data.py` | dodano: `cash_rate()`, `recommend_chain()`, popravek zamika, popravljen predpomnilnik |
| `shared/etf_universe.py` | `Proxy` z izmerjeno kakovostjo in oznako popravka zamika |
| `testing/scripts/etf_data_audit.py` | izmeri vsak nadomestek, ga oceni, zapiše ocene |
| `testing/scripts/etf_davek.py` | primernost za INR in donos pred/po davku |
| `testing/data/etf_proxy_quality.json` | ocene, ki jih bere nalagalnik |

```bash
python testing/scripts/etf_data_audit.py
python testing/scripts/etf_davek.py
cd etf && ../.venv/Scripts/python -m pytest diversitas/tests/ -q   # 24 passed
```

---

## Del 6: kaj optimizirati (Sharpe ali Sortino)

Merilo tu ni opis, ampak **izbirnik**. 135 nastavitev trendne strategije na
svetovnem indeksu, 2013–2026, 0,20 % na posel. Skripta:
`testing/scripts/etf_kriterij.py`.

### Prenos razvrstitve (Spearman pred rezom → po rezu)

| rez | Sharpe | Sortino | Calmar | Omega | Martin | CAGR |
|---|---|---|---|---|---|---|
| 2018-06-30 | +0,304 | +0,304 | +0,326 | +0,352 | +0,365 | +0,264 |
| 2020-06-30 | +0,199 | +0,197 | +0,191 | +0,203 | +0,200 | +0,158 |
| 2021-06-30 | +0,480 | +0,485 | +0,460 | +0,445 | +0,436 | +0,494 |
| 2023-06-30 | +0,048 | +0,054 | +0,045 | −0,115 | +0,048 | +0,242 |
| 2024-06-30 | +0,039 | +0,042 | +0,049 | +0,030 | +0,110 | +0,057 |
| **povprečje 7 rezov** | **+0,216** | **+0,219** | **+0,217** | +0,194 | **+0,228** | **+0,231** |
| med posameznimi leti | +0,020 | +0,006 | +0,009 | +0,048 | +0,029 | −0,011 |

**Razlika med merili je v tretji decimalki.** Vzvod ni izbira merila, ampak
dolžina okna: na sedmih letih rho okoli +0,3, med posameznimi leti okoli nič.

Opomba k metodi: en sam rez (2023-06-30) je dal rho okoli nič ali negativno pri
vseh razmerjih in je izgledal kot dokaz, da razvrščajo šum. Sedem rezov pokaže,
da je bil ta rez nereprezentativen.

### Natančnost merila (vezani bločni bootstrap, 2000 vzorcev)

| merilo | ocena | 95 % interval | širina/ocena |
|---|---|---|---|
| Omega | 1,103 | [+0,961, +1,249] | **0,26** |
| Sharpe | 0,373 | [−0,142, +0,864] | 2,70 |
| **Sortino** | 0,514 | [−0,186, +1,256] | **2,81** |
| CAGR | 2,3 % | [−1,2 %, +5,9 %] | 3,02 |
| Calmar | 0,156 | [−0,040, +0,525] | 3,61 |
| Martin | 0,375 | [−0,074, +1,557] | **4,34** |

Sortino je šumnejši od Sharpa, ker imenovalec ocenjuje iz manj opazovanj.
Merili na najhujšem padcu sta najšumnejši, ker je MaxDD ena sama skrajna
vrednost. Omega ima najožji interval in najslabši prenos — natančno merjenje
napačne stvari.

### In kar vse preglasi

| | |
|---|---|
| najboljši Sharpe v mreži | **0,529** |
| pričakovani največji Sharpe iz 135 poskusov brez učinka | **0,471** |
| popravljena verjetnost (deflated Sharpe) | **0,585** (prag 0,95) |

Zmagovalec mreže ni ločljiv od tega, kar bi 135 poskusov dalo na čistem šumu.

### Priporočilo

1. **Ne Sortino.** Ne razvršča bolje (+0,219 proti +0,216), je šumnejši, in ob
   negativnem povprečnem donosu se obrne — kar je tvoj projekt pri altcoinih že
   ugotovil. To se zgodi natanko v padajočih fazah.
2. **Če že eno število, Sharpe**, poleg njega pa MaxDD in trajanje okrevanja kot
   **ločeni** številki, ne stlačeni v razmerje.
3. **Za odločitev končna vrednost po davku**, ker razmerja pred davkom
   sistematično favorizirajo obrat.
4. **Popravi za število poskusov.** Pri 135 poskusih je prag za Sharpe 0,471.
5. **Optimiziraj čim manj.** Med posameznimi leti je razvrstitev met kovanca pri
   vsakem merilu.

### Davek v kriteriju: prag, ne člen

Po Jeffreyju in Arnottu (1993): je alfa dovolj velik, da pokrije svoj davek?

| postavka | Portfelj 1 |
|---|---|
| razlika v davčnem zaostanku | ≈ 0,9 pp/leto |
| razlika v proviziji | ≈ 0,6 pp/leto |
| **prag, ki ga mora kandidat preseči** | **≈ 1,5 pp/leto** |
| dejanski zaostanek trendnega sloja | **≈ 12 pp/leto** |

Prag ni tesen, je nedosežen za red velikosti. Davčna optimizacija tega kandidata
ne more rešiti; bodoči kandidat pa mora osnovo presegati za približno 1,5 točke
na leto, preden ga je vredno jemati resno.

Če že optimiziraš: ciljna funkcija naj bo končna vrednost po davku, najhujši
padec pa **omejitev, določena vnaprej**, in ne člen v imenovalcu — ker je prav
stlačenje padca v imenovalec tisto, kar Calmar in Martin naredi najšumnejša
merila v tabeli zgoraj.

### Popravek v `testing/scripts/stats.py`

`deflated_sharpe` je pričakoval standardni odklon Sharpov **na palico**, klic pa
mu je lahko podal letnega. Napaka je tiha in velika: imenovalec je narobe za
faktor `td`, prag eksplodira in funkcija vrne samozavestno ničlo. Dodan je
parameter `td` (privzeto 365, da se kripto klici ne spremenijo) in opozorilo v
dokumentaciji.
