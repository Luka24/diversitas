# Nested walk-forward (BTC) — pravi test brez selection biasa

Prej sem kandidata izbral gledajoč vse podatke, kar je selection bias. Tukaj v vsakem obdobju parameter izberem SAMO iz preteklosti (train), potem ga uporabim na neviden test. Izbira nikoli ne vidi testa. Iščem po re-entry {1,2,3,4} × bear-cut {0,25,50,75} × trail {10,12,15,18,20} (= 80 kombinacij), izberem po train Sortino.

## Train / test obdobja (anchored — train raste, test je naslednje leto)

Train se vedno začne na začetku podatkov (2019-05-23) in raste; med train in test je 21-dnevni embargo (luknja, da drseči indikatorji ne pogledajo v test).

| Fold | TRAIN | TEST | izbran iz train (re-entry / bear / trail) | OOS Sortino izbran | OOS Sortino baseline |
|---|---|---|---|---|---|
| bull/top | 2019-05-23 → 2020-12-11 | 2021-01-01 → 2021-12-31 | re-entry 3 / bear 75 / trail 10 | 1.90 | 1.44 |
| bear | 2019-05-23 → 2021-12-11 | 2022-01-01 → 2022-12-31 | re-entry 2 / bear 75 / trail 12 | -2.77 | -2.76 |
| recovery | 2019-05-23 → 2022-12-11 | 2023-01-01 → 2023-12-31 | re-entry 2 / bear 0 / trail 12 | 3.59 | 3.72 |
| bull | 2019-05-23 → 2023-12-11 | 2024-01-01 → 2024-12-31 | re-entry 2 / bear 0 / trail 12 | 2.03 | 2.09 |
| bear/chop | 2019-05-23 → 2024-12-11 | 2025-01-01 → 2025-12-31 | re-entry 3 / bear 25 / trail 10 | -0.35 | -0.35 |

**Zlepljen OOS Sortino: izberi-iz-train 1.13 vs fiksni baseline 1.16 (Δ -0.03).** Nevtralna referenca (BTC buy&hold, ista okna): 0.99.

Izbrani re-entry po foldih: [3, 2, 2, 2, 3]. Bear-cut: [75, 75, 0, 0, 25]. Trail: [10, 12, 12, 12, 10].

## Kaj to pomeni

**Ko izbira NE vidi testa, prednost izgine (Δ ≈ 0, tu celo rahlo negativna).** Full-sample 'win' (Sortino 1.62 → 1.92) je bil **selection bias** — nastal ker sem parameter izbral gledajoč iste podatke na katerih sem ga potem meril.

Da je to res overfitting, potrdi še eno opažanje: **ko sem v grid dodal še trailing (80 kombinacij namesto 16), je OOS postal slabši, ne boljši** (1.13 proti prej 1.16). Več parametrov za izbiranje = več prostora da nekaj po sreči izgleda dobro na train delu = slabše na testu. To je klasičen podpis overfittinga.

Mehanizem se vidi v izbranih parametrih — **nestabilni so**: bear-cut [75, 75, 0, 0, 25], trail [10, 12, 12, 12, 10]. Skačejo iz folda v fold, ker kar je bilo optimalno na preteklosti ni optimalno naprej (nestacionaren trg). Re-entry je edini pol-stabilen (večinoma 2-3), a sam ne dvigne OOS nad baseline.

## Je baseline (12/4/50) morda tudi overfit?

Upravičeno vprašanje. Dva razloga zakaj baseline ni glavna skrb:

1. **Absolutna številka ne rabi baseline-a.** OOS Sortino adaptivnega postopka je 1.13 sam po sebi — pošten forward pogled na to kar re-optimizacija dejansko prinese. Za primerjavo: gol BTC buy&hold na istih oknih da 0.99. Strategija (adaptivna ali baseline ~1.16) je krepko nad buy&hold — torej ne baseline ne adaptivna nista slabša od trivialne alternative.

2. **Fiksni config se ne more overfitati na test tako kot adaptivni.** 12/4/50 je enak v vseh foldih — ne prilagaja se posameznemu obdobju in ne 'pokuka' v test. Edina možnost je, da je Pine avtor te vrednosti izbral gledajoč zgodovino. A iz sweep-a se vidi da baseline **sedi na platoju** (trailing 12/15/18/20 dajo skoraj isto, re-entry 3/4 podobno) — plato pomeni robustno, ne konico. Overfitan config bi bil osamljena konica, kjer sosednje vrednosti padejo.

Tako da: baseline ni magičen, je pa razumna, robustna izbira. In ključno — **dejstvo da ga adaptivno re-optimiziranje ne premaga OOS pomeni ravno to, da dodaten tuning ne doda vrednosti, ne da je baseline skrivaj natreniran na te podatke.**

*Nested walk-forward: edini način ki brez ločenega fiksnega test-seta zagotovi da izbira parametra ne pogleda testnih podatkov (Lopez de Prado, AFML ch. 7/12).*
