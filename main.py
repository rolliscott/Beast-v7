import json, time, requests
from datetime import datetime

CLOUD_FILE = "status.json"
atrLen = 14
atrSlopeLen = 14
expansionThreshold = 0.8
contractionThreshold = 0.8
wickPercent = 40
sweepLen = 20

def get_ohlc(symbol="GC=F", interval="5m", range_="5d"):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        res = r["chart"]["result"][0]
        o = res["indicators"]["quote"][0]["open"]
        h = res["indicators"]["quote"][0]["high"]
        l = res["indicators"]["quote"][0]["low"]
        c = res["indicators"]["quote"][0]["close"]
        data=[]
        for i in range(len(c)):
            if c[i] is None: continue
            data.append({"open":o[i] or c[i],"high":h[i] or c[i],"low":l[i] or c[i],"close":c[i]})
        return data
    except: return []

def calc_atr_series(data, length=14):
    if len(data) < length+2: return [1.5], 1.5
    trs=[]
    for i in range(1,len(data)):
        hl=data[i]["high"]-data[i]["low"]
        hc=abs(data[i]["high"]-data[i-1]["close"])
        lc=abs(data[i]["low"]-data[i-1]["close"])
        trs.append(max(hl,hc,lc))
    atrs=[]
    atr=sum(trs[:length])/length
    atrs.append(atr)
    for tr in trs[length:]:
        atr=(atr*(length-1)+tr)/length
        atrs.append(atr)
    return atrs, atrs[-1] if atrs else 1.5

def calc_slope(atrs, lookback=14):
    if len(atrs) < lookback+1: return 0
    now=atrs[-1]
    prev=atrs[-lookback-1]
    if prev==0: return 0
    return (now-prev)/prev*100

