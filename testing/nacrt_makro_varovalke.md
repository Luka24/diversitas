# Makro varovalke — načrt, zapisan pred izvedbo

Vse spodaj je določeno **preden** sem pognal en sam test. Brez tega je vsak
rezultat izbran za nazaj.

## Kaj sploh testiramo

Ali makro filter, prilepljen na Lean, izboljša tvegano prilagojen donos po
proviziji 0,30 % na stran, **od 1. 1. 2021**, na BTC in ETH.

## Zakaj je vzorec problem in kako ga obidem

Od 2021 ima BTC **11 poslov**, ETH **8**. Na tem se ne da dokazati nič — ena
srečna izognitev in Sortino poskoči.

Zato **ne merim na ravni poslov**. Merim na ravni dnevnih donosov: BTC je v
poziciji 730 dni od 2036, od tega **365 izgubnih**, s skupno izgubo 603 %. To je
material, na katerega varovalka lahko vpliva, in tam ima test moč.

## Podatki

Vse z Yahooja, predpomnjeno v `testing/data/macro.parquet`.

| serija | kaj meri | smer |
|---|---|---|
| DXY | dolar | visok = slabo |
| VIX | volatilnost delnic | visok = slabo |
| MOVE | volatilnost obveznic | visok = slabo |
| HYG/IEF | kreditni pribitek | **nizek = slabo** |

Kreditni pribitek namenoma **ni** iz FRED-a. Tamkajšnja BAMLH0A0HYM2 izhaja z
zamikom in se revidira, zato bi backtest bral številke, ki tistega dne niso
obstajale — lookahead, ki ga ne opaziš, če ga ne iščeš. Razmerje dveh ETF-ov
meri isto stvar, objavlja se sproti in se ne popravlja.

**Zamik en dan.** ZDA trgi zaprejo ~21:00 UTC, Binance dnevna sveča ob 23:59
UTC, torej bi isti dan tehnično že smel uporabiti. Zamaknem vseeno — stane nekaj
signala in odvzame vsak ugovor.

## Oblika filtra — enaka za vse serije

```
risk_ok  =  vrednost  <  MA200(vrednost)        za DXY, VIX, MOVE
risk_ok  =  vrednost  >  MA200(vrednost)        za kreditno razmerje
```

Ena sama oblika za vse štiri. Nobenih pragov, nobenega prilagajanja po seriji.
**MA200 ni izbran iz teh podatkov** — je ista dolžina, ki jo strategija že
uporablja za režim, izbrana zunaj tega testa. Periode ne bom optimiziral; to je
natanko past, ki smo se ji izognili pri Donchianu.

## Različice — celoten seznam, nič dodanega pozneje

| | filter |
|---|---|
| A | brez (izhodišče) |
| B | samo DXY |
| C | samo kredit |
| D | samo VIX |
| E | samo MOVE |
| F | vsi štirje hkrati |
| G | večina (≥3 od 4) |

Vsaka v dveh načinih: **blokira samo vstop**, in **blokira vstop + sili izstop**
(s trodnevno potrditvijo, kot obstoječi izstop). Skupaj 13 celic proti izhodišču.

## Statistika

1. Glavne številke od 2021: Sortino, CAGR, MaxDD, posli, izpostavljenost
2. Parni blok bootstrap ΔSortino proti A, blok 20, 5000 vzorcev
3. **Krožni zamik kot placebo**: makro signal zavrtim 1000-krat. Ohrani
   frekvenco in gručenje, uniči poravnavo s ceno. Če pravi ne prekaša zavrtenih,
   filter ne ve nič — le manj je v trgu.
4. PBO po CSCV z 21-dnevnim purgeom čez vse celice
5. Izpostavljenost: Sortino je invarianten na skaliranje, zato filter, ki samo
   zmanjša čas v trgu, **ne more** dvigniti Sortina — dvig pomeni informacijo.
   MaxDD primerjam proti izhodišču, skaliranem na isto izpostavljenost.

## Merilo za sprejem — določeno zdaj

Sprejmem samo, če velja **vse štiri**:

- ΔSortino na BTC ima interval zaupanja, ki **ne objame ničle**
- na ETH je **isti predznak**
- placebo: pravi signal nad **95. percentilom** zavrtenih
- **PBO < 0,5**

Če pade katerakoli, je odgovor ne. Glede na to, kako so se končali premor pred
vstopom, prilagodljivi pas, večinski vstop in ATR stop, to pričakujem.

## Česar ta test ne pove

Od 2021 ni prave recesije ne kreditnega dogodka. Marec 2020 — edini resnični
stresni test v kripto dobi — je **zunaj okna**. Filter, ki tu ne pokaže ničesar,
je lahko vseeno koristen v krizi, ki je vzorec ne vsebuje. To je argument iz
mehanizma, ne iz številk, in ga bom kot takega tudi označil.
