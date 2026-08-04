# Korak 5 — prilagodljivi mrtvi pas

**Status:** načrt in predregistracija, pred izvedbo
**Podatki:** BTC, Binance, 2019-03-09 → 2026-07-29, 2700 barov
**Stroški:** 0,30 % na stran, povsod
**Novi parametri:** 0
**Ocena časa:** 5–6 ur

---

## 0. Zakaj ta korak in zakaj ima več moči kot prejšnji

Mrtvi pas je fiksnih **3 %** okoli razpona. Vstop zahteva ceno nad `razpon + 3 %`,
izstop pod `razpon − 3 %`.

Letna nihajnost BTC v našem oknu niha med **11 % in 248 %**, mediana 50 %. Fiksni
3 % pas je torej v mirnem trgu velika ovira, v divjem pa šum. Strogost pravila se
giblje **obratno od tega, kar bi človek hotel**.

**Ključna razlika proti 4. koraku:** premor je ugriznil desetkrat v sedmih letih,
zato je bilo vprašanje nerešljivo. Mrtvi pas se presoja **vsak dan** — na 2700
dneh. Primarni test tega koraka zato ne bo Sortino na 21 poslih, ampak
**dnevna študija dogodkov na dnevih, kjer se odločitev razlikuje**, kjer gre
vzorec v stotine.

### Vhodna diagnostika (že izmerjena, šteje kot hipoteza, ne kot dokaz)

Za dneve, ko smo bili zunaj trga in je bil kršen **samo en** vstopni pogoj,
donos BTC v naslednjih 20 dneh:

| edini kršeni pogoj | dni | donos +20 dni | 95 % IZ |
|---|---|---|---|
| **cena pod razponom + 3 %** | 118 | **+5,67 %** | [−0,35, +11,90] |
| razpon ne raste | 115 | +1,81 % | [−5,13, +8,73] |
| medvedji režim | 29 | premalo | — |
| *(primerjava)* premor | 118 | +2,12 % | [−2,56, +5,95] |
| *(izhodišče)* vsi dnevi | 2680 | +3,27 % | [+1,14, +5,56] |

Mrtvi pas je edini pogoj, ki blokira **nadpovprečne** dneve. To je razlog za ta
korak — a **ni dokaz**: interval objame ničlo, 118 dni se ob 20-dnevnem horizontu
strne v ~6 neodvisnih blokov, in izbral sem najvišjo od sedmih skupin. Diagnostika
je generirala hipotezo; dokaz mora priti iz svežega testa v §5.

---

## 1. Kaj pravi literatura

### 1.1 Opozorilo, ki oblikuje celoten korak

**Kim, Tse & Wald (2016), *Journal of Financial Markets* 30** — »Time Series
Momentum and Volatility Scaling«. Ugotovitev: presežni donos strategij sledenja
trendu je **v veliki meri posledica skaliranja z nihajnostjo, ne trendnega
signala**. Brez skaliranja je alfa 0,39 % mesečno proti 1,08 % s skaliranjem, in
nescalirana strategija je statistično neločljiva od kupi-in-drži.

**Zakaj je to za nas kritično.** Prilagodljivi pas je po konstrukciji skaliranje z
nihajnostjo v preobleki: pas je širši, kadar je nihajnost visoka, torej vstopamo
manj v divjih obdobjih in več v mirnih. To **samo po sebi** izboljša Sortino, tudi
če je vstopni signal enako slab. Zato je v §5.7 obvezen **placebo z nihajnostjo**:
vzamem današnjo strategijo A in ji zgolj skaliram pozicijo tako, da dobi enak
profil izpostavljenosti glede na nihajnost. Če to izenači prilagodljivi pas, potem
nismo izboljšali vstopov — le po ovinku uvedli skaliranje.

### 1.2 Metodologija izbire med različicami

**Bailey & López de Prado**: »The Probability of Backtest Overfitting« (2014) in
»The Deflated Sharpe Ratio« (2014). Verjetnost, da je izbrani zmagovalec
prilagojen preteklosti, hitro raste s številom poskusov; Sortino/Sharpe je treba
popraviti za to, da je bil izbran izmed mnogih.

