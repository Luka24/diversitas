# Predregistracija — Donchian na ETH

**Status:** zapisano PRED zagonom · nobena metrika na ETH še ni bila izračunana
**Podatki:** ETH, Binance, uporabno okno **2020-01-01 → 2026-07-27, 2400 barov**
**Stroški:** 0,30 % **na stran** (nakup 0,30 %, prodaja 0,30 %, zaokrožen posel 0,60 %)

---

## 1. Zakaj zdaj in kaj to stane

ETH je v tem projektu **enkratna karta**. Načrt ga je rezerviral za zunajvzorčno
potrditev z največ dvema vnaprej zapisanima hipotezama.

Donchian je edini kandidat doslej, ki je prestal ugnezdeni walk-forward na BTC.
Pade pa na doslednosti po obdobjih (2 od 4), zato je odločitev brez ETH **presoja
in ne dokaz**. Prav za to je bila rezerva.

**Cena:** po tem testu ETH ni več čist za to vprašanje. Poznejša celovita analiza
ETH je še vedno mogoča, a ne več kot neodvisna potrditev Donchiana.

## 2. Ena hipoteza, en strel

> **Donchianova potrditev vstopa, perioda 20, brezpogojno, izboljša strategijo
> tudi na ETH.**

| | |
|---|---|
| perioda | **20**, fiksna |
| `donchian_top_frac` | 0,75 — obstoječa privzeta vrednost, se ne dotika |
| kontrola | ista strategija z Donchianom izklopljenim |

### Zakaj perioda 20 in nobena druga

Izbrana je **iz dokazov na BTC, pred pogledom na ETH**:

* leži v sredini platoja 12–22
* **ni ob robu mreže** — najboljša na BTC je bila 12, ta pa meji na 10, ki je rob
* okrogla vrednost, ki jo je prvotna analiza (`korak1_lean_parametri.md`) že
  izpostavila

### Česa NE bom naredil

* **nobenega sweepa period na ETH.** Vsa vrednost zunajvzorčnega testa je v tem,
  da je bila izbira narejena drugje. Če bi na ETH iskal najboljšo periodo, bi test
  spremenil v drugi sweep in ne bi dokazal ničesar.
* **ne bom testiral pogojne različice** (Donchian samo v trendu). Ta je nastala kot
  odgovor na vzorec neuspeha **na BTC**, torej je že prilagojena BTC-ju.
  Preverjanje BTC-prilagojene izboljšave na ETH je šibkejši dokaz kot preverjanje
  gole oblike.
* **ne bom popravljal pragov iz §5**, ko bom videl rezultate.
* **če pade, ne bom iskal druge periode.** Vprašanje je s tem zaprto.

## 3. Kaj se meri

Neto 0,30 % na stran, na celotnem oknu in po štirih podobdobjih:

Sortino · Sharpe · CAGR · MaxDD · končni mnogokratnik · izpostavljenost ·
obrat · število poslov · zajem navzgor in navzdol.

Poleg tega:

* **izenačena izpostavljenost** — Donchian zmanjša čas v trgu, zato se **izklopljeno
  stanje pomanjša navzdol** do njegove ravni. Obratno skaliranje je pri binarni
  poziciji brez učinka; to napako sem naredil pri BTC in jo popravil.
* **razčlenitev izboljšanja padca** na del, ki izvira iz manj časa v trgu, in del,
  ki izvira iz izbire dni
* **dnevi, ko Donchian spremeni pozicijo**, in donos ETH v naslednjih 20 dneh na
  teh dnevih
* **revizija pogleda v prihodnost**

## 4. Opozorilo o oknu

ETH datoteka nima ogrevalnega dela, zato obrezovanje poje prvih 199 barov
dejanske zgodovine. Uporabno okno je **2020-01-01 → 2026-07-27**, ne od 2019.

Posledica: **prvo podobdobje je krajše** — 397 dni namesto ~700. Ostala tri so
primerljiva (668, 670, 665 dni). Ker je bilo na BTC prvo obdobje tisto, kjer je
Donchian najbolj pomagal, je ETH v tem pogledu **strožji preizkus**, ne blažji.

## 5. Odločitveno pravilo — vnaprej

### Prestane, če velja VSE troje:

| | pogoj |
|---|---|
| 1 | Sortino boljši od izklopljenega na celotnem oknu |
| 2 | boljši v **≥ 2 od 4** podobdobij |
| 3 | padec se **ne poslabša** pri izenačeni izpostavljenosti |

Prag 2 od 4 je nižji kot na BTC (3 od 4) namenoma: to je potrditveni test na
drugem sredstvu s krajšim oknom, ne primarni izbirni test. Zahtevati enako
strogost dvakrat pomeni zahtevati, da se naključje ne zgodi nikoli.

### Pade, če:

* Sortino je slabši od izklopljenega, **ali**
* ponovi se vzorec z BTC — pomaga samo v trendnih obdobjih in škoduje v stranskih

### Kaj sledi

* **Prestane** → Donchian gre v strategijo pri periodi 20; `donchian_period = 55`
  se popravi na 20 in zastavica se vklopi.
* **Pade** → Donchian ostane izklopljen, vprašanje zaprto. `donchian_period = 55`
  se vseeno popravi ali odstrani, ker leži v najslabšem delu mreže in bi vsakogar,
  ki zastavico vklopi, pripeljal do slabšega rezultata od platoja.

## 6. Kaj pričakujem — zapisano vnaprej

1. Sortino na ETH bo **boljši od izklopljenega**. **Verjetno** — na BTC je bilo
   boljših vseh osem period, ne ena.
2. Izpostavljenost bo padla za 5–10 o. t. **Verjetno.**
3. Vzorec »pomaga v trendu, škoduje v stranskem trgu« se bo **ponovil**, torej bo
   obdobje II (medvedji trg 2022) slabše. **Verjetno.**
4. Pogoj 2 (≥ 2 od 4) bo **odločal** — in izid je zares negotov.

Napoved o skupnem izidu **namenoma ne dam.** Pri prejšnjih korakih sem jo dal in
se je izkazala za pravilno, kar je zaneslo v to, da sem izid poznal vnaprej. Tu
ga ne poznam.
