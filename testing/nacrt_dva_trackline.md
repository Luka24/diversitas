# Potrebujemo oba trackline pogoja ali enega?

**Status:** predregistracija, pred izvedbo
**Podatki:** BTC 2019-03-09 → 2026-07-29 (2700) · ETH 2020-01-01 → 2026-07-27 (2400)
**Stroški:** 0,30 % na stran
**Novi parametri:** 0 — vse periode in pasovi so obstoječe vrednosti

---

## 0. Zakaj to vprašanje sploh obstaja

Donchianov pogoj se algebraično poenostavi v isto obliko kot naš obstoječi
trackline:

```
A   cena > sredina razpona 75 dni  +  3 % cene           (danes)
D   cena > sredina razpona 20 dni  +  25 % širine razpona 20 dni   (Donchian)
```

Ista formula, drugačna perioda in drugače merjen pas. Če Donchiana dodamo,
strategija računa **dva trackline hkrati**. Vprašanje ni več »ali dodati filter«,
ampak **»katerega od dveh trackline pravil sploh potrebujemo«** — in če zadošča
eno, se kompleksnost zmanjša, ne poveča.

### Izmerjeno prekrivanje — nobeden ne implicira drugega

| | BTC | ETH |
|---|---|---|
| A velja | 50,1 % dni | 48,9 % |
| D velja | 32,8 % dni | 32,8 % |
| oba hkrati | 25,7 % | 24,8 % |
| **samo A** (D blokira) | **24,3 %** | 24,2 % |
| **samo D** (A blokira) | **7,1 %** | 8,1 % |
| ujemanje odločitve | 68,6 % | 67,8 % |
| Jaccard | 0,450 | 0,434 |

D **ne implicira** A — na 191 dneh (BTC) bi D dovolil vstop, A pa ne. Pogoja
torej nosita različno informacijo in vprašanje je odprto v obe smeri.

---

## 1. Pet različic — popolna mreža, brez iskanja

Spremeni se **samo trackline vrata**, vse ostalo ostane nedotaknjeno.

| | pravilo | trackline, ki jih računa |
|---|---|---|
| **1. A** | samo A | 1 — današnje stanje |
| **2. D** | samo D | 1 |
| **3. A ∧ D** | oba potrebna | 2 — to je testiral Donchianov korak |
| **4. A ∨ D** | zadošča eden | 2 |
| **5. brez** | trackline vrat ni | 0 — kontrola |

To je celotna mreža nad dvema binarnima pogojema. **Nič se ne prevrta**: obe
periodi (75, 20) in oba pasova (3 %, 25 % razpona) so obstoječe vrednosti.
Peta celica je kontrola, ki pove, koliko sploh prispeva celotna družina.

---

## 2. Metode

### 2.1 Test zaobjetja (forecast encompassing) — neposreden odgovor

Standardni način, kako se preveri, ali informacija enega signala vsebuje
informacijo drugega. Regresija donosa naprej na oba indikatorja hkrati:

```
r(t → t+20)  =  α  +  β₁·A(t)  +  β₂·D(t)  +  ε
```

| izid | pomen |
|---|---|
| β₁ ≈ 0, β₂ ≠ 0 | **A je odveč** → 75-dnevni trackline lahko pade |
| β₁ ≠ 0, β₂ ≈ 0 | **D ne doda ničesar** → Donchiana ne uvajamo |
| oba ≠ 0 | oba nosita svojo informacijo → obdržimo oba |
| oba ≈ 0 | družina ne napoveduje ničesar |

Donosi naprej se prekrivajo 20 dni, zato **Newey–West (HAC) standardne napake** z
zamikom 20. Brez tega bi bile napake podcenjene za faktor ~4.

### 2.2 Model Confidence Set (Hansen, Lunde & Nason, *Econometrica* 2011)

Postopek, ki iz nabora modelov izlušči **množico, ki z dano gotovostjo vsebuje
najboljšega**. Njegova bistvena lastnost za nas: kadar podatki niso informativni,
množica ostane velika. To je vgrajena poštenost — če podatki ne znajo ločiti med
petimi različicami, nam MCS to pove, namesto da bi razglasil zmagovalca.

Zagon na dnevnih neto donosih vseh petih celic, blokovni bootstrap, α = 0,10.

### 2.3 Ugnezdeni walk-forward

