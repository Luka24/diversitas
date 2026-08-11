# Korak 4 — premor pred ponovnim vstopom

**Status:** načrt, pred izvedbo
**Podatki:** BTC, Binance, 2019-03-09 → 2026-07-29, 2700 barov
**Stroški:** 0,30 % na stran, povsod, brez izjem
**Novi parametri:** 0
**Ocena časa:** 4–5 ur

---

## 0. Kaj premor sploh je in koliko ugrizne

Po vsaki spremembi signala mora preteči `reentry_hold = 15` barov, preden je
mogoč nov vstop v BULL. Namen je preprečiti brcanje sem in tja okoli trackline.

Prvo, kar sem izmeril — pred vsem ostalim, ker od tega je odvisno, ali ima ta
korak sploh smisel:

```
dni, ko je premor blokiral sicer veljaven vstop      118
ločenih epizod blokade                                10
epizod, ki so trajale polnih 14 dni                    8
vstopov (od 21), ki jih je premor zamaknil            10
```

| epizoda | trajanje | cena med čakanjem | 20 dni po sprostitvi |
|---|---|---|---|
| 2019-05-11 → 05-24 | 14 | +12,6 % | +3,2 % |
| 2019-06-25 → 07-08 | 14 | +3,5 % | −22,0 % |
| 2019-08-07 → 08-09 | 3 | −0,8 % | −20,0 % |
| 2020-11-19 → 12-02 | 14 | +7,9 % | +24,0 % |
| 2020-12-31 → 01-13 | 14 | **+29,2 %** | −5,1 % |
| 2021-02-22 → 03-07 | 14 | −5,8 % | +9,5 % |
| 2023-12-06 → 12-19 | 14 | −3,4 % | +11,1 % |
| 2024-03-05 → 03-18 | 14 | +6,1 % | +2,6 % |
| 2024-11-22 → 12-05 | 14 | −2,0 % | +2,6 % |
| 2025-10-07 → 10-09 | 3 | +0,3 % | −9,6 % |

Povprečje zamujenega giba **+4,8 %**, mediana +1,9 %, standardni odklon ~10 o. t.
Brez januarja 2021 povprečje pade na **+2,0 %**.

### Kaj to pomeni za zasnovo koraka

**Efektivni vzorec je 10, ne 118.** Dnevi znotraj epizode niso neodvisni — osem
epizod je trajalo polnih 14 dni, torej jih ni sprostil noben nov pogoj, ampak
iztek istega števca. Pri n = 10 in raztrosu ±10 o. t. je standardna napaka
povprečja ~3,2 o. t., torej bo vsak interval zaupanja objel ničlo. Nobena
različica ne bo statistično značilno prekašala nobene druge in to vem **vnaprej**.

**Polovica dokazov je iz let 2019–2021.** Pet od desetih epizod je pred marcem
2021. To je najstarejši in najmanj reprezentativen del okna.

**Ena epizoda nosi povprečje.** Januar 2021 je 29,2 % od skupno 47,6 o. t.
seštevka. Pravilo, sešito tako, da ujame ta en dogodek, je učbeniški primer
prilagajanja preteklosti.

**Premor pojasni le del zamude.** Zamaknil je 10 od 21 vstopov, skupno 118 dni.
Preostalih 11 vstopov je zamujalo zaradi `confirm_bars` in zato, ker so se pogoji
prižgali pozno — tega ta korak ne dotakne. Če je diagnoza »vstopi zamujajo«
pravilna, sta koraka 5 in 6 pomembnejša od tega.

### Posledica za odločitveno pravilo

Vprašanja »katera različica je boljša« ni mogoče rešiti na teh podatkih. Zato
korak **ni izbirni postopek, ampak preverjanje neškodljivosti**: iščem najbolj
preprosto različico, za katero se ne da pokazati, da je slabša. To je edina
oblika sklepa, ki jo 10 opažanj zdrži.

---

## 1. Predregistracija

Ta dokument se **commita, preden se požene karkoli**. Po tem se hipoteze, pragovi
in podobdobja ne smejo spremeniti. Če se izkaže, da je bil kakšen prag napačno
izbran, se to zapiše kot ugotovitev, prag pa ostane.

