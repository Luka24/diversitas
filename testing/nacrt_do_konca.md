# Načrt do konca

**Stanje:** ~200 preizkušenih konfiguracij · ETH porabljen · ena odprta odločitev

---

## Kje smo

| | izid |
|---|---|
| revizija pogleda v prihodnost | čisto, 200 datumov |
| zamrznjena referenca | postavljena, SHA256 `957d3bc9…` |
| poenostavitev | 14 → 10 parametrov, serija pozicij nespremenjena |
| pregretje blokira tudi vstop | sprejeto, dokazljivo nevtralno |
| premor pred ponovnim vstopom | **brez spremembe** |
| prilagodljivi mrtvi pas | **brez spremembe** |
| vstop po večini pogojev | **zavrnjeno** — poslabša |
| izstopne različice (Turtle 10/20/55) | **brez spremembe**, današnji zmaga |
| `exit_grace_bars = 3` | **potrjen** — brez njega −0,325 Sortina |
| Donchian | prestal walk-forward, ETH, CSCV, naključni zamik — **odprto** |

**Ena odprta odločitev, nič drugega.**

---

## Zakaj se iskanje izboljšav tu konča

Trije razlogi, vsi izmerjeni v tem projektu:

1. **~200 konfiguracij.** Deflacionirani Sharpe uporablja **skupno** število
   poskusov. Vsaka nova hipoteza razvrednoti vse prejšnje sklepe.
2. **ETH je porabljen.** Načrt je dovolil dve vnaprej zapisani hipotezi; obe sta
   izkoriščeni. Tretji zajem ni dokaz.
3. **PBO 0,694** na zgodnjih parametrih. Izbiranje najboljše nastavitve na teh
   podatkih je **slabše od meta kovanca**.

Od tu naprej so vredni samo testi, ki **ne uvajajo novih pravil**.

**Trdo pravilo:** nobene nove vstopne ali izstopne hipoteze na BTC ali ETH.
Če hočemo več, potrebujemo nove podatke — tretje sredstvo z novo predregistracijo
ali preprosto čas.

---

## Faza A — zapri odprto odločitev (1–2 h)

**A1. Odločitev o Donchianu.** Priporočilo: **dodati, ne zamenjati**.

Za: prestal ugnezdeni walk-forward v obeh shemah (edini kandidat v projektu),
ETH zunaj vzorca, CSCV 97,5 % zunajvzorčnih polovic, naključni zamik 96. percentil,
zniža stroške.

Proti: mejni prispevek ob obstoječih pravilih majhen, na BTC petkrat prihrani in
petkrat stane, v letih 2025–2026 ni spremenil nobenega dne.

Odstranitev 75-dnevnega pogoja **ne**, ker sem na istih podatkih dvakrat sklenil
nasprotno — kar pomeni, da dokaz ni dovolj trden za odstranitev delujočega pravila.

**A2. Če da:** `use_donchian = True`, `donchian_period = 20`, `donchian_top_frac`
ostane 0,75. Parametrov 10 → 11.

**A3. Referenco na novo zamrzniti** z zapisom, zakaj — prva namerna sprememba
vedenja v projektu. Test `test_reference.py` mora ostati zelen proti novi
referenci, negativna kontrola pa mora še vedno zaznati spremembo.

**A4. Zaklepni test:** perioda 20 se ne sme prevrtati. Zapisati v `config.py` z
razlogom (PBO 0,672 za izbiro periode).

---

## Faza B — preverjanja brez novih pravil (~6 h)

Nobeno od teh ne uvaja parametra. Vsa preverjajo, ali obstoječa strategija drži.

**B1. 4-urni bari.** Vsi časovni pogledi × 6, da se ohrani ekonomski horizont.
Vprašanje: ali je rezultat odvisen od tega, da gledamo dnevne zaključke?
Podatki že obstajajo (`BTC_binance_4h.parquet`).

**B2. Obdobje po ETF (od 2024-01).** Ali se je režim spremenil? Nižja nihajnost,
več institucij. Opisno — 2,5 leta je premalo za sklep, a če se strategija tam
obnaša drugače, je to treba vedeti.

**B3. Časovnica izvedbe.** Danes trgujemo po zaključku. Kaj če po **odprtju
naslednjega dne**? To je realnejše in je test robustnosti, ne izboljšava.
Pričakovati je poslabšanje; vprašanje je, koliko.

**B4. Vir podatkov.** Binance proti Coinbase proti Yahoo na istem oknu. Če se
rezultat premakne za več kot nekaj stotink, je odvisen od vira.

---

## Faza C — poštena karakterizacija (~4 h)

Nič od tega ne spreminja strategije; vse odgovarja na »kaj naj pričakujemo«.

**C1. Deflacionirani Sharpe s polnim številom poskusov.** Doslej smo poročali
nedeflacionirane številke. S ~200 poskusi je popravek velik in ga je treba
poznati, preden gre karkoli v produkcijo.

**C2. Sodelovanje v padcih.** Koliko strategija izgubi, ko BTC izgubi 20, 40, 60 %?
Primerjava s statičnim 40 % BTC / 60 % gotovina, ker je to najbližja preprosta
alternativa.

**C3. MinTRL.** Koliko let bi potrebovali, da bi z gotovostjo ločili to strategijo
od kupi-in-drži? Prej izmerjeno: 25 do 1200 let. To je treba **povedati naglas**,
ne skriti.

**C4. Pošteno pričakovanje naprej.** Ena številka za sodelavce, z intervalom.

---

## Faza D — zaključek

**D1. Končno poročilo** — kaj je bilo ugotovljeno, kaj **ni**, in kaj je bilo
zavrnjeno. Seznam zavrnjenih je enako pomemben kot seznam sprejetih.

**D2. Kaj ostaja nedokazano** — izrecen seznam. Npr.: da je strategija boljša od
kupi-in-drži (MinTRL pravi, da tega na teh podatkih ni mogoče pokazati).

**D3. Pravilo za ponovno odpiranje.** Kaj bi upravičilo nove teste:
- 12 mesecev novih podatkov naprej
- tretje sredstvo z novo predregistracijo
- sprememba v izvedbi (stroški, likvidnost), ki spremeni predpostavke

**Ne** upravičuje: slabša uspešnost v enem četrtletju. To je natanko trenutek,
ko se strategije po nepotrebnem popravlja.

---

## Kaj bi najbolj izboljšalo zaupanje

**Čas.** Vsak mesec doda ~21 dni resnično novih podatkov — edini vir, ki ga ne
moremo izčrpati z večkratnim testiranjem. Po dvanajstih mesecih bo naprej
obstajalo ~250 dni popolnoma svežega vzorca, kar je več, kot je prispevala
katerakoli od dosedanjih hipotez.

To je tudi razlog, da se **zdaj ustaviti** ni izguba: karkoli bi zdaj še našli,
bi bilo šibkejše od tega, kar bo čez leto na voljo zastonj.

---

## Vrstni red in čas

| | | ure |
|---|---|---|
| A | odločitev o Donchianu + referenca | 1–2 |
| B | robustnost brez novih pravil | 6 |
| C | poštena karakterizacija | 4 |
| D | zaključek in dokumentacija | 3 |
| | **skupaj** | **~15** |

Po fazi D **stop**, dokler ne nastopi eden od pogojev iz D3.
