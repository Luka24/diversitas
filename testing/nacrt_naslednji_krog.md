# Naslednji krog: BTC in altcoini

Zapisano 8. oktobra 2026.

Pet dni septembrskega preizkušanja se je končalo s sklepom "ne spreminjaj
ničesar". Ta načrt ne išče novih pravil. Najprej preveri, ali so bila stara
merjena pošteno, potem pa poskusi nekaj kandidatov z jasnim mehanizmom, ki jih
doslej ni nihče preizkusil.

Vrstni red je pomemben. Dokler točke 1 do 4 niso narejene, nima smisla iskati
novih pravil, ker ne vemo, ali je merilo pravo.

---

## Kaj že vemo, preden začnemo

Dve meritvi sta narejeni ob pisanju tega načrta.

### Petina knjige je bila mrtva gotovina

`testing/scripts/fantomska_gotovina.py`

Knjiga sredstvu brez podatkov da pozicijo 0, mesečno uravnavanje pa kapital
vseeno natoči v ta rukav. SOL ima pozicijo šele od 2022, HYPE od 2025.

| | BTC | ETH | BNB | LINK | SOL | HYPE |
|---|---|---|---|---|---|---|
| dni s pozicijo | 100 % | 92,1 % | 78,2 % | 62,8 % | 44,1 % | 11,3 % |

V povprečju je bilo **21,2 %** knjige v gotovini, ki je nihče ne bi držal.

| | Sharpe | Sortino | CAGR | MaxDD | konec |
|---|---|---|---|---|---|
| šest, kot danes | 1,47 | 2,28 | 39 % | **−28 %** | 34x |
| šest, normalizirane uteži | 1,53 | 2,42 | 58 % | **−39 %** | 123x |
| tri, kot danes | 1,53 | 2,48 | 41 % | −28 % | 37x |
| tri, normalizirane uteži | 1,67 | 2,75 | 64 % | −34 % | 189x |

Normalizirano pomeni, da se utež manjkajočega sredstva razdeli med tista, ki
podatke imajo. To ne gleda naprej, ker je znano v realnem času.

Kaj iz tega sledi:

- **Sklep tri proti šestim zdrži.** Pri današnji konvenciji +0,18 [−0,39, +0,80],
  pri normalizirani +0,32 [−0,32, +0,97]. Ni se obrnil, ker ima knjiga treh
  skoraj enak delež mrtve gotovine, 21,3 %.
- **Merilo pod padcem pa se premakne**, z −28 % na −39 %. Ravno padec je os,
  na kateri je projekt dobil edini dokaz (ciljanje volatilnosti) in edino
  zavrnitev z dokazom (denar v BTC). Oba sta merjena proti osnovi, ki je imela
  petino kapitala v gotovini.

### Davek: danes ga ni, tveganje je drugje

`testing/scripts/stevilo_odsvojitev.py`

Stanje oktobra 2026. Fizična oseba v Sloveniji od dobička pri prodaji
kriptovalut **ne plača dohodnine**, razen če FURS trgovanje šteje za
**dejavnost**. Zakon o 25-odstotnem davku je vlada potrdila julija 2025, DZ pa
ga je novembra 2025 umaknil z dnevnega reda in ni bil sprejet. Avgusta 2026 je
svetovalna skupina nove vlade predlagala drug model, 5 % na **znesek
unovčenja** nad 10.000 evrov na leto. Ta ni v zakonodajnem postopku.

Lestvice v `shared/tax.py` so za vrednostne papirje in za kripto ne veljajo.

Za koliko transakcij gre:

| | prodaj v 10,6 letih |
|---|---|
| iz signala, vseh šest sredstev | **94** |
| iz mesečnega uravnavanja | **do 762** |
| kupi in drži | **1** |

Ta številka danes ni davek. Je pa eden od dveh dejavnikov, ki ju FURS navaja
pri presoji, ali gre za dejavnost: vrednost prometa in število transakcij.
Avtomatizirana strategija z mesečnim uravnavanjem šestih sredstev je bližje tej
meji kot kupi in drži.

