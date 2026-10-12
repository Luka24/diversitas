# Načrt: štiri ideje iz Worda (3.6.2026), testirane na današnjem lean

Oktober 2026. Izhodišče je dokument `Diversitas_vprašanja_3.6.2026.docx` (moja
vprašanja in odgovori nanje). Skoraj vse iz njega je bilo testirano 5.–10. julija,
vendar na lean pred prenovo 10. avgusta (vstop je takrat še odločal trackline, ni bilo
Donchiana in ne 5 % dna) in deloma s postopkom, ki je pri izbiri uporabljal hold-out.
Teh verdiktov zato ne prenašamo samodejno. Ponovno ne testiramo vsega, ker bi bilo to
ribarjenje. Izbrane so štiri ideje, pri katerih je prenova spremenila mehanizem ali pa
so se spremenili podatki.

| # | ideja | vrsta testa | pričakovan izid |
|---|---|---|---|
| 1 | blow-off izstop (25 % nad tracklineom in RSI > 80) | kandidat proti osnovi | odprto |
| 2 | buffer 3 % prilagojen volatilnosti kovanca | kandidat proti osnovi, samo alti | odprto |
| 3 | MVRV kot varovalka | test, ali se pravilo sploh da pošteno preveriti | verjetno "ne da se" |
| 4 | pristranskost preživelih | meritev, ne kandidat | koliko so alti napihnjeni |

---

## Pravila, ki veljajo za vse štiri

1. **Najprej zapis, potem zagon.** Vsaka skripta ima merila v uvodnem komentarju,
   preden se prvič požene, tako kot `ura_zakljucka.py`. Ta načrt se commita pred prvim
   zagonom, da je iz zgodovine gita razvidno, da merila niso bila prilagojena izidu.
2. **Največ dve različici na idejo, obe določeni tu.** Brez iskanja najboljšega praga.
   Če se po izidu pojavi "še ena različica bi bila boljša", se zapiše za naslednji krog
   in se ne požene zdaj.
3. **Sprejem po faznem protokolu** (`protokol_faze.py`): C1 zmaga v vsaj 3 od 4
   rastočih faz, C2 v vsaj 3 od 5 padajočih, C3 v vsaj 70 % od 84 kombinacij treh faz,
   C4 95 % interval na celi zgodovini izključuje nič. Vse štiri, sicer ostane osnova.
4. **Popravek za več testov.** Testa 1 in 2 imata skupaj tri kandidate. Pri C4 zato
   zahtevamo interval 98,3 % (Bonferroni, 0,05 / 3), ne 95 %.
5. **Meja šuma.** Test ure zaključka je pokazal, da sama izbira ure premakne Sortino
   za ±0,4. Razlika med kandidatom in osnovo, ki je manjša od tega, se poroča kot
   "v šumu", tudi če gre slučajno skozi merila.
6. **Robustnost na uri (samo BTC).** Kandidat, ki se nanaša na BTC, mora zmagati
   (višji Sortino od osnove) pri vsaj 16 od 24 ur zaključka svečke. Urni podatki so že
   v `testing/data/sources/BTC_coinbase_1h.parquet`.
7. **Kontrole.** Vsak test ima pozitivno kontrolo (nekaj, kar mora dati znan izid,
   sicer je napaka v kodi) in, kjer gre, negativno kontrolo (placebo, ki ne sme
   zmagati).
8. **Produkcija se ne spremeni v tem krogu**, tudi če kandidat zmaga. Sprejet kandidat
   gre najprej v vzporedno spremljanje na dashboardu.

---

## 1. Blow-off izstop

### Kaj smo videli

Na današnjem lean je blow-off glavni izstop: pri BTC 16 od 27 izstopov, pri ETH 14 od
22. Po izstopu zaradi blow-offa je bil ponovni vstop v mediani dražji (BTC +9 %, višje v
13 od 16; ETH +14 %, 11 od 14), cena 60 dni kasneje pa višja (BTC +34 %, ETH +17 %).
Po drugi strani je isto pravilo ETH umaknilo pred tremi zlomi (februar 2020 do −51 %,
maj 2021 do −44 %, januar 2018 do −39 % v naslednjih 60 dneh). Od 16 BTC blow-offov jih
je 9 iz let 2016–17. Stara ablacija (29.7., še pred prenovo) je bila neodločena:
interval [−0,05, +0,54].

### Kaj pravijo drugi

