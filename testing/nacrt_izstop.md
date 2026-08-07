# Izstopna stran — načrt in predregistracija

**Status:** zapisano pred izvedbo
**Podatki:** BTC 2019-03-09 → 2026-07-29 (2700) · ETH 2020-01-01 → 2026-07-27 (2400)
**Stroški:** 0,30 % na stran
**Novi parametri:** 0 — vse periode so Turtlove konvencije

---

## 0. Zakaj to in zakaj šele zdaj

V tem projektu je bilo preizkušenih približno **195 konfiguracij, skoraj vse na
vstopni strani**. Izstop je bil testiran enkrat — prilagodljivi pas v 5. koraku —
in tam je škodil.

To je nesorazmerje, ki ga je treba popraviti, preden se odloči karkoli o vstopu.

### Kaj pravi stroka

| sistem | vstop | izstop |
|---|---|---|
| Turtle System 1 | 20-dnevni vrh | **10-dnevno dno** |
| Turtle System 2 | 55-dnevni vrh | **20-dnevno dno** |

**Izstop je vedno hitrejši od vstopa, nikoli obratno.** Literatura o sledenju
trendu gre dlje: dobičkonosnost izvira bolj iz asimetričnih izstopov kot iz
časovnice vstopa, in zgodnejši izstopi so pomembnejši, ker trg pogosto naredi
obrat v obliki črke V.

### Zakaj to zadeva odločitev o Donchianu

Če vstop zamenjamo z 20-dnevnim kanalom, izstop pa pustimo pri 75-dnevnem,
dobimo **vstop hitrejši od izstopa** — nasprotno od uveljavljene prakse. Tega
nismo preverili. Lahko se izkaže, da je pravi par »hiter vstop + hiter izstop«,
in ne tisto, kar bi dobili z zdajšnjim predlogom.

**Zato o vstopu ne odločam, dokler izstop ni izmerjen.**

---

## 1. Kaj je današnji izstop

```
cena < trackline75 × (1 − 3 %)   in to tri dni zapored     (trend break)
ali  blow-off                                              (pregretje)
```

Blow-off ostane nedotaknjen v vseh celicah.

## 2. Pet celic

Vstop v **vseh** ostane današnji, da je vsak učinek pripisljiv izstopu.

| | izstopni sprožilec | prizanesljivost |
|---|---|---|
| **E0** | trackline75 − 3 % | 3 dni — **današnje stanje, kontrola** |
| **E0h** | trackline75 − 3 % | **0 dni** — loči učinek prizanesljivosti |
| **E10** | cena < **10-dnevno dno** | 0 dni — Turtle System 1 |
| **E20** | cena < **20-dnevno dno** | 0 dni — Turtle System 2 |
| **E55** | cena < **55-dnevno dno** | 0 dni |

**E0h ni kandidat, ampak kontrola.** Turtlovi izstopi se sprožijo takoj, naš pa
zahteva tri dni. Brez te celice bi spreminjali dve stvari hkrati in ne bi vedeli,
katera je učinkovala.

Periode 10, 20 in 55 so **obstoječe konvencije**, ne izbrane iz mreže. Nič se ne
prevrta.

---

## 3. Metode

Ista baterija kot pri Donchianu, ker mora biti primerljiva:

1. **Kontrola** — E0 mora reproducirati zamrznjeno referenco bar za barom. Če ne,
   se korak ustavi.
2. **Metrike** — Sortino, CAGR, MaxDD, končni mnogokratnik, izpostavljenost,
   obrat, poslov; celotno okno in štiri vnaprej določena podobdobja.
3. **Sparjeni blokovni bootstrap** ΔSortino proti E0, blok 20, 5000 vzorcev.
4. **Model Confidence Set** z **obema** funkcijama izgube — povprečen donos in
   s kaznijo za padce. Prva ima več moči, druga vidi rep.