Razlog: pri n = 10 je razlika med »izbral sem prag vnaprej« in »izbral sem prag,
ko sem videl rezultate« razlika med meritvijo in samoprepričevanjem.

---

## 2. Štiri različice, nič novih parametrov

| | pravilo | nov parameter |
|---|---|---|
| **A** | brezpogojnih 15 dni | — (današnje stanje, kontrola) |
| **B** | 15 dni **samo po izgubljenem poslu**, sicer 0 | ne — uporabi `reentry_hold` in predznak zadnjega posla |
| **C** | 0 dni, kadar je `ma_long_rising`, sicer 15 | ne — `ma_long_rising` že obstaja |
| **D** | brez premora, blokado opravi `regime_ok` | ne — **odstrani** `reentry_hold`, 10 → 9 parametrov |

**Zakaj prav te štiri.** B je predlog s sestanka, C predlog sodelavca, D je
logični zaključek opažanja, da je `regime_ok` že vstopni pogoj — v medvedjem
režimu ponoven vstop ionako ni mogoč, zato bi blokada v šibkem režimu ne dodala
ničesar. Novo je samo skrajšanje v uptrendu.

**Kaj tu NE bom naredil.** Ne bom definiral »močnega trenda« z novim pragom
(npr. naklon 200 MA > x %). Vsaka taka definicija je nov parameter, izbran ob
pogledu na 10 epizod. C zato uporabi `ma_long_rising` tak, kot je že izračunan.

**B doda stanje, ne parametra.** Potrebuje predznak izida zadnjega zaprtega
posla. To je znano ob izstopu, torej brez pogleda v prihodnost — kar bo tudi
preverjeno (§7).

---

## 3. Izvedba brez dotikanja motorja

Različice se **ne** pišejo v `lean/diversitas/strategy.py`. Zamrznjena referenca
iz 2. koraka mora ostati veljavna, dokler se ne odločimo za spremembo.

Namesto tega `testing/scripts/reentry_pause.py` znova napiše zanko stanj s
**premorom kot vstavljivo funkcijo**:

```python
def may_enter(bars_since_sig, ctx) -> bool: ...
```

**Samopreverba, ki mora uspeti, sicer se korak ustavi:** različica A mora
reproducirati zamrznjeno serijo pozicij, bar za barom, vključno s
SHA256 `957d3bc9…`. Če se harness ne ujema s produkcijskim motorjem na kontroli,
so vse tri preostale številke brez pomena.

---

## 4. Kaj se meri

Za vsako različico, neto 0,30 % na stran:

**Glavno — meri diagnozo:**
- povprečna in mediana zamuda vstopa (dni)
- donos, zamujen med zamudo (%)
- zajem navzgor / zajem navzdol (o. t.)

**Nadzor — meri, ali smo kaj pokvarili:**
- izpostavljenost (%)
- Sortino, Sharpe, MaxDD, število poslov, obrat

Vsaka številka se objavi za vse štiri različice hkrati. Nobenega poročanja samo
zmagovalca.

---

## 5. Testi

### 5.1 Epizodni prikaz — primarno, opisno

Vseh 10 epizod posamično, ne le povprečje. Zraven **jackknife**: povprečje ob
izpustu vsake epizode po vrsti. Če izpust ene same obrne predznak, to piše v
zaključku z imenom te epizode. Pri n = 10 je to iskrenejše od intervala zaupanja.

### 5.2 Sparjeni blokovni bootstrap, ΔSortino proti A

10 000 vzorcev, dolžina bloka 20 (enaka horizontu), iste prevzorčene dneve na
obeh serijah, da se gibanje trga odšteje. **Pričakujem, da bodo vsi intervali
objeli ničlo.** To je zabeleženo vnaprej, da rezultat »ni značilno« ne bo
naknadno predstavljen kot presenečenje.

### 5.3 Doslednost po podobdobjih — glavna obramba

Štiri disjunktna okna, določena **zdaj**, ne po pogledu na rezultate:

```
I    2019-03-09 → 2021-01-31
II   2021-02-01 → 2022-11-30
III  2022-12-01 → 2024-09-30
IV   2024-10-01 → 2026-07-29
```