- **Klasični trendni sledilci ne prodajajo zaradi pregretosti.** Turtle pravila,
  Clenow in Faber puščajo dobiček teči. Donos trendnega sledenja prihaja iz debelega
  repa, iz nekaj velikih poslov, in cilj dobička ta rep odreže.
- **Concretum (Zarattini, Pagani, Barbon 2025, "Catching Crypto Trends")** na BTC in
  altih nima izstopa zaradi pregretosti. Edini izstop je drseči stop: višji od
  včerajšnjega stopa in sredine kanala. To je v bistvu naš trackline, ki se ne more
  znižati.
- **V prid pravilu** so predvsem strategije na TradingView z "extension" izstopom (RSI
  nad pragom). Rezultati so na posameznih grafih brez izven-vzorčnega preverjanja, zato
  jih jemljemo kot šibek dokaz.
- Splošni zaključek drugih: fiksen cilj ali prodaja v moči je primerna za vračanje k
  povprečju, za trend pa praviloma škodi. Naše pravilo je mešanica, ker zahteva tudi
  RSI > 80, zato je vprašanje res odprto.

### Kandidati, zapisani vnaprej

- **A0 osnova:** današnji lean.
- **A1 brez blow-offa:** `blowoff_dist_pct = 999`. Ker blow-off tudi blokira vstop, se
  hkrati odstrani ta blokada. To je ista sprememba, ne dve.
- **A2 ATR-percentil iz Worda:** blow-off, ko je RSI > 80 in
  `(close − trackline) / ATR(14)` presega 97,5. percentil iste količine na tem kovancu,
  izračunan samo iz preteklosti (razširjajoče se okno do včeraj, najmanj 365 dni
  zgodovine, prej velja današnje pravilo). Izbran je 97,5 in ne 95, ker je Word
  predlagal oba, 97,5 pa je bliže današnji pogostosti sprožitve. 95 se ne požene.

RSI prag 80 in ATR 14 ostaneta, ker sta učbeniški vrednosti in se ju ne testira.

### Kako

1. Najprej BTC in ETH posebej, fazni protokol, vsak kandidat proti A0.
2. Nato knjiga (BTC 50 %, alti po 10 %) z normaliziranimi utežmi (popravek mrtve
   gotovine iz `fantomska_gotovina.py`).
3. BTC na vseh 24 urah zaključka (pravilo 6).

**Pozitivna kontrola:** A1 s pragom 25 namesto 999 mora dati natanko A0, bit za bit.

**Negativna kontrola (placebo):** blow-off izstope nadomestimo z enakim številom
izstopov na naključne dni, ko je lean notri in je cena vsaj 10 % nad tracklineom,
200 ponovitev. Če pravi blow-off ni boljši od vsaj 80 % placebov, nima informacije o
vrhu in samo naključno skrajša posle. To pove, ali je pravilo pametno, ne samo, ali
pomaga.

**Repi:** ločeno poročamo največji drawdown in najslabših 60 dni po vsakem izstopu, ki
ga A1 ne bi naredil. Pravilo vnaprej: A1 je zavrnjen, če knjigi poslabša največji
drawdown za več kot 5 odstotnih točk, tudi če gre skozi C1–C4.

**Diagnostika (ni merilo):** isto brez let 2016–17, da vidimo, ali je rezultat samo
leto 2017.

### Odločitev

- A1 ali A2 sprejet samo, če izpolni C1–C4 na knjigi in na BTC, robustnost na uri ter
  pravilo o drawdownu.
- Če zmagata oba, ima prednost A1, ker je preprostejši (pravilo manj).
- Če noben, ostane 25 %, in tega praga ne nastavljamo.

---

## 2. Buffer prilagojen volatilnosti

### Kaj smo videli

3 % pomeni pri BTC 0,85 dnevnega nihanja, pri LINK pa 0,55. Alt torej pade pod mejo ob
manjšem šumu. Julija je bil ATR buffer zavrnjen (k = 1,5 je bil na načrtu +22 %, na
validaciji slabši), vendar je takrat buffer odločal tudi o vstopu, danes pa samo o
izstopu.

### Kaj pravijo drugi

- **Carver** (Systematic Trading, Advanced Futures Trading Strategies) vse, kar je
  odvisno od cene, meri v enotah volatilnosti. Tako lahko isto pravilo z istimi
  parametri teče na vseh instrumentih. Fiksen odstotek za vse je ravno tisto, česar ne
  priporoča.
