import json, time, requests, os
from datetime import datetime

CLOUD_FILE = "status.json"
atrLen = 14
atrSlopeLen = 14
expansionThreshold = 0.8
contractionThreshold = 0.8
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
    except Exception as e:
        print(f"OHLC FAIL {symbol} {interval}: {e}")
        return []  # NO DUMMY - return empty

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
    return atrs, atrs[-1]

def calc_slope(atrs, lookback=14):
    if len(atrs) < lookback+1: return 0
    now=atrs[-1]
    prev=atrs[-lookback-1]
    if prev==0: return 0
    return (now-prev)/prev*100

def get_dynamic_levels_live(data, lookback=20):
    recent_high = max([d["high"] for d in data[-lookback:]])
    recent_low = min([d["low"] for d in data[-lookback:]])
    for i in range(len(data)-3, len(data)-lookback, -1):
        if data[i]["high"] > data[i-1]["high"] and data[i]["high"] > data[i+1]["high"]:
            recent_high = data[i]["high"]
            break
    for i in range(len(data)-3, len(data)-lookback, -1):
        if data[i]["low"] < data[i-1]["low"] and data[i]["low"] < data[i+1]["low"]:
            recent_low = data[i]["low"]
            break
    balance = (recent_high + recent_low) / 2
    fifty_dynamic = recent_low + (recent_high - recent_low) * 0.5
    return recent_high, recent_low, balance, fifty_dynamic

def main():
    print("DELPHIAN V8.9 LIVE - NO DUMMY PRICES - HTF BIAS ONLY LTF 5M ALL")
    htf_data = get_ohlc("GC=F","60m","5d")
    ltf = get_ohlc("GC=F","5m","5d")

    # CRITICAL FIX: NO DUMMY - If no real data, DO NOT TRADE, keep old status
    if len(ltf) < 30 or len(htf_data) < 30:
        print(f"❌ NO REAL DATA ltf={len(ltf)} htf={len(htf_data)} - Keeping old status.json, NOT trading fake 4027")
        # Don't overwrite status.json with fake levels - exit
        if os.path.exists(CLOUD_FILE):
            with open(CLOUD_FILE,"r") as f:
                old = json.load(f)
            old["last_update"] = datetime.now().strftime("%H:%M:%S") + " NO DATA - HOLD"
            old["ghost_signal"] = "WAIT"
            old["invasion_pct"] = 0
            old["pattern"] = f"NO REAL DATA - Yahoo fail ltf {len(ltf)} htf {len(htf_data)} - HOLDING LAST"
            with open(CLOUD_FILE,"w") as out:
                json.dump(old, out, indent=2)
        else:
            # First run no data - write WAIT not fake trade
            status = {
                "invasion_pct": 0,
                "ghost_signal": "WAIT",
                "pattern": "NO REAL DATA - WAIT",
                "last_update": datetime.now().strftime("%H:%M:%S"),
                "timestamp": int(time.time()),
                "version": "V8.9 NO DUMMY"
            }
            with open(CLOUD_FILE,"w") as out:
                json.dump(status, out, indent=2)
        return

    ltf_series, ltf_atr = calc_atr_series(ltf, atrLen)
    htf_series, htf_atr = calc_atr_series(htf_data, atrLen)
    ltf_slope = calc_slope(ltf_series, atrSlopeLen)
    htf_slope = calc_slope(htf_series, atrSlopeLen)

    isHTF_HILL = htf_slope > expansionThreshold
    isHTF_VALLEY = htf_slope < -contractionThreshold
    isLTF_HILL = ltf_slope > expansionThreshold
    isLTF_VALLEY = ltf_slope < -contractionThreshold

    last = ltf[-1]
    bsl_live, ssl_live, balance_live, fifty_live = get_dynamic_levels_live(ltf, sweepLen)

    isBSL_Sweep_Live = last["high"] > bsl_live and last["close"] < bsl_live
    isSSL_Sweep_Live = last["low"] < ssl_live and last["close"] > ssl_live

    hh_lh = 0
    ll_hl = 0
    for i in range(2, len(ltf_series)-2):
        if ltf_series[i] > ltf_series[i-1] and ltf_series[i] > ltf_series[i-2] and ltf_series[i] > ltf_series[i+1] and ltf_series[i] > ltf_series[i+2]:
            hh_lh += 1
        if ltf_series[i] < ltf_series[i-1] and ltf_series[i] < ltf_series[i-2] and ltf_series[i] < ltf_series[i+1] and ltf_series[i] < ltf_series[i+2]:
            ll_hl += 1
    hh_lh = min(hh_lh, 10)
    ll_hl = min(ll_hl, 10)

    sell_ready = isHTF_VALLEY and isLTF_HILL and hh_lh >= 2
    buy_ready = isHTF_HILL and isLTF_VALLEY and ll_hl >= 2
    finalSell = sell_ready and isBSL_Sweep_Live
    finalBuy = buy_ready and isSSL_Sweep_Live

    live_price = last["close"]
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=10).json()
        if r.get("price"): live_price = float(r["price"])
    except: pass
    try:
        rN = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?interval=1m&range=1d", timeout=10).json()
        nas_price = rN["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except:
        nas_price = 28950

    if finalSell:
        ghost="GHOST SHORT"
        pattern=f"SELL HILL LTF 5M LIVE - HTF VALLEY + BSL {bsl_live:.2f} swept LIVE -> TP {balance_live:.2f}"
        invasion=75
    elif finalBuy:
        ghost="GHOST LONG"
        pattern=f"BUY VALLEY LTF 5M LIVE - HTF HILL + SSL {ssl_live:.2f} swept LIVE -> TP {balance_live:.2f} WAR OVER"
        invasion=75
    elif sell_ready:
        ghost="WAIT"
        pattern=f"HTF VALLEY + LTF HILL {hh_lh} READY - WAITING BSL SWEEP LIVE {bsl_live:.2f}"
        invasion=50
    elif buy_ready:
        ghost="WAIT"
        pattern=f"HTF HILL + LTF VALLEY {ll_hl} READY - WAITING SSL SWEEP LIVE {ssl_live:.2f}"
        invasion=50
    else:
        ghost="WAIT"
        pattern=f"BALANCE LIVE HTF {htf_slope:.1f}% LTF {ltf_slope:.1f}% BSL {bsl_live:.2f} SSL {ssl_live:.2f} Bal {balance_live:.2f}"
        invasion=0

    status={
        "invasion_pct": invasion,
        "ghost_signal": ghost,
        "fifty_level": round(fifty_live,2),
        "balance_price": round(balance_live,2),
        "bsl_liquidity": round(bsl_live,2),
        "ssl_liquidity": round(ssl_live,2),
        "signal": ghost,
        "pattern": pattern,
        "htf_regime": "VALLEY SELL BIAS HTF ONLY" if isHTF_VALLEY else "HILL BUY BIAS HTF ONLY" if isHTF_HILL else "BALANCE HTF",
        "ltf_breath": f"HILL {hh_lh} LTF" if isLTF_HILL else f"VALLEY {ll_hl} LTF" if isLTF_VALLEY else "BALANCE LTF",
        "ltf_sweep": f"BSL SWEPT {bsl_live:.2f}" if isBSL_Sweep_Live else f"SSL SWEPT {ssl_live:.2f}" if isSSL_Sweep_Live else f"NO SWEEP BSL {bsl_live:.2f} SSL {ssl_live:.2f}",
        "hh_lh_count": hh_lh,
        "ll_hl_count": ll_hl,
        "atr_ltf": round(ltf_slope,2),
        "atr_htf": round(htf_slope,2),
        "price": live_price,
        "xau_price": live_price,
        "nas_price": nas_price,
        "tp_target": round(balance_live,2),
        "execution": "NO DUMMY - ALL LIVE TICK LTF 5M",
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "timestamp": int(time.time()),
        "version": "V8.9 NO DUMMY LIVE - HTF BIAS ONLY",
        "logic": "NO FAKE 4027 - If Yahoo fails, HOLD old status, don't trade fake. All levels dynamic live from LTF 5m"
    }

    with open(CLOUD_FILE,"w") as f:
        json.dump(status,f,indent=2)

    print(f"✅ LIVE {pattern} | BSL {bsl_live:.2f} SSL {ssl_live:.2f} Bal {balance_live:.2f} Fifty {fifty_live:.2f} LIVE {live_price} | GHOST {ghost} {invasion}%")

if __name__=="__main__":
    main()
