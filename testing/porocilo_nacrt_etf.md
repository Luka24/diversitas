# Razširitev na ETF: načrt, koda in prve meritve

> **Presezeno.** Provizija je bila tu 0,10 % na stran, po naročilu je zdaj
> 0,20 % na vsak posel, in vse številke so preračunane v
> `porocilo_etf_podatki_davek.md`. Tam so tudi podaljsana zgodovina, obrestna
> mera gotovine, davek in popravek napake v predpomnilniku, ki je tiho skrajsala
> okno ablacije. Sklepi se ne spremenijo, postanejo pa mocnejsi.

Stanje 1. septembra 2026. Vse številke iz `testing/scripts/etf_baseline.py`,
`etf_kaj_deluje.py` in `shared/etf_data.py`, na cenah, prenesenih isti dan.

---

## Povzetek

**Načrt je izveden, ne samo predlagan.** Podatkovni nalagalnik, tri strategije,
tri plasti razporejanja, ocenjevalni panel in protokol so v repozitoriju in
tečejo. 18 novih testov, 89 starih še vedno zelenih. `testing/scripts/engine.py`
zdaj poganja ETF kot tretjo različico ob `lean` in `momentum`, brez posebnega
primera.

**Podatki so v redu, ampak ne tam, kjer bi pričakoval.** Vseh osem je
akumulativnih, zato je `close` že donos s ponovnim vlaganjem — `adjclose` se od
njega ne razlikuje niti za tisočinko odstotka. Prava past je drugje: Yahoo isti
ISIN objavlja na več borzah in **te vzporedne vrstice niso neodvisne kotacije**.
IGLN.L (USD) in EGLN.L (EUR) se 8. aprila 2011 začneta pri **isti** vrednosti
29,39. Do danes se razideta za 110 odstotnih točk. Enako CMOD.L in CMOD.MI, oba
17,46. Zato: ena borza na ISIN, valuta se pretvarja izrecno, po datiranem tečaju
ECB ob 16.00 po srednjeevropskem času.

**Uporabna zgodovina je krajša od kotirane.** IWDA.L ponovi včerajšnji zaključek
na 78 % dni v letu 2009, 81 % v 2010, 40 % v 2011–2012, nato 0,4 % v 2013 in nič
naprej. EUNA.DE na 21 % dni v 2018 in nič od 2019. Trgovalna zgodovina se torej
za Portfelj 1 začne **27. 3. 2018** in za Portfelj 2 **2. 1. 2019**. To je 8,6
oziroma 7,8 leta.

**Trendni sloj na teh knjigah pade, in to prepričljivo.** Prenesen kripto sklop
vstopnih pogojev na svetovnem indeksu doseže CAGR 0,11 % proti 12,74 % za kupi
in drži. Ni le slabši od kupi in drži — ob 34 % izpostavljenosti zajame 25 %
rasti in 25 % padcev, razmerje 0,87. Časovna izbira je slabša od naključne.
Protokol faz: **0 zmag od 5 rastočih faz, 4 od 4 padajočih**, d Sortino
**−0,97 [−1,52, −0,35]**. Interval izključuje ničlo **navzdol**.

**In to ni lastnost tega okna.** Z zgodovino, podaljšano prek ACWI in SPY na
1999–2026, ki vsebuje razpad dot-coma in leto 2008: kupi in drži 6,66 % CAGR pri
padcu −67 %, pravilo `close > SMA200` 3,79 % pri −36 %. **Enak Calmar, 0,10 v
obeh primerih.** Po devetintridesetih datiranih fazah zmaga trendno pravilo v
**0 od 19 rastočih in 18 od 18 padajočih**. Popolnoma monotono.

**Ostane natanko ena stvar z dokazom, in je ista kot pri altcoinih.** Ciljanje
volatilnosti na ravni knjige je na Portfelju 1 dokazan zmanjševalec padca:
pri cilju 6 % d MaxDD **+17,5 [+7,1, +23,7]**, pri 10 % **+8,4 [+0,5, +11,4]**.
Sortino ni dokazan pri nobeni nastavitvi. Cena je znana: pri cilju 6 % pade CAGR
z 11,9 % na 3,9 %. Gumb na osi tveganja, ne izboljšava.

**Na Portfelju 2 ne deluje niti to.** d MaxDD je **+0,0** pri vsaki nastavitvi,
ker je lastna volatilnost knjige 7,0 % in cilj skoraj nikoli ne ugrizne. Z
vzvodom do 1,5x je padec **statistično značilno globlji**, −6,8 [−11,7, −1,7].
Uteži po obratni volatilnosti so značilno slabše po Sortinu, −0,40 [−0,75, −0,11].

**Portfelj 2, kot je zapisan, je najboljši izmerjeni izdelek v tem poročilu.**
Sharpe 0,98, Sortino 1,36, najhujši padec −15,1 %, Calmar 0,45 — proti 0,77 /
1,06 / −32,8 % / 0,36 za Portfelj 1. Nič, kar sem preizkusil, ga ne izboljša.

---

## Del 0: kaj je narejeno

