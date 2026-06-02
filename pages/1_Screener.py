"""
pages/1_Sectors.py — Comprehensive Weinstein Screener
=======================================================
Merged: Sectors + Industries + Signals + Stage 1 Watchlist
"""

import streamlit as st
from io import StringIO
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import json
from datetime import datetime, timedelta

from utils.theme import page_config, inject_css, get_colors
from utils.screener import (
    get_spx_data, scan_tickers, scan_batch, fetch_weekly,
    scan_tickers_daily, get_spx_daily, fetch_daily_data, evaluate_daily,
    SECTORS, SECTOR_STOCKS, fmt, rs_tag, sig_icon, signal_card_html,
    export_tv, export_tv_lines, fetch_nyse_tickers
)
from utils.db import add_to_watchlist

def compute_rrg_inline(tickers, years=2):
    end = datetime.today(); start = end - timedelta(weeks=years*52+20)
    all_tks = list(set(tickers + ["SPY"]))
    try:
        raw = yf.download(all_tks, start=start, end=end, interval="1wk",
                          auto_adjust=True, progress=False, threads=False)["Close"]
        if isinstance(raw, pd.Series): raw = raw.to_frame(all_tks[0])
        raw = raw.ffill().dropna(how="all")
    except: return []
    if "SPY" not in raw.columns or len(raw) < 20: return []
    spy = raw["SPY"].copy()
    results = []
    for tk in tickers:
        if tk not in raw.columns: continue
        try:
            df2 = pd.concat([raw[tk], spy], axis=1).dropna()
            if len(df2) < 20: continue
            rs_raw = (df2.iloc[:,0] / df2.iloc[:,1]) * 100
            rs_ema = rs_raw.ewm(span=10, adjust=False).mean()
            norm   = rs_ema.iloc[-26:].mean()
            rs_r   = (rs_ema / norm) * 100 if norm > 0 else rs_ema
            rs_m   = (rs_r / rs_r.shift(4) * 100).ewm(span=10, adjust=False).mean()
            x = round(float(rs_r.iloc[-1]), 2)
            y = round(float(rs_m.iloc[-1]), 2)
            if pd.isna(x) or pd.isna(y): continue
            if x>100 and y>100: q="Leading"
            elif x>100:          q="Weakening"
            elif y>100:          q="Improving"
            else:                q="Lagging"
            dx = x - float(rs_r.iloc[-2]) if len(rs_r)>=2 else 0
            dy = y - float(rs_m.iloc[-2]) if len(rs_m)>=2 else 0
            trail_x2=[round(float(v),2) for v in rs_r.iloc[-3:-1].values if not pd.isna(v)]
            trail_y2=[round(float(v),2) for v in rs_m.iloc[-3:-1].values if not pd.isna(v)]
            results.append({"ticker":tk,"x":x,"y":y,"quadrant":q,
                "trail_x":trail_x2,"trail_y":trail_y2,
                "dx":round(dx,2),"dy":round(dy,2),
                "rotating_in": q in ("Improving","Leading") and dy>0})
        except: continue
    return results


def plot_rrg(rrg_data: list, title: str = "", height: int = 420, key: str = "rrg") -> None:
    """Render a proper JdK RRG with trails and rotation indicators."""
    if not rrg_data:
        st.info("Not enough data to build RRG.")
        return

    C = get_colors()
    qc = {"Leading":"rgba(74,222,128,0.9)","Weakening":"rgba(251,191,36,0.9)",
          "Lagging":"rgba(248,113,113,0.9)","Improving":"rgba(96,165,250,0.9)"}
    qbg= {"Leading":"rgba(74,222,128,0.06)","Weakening":"rgba(251,191,36,0.06)",
          "Lagging":"rgba(248,113,113,0.06)","Improving":"rgba(96,165,250,0.06)"}

    xs = [r["x"] for r in rrg_data]; ys = [r["y"] for r in rrg_data]
    cx = 100; cy = 100  # JdK centre is always 100,100
    pad = max(max(abs(x-100) for x in xs+[101]), max(abs(y-100) for y in ys+[101])) * 1.3

    fig = go.Figure()

    # Quadrant backgrounds
    for xr,yr,q in [(cx+pad,cy+pad,"Leading"),(cx+pad,cy,"Weakening"),
                    (cx,cy,"Improving"),(cx,cy-pad,"Lagging")]:
        x0 = cx if xr > cx else cx-pad
        y0 = cy if yr > cy else cy-pad
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=xr if xr>cx else cx, y1=yr if yr>cy else cy,
                      fillcolor=qbg[q], line_width=0)

    # Centre lines
    fig.add_hline(y=cy, line_color=C["BORDER"], line_width=1.5)
    fig.add_vline(x=cx, line_color=C["BORDER"], line_width=1.5)

    # Quadrant labels
    for lb,xp,yp in [("LEADING",0.75,0.8),("WEAKENING",0.75,-0.8),
                     ("IMPROVING",-0.75,0.8),("LAGGING",-0.75,-0.8)]:
        fig.add_annotation(x=cx+pad*xp, y=cy+pad*yp, text=lb, showarrow=False,
            font=dict(size=9, color=C["BORDER"]), opacity=0.5)

    # Trails (last 4 weeks path)
    for r in rrg_data:
        if r.get("trail_x") and len(r["trail_x"]) >= 2:
            tx = r["trail_x"] + [r["x"]]; ty = r["trail_y"] + [r["y"]]
            fig.add_trace(go.Scatter(x=tx, y=ty, mode="lines",
                line=dict(color=qc[r["quadrant"]], width=1, dash="dot"),
                showlegend=False, hoverinfo="skip"))

    # Dots
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers+text",
        text=[r["ticker"] for r in rrg_data],
        textposition="top center",
        textfont=dict(size=8, color=C["SUB"]),
        marker=dict(
            color=[qc[r["quadrant"]] for r in rrg_data],
            size=14, line=dict(width=1, color=C["BORDER"])
        ),
        customdata=[[r["quadrant"], r["dx"], r["dy"]] for r in rrg_data],
        hovertemplate=(
            "<b>%{text}</b><br>"
            "RS-Ratio: %{x:.1f}<br>"
            "RS-Momentum: %{y:.1f}<br>"
            "Quadrant: %{customdata[0]}<br>"
            "Δ this week: RS %{customdata[1]:+.2f} / Mom %{customdata[2]:+.2f}"
            "<extra></extra>"
        ),
    ))

    # Velocity arrows for rotating sectors
    for r in rrg_data:
        if abs(r.get("dx",0)) > 0.1 or abs(r.get("dy",0)) > 0.1:
            fig.add_annotation(x=r["x"], y=r["y"],
                ax=r["x"]-r["dx"]*3, ay=r["y"]-r["dy"]*3,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=1.2,
                arrowwidth=1.5,
                arrowcolor=qc[r["quadrant"]])

    fig.update_layout(
        height=height, margin=dict(l=0,r=0,t=24,b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["TEXT"], family="Inter"),
        xaxis=dict(title="RS-Ratio (>100 = outperforming SPY)",
                   range=[cx-pad, cx+pad],
                   showgrid=True, gridcolor=C["BORDER"], color=C["SUB"], zeroline=False),
        yaxis=dict(title="RS-Momentum (>100 = accelerating)",
                   range=[cy-pad, cy+pad],
                   showgrid=True, gridcolor=C["BORDER"], color=C["SUB"], zeroline=False),
        showlegend=False,
    )

    event = st.plotly_chart(fig, use_container_width=True,
                             on_select="rerun", key=f"rrg_{key}")
    return event


page_config("Screener · Weinstein V6")
inject_css()
C = get_colors()

user         = st.session_state.get("username", "")
is_logged_in = st.session_state.get("logged_in", False)

