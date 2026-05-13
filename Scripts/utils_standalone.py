"""
scripts/utils_standalone.py
==============================
Standalone version of screener utilities for GitHub Actions.
No Streamlit dependency.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

SMA_WEEKS          = 50
RS_MA_WEEKS        = 10
SMA_SLOPE_LOOKBACK = 10
BREAKOUT_LOOKBACK  = 52
MAX_ABOVE_SMA      = 0.30
RECENT_CROSS_WEEKS = 8
VOLUME_AVG_WEEKS   = 26
VOLUME_BREAKOUT    = 1.5
SLOPE_THRESHOLD    = 0.0005
YEARS              = 4
BENCHMARK          = "SPY"

SECTORS = {
    "XLK":"Technology","XLF":"Financials","XLE":"Energy",
    "XLV":"Health Care","XLI":"Industrials","XLY":"Consumer Discret.",
    "XLP":"Consumer Staples","XLU":"Utilities","XLRE":"Real Estate",
    "XLB":"Materials","XLC":"Comm. Services",
    "SMH":"Semiconductors","HACK":"Cybersecurity","ARKK":"Innovation/ARK",
    "BOTZ":"Robotics & AI","FINX":"Fintech","XBI":"Biotech",
    "IHI":"Medical Devices","XOP":"Oil & Gas E&P","GDX":"Gold Miners",
    "COPX":"Copper Miners","LIT":"Lithium/Battery","TAN":"Solar Energy",
    "ICLN":"Clean Energy","ITB":"Homebuilders","PAVE":"Infrastructure",
    "UFO":"Space","DRIV":"EV & Autonomy","JETS":"Airlines","MOO":"Agribusiness",
}

SECTOR_STOCKS = {
    "XLK":  ["AAPL","NVDA","MSFT","AVGO","ORCL","CRM","AMD","ACN","ADBE","CSCO",
              "NOW","PANW","FTNT","SNPS","CDNS","AMAT","KLAC","LRCX","MU","TXN",
              "QCOM","ANET","MCHP","ADI","MRVL","ON","ZS","NET","DDOG","MDB","SNOW","PLTR","CRWD"],
    "XLF":  ["BRK-B","JPM","V","MA","BAC","GS","MS","WFC","SPGI","BLK",
              "AXP","C","USB","PNC","TFC","COF","CME","ICE","MMC","AON","MET"],
    "XLE":  ["XOM","CVX","COP","EOG","SLB","MPC","PSX","OXY","VLO","WMB",
              "KMI","OKE","BKR","DVN","HAL","CTRA","EQT","AR","MTDR","TPL"],
    "XLV":  ["LLY","UNH","JNJ","ABBV","MRK","TMO","ABT","DHR","PFE","AMGN",
              "ISRG","BMY","ELV","MDT","GILD","CVS","REGN","VRTX","BSX","CI","HCA","ZTS"],
    "XLI":  ["GE","RTX","CAT","HON","UPS","DE","BA","LMT","ETN",
              "NOC","GD","EMR","PH","ITW","CSX","NSC","UNP","FDX","WM","AME"],
    "XLY":  ["AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","BKNG","CMG",
              "ABNB","MAR","GM","ORLY","AZO","ROST","YUM","RCL","LULU","DECK"],
    "XLP":  ["PG","COST","KO","PEP","WMT","PM","MDLZ","CL","GIS",
              "KMB","KR","KDP","HSY","CHD","MNST","TGT"],
    "XLU":  ["NEE","SO","DUK","AEP","SRE","D","EXC","XEL","PEG","ED","VST","CEG"],
    "XLRE": ["PLD","AMT","EQIX","WELL","SPG","O","DLR","CCI","VICI","AVB","EQR","MAA"],
    "XLB":  ["LIN","SHW","FCX","ECL","APD","NEM","DD","DOW","NUE","STLD","VMC","MLM","CF","MOS"],
    "XLC":  ["META","GOOGL","NFLX","TMUS","DIS","VZ","T","CMCSA","EA","TTD","PINS","SNAP"],
    "SMH":  ["NVDA","TSM","AVGO","AMD","ASML","TXN","QCOM","MU","AMAT","LRCX",
              "KLAC","ADI","MCHP","ON","MRVL","NXPI","ARM","INTC","WOLF"],
    "HACK": ["CRWD","PANW","ZS","FTNT","OKTA","NET","S","TENB","CYBR","QLYS","VRNS"],
    "ARKK": ["TSLA","ROKU","COIN","SQ","SHOP","ZM","BEAM","CRSP","RXRX","PLTR","PATH","U"],
    "BOTZ": ["ISRG","ABB","NVDA","ZBRA","TER","NXPI","AZTA","BRKS","ONTO","CGNX","PTC"],
    "XBI":  ["MRNA","VRTX","REGN","BIIB","ALNY","BMRN","ARWR","CRSP","BEAM","SRPT","EXEL"],
    "IHI":  ["ISRG","MDT","BSX","EW","SYK","BDX","ZBH","HOLX","INSP","NARI","SWAV","DXCM"],
    "XOP":  ["XOM","CVX","COP","EOG","OXY","DVN","MRO","APA","AR","EQT","MTDR","CTRA"],
    "GDX":  ["NEM","GOLD","AEM","AGI","KGC","WPM","FNV","RGLD","EGO","PAAS","MAG","AG"],
    "COPX": ["FCX","SCCO","HBM","TECK","RIO","BHP","ERO","MP"],
    "LIT":  ["ALB","SQM","LTHM","LAC","PLL","SGML","ENVX","SLDP","QS","STEM"],
    "TAN":  ["FSLR","ENPH","RUN","NOVA","ARRY","CSIQ","SEDG","SPWR","JKS","SHLS"],
    "ICLN": ["NEE","BEP","BEPC","AES","CWEN","FSLR","ENPH","RUN","PLUG","STEM","BE"],
    "ITB":  ["DHI","LEN","TOL","PHM","NVR","MDC","TMHC","MTH","HD","LOW","SHW","BLDR"],
    "PAVE": ["PWR","MTZ","STRL","ROAD","MYR","APG","TTEK","ACM","KBR","GVA","AGX","PRIM"],
    "UFO":  ["RKLB","ASTS","KTOS","BWXT","BA","NOC","RTX","JOBY","ACHR","LMT"],
    "DRIV": ["TSLA","NIO","LI","XPEV","RIVN","LCID","APTV","LEA","BWA","ALB","ON","NXPI"],
    "JETS": ["UAL","DAL","AAL","LUV","JBLU","ALK","ULCC","BA"],
    "MOO":  ["DE","ADM","BG","MOS","CF","CTVA","FMC","NTR","AGCO","INGR"],
    "FINX": ["SQ","AFRM","UPST","PYPL","COIN","HOOD","LC","SOFI","GPN","FIS","FISV"],
}


def fetch_weekly_raw(ticker: str, years: int = YEARS) -> pd.DataFrame:
    end = datetime.today(); start = end - timedelta(weeks=years*52+10)
    for attempt in range(4):
        try:
            if attempt > 0: time.sleep(3*attempt)
            t  = yf.Ticker(ticker)
            df = t.history(start=start, end=end, interval="1wk", auto_adjust=True)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df.dropna()
        except Exception as e:
            print(f"  Attempt {attempt+1} failed for {ticker}: {e}")
    return pd.DataFrame()


def _clean_index(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.to_datetime(s.index)
    try: s.index = s.index.tz_localize(None)
    except:
        try: s.index = s.index.tz_convert(None)
        except: pass
    s.index = s.index.normalize()
    return s


def evaluate(df: pd.DataFrame, spx_close: pd.Series) -> dict:
    r = dict(price=None,sma50w=None,pct_above=None,
             above_sma=False,sma_rising=False,rs_up=False,
             near_high=False,not_extended=False,
             rs=None,stage="Unknown",cross=-1,early=False,
             vol=None,vol_ok=False,base_w=0,base_q="Short",
             stop=None,risk=None,score=0,label="Not Stage 2",
             early_sig=False,premium=False)

    if df.empty or len(df) < SMA_WEEKS+5: return r

    close = df["Close"]; volume = df.get("Volume", pd.Series(dtype=float))
    ma50  = close.rolling(SMA_WEEKS).mean()
    cp, cm = float(close.iloc[-1]), float(ma50.iloc[-1])
    if pd.isna(cm): return r

    r["price"] = round(cp,2); r["sma50w"] = round(cm,2)
    pct = (cp/cm)-1; r["pct_above"] = round(pct*100,1)

    v = ma50.dropna().iloc[-SMA_SLOPE_LOOKBACK:]
    slope = np.nan
    if len(v) >= SMA_SLOPE_LOOKBACK:
        sl, _ = np.polyfit(np.arange(len(v)), v.values, 1)
        slope = sl / (abs(v.iloc[-1]) or 1)

    r["above_sma"]  = cp > cm
    r["sma_rising"] = not pd.isna(slope) and slope > SLOPE_THRESHOLD

    # RS
    try:
        a = _clean_index(close); b = _clean_index(spx_close)
        c = pd.concat([a,b],axis=1).dropna()
        if not c.empty and c.shape[1] == 2:
            rs = c.iloc[:,0]/c.iloc[:,1]
            if len(rs) >= RS_MA_WEEKS+5:
                rm = rs.rolling(RS_MA_WEEKS).mean()
                if not pd.isna(rm.iloc[-1]) and rm.iloc[-1] > 0:
                    sc = round(((rs.iloc[-1]/rm.iloc[-1]-1)+(rs.iloc[-1]/rs.iloc[-(RS_MA_WEEKS+1)]-1))*100,2)
                    r["rs"] = sc; r["rs_up"] = sc > 0
    except Exception: pass

    wh = float(close.iloc[-BREAKOUT_LOOKBACK:].max())
    r["near_high"]    = (cp/wh)-1 >= -0.15
    r["not_extended"] = 0 < pct < MAX_ABOVE_SMA

    if r["above_sma"] and r["sma_rising"]:       r["stage"] = "Stage 2"
    elif r["above_sma"] and not r["sma_rising"]:  r["stage"] = "Stage 3"
    elif not r["above_sma"] and not r["sma_rising"]:r["stage"] = "Stage 4"
    else:                                          r["stage"] = "Stage 1"

    # Cross
    c2 = pd.concat([_clean_index(close), _clean_index(ma50)], axis=1).dropna().iloc[-(RECENT_CROSS_WEEKS+5):]
    above = (c2.iloc[:,0] > c2.iloc[:,1]).values
    cross = -1
    for i in range(len(above)-1,0,-1):
        if above[i] and not above[i-1]:
            w = len(above)-1-i
            cross = w if w <= RECENT_CROSS_WEEKS else -1; break
    r["cross"] = cross; r["early"] = 0 <= cross <= RECENT_CROSS_WEEKS

    # Volume
    if not volume.empty and len(volume) >= VOLUME_AVG_WEEKS+5:
        if cross >= 0:
            idx = len(volume)-1-cross
            if idx >= VOLUME_AVG_WEEKS:
                bv = float(volume.iloc[idx])
                bl = float(volume.iloc[idx-VOLUME_AVG_WEEKS:idx].mean())
                r["vol"] = round(bv/bl,2) if bl > 0 else None
        if r["vol"] is None:
            bl = float(volume.iloc[-(VOLUME_AVG_WEEKS+4):-4].mean())
            rc = float(volume.iloc[-4:].mean())
            r["vol"] = round(rc/bl,2) if bl > 0 else None
    r["vol_ok"] = r["vol"] is not None and r["vol"] >= VOLUME_BREAKOUT

    # Base
    bx = len(close)-1-cross if cross >= 0 else len(close)-1
    bp = float(close.iloc[bx]) if bx < len(close) else float(close.iloc[-1])
    bd = 0
    for i in range(bx-1, max(0,bx-120),-1):
        if float(close.iloc[i]) >= bp*0.92: bd += 1
        else: break
    r["base_w"] = bd
    r["base_q"] = "V.Long" if bd>=80 else "Long" if bd>=40 else "Medium" if bd>=15 else "Short"

    # Stop
    sl = float(close.iloc[-8:].min())
    cands = [v2 for v2 in [cm, sl] if v2 < cp and not pd.isna(v2)]
    if cands:
        stop = max(cands)
        r["stop"] = round(stop,2); r["risk"] = round((stop/cp-1)*100,1)

    r["score"] = sum([r["above_sma"],r["sma_rising"],r["rs_up"],r["near_high"],r["not_extended"]])
    r["label"] = {5:"STRONG Stage 2",4:"Stage 2",3:"Borderline"}.get(r["score"],"Not Stage 2")
    r["early_sig"] = r["early"] and r["sma_rising"] and r["rs_up"] and r["vol_ok"]
    r["premium"]   = r["early_sig"] and bd >= 40
    return r