| datoteka | kaj je |
|---|---|
| `shared/etf_universe.py` | osem instrumentov, izbrana borza na ISIN, datum uporabnosti, verige nadomestkov |
| `shared/etf_data.py` | nalagalnik: Yahoo + tečaji ECB, koledar TARGET, oznake `traded` / `stale` / `filled`, preverjanje akumulativnosti, predpomnjenje |
| `shared/indicators.py` | dodano: ATR, ATR v %, realizirana volatilnost, Bollinger, prilagodljiv množitelj pasu, Donchianova sredina, z-vrednost |
| `etf/diversitas/config.py` | `ETFConfig`, ista oblika kot `MomentumConfig`, druge vrednosti |
| `etf/diversitas/strategy.py` | strategija 1: sledenje trendu z ATR |
| `etf/diversitas/mean_reversion.py` | strategija 2: vračanje k povprečju v smeri makro trenda |
| `etf/diversitas/rotation.py` | strategija 3: tri plasti razporejanja + merilo kupi in drži |
| `etf/diversitas/backtest.py` | ukazna vrstica |
| `etf/diversitas/tests/` | 18 testov |
| `testing/scripts/etf_eval.py` | trajanje okrevanja, zajem navzgor/navzdol, primerjava z merilom |
| `testing/scripts/etf_wfo.py` | delitev, datiranje faz, CPCV, vezani bločni bootstrap, walk-forward |
| `testing/scripts/etf_baseline.py` | osnovna meritev, šest razdelkov |
| `testing/scripts/etf_kaj_deluje.py` | ciljanje volatilnosti in uteži po tveganju |

```bash
cd etf && ../.venv/Scripts/python -m diversitas.backtest --portfolio P2 --compare
python testing/scripts/etf_baseline.py
python testing/scripts/etf_kaj_deluje.py
cd etf && ../.venv/Scripts/python -m pytest diversitas/tests/ -q     # 18 passed
```

---

## Del 1: podatkovni viri

### 1a. Primerjava štirih predlaganih ponudnikov

Vprašanje ni "kateri je najboljši ponudnik", ampak "kateri sploh nosi te
instrumente". To so irski UCITS skladi, kotirani na LSE, Xetri, Euronextu in
Borsi Italiani. Trije od štirih predlaganih so ameriški.

| vir | nosi teh 8 | opomba |
|---|---|---|
| **yfinance / Yahoo** | **da, vseh 8, preverjeno 1. 9. 2026** | edini brezplačni, ki nosi evropske vrstice. Brez ključa. Pasti spodaj |
| **Alpaca** | ne | ameriške delnice, ETF, opcije in kripto. Evropskih borz ne pokriva. Za to nalogo neuporabno |
| **Polygon.io** | ne za te vrstice | težišče so ameriški trgi. Mednarodno pokritje je omejeno in vezano na dražje pakete — pred nakupom preveri njihov seznam borz za LSE, Xetro in Euronext |
| **Alpha Vantage** | delno | ima nekaj oznak z LSE in Xetre, brezplačna omejitev je 25 zahtevkov na dan. Za dnevno osvežitev osmih instrumentov je to na meji, za zgodovinsko delo ne zadošča |

Kar na tem seznamu manjka in je za UCITS sklade dejansko najboljši vir:

**Uradna vrednost enote pri izdajatelju.** iShares in Invesco objavljata dnevno
zgodovino NAV na strani vsakega sklada. To je edini vir, pri katerem ni
vprašanja borze, valutne vrstice ali časa zaključka — vse enote so obračunane ob
istem trenutku. Nima OHLC, torej ne da najvišje in najnižje cene, ki ju
potrebujeta ATR in Donchianova sredina. Priporočena vloga: **primarni vir za
zaključne cene ali vsaj tedenska kontrola** proti borzni vrstici. Odjemalca zanj
nisem napisal, ker se je pot do CSV medtem spremenila in je ne morem preveriti,
ne da bi ugibal.

**Plačljivi:** EOD Historical Data pokriva evropske borze po ISIN po nizki ceni
in je verjetno najbolj neposredna nadgradnja, če Yahoo odpove. Tiingo je
ameriški. Refinitiv in Bloomberg sta pravilna odgovora in nista sorazmerna
velikosti tega projekta.

**O podatkih v realnem času.** Za te instrumente je pravi podatek v realnem času
licenciran po borzah in se plačuje. Vsi brezplačni viri zamujajo približno 15
minut. Vendar: ta strategija se odloča na dnevnem zaključku. Ne potrebuje
realnega časa, potrebuje **zanesljiv prenos po 17.35 po srednjeevropskem času**
in preverjanje, da je zaključek resničen in ne prenesen z včeraj. To drugo je
težji del in ga nalagalnik že dela.

### 1b. Osem instrumentov, izbrana borza

Razrešeno prek Yahoojevega iskanja po ISIN, nato preverjeno po deležu manjkajočih
in ponovljenih zaključkov v zadnjih treh letih.

| ISIN | ključ | oznaka | borza | valuta | od | uporabno od |
|---|---|---|---|---|---|---|
| IE00B4L5Y983 | World | IWDA.L | LSE | USD | 2009-09-25 | **2013-01-01** |
| IE00BKM4GZ66 | EM | EIMI.L | LSE | USD | 2014-05-30 | 2014-05-30 |
| IE00BF4RFH31 | SmallCap | WSML.L | LSE | USD | 2018-03-27 | 2018-03-27 |
| IE00BP3QZ601 | Quality | IWQU.L | LSE | USD | 2014-10-06 | 2014-10-06 |
| IE00BDBRDM35 | GlobAgg | EUNA.DE | Xetra | EUR | 2017-11-21 | **2019-01-01** |
| IE00B0M62X26 | InflLink | IBCI.AS | Euronext Amsterdam | EUR | 2008-01-02 | 2008-01-02 |
| IE00B4ND3602 | Gold | IGLN.L | LSE | USD | 2011-04-08 | 2011-04-08 |
| IE00BD6FTQ80 | Commod | CMOD.L | LSE | USD | 2017-01-09 | 2017-01-09 |