Za to strategijo je PBO že izmerjen: **0,694 na 137 poskusih**. Najboljša
nastavitev je bila v 69 % primerov podpovprečna zunaj vzorca. To je razlog, da
korak 5 preizkusi **tri različice, ne trideset**.

**Plato, ne konica** — standardna praksa: izbrani parametri morajo ležati sredi
široke ravnine, ne na ozki konici. Pri nas je to že merjeno pri 14 parametrih.

### 1.3 Kje se od literature razhajamo, in zakaj

**Zarattini, Pagani & Barbon (2025)**, »Catching Crypto Trends« (SSRN 5209907):
ansambel Donchian kanalov z **različnimi dolžinami** namesto ene izbrane, plus
sizing po nihajnosti; neto Sharpe 1,58, CAGR 30 %, alfa +14 % proti BTC na
2015–2025.

Njihov odgovor na izbiro parametra je torej: **ne izbiraj, povpreči**. Mi smo
ansambel v tem projektu že testirali in **zavrnili**: pričakovanje naprej je bilo
enako, stalo pa je 3 o. t. padca in 50 % več obrata, in izgubil je v 0 od 4
walk-forward shem.

Razhajanje je razložljivo in ga ne skrivam: oni vodijo **rotacijski portfelj 20
kovancev**, kjer ansambel diverzificira tudi po sredstvih. Mi imamo **eno
sredstvo**, kjer ansambel doda samo obrat. Če se korak 5 izjalovi, je ansambel
vreden ponovnega premisleka — a na več sredstvih, ne na BTC samem.

### 1.4 Skrita past prilagodljivih pragov

Splošno opozorilo iz literature o prilagodljivih oknih: prilagodljivi prag skoraj
vedno uvede **nov parameter** (dolžina okna, množitelj), in izbira tega okna je
enako podvržena prilagajanju kot prag, ki ga nadomešča.

**Tej pasti se izognemo tako, da ne uvedemo nobene nove količine** — glej §2.

---

## 2. Različice — nič novih parametrov

Prilagodljivi pas sestavim iz dveh količin, ki **že obstajata v kodi** in ju
strategija že računa (ostali sta po 3. koraku, ker ju dashboard riše):

```
pas_t  =  3 %  ×  ( annual_vol_t / vol_avg50_t )
```

* `annual_vol` — 20-dnevna nihajnost, letno preračunana
* `vol_avg50` — 50-dnevno povprečje te nihajnosti
* `3 %` — obstoječi `track_buf_pct`, nespremenjen

Razmerje je po konstrukciji ~1 v povprečju, zato **sidro 3 % ostane**. Izmerjeno
na naših podatkih: povprečje **3,05 %**, mediana 2,84 %.

| percentil | 1 | 5 | 25 | 50 | 75 | 95 | 99 |
|---|---|---|---|---|---|---|---|
| pas | 1,42 % | 1,67 % | 2,31 % | 2,84 % | 3,68 % | 4,77 % | 6,66 % |

Obe količini sta **zaostali** (trailing), torej brez pogleda v prihodnost — in
kalibracija ni narejena na celotnem vzorcu, kar bi bilo tiho puščanje.

| | pravilo | novi parametri |
|---|---|---|
| **A** | fiksnih 3 % na obeh straneh | — (kontrola, današnje stanje) |
| **E** | prilagodljivi pas na **obeh** straneh | 0 |
| **F** | prilagodljivi pas **samo za vstop**, izstop ostane fiksen | 0 |

**Zakaj F.** Pas nastopa v vstopu (`nad razpon + pas`) in v izstopu
(`pod razpon − pas`), in učinka sta nasprotna: širši pas v divjem trgu pomeni
**težji vstop**, a tudi **poznejši izstop**. F to razdvoji in pove, kje je učinek —
brez novega parametra.

### Česa NE bom naredil

