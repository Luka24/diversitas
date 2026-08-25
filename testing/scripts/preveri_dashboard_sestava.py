import sys, pathlib, warnings, importlib.util
warnings.filterwarnings("ignore")
ROOT = pathlib.Path(r"C:/Users/lukap/Documents/ICONOMI/diversitas/diversitas")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"lean"))
import numpy as np, pandas as pd
from dataclasses import replace

spec = importlib.util.spec_from_file_location("dash", ROOT/"testing"/"dashboard_sestava.py")
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
print("1) UVOZ IN SINTAKSA                        OK")

vsi = ("BTC","ETH","SOL","LINK","BNB","HYPE","XRP")
CENE = D._cene.__wrapped__(vsi); SIG = D._signali.__wrapped__(vsi, CENE)
print("\n2) PODATKI")
for s in vsi:
    print("     %-5s %5d barov  %s do %s   signal od %s"
          % (s, len(CENE[s]), CENE[s].index[0].date(), CENE[s].index[-1].date(), SIG[s][0].index[0].date()))

KON = pd.Timestamp("2026-08-24", tz="UTC")
sesto_od = SIG["HYPE"][0].index[0]
UT = {"BTC":.50,"ETH":.10,"SOL":.10,"LINK":.10,"BNB":.10,"SESTO":.10}

print("\n3) IDENTITETA: koncna vrednost = 100 x (1 + skupaj)")
for z in ("2021-01-01","2023-07-01"):
    idx = CENE["BTC"].loc[pd.Timestamp(z,tz="UTC"):KON].index
    r, prov, konc, pot = D._knjiga(idx, CENE, SIG, UT, 30, True, sesto_od)
    m = D._metrike(r)
    print("     %s  %.4f proti %.4f   %s" % (z, konc, 100*(1+m["skupaj"]/100),
          "OK" if abs(konc-100*(1+m["skupaj"]/100))<1e-6 else "NAPAKA"))

print("\n4) ROBNI PRIMERI")
idx = CENE["BTC"].loc[pd.Timestamp("2023-01-01",tz="UTC"):KON].index
_,_,k0,_ = D._knjiga(idx, CENE, SIG, UT, 0, True, sesto_od)
_,_,k30,_ = D._knjiga(idx, CENE, SIG, UT, 30, True, sesto_od)
print("     brez provizij > s provizijami: %.1f > %.1f   %s" % (k0,k30,"OK" if k0>k30 else "NAPAKA"))
_,pr0,_,_ = D._knjiga(idx, CENE, SIG, UT, 0, True, sesto_od)
print("     pri 0 bp so provizije nic: %.4f   %s" % (sum(pr0.values()), "OK" if sum(pr0.values())<1e-9 else "NAPAKA"))
_,prU,_,_ = D._knjiga(idx, CENE, SIG, UT, 30, False, sesto_od)
print("     brez uravnavanja je ta postavka nic: %.4f   %s" % (prU["uravnavanje"], "OK" if prU["uravnavanje"]<1e-9 else "NAPAKA"))
# samo BTC prek knjige proti neposrednemu izracunu
from diversitas.config import LeanConfig
from diversitas.strategy import position, traded_fraction, run_strategy
from shared.warmup import trim_warmup
from shared.data_source import DEFAULT_SYMBOL_MAP
sm = dict(DEFAULT_SYMBOL_MAP); sm["HYPE"]={"hyperliquid":"HYPE"}
cfg = replace(LeanConfig(), symbol_map=sm)
_,_,kb,_ = D._knjiga(idx, CENE, SIG, {"BTC":1.0}, 30, False, None)
df = trim_warmup(run_strategy(CENE["BTC"], config=cfg).df)
p = position(df,cfg).reindex(idx); t = traded_fraction(df,cfg).reindex(idx).fillna(0)
ret = CENE["BTC"]["close"].pct_change().reindex(idx).fillna(0.0)
v = 100.0
for i in range(len(idx)): v *= (1 + p.iloc[i]*ret.iloc[i] - t.iloc[i]*0.003)
print("     samo BTC: knjiga %.3f, neposredno %.3f   %s" % (kb, v, "OK" if abs(kb-v)<0.01 else "NAPAKA"))

print("\n5) PRIMERJAVA, konec fiksiran na %s\n" % KON.date())
print("     %-12s%9s%7s%7s%7s%9s%8s   |  porocilo (konec 25.8., nedokoncan)" % ("vstop","skupaj","Sh","Sor","MDD","konc.","prov."))
POR = {"2021-01-01":"277%  0.99  1.49  -29%   377  16.9","2021-07-01":"139%  0.80  1.19  -29%   239   9.6",
       "2022-01-01":"119%  0.88  1.36  -20%   219   8.2","2023-07-01":"118%  1.16  1.79  -16%   218   7.1",
       "2025-01-01":" 18%  0.57  0.81  -15%   118   1.7","2026-01-01":"  9%  1.75  2.95   -3%   109   0.4"}
for z, ref in POR.items():
    idx = CENE["BTC"].loc[pd.Timestamp(z,tz="UTC"):KON].index
    r, prov, konc, _ = D._knjiga(idx, CENE, SIG, UT, 30, True, sesto_od)
    m = D._metrike(r)
    print("     %-12s%8.0f%%%7.2f%7.2f%6.0f%%%9.0f%8.1f   |  %s"
          % (z, m["skupaj"], m["sharpe"], m["sortino"], m["maxdd"], konc, sum(prov.values()), ref))