def main():
    print("DELPHIAN V8.7 FINAL - HTF ONLY BIAS, ALL SWEEP/ENTRY LTF 5M")
    # HTF ONLY FOR BIAS - 60m
    htf_data = get_ohlc("GC=F","60m","5d")
    # LTF 5M - FOR EVERYTHING: Sweep, Bumps, Entry, TP
    ltf = get_ohlc("GC=F","5m","5d")

    if len(ltf) < 30 or len(htf_data) < 30:
        print("No data")
        ltf=[{"open":4027,"high":4030,"low":4025,"close":4027}]*50
        htf_data=[{"open":4027,"high":4050,"low":4000,"close":4027}]*50

    ltf_series, ltf_atr = calc_atr_series(ltf, atrLen)
    htf_series, htf_atr = calc_atr_series(htf_data, atrLen)
    ltf_slope = calc_slope(ltf_series, atrSlopeLen)
    htf_slope = calc_slope(htf_series, atrSlopeLen)

    # === HTF ONLY BIAS CHECK ===
    isHTF_HILL = htf_slope > expansionThreshold  # HTF HILL Expansion HH = BUY BIAS
    isHTF_VALLEY = htf_slope < -contractionThreshold  # HTF VALLEY Contraction LL = SELL BIAS
    # LTF BREATH
    isLTF_HILL = ltf_slope > expansionThreshold
    isLTF_VALLEY = ltf_slope < -contractionThreshold

    # === LTF 5M ONLY - SWEEP LEVELS (Liquidity) ===
    # Previous 20 bars of LTF 5m only
    prevHigh_LTF = max([d["high"] for d in ltf[-sweepLen-1:-1]])  # BSL - Sell side liquidity - resistance - LTF 5m
    prevLow_LTF = min([d["low"] for d in ltf[-sweepLen-1:-1]])   # SSL - Buy side liquidity - support - LTF 5m
    balance_LTF = (prevHigh_LTF + prevLow_LTF) / 2  # Balance / 50% TP - LTF 5m
    last = ltf[-1]

    # LTF 5M SWEEP - Real liquidity sweep
    isBSL_Sweep_LTF = last["high"] > prevHigh_LTF and last["close"] < prevHigh_LTF  # LTF 5m swept BSL
    isSSL_Sweep_LTF = last["low"] < prevLow_LTF and last["close"] > prevLow_LTF  # LTF 5m swept SSL

    # LTF 5M BUMP LAW
    hh_lh = 0
    ll_hl = 0
    for i in range(2, len(ltf_series)-2):
        if ltf_series[i] > ltf_series[i-1] and ltf_series[i] > ltf_series[i-2] and ltf_series[i] > ltf_series[i+1] and ltf_series[i] > ltf_series[i+2]:
            hh_lh += 1
        if ltf_series[i] < ltf_series[i-1] and ltf_series[i] < ltf_series[i-2] and ltf_series[i] < ltf_series[i+1] and ltf_series[i] < ltf_series[i+2]:
            ll_hl += 1
    hh_lh = min(hh_lh, 10)
    ll_hl = min(ll_hl, 10)

    hill_exhaustion_LTF = hh_lh >= 2  # HH -> LH LTF 5m
    valley_exhaustion_LTF = ll_hl >= 2  # LL -> HL LTF 5m

    # === FINAL - HTF BIAS + LTF EXECUTION ===
    # SELL HILL: HTF bias VALLEY + LTF 5m HILL + BSL sweep LTF 5m + HH->LH bumps LTF 5m -> Ride to Balance
    sell_hill_LTF = isHTF_VALLEY and isLTF_HILL and hill_exhaustion_LTF and isBSL_Sweep_LTF
    # BUY VALLEY: HTF bias HILL + LTF 5m VALLEY + SSL sweep LTF 5m + LL->HL bumps LTF 5m -> Ride to Balance, war over
    buy_valley_LTF = isHTF_HILL and isLTF_VALLEY and valley_exhaustion_LTF and isSSL_Sweep_LTF

    # Real live prices for app
    xau_price = last["close"]
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        if r.get("price"): xau_price = float(r["price"])
    except: pass
    try:
        rN = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?interval=1m&range=1d", timeout=10).json()
        nas_price = rN["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except:
        nas_price = 28950

    fifty = round(xau_price/50)*50

    if sell_hill_LTF:
        ghost="GHOST SHORT"
        pattern=f"SELL HILL LTF 5M - HTF BIAS VALLEY + BSL {prevHigh_LTF:.2f} swept LTF + HH->LH {hh_lh} -> TP Balance {balance_LTF:.2f}"
        invasion=75
    elif buy_valley_LTF:
        ghost="GHOST LONG"
        pattern=f"BUY VALLEY LTF 5M - HTF BIAS HILL + SSL {prevLow_LTF:.2f} swept LTF + LL->HL {ll_hl} WAR OVER -> TP Balance {balance_LTF:.2f}"
        invasion=75
    elif isHTF_VALLEY and isLTF_HILL and hill_exhaustion_LTF:
        ghost="WAIT"
        pattern=f"HTF VALLEY BIAS + LTF HILL HH->LH {hh_lh} READY LTF - WAITING BSL SWEEP LTF {prevHigh_LTF:.2f}"
        invasion=50
    elif isHTF_HILL and isLTF_VALLEY and valley_exhaustion_LTF:
        ghost="WAIT"
        pattern=f"HTF HILL BIAS + LTF VALLEY LL->HL {ll_hl} READY LTF - WAITING SSL SWEEP LTF {prevLow_LTF:.2f}"
        invasion=50
    else:
        ghost="WAIT"
        pattern=f"BALANCE LTF - HTF {htf_slope:.1f}% LTF {ltf_slope:.1f}% | BSL LTF {prevHigh_LTF:.2f} SSL LTF {prevLow_LTF:.2f} Balance LTF {balance_LTF:.2f}"
        invasion=0

    status={
        "invasion_pct": invasion,
        "ghost_signal": ghost,
        "fifty_level": fifty,
        "balance_price": round(balance_LTF,2),
        "bsl_liquidity": round(prevHigh_LTF,2),
        "ssl_liquidity": round(prevLow_LTF,2),
        "signal": ghost,
        "pattern": pattern,
        "htf_regime": "VALLEY LL - SELL BIAS (HTF ONLY BIAS)" if isHTF_VALLEY else "HILL HH - BUY BIAS (HTF ONLY BIAS)" if isHTF_HILL else "BALANCE",
        "ltf_breath": f"HILL HH->LH {hh_lh} LTF 5M" if isLTF_HILL else f"VALLEY LL->HL {ll_hl} LTF 5M WAR OVER" if isLTF_VALLEY else "BALANCE LTF",
        "htf_sweep": "HTF ONLY BIAS - NO SWEEP",
        "ltf_sweep": f"BSL SWEPT LTF {prevHigh_LTF:.2f}" if isBSL_Sweep_LTF else f"SSL SWEPT LTF {prevLow_LTF:.2f}" if isSSL_Sweep_LTF else f"NO SWEEP LTF - BSL {prevHigh_LTF:.2f} SSL {prevLow_LTF:.2f}",
        "hh_lh_count": hh_lh,
        "ll_hl_count": ll_hl,
        "atr_ltf": round(ltf_slope,2),
        "atr_htf": round(htf_slope,2),
        "price": xau_price,
        "xau_price": xau_price,
        "nas_price": nas_price,
        "tp_target": round(balance_LTF,2),
        "execution": "ALL LTF 5M - Sweep + Entry + TP Balance/Fifty | HTF ONLY BIAS",
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "timestamp": int(time.time()),
        "version": "V8.7 FINAL HTF BIAS ONLY LTF 5M EXECUTION",
        "logic": "HTF ONLY BIAS | LTF 5M: Sweep BSL/SSL liquidity + HH->LH/LL->HL bumps + Ride to Balance/Fifty"
    }

    with open(CLOUD_FILE,"w") as f:
        json.dump(status,f,indent=2)

    print(f"✅ {pattern}")
    print(f"   HTF BIAS ONLY: {status['htf_regime']} | LTF 5M EXECUTION: {status['ltf_breath']} | BSL LTF {prevHigh_LTF:.2f} SSL LTF {prevLow_LTF:.2f} Balance LTF {balance_LTF:.2f} | GHOST {ghost} {invasion}% | XAU {xau_price}")

if __name__=="__main__":
    main()