- **ne bom omejil pasu na razpon** (npr. med 1,5 % in 6 %) — to je nov parameter
- **ne bom vrtel sidra 3 %** — obstoječi sweep že obstaja
- **ne bom spreminjal oken 20 in 50** — podedovani sta, ne izbrani
- **ne bom uvedel ATR namesto nihajnosti** — ATR bi zahteval novo dolžino okna
- **ne bom testiral na ETH**, da bi »potrdil« izid — ETH je korak 11, enkrat
- **ne bom popravljal pragov iz §6**, ko bom videl rezultate

---

## 3. Izvedba

Različice se pišejo v `testing/scripts/adaptive_buffer.py`, **ne** v `lean/`.
Zamrznjena referenca iz 2. koraka ostane veljavna, dokler odločitev ne pade.

**Vrata, ki morajo uspeti, sicer se korak ustavi:** različica A mora reproducirati
zamrznjeno serijo pozicij bar za barom, vključno s SHA256 `957d3bc9…`.

---

## 4. Kaj se meri

**Primarno (dnevno, vzorec v stotinah):**
- donos +20 dni na dneh, kjer se odločitev o pasu razlikuje
- ločeno za dneve, kjer različica **vstopi** in A ne, ter obratno

**Sekundarno (na poslih, vzorec ~21):**
- Sortino, Sharpe, MaxDD, končni mnogokratnik
- izpostavljenost, obrat, število poslov
- zajem navzgor / navzdol
- povprečna zamuda vstopa

**Nadzor:**
- porazdelitev dejanskega pasu (min, percentili, max) — da ne uide v absurd
- delež dni, ko je pas pod 1,5 % ali nad 6 %

---

## 5. Testi

### 5.1 Dnevna študija dogodkov — PRIMARNO

Za vsak dan, kjer se `above_tl` razlikuje med A in različico, izmeri donos BTC v
naslednjih 20 dneh. Blokovni bootstrap, dolžina bloka 20 (enaka horizontu),
10 000 vzorcev.

**To je edini test tega koraka, ki ima dovolj moči, da lahko izključi ničlo.**
Če je ne izključi, mehanizma ni in ostalo je nepomembno.

### 5.2 Sparjeni blokovni bootstrap na dnevnih donosih, ΔSortino proti A

Iste prevzorčene dneve na obeh serijah. Pričakujem, da bo objel ničlo — 21 poslov
je 21 poslov. Zabeleženo vnaprej.

### 5.3 Doslednost po podobdobjih

Ista štiri okna kot v 4. koraku, določena vnaprej, zato primerljivo:

```
I    2019-03-09 → 2021-01-31      III  2022-12-01 → 2024-09-30
II   2021-02-01 → 2022-11-30      IV   2024-10-01 → 2026-07-29
```

### 5.4 Izenačena izpostavljenost

Vsaka različica pomanjšana na izpostavljenost A, nato primerjava MaxDD in zajema
navzdol. V tem projektu se je prednost pri padcu **trikrat** izkazala za artefakt
časa v trgu.

### 5.5 Kje se različice sploh razlikujejo

Število dni razlike in njihov časovni razpon. Če je razlika stisnjena v eno
obdobje, to ni ugotovitev o pravilu, ampak o tistem obdobju — natanko past, ki je
v 4. koraku razkrinkala različico B.

### 5.6 Porazdelitev pasu

Realizirani pas po percentilih in po letih. Če v kakšnem obdobju zaide pod 1 % ali
čez 10 %, to zapiši — tudi če rezultat izgleda dobro.

### 5.7 PLACEBO Z NIHAJNOSTJO — obvezna vrata (Kim, Tse & Wald)

Najpomembnejši test tega koraka.

Vzemi **A brez sprememb** in ji skaliraj pozicijo z `vol_avg50 / annual_vol`,
normalizirano na enako povprečno izpostavljenost. To je čisto skaliranje z
nihajnostjo, **brez kakršnekoli spremembe vstopnih pravil**.

* Če ta placebo doseže enako izboljšanje kot E, potem E **ni boljši vstop**, ampak
  skaliranje z nihajnostjo po ovinku. V tem primeru je poštena ugotovitev, da naj
  se skaliranje uvede odkrito kot sizing (kjer je merljivo in razumljivo), ne
  skrito v vstopni pogoj.