Vrstice LSE zmagajo, kjer obstajajo: 0,0 % manjkajočih in 0,1–0,5 % ponovljenih
zaključkov, proti 0,4 % in 0,4–1,2 % za Xetro in Amsterdam. Za obe obveznici
uporabne vrstice na LSE ni — `0GGH.L` pogreša 4,7 % zaključkov. LSE, Xetra,
Euronext in Borsa Italiana zapirajo v razmiku desetih minut okoli 17.30 po
srednjeevropskem času, zato mešanje teh borz ne prinese resne časovne
neusklajenosti. Mešanje z ameriško kotacijo bi jo.

### 1c. Tri pasti, ki jih nalagalnik zapira

**Vzporedne vrstice istega ISIN niso neodvisne.** Najbolj poveden dokaz so
izhodiščne vrednosti:

| par | prvi dan | vrednost EUR-vrstice | vrednost USD-vrstice | razhajanje do danes |
|---|---|---|---|---|
| EGLN.L / IGLN.L | 2011-04-08 | 29,39 | 29,39 | **110 o. t.** |
| CMOD.MI / CMOD.L | 2017-01-09 | 17,46 | 17,46 | 9 o. t. |
| IS3Q.DE / IWQU.L | 2014-10-06 | 25,06 | 25,13 | **80 o. t.** |

Dve različni valuti se ne moreta začeti pri isti številki. Yahoo drugo vrstico
napolni z zgodovino prve in ji pripiše drugo valutno oznako. Zato: **nikoli ne
jemlji EUR-vrstice namesto pretvorbe.**

**Tečaj mora biti usklajen z zaključkom.** Yahoojev `EURUSD=X` je 24-urna sveča,
katere zaključek je ure stran od zaključka evropske borze. ECB objavlja
referenčni tečaj, določen ob 16.00 po srednjeevropskem času, na vsak delovni dan
TARGET, brezplačno in brez ključa
(`data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A`). Devetdeset minut
pred zaključkom je bolje kot šest ur po njem. ECB je privzeti vir, Yahoo je
rezerva. Preverjeno: 5579 opazovanj od 2005-01-03.

**Prazniki in zamrznjene cene sta dve različni napaki.** Vrzel (borza je bila
zaprta) ne sme postati ničelni donos, sicer je volatilnost podcenjena.
Zamrznjena cena (borza odprta, ta vrstica ni trgovala) je hujša: to je cena, po
kateri strategija lahko ukrepa, po njej pa nihče ne bi mogel izpolniti naročila.
Nalagalnik ju loči in označi, ne zgladi:

```
traded  resničen odtis na dan, ko je bila borza odprta
stale   borza odprta, cena se ni premaknila in ni bilo prometa
filled  odtisa ni bilo; prenesen naprej največ 3 dni
```

Delež `filled` je približno 1,5 % na leto in je skoraj v celoti posledica
britanskih bančnih praznikov, ki so delovni dnevi TARGET.

**Prilagojena zaključna cena.** Vseh osem je akumulativnih. Največje odstopanje
`adjclose` od `close` čez celotno zgodovino vseh osmih je **0,000 %**. `close`
je torej že donos s ponovnim vlaganjem. To je dejstvo o današnjih razredih enot
in ne zakon, zato nalagalnik ob vsakem prenosu preveri in **vrže napako**, če se
pojavi izplačilo. Sklad, ki bi začel izplačevati, bi sicer neopazno in
sestavljeno požrl dividendni donos iz vsakega izračuna.

### 1d. Zakaj je uporabna zgodovina krajša

Delež dni, na katere se zaključek ponovi ob ničelnem prometu:

| leto | IWDA.L | EUNA.DE |
|---|---|---|
| 2009 | 78,3 % | — |
| 2010 | 81,0 % | — |
| 2011 | 40,1 % | — |
| 2012 | 38,7 % | — |
| 2013 | 0,4 % | — |
| 2018 | 0,0 % | 20,8 % |
| 2019 in naprej | 0,0 % | 0,0 % |

Trendno pravilo, ki mu podtakneš zamrznjene cene, poroča o poslih po cenah, ki
jih ni bilo. Učinek je največji natanko tam, kjer je zgodovina videti
najdragocenejša — v dodatnih letih na začetku. Zato ima vsak instrument zapisan
`usable_from` in `load_panel(min_quality=True)` začne tam.

---

## Del 2: vključitev v obstoječo arhitekturo

### 2a. Kaj je bilo že tržno nevtralno in kaj ne

Ločnica je čista. `shared/indicators.py`, `shared/costs.py` in
`shared/warmup.py` ne vedo nič o kriptu in so uporabljeni nespremenjeni.
`shared/data_source.py` je specifičen za kripto in ga ETF ne uporablja — dobil je
dvojčka, ne razširitve, ker se problemi ne prekrivajo: kripto potrebuje tri
borze in zaporedno rezervo, ETF potrebuje valuto, koledar in preverjanje odtisa.

`ETFConfig` ima **ista imena polj** kot `MomentumConfig` za iste pojme. Zaradi
tega `shared/warmup.required_history` in `testing/scripts/engine.py` delujeta
brez posebnega primera. Registracija je bila dve vrstici:

```python
_VARIANT_DIRS = { "lean": …, "momentum": …, "full": …, "etf": _ROOT / "etf" }
```

Preverjeno, da deluje:

```python
df = engine.run("etf", load("World"))
r  = engine.strat_returns(df, fee_per_side_pct=0.10, s_bull_code=engine.s_bull("etf"))
```

`run_strategy` sprejme `btc_daily` pod tem imenom samo zato, da ga `engine.run`
lahko pokliče brez izjeme; pošteni vzdevek je `anchor_daily` in ima prednost.

### 2b. Parametri, ki jih je bilo nujno spremeniti

| kaj | kripto | ETF | zakaj |
|---|---|---|---|
| `trading_days` | 365 | **252** | najbolj vplivna vrstica v datoteki. Vsaka letna številka se množi s korenom tega. 365 napihne volatilnost, Sharpe in Sortino za faktor **1,204** in na grafu se to ne vidi |
| dolžine oken | 35 / 75 palic | 100 / 50 / 200 | 75 palic 24/7 je 75 koledarskih dni; 75 palic na ETF je 109. Pretvorba po koledarskem času da 52, nato zaokroženo na 50 in 200, ki sta konvenciji delniške literature — en prosti parameter manj |
| vstopni pas | 2,0 % trackline | **0,5 × ATR** | 2 % je na Global Aggregate, ki niha 4,4 % letno, premik, ki se zgodi dvakrat na leto. Pas ne bi filtriral šuma, prepovedal bi trgovanje. ATR je ista statistična razdalja na vsakem instrumentu |
| sledilni izstop | 12 % od vrha | **3 × ATR** | 12 % je v BTC običajen teden in na obveznicah zlom. Chandelier se prilagodi instrumentu in režimu |
| filter kakovosti trenda | Efficiency Ratio > 0,25 | ADX > 18 | ER je bil umerjen na kriptov šum. ADX je delniška konvencija |
| `target_vol_pct` | 60 | **12** | pri 60 je `min(1; 60/15)` vsak miren dan enak 1 — ciljanje se samo izklopi. Ista okvara kot v Leanu, kjer je bila vgrajena pot mrtva in je učinek pokazal šele prekrivni sloj |
| `max_leverage` | — | **1,0** | edini dokazani učinek ciljanja je manjši padec. Vzvod bi to dokazano korist zamenjal za nedokazano |
| `vol_floor_pct` | — | **3,0** | brez dna da 12 % / 1 % obvezniške volatilnosti dvanajstkratnik |
| provizija na stran | 0,30 % | 0,10 % | razmik na IWDA.L je pol odstotne desetinke, provizija nekaj evrov pavšalno. 0,10 % je namenoma konservativno za likvidne rokave; tanki imajo svoje številke v `fee_overrides` |

### 2c. Kar v modelu stroškov manjka in je verjetno največja postavka

Davek. Strategija z obratom 325 % na leto in strategija, ki se drži petnajst let,
sta v Sloveniji dva različna davčna izdelka, ker se stopnja na kapitalski dobiček
znižuje z dobo imetja. Razlika je skoraj zagotovo večja od vseh razmikov in
provizij v tem poročilu skupaj. Nisem je modeliral in je ne znam pravilno
ovrednotiti — stopnje in trenutno stanje predpisov je treba potrditi pri davčnem
svetovalcu. **Preden se karkoli od tega izvede v živo, je to prva postavka, ki
jo je treba izračunati**, in verjetno sama po sebi odloči.

---

## Del 3: tri strategije

Vse tri vračajo isto obliko okvira (`signal_state`, `target_alloc`,
`signal_changed`), zato jih `engine.position`, `shared.costs` in celoten
ocenjevalni panel poganjajo brez prilagoditve.

### 3a. Sledenje trendu — `etf/diversitas/strategy.py`

Zgradba je namenoma nespremenjena glede na `momentum`: stanje stroja je edini
del projekta, ki je vrstico za vrstico revidiran proti Pinu in preverjen na
pogled v prihodnost. Zamenjani so pas, izstop, filter kakovosti in dimenzioniranje.

```
above_tl        = close > trackline + 0,5 × ATR
bull_condition  = above_tl AND close > SMA50 AND (RSI > 50 AND close > EMA100)
                  AND trackline narašča AND ADX > 18
trail_stop      = najvišji zaključek od vstopa − 3 × ATR
alloc           = 100 × min(1; 12 / max(σ60; 3))    × (0,5 če medvedji režim)
```

### 3b. Vračanje k povprečju — `etf/diversitas/mean_reversion.py`

Naloga zahteva RSI z dinamičnimi Bollingerjevimi pasovi in vstopom ob
preprodanosti **v smeri makro trenda**. Zadnji del je celotna strategija; brez
njega je to stroj za kupovanje medvedjih trgov.

Tri odločitve, ki jih je vredno zagovarjati:

**Kratek RSI, ne RSI(14).** RSI(14) je trendni filter, ki je slučajno omejen. Ko
na dnevnem delniškem ETF pokaže 30, je gibanje običajno mimo. Literatura o
kratkih obratih uporablja 2 do 4 periode in opisuje obrat, dolg 1 do 5 dni.
Tukaj `rsi_len = 3`.

**Prilagodljiv pas, ne 2 sigmi.** Fiksni 2-sigma pas ni fiksna pogostost dogodka.
V mirnem trgu se ga dotika ves čas, v napetem skoraj nikoli — torej se pravilo
sproža prepogosto natanko takrat, ko je kupovanje padcev varno, in skoraj nikoli
takrat, ko največ prinese. Množitelj se skalira s percentilom volatilnosti.