Oba predloga imata eno skupno potezo, ki je za načrt pomembna: menjava
kriptosredstva za drugo kriptosredstvo **ni** obdavčljiva, obdavči se šele
prehod v evre ali plačilo. Če bi bil kateri sprejet, bi štelo samo, kam gre
denar ob izstopu.

---

## Pravila, ki veljajo za ves krog

Vse, kar je v septembru delovalo, ostane:

- protokol faz iz `protokol_faze.py`, pogoji C1 do C4, zapisani vnaprej
- v padajočih fazah se primerja zložen donos, ne razmerja
- interval iz bločnega bootstrapa, bloki po 20 dni, iste bloke za obe različici
- provizija in zdrs 0,30 % na stran, dokler točka 20 ne da boljše številke

Dodano v tem krogu:

- **vsak test na knjigi se požene pri obeh konvencijah uteži.** Obvelja samo
  sklep, ki zdrži pri obeh. Kar se obrne, je ugotovitev o knjigovodstvu
- **merilo za sprejem se zapiše v skripto pred prvim zagonom**, kot pri
  `sreca_datuma.py`

---

## Prvi del: ali je bilo merjeno pošteno

### 1. Davek: ne izračun, ampak odločitev o izstopu in vprašanje dejavnosti

Davka danes ni, zato izračun po davku ni prva naloga. Ostaneta dve stvari:

- **Dejavnost.** Vprašaj davčnega svetovalca, ali avtomatizirano trgovanje s
  približno 9 izstopi in do 72 uravnavanji na leto FURS lahko šteje za
  dejavnost. Če lahko, je to edini scenarij, v katerem davek nastane že danes,
  in to kot dohodek iz dejavnosti s prispevki. Ni naloga za backtest.
- **Kam gre denar ob izstopu.** Če gre v stablecoin namesto v evre, ostane
  izstop pri obeh dosedanjih predlogih menjava kripto za kripto. Preveri v
  besedilu predloga, ali stablecoin šteje za kriptosredstvo. Backtest naj ima
  stroške menjave v stablecoin namesto v evre.

Če bo kateri predlog sprejet, se v `tax.py` doda kripto ureditev in požene
knjigo. Model s 5 % na znesek unovčenja je od obrata neodvisen, model s 25 % na
dobiček pa obdavči samo prehod v evre.

### 2. Ponovi verdikte na knjigi pri normaliziranih utežeh

Pet verdiktov je bilo merjenih proti knjigi z 21 % gotovine:

| verdikt | danes | ponovi |
|---|---|---|
| ciljanje volatilnosti, hierarhično | d MaxDD +13,1 [+5,6, +23,0] | ali dokaz zdrži |
| denar ob izstopu v BTC | d MaxDD −15,5 [−24,7, −6,8] | ali je bil zavrnjen zaradi mrtve gotovine |
| tri proti šestim | narejeno zgoraj | — |
| uteži po tveganju | vsi intervali čez ničlo | ali se kaj premakne |
| tedensko ukrepanje | d Sortino −0,53 [−1,08, −0,04] | ali zavrnitev zdrži |

Koda obstaja. Potrebna je ena funkcija uteži, ki jo lahko vzameš iz
`fantomska_gotovina.py`.

### 3. Zamuda izvedbe

Backtest kupi po naslednjem zaključku. V resnici bo naročilo oddano minute ali
ure kasneje. Dokazano je, da teden zamude vzame 0,53 Sortina. Vprašanje je,
kje med eno uro in sedmimi dnevi se to začne.

Na 1h svečkah premakni izvedbo za 1, 4, 12 in 24 ur, signal pusti na dnevnem
zaključku. Postopek je enak kot v `sreca_datuma.py`.

**Kaj odloči:** če pri 4 urah izgine več kot polovica prednosti pred statičnim
deležem, strategija potrebuje avtomatsko izvedbo ob zaključku, in to je treba
vedeti pred kakršnimkoli živim denarjem.