* Če E prekaša placebo, potem je v pasu nekaj, česar skaliranje ne ujame.

### 5.8 Revizija pogleda v prihodnost

`lookahead_audit.py` na E in F. Pas je po konstrukciji zaostal, a to je argument;
predregistracija zahteva meritev.

### 5.9 Disciplina reference

SHA256 serije pozicij vsake različice v JSON.

---

## 6. Odločitveno pravilo — vnaprej

Zavestno drugačno kot v 4. koraku. Tam sem zahteval, da interval zaupanja na
Sortinu izključi ničlo — česar 21 poslov ne more doseči, zato test ni mogel
uspeti. Tu je **primarni dokaz dnevni**, kjer je moč resnična, poslovne metrike pa
so potrditev.

### Sprejmi E ali F, če velja VSE:

| | pogoj |
|---|---|
| 1 | **dnevno**: na dneh, kjer različica vstopi in A ne, je donos +20 dni pozitiven in **IZ izključuje ničlo** |
| 2 | Sortino boljši od A na celotnem oknu |
| 3 | boljši v **≥ 3 od 4** podobdobij |
| 4 | prednost preživi **izenačeno izpostavljenost** |
| 5 | **prekaša placebo z nihajnostjo** (§5.7) |

### Delni izidi in kaj z njimi

- **1 uspe, 2–4 padejo** → mehanizem obstaja, a ga pojedo stroški in obrat.
  Zapiši; premisli o F ali o širšem pasu samo za izstop (korak 7).
- **1 uspe, 5 pade** → ni boljši vstop, ampak skaliranje z nihajnostjo. Zapiši in
  **premakni skaliranje v sizing**, kjer je odkrito — ne obdrži ga v pogoju.
- **1 pade** → mehanizma ni. Ustavi korak, pojdi na korak 6 (vstop po večini
  pogojev). Prilagodljivi pas se ne uvaja.

### Kaj bi bilo sumljivo

- razlika stisnjena v eno podobdobje → glej 4. korak, različica B
- E bistveno boljša od F **in** obratno na drugem podobdobju → šum
- realizirani pas pogosto pod 1 % → strategija vstopa na šumu, tudi če številke
  izgledajo lepo

---

## 7. Rezultati koraka

| datoteka | vsebina |
|---|---|
| `testing/nacrt_korak5.md` | ta dokument — hkrati predregistracija |
| `testing/scripts/adaptive_buffer.py` | harness, pas kot vstavljiva funkcija |
| `testing/data/adaptive_buffer_BTC.json` | meritve + SHA256 vsake serije |
| `testing/korak5_rezultati_BTC.md` | tabele, placebo, sklep |

---

## 8. Kaj pričakujem — zapisano vnaprej

1. Dnevna študija **bo** imela dovolj moči, da pove nekaj določnega — za razliko
   od 4. koraka. **Verjetno.**
2. E bo imela nižjo izpostavljenost od A (širši pas v divjih obdobjih prevlada).
   **Verjetno.**
3. Placebo z nihajnostjo bo ujel **velik del** razlike med E in A. **Verjetno** —
   prav to je ugotovitev Kim/Tse/Wald.
4. F (samo vstop) bo bližje A kot E, ker se največ dogaja pri izstopu.
   **Negotovo.**
5. Najverjetnejši končni izid: **mehanizem obstaja na dnevni ravni, a ga na ravni
   poslov pojedo stroški in ga večinoma pojasni skaliranje z nihajnostjo** — in
   pravi zaključek bo, da naj se nihajnost uporabi odkrito pri sizingu, ne skrito
   v vstopnem pogoju.

---

## Viri

- Kim, Tse & Wald (2016), *Time series momentum and volatility scaling*, Journal
  of Financial Markets 30 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2786955
- Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Bailey & López de Prado, *The Deflated Sharpe Ratio*
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Zarattini, Pagani & Barbon (2025), *Catching Crypto Trends*
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907
- Moskowitz, Ooi & Pedersen, *Time Series Momentum*
  — https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum
