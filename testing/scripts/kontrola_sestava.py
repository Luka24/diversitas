"""Cista kontrola: BTC sam proti sestavi, vec oken, ena sama koda."""
import sys; sys.path.insert(0, '.')
from dataclasses import replace
import numpy as np, pandas as pd, requests, time
from model.config import DEFAULT_CONFIG as base
from model.data_source import fetch_candles, DEFAULT_SYMBOL_MAP
from model.strategy import run_strategy, trim_warmup, position, traded_fraction
BPS, PPY = 30, 365
UT = {"BTC":.50,"ETH":.10,"SOL":.10,"LINK":.10,"HYPE":.10,"BNB":.10}
sm = dict(DEFAULT_SYMBOL_MAP); sm["HYPE"]={"hyperliquid":"HYPE"}
C = replace(base, symbol_map=sm)
def binance(s):
    out, st = [], 1500000000000
    while True:
        r = requests.get("https://api.binance.com/api/v3/klines", timeout=30,
                         params={"symbol":s,"interval":"1d","startTime":st,"limit":1000}).json()
        if not r: break
        out += r
        if len(r)<1000: break
        st = r[-1][0]+86400000; time.sleep(0.2)
    d = pd.DataFrame(out, columns=["t","open","high","low","close","volume"]+["x"]*6)
    d["time"] = pd.to_datetime(d["t"], unit="ms", utc=True)
    return d.set_index("time")[["open","high","low","close","volume"]].astype(float)
R = {s: fetch_candles(s,"1d",bars=5000,config=C,prefer=("hyperliquid" if s=="HYPE" else "coinbase"),strict=True)
     for s in UT if s!="BNB"}
R["BNB"] = binance("BNBUSDT")
POS = {s: (lambda df: (position(df,C), traded_fraction(df,C).fillna(0)))(trim_warmup(run_strategy(R[s],config=C).df))
       for s in UT}
kon = min(d.index[-1] for d in R.values())

def met(r):
    eq=np.cumprod(1+r); dd=eq/np.maximum.accumulate(eq)-1
    vol=r.std()*np.sqrt(PPY); dn=np.sqrt(np.mean(np.minimum(r,0.0)**2))*np.sqrt(PPY)
    return ((eq[-1]-1)*100,(eq[-1]**(PPY/len(r))-1)*100, vol*100, r.mean()*PPY/vol, r.mean()*PPY/dn, dd.min()*100)
def sam(s, idx):
    p,t = POS[s]; p=p.reindex(idx).fillna(0); t=t.reindex(idx).fillna(0)
    ret = R[s]["close"].pct_change().reindex(idx).fillna(0.0)
    return (p*ret - t*BPS/10000).to_numpy(float)
def knjiga(idx):
    v = dict(UT); don = np.zeros(len(idx))
    P = {s:(POS[s][0].reindex(idx), POS[s][1].reindex(idx).fillna(0)) for s in UT}
    RT = {s: R[s]["close"].pct_change().reindex(idx).fillna(0.0) for s in UT}
    for i in range(len(idx)):
        sk=sum(v.values()); d=0.0
        for s in UT:
            p=P[s][0].iloc[i]
            if pd.isna(p): continue
            tr=P[s][1].iloc[i]; r=RT[s].iloc[i]; sh=v[s]/sk
            d += sh*(p*r - tr*BPS/10000); v[s] *= (1+p*r-tr*BPS/10000)
        don[i]=d
    return don

OKNA = [("3 leta", kon-pd.Timedelta(days=365*3)),
        ("4 leta", kon-pd.Timedelta(days=365*4)),
        ("5 let",  kon-pd.Timedelta(days=365*5)),
        ("od 2021-06-17", pd.Timestamp("2021-06-17", tz="UTC")),
        ("vse, odkar so vsi 4 osnovni", None)]
print("stroski 0,30 %%/stran,  do %s\n" % kon.date())
print("%-16s%13s%9s%8s%7s%8s%9s%7s" % ("okno","od","skupaj","letno","vol","Sharpe","Sortino","MaxDD"))
for ime, z in OKNA:
    if z is None:
        z = max(POS[s][0].index[0] for s in ("BTC","ETH","SOL","LINK"))
    idx = R["BTC"].loc[z:kon].index
    for lbl, r in (("  sam BTC", sam("BTC", idx)), ("  sestava 50/10x5", knjiga(idx))):
        m = met(r)
        print("%-16s%13s%8.0f%%%7.0f%%%6.0f%%%8.2f%9.2f%6.0f%%" % (ime if lbl.strip()=="sam BTC" else "", idx[0].date() if lbl.strip()=="sam BTC" else "", *m) if False else
              "%-16s%13s%8.0f%%%7.0f%%%6.0f%%%8.2f%9.2f%6.0f%%" % (lbl, idx[0].date(), *m))
    print()