5. **Ugnezdeni walk-forward** — celica izbrana samo iz učnega dela, shemi 3/1 in 2/1.
6. **PBO prek CSCV** — 12 blokov, 924 delitev.
7. **Naključni zamik** vodilne celice — 1000 rotacij.
8. **Kje se pozicije razlikujejo** — dnevi, epizode, gibanje cene.

## 4. ETH — tretja uporaba, zato ne šteje kot dokaz

Načrt je dovolil **dve** vnaprej zapisani hipotezi na ETH. Obe sta porabljeni:
Donchian in vprašanje dveh trackline.

ETH bom **izračunal in poročal**, a ga **ne bom štel kot potrditev**. Zapisal sem,
da je vsak nadaljnji zajem tretji iz istega vodnjaka, in tega ne bom obšel s tem,
da si premislim, ko bi mi prav prišlo.

---

## 5. Odločitveno pravilo — vnaprej

**Sprejmi drugačen izstop, če velja vse:**

| | pogoj |
|---|---|
| 1 | Sortino boljši od E0 na BTC |
| 2 | boljši v **≥ 3 od 4** podobdobij |
| 3 | preživi **oba** MCS (vsaj ne izločen pri nobenem) |
| 4 | ugnezdeni walk-forward ga izbere v **obeh** shemah |
| 5 | naključni zamik ga postavi nad **90. percentil** |

Prag 3 od 4 je strožji kot pri ETH testu, ker je to **primarni izbirni test na
glavnem sredstvu**, ne potrditev.

**Če prestane več celic**, odloča preprostost: manj indikatorjev in nič
prizanesljivosti pred več indikatorji.

**Če prestane E0h in nobena Donchianova**, je ugotovitev, da je učinek v
**prizanesljivosti**, ne v sprožilcu — in takrat se lotimo nje, ne kanalov.

### Kaj bi bilo sumljivo

- **E55 zmaga** — najpočasnejši izstop, torej najdlje v trgu; najprej preveri, ali
  ni to samo več časa v trgu
- **razlika stisnjena v eno obdobje** — enako kot pri premoru in mrtvem pasu
- **E0h se izkaže za boljšo od E0** — potem je `exit_grace_bars = 3` slaba
  privzeta vrednost in to je treba povedati ločeno od Donchiana

---

## 6. Kaj se ne dela

- **ne prevrtavam period** — 10, 20, 55 in nič vmes
- **ne testiram vstopa hkrati** — vstop je fiksen, sicer učinek ni pripisljiv
- **ne spreminjam blow-offa**
- **ne uporabljam ETH kot dokaz**
- **ne popravljam pragov iz §5**, ko vidim rezultate

## 7. Odprto priznanje o dosedanjem sklepanju

Pri vprašanju, ali je 75-dnevni vstopni pogoj potreben, sem **dvakrat sklenil
nasprotno na istih podatkih** — enkrat iz mreže celic, enkrat iz sparjene
primerjave. To pomeni, da so tam dokazi dovolj šibki, da jih uokvirjenje premakne.

Poleg tega sem takrat rekel, da se sredstvi strinjata. **Ne strinjata se** — na
ETH se tisti pogoj sproži en sam dan, kar pomeni, da je tam **neaktiven**, ne pa
da je nepotreben. Celoten primer je slonel na šestih epizodah na BTC.

Odločitev o vstopu je zato **odložena**, dokler izstop ni izmerjen.

## 8. Rezultati

| datoteka | vsebina |
|---|---|
| `testing/nacrt_izstop.md` | ta dokument |
| `testing/scripts/exit_variants.py` | pet celic, vse metode |
| `testing/data/exit_variants.json` | meritve |

---

## Viri

- Original Turtle rules — https://www.theturtletrader.com/turtle-trading-rules/
- Turtle System rules, Trading Blox — https://www.tradingblox.com/Manuals/UsersGuideHTML/turtlesystem.htm
- Hansen, Lunde & Nason (2011), *The Model Confidence Set*, Econometrica 79(2)
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=522382
- Bailey, Borwein, López de Prado & Zhu, *The Probability of Backtest Overfitting*
  — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