Vsako vsebuje vzpon in padec. Meri se **rang** različic v vsakem oknu. Različica,
ki zmaga v 4/4, je nekaj vredna; različica, ki zmaga skupno zaradi enega okna, ni.

### 5.4 Izenačena izpostavljenost — obvezna vrata

D bo skoraj gotovo povečala izpostavljenost. V sedemletnem vzorcu, ki se konča
višje, kot se je začel, več časa v trgu **samo po sebi** izboljša donos in
poslabša padec. To me je v tem projektu ujelo že dvakrat: enkrat proti kupi-in-drži,
enkrat proti enovrstičnemu MA pravilu — oba »prednosti pri padcu« sta bila
artefakt izpostavljenosti.

Zato: vsaka različica se pomanjša na izpostavljenost različice A in šele nato
primerja MaxDD in zajem navzdol. Če prednost izgine, ni prednost.

### 5.5 Placebo premor — ali je mehanizem ali le manj časa v trgu

1000 naključnih razporeditev: 10 premorov po 14 dni, postavljenih na naključne
izstope, z enako pogostostjo blokiranja kot pravi premor. Če učinek pravega
premora leži znotraj porazdelitve placeba, **čas premora ne nosi informacije** in
gre le za manjšo izpostavljenost. Poceni test, ki loči pravilo od naključja.

### 5.6 Občutljivost `reentry_hold` — ŽE IZMERJENA, NE PONAVLJAM

Sweep obstaja v `testing/data/parametri_BTC.json` in ga **ne bom ponovil**.
Ponovitev bi bila nov poskus na istih podatkih, ki ne bi dodal informacije, bi pa
razširil mrežo za naključje.

| dni | 0 | 3 | 6 | 9 | 12 | **15** | 18 | 21 | 25 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| Sortino | 1,05 | 1,01 | 1,07 | 0,97 | 1,13 | **1,22** | 1,20 | 1,03 | 0,98 | 1,06 |
| izpostavljenost | 46,8 | 46,2 | 45,6 | 44,8 | 44,3 | 43,5 | 42,5 | 41,1 | 40,1 | 38,6 |

Kaj se iz tega prebere:

- **Vrh leži natanko na privzeti vrednosti 15.** Ta je ročno vtipkana v Pine
  skripto (`lean/diversitas_lean.pine:44`, `input.int(15, …)`); momentum
  različica ima na istem mestu 4. Ni izpeljana iz ničesar. Vrh na taki vrednosti
  je znak naključja, ne potrditev.
- **Krivulja Sortina je nazobčana, ne grbasta.** Sosednje nastavitve nihajo za
  ~0,1 v obe smeri brez vzorca. Razpon 0,248 je pri 21 poslih znotraj šuma.
- **Edina gladka in enosmerna količina je izpostavljenost** — pada s 46,8 % na
  38,6 % brez izjeme. Parameter torej zanesljivo počne eno stvar: drži nas zunaj.

**Vnaprejšnja napoved iz te tabele.** Različica D je približno vrstica »0 dni«:
Sortino 1,05 pri 46,8 % proti 1,22 pri 43,5 % za A. Razlika 0,17 Sortina ob
3,3 o. t. več časa v trgu. **Zato je izenačenje izpostavljenosti (§5.4) glavni
test tega koraka, ne stranski.** Če razlika po izenačenju izgine, je odgovor, da
premor ne počne nič razen tega, da nas drži zunaj — in za to ni potreben poseben
parameter.

Občutljivost B pri 10 · 20 · 25 dneh ostaja, ker je to nov, še neizmerjen objekt.
Tudi tam argmaksa ne bom izbral; gleda se le, ali je krivulja ravna.

### 5.7 Ponovna revizija pogleda v prihodnost

Različica B uvede novo stanje (izid zadnjega posla). Zanjo se požene
`lookahead_audit.py` z obema kontrolama. Brez tega B ne sme naprej.

### 5.8 Disciplina reference

Serija pozicij vsake različice se zgošči (SHA256) in zapiše v JSON, da je vsaka
številka pozneje reproducibilna in da se dve različici ne moreta tiho izkazati za
isto stvar.

---

## 6. Odločitveno pravilo — nesimetrično in vnaprej zapisano