- **Turtle pravila** imajo stop v enotah N (ATR), ne v odstotkih.
- **Concretum** prilagaja volatilnosti velikost pozicije (ciljna volatilnost 25 %), ne
  stopa.
- Splošno sprejeto: drseči stopi na podlagi ATR so standard v trendnem sledenju. Ni pa
  enotnega dokaza, da so boljši od fiksnih, ko je velikost pozicije že prilagojena
  volatilnosti.

### Kandidat, zapisan vnaprej (samo eden)

- **B1:** buffer kovanca = 3 % × (σ kovanca / σ BTC). σ je standardni odklon dnevnih
  log donosov v zadnjih 365 dneh, zamaknjen za en dan. BTC ima tako vedno točno 3 %.
- **Zakaj 365 dni:** buffer naj odraža običajen šum kovanca, ne trenutnega režima. Na
  režim odziven buffer (ATR(14)) je bil julija zavrnjen in ga ne ponavljamo. Drugih oken
  ne poganjamo.
- **Brez spodnje in zgornje meje.** Če pride buffer pri HYPE v prvem letu nad 10 %, to
  zapišemo, ne popravljamo.
- Dokler kovanec nima 365 dni zgodovine, velja 3 %.

### Kako

1. Vsak alt posebej (ETH, SOL, LINK, BNB, HYPE): fazni protokol, kjer je dovolj faz;
   SOL in HYPE imata kratko zgodovino, zato samo poročilo.
2. **Glavno merilo:** knjiga, C1–C4.
3. **Preverba mehanizma:** delež izstopov, po katerih se lean v 30 dneh vrne po višji
   ceni (danes: ETH 8 od 22, LINK 6 od 15, BNB 6 od 19). Pri B1 mora pasti. Če Sortino
   zraste, ta delež pa ne pade, je izboljšava prišla od drugod in ji ne verjamemo.

**Pozitivna kontrola:** BTC pod B1 mora biti bit za bit enak osnovi. To je vgrajeno v
pravilo in se preveri z assertom.

**Negativna kontrola:** obrnjeno pravilo, buffer = 3 % × (σ BTC / σ kovanca), ki je pri
bolj nihajočih kovancih ožji. Če zmaga tudi to, učinek ni volatilnost, ampak samo
naključna sprememba bufferja, in B1 je zavrnjen.

### Odločitev

B1 sprejet, če izpolni C1–C4 na knjigi, izid je izven meje šuma, preverba mehanizma
zdrži in negativna kontrola ne zmaga.

---

## 3. MVRV

### Kaj smo videli

MVRV je zdaj brezplačen (CoinMetrics community API, `CapMVRVCur`, BTC od 2010 in ETH,
dnevno). Prag 3,5 iz dokumenta se je v oknu lean sprožil samo v letu 2017 in na začetku
2021. Letni vrhovi: 5,9 (2013), 4,7 (2017), 4,0 (2021), 2,8 (2024), 2,5 (2025). Od
2021 se nista sprožila niti 3,5 niti 3,0.

### Kaj pravijo drugi

- **arXiv 2607.26188 ("Bitcoin Runs on a Clock", 2026):** vrhovi petih oscilatorjev za
  iskanje vrha (Pi Cycle, MVRV, Mayer, Puell) po ciklih monotono padajo, dna pa so
  vsakič višja. Zato mora vsak prag, nastavljen na pretekle cikle, nehati delovati. Ti
  kazalci so se pokvarili v zaporedju "natančni, nato prezgodnji, nato tiho".
- **Analize vrha oktobra 2025** (Axel Adler, bit.com): BTC je dosegel vrh pri približno
  126.000 $ in nato padel za več kot 50 %, MVRV pa je imel vrh pri 2,52 in se ni
  približal 3,5. Prvič je velik vrh prišel brez kateregakoli klasičnega on-chain
  signala. Razlaga: ETF-ji in podjetniške zakladnice ne ustvarjajo refleksivnega
  maloprodajnega navdušenja, na katerem so bili pragovi umerjeni.
- **Akademska kritika:** enotni pragovi za različne verige niso zanesljivi, ker ima vsak
  kovanec svojo pot MVRV. Za alte MVRV ni uporaben, kar je bilo že zapisano v Wordu.

### Kandidat, zapisan vnaprej

Edina različica, ki ne gleda v prihodnost:

- **C1-MVRV:** lean ne vstopa na novo, ko je MVRV nad 95. percentilom lastnih zadnjih
  1460 dni (en cikel), zamaknjeno za en dan. Pozicije, ki so že odprte, ostanejo.
  Samo BTC.
- Fiksni prag (3,5 ali 3,0) se ne testira. Izbran je bil z vedenjem o preteklih vrhovih,
  zato bi bil vsak izid pristranski.

### Kako

1. **Najprej štetje, brez donosov:** kolikokrat in v katerih obdobjih se pravilo sproži,
   in koliko lean vstopov bi blokiralo. Če blokira manj kot 5 vstopov v vsej zgodovini,
   se test ustavi tukaj z zaključkom "premalo opazovanj, ni preverljivo".
2. Če jih je dovolj: fazni protokol na BTC, robustnost na uri.
3. **Opomba o podatkih:** CoinMetrics realizirano kapitalizacijo za nazaj popravlja,
   zato zgodovina ni nujno taka, kot je bila tisti dan na voljo. To zapišemo kot omejitev.

**Pozitivna kontrola:** pravilo, ki se nikoli ne sproži (percentil 101), mora dati
osnovo.

### Odločitev

Pričakujem korak 1 in zaključek "ni preverljivo". Točka "MVRV ostaja netestiran, ker
je plačljiv" v `coverage_and_methodology.md` se zapre z razlogom: podatek je
brezplačen, pravilo pa ni preverljivo in drugi poročajo, da je prenehalo delovati.
MVRV lahko ostane na dashboardu kot informacija, ne kot pravilo.

---

## 4. Pristranskost preživelih

### Zakaj

ETH, SOL, LINK, BNB in HYPE so izbrani s tem, kar vemo danes. Julijska kontrola (XRP,
BNB, ADA) je bila spet na kovancih, ki so preživeli. Word je to tveganje omenil že
junija.

### Kaj pravijo drugi

- **Ammann, Burdorf, Liebi, Stöckl (Univerza St. Gallen), "Survivorship and delisting
  bias in cryptocurrency markets":** 3.904 kovancev, 2014–2021. Pristranskost je 0,93 %
  na leto pri uteži po kapitalizaciji in 62,19 % na leto pri enakih utežeh. Premija
  majhnosti je v vzorcu preživelih precenjena za 50 %.
- Od približno 20.000 žetonov, ki jih CoinMarketCap spremlja od 2017, jih je okoli 60 %
  neaktivnih ali umaknjenih.
- **Concretum** je svoj test na altih naredil na podatkih brez pristranskosti preživelih
  (21.616 kovancev, pogoj: vsaj leto kotacije in vsaj 2 mio $ mediane dnevnega prometa).
  To je standard, ki mu sledimo.

Za našo knjigo je pomembno: alti imajo enake uteži (po 10 %), zato smo bližje primeru z
enakimi utežmi, kjer je pristranskost velika. Odprto je, koliko jo lean ublaži, ker
izstopi iz padajočih kovancev.

### Kaj se meri (ni kandidata, je meritev)

**Univerzum, določen vnaprej:** vsak 1. januar pet USDT parov na Binance z največjim
prometom v zadnjih 90 dneh. Izločeni so BTC, stablecoini, zaviti žetoni (WBTC ...) in
vzvodni žetoni (UP/DOWN, BULL/BEAR). Ni pa izločen noben kovanec, ki je kasneje
propadel. Sestava se spremeni enkrat letno; kovanec, ki ga Binance med letom umakne, gre
na zadnjo ceno v gotovino.

**Podatki:** data.binance.vision ima mesečne in dnevne svečke tudi za umaknjene pare
(LUNAUSDT, FTTUSDT ...), s kontrolno vsoto za vsako datoteko. Binance se začne julija
2017, zato je okno 2018–2026. Shrani se v `testing/data/sources/`.

**Tri knjige, vse z nespremenjenim lean in normaliziranimi utežmi:**

1. današnja fiksna knjiga (izbrana danes);
2. dinamična knjiga (BTC 50 % + pet altov po 10 % iz letnega univerzuma);
3. dinamična knjiga kupi in drži.

**Rezultat:**

- razlika 1 − 2 je ocena, koliko so današnji rezultati altov napihnjeni zaradi izbire;
- razlika 2 − 3 je prednost lean na pošteni množici kovancev. To je glavno merilo:
  C1–C4 (oziroma faze, ki jih okno 2018–2026 pokrije).