# ── Universe ──────────────────────────────────────────────────
FINVIZ_INDUSTRIES = {
    "Semiconductors":             ["NVDA","AMD","AVGO","QCOM","TXN","MCHP","ADI","AMAT","LRCX","KLAC","ASML","ARM","MU","SMCI","ON","MRVL","INTC","NXPI","WOLF","SITM","CRUS","SWKS"],
    "Semiconductor Equipment":    ["AMAT","LRCX","KLAC","ASML","ONTO","UCTT","ICHR","ACLS","AMKR","COHU","FORM","KLIC"],
    "Software - Application":     ["CRM","NOW","ADBE","INTU","CDNS","SNPS","ANSS","PTC","MANH","PCTY","PAYC","DOCU","HUBS","FRSH","MNDY","BRZE"],
    "Software - Infrastructure":  ["MSFT","ORCL","PLTR","MDB","DDOG","SNOW","NET","ZS","CRWD","PANW","FTNT","OKTA","ESTC","GTLB"],
    "Computer Hardware":          ["AAPL","HPQ","HPE","DELL","NTAP","PSTG","WDC","STX","NTNX","SMCI","PURE"],
    "IT Services":                ["ACN","IBM","INFY","WIT","CTSH","DXC","EPAM","GLOB","EXLS","CDW"],
    "Internet Content":           ["GOOGL","META","PINS","SNAP","RBLX","MTCH","TTD","ZETA"],
    "Communication Equipment":    ["CSCO","JNPR","ANET","CIEN","VIAV","CALX","INFN"],
    "Drug Manufacturers - Major": ["LLY","JNJ","MRK","ABBV","PFE","AMGN","BMY","GILD","REGN","VRTX","MRNA","AZN","NVO"],
    "Drug Manufacturers - Specialty":["JAZZ","SUPN","PRGO","IMVT","ARWR","ALNY","IONS","ITCI","HRMY"],
    "Biotechnology":              ["MRNA","BIIB","REGN","VRTX","ALNY","BMRN","EXEL","ARWR","SRPT","CRSP","BEAM","NTLA"],
    "Medical Devices":            ["ISRG","MDT","BSX","EW","SYK","BDX","ZBH","HOLX","INSP","NARI","SWAV"],
    "Diagnostics & Research":     ["TMO","DHR","IQV","ILMN","A","EXAS","GH","NTRA","RXRX"],
    "Healthcare Plans":           ["UNH","ELV","CI","HUM","MOH","CNC","OSCR"],
    "Banks - Major":              ["JPM","BAC","WFC","C","GS","MS","USB","PNC","TFC","COF","BK"],
    "Banks - Regional":           ["ZION","MTB","BOKF","EWBC","FFIN","IBOC","WAFD","CUBI"],
    "Asset Management":           ["BLK","APO","KKR","BX","CG","ARES","BAM","OWL","AMG"],
    "Insurance":                  ["PGR","ALL","TRV","CB","HIG","MKL","CINF","WRB","AON","MMC","AJG"],
    "Financial Data & Exchanges": ["SPGI","MCO","CME","ICE","MSCI","NDAQ","TW","CBOE","FDS"],
    "Credit Services":            ["V","MA","AXP","COF","DFS","SYF","ALLY","AFRM","UPST"],
    "Auto Manufacturers":         ["TSLA","GM","F","RIVN","LCID","STLA","NIO","LI","XPEV"],
    "Specialty Retail":           ["HD","LOW","ORLY","AZO","TSCO","WSM","RH","BBWI","URBN","ANF","FIVE"],
    "Internet Retail":            ["AMZN","BKNG","EXPE","ABNB","W","ETSY","EBAY","CHWY","CVNA"],
    "Restaurants":                ["MCD","SBUX","CMG","YUM","QSR","DPZ","WING","TXRH","DRI","CAVA"],
    "Apparel & Footwear":         ["NKE","LULU","DECK","ONON","CROX","SKX","RL","UAA"],
    "Entertainment & Leisure":    ["MAR","HLT","H","WH","RCL","CCL","NCLH","LYV","IMAX"],
    "Gambling":                   ["LVS","MGM","WYNN","CZR","BYD","PENN","DKNG","FLUT"],
    "Discount Stores":            ["WMT","COST","TGT","DG","DLTR","FIVE","OLLI"],
    "Household & Personal":       ["PG","CL","CHD","KMB","ELF","HIMS","KENVUE"],
    "Beverages":                  ["KO","PEP","MNST","CELH","FIZZ","STZ","BUD","TAP"],
    "Food & Staples":             ["MDLZ","GIS","K","CPB","CAG","HRL","MKC","POST"],
    "Grocery & Drug Stores":      ["KR","CVS","WBA","CASY"],
    "Oil & Gas E&P":              ["XOM","CVX","COP","EOG","OXY","DVN","FANG","MRO","APA","AR","EQT","MTDR","CTRA"],
    "Oil & Gas Midstream":        ["WMB","OKE","KMI","EPD","ET","MPLX","TRGP","LNG"],
    "Oil & Gas Refining":         ["MPC","VLO","PSX","PBF","DINO"],
    "Oil & Gas Services":         ["SLB","HAL","BKR","NOV","WHD","LBRT"],
    "Uranium":                    ["CCJ","UEC","UUUU","DNN","NXE","BWXT"],
    "Renewable Energy":           ["NEE","BEP","BEPC","FSLR","ENPH","RUN","NOVA","ARRY"],
    "Aerospace & Defense":        ["LMT","RTX","NOC","GD","BA","HII","TDG","HEI","AXON","KTOS","RKLB"],
    "Airlines":                   ["UAL","DAL","AAL","LUV","JBLU","ALK"],
    "Logistics & Freight":        ["FDX","UPS","XPO","GXO","CHRW","SAIA","ODFL","WERN","JBHT"],
    "Railroads":                  ["UNP","CSX","NSC","CP","CN","WAB"],
    "Industrial Machinery":       ["EMR","ROK","ITW","IEX","ROP","GNRC","AME","GTLS"],
    "Construction":               ["GE","CAT","HON","DE","CMI","AGCO","TEX","PWR","ACM"],
    "Chemicals":                  ["LIN","APD","ECL","DD","EMN","RPM","IFF","ALB","FMC","CF","MOS"],
    "Steel & Metals":             ["NUE","STLD","CMC","CLF","X","RS","ATI"],
    "Gold & Silver":              ["NEM","GOLD","AEM","AGI","KGC","WPM","FNV","RGLD","PAAS"],
    "Copper & Mining":            ["FCX","SCCO","HBM","TECK","MP"],
    "Building Materials":         ["SHW","VMC","MLM","EXP","LPX","UFPI","BLDR"],
    "REIT - Industrial & Data":   ["PLD","REXR","EGP","STAG","EQIX","DLR","IRM","CCI","AMT","SBAC"],
    "REIT - Residential & Retail":["EQR","AVB","MAA","ESS","SPG","O","KIM","NNN","VICI","INVH"],
    "Utilities":                  ["NEE","SO","DUK","AEP","XEL","EXC","ED","SRE","D","PEG","VST","CEG"],
    "Telecom & Media":            ["T","VZ","TMUS","DIS","NFLX","WBD","PARA","CMCSA","CHTR"],
    "Real Estate Services":       ["CBRE","JLL","EXPI","OPEN"],
    "Residential Construction":   ["DHI","LEN","TOL","PHM","NVR","MDC","TMHC","MTH","LGIH"],
}

TICKER_TO_INDUSTRY = {}
for ind, tks in FINVIZ_INDUSTRIES.items():
    for tk in tks:
        if tk not in TICKER_TO_INDUSTRY:
            TICKER_TO_INDUSTRY[tk] = ind

SECTOR_TO_INDUSTRIES = {
    "XLK":  ["Semiconductors","Semiconductor Equipment","Software - Application","Software - Infrastructure","Computer Hardware","IT Services","Internet Content","Communication Equipment"],
    "XLF":  ["Banks - Major","Banks - Regional","Asset Management","Insurance","Financial Data & Exchanges","Credit Services"],
    "XLE":  ["Oil & Gas E&P","Oil & Gas Midstream","Oil & Gas Refining","Oil & Gas Services","Uranium"],
    "XLV":  ["Drug Manufacturers - Major","Drug Manufacturers - Specialty","Biotechnology","Medical Devices","Diagnostics & Research","Healthcare Plans"],
    "XLI":  ["Aerospace & Defense","Airlines","Logistics & Freight","Railroads","Industrial Machinery","Construction"],
    "XLY":  ["Auto Manufacturers","Specialty Retail","Internet Retail","Restaurants","Apparel & Footwear","Entertainment & Leisure","Gambling"],
    "XLP":  ["Discount Stores","Household & Personal","Beverages","Food & Staples","Grocery & Drug Stores"],
    "XLU":  ["Utilities","Renewable Energy"],
    "XLRE": ["REIT - Industrial & Data","REIT - Residential & Retail","Real Estate Services","Residential Construction"],
    "XLB":  ["Chemicals","Steel & Metals","Gold & Silver","Copper & Mining","Building Materials"],
    "XLC":  ["Telecom & Media"],
}

# ── Load data ─────────────────────────────────────────────────
with st.spinner("Loading market data…"):
    spx_ev, sec_df, spx_close_json = get_spx_data()

if spx_ev is None:
    st.error("Yahoo Finance is rate-limiting. Please wait 30 seconds and refresh.")
    if st.button("🔄 Retry"):
        st.cache_data.clear(); st.rerun()
    st.stop()

