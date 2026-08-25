"""Ponovitev programa iz clanka, vse tri sirine, s prikazom zapolnjenosti."""
import sys; sys.path.insert(0, '.')
from dataclasses import replace
import concurrent.futures as cf
import numpy as np, pandas as pd, requests
from model.config import DEFAULT_CONFIG as base
from model.data_source import fetch_candles, DEFAULT_SYMBOL_MAP
DOL = [5,10,20,30,60,90,150,250,360]; PPY = 365

pr = requests.get("https://api.exchange.coinbase.com/products", timeout=30).json()
usd = sorted([p["base_currency"] for p in pr if p.get("quote_currency")=="USD"
              and p.get("status")=="online" and not p.get("trading_disabled")
              and not p.get("limit_only")])
IZL = {"USDT","USDC","DAI","PYUSD","EURC","GUSD","WBTC","CBETH","WETH","LSETH","USDS","PAX","BUSD"}
KAND = [s for s in usd if s not in IZL]
sm = dict(DEFAULT_SYMBOL_MAP)
for s in KAND: sm.setdefault(s, {})["coinbase"] = f"{s}-USD"
C = replace(base, symbol_map=sm)

def poberi(s):
    try:
        d = fetch_candles(s,"1d",bars=1600,config=C,prefer="coinbase",strict=True)
        return (s, d) if len(d) > 400 else (s, None)
    except Exception: return (s, None)
with cf.ThreadPoolExecutor(10) as ex:
    R = {s:d for s,d in ex.map(poberi, KAND) if d is not None}
print("kandidatov na Coinbase: %d, s podatki: %d\n" % (len(KAND), len(R)))

def podmodel(d,n):
    up=d["high"].rolling(n).max().shift(1); lo=d["low"].rolling(n).min().shift(1)
    mid=((up+lo)/2).to_numpy(); c=d["close"].to_numpy(); U=up.to_numpy()
    p=np.zeros(len(d)); st=np.nan
    for i in range(len(d)):
        if np.isnan(U[i]): continue
        pr_ = p[i-1] if i else 0.0
        if pr_==0.0:
            if c[i]>U[i]: p[i]=1.0; st=mid[i]
        else:
            if c[i]<=st: p[i]=0.0; st=np.nan
            else: p[i]=1.0; st = mid[i] if np.isnan(st) else max(st,mid[i])
    return pd.Series(p,index=d.index)
def combo(d):
    ret=d["close"].pct_change(); sg=ret.rolling(91).std()*np.sqrt(PPY)
    sk=np.minimum(0.25/sg.replace(0,np.nan), 2.0)
    dd=[n for n in DOL if n < len(d)-30]
    return pd.concat([(sk*podmodel(d,n)).fillna(0.0) for n in dd],axis=1).mean(axis=1)

W = {s: combo(d) for s,d in R.items()}
PROM = {s: (d["volume"]*d["close"]) for s,d in R.items()}
kon = min(d.index[-1] for d in R.values()); zac = kon - pd.Timedelta(days=365*3)
meseci = pd.date_range(zac, kon, freq="ME", tz="UTC"); idx = R["BTC"].loc[zac:kon].index

def upravicena(dat):
    o = {}
    for s,d in R.items():
        if len(d.loc[:dat]) < 365: continue
        m = float(PROM[s].loc[:dat].tail(30).median())
        if m >= 2_000_000: o[s] = m
    return o

def program(B, bps):
    izb = {m: sorted(u := upravicena(m), key=lambda k:-u[k])[:B] for m in meseci}
    r = np.zeros(len(idx)); tren = []; napolnjenost = []
    for i,t in enumerate(idx):
        a = [x for x in meseci if x <= t]
        sel = izb[a[-1]] if a else izb[meseci[0]]
        napolnjenost.append(len(sel)/B)
        if sel != tren:
            r[i] -= (len(set(sel) ^ set(tren))/max(B,1))*bps/10000; tren = sel
        for s in sel:
            w = W[s].reindex(idx).fillna(0.0)
            ret = R[s]["close"].pct_change().reindex(idx).fillna(0.0)
            r[i] += (1.0/B)*(float(w.shift(1).fillna(0).iloc[i])*float(ret.iloc[i])
                             - abs(float(w.diff().fillna(0).iloc[i]))*bps/10000)
    return r, float(np.mean(napolnjenost))

def met(r):
    eq=np.cumprod(1+r); dd=eq/np.maximum.accumulate(eq)-1
    vol=r.std()*np.sqrt(PPY); dn=np.sqrt(np.mean(np.minimum(r,0.0)**2))*np.sqrt(PPY)
    return ((eq[-1]**(PPY/len(r))-1)*100, vol*100, r.mean()*PPY/vol, r.mean()*PPY/dn, dd.min()*100)

print("%s do %s (%d dni)\n" % (idx[0].date(), idx[-1].date(), len(idx)))
print("%-26s%8s%7s%8s%9s%7s%14s" % ("","letno","vol","Sharpe","Sortino","MaxDD","zapolnjenost"))
for bps in (10, 30):
    for B in (5,10,20):
        r, nap = program(B, bps)
        print("%-26s%7.0f%%%6.0f%%%8.2f%9.2f%6.0f%%%13.0f %%"
              % ("top %d, %d bp" % (B,bps), *met(r), nap*100))
    print()
print("upravicenih sredstev po mesecih:")
for m in meseci[::6]: print("   %s   %d" % (m.date(), len(upravicena(m))))
print("   %s   %d" % (meseci[-1].date(), len(upravicena(meseci[-1]))))
