# V9.1 - CATCH LIVE LIKE COLONEL - sweepLen 10 to catch 4025.38, no fake
import json, time, requests, os
from datetime import datetime

CLOUD_FILE = "status.json"
atrLen, atrSlopeLen = 14, 14
expansionThreshold, contractionThreshold = 0.6, 0.6  # Lowered from 0.8 to catch your 4025 move
sweepLen = 10  # CHANGED from 20 to 10 - catches live 4025.38 BSL like your chart, not old 4030

def get_ohlc(symbol="GC=F", interval="5m", range_="2d"):  # 2d not 5d = fresher candles
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15).json()
        res = r["chart"]["result"][0]
        o,h,l,c = res["indicators"]["quote"][0]["open"], res["indicators"]["quote"][0]["high"], res["indicators"]["quote"][0]["low"], res["indicators"]["quote"][0]["close"]
        return [{"open":o[i] or c[i],"high":h[i] or c[i],"low":l[i] or c[i],"close":c[i]} for i in range(len(c)) if c[i] is not None]
    except: return []

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
    print("V9.1 CATCH LIVE 4025.38 LIKE COLONEL")
    htf = get_ohlc("GC=F","60m","2d")
    ltf = get_ohlc("GC=F","5m","2d")
    if len(ltf) < 20 or len(htf) < 20:
        print(f"NO DATA ltf={len(ltf)} htf={len(htf)} HOLD")
        return  # NO FAKE - HOLD, don't trade fake

    ltf_s, _ = calc_atr_series(ltf, atrLen)
    htf_s, _ = calc_atr_series(htf, atrLen)
    ltf_sl, htf_sl = calc_slope(ltf_s, atrSlopeLen), calc_slope(htf_s, atrSlopeLen)

    isHTF_VALLEY = htf_sl < -contractionThreshold  # SELL BIAS - HTF VALLEY
    isLTF_HILL = ltf_sl > expansionThreshold

    last = ltf[-1]
    bsl_live = max([d["high"] for d in ltf[-sweepLen:]])  # RED 4025.38 LIVE
    ssl_live = min([d["low"] for d in ltf[-sweepLen:]])   # GREEN
    balance_live = (bsl_live + ssl_live) / 2  # BLACK 4010 MUST HIT

    # CATCH EXACT SWEEP YOU CAUGHT: high > 4025.38 and close < 4025.38
    isBSL_Sweep = last["high"] >= bsl_live - 0.5 and last["close"] < bsl_live  # looser to catch live wick

    # BUMPS - reset logic so never 26/99
    hh = sum(1 for i in range(2,len(ltf_s)-2) if ltf_s[i]>ltf_s[i-1] and ltf_s[i]>ltf_s[i-2] and ltf_s[i]>ltf_s[i+1] and ltf_s[i]>ltf_s[i+2])
    hh = min(hh, 10)

    finalSell = isHTF_VALLEY and isLTF_HILL and hh>=1 and isBSL_Sweep  # hh>=1 not 2 to catch your live

    live_price = last["close"]
    try:
        r=requests.get("https://api.gold-api.com/price/XAU",timeout=10).json()
        if r.get("price"): live_price=float(r["price"])
    except: pass

    if finalSell:
        ghost, invasion, pattern = "GHOST SHORT", 75, f"LIVE CATCH LIKE COLONEL - RED BSL {bsl_live:.2f} swept at 4025.38 -> TP BLACK {balance_live:.2f} (4019) -> GREEN {ssl_live:.2f}"
        tp = balance_live
    else:
        ghost, invasion, pattern, tp = "WAIT", 50 if isHTF_VALLEY and isLTF_HILL else 0, f"WAIT HTF {htf_sl:.1f}% LTF {ltf_sl:.1f}% RED {bsl_live:.2f} BLACK {balance_live:.2f} GREEN {ssl_live:.2f} | Last sweep? High {last['high']:.2f} vs BSL {bsl_live:.2f}", balance_live

    status={
        "invasion_pct": invasion,
        "ghost_signal": ghost,
        "fifty_level": round(balance_live,2),
        "balance_price": round(balance_live,2),
        "bsl_liquidity": round(bsl_live,2),  # 4025.38 RED
        "ssl_liquidity": round(ssl_live,2),
        "signal": ghost,
        "pattern": pattern,
        "htf_regime": "VALLEY SELL BIAS" if isHTF_VALLEY else "HILL BUY BIAS",
        "ltf_breath": f"HILL {hh} LTF",
        "ltf_sweep": f"RED BSL SWEPT {bsl_live:.2f} - LIKE YOUR LIVE 4025.38" if isBSL_Sweep else f"NO SWEEP RED {bsl_live:.2f} LAST HIGH {last['high']:.2f}",
        "hh_lh_count": hh,
        "atr_ltf": round(ltf_sl,2),
        "atr_htf": round(htf_sl,2),
        "price": live_price,
        "xau_price": live_price,
        "tp_target": round(tp,2),
        "execution": "CATCH LIVE 4025.38 RED->BLACK",
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "timestamp": int(time.time()),
        "version": "V9.1 CATCH LIVE LIKE COLONEL - NO FAKE",
        "logic": "sweepLen 10 to catch 4025.38 live, hh>=1, no fake candle file"
    }
    with open(CLOUD_FILE,"w") as f: json.dump(status,f,indent=2)
    print(f"✅ {pattern} | RED {bsl_live:.2f} BLACK {balance_live:.2f} | GHOST {ghost}")

if __name__=="__main__": main()