Skripta: `zamuda_izvedbe.py`

### 4. Slabe svečke

Za ETF-je obstaja `etf_data_audit.py`, za kripto nič. Kripto je bolj umazan,
Coinbase je imel 2017 ETH na 10 centih.

Poišči svečke, ki izstopajo: dnevni razpon nad 5 sigma, zaključek, ki se med
Coinbase in Binance razlikuje za več kot 2 %. Preveri, ali katera leži na dan
vstopa ali izstopa. Poženi strategijo še na očiščenih podatkih.

**Kaj odloči:** če se nobeden od 28 poslov na BTC ne premakne, je to zapisano
in zaprto. Če se premakne, ga je treba pojasniti, preden se karkoli drugega
meri.

Skripta: `kripto_data_audit.py`

### 5. Koliko dni nosi vso prednost

Dneve, ko je strategija zunaj, razvrsti po tem, koliko je izogib prinesel.
Odštej najboljših 5, 10 in 20. Poglej, koliko prednosti pred statičnim deležem
ostane.

**Kaj odloči:** če po desetih dneh prednost izgine, je to deset srečnih dni, ne
veščina. Če ostane, je to najbolj razumljiv argument za strategijo, kar jih
imamo.

Skripta: `koncentracija_prednosti.py`

### 6. Čas pod vodo in najslabše drseče leto

`metrics.py` meri globino padca, ne pa njegovega trajanja. Dodaj:

- najdaljšo serijo dni brez novega vrha
- najslabši drseči 12-mesečni donos

Primerjaj z BTC kupi in drži in s statičnim deležem. Strategija, ki je 28 %
časa v trgu, ima lahko daljši čas pod vodo kot kupi in drži, čeprav plitvejši
padec, ker zamudi okrevanje.

To je pol ure dela in številka, ki jo potrebuje vsak, ki bo ta denar nosil.

Mesto: `testing/scripts/metrics.py`, z enim testom v `testing/tests/`

### 7. Je perioda 75 poseben, ali je bil srečen

Ansambel je padel samo zato, ker je 75 najboljši član mreže. Del 9 altcoinskega
poročila pravi, da bi to premislilo sklep.

Za vsak kovanec z vsaj 1000 dnevi in na 4h svečkah na BTC poglej, na katerem
percentilu mreže iz `ansambel.py` leži 75.

**Merilo, zapisano zdaj:** če je 75 nad 70. percentilom na manj kot polovici
kovancev in na 4h uri ni nad mediano, je bila zavrnitev ansambla artefakt
enega vzorca, in ansambel postane pravilna izbira kot zaščita pred napačno
periodo.

Skripta: `je_75_poseben.py`

---

## Drugi del: novi kandidati, binarni, z mehanizmom

Vsi gredo skozi protokol faz in skozi obe konvenciji uteži.

### 8. Širina signala med sredstvi

Vstop je dovoljen samo, če ima signal vsaj K od šestih sredstev, K = 2, 3, 4.

Mehanizem: če se giblje en kovanec sam, je to običajno šum. Če se gibljejo
vsi, je trend pravi. `vec_sredstev.py` to število že izpisuje, za odločitev pa
ga nikoli ni uporabil.

### 9. Obseg trgovanja kot potrditev vstopa

Lean obsega ne gleda, Full ga ima. V `features.py` ga ni med preizkušenimi.

Najprej predtest, ki je skoraj zastonj: ali je komponenta obsega v Full kdaj
premaknila kakšen posel. Če ni, je stvar zaprta kot pri `vol_shock`.

Če je, pravilo za lean: zaključek v zgornji četrtini kanala in obseg nad
20-dnevnim povprečjem.

### 10. BTC filter na altcoinih

`use_btc_filter` obstaja in je za lean izklopljen. Edini test je bil julija, za
momentum, brez intervalov in brez faz. Nič novega ni treba napisati.