**Izrecen časovni izstop.** Trendno pravilo sme držati zmagovalca večno, obratno
ne, ker ima njegova prednost razpolovno dobo. Brez časovnega izstopa se posel, ki
se ne obrne, tiho spremeni v kupi in drži z etiketo vračanja k povprečju, in
zaledni test pripiše donos trga signalu. `exit_reason` beleži, kateri izstop se
je sprožil — to je najbolj diagnostična številka, ki jo ta strategija proizvede.

### 3c. Rotacija — `etf/diversitas/rotation.py`

Tri plasti, vsaka uporabna sama, vsaka odgovarja na drugo vprašanje. Če jih zliješ
v eno funkcijo in je rezultat dober, nihče ne more povedati, katera je zaslužna.

| plast | kaj naredi |
|---|---|
| `overlay_book` | obdrži strateške uteži, vsak rokav pomnoži z njegovim trendnim signalom, ostalo gotovina. Konservativno: knjiga, ki si jo izbral, je še vedno knjiga, ki jo držiš |
| `rotate_within` | opusti strateške uteži, drži najboljših k rokavov po momentumu. Neposreden prenos `momentum/diversitas/rotation.py` |
| `dual_book` | naloga iz vprašanja: drži Portfelj 1 ali Portfelj 2 ali gotovino, po absolutnem in relativnem momentumu |

Dve stvari, ki ju je bilo treba spremeniti glede na kripto različico. Rangiranje
gre po `dist_atr` in ne po `dist_pct`: v odstotkih bi bil na vrhu vsak dan
najbolj nihajoč rokav, kar je stava na volatilnost z etiketo momentuma. In
absolutni momentum se meri proti **dejanski obrestni meri gotovine**, ne proti
nič — strategija, ki eno leto sedi v gotovini in se ji prizna 0 %, je v letih
2023–2026 podcenjena, ista strategija z današnjo mero čez celo zgodovino pa
precenjena.

**Obrat med rebalansiranji se ne zaračuna.** `_drifted` vodi dejansko držane
uteži, ker pozicija, ki je zrasla, ker je cena zrasla, ni bila kupljena. To je
delniška ustreznica opombe v `shared/costs.py` in na mesečno uravnavani knjigi
zaračunavanje `weights.diff()` precenjuje strošek vsak dan.

---

## Del 4: ocenjevalni načrt in kaj je pokazal

### 4a. Kaj je bilo dodano `metrics.py`

`testing/scripts/metrics.py` ostane edini vir za CAGR, Sharpe, Sortino, MaxDD,
Calmar, profitni faktor in delež dobitkov. Ni podvojen. `etf_eval.py` dodaja
štiri stvari, ki jih ni imel:

**Trajanje okrevanja.** MaxDD pove, kako globoko, ne pove, kako dolgo. Na
dvajsetletnem obzorju sta "okrevalo v sedmih mesecih" in "okrevalo v šestih
letih" ista številka v `core_stats`. `drawdown_episodes` datira vsako epizodo in
označi tisto, ki še ni okrevala.

**Merilo, ki je dejansko ta knjiga.** Primerjava trendnega sloja z gotovino ali
z indeksom S&P ne odgovori na nič. Merilo je istih osem skladov, iste uteži, isti
koledar uravnavanja, isti stroški — da ostane razlika samo signal.

**Zajem navzgor in navzdol.** Najbolj uporabna posamezna diagnostika altcoinske
kampanje: obrambni sloj vedno polepša razmerja že s tem, da ga v trgu ni, zato
razmerja sama ne ločijo veščine od odsotnosti. Računano kot geometrijsko
povprečje na dan navzgor oziroma navzdol; različica z zloženim donosom je videti
naravnejša in je neuporabna, ker je produkt čez sedemnajst let dni navzgor reda
1e30.

**Konstanta trgovalnih dni.** `metrics.TRADING_DAYS` je 365 in `stats._SQRT_TD`
je 365. Oboje je pravilno za sredstvo 24/7 in oboje je tukaj napačno. Vsaka
vstopna točka v `etf_eval.py` poda 252 izrecno; nič ne podeduje privzetka.

### 4b. Protokol proti prilagajanju

Prenesen iz altcoinske kampanje, s poštenim popravkom navzdol.

| del | kaj |
|---|---|
| delitev | zasnova do 30. 6. 2023, validacija do 30. 6. 2025, hold-out od 1. 7. 2025 |
| walk-forward | zasidran, z embargom 21 dni, prilagoditev na treningu, uporaba na naslednjem neviđenem bloku takšna, kot je |
| faze | datirane po Bry-Boschanu v različici Pagan-Sossounov |
| CPCV | vse podmnožice po tri faze |
| interval | vezani bločni bootstrap, isti bloki iz obeh vrst. Interval, ki vsebuje ničlo, ni rezultat |

**Datiranje faz sem moral prekalibrirati in razlog je vreden zapisa.**
Objavljene nastavitve Pagan-Sossounova, prevedene na dnevne palice, so K = 126,
najkrajša faza 84 palic, amplituda 15 %. Na tem vzorcu najdejo eno rastočo in dve
padajoči fazi, ker **v celoti izločijo covidni zlom**: −34,0 % v 33 trgovalnih
dneh je pod najkrajšo dolžino. Zavreči najgloblji in najhitrejši padec vzorca, na
tako kratkem vzorcu, bi ves protokol izpraznilo. Privzetek je zato K = 63,
najkrajša faza 21 palic, amplituda 10 %, kar da **8 rastočih in 9 padajočih faz**
in vsebuje 2018 Q4, covid, 2022 in april 2025. Objavljene nastavitve ostanejo na
voljo kot kontrola.