Izbira med petimi celicami **izključno iz učnega dela**, meritev na testnem. Dve
shemi, isti kot pri Donchianu: 3 leta / 1 leto in 2 leti / 1 leto.

### 2.4 PBO prek CSCV

12 blokov, vseh 924 uravnoteženih delitev, pet konfiguracij. Primerljivo s
prejšnjima 0,694 in 0,672.

### 2.5 Naključni zamik

Za celico, ki preživi: zavrti trackline pogoj za naključni odmik in preveri,
kje leži pravi med 1000 zamiki. Ohrani pogostost in gručenje, uniči poravnavo.

---

## 3. ETH — druga in zadnja uporaba

Načrt je ETH rezerviral za **največ dve vnaprej zapisani hipotezi**. Prva je bila
Donchian. **To je druga in s tem zadnja.**

Po tem testu ETH ni več čist za nobeno vprašanje o vstopnih pravilih. Vsaka
nadaljnja »potrditev na ETH« bo tretji zajem iz istega vodnjaka in je ne bom
štel kot dokaz.

Poleg tega: korelacija donosov strategije BTC–ETH je 0,477, položaj se ujema na
76,5 % dni. **ETH je delna, ne polna neodvisnost.**

---

## 4. Odločitveno pravilo — vnaprej

Vrstni red je pomemben. Najprej se vpraša, ali podatki sploh znajo ločiti, in
šele nato, katera je boljša.

**Korak 1 — MCS.** Če množica vsebuje več kot eno celico, podatki ne znajo
ločiti. Takrat **odloča preprostost**, ne točkovna ocena:

```
1 trackline  (A ali D)      <  2 trackline  (A∧D ali A∨D)
```

Med celicama z enim trackline odloča točkovna ocena in doslednost po obdobjih.

**Korak 2 — test zaobjetja.** Če pokaže, da je en pogoj odveč, se ga odstrani ne
glede na to, kaj kaže MCS. Odvečen pogoj je odvečen tudi, če ne škodi.

**Korak 3 — walk-forward.** Celica, ki jo izberemo, mora prekašati današnje
stanje zunaj vzorca v **obeh shemah**. Če ne, ostane današnje stanje.

**Korak 4 — ETH.** Ista celica mora biti boljša od današnjega stanja tudi na ETH.
Prag: boljši Sortino in boljši v ≥ 2 od 4 podobdobij.

### Kaj bi bilo sumljivo

- **A ∨ D zmaga** — to je najbolj ohlapna varianta, ki poveča izpostavljenost;
  če zmaga, najprej preveri, ali ni to samo več časa v trgu
- **razlika stisnjena v eno obdobje** — enako kot pri premoru in mrtvem pasu
- **kontrola »brez trackline vrat« se izkaže za konkurenčno** — potem celotna
  družina ne prispeva in problem je drugje

---

## 5. Opozorilo o številu poskusov

V tem projektu je bilo doslej preizkušenih približno **185 konfiguracij**:

| | poskusov |
|---|---|
| zgodnja parametrska analiza | 137 |
| premor pred ponovnim vstopom | 8 |
| prilagodljivi mrtvi pas | 28 |
| Donchianove periode | 8 |
| razgradnja Kijun/Donchian | 4 |
| **ta načrt** | **5** |

Vsak poskus širi mrežo za naključje. Pet celic je majhen dodatek, a **skupno
število je treba upoštevati pri vsaki trditvi o značilnosti** — deflacionirani
Sharpe uporablja skupno število poskusov, ne število v zadnjem testu.

Po tem testu predlagam **premor pri dodajanju hipotez** in prehod na preverjanja,
ki ne uvajajo novih pravil: 4-urni bari, obdobje po ETF, sodelovanje v padcih.

---

## 6. Rezultati koraka

| datoteka | vsebina |
|---|---|
| `testing/nacrt_dva_trackline.md` | ta dokument, hkrati predregistracija |
| `testing/scripts/two_tracklines.py` | pet celic, vse metode |
| `testing/data/two_tracklines.json` | meritve |
| `testing/rezultati_dva_trackline.md` | tabele in sklep |

---

## Viri

- Hansen, Lunde & Nason (2011), *The Model Confidence Set*, Econometrica 79(2),
  453–497 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=522382
- Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Bailey & López de Prado, *The Deflated Sharpe Ratio*
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Test zaobjetja napovedi (forecast encompassing)
  — https://economicsnetwork.ac.uk/showcase/cook_encompassing