### 11. BTC odloča o izstopu altov, ne o vstopu

Alt vstopi po svojem signalu, izstopi pa tudi, ko BTC pade pod svoj pas.

Mehanizem: v rasti so alti pogosto pred BTC, zato vstopni filter odreže
najboljše začetke, kar se sklada s tem, da je knjižno stikalo padlo v 0 od 4
rastočih faz. V padcu pa alti vedno padejo z BTC, le globlje. Filter gre samo
tja, kjer je povezava zanesljiva.

To je oblika kandidata, ki lahko izpolni C1 in C2 hkrati.

### 12. Prerazporeditev v sredstva s signalom

Kapital gre v vsa sredstva s signalom po 1/K, namesto v gotovino. Pozicija na
sredstvo ostane binarna.

Bratranec zavrnjenega "denar v BTC". Ta je bil delno zavrnjen zato, ker je
uporabil mrtvi kapital, in zdaj vemo, da ga je bilo 21 % iz drugega razloga.
Ti dve stvari je treba ločiti. Pričakovanje: pade na C2. Vredno je vedeti
zakaj.

### 13. Košarica izbrana po korelaciji, ne po velikosti

IDM 1,09 pravi, da se šest sredstev vede kot eno. Preizkus širine je dodajal
kovance po kotaciji, pravilo iz `porocilo_vec_sredstev.md` po velikosti.
Nikoli po razpršitvi.

Vsak mesec med likvidnimi kovanci izberi tri ali štiri z najnižjo medsebojno
korelacijo na zadnjem letu. Izmeri IDM.

**Kaj odloči:** če se dvigne nad 1,5, se vprašanje širine postavi na novo. Če
ostane pod 1,2, v kriptu razpršitve ni, in to je zapisano za vedno.

### 14. Signal na košarici namesto na vsakem kovancu

Enakoutežni indeks altov, lean na njegovi ceni, ena pozicija za ves košarični
del.

Mehanizem: šum posameznega kovanca se v indeksu pokrajša, število poslov pade
približno šestkrat. To pomaga pri provizijah in zmanjša število transakcij, ki jih FURS gleda pri presoji dejavnosti (točka 1).

`one_signal.py` tega ne pokriva.

---

## Tretji del: zvezno, samo kot primerjalna cena

Ne za uvedbo, ker rušita binarno omejitev. Za to, da vemo, koliko ta omejitev
stane.

### 15. Carverjeva napoved

Razlika dveh eksponentnih povprečij, deljena z volatilnostjo, skalirana na
povprečno absolutno vrednost 10, omejena na ±20, hitrosti seštete z
množiteljem razpršitve. `porocilo_vec_sredstev.md` jo navaja kot nepreizkušeno,
`hitrosti.py` je ni pokril.

Razlog: deljenje z volatilnostjo je edina os, na kateri je projekt kdaj dobil
interval, ki izključuje ničlo.

### 16. Ciljanje volatilnosti na popravljeni osnovi

Ponovitev edinega dokaza v projektu proti polno naloženi knjigi. Del točke 2,
tu navedeno posebej, ker je odločitev o njem drugačna.

---

## Četrti del: ali se da izvesti in ali bo kdo zdržal

### 17. Kapaciteta

Za vsako sredstvo mediana dnevnega prometa in delež, ki ga predstavlja posel
pri 100.000, 1 milijonu in 10 milijonih evrov kapitala. Nad nekaj odstotki
predpostavka 0,30 % ne velja, ne glede na meritev zdrsa.

Posebej HYPE, ki se trguje na eni borzi.

### 18. Sreča vstopnega datuma

Strategija iz vsakega možnega začetnega meseca, porazdelitev končnega izida
proti kupi in drži. Pri ETF-jih je isti postopek pokazal, da je vsa prednost
prihajala iz enega dneva. Za kripto ni bil narejen.

### 19. Mesečno dolaganje