Ob tem sem v kripto različici algoritma našel **napako**. Pri odstranjevanju
prekratke faze je brisala eno mejno točko in nato slepo naslednjo, kar zlije
pravo dno stran. Na tem vzorcu je proizvedla fazo, označeno kot **padec**, ki se
je končala **48 % višje**, kot se je začela. Te oznake so skupine, po katerih
protokol razrezuje podatke. Nova različica briše obe mejni točki, ponovno vsili
izmenjavanje in ima postpogoj, ki se glasno zlomi. Isto napako je vredno
preveriti v `testing/scripts/faze_ciklov.py`.

### 4c. Ablacija: kateri prenesen pogoj koliko stane

Svetovni indeks v EUR, 2013-01-02 do 2026-09-01, provizija 0,10 % na stran.

| različica | CAGR | Sharpe | Sortino | MaxDD | Calmar | izpost. | zajem ↑ | zajem ↓ |
|---|---|---|---|---|---|---|---|---|
| **kupi in drži** | **12,74 %** | **0,84** | **1,18** | −33,97 % | **0,38** | 100 % | — | — |
| 12-mesečni momentum > 0 | 5,64 % | 0,49 | 0,67 | −28,28 % | 0,20 | 81 % | 74 % | 78 % |
| `close > SMA200` | 5,23 % | 0,51 | 0,71 | −29,71 % | 0,18 | 76 % | 64 % | 68 % |
| samo trackline + MA200 | 4,24 % | 0,54 | 0,75 | **−16,99 %** | 0,25 | 51 % | 42 % | 43 % |
| brez sledilnega izstopa | 3,64 % | 0,47 | 0,66 | −17,30 % | 0,21 | 49 % | 40 % | 41 % |
| brez filtra ADX | 1,08 % | 0,19 | 0,26 | −19,60 % | 0,06 | 40 % | 29 % | 33 % |
| brez vstopnega pasu ATR | 0,23 % | 0,07 | 0,09 | −23,21 % | 0,01 | 34 % | 25 % | 28 % |
| **prenesen sklop, vsi pogoji** | **0,11 %** | 0,05 | 0,07 | −23,21 % | 0,00 | 34 % | 25 % | 29 % |
| brez naraščajoče trackline | −0,42 % | −0,03 | −0,04 | −24,72 % | −0,02 | 34 % | 24 % | 28 % |

Bere se takole. Vsak dodan pogoj iz kripto sklopa **zniža** donos, ne da bi
sorazmerno znižal padec. Razmerje zajema je pri vsaki različici **pod 1,0** —
torej časovna izbira ni le manj tvegana, je aktivno škodljiva. Najboljša
različica te družine, "samo trackline + MA200", ima Calmar 0,25 proti 0,38 za
kupi in drži.

### 4d. Knjigi

Portfelj 1, 2018-03-27 do 2026-09-01:

| kandidat | CAGR | Sharpe | Sortino | MaxDD | obrat/leto | strošek/leto |
|---|---|---|---|---|---|---|
| **kupi in drži, četrtletno** | **11,91 %** | **0,77** | **1,06** | −32,82 % | 37 % | 0,04 % |
| kupi in drži, letno | 12,53 % | 0,76 | 1,05 | −35,64 % | 28 % | 0,03 % |
| trendni sloj, dnevno | 0,83 % | 0,17 | 0,23 | **−16,36 %** | 512 % | 0,52 % |
| trendni sloj, mesečno | 0,23 % | 0,07 | 0,09 | −21,77 % | 325 % | 0,35 % |
| rotacija top-k, mesečno | 0,13 % | 0,06 | 0,08 | −26,35 % | 575 % | 0,63 % |

Portfelj 2, 2019-01-02 do 2026-09-01:

| kandidat | CAGR | Sharpe | Sortino | MaxDD | Calmar |
|---|---|---|---|---|---|
| **kupi in drži, letno** | **6,95 %** | **0,99** | **1,38** | **−15,05 %** | **0,46** |
| kupi in drži, četrtletno | 6,75 % | 0,98 | 1,36 | −15,05 % | 0,45 |
| rotacija top-k, mesečno | 3,17 % | 0,44 | 0,60 | −21,40 % | 0,15 |
| trendni sloj, mesečno | 1,27 % | 0,52 | 0,73 | −5,24 % | 0,24 |
| trendni sloj, dnevno | 0,06 % | 0,04 | 0,05 | −8,33 % | 0,01 |

Po oknih, Sortino in MaxDD:

| kandidat | zasnova | validacija | hold-out |
|---|---|---|---|
| P1 kupi in drži | +0,82 / −35,6 | +1,21 / −19,3 | +2,86 / −6,8 |
| P1 trendni sloj | −0,28 / −21,8 | +0,87 / −7,0 | +1,77 / −1,9 |
| P2 kupi in drži | +0,95 / −15,0 | +1,76 / −7,6 | +2,73 / −4,2 |
| P2 trendni sloj | +0,64 / −5,2 | +1,29 / −2,2 | −0,01 / −1,8 |

### 4e. Sodba protokola

