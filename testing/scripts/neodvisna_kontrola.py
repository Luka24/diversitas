"""Neodvisna ponovitev: vodim DENAR po rokavih, ne donosov, in sele nato metrike."""
import sys; sys.path.insert(0, '.')
from dataclasses import replace
import numpy as np, pandas as pd, requests, time
from model.config import DEFAULT_CONFIG as base
from model.data_source import fetch_candles, DEFAULT_SYMBOL_MAP
from model.strategy import run_strategy, trim_warmup, position, traded_fraction
BPS, PPY = 30, 365
sm = dict(DEFAULT_SYMBOL_MAP); sm["HYPE"]={"hyperliquid":"HYPE"}
C = replace(base, symbol_map=sm)
def binance(s):
    out, st = [], 1400000000000
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
     for s in ("BTC","ETH","SOL","LINK","HYPE")}
R["BNB"] = binance("BNBUSDT"); R["XRP"] = binance("XRPUSDT")
POS = {s:(lambda d:(position(d,C), traded_fraction(d,C).fillna(0)))(trim_warmup(run_strategy(R[s],config=C).df)) for s in R}
kon = min(R[s].index[-1] for s in R); HYPE_OD = POS["HYPE"][0].index[0]
CILJ = {"BTC":.50,"ETH":.10,"SOL":.10,"LINK":.10,"BNB":.10,"SESTO":.10}

def neodvisno(idx, uravnavaj):
    """Vsak rokav je znesek v EUR. Nic donosov, samo denar."""
    E = {k: 100.0*CILJ[k] for k in CILJ}      # zacnemo s 100 EUR
    zgod = [sum(E.values())]
    prov = {"signal":0.0, "ura":0.0, "zam":0.0}
    prej6 = "HYPE" if idx[0] >= HYPE_OD else "XRP"
    _s = pd.Series(idx, index=idx); konci = set(_s.groupby([idx.year, idx.month]).last())
    P = {s:(POS[s][0].reindex(idx), POS[s][1].reindex(idx).fillna(0)) for s in R}
    RT = {s: R[s]["close"].pct_change().reindex(idx).fillna(0.0) for s in R}
    for i,t in enumerate(idx):
        s6 = "HYPE" if t >= HYPE_OD else "XRP"
        if s6 != prej6:
            c = E["SESTO"]*2*BPS/10000
            E["SESTO"] -= c; prov["zam"] += c; prej6 = s6
        for k in CILJ:
            s = s6 if k=="SESTO" else k
            p = P[s][0].iloc[i]
            if pd.isna(p): continue
            c = E[k]*P[s][1].iloc[i]*BPS/10000
            E[k] -= c; prov["signal"] += c
            E[k] *= (1 + p*RT[s].iloc[i])
        if uravnavaj and (t in konci) and i < len(idx)-1:
            sk = sum(E.values())
            c = sum(abs(E[k] - CILJ[k]*sk) for k in CILJ)*BPS/10000
            prov["ura"] += c; sk -= c
            E = {k: CILJ[k]*sk for k in CILJ}
        zgod.append(sum(E.values()))
    v = np.array(zgod); r = v[1:]/v[:-1] - 1
    return r, prov, v[-1]

def met(r):
    eq=np.cumprod(1+r); dd=eq/np.maximum.accumulate(eq)-1
    vol=r.std()*np.sqrt(PPY); dn=np.sqrt(np.mean(np.minimum(r,0.0)**2))*np.sqrt(PPY)
    return ((eq[-1]-1)*100,(eq[-1]**(PPY/len(r))-1)*100, r.mean()*PPY/vol, r.mean()*PPY/dn, dd.min()*100)

print("NEODVISNA PONOVITEV, denar po rokavih  (do %s)\n" % kon.date())
print("%-11s%9s%7s%7s%7s%12s%9s%9s%9s" % ("vstop","skupaj","Sh","Sor","MDD","konc.EUR","prov.sig","prov.ura","prov.zam"))
for leto in range(2021,2027):
    for mes in (1,7):
        z = pd.Timestamp(f"{leto}-{mes:02d}-01", tz="UTC")
        if z >= kon - pd.Timedelta(days=200): continue
        idx = R["BTC"].loc[z:kon].index
        if len(idx) < 200: continue
        r, prov, konc = neodvisno(idx, True)
        m = met(r)
        print("%-11s%8.0f%%%7.2f%7.2f%6.0f%%%12.0f%9.1f%9.1f%9.1f"
              % (z.date(), m[0], m[2], m[3], m[4], konc, prov["signal"], prov["ura"], prov["zam"]))
print("\n   kontrola: koncni EUR mora biti 100 x (1 + skupaj/100)")