# ── Helpers ───────────────────────────────────────────────────
@st.cache_data(ttl=7*24*3600, show_spinner=False)
def industry_rs(tickers_json, days):
    tks = json.loads(tickers_json)
    end = datetime.today(); start = end - timedelta(days=days+5)
    try:
        all_tks = list(set(tks+["SPY"]))
        raw = yf.download(all_tks, start=start, end=end, auto_adjust=False, progress=False, threads=False)["Close"]
        if isinstance(raw, pd.Series): raw = raw.to_frame(all_tks[0])
        raw = raw.ffill().dropna(how="all")
        if len(raw)<2 or "SPY" not in raw.columns: return None
        n = min(days, len(raw)-1)
        basket = raw[[t for t in tks if t in raw.columns]].iloc[-(n+1):]
        if basket.empty: return None
        ir = ((basket.iloc[-1]/basket.iloc[0])-1).mean()*100
        sr = (raw["SPY"].iloc[-1]/raw["SPY"].iloc[-n-1]-1)*100
        return round(ir-sr, 2)
    except: return None

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def get_chart_data(ticker):
    return fetch_weekly(ticker, years=5)

def make_chart(ticker):
    df = get_chart_data(ticker)
    if df.empty: return None
    close = df["Close"]; df1y = df.iloc[-52:]
    sma50 = close.rolling(50).mean().iloc[-52:]
    sma200= close.rolling(200).mean().iloc[-52:]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df1y.index, y=df1y["Close"].values, mode="lines",
        name=ticker, line=dict(color=C["BLUE"],width=2),
        hovertemplate="%{x|%b %d %Y}<br><b>$%{y:.2f}</b><extra></extra>"))
    if not sma50.isna().all():
        fig.add_trace(go.Scatter(x=df1y.index,y=sma50.values,mode="lines",name="50w",
            line=dict(color=C["YELLOW"],width=1.5),hoverinfo="skip"))
    if not sma200.isna().all():
        fig.add_trace(go.Scatter(x=df1y.index,y=sma200.values,mode="lines",name="200w",
            line=dict(color=C["RED"],width=1.5,dash="dot"),hoverinfo="skip"))
    fig.update_layout(height=200,margin=dict(l=0,r=0,t=16,b=0),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=C["TEXT"],family="Inter",size=10),
        xaxis=dict(showgrid=False,color=C["SUB"],tickfont=dict(size=9),zeroline=False),
        yaxis=dict(showgrid=True,gridcolor=C["BORDER"],color=C["SUB"],
                   tickfont=dict(size=9),zeroline=False,tickprefix="$"),
        legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(size=9),orientation="h",x=0,y=1.15),
        hovermode="x unified")
    return fig

def entry_label(r):
    cross = r.get("cross",-1); stage = r.get("stage","")
    if "Stage 2" not in stage: return ""
    return f"Entered {cross}w ago" if cross>=0 else "In Stage 2"

def wl_btn(tk, key):
    if not is_logged_in: return
    if st.button("➕", key=f"wl_{key}", help=f"Add {tk} to watchlist"):
        add_to_watchlist(user, tk, tag="screen")
        st.toast(f"✓ {tk} added to watchlist", icon="📌")

def stock_grid(tickers, scan_df, key_prefix=""):
    for i in range(0, len(tickers), 3):
        batch = tickers[i:i+3]
        gcols = st.columns(3)
        for col, tk in zip(gcols, batch):
            with col:
                r = {}
                if not scan_df.empty:
                    m = scan_df[scan_df["ticker"]==tk]
                    if not m.empty: r = m.iloc[0].to_dict()
                stage = r.get("stage","–"); score = r.get("score",0)
                sig   = sig_icon(r); entry = entry_label(r)
                dot   = "🟢" if "Stage 2" in stage else "🟡" if "Stage 3" in stage else "🔴" if "Stage 4" in stage else "🔵"
                sig_h = f"&nbsp;<span style='color:{C['GREEN']};font-weight:700'>{sig}</span>" if sig else ""
                ent_h = f"&nbsp;<span style='color:{C['SUB']};font-size:0.7rem'>· {entry}</span>" if entry else ""
                hcol, bcol = st.columns([9,1])
                with hcol:
                    st.markdown(f"<div style='padding:4px 0 1px'><span style='font-weight:700'>{dot} {tk}</span>"
                        f"<span style='color:{C['SUB']};font-size:0.73rem;margin-left:6px'>{stage}·{score}/5"
                        f"·RS {fmt(r.get('rs'),'',1)}{sig_h}{ent_h}</span></div>", unsafe_allow_html=True)
                with bcol:
                    wl_btn(tk, f"{key_prefix}_{tk}_{i}")
                with st.expander("📊 Chart", expanded=False):
                    fig = make_chart(tk)
                    if fig: st.plotly_chart(fig, width="stretch", key=f"fig_{key_prefix}_{tk}_{i}")
                    else: st.caption("No data")

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def get_yf_industry(ticker):
    try: return yf.Ticker(ticker).info.get("industry","") or ""
    except: return ""

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def scan_industry_expanded(industry_name, curated_json, spx_json):
    curated = json.loads(curated_json)
    all_tks = fetch_nyse_tickers()
    extra   = [t for t in all_tks if t not in curated]
    kw_map  = {
        "Semiconductors":["semiconductor"],"Biotechnology":["biotechnology"],
        "Drug Manufacturers - Major":["drug manufacturers—general","pharmaceuticals"],
        "Medical Devices":["medical devices"],"Banks - Major":["banks—diversified","money center"],
        "Banks - Regional":["banks—regional"],"Oil & Gas E&P":["oil & gas e&p","exploration"],
        "Aerospace & Defense":["aerospace & defense"],"Gold & Silver":["gold","silver"],
        "Steel & Metals":["steel"],"Chemicals":["specialty chemicals","chemicals"],
        "Utilities":["utilities—regulated"],"Renewable Energy":["solar","renewable"],
        "Insurance":["insurance"],"Restaurants":["restaurants"],
        "Software - Application":["software—application","application software"],
        "Software - Infrastructure":["infrastructure software","systems software"],
    }
    keywords = []
    for k, kws in kw_map.items():
        if k.lower()==industry_name.lower(): keywords=kws; break
    if not keywords:
        words = industry_name.lower().replace(" - "," ").split()
        keywords = [" ".join(words[:2])] if len(words)>=2 else words
    matched = [t for t in extra[:2000] if any(kw in get_yf_industry(t).lower() for kw in keywords)]
    if not matched: return pd.DataFrame()
    res = scan_batch(json.dumps(matched), spx_json, min_score=0, min_price=1.0)
    return pd.DataFrame(res) if res else pd.DataFrame()

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def build_industry_table():
    rows = []
    for ind_name, tks in FINVIZ_INDUSTRIES.items():
        rs1w=industry_rs(json.dumps(tks[:8]),5)
        rs1m=industry_rs(json.dumps(tks[:8]),21)
        rs3m=industry_rs(json.dumps(tks[:8]),63)
        rows.append({"Industry":ind_name,"Stocks":len(tks),
            "RS 1W":round(rs1w,1) if rs1w else None,
            "RS 1M":round(rs1m,1) if rs1m else None,
            "RS 3M":round(rs3m,1) if rs3m else None,
            "_rs1w":rs1w or -999,"_rs1m":rs1m or -999,"_rs3m":rs3m or -999})
    return pd.DataFrame(rows)

def sig_table(scan_df, min_score=3):
    if scan_df.empty: return
    sf = scan_df[scan_df["score"]>=min_score].sort_values(
        ["premium","early_sig","score","rs"],ascending=[False,False,False,False])
    if sf.empty: return
    rows=[]
    for _,r in sf.iterrows():
        cross=f"{int(r['cross'])}w" if r.get("cross",-1)>=0 else "–"
        rows.append({"Signal":sig_icon(r.to_dict()),"Ticker":r["ticker"],
            "Stage":r["stage"],"Score":f"{r['score']}/5",
            "RS":fmt(r["rs"],"",1),"Price":fmt(r["price"]),
            "%>SMA":fmt(r["pct_above"],"%",1),"Vol":fmt(r["vol"],"x",1),
            "Base":f"{r['base_w']}w","Entry":entry_label(r.to_dict()),
            "Cross":cross,"Stop":fmt(r["stop"]),"Risk":fmt(r["risk"],"%",1)})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

def wl_selector(scan_df, key):
    if not is_logged_in or scan_df.empty: return
    tickers = scan_df[scan_df["score"]>=3]["ticker"].tolist()
    if not tickers: return
    c1,c2 = st.columns([3,1])
    with c1:
        pick = st.selectbox("Add to watchlist",["–"]+tickers,
                             key=f"wl_sel_{key}",label_visibility="collapsed")
    with c2:
        if st.button("➕ Watchlist",key=f"wl_btn_{key}"):
            if pick!="–":
                add_to_watchlist(user,pick,tag="screen")
                st.toast(f"✓ {pick} added",icon="📌")

# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
st.markdown("# 📈 Weinstein Screener")

pct=spx_ev.get("pct_above") or 0; stage=spx_ev.get("stage","")
m1,m2,m3,m4,m5=st.columns(5)
m1.metric("SPY Stage",stage); m2.metric("Price",fmt(spx_ev["price"]))
m3.metric("50w SMA",fmt(spx_ev["sma50w"])); m4.metric("% above SMA",fmt(pct,"%",1))
m5.metric("Stage Score",f"{spx_ev['score']}/5")

