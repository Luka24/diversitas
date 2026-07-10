# Metodologija: kako testirati spremembo parametra brez overfittinga

Namen: ko hočemo spremeniti kakšen parameter (npr. re-entry lock, bear-cut, trailing),
potrebujemo postopek ki nam pove ali sprememba dejansko dela — ne samo ali izgleda dobro na
zgodovini. Spodaj je postopek, in za vsak korak zakaj je pomemben.

## Zakaj naivno testiranje zavaja

Trije razlogi zakaj "spremenil sem parameter in Sortino je zrasel" ni dokaz:

1. **Selection bias.** Če pregledamo 20 vrednosti in izberemo najboljšo, bo ta najboljša delno
   po sreči — ravno tista ki se je najbolj prilegla šumu v teh podatkih. Če jo potem merimo na
   istih podatkih, dobimo napihnjeno številko. To je past v katero je enostavno pasti: izbereš
   na celi zgodovini, potem "validiraš" na isti zgodovini.

2. **Nestacionarnost.** Kripto trg se spreminja (2021 bull, 2022 bear, ETF doba 2023-25).
   Parameter ki je bil optimalen na preteklosti sistematično ni optimalen za naslednje obdobje.
   Zato optimizacija na celoti ne pove kaj bo delalo naprej.

3. **En režim ni dovolj.** Če testiraš samo na zadnjem letu (ki je bilo npr. bear), preveriš
   samo eno tržno stanje. Strategija ki dela le v enem režimu je overfit nanj.

## Postopek po korakih

### 1. Razdeli podatke in en del zamrzni

Podatke razdeli na tri dele: **train** (za nastavljanje), **validacijo** (za izbiro med
variantami) in **končni holdout** ki ga zamrzneš in se ga dotakneš ENKRAT na koncu. Ključno:
holdout ne sme vplivati na nobeno odločitev do zadnjega koraka — v trenutku ko ga pogledaš pri
izbiri, ni več čist.

Zakaj: brez ločenega, res nevidenega dela ne moreš zares izmeriti kako se strategija obnese na
podatkih ki jih ni videla.

### 2. Omeji svobodo