**Študije primera (samo poročilo):** LUNA maj 2022 in FTT november 2022. Datum izstopa,
izguba od vrha posla in koliko bi izgubil kupi in drži.

**Pozitivna kontrola:** BNB iz arhiva data.binance.vision mora biti enak BNB, ki ga
`graded_alti.cene()` že dobi z Binance API.

### Odločitev

- Če lean ohrani prednost na dinamični knjigi (C4 izključuje nič), je to močan argument,
  da alt del ne sloni na izbiri kovancev.
- Če prednost izgine, izbire altov ne utemeljujemo z backtestom, ampak samo z
  likvidnostjo, in to povemo naprej.
- **Če LUNA izpade slabo, v tem krogu ne dodajamo pravila zanjo.** Pravilo, narejeno po
  enem dogodku, je prilagajanje šumu. Zapiše se kot znano tveganje.

---

## Vrstni red in čas

| korak | delo | ocena |
|---|---|---|
| 0 | commit tega načrta (zamrznitev meril) | 5 min |
| 1 | test 3, MVRV, korak 1 (štetje) | pol dneva |
| 2 | test 1, blow-off: BTC, ETH, knjiga, placebo, 24 ur | 1–2 dni |
| 3 | test 2, buffer: alti, knjiga, obrnjena kontrola | 1 dan |
| 4 | test 4, preživeli: prenos arhiva, univerzum, tri knjige | 2–3 dni |
| 5 | poročilo za vse štiri, tudi neuspehe | pol dneva |

MVRV je prvi, ker je najkrajši in verjetno zapre točko. Preživeli so zadnji, ker
potrebujejo nove podatke, ne smejo pa odpasti: od vseh štirih edino ta meri, ali so
naše obstoječe številke poštene.

## Skripte

| test | skripta | izhod |
|---|---|---|
| 1 | `testing/scripts/blowoff_izstop.py` | `testing/data/blowoff_izstop.json` |
| 2 | `testing/scripts/buffer_volatilnost.py` | `testing/data/buffer_volatilnost.json` |
| 3 | `testing/scripts/mvrv_varovalka.py` | `testing/data/mvrv_varovalka.json` |
| 4 | `testing/scripts/prezivetje_altov.py` | `testing/data/prezivetje_altov.json` |

## Viri

- Zarattini, Pagani, Barbon (2025), Catching Crypto Trends:
  https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/
  in povzetek https://www.cxoadvisory.com/technical-trading/crypto-asset-trend-following-strategies/
- Bitcoin Runs on a Clock (arXiv 2607.26188): https://arxiv.org/pdf/2607.26188
- MVRV in vrh 2025: https://axeladlerjr.com/bitcoin-mvrv-ratio-definition-formula-cycle-signals/ ,
  https://www.bit.com/square/mvrv-explained
- Ammann, Burdorf, Liebi, Stöckl, Survivorship and delisting bias in cryptocurrency
  markets: https://alexandria.unisg.ch/handle/20.500.14171/108037
- Delež neaktivnih žetonov: https://backtrex.com/en/blog/survivorship-bias-trading-backtesting
- Binance arhiv: https://github.com/binance/binance-public-data/
- Trendno sledenje in puščanje dobička: https://www.turtletrader.com/trick/ ,
  https://twoquants.substack.com/p/why-trend-systems-work
- Volatilnostni stop: https://www.luxalgo.com/library/concept/volatility-stop.md
- Primer "extension" izstopa: https://www.luxalgo.com/library/indicator/hjHwHStD-trend-following-rsi-strategy/

## Rezultati (2026-10-11)

Vsi štirje testi so tekli po zgoraj zapisanih merilih. Pozitivne kontrole so
povsod prešle. Produkcija ostane nespremenjena.

### Test 3, MVRV: ni preverljivo

Pravilo (MVRV včeraj nad 95. percentilom zadnjih 1460 dni) je aktivno 153 od
3861 dni, v štirih epizodah, vse v 2017 in začetku 2021. Po juniju 2021 ni
epizode. Blokiralo bi 4 od 30 vstopov osnove (2017-05-15, 2017-06-08,
2017-12-17, 2021-03-11). 4 < 5, zato se je test ustavil po koraku 1, donosi niso
izračunani. MVRV ostane na dashboardu samo kot informacija.