if "Stage 2" not in stage:
    st.markdown(f'<div class="wcard-warn">⚠ <strong>SPY not in Stage 2.</strong> Per Weinstein: no new buys until market recovers.</div>',unsafe_allow_html=True)
elif pct>10:
    st.markdown(f'<div class="wcard-warn" style="border-left-color:{C["YELLOW"]}">⚡ <strong>SPY extended</strong> ({pct:.1f}% above SMA). Wait for pullback before fresh entries.</div>',unsafe_allow_html=True)
else:
    st.markdown(f'<div class="wcard-info">✓ <strong>SPY in Stage 2.</strong> Conditions favourable. Signals are valid.</div>',unsafe_allow_html=True)

st.markdown("---")

# ── Stock Search ─────────────────────────────────────────────
with st.expander("🔎 Analyze a stock", expanded=False):
    sc1, sc2 = st.columns([4,1])
    with sc1:
        search_q = st.text_input("", placeholder="e.g. NVDA, ARM, TSLA…",
                                  label_visibility="collapsed", key="stock_search")
    with sc2:
        do_search = st.button("Analyze", use_container_width=True, key="stock_search_btn")

    if search_q and do_search:
        q = search_q.strip().upper()
        with st.spinner(f"Analyzing {q}…"):
            spx_close_s = pd.read_json(StringIO(spx_close_json), typ="series")
            df_s = fetch_weekly(q)

        if df_s.empty:
            st.error(f"Could not find data for {q}.")
        else:
            from utils.screener import evaluate
            r = evaluate(df_s, spx_close_s)
            stage = r["stage"]

            # Metrics
            a1,a2,a3,a4 = st.columns(4)
            a1.metric("Stage",     stage)
            a2.metric("Score",     f"{r['score']}/5")
            a3.metric("RS vs SPX", fmt(r["rs"],"",1))
            a4.metric("%>50w SMA", fmt(r["pct_above"],"%",1))
            b1,b2,b3,b4 = st.columns(4)
            b1.metric("Price",   fmt(r["price"]))
            b2.metric("50w SMA", fmt(r["sma50w"]))
            b3.metric("Stop",    fmt(r["stop"]))
            b4.metric("Risk",    fmt(r["risk"],"%",1))

            st.markdown("---")
            st.markdown("#### ✅ Weinstein Checklist")

            def chk(passed, label, detail):
                icon  = "✅" if passed else "❌"
                color = C["GREEN"] if passed else C["RED"]
                return (f'<div style="display:flex;gap:10px;padding:8px 14px;margin:4px 0;'
                        f'background:{C["CARD"]};border-radius:8px;border:1px solid {C["BORDER"]}">' 
                        f'<span style="font-size:1.1rem">{icon}</span>'
                        f'<div><strong style="color:{color}">{label}</strong><br>'
                        f'<span style="color:{C["SUB"]};font-size:0.8rem">{detail}</span></div></div>')

            pct = r["pct_above"] or 0
            st.markdown(chk(r["above_sma"],"Price above 50w SMA",
                f"Price {fmt(r['price'])} is {fmt(pct,'%',1)} {'above' if pct>=0 else 'below'} the 50w SMA ({fmt(r['sma50w'])})"),unsafe_allow_html=True)
            st.markdown(chk(r["sma_rising"],"50w SMA is rising",
                "SMA slope positive — uptrend confirmed." if r["sma_rising"] else "SMA flat or declining — warning."),unsafe_allow_html=True)
            st.markdown(chk(r["rs_up"],"RS vs SPX positive",
                f"RS: {fmt(r['rs'],'',1)} — {rs_tag(r['rs'])}. {'Outperforming market.' if r['rs_up'] else 'Underperforming — Weinstein avoids these.'}"),unsafe_allow_html=True)
            st.markdown(chk(r["near_high"],"Near 52-week high (within 15%)",
                "Within breakout zone." if r["near_high"] else "More than 15% below 52w high."),unsafe_allow_html=True)
            st.markdown(chk(r["not_extended"],"Not overextended (<30% above SMA)",
                f"{fmt(pct,'%',1)} above SMA. {'Ideal entry zone.' if 0<pct<15 else 'Extended — wait for pullback.' if pct>=15 else 'Below SMA.'}"),unsafe_allow_html=True)
            vol = r["vol"]
            st.markdown(chk(r["vol_ok"],"Breakout on above-average volume (≥1.5x)",
                f"Vol ratio: {fmt(vol,'x',1)}. {'Strong buying.' if vol and vol>=2 else 'Confirmed.' if vol and vol>=1.5 else 'Below avg — low conviction.'}"),unsafe_allow_html=True)
            bw = r["base_w"]
            st.markdown(chk(bw>=15,"Base ≥15 weeks",
                f"Base: {bw}w ({r['base_q']}). {'Very long — Weinstein ideal.' if bw>=80 else 'Long.' if bw>=40 else 'Medium.' if bw>=15 else 'Too short.'}"),unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### 🧠 Verdict")
            if "Stage 2" in stage and r["score"]>=4:
                if r.get("premium"):
                    vc=C["GREEN"]; v=f"**🟢 PREMIUM** — {q} is in a textbook Stage 2 breakout with a {bw}w base. Stop at {fmt(r['stop'])} ({fmt(r['risk'],'%',1)} risk)."
                elif r.get("early_sig"):
                    vc=C["GREEN"]; v=f"**🟢 EARLY** — {q} crossed above 50w SMA {r['cross']}w ago with {fmt(vol,'x',1)} volume. Entry window open. Stop at {fmt(r['stop'])}."
                else:
                    vc=C["BLUE"]; v=f"**🔵 STAGE 2 — LATE** — {q} is in Stage 2 but move is underway ({fmt(pct,'%',1)} above SMA). Wait for pullback toward {fmt(r['sma50w'])}."
            elif "Stage 1" in stage:
                vc=C["BLUE"]; v=f"**🔵 STAGE 1** — {q} building a {bw}w base. Not actionable yet. Alert at {fmt(r['sma50w'])} + volume."
            elif "Stage 3" in stage:
                vc=C["YELLOW"]; v=f"**🟡 STAGE 3** — {q} topping. SMA flattening. Tighten stops, do not buy."
            else:
                vc=C["RED"]; v=f"**🔴 STAGE 4** — {q} in downtrend. Never buy Stage 4."

            st.markdown(f'<div style="background:{C["CARD"]};border-left:4px solid {vc};border:1px solid {vc}33;border-radius:10px;padding:16px 20px;line-height:1.7">{v}</div>',unsafe_allow_html=True)

            # Mini chart
            with st.expander("📊 Chart", expanded=True):
                fig_s = make_chart(q)
                if fig_s: st.plotly_chart(fig_s, use_container_width=True)

            if is_logged_in:
                if st.button(f"➕ Add {q} to watchlist", key=f"wl_search_{q}"):
                    add_to_watchlist(user, q, tag="analyzed")
                    st.toast(f"✓ {q} added to watchlist", icon="📌")

st.markdown("---")

tab_sectors, tab_industries, tab_signals, tab_s1, tab_daily = st.tabs([
    "🏦 Sectors & RRG", "🔍 Industries", "🚨 Signals", "👁 Stage 1 Watchlist", "📅 Daily"])

# ══════════════════════════════════════
# TAB 1 — SECTORS + RRG
# ══════════════════════════════════════
with tab_sectors:
    st.markdown("---")
    st.markdown("#### Relative Rotation Graph")
    st.markdown(f"<p class='subtext'>Leading (top-right) · Weakening (bottom-right) · Improving (top-left) · Lagging (bottom-left)</p>",unsafe_allow_html=True)

    # JdK RRG
    with st.spinner('Computing JdK RRG (RS-Ratio / RS-Momentum)…'):
        rrg_data = compute_rrg_inline(list(SECTORS.keys()))

    if rrg_data:
        improving = [r for r in rrg_data if r['quadrant']=='Improving' and r['rotating_in']]
        if improving:
            names = [SECTORS.get(r['ticker'],r['ticker']) for r in improving]
            st.markdown(f'<div class="wcard-info">🔄 <strong>Early rotation signal:</strong> {", ".join(names)} moving Lagging → Improving. Watch for entry.</div>', unsafe_allow_html=True)
        rrg_event = plot_rrg(
            [{**r, "ticker": SECTORS.get(r["ticker"],r["ticker"])} for r in rrg_data],
            key="sector_rrg", height=420)
        if rrg_event and hasattr(rrg_event,"selection") and rrg_event.selection.get("points"):
            clicked = rrg_event.selection["points"][0].get("text","")
            if clicked and clicked in list(SECTORS.values()):
                st.session_state["sec_drill"] = clicked
                st.toast(f"📍 {clicked} selected", icon="🏦")
        st.markdown("<p class='subtext'>RS-Ratio >100 = outperforms SPY · RS-Momentum >100 = accelerating · Dotted trail = last 4 weeks · Arrows = weekly direction</p>", unsafe_allow_html=True)
        st.markdown("---")
    st.markdown("#### Sector Ranking")
    sec_rows=[]
    for _,r in sec_df.iterrows():
        cross=f"{int(r['cross'])}w" if r.get("cross",-1)>=0 else "–"
        sec_rows.append({"Sector":r.get("name",r["ticker"]),"Price":fmt(r["price"]),
            "%>SMA":fmt(r["pct_above"],"%",1),"RS":round(r["rs"],1) if r["rs"] else None,
            "RS Trend":rs_tag(r["rs"]),"Vol":fmt(r["vol"],"x",1),
            "Base":f"{r['base_w']}w","Cross":cross,"Score":f"{r['score']}/5","Signal":sig_icon(r.to_dict())})
    styled_sec=pd.DataFrame(sec_rows).style.map(
        lambda v:f"color:{'#16a34a' if isinstance(v,(int,float)) and v>0 else '#dc2626' if isinstance(v,(int,float)) and v<0 else ''};font-weight:{'600' if isinstance(v,(int,float)) else ''}",
        subset=["RS"]).format({"RS":lambda v:f"{v:+.1f}" if v and not np.isnan(v) else "–"})
    st.dataframe(styled_sec, width="stretch", hide_index=True, height=430)

    early_secs=sec_df[sec_df["early_sig"]]
    if not early_secs.empty:
        st.markdown("#### 🟡 Early Sector Signals")
        for _,r in early_secs.iterrows():
            st.markdown(signal_card_html(r.to_dict(),r["name"],C),unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Drill into Sector")
    sel_sec=st.selectbox("",["– select –"]+list(SECTORS.values()),key="sec_drill",label_visibility="collapsed")

    if sel_sec and sel_sec!="– select –":
        sec_tk=next((k for k,v in SECTORS.items() if v==sel_sec),None)
        sec_inds=SECTOR_TO_INDUSTRIES.get(sec_tk,[])
        sec_stocks=SECTOR_STOCKS.get(sec_tk,[])
        st.markdown(f"### {sel_sec}")

        if sec_inds:
            st.markdown("**Industries:**")
            icols=st.columns(3)
            for i,ind in enumerate(sec_inds):
                tks=FINVIZ_INDUSTRIES.get(ind,[])
                rs3=industry_rs(json.dumps(tks[:8]),63) if tks else None
                cc="#16a34a" if (rs3 and rs3>0) else "#dc2626" if rs3 else C["SUB"]
                icols[i%3].markdown(f"<span style='font-size:0.8rem'><strong>{ind}</strong> "
                    f"<span style='color:{cc}'>{f'{rs3:+.1f}%' if rs3 else '–'}</span> RS 3M</span>",unsafe_allow_html=True)

        st.markdown("---")
        with st.spinner(f"Scanning {sel_sec}…"):
            df_sec=scan_tickers(json.dumps(sec_stocks),spx_close_json)
        if not df_sec.empty:
            sig_table(df_sec)
            wl_selector(df_sec, f"sec_{sel_sec[:8]}")
            sig_tks=df_sec[df_sec["score"]>=4].sort_values(["premium","early_sig","score"],ascending=False)["ticker"].tolist()
            if sig_tks:
                st.markdown("**Charts — Stage 2+ stocks:**")
                stock_grid(sig_tks[:12],df_sec,f"sec_{sel_sec[:8]}")


# ══════════════════════════════════════
# TAB 2 — INDUSTRIES
# ══════════════════════════════════════
with tab_industries:
    st.markdown("---")
    st.markdown(f"<p class='subtext'>{len(FINVIZ_INDUSTRIES)} industries · {sum(len(v) for v in FINVIZ_INDUSTRIES.values())} stocks</p>",unsafe_allow_html=True)

    # ── Industry RRG ──────────────────────────────────────────
    with st.expander("📡 Industry Relative Rotation Graph", expanded=False):
        st.markdown(f"<p class='subtext'>Based on RS 3M (X) and RS 1W vs 3M momentum (Y). Click a dot to drill into that industry.</p>",
                    unsafe_allow_html=True)
        with st.spinner("Building industry RRG…"):
            ind_rrg_rows = []
            for ind_name, tks in list(FINVIZ_INDUSTRIES.items()):
                rs3m = industry_rs(json.dumps(tks[:8]), 63)
                rs1w = industry_rs(json.dumps(tks[:8]), 5)
                if rs3m is None: continue
                momentum = (rs1w or 0) - (rs3m / 12)  # 1W RS vs monthly average
                ind_rrg_rows.append({"name": ind_name, "x": rs3m, "y": momentum})

        if ind_rrg_rows:
            ix=[r["x"] for r in ind_rrg_rows]
            iy=[r["y"] for r in ind_rrg_rows]
            il=[r["name"] for r in ind_rrg_rows]
            ic=[("rgba(74,222,128,0.9)" if r["x"]>0 and r["y"]>0 else
                 "rgba(251,191,36,0.9)" if r["x"]>0 else
                 "rgba(96,165,250,0.9)"  if r["y"]>0 else
                 "rgba(248,113,113,0.9)") for r in ind_rrg_rows]

            mx2=max(abs(v) for v in ix+[1])*1.2; my2=max(abs(v) for v in iy+[1])*1.2
            fig_ind_rrg=go.Figure()
            for xr,yr,col in [(mx2,my2,"rgba(74,222,128,0.05)"),(mx2,-my2,"rgba(251,191,36,0.05)"),
                              (-mx2,-my2,"rgba(248,113,113,0.05)"),(-mx2,my2,"rgba(96,165,250,0.05)")]:
                fig_ind_rrg.add_shape(type="rect",x0=0 if xr>0 else xr,y0=0 if yr>0 else yr,
                    x1=xr if xr>0 else 0,y1=yr if yr>0 else 0,fillcolor=col,line_width=0)
            fig_ind_rrg.add_hline(y=0,line_color=C["BORDER"],line_width=1)
            fig_ind_rrg.add_vline(x=0,line_color=C["BORDER"],line_width=1)
            for lb,xp,yp in [("LEADING",0.75,0.85),("WEAKENING",0.75,-0.85),("IMPROVING",-0.75,0.85),("LAGGING",-0.75,-0.85)]:
                fig_ind_rrg.add_annotation(x=mx2*xp,y=my2*yp,text=lb,showarrow=False,
                    font=dict(size=8,color=C["BORDER"]),opacity=0.5)
            fig_ind_rrg.add_trace(go.Scatter(x=ix,y=iy,mode="markers+text",
                text=il,textposition="top center",textfont=dict(size=8,color=C["TEXT"]),
                marker=dict(color=ic,size=10,line=dict(width=1,color=C["BORDER"])),
                hovertemplate="<b>%{text}</b><br>RS 3M: %{x:.1f}%<br>Momentum: %{y:.1f}<extra></extra>"))
            fig_ind_rrg.update_layout(height=450,margin=dict(l=0,r=0,t=10,b=0),
                paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=C["TEXT"],family="Inter"),
                xaxis=dict(title="RS 3M vs SPX (%)",showgrid=True,gridcolor=C["BORDER"],color=C["SUB"],zeroline=False),
                yaxis=dict(title="Momentum",showgrid=True,gridcolor=C["BORDER"],color=C["SUB"],zeroline=False),
                showlegend=False)

            ind_rrg_event = st.plotly_chart(fig_ind_rrg, width="stretch",
                                             on_select="rerun", key="rrg_ind_chart")
            if ind_rrg_event and hasattr(ind_rrg_event,"selection") and ind_rrg_event.selection.get("points"):
                clicked_ind = ind_rrg_event.selection["points"][0].get("text","")
                if clicked_ind in FINVIZ_INDUSTRIES:
                    st.session_state["ind_drill2"] = clicked_ind
                    st.toast(f"📍 {clicked_ind} selected — see drill-down below", icon="🔍")

    st.markdown("---")
    with st.expander("📋 Industry RS Table", expanded=True):
        ic1,ic2,ic3=st.columns([2,2,2])
        with ic1: ind_sort=st.selectbox("Sort by",["RS 3M","RS 1M","RS 1W","Industry"],key="ind_sort2")
        with ic2: ind_filter=st.selectbox("Filter",["All","Positive RS 3M","RS 3M > 5%","RS 3M > 10%","Negative RS 3M"],key="ind_filter2")
        with ic3: ind_asc=st.toggle("↑ Low→High" if st.session_state.get("ind_asc2") else "↓ High→Low",value=False,key="ind_asc2")

        with st.spinner("Loading RS data…"):
            df_ind=build_industry_table()

        if ind_filter=="Positive RS 3M": df_ind=df_ind[df_ind["_rs3m"]>0]
        elif ind_filter=="RS 3M > 5%":   df_ind=df_ind[df_ind["_rs3m"]>5]
        elif ind_filter=="RS 3M > 10%":  df_ind=df_ind[df_ind["_rs3m"]>10]
        elif ind_filter=="Negative RS 3M":df_ind=df_ind[df_ind["_rs3m"]<0]

        sk={"RS 3M":"_rs3m","RS 1M":"_rs1m","RS 1W":"_rs1w","Industry":"Industry"}.get(ind_sort,"_rs3m")
        df_ind=df_ind.sort_values(sk,ascending=ind_asc).reset_index(drop=True)

        def style_num(v):
            if not isinstance(v,(int,float)) or np.isnan(v): return ""
            return f"color:{'#16a34a' if v>0 else '#dc2626'};font-weight:600"

        styled_ind=df_ind[["Industry","Stocks","RS 1W","RS 1M","RS 3M"]].style.map(
            style_num,subset=["RS 1W","RS 1M","RS 3M"]).format(
            {c:lambda v:f"{v:+.1f}%" if isinstance(v,(int,float)) and not np.isnan(v) else "–"
             for c in ["RS 1W","RS 1M","RS 3M"]})
        st.dataframe(styled_ind, width="stretch", hide_index=True, height=520)

    st.markdown("---")
    st.markdown("#### Drill-down")
    dc1,dc2=st.columns([4,1])
    with dc1: sel_ind=st.selectbox("",["– select –"]+df_ind["Industry"].tolist(),key="ind_drill2",label_visibility="collapsed")
    with dc2: expand_nyse=st.toggle("+ NYSE",value=False,key="ind_nyse2",help="Expand with NYSE/NASDAQ via yfinance tags. Cached 7 days.")

    if sel_ind and sel_ind!="– select –":
        curated=FINVIZ_INDUSTRIES.get(sel_ind,[])
        if expand_nyse:
            st.info("📡 Expanding with NYSE/NASDAQ…")
            with st.spinner("Fetching extra stocks…"):
                extra_df=scan_industry_expanded(sel_ind,json.dumps(curated),spx_close_json)
            extra_tks=extra_df["ticker"].tolist() if not extra_df.empty else []
            all_tks=list(dict.fromkeys(curated+extra_tks))
        else:
            all_tks=curated; extra_df=pd.DataFrame()

        st.markdown(f"### {sel_ind} — {len(all_tks)} stocks")
        with st.spinner(f"Scanning…"):
            ind_scan=scan_tickers(json.dumps(curated),spx_close_json)
            if expand_nyse and not extra_df.empty:
                ind_scan=pd.concat([ind_scan,extra_df],ignore_index=True).drop_duplicates("ticker")

        if not ind_scan.empty:
            n_p=len(ind_scan[ind_scan["premium"]]); n_e=len(ind_scan[ind_scan["early_sig"]])
            mm1,mm2,mm3,mm4=st.columns(4)
            mm1.metric("Stocks",len(all_tks)); mm2.metric("🟢 Premium",n_p)
            mm3.metric("🟡 Early",n_e); mm4.metric("🔵 Stage 2+",len(ind_scan[ind_scan["score"]>=4]))
            sig_table(ind_scan)
            wl_selector(ind_scan,f"ind_{sel_ind[:10]}")
            st.markdown("**Charts:**")
            stock_grid(all_tks,ind_scan,f"ind_{sel_ind[:10]}")

        ex1,ex2,ex3=st.columns(3)
        with ex1:
            st.download_button("⬇️ All (.txt)",export_tv_lines(all_tks),
                file_name=f"TV_{sel_ind.replace(' ','_')}_all.txt",mime="text/plain",key=f"dl_all_{sel_ind[:12]}")
        if not ind_scan.empty:
            s_tks=ind_scan[ind_scan["early_sig"]|ind_scan["premium"]]["ticker"].tolist()
            s2_tks=ind_scan[ind_scan["score"]>=4]["ticker"].tolist()
            with ex2:
                if s_tks: st.download_button("⬇️ Signals (.txt)",export_tv_lines(s_tks),
                    file_name=f"TV_{sel_ind.replace(' ','_')}_signals.txt",mime="text/plain",key=f"dl_sig_{sel_ind[:12]}")
            with ex3:
                if s2_tks: st.download_button("⬇️ S2+ (.txt)",export_tv_lines(s2_tks),
                    file_name=f"TV_{sel_ind.replace(' ','_')}_s2.txt",mime="text/plain",key=f"dl_s2_{sel_ind[:12]}")


# ══════════════════════════════════════
# TAB 3 — SIGNALS
# ══════════════════════════════════════
with tab_signals:
    st.markdown("---")
    sr1,sr2,sr3,sr4=st.columns([3,1,1,1])
    with sr1: sig_inds=st.multiselect("Industries",list(FINVIZ_INDUSTRIES.keys()),default=list(FINVIZ_INDUSTRIES.keys())[:12],label_visibility="collapsed")
    with sr2: min_sig=st.selectbox("Min score",[3,4,5],index=0,key="sig_min2")
    with sr3: run_sig=st.button("🔍 Scan",width="stretch",key="run_sig2")
    with sr4: nyse_sig=st.toggle("Full NYSE",value=False,key="nyse_sig2")
    sig_filt=st.selectbox("Show",["All","🟢+🟡 Best","🟢 Premium","🟡 Early","🔵 S2 only"],key="sig_filt2")

    if nyse_sig:
        st.info("📡 Full NYSE+NASDAQ scan. First run ~10-15 min, cached 7 days.")
        with st.spinner("Batch scanning…"):
            tks_all=fetch_nyse_tickers()
            nyse_res=scan_batch(json.dumps(tks_all),spx_close_json,min_score=min_sig,min_price=2.0)
        if nyse_res:
            df_nyse=pd.DataFrame(nyse_res)
            if sig_filt=="🟢+🟡 Best":   df_nyse=df_nyse[df_nyse["premium"]|df_nyse["early_sig"]]
            elif sig_filt=="🟢 Premium": df_nyse=df_nyse[df_nyse["premium"]]
            elif sig_filt=="🟡 Early":   df_nyse=df_nyse[df_nyse["early_sig"]]
            elif sig_filt=="🔵 S2 only": df_nyse=df_nyse[~(df_nyse["premium"]|df_nyse["early_sig"])&(df_nyse["score"]>=4)]
            n_p=len(df_nyse[df_nyse["premium"]]); n_e=len(df_nyse[df_nyse["early_sig"]])
            nm1,nm2,nm3,nm4=st.columns(4)
            nm1.metric("Total",len(df_nyse)); nm2.metric("🟢 Premium",n_p)
            nm3.metric("🟡 Early",n_e); nm4.metric("🔵 S2",len(df_nyse)-n_p-n_e)
            rows_n=[]
            for _,r in df_nyse.iterrows():
                cross=f"{int(r['cross'])}w" if r.get("cross",-1)>=0 else "–"
                rows_n.append({"Signal":sig_icon(r.to_dict()),"Ticker":r["ticker"],
                    "Industry":TICKER_TO_INDUSTRY.get(r["ticker"],"–"),
                    "Stage":r["stage"],"Score":f"{r['score']}/5",
                    "RS":fmt(r["rs"],"",1),"Price":fmt(r["price"]),
                    "%>SMA":fmt(r["pct_above"],"%",1),"Vol":fmt(r["vol"],"x",1),
                    "Base":f"{r['base_w']}w","Entry":entry_label(r.to_dict()),
                    "Cross":cross,"Stop":fmt(r["stop"]),"Risk":fmt(r["risk"],"%",1)})
            st.dataframe(pd.DataFrame(rows_n),width="stretch",hide_index=True,height=600)
            wl_selector(df_nyse,"nyse_sig")
            st.download_button("⬇️ Export (.txt)",export_tv_lines(df_nyse["ticker"].tolist()),
                file_name="TV_full_signals.txt",mime="text/plain",key="dl_nyse_sig2")

    elif run_sig and sig_inds:
        all_rows=[]
        prog=st.progress(0)
        for idx,ind in enumerate(sig_inds):
            prog.progress((idx+1)/len(sig_inds),text=f"Scanning {ind}…")
            tks=FINVIZ_INDUSTRIES[ind]; df=scan_tickers(json.dumps(tks),spx_close_json)
            if df.empty: continue
            sec_n="–"; sec_rs_v=None
            for sec_tk,sec_name in SECTORS.items():
                if sec_name.lower() in ind.lower():
                    sr_=sec_df[sec_df["ticker"]==sec_tk]
                    if not sr_.empty: sec_rs_v=sr_.iloc[0]["rs"]; sec_n=sec_name; break
            for _,r in df[df["score"]>=min_sig].iterrows():
                if sig_filt=="🟢+🟡 Best" and not(r["premium"] or r["early_sig"]): continue
                elif sig_filt=="🟢 Premium" and not r["premium"]: continue
                elif sig_filt=="🟡 Early" and not r["early_sig"]: continue
                elif sig_filt=="🔵 S2 only" and (r["premium"] or r["early_sig"]): continue
                cross=f"{int(r['cross'])}w" if r.get("cross",-1)>=0 else "–"
                all_rows.append({"Signal":sig_icon(r.to_dict()),"Ticker":r["ticker"],
                    "Industry":ind,"Sector":sec_n,"Sec RS":fmt(sec_rs_v,"",1),
                    "Stage":r["stage"],"Score":f"{r['score']}/5",
                    "RS":fmt(r["rs"],"",1),"Price":fmt(r["price"]),
                    "%>SMA":fmt(r["pct_above"],"%",1),"Vol":fmt(r["vol"],"x",1),
                    "Base":f"{r['base_w']}w","Entry":entry_label(r.to_dict()),
                    "Cross":cross,"Stop":fmt(r["stop"]),"Risk":fmt(r["risk"],"%",1)})
        prog.empty()
        if all_rows:
            sf=pd.DataFrame(all_rows)
            sm1,sm2,sm3,sm4=st.columns(4)
            sm1.metric("Total",len(sf))
            sm2.metric("🟢 Premium",len(sf[sf["Signal"].str.contains("PREMIUM",na=False)]))
            sm3.metric("🟡 Early",  len(sf[sf["Signal"].str.contains("EARLY",  na=False)]))
            sm4.metric("🔵 S2",     len(sf[sf["Signal"].str.contains("S2",     na=False)]))
            st.dataframe(sf,width="stretch",hide_index=True,height=600)
            if is_logged_in:
                c1,c2=st.columns([3,1])
                with c1: pick=st.selectbox("Add to watchlist",["–"]+sf["Ticker"].tolist(),key="wl_indsig2",label_visibility="collapsed")
                with c2:
                    if st.button("➕ Watchlist",key="wlbtn_indsig2"):
                        if pick!="–": add_to_watchlist(user,pick,tag="signal"); st.toast(f"✓ {pick} added",icon="📌")
            st.download_button("⬇️ Export (.txt)",export_tv_lines(sf["Ticker"].tolist()),
                file_name="TV_industry_signals.txt",mime="text/plain",key="dl_indsig2")
        else:
            st.info("No signals found. Try lowering the minimum score or selecting more industries.")


# ══════════════════════════════════════
# TAB 4 — STAGE 1 WATCHLIST
# ══════════════════════════════════════
with tab_s1:
    st.markdown("---")
    st.markdown("### 👁 Stage 1 Watchlist — Bases Building")
    st.markdown(f"<p class='subtext'>40+ week bases with tight price action. Not buy signals — set TradingView alerts for SMA crossover on high volume.</p>",unsafe_allow_html=True)

    s1c1,s1c2,s1c3,s1c4=st.columns(4)
    min_base=s1c1.slider("Min base (weeks)",40,120,40,5,key="s1_base2")
    max_tight=s1c2.slider("Max tightness %",2.0,20.0,12.0,0.5,key="s1_tight2")
    sec_f=s1c3.selectbox("Sector",["All","Bullish only","Bearish only"],key="s1_sec2")
    s1_nyse=s1c4.toggle("Include NYSE+NASDAQ",value=False,key="s1_nyse2")

    with st.spinner("Scanning for Stage 1 bases…"):
        all_s1=[]
        for sec_tk,stocks in SECTOR_STOCKS.items():
            stk_df=scan_tickers(json.dumps(stocks),spx_close_json)
            if stk_df.empty: continue
            for _,r in stk_df.iterrows():
                if "Stage 1" not in r.get("stage",""): continue
                if r.get("base_w",0)<40: continue
                rd=r.to_dict(); rd["sec_tk"]=sec_tk; rd["sec_name"]=SECTORS.get(sec_tk,"")
                all_s1.append(rd)
        if s1_nyse:
            nyse_tks2=fetch_nyse_tickers()
            for r in scan_batch(json.dumps(nyse_tks2),spx_close_json,min_score=0,min_price=2.0):
                if "Stage 1" not in r.get("stage",""): continue
                if r.get("base_w",0)<40: continue
                all_s1.append(r)

    if not all_s1:
        st.info("No Stage 1 bases of 40+ weeks found.")
    else:
        s1_df=pd.DataFrame(all_s1)
        def get_sr(sec_tk):
            if not sec_tk: return None
            row=sec_df[sec_df["ticker"]==sec_tk]
            return float(row.iloc[0]["rs"]) if not row.empty else None
        if "sec_tk" in s1_df.columns: s1_df["sec_rs"]=s1_df["sec_tk"].apply(get_sr)
        else: s1_df["sec_rs"]=None

        s1_df=s1_df[s1_df["base_w"]>=min_base]
        if "base_tightness" in s1_df.columns:
            s1_df=s1_df[s1_df["base_tightness"].isna()|(s1_df["base_tightness"]<=max_tight)]
        if sec_f=="Bullish only": s1_df=s1_df[s1_df["sec_rs"].notna()&(s1_df["sec_rs"]>0)]
        elif sec_f=="Bearish only": s1_df=s1_df[s1_df["sec_rs"].notna()&(s1_df["sec_rs"]<=0)]
        if "base_tightness" in s1_df.columns:
            s1_df=s1_df.sort_values(["base_tightness","base_w"],ascending=[True,False],na_position="last")

        st.caption(f"{len(s1_df)} stocks found")
        if not s1_df.empty:
            top5=s1_df.head(5); cards=st.columns(min(5,len(top5)))
            for idx,(_,r) in enumerate(top5.iterrows()):
                sr=r.get("sec_rs"); sc=C["GREEN"] if(sr and sr>0) else C["RED"]
                tight=r.get("base_tightness")
                with cards[idx]:
                    st.markdown(f"""<div class="wcard" style="text-align:center;padding:12px 8px">
                      <div style="font-size:1.05rem;font-weight:800">🔵 {r['ticker']}</div>
                      <div style="color:{C['SUB']};font-size:0.72rem">{r.get('sec_name','–')}</div>
                      <div style="font-weight:700;margin:5px 0">{r['base_w']}w base</div>
                      <div style="font-size:0.77rem">Tight: <strong>{fmt(tight,'%',1) if tight else '–'}</strong></div>
                      <div style="font-size:0.73rem;color:{sc}">Sec RS: {fmt(sr,'',1)}</div>
                      <div style="font-size:0.7rem;color:{C['SUB']};margin-top:3px">Trigger: {fmt(r['sma50w'])}</div>
                    </div>""",unsafe_allow_html=True)
                    wl_btn(r["ticker"],f"s1card_{idx}")
            st.markdown("---")
            s1_rows=[]
            for _,r in s1_df.iterrows():
                sr=r.get("sec_rs"); tight=r.get("base_tightness")
                bq="⭐ Extremely tight" if tight and tight<5 else "✓ Clean" if tight and tight<8 else "~ Moderate" if tight and tight<12 else "✗ Wide"
                s1_rows.append({"Ticker":r["ticker"],"Sector":r.get("sec_name","–"),
                    "Sec RS":fmt(sr,"",1),"Base (wks)":r["base_w"],
                    "Tightness":fmt(tight,"%",1) if tight else "–","Quality":bq,
                    "Price":fmt(r["price"]),"vs SMA":fmt(r["pct_above"],"%",1),
                    "Stock RS":fmt(r["rs"],"",1),"Trigger":fmt(r["sma50w"])+" + vol"})
            st.dataframe(pd.DataFrame(s1_rows),width="stretch",hide_index=True,height=500)
            s1_tks=s1_df["ticker"].tolist()
            e1,e2=st.columns(2)
            with e1: st.code(export_tv(s1_tks),language=None)
            with e2: st.download_button("⬇️ Stage 1 (.txt)",export_tv_lines(s1_tks),
                file_name="TV_stage1.txt",mime="text/plain",key="dl_s1_2")

# ══════════════════════════════════════
# TAB 5 — DAILY TIMEFRAME
# ══════════════════════════════════════
with tab_daily:
    st.markdown("---")

    # Header with clear daily vs weekly distinction
    st.markdown("""
    <div style="background:linear-gradient(135deg,#4361ee22,transparent);
         border:1px solid #4361ee44;border-left:4px solid #4361ee;
         border-radius:12px;padding:16px 20px;margin-bottom:16px">
      <div style="font-size:1.1rem;font-weight:800">📅 Daily Timeframe Screener</div>
      <div style="font-size:0.82rem;color:#7b83a6;margin-top:4px;line-height:1.6">
        Uses <strong>daily bars + 50-day SMA</strong> instead of weekly bars + 50-week SMA.<br>
        Purpose: find stocks building <strong>daily bases</strong> that can swing trade within a weekly uptrend.<br>
        ⚠ Only meaningful for stocks already in <strong>weekly Stage 2</strong> — use this tab to time entries, not find setups.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Load daily SPX
    with st.spinner("Loading daily market data…"):
        spx_daily = get_spx_daily()

    if spx_daily.empty:
        st.error("Could not load SPY daily data.")
        if st.button("🔄 Retry", key="retry_daily"):
            st.cache_data.clear(); st.rerun()
    else:
        # Daily SPY status
        from utils.screener import evaluate_daily, fetch_daily_data
        spx_d_df = fetch_daily_data("SPY")
        spx_d_ev  = evaluate_daily(spx_d_df, spx_daily) if not spx_d_df.empty else {}

        d1,d2,d3,d4 = st.columns(4)
        d1.metric("SPY Daily Stage", spx_d_ev.get("stage","–"))
        d2.metric("Price",           fmt(spx_d_ev.get("price")))
        d3.metric("50d SMA",         fmt(spx_d_ev.get("sma50d")))
        d4.metric("% above 50d",     fmt(spx_d_ev.get("pct_above"),"%",1))

        spx_d_stage = spx_d_ev.get("stage","")
        if "Stage 2" in spx_d_stage:
            st.markdown(f'<div class="wcard-info">✓ SPY above rising 50d SMA — daily conditions favourable for entries.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="wcard-warn">⚠ SPY not in daily Stage 2. Risky to buy dips — wait for 50d SMA to stabilise.</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Controls
        dc1,dc2,dc3 = st.columns([2,2,2])
        with dc1:
            d_sec = st.selectbox("Sector/ETF", ["All"]+list(SECTORS.values()), key="d_sec")
        with dc2:
            d_min_score = st.selectbox("Min score", [0,1,2,3,4,5], index=3, key="d_minscore")
        with dc3:
            d_sig_filt = st.selectbox("Signal", ["All","🟢+🟡 Best","🟢 Premium","🟡 Early","🔵 Stage 2+"], key="d_sigfilt")

        # Build ticker list
        if d_sec == "All":
            d_tickers = []
            for tks in SECTOR_STOCKS.values():
                d_tickers += tks
            d_tickers = list(dict.fromkeys(d_tickers))
        else:
            sec_tk = next((k for k,v in SECTORS.items() if v==d_sec), None)
            d_tickers = SECTOR_STOCKS.get(sec_tk, [])

        spx_daily_json = spx_daily.to_json()

        with st.spinner(f"Scanning {len(d_tickers)} stocks on daily bars…"):
            d_df = scan_tickers_daily(json.dumps(d_tickers), spx_daily_json)

        if d_df.empty:
            st.info("No results. Try selecting a specific sector or lowering the minimum score.")
        else:
            d_df = d_df[d_df["score"] >= d_min_score]
            if d_sig_filt == "🟢+🟡 Best":   d_df = d_df[d_df["premium"]|d_df["early_sig"]]
            elif d_sig_filt == "🟢 Premium": d_df = d_df[d_df["premium"]]
            elif d_sig_filt == "🟡 Early":   d_df = d_df[d_df["early_sig"]]
            elif d_sig_filt == "🔵 Stage 2+":d_df = d_df[d_df["score"]>=4]

            # Metrics
            n_p=len(d_df[d_df["premium"]]); n_e=len(d_df[d_df["early_sig"]])
            em1,em2,em3,em4 = st.columns(4)
            em1.metric("Stocks", len(d_df))
            em2.metric("🟢 Premium (daily)", n_p)
            em3.metric("🟡 Early (daily)",   n_e)
            em4.metric("🔵 Stage 2+ (daily)", len(d_df[d_df["score"]>=4]))

            # Signal cards
            best = d_df[d_df["premium"]|d_df["early_sig"]]
            if not best.empty:
                st.markdown("#### 🚨 Daily Signals")
                for _,r in best.iterrows():
                    tag = "PREMIUM" if r["premium"] else "EARLY"
                    cls = "wcard-premium" if r["premium"] else "wcard-early"
                    col = "#4ade80" if r["premium"] else "#fbbf24"
                    cross = f"{int(r['cross'])}d ago" if r.get("cross",-1)>=0 else "–"
                    st.markdown(f"""<div class="{cls}">
                        <span style="color:{col};font-weight:700">[DAILY] {tag}</span> &nbsp;
                        <strong>{r['ticker']}</strong> &nbsp;·&nbsp;
                        Crossed 50d {cross} &nbsp;·&nbsp; Base {r['base_d']}d &nbsp;·&nbsp;
                        RS {fmt(r['rs'],'',1)} &nbsp;·&nbsp; Vol {fmt(r['vol'],'x',1)} &nbsp;·&nbsp;
                        Stop {fmt(r['stop'])} ({fmt(r['risk'],'%',1)})
                    </div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("#### Full Daily Results")
            st.markdown(f"<p class='subtext'>📅 Daily bars · 50-day SMA · RS vs SPX daily · Crossover window = 12 days</p>", unsafe_allow_html=True)

            rows_d = []
            for _,r in d_df.iterrows():
                cross = f"{int(r['cross'])}d" if r.get("cross",-1)>=0 else "–"
                sig = "🟢 PREM" if r["premium"] else "🟡 EARLY" if r["early_sig"] else "🔵 S2" if r["score"]>=4 else ""
                rows_d.append({
                    "Signal":    sig,
                    "Ticker":    r["ticker"],
                    "D.Stage":   r["stage"],
                    "Score":     f"{r['score']}/5",
                    "RS":        fmt(r["rs"],"",1),
                    "Price":     fmt(r["price"]),
                    "%>50d":     fmt(r["pct_above"],"%",1),
                    "Vol":       fmt(r["vol"],"x",1),
                    "Base(d)":   r["base_d"],
                    "Cross":     cross,
                    "Stop":      fmt(r["stop"]),
                    "Risk":      fmt(r["risk"],"%",1),
                })
            st.dataframe(pd.DataFrame(rows_d), width="stretch", hide_index=True, height=600)

            # Watchlist add
            if is_logged_in and not d_df.empty:
                wc1,wc2 = st.columns([3,1])
                with wc1:
                    d_pick = st.selectbox("Add to watchlist",["–"]+d_df["ticker"].tolist(),
                                          key="d_wl_pick",label_visibility="collapsed")
                with wc2:
                    if st.button("➕ Watchlist",key="d_wl_btn"):
                        if d_pick!="–":
                            add_to_watchlist(user,d_pick,tag="daily")
                            st.toast(f"✓ {d_pick} added (daily setup)",icon="📅")

            # Export
            d_tks = d_df["ticker"].tolist()
            best_tks = d_df[d_df["premium"]|d_df["early_sig"]]["ticker"].tolist()
            ex1,ex2 = st.columns(2)
            with ex1:
                st.download_button("⬇️ All daily signals (.txt)", export_tv_lines(d_tks),
                    file_name="TV_daily_signals.txt", mime="text/plain", key="dl_daily_all")
            with ex2:
                if best_tks:
                    st.download_button("⬇️ Best daily (.txt)", export_tv_lines(best_tks),
                        file_name="TV_daily_best.txt", mime="text/plain", key="dl_daily_best")

        st.markdown("""
        <div style="margin-top:16px;padding:12px 16px;background:#fbbf2411;border:1px solid #fbbf2433;
             border-radius:8px;font-size:0.8rem;color:#7b83a6">
          <strong>📅 Daily vs 📊 Weekly — what's the difference?</strong><br>
          Weekly Stage 2 = stock is in a multi-month or multi-year uptrend. Buy on pullbacks to 50w SMA.<br>
          Daily Stage 2 = stock has crossed its 50d SMA recently. Good for swing entries within a weekly uptrend.<br>
          Best setup: Weekly Stage 2 ✓ + Daily Early signal ✓ = high-conviction swing entry.
        </div>""", unsafe_allow_html=True)


# ── Legend ──────────────────────────────────────────────────
with st.expander("📖 Legend"):
    st.markdown("""
| Term | Meaning |
|---|---|
| **🟢 PREMIUM** | Crossover ≤8w + SMA rising + RS positive + volume ≥1.5x + base ≥40w |
| **🟡 EARLY** | Crossover ≤8w + SMA rising + RS positive + volume confirmed |
| **🔵 S2** | Stage 2 but no recent crossover — move underway |
| **Entry** | Weeks ago since 50w SMA crossover |
| **RRG** | Leading=strong RS+rising; Weakening=strong but fading; Improving=weak but recovering; Lagging=weak+falling |
| **Tightness** | Std dev of price vs SMA in base. <5%=very tight; 5-8%=clean; >12%=wide |
| **➕** | Add to watchlist (sign in required) |
""")

st.markdown(f"<p class='subtext'>Data cached 7 days · {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} UTC · Weekly closes (Fri) · Not financial advice</p>",unsafe_allow_html=True)