| knjiga in kandidat | rast | padec | podmnožice | d Sortino [95 % IZ] | d MaxDD [95 % IZ] |
|---|---|---|---|---|---|
| P1 trendni sloj | **0/5** | 4/4 | 40 % | **−0,97 [−1,52, −0,35]** slabši | +13,9 [−3,6, +20,2] |
| P1 rotacija | **0/5** | 4/4 | 39 % | **−0,97 [−1,52, −0,33]** slabši | +9,3 [−14,0, +13,4] |
| P2 trendni sloj | **0/4** | 3/3 | 37 % | −0,65 [−1,59, +0,15] | **+9,8 [+2,6, +16,8]** boljši |
| P2 rotacija | **0/4** | 3/3 | 38 % | −0,77 [−1,85, +0,12] | −6,3 [−14,1, +5,8] |

**Sprejetih 0 od 4.** In dva rezultata sta značilna v napačno smer, kar je močnejša
ugotovitev od preproste zavrnitve.

### 4f. Ali je to lastnost tega okna

To je bilo najpomembnejše preostalo vprašanje. Osemletni vzorec je pretežno en
močan bikovski trg s hitrimi padci v obliki črke V, kar je za sledenje trendu
najbolj sovražno možno okolje. Zgodovino sem zato podaljšal prek ACWI in nato
SPY na **1999–2026**, kar zajame razpad dot-coma in leto 2008.

| različica | CAGR | Sharpe | Sortino | MaxDD | Calmar | izpost. |
|---|---|---|---|---|---|---|
| kupi in drži | **6,66 %** | 0,43 | 0,60 | **−66,98 %** | 0,10 | 100 % |
| `close > SMA200` | 3,79 % | 0,37 | 0,52 | −36,16 % | 0,10 | 69 % |
| 12-mesečni momentum | 2,40 % | 0,25 | 0,34 | −43,90 % | 0,05 | 72 % |
| trackline + MA200 | 1,99 % | 0,28 | 0,39 | **−25,30 %** | 0,08 | 44 % |
| prenesen sklop | **−1,57 %** | −0,24 | −0,31 | −45,02 % | −0,03 | 25 % |

Po desetletjih, CAGR in MaxDD:

| obdobje | kupi in drži | SMA200 | trackline + MA200 |
|---|---|---|---|
| 2000–2009 | −5,1 % / −67,0 % | −0,9 % / −36,2 % | −1,5 % / −25,3 % |
| 2010–2019 | 12,2 % / −22,6 % | 6,8 % / −20,7 % | 5,0 % / −11,3 % |
| 2020–2026 | 12,7 % / −34,0 % | 4,4 % / −29,7 % | 3,2 % / −17,0 % |

Protokol na 39 datiranih fazah:

| različica | rast | padec | d Sortino | d MaxDD |
|---|---|---|---|---|
| trackline + MA200 | **0/19** | **18/18** | −0,22 [−0,72, +0,24] | **+41,7 [+0,6, +46,3]** boljši |
| `close > SMA200` | **0/19** | 15/18 | −0,08 [−0,53, +0,34] | +30,8 [−8,5, +38,3] |

**Popolnoma monotono.** Trendno pravilo zmaga v vsaki padajoči fazi in v nobeni
rastoči, čez sedemindvajset let. Calmar je pri kupi in drži in pri SMA200 enak,
0,10. Ugotovitev iz kratkega vzorca ni artefakt okna: sledenje trendu na
razpršenem delniškem indeksu je **menjava tveganja za donos po približno pošteni
ceni**, ne izboljšava. Prenesen kripto sklop pa v sedemindvajsetih letih izgubi
denar in to je ločeno in trdno.

---

## Del 5: kaj potem deluje

`etf_kaj_deluje.py` preveri edino družino, ki je v altcoinski kampanji dala
statistično značilen pozitiven rezultat.

**Portfelj 1, ciljanje volatilnosti na ravni knjige:**

| različica | CAGR | Sharpe | Sortino | MaxDD | rast | padec | d MaxDD [95 % IZ] |
|---|---|---|---|---|---|---|---|
| kupi in drži | 11,91 % | 0,77 | 1,06 | −32,82 % | — | — | referenca |
| ciljanje 12 % | 7,38 % | 0,63 | 0,84 | −28,63 % | 2/4 | 4/4 | +4,2 [−3,5, +7,2] |
| ciljanje 10 % | 6,37 % | 0,62 | 0,83 | −24,40 % | 1/4 | 4/4 | **+8,4 [+0,5, +11,4]** |
| ciljanje 8 % | 5,16 % | 0,62 | 0,83 | −19,96 % | 1/4 | 4/4 | **+12,9 [+4,4, +16,9]** |
| ciljanje 6 % | 3,92 % | 0,62 | 0,83 | −15,31 % | 1/4 | 4/4 | **+17,5 [+7,1, +23,7]** |

Sortino ni dokazan pri nobeni, vsi intervali vsebujejo ničlo. Najhujši padec je
dokazan pri treh. **Točno isti vzorec kot na BTC in na kripto knjigi.**

Poštena menjava z znanim tečajem:

| ciljanje 8 % na Portfelju 1 | dobiš | plačaš |
|---|---|---|
| najhujši padec | −32,8 % postane **−20,0 %** | |
| letni donos | | 11,9 % postane **5,2 %** |

**Portfelj 2: ne deluje nič, in to je koristno vedeti.**

| različica | d Sortino [95 % IZ] | d MaxDD [95 % IZ] |
|---|---|---|
| ciljanje 6 % | −0,18 [−0,46, +0,11] | +0,0 [−2,3, +3,2] |
| ciljanje 10 % | **−0,19 [−0,41, −0,03]** slabši | +0,0 [−2,4, +0,3] |
| ciljanje 12 %, do 1,5x | **−0,21 [−0,45, −0,03]** slabši | **−6,8 [−12,1, −2,7]** slabši |
| uteži po obratni volatilnosti | **−0,40 [−0,75, −0,11]** slabši | +2,2 [−1,9, +3,5] |

