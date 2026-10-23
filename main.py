import json, time, requests, os
from datetime import datetime

CLOUD_FILE = "status.json"
atrLen, atrSlopeLen = 14, 14
expansionThreshold = 1.0
contractionThreshold = 1.0
sweepLen = 10

def get_ohlc(symbol="GC=F", interval="5m", range_="2d"):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        res = r["chart"]["result"][0]
        o,h,l,c = res["indicators"]["quote"][0]["open"], res["indicators"]["quote"][0]["high"], res["indicators"]["quote"][0]["low"], res["indicators"]["quote"][0]["close"]
        return [{"open":o[i] or c[i],"high":h[i] or c[i],"low":l[i] or c[i],"close":c[i]} for i in range(len(c)) if c[i] is not None]
    except Exception as e:
        print(f"OHLC FAIL {symbol}: {e}")
        return []

def calc_atr_series(data, length=14):
    if len(data) < length+2: return [1.5], 1.5
    trs = [max(data[i]["high"]-data[i]["low"], abs(data[i]["high"]-data[i-1]["close"]), abs(data[i]["low"]-data[i-1]["close"])) for i in range(1,len(data))]
    atrs, atr = [], sum(trs[:length])/length
    atrs.append(atr)
    for tr in trs[length:]:
        atr=(atr*(length-1)+tr)/length
        atrs.append(atr)
    return atrs, atrs[-1]

def calc_slope(atrs, lookback=14):
    return 0 if len(atrs) < lookback+1 or atrs[-lookback-1]==0 else (atrs[-1]-atrs[-lookback-1])/atrs[-lookback-1]*100

