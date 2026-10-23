import json, time, requests
from datetime import datetime

CLOUD_FILE = "status.json"
atrLen = 14
atrSlopeLen = 14
expansionThreshold = 0.8
contractionThreshold = 0.8
wickPercent = 80
sweepLen = 20
sweepAtrMult = 0.2

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

def calc_atr(data, length=14):
    if len(data) < length+1: return 1.5, []
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
    return atrs[-1] if atrs else 1.5, atrs

def calc_slope(atrs, lookback=14):
    if len(atrs) < lookback+1: return 0
    now=atrs[-1]
    prev=atrs[-lookback-1]
    if prev==0: return 0
    return (now-prev)/prev*100

def detect_sweeps(ltf_data, htf_high, htf_low, atr):
    if not ltf_data: return False, False
    last=ltf_data[-1]
    isBSL = last["high"] > htf_high + atr*0.2 and last["close"] < htf_high
    isSSL = last["low"] < htf_low - atr*0.2 and last["close"] > htf_low
    return isBSL, isSSL

def main():
    print("DELPHIAN V8.4 CORRECTED - SELL HILL / BUY VALLEY (INVERTED FIX)")
    ltf = get_ohlc("GC=F","5m","5d")
    htf_data = get_ohlc("GC=F","60m","5d")
    if not ltf or not htf_data:
        ltf=[{"open":4027,"high":4030,"low":4025,"close":4027}]*50
        htf_data=[{"open":4027,"high":4050,"low":4000,"close":4027}]*50

    ltf_atr, ltf_series = calc_atr(ltf, atrLen)
    htf_atr, htf_series = calc_atr(htf_data, atrLen)
    ltf_slope = calc_slope(ltf_series, atrSlopeLen)
    htf_slope = calc_slope(htf_series, atrSlopeLen)

    isHTF_Expansion = htf_slope > expansionThreshold  # HTF HILL - BULL
    isHTF_Contraction = htf_slope < -contractionThreshold  # HTF VALLEY - BEAR/BASE
    isLTF_ExpansionHill = ltf_slope > expansionThreshold  # LTF HILL
    isLTF_ContractionValley = ltf_slope < -contractionThreshold  # LTF VALLEY

    htf_high = max([d["high"] for d in htf_data[-sweepLen:]])
    htf_low = min([d["low"] for d in htf_data[-sweepLen:]])
    isBSL_Now, isSSL_Now = detect_sweeps(ltf, htf_high, htf_low, ltf_atr)

    # Bump Law - Higher High -> Lower High (Hill exhaustion) | Lower Low -> Higher Low (Valley exhaustion)
    hh_lh = 0
    ll_hl = 0
    for i in range(1, len(ltf_series)-3):
        if ltf_series[i] > ltf_series[i-1] and ltf_series[i] > ltf_series[i+1]:
            hh_lh += 1
        if ltf_series[i] < ltf_series[i-1] and ltf_series[i] < ltf_series[i+1]:
            ll_hl += 1
    hh_lh = min(hh_lh,5)
    ll_hl = min(ll_hl,5)

    # === CORRECTED LOGIC PER YOUR NOTE ===
    
    # SELL FROM HILL: HTF VALLEY (Contraction LL) + LTF HILL (Expansion HH+LH bumps)
    # ATR: Higher High -> Lower High (second bump LH) = exhaustion of LTF up move
    # Mean reversion short aligns with 1H Valley bias
    hill_exhaustion = hh_lh >= 2  # HH then LH
    sell_hill_condition = isHTF_Contraction and isLTF_ExpansionHill and hill_exhaustion

    # BUY FROM VALLEY: HTF HILL (Expansion HH) + LTF VALLEY (Contraction LL+HL bumps)
    # ATR: Lower Low -> Higher Low (second bump HL) = exhaustion down, trend resuming, war over, HTF regains
    valley_exhaustion = ll_hl >= 2  # LL then HL
    buy_valley_condition = isHTF_Expansion and isLTF_ContractionValley and valley_exhaustion

    lowestLow = min([d["low"] for d in ltf[-20:]])
    highestHigh = max([d["high"] for d in ltf[-20:]])
    last = ltf[-1]
    body = abs(last["close"]-last["open"])
    upperWick = last["high"] - max(last["open"], last["close"])
    lowerWick = min(last["open"], last["close"]) - last["low"]
    isFreshValley = last["low"] == lowestLow and lowerWick > body*(wickPercent/100) and isLTF_ContractionValley
    isStaleHill = last["high"] == highestHigh and upperWick > body*(wickPercent/100) and isLTF_ExpansionHill

    ny = datetime.now().hour >= 9  # simplified NY filter

    # FINAL - CORRECTED
    finalSell = sell_hill_condition and isStaleHill and isBSL_Now and ny  # Sell from Hill top
    finalBuy = buy_valley_condition and isFreshValley and isSSL_Now and ny  # Buy from Valley bottom

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

    if finalSell:
        ghost="GHOST SHORT"
        pattern="SELL FROM HILL - HTF VALLEY + LTF HILL EXHAUSTION HH->LH"
        invasion=75 if hh_lh>=2 else 50
    elif finalBuy:
        ghost="GHOST LONG"
        pattern="BUY FROM VALLEY - HTF HILL + LTF VALLEY EXHAUSTION LL->HL WAR OVER"
        invasion=75 if ll_hl>=2 else 50
    else:
        ghost="WAIT"
        if sell_hill_condition and not isBSL_Now:
            pattern=f"HTF VALLEY + LTF HILL READY - WAITING BSL SWEEP | HH_LH {hh_lh}"
            invasion=25
        elif buy_valley_condition and not isSSL_Now:
            pattern=f"HTF HILL + LTF VALLEY READY - WAITING SSL SWEEP | LL_HL {ll_hl}"
            invasion=25
        else:
            pattern="BALANCE - NO HTF/LTF MISALIGNMENT"
            invasion=0

    status={
        "invasion_pct": invasion,
        "ghost_signal": ghost,
        "fifty_level": fifty,
        "signal": ghost,
        "pattern": pattern,
        "htf_regime": "VALLEY CONTRACTION LL - SELL BIAS" if isHTF_Contraction else "HILL EXPANSION HH - BUY BIAS" if isHTF_Expansion else "BALANCE",
        "ltf_breath": "HILL EXPANSION - EXHAUSTION SHORT SETUP" if isLTF_ExpansionHill else "VALLEY CONTRACTION - EXHAUSTION LONG SETUP" if isLTF_ContractionValley else "BALANCE",
        "htf_sweep": "BSL SWEPT - SELL READY" if isBSL_Now else "SSL SWEPT - BUY READY" if isSSL_Now else "NO SWEEP",
        "hh_lh_count": hh_lh,
        "ll_hl_count": ll_hl,
        "atr_ltf": round(ltf_slope,2),
        "atr_htf": round(htf_slope,2),
        "price": xau_price,
        "xau_price": xau_price,
        "nas_price": nas_price,
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "timestamp": int(time.time()),
        "version": "V8.4 CORRECTED SELL HILL / BUY VALLEY",
        "logic": "SELL: HTF VALLEY + LTF HILL HH->LH exhaustion | BUY: HTF HILL + LTF VALLEY LL->HL war over"
    }

    with open(CLOUD_FILE,"w") as f:
        json.dump(status,f,indent=2)

    print(f"✅ {pattern}")
    print(f"   GHOST: {ghost} {invasion}% | {status['htf_regime']} | {status['ltf_breath']} | Bumps HH_LH {hh_lh} LL_HL {ll_hl} | XAU {xau_price}")
    print(json.dumps(status,indent=2))

if __name__=="__main__":
    main()