Testiraj čim manj parametrov naenkrat (pravilo: vsaj ~10 tradov na parameter) in majhen razpon.
Vsak dodaten "gumb" ki ga vrtiš poveča možnost da nekaj po sreči izgleda dobro. In vsaka
sprememba naj ima **ekonomsko logiko** — ne samo številke ki delujejo (npr. "hitrejši re-entry
ujame nadaljevanje trenda" je logika; "re-entry 7 je dal najvišji Sortino" ni).

### 3. Jedro: nested walk-forward (izbira samo iz preteklosti)

To je edini korak ki res odpravi selection bias. Postopek:

- Razdeli čas na več zaporednih oken (foldov). Vsak fold ima **train** del (vse do neke točke)
  in **test** del (naslednje obdobje, ki ga train ne vidi). Med njima pusti embargo (nekaj
  tednov), da se indikatorji ne "prelijejo" čez mejo.
- V vsakem foldu **izberi parameter SAMO iz train dela** (po neki meri, npr. Sortino na train).
- Izbrani parameter **uporabi as-is na test del** — brez naknadnega prilagajanja.
- Rezultate vseh test delov **zlepi** v eno OOS krivuljo.
- Primerjaj to zlepljeno OOS z isto strategijo pri fiksnem baseline-u.

Zakaj: izbira nikoli ne pogleda testnih podatkov. Če "izberi-iz-preteklosti" postopek na
nevidenih delih premaga baseline, potem sprememba dejansko generalizira. Če se izenači ali
izgubi (kot se je pri nas: 1.16 = 1.16), je bil lep rezultat na celoti selection bias.

Pomembno je pogledati tudi **katere vrednosti izbere po foldih**. Če so stabilne (skoraj vedno
ista), je smer prava. Če skačejo (pri nas bear-cut: 75, 75, 0, 0, 25), to pomeni da ni stabilne
"prave" vrednosti — trg se spreminja in optimum z njim.

### 4. Izberi plato, ne konice

Ko že izbiraš vrednost, ne vzemi tiste ki da najvišjo številko, ampak sredino širokega območja
kjer je rezultat podoben. Če re-entry 1/2/3 vsi delujejo podobno, je to plato (robustno). Če
samo ena vrednost izstopa in sosednje padejo, je to konica (overfit).

### 5. Preveri čez režime

Poglej rezultat ločeno v bull, bear in sideways obdobjih (in v več različnih letih). Sprememba
naj pomaga ali vsaj ne škodi v večini režimov, ne le v enem. To je zaščita proti "dela samo v
bull trgu".

Dodatno: testiraj na **več coinih**, ne le enem. Vsak coin je dodaten vzorec različnih pogojev.

### 6. Statistika na zlepljenem OOS

Ko imaš pošteno OOS krivuljo (iz koraka 3), preveri še:

- **Bootstrap interval zaupanja** na izboljšavo (ΔSortino/ΔCalmar): resampliraj z bloki (npr.
  20 dni, da ohraniš serijsko korelacijo) in poglej ali je razlika zanesljivo nad 0 ali samo šum.
- **CPCV** (combinatorial purged CV): namesto ene poti sestavi mnogo mešanih train/test
  kombinacij → dobiš porazdelitev rezultatov, ne ene številke. Pove ali je prednost stabilna
  čez mnogo scenarijev.
- **Deflated Sharpe** če si testiral veliko variant: kaznuje večkratno testiranje (če preizkusiš
  500 stvari, bo ena dobra po sreči).

Opozorilo: ti checki so smiselni SAMO na pošteni OOS krivulji iz koraka 3. Če jih poganjaš na
celi zgodovini na izbrani varianti, spet merijo selection bias (to je bila naša napaka).

### 7. Odločitveno pravilo

Spremembo sprejmi le če velja VSE:
- nested OOS premaga baseline za smiselno mero (ne le 0.0),
- izbrani parametri so čez folde stabilni,
- pomaga (ali ne škodi) v več režimih,
- bootstrap razlika je večinoma nad 0,
- ima ekonomsko logiko.

Če katerikoli pade, ostani pri obstoječi (baseline) vrednosti. "Optimizirali smo in namerno nič
spremenili" je legitimen in pogosto pravi rezultat.

### 8. Končni holdout + paper trading

Šele na koncu, ko je odločitev sprejeta, poženeš izbrano konfiguracijo enkrat na zamrznjenem
holdoutu. In pred pravim kapitalom paper trading — ker se trg spreminja, je edini res nov test
naprej v času.

## Kaj NE delati (pasti ki smo jih sami naredili)

- Izbrati parameter na celi zgodovini, potem "validirati" na isti zgodovini (per-leto, CPCV,
  bootstrap) — vse to je še vedno selection bias.
- Zaupati enemu holdoutu ki pokriva samo en režim (npr. eno bear leto).
- Loviti najvišjo številko (konico) namesto širokega platoja.
- Testirati veliko parametrov naenkrat brez korekcije za večkratno testiranje.

## Konkreten recept (kar imamo v repozitoriju)

1. `run_sensitivity.py` — kateri parametri sploh premikajo rezultat (in kje se nasitijo).
2. `run_aggressive_nested.py` / `run_wfo.py` — nested walk-forward, izbira samo iz train.
3. `run_aggressive_robustness.py` — per-režim + CPCV + bootstrap na OOS.
4. `dataio.py` — zamrznjen holdout (2025+), ločen od dizajn podatkov.

Kratek povzetek v enem stavku: **spremembo lahko zaupaš le če jo izbereš iz preteklosti in
izmeriš na prihodnosti (nested walk-forward), preveriš čez več režimov, in razlika preživi
statistični interval — sicer je lepa številka le selection bias.**
