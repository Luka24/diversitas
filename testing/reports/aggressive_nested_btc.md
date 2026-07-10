# Nested walk-forward (BTC) — pravi test brez selection biasa

Prej sem kandidata izbral gledajoč vse podatke, kar je selection bias. Tukaj v vsakem obdobju parameter izberem SAMO iz preteklosti (train), potem ga uporabim na neviden test. Izbira nikoli ne vidi testa. Iščem po re-entry {1,2,3,4} × bear-cut {0,25,50,75}, izberem po train Sortino.

| Test obdobje | režim | izbran iz train | OOS Sortino (izbran) | OOS Sortino (baseline) |
|---|---|---|---|---|
| bull/top | | re-entry 3, bear 75 | 2.02 | 1.44 |
| bear | | re-entry 2, bear 75 | -2.77 | -2.76 |
| recovery | | re-entry 2, bear 0 | 3.59 | 3.72 |
| bull | | re-entry 2, bear 0 | 2.03 | 2.09 |
| bear/chop | | re-entry 2, bear 25 | -0.35 | -0.35 |

**Zlepljen OOS Sortino: izberi-iz-train 1.16 vs fiksni baseline 1.16 (Δ -0.00).**

## Kaj to pomeni

**Ko izbira NE vidi testa, prednost izgine (Δ ≈ 0).** To pomeni da je bil full-sample 'win' (Sortino 1.62 → 1.92) večinoma **selection bias** — nastal je ker sem parameter izbral gledajoč iste podatke na katerih sem ga potem meril. Na res nevidenih podatkih se prednost ne ponovi.

Mehanizem se vidi v izbranih parametrih: **bear-cut je nestabilen** — train izbere 75 (2021, 2022), potem 0 (2023, 2024), potem 25 (2025). Nima stabilne vrednosti, ker kar je bilo optimalno na preteklosti ni optimalno na naslednjem obdobju (nestacionaren trg). Re-entry je bolj stabilen (večinoma 2), a sam ne dvigne zlepljenega OOS nad baseline.

**Zaključek: brez ločenega train/test-a so per-leto/CPCV/bootstrap checki gledali isto izbiro na istih podatkih in so bili zavajajoče pozitivni. Nested walk-forward je edini ki to odpravi — in pokaže da tuning teh parametrov ne prinese zanesljive OOS prednosti. Ostani pri baseline (Pine) vrednostih.**
Izbrani re-entry po foldih: [3, 2, 2, 2, 2]. Izbrani bear-cut: [75, 75, 0, 0, 25].

*To je nested walk-forward: edini način ki brez ločenega fiksnega test-seta zagotovi da izbira parametra ne pogleda testnih podatkov (Lopez de Prado, AFML ch. 7/12).*