d MaxDD je natanko **+0,0** pri vsaki nastavitvi brez vzvoda. Razlog je viden
takoj: lastna volatilnost knjige je 7,0 %, cilj 8 do 12 % torej skoraj nikoli ne
ugrizne, in kadar ugrizne, ugrizne ob napačnem času. Z vzvodom je padec značilno
globlji. **Portfelj 2 je že opravil delo, ki naj bi ga ciljanje volatilnosti
opravilo zanj.**

### Razpršitev, izmerjena

| | Portfelj 1 | Portfelj 2 |
|---|---|---|
| volatilnost knjige | 16,80 % | **7,02 %** |
| množitelj razpršitve IDM | **1,04** | **1,53** |

IDM 1,04 pomeni, da se štirje rokavi Portfelja 1 obnašajo kot **eno sredstvo**.
Korelacija World-Quality je 0,98, World-SmallCap 0,92, World-EM 0,78. To je ista
ugotovitev kot pri kripto knjigi, kjer je IDM 1,09, in ima isto posledico:
dodajanje rokavov znotraj razreda ne razprši ničesar.

Kapital proti tveganju:

| Portfelj 2 | delež kapitala | delež tveganja |
|---|---|---|
| World | 23 % | **47 %** |
| EM | 7 % | 15 % |
| GlobAgg | 35 % | 9 % |
| InflLink | 20 % | 11 % |
| Gold | 10 % | 13 % |
| Commod | 5 % | 6 % |

30 % kapitala v delnicah nosi **62 % tveganja**. To je opažanje, ne priporočilo —
altcoinski krog je pokazal, da popravljanje te neenakosti z utežmi po tveganju v
rezultatu ni ločljivo od šuma, in zgornja vrstica o obratni volatilnosti pove
isto tudi tukaj, tokrat z značilno **slabšim** Sortinom. Če te razporeditev moti
kot vprašanje zasnove, je poštena pot enkratna odločitev o utežeh, ne mehanizem.

---

## Del 6: kaj bi naredil naprej

Po vrsti, po razmerju med dokazom in trudom.

**1. Izračunaj davčno posledico obrata.** Edina postavka, ki je verjetno večja od
vsega izmerjenega v tem poročilu, in edina, ki jo je mogoče izračunati brez novih
podatkov. Če trendni sloj že pred davkom izgubi 11 odstotnih točk CAGR, ga davek
dokončno zapre — kar je koristno, ker vprašanje odpade.

**2. Preveri izbrano borzno vrstico proti uradni vrednosti enote izdajatelja.**
Enkraten posel, en teden podatkov na instrument. To je edina neodvisna kontrola,
ki jo imamo, in glede na ugotovitev o vzporednih vrsticah je nujna, preden se
karkoli izvede v živo.

**3. Izmeri resnične razmike pri svojem posredniku.** Celoten model stroškov je
predpostavka. Pri tanjših rokavih, SmallCap in Commod, je razlika med 0,10 % in
0,25 % na stran večja od vsega, kar dela signal.

**4. Ne prilagajaj parametrov trendne strategije.** Ablacija kaže, da problem ni
napačna nastavitev, ampak napačna družina za to sredstvo, in isto pove
sedemindvajsetletni vzorec. Gnezdeni walk-forward na kriptu je dal razliko točno
0,00; ni razloga pričakovati kaj drugega tukaj, na štirikrat krajšem vzorcu.

**5. Če hočeš plitvejši padec na Portfelju 1, uporabi ciljanje volatilnosti in
ga poimenuj po tem, kar je.** Gumb na osi tveganja z izmerjenim tečajem, ne
izboljšava. Tabela v delu 5 je celotna ponudba.

**6. Vprašanja, na katera ta vzorec ne more odgovoriti.** Ali kombinacija dveh
knjig prek `dual_book` prinese kaj, se na 7,8 leta in enem prehodu med režimoma
ne da izmeriti. Kodo za to sem napisal in je namenoma nisem poganjal kot
rezultat: z eno menjavo režima v vzorcu bi bila katera koli številka iz nje
opisna, ne dokazna.

---

## Del 7: na čem je vse merjeno

Cene: Yahoo, ena borzna vrstica na ISIN po tabeli v delu 1b, prenesene 1. 9. 2026.
Valuta: EUR, pretvorjeno po dnevnem referenčnem tečaju ECB, določenem ob 16.00 po
srednjeevropskem času. Koledar: delovni dnevi TARGET, z ločenimi oznakami za
prenesene in zamrznjene odtise.

Provizija in zdrs skupaj **0,10 % na stran** za likvidne rokave, 0,15 % za
SmallCap, 0,20 % za Commod, 0,12 % za InflLink. Vse te številke so predpostavke.

Letno preračunavanje s **252** dnevi povsod. Vezani bločni bootstrap, 2000
vzorcev, povprečen blok 20 dni, isti bloki za obe primerjani vrsti.

Podaljšana zgodovina v delu 4f je sestavljena iz ACWI pred 2013-01-02 in SPY pred
2008-03-28, spojena na ravni ob predaji, tako da nadomestek prispeva samo svoje
donose. SPY je zgolj ameriški in je zato slab nadomestek MSCI World po ravni;
uporabljen je za vprašanje o robustnosti čez režime, ne kot podatek o uspešnosti.