def main():
    print("V9.4 BOSS SWEEP FIXED - PREVIOUS BSL/SSL")
    htf = get_ohlc("GC=F","60m","2d")
    ltf = get_ohlc("GC=F","5m","2d")
    htf_nas = get_ohlc("NQ=F","60m","2d")
    ltf_nas = get_ohlc("NQ=F","5m","2d")

    if len(ltf) < sweepLen+5 or len(htf) < 20:
        print(f"NO DATA ltf={len(ltf)} HOLD")
        return

    ltf_s, _ = calc_atr_series(ltf, atrLen)
    htf_s, _ = calc_atr_series(htf, atrLen)
    ltf_sl, htf_sl = calc_slope(ltf_s, atrSlopeLen), calc_slope(htf_s, atrSlopeLen)

    isHTF_HILL = htf_sl > 1.0
    isHTF_VALLEY = htf_sl < -1.0
    isLTF_HILL = ltf_sl > 0.8
    isLTF_VALLEY = ltf_sl < -0.8

    last = ltf[-1]
    prev_candles = ltf[-sweepLen-1:-1]  # FIX: PREVIOUS 10, not including current
    bsl_live = max([d["high"] for d in prev_candles])
    ssl_live = min([d["low"] for d in prev_candles])
    balance_live = (bsl_live + ssl_live) / 2

    isBSL_Sweep = last["high"] > bsl_live and last["close"] < bsl_live
    isSSL_Sweep = last["low"] < ssl_live and last["close"] > ssl_live

    hh = sum(1 for i in range(2,len(ltf_s)-2) if ltf_s[i]>ltf_s[i-1] and ltf_s[i]>ltf_s[i-2] and ltf_s[i]>ltf_s[i+1] and ltf_s[i]>ltf_s[i+2])
    ll = sum(1 for i in range(2,len(ltf_s)-2) if ltf_s[i]<ltf_s[i-1] and ltf_s[i]<ltf_s[i-2] and ltf_s[i]<ltf_s[i+1] and ltf_s[i]<ltf_s[i+2])
    hh, ll = min(hh,10), min(ll,10)

    finalSell = isHTF_VALLEY and isLTF_HILL and hh>=1 and isBSL_Sweep
    finalBuy = isHTF_HILL and isLTF_VALLEY and ll>=1 and isSSL_Sweep

    xau_live = last["close"]
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=10).json()
        if r.get("price"): xau_live=float(r["price"])
    except: pass

    nas_live = ltf_nas[-1]["close"] if ltf_nas and len(ltf_nas)>0 else None
    if not nas_live:
        try:
            rN=requests.get("https://query1.finance.yahoo.com/v8/finance/chart/NQ=F?interval=1m&range=1d",timeout=10).json()
            nas_live = rN["chart"]["result"][0]["meta"]["regularMarketPrice"]
        except: pass
    if not nas_live and os.path.exists(CLOUD_FILE):
        try:
            with open(CLOUD_FILE,"r") as f: nas_live = json.load(f).get("nas_price")
        except: pass

    if finalSell:
        ghost, invasion, pattern, tp = "GHOST SHORT", 75, f"BOSS SELL: HTF VALLEY {htf_sl:.2f}% (<-1.0%) + LTF HILL {ltf_sl:.1f}% MISALIGN + RED BSL SWEEP {bsl_live:.2f} -> TP BLACK {balance_live:.2f}", balance_live
    elif finalBuy:
        ghost, invasion, pattern, tp = "GHOST LONG", 75, f"BOSS BUY: HTF HILL {htf_sl:.2f}% (>+1.0%) + LTF VALLEY {ltf_sl:.1f}% MISALIGN + GREEN SSL SWEEP {ssl_live:.2f} -> TP BLACK {balance_live:.2f} WAR OVER", balance_live
    else:
        if isHTF_VALLEY and isLTF_HILL:
            ghost, invasion, pattern = "WAIT", 50, f"HTF VALLEY SELL BIAS {htf_sl:.2f}% + LTF HILL {hh} MISALIGN - HUNTING RED BSL SWEEP {bsl_live:.2f} NOT BLACK {balance_live:.2f}"
        elif isHTF_HILL and isLTF_VALLEY:
            ghost, invasion, pattern = "WAIT", 50, f"HTF HILL BUY BIAS {htf_sl:.2f}% + LTF VALLEY {ll} MISALIGN - HUNTING GREEN SSL SWEEP {ssl_live:.2f} NOT BLACK {balance_live:.2f}"
        else:
            ghost, invasion, pattern = "WAIT", 0, f"BALANCE RANDOM HTF {htf_sl:.2f}% LTF {ltf_sl:.1f}% - WAIT FOR +-1.0% THEN HUNT RED {bsl_live:.2f} GREEN {ssl_live:.2f} BLACK TP {balance_live:.2f}"
        tp = balance_live

    status={
        "invasion_pct": invasion,
        "ghost_signal": ghost,
        "fifty_level": round(balance_live,2),
        "balance_price": round(balance_live,2),
        "bsl_liquidity": round(bsl_live,2),
        "ssl_liquidity": round(ssl_live,2),
        "signal": ghost,
        "pattern": pattern,
        "htf_regime": "VALLEY SELL - HUNT RED BSL" if isHTF_VALLEY else "HILL BUY - HUNT GREEN SSL" if isHTF_HILL else f"BALANCE WAIT 1.0% HTF {htf_sl:.2f}%",
        "ltf_breath": f"HILL {hh} MISALIGN" if isLTF_HILL else f"VALLEY {ll} MISALIGN" if isLTF_VALLEY else "BALANCE",
        "ltf_sweep": f"RED BSL SWEPT {bsl_live:.2f} FOR SELL" if isBSL_Sweep else f"GREEN SSL SWEPT {ssl_live:.2f} FOR BUY" if isSSL_Sweep else f"HUNTING SWEEP RED {bsl_live:.2f} GREEN {ssl_live:.2f} NOT 50% {balance_live:.2f}",
        "hh_lh_count": hh, "ll_hl_count": ll,
        "atr_ltf": round(ltf_sl,2), "atr_htf": round(htf_sl,2),
        "price": xau_live,
        "xau_price": xau_live,
        "nas_price": nas_live,
        "nas_live_src": "NQ=F LIVE" if ltf_nas else "HOLD",
        "tp_target": round(tp,2),
        "execution": "BOSS HUNT PREVIOUS SWEEP - RED FOR SELL, GREEN FOR BUY, BLACK IS TP",
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "timestamp": int(time.time()),
        "version": "V9.4 FIXED PREVIOUS BSL/SSL + NAS LIVE",
        "logic": "FIXED: bsl/ssl from previous 10, current must sweep previous. HTF +-1.0% boss, NAS live NQ=F"
    }
    with open(CLOUD_FILE,"w") as f: json.dump(status,f,indent=2)
    print(f"✅ {pattern} | XAU {xau_live} NAS {nas_live} | {ghost}")

if __name__=="__main__": main()