Ista strategija, ko denar prihaja mesečno namesto enkrat. Drugačna povprečna
vstopna cena, več in mlajših davčnih svežnjev. Možno je, da strategija tu
izgubi manj kot kupi in drži, ker ima gotovino, s katero vplačila sprejme.

### 20. Kje se bo izvajalo

0,30 % je ena številka namesto treh: provizija, razmik in zdrs zaradi
velikosti. Zapiši cenik in čas izvedbe dejanske platforme.

---

## Peti del: merjenje, ki je bilo načrtovano in ni narejeno

### 21. Zdrs

Ukrep 3 iz altcoinskega poročila. Dnevnika v repozitoriju ni.

- **zgradi ga**: cena, ki jo je videla strategija, in cena izvedbe, vsak dan
- **oceni ga že zdaj** iz 1-minutnih svečk: porazdelitev cene v prvih minutah po
  dnevnem zaključku
- **izračunaj prelomno ceno**: pri kateri ceni posla današnja oblika neha
  premagovati statični delež. Če je pri 0,9 %, je razprava o 0,30 % proti
  0,45 % nepomembna

### 22. Moč varovalke in prednost na enoto volatilnosti

Varovalka "Sharpe pod 0,3 v 18 mesecih ob rastočem BTC": z
`min_track_record.py` izračunaj, kako pogosto bi se sprožila, če se ni nič
spremenilo. Če je odgovor 40 %, prag ni uporaben.

Zraven regresija presežka nad statičnim deležem na uresničeno volatilnost. Če
ostanek nima trenda, je "propadanje" v resnici mirnejši trg, in pričakovanja
iz Ukrepa 4 je treba preskalirati na današnjo volatilnost.

---

## Česa ne delamo

| ne | zakaj |
|---|---|
| prilagajanje parametrov | gnezdeni walk-forward, razlika točno 0,00 |
| tedensko ali mesečno ukrepanje | dokazano slabše, razen če točka 2 obrne |
| uteži po tveganju | vsi intervali čez ničlo |
| pas brez trgovanja | validacija 1,78, hold-out 0,20 |
| zunanji makro viri | sprožijo se na 11 od 2600 dni |
| stopnjevana velikost | na validaciji ničelno že pred stroški |
| hitrost izstopa, trajno dno | plato, današnja nastavitev na vrhu |
| parametrski ansambel | razen če ga odklene točka 7 |
| več kovancev za večji vzorec | IDM 1,09 pomeni približno 1,4 neodvisnega sredstva |

Zadnja vrstica je pomembna, ker se zdi mamljiva. Petdeset kovancev bi dalo
videz petdesetkratnega vzorca in skoraj nič informacije. Več dokazov je samo v
finejši uri (točki 3 in 7) in v manj neznankah (točke 1, 20, 21).

---

## Razpored

| dan | točke |
|---|---|
| 1 | ponovitev verdiktov na knjigi (2), vprašanje dejavnosti svetovalcu (1) |
| 2 | zamuda izvedbe (3), slabe svečke (4) |
| 3 | koncentracija prednosti (5), čas pod vodo (6), perioda 75 (7) |
| 4 | BTC izstop za alte (11), širina signala (8), BTC filter (10) |
| 5 | zdrs: dnevnik, ocena, prelomna cena (21) |

Kapaciteta (17) in sreča datuma (18) sta po dve uri in se vrineta kamorkoli.

---

## Kje so skripte

| kaj | datoteka | stanje |
|---|---|---|
| mrtva gotovina v knjigi, tri proti šest | `testing/scripts/fantomska_gotovina.py` | narejeno |
| število davčnih dogodkov | `testing/scripts/stevilo_odsvojitev.py` | narejeno |
| zamuda izvedbe | `testing/scripts/zamuda_izvedbe.py` | za napisati |
| slabe svečke | `testing/scripts/kripto_data_audit.py` | za napisati |
| koncentracija prednosti | `testing/scripts/koncentracija_prednosti.py` | za napisati |
| perioda 75 | `testing/scripts/je_75_poseben.py` | za napisati |