Ker so vse različice v dokazni moči izenačene, odloča **preprostost**, ne točkovna
ocena. Bremeni dokazovanja sta zato različni:

### D (odstrani parameter) — dovolj je, da ni slabša

Sprejmi D, če velja **vse troje**:
1. spodnja meja intervala ΔSortino proti A > **−0,15** (neinferiornost)
2. izpostavljenost naraste za manj kot **5 o. t.**
3. zajem navzdol se **pri izenačeni izpostavljenosti** poslabša za manj kot **1,0 o. t.**

Prag −0,15 je ~10 % današnjega Sortina in je stvar presoje. Fiksiran je vnaprej —
v tem je bistvo.

### B ali C (dodata mehanizem) — morata jasno zmagati

Sprejmi B ali C samo, če velja **vse štiri**:
1. točkovna ocena boljša od **A in D**
2. interval zaupanja ΔSortino izključuje ničlo
3. isti predznak v **≥ 3 od 4** podobdobij
4. prednost preživi izenačenje izpostavljenosti (§5.4)

### Če ne prestane nič

Ostane A. V dokument se zapiše, da vprašanje premora **na BTC ni rešljivo**, in
se uvrsti med odprta vprašanja — ne med potrjene odločitve. To je legitimen izid
in najverjetnejši.

### Kaj bi bilo sumljivo

- **D prekaša B in C.** Potem premor sam ni potreben; to je ugotovitev o
  parametru, ne uspeh pogojne oblike. Zapiši tako.
- **B zmaga izrazito.** Preveri, na koliko od 10 epizod se sploh razlikuje od A.
  Če na treh ali manj, je »zmaga« šum, ne glede na to, kako lepo izgleda.
- **Katerakoli različica zmaga zaradi januarja 2021.** Jackknife (§5.1) to pokaže.
  Če drži, sklep pade.

---

## 7. Česa v tem koraku ne bom počel

- ne bom vrtel `reentry_hold` in vzel najboljše vrednosti
- ne bom uvedel novega praga za »močan trend«
- ne bom poročal samo zmagovalca ali samo obdobja, kjer različica deluje
- ne bom testiral na ETH, da bi »potrdil« izid — ETH je rezerviran za korak 11,
  enkrat, z dvema vnaprej zapisanima hipotezama
- ne bom prilagajal pragov iz §6, ko bom videl rezultate
- ne bom spreminjal `lean/` prej, kot pade odločitev

---

## 8. Rezultati koraka

| datoteka | vsebina |
|---|---|
| `testing/nacrt_korak4.md` | **ta dokument — hkrati predregistracija**, commitan pred izvedbo |
| `testing/scripts/reentry_pause.py` | harness s premorom kot vstavljivo funkcijo |
| `testing/data/reentry_pause_BTC.json` | vse meritve + SHA256 vsake serije |
| `testing/korak4_rezultati_BTC.md` | epizode, tabele, jackknife, sklep |

---

## 9. Kaj pričakujem, da bo izid

Zapisano vnaprej, da se pozneje vidi, ali sem znal napovedati:

1. Vsi intervali zaupanja objamejo ničlo. **Zelo verjetno.**
2. D poveča izpostavljenost za 2–5 o. t. in poslabša MaxDD; pri izenačeni
   izpostavljenosti razlika izgine. **Verjetno.**
3. Krivulja `reentry_hold` je razmeroma ravna med 10 in 25. **Verjetno** — 8 od
   10 epizod je trajalo polnih 14 dni, kar pomeni, da bi krajši premor le
   premaknil vstop za nekaj dni, ne pa odprl novih poslov.
4. B se od A razlikuje na manj kot polovici epizod. **Verjetno.**
5. Odločitev pade na §6 »ne prestane nič«, torej ostane A. **Najverjetnejši izid.**

Če se to uresniči, je pravi zaključek koraka 4 ta, da je **težišče problema
zamude drugje** — pri `confirm_bars` in pri tem, kdaj se pogoji sploh prižgejo —
in da sta koraka 5 (prilagodljivi mrtvi pas) in 6 (vstop po večini pogojev)
pomembnejša od tega, kar sem pravkar izmeril.