### Test 1, blow-off: oba kandidata zavrnjena, 25 % ostane

| Sortino | A0 danes | A1 brez blow-offa | A2 ATR-percentil |
|---|---|---|---|
| BTC | 2,22 | 2,23 | 2,24 |
| ETH | 2,10 | 1,99 | 1,74 |
| knjiga | 2,43 | 2,43 | 2,39 |

MaxDD ETH: −44,6 % (A0) proti −65,5 % (A1 in A2). MaxDD knjige: −43,7 %, −45,3 %,
−45,9 %. C2 in C4 padeta povsod. Ure zaključka: A1 zmaga na 11/24, A2 na 13/24
(potrebno 16). Placebo: A0 je boljši le od 69 % (BTC) oziroma 68 % (ETH)
naključno postavljenih izstopov, kar ni ločljivo od naključja. Diagnostika (ni
merilo): od 2018 dalje bi bil BTC brez blow-offa nekoliko boljši (1,58 proti
1,45), ETH obratno.

### Test 2, buffer po volatilnosti: B1 zavrnjen

Mediane bufferjev B1: ETH 4,0 %, SOL 5,5 %, LINK 5,0 %, BNB 3,5 %, HYPE 6,6 %.
Sortino osnova → B1: ETH 2,10 → 2,06, SOL 1,02 → 0,87, LINK 0,46 → 0,33,
BNB 1,31 → 1,39, HYPE 1,38 → 1,25. Knjiga 2,43 → 2,41 (v šumu). C1 drži, C2-C4
padejo. Mehanizem formalno drži (35 % proti 37 % izstopov s ponovnim nakupom
dražje v 30 dneh), a premalo, da bi pomenil kaj. Obrnjeno pravilo B− da +0,01.

### Test 4, preživeli: napihnjenost okoli 0,35 Sortina, prednost lean ni dokazana

Univerzum (top 5 po prometu v Q4 prejšnjega leta, vsaj 365 dni zgodovine):

| leto | kovanci |
|---|---|
| 2019 | ETH, BCC, BNB, LTC, NEO |
| 2020 | ETH, BNB, XRP, EOS, BCHABC |
| 2021 | ETH, XRP, LTC, LINK, BNB |
| 2022 | ETH, BNB, SOL, SAND, MANA |
| 2023 | ETH, DOGE, XRP, BNB, SOL |
| 2024 | ETH, SOL, XRP, BNB, AVAX |
| 2025 | ETH, DOGE, XRP, SOL, PEPE |
| 2026 | ETH, SOL, BNB, ZEC, XRP |

Okno 2019-01-01 do 2026-08-30:

| knjiga | Sortino | MaxDD | CAGR |
|---|---|---|---|
| (i) današnji alti, lean | 1,99 | −34,2 % | 41,3 % |
| (ii) dinamični alti, lean | 1,64 | −35,2 % | 31,7 % |
| (iii) dinamični alti, kupi in drži | 1,25 | −83,7 % | 43,5 % |

(i) − (ii): Sortino +0,35, CAGR +9,6 o.t. To je ocena, koliko backtesta altov
izvira iz izbire kovancev za nazaj. (ii) proti (iii): rast 0/4, padec 4/4,
kombinacije 48 %, C4 ne (interval vključuje nič). Po vnaprej zapisanem pravilu
izbire altov ne utemeljujemo z backtestom. Lean na altih zmanjša padce, ne
moremo pa trditi, da prinese več donosa kot kupi in drži.

Študiji primera: LUNA, zadnji izstop lean 2022-05-08 (−43 % na poslu), kupi in
drži −100 %. FTT, lean zunaj od 2022-04-13, novembrski zlom ga ne zadane.

Odstopanja od načrta:
- Pozitivna kontrola BNB je ob prvem zagonu padla samo na zadnjem dnevu
  predpomnilnika cene() (2026-08-30, −1,3 %, sveča shranjena pred zaprtjem).
  Ostalih 3219 dni se ujema natančno, zato se zadnji dan pri primerjavi izpusti.
- Bitcoin Cash je bil v 2019 (BCC) in 2020 (BCHABC) izbran pod oznakama, ki ju je
  Binance kmalu preimenoval, zato zanju v tistem letu ni podatkov. V teh dveh letih
  so bili v knjigi 4 alti namesto 5.
- Okno se začne 2019, ne 2017 kot ostali testi, zato 1,99 ni primerljivo z 2,43.
