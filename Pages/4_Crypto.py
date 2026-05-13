"""
pages/5_Crypto.py — Crypto Stage Screener
==========================================
- Top 300 coins via CoinGecko free API
- Daily timeframe (50-day SMA)
- Relative Strength vs BTC
- Weinstein Stage Analysis adapted for crypto
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import yfinance as yf
import json
import time
from datetime import datetime, timedelta
from io import StringIO
import urllib.request
import urllib.error
from utils.theme import page_config, inject_css, get_colors
from utils.screener import fmt, rs_tag, sig_icon, export_tv, export_tv_lines

page_config("Crypto · Weinstein V6")
inject_css()
C = get_colors()

# ── Config ────────────────────────────────────────────────────
SMA_DAYS            = 50
RS_MA_DAYS          = 10
SMA_SLOPE_LB        = 10
BREAKOUT_LB         = 365   # 1 year high
MAX_ABOVE_SMA       = 0.50  # crypto can run more than stocks
RECENT_CROSS_DAYS   = 12    # ~2 weeks
VOL_AVG_DAYS        = 20
VOL_BREAKOUT_MULT   = 1.5
SLOPE_THRESHOLD     = 0.0003
YEARS_DATA          = 2
BENCHMARK           = "BTC-USD"

# ── CoinGecko top coins ───────────────────────────────────────

# ── Hardcoded top 300 coins (fallback if CoinGecko unavailable) ──
TOP_COINS_FALLBACK = [
    ("btc","Bitcoin",1300e9),("eth","Ethereum",380e9),("usdt","Tether",120e9),
    ("bnb","BNB",85e9),("sol","Solana",78e9),("xrp","XRP",73e9),
    ("usdc","USD Coin",45e9),("doge","Dogecoin",42e9),("ada","Cardano",28e9),
    ("avax","Avalanche",22e9),("trx","TRON",20e9),("dot","Polkadot",18e9),
    ("link","Chainlink",16e9),("matic","Polygon",14e9),("shib","Shiba Inu",13e9),
    ("dai","Dai",12e9),("uni","Uniswap",11e9),("atom","Cosmos",10e9),
    ("ltc","Litecoin",9.5e9),("etc","Ethereum Classic",8e9),("near","NEAR",7.5e9),
    ("apt","Aptos",7e9),("xlm","Stellar",6.5e9),("okb","OKB",6e9),
    ("algo","Algorand",5.5e9),("hbar","Hedera",5e9),("fil","Filecoin",4.8e9),
    ("arb","Arbitrum",4.5e9),("op","Optimism",4.2e9),("inj","Injective",4e9),
    ("sui","Sui",3.8e9),("imx","Immutable",3.5e9),("vet","VeChain",3.3e9),
    ("aave","Aave",3.1e9),("qnt","Quant",3e9),("sand","The Sandbox",2.8e9),
    ("mana","Decentraland",2.6e9),("axs","Axie Infinity",2.5e9),("theta","Theta",2.4e9),
    ("grt","The Graph",2.3e9),("eos","EOS",2.2e9),("xmr","Monero",2.1e9),
    ("cake","PancakeSwap",2e9),("crv","Curve",1.9e9),("ldo","Lido",1.8e9),
    ("egld","MultiversX",1.7e9),("ape","ApeCoin",1.6e9),("mkr","Maker",1.5e9),
    ("xtz","Tezos",1.4e9),("rune","THORChain",1.3e9),("stx","Stacks",1.2e9),
    ("snx","Synthetix",1.1e9),("ftm","Fantom",1e9),("neo","NEO",0.9e9),
    ("kava","Kava",0.85e9),("flow","Flow",0.8e9),("zil","Zilliqa",0.75e9),
    ("bat","Basic Attention",0.7e9),("1inch","1inch",0.65e9),("comp","Compound",0.6e9),
    ("enj","Enjin",0.55e9),("chz","Chiliz",0.5e9),("hot","Holo",0.48e9),
    ("waves","Waves",0.45e9),("iota","IOTA",0.43e9),("dash","Dash",0.42e9),
    ("zec","Zcash",0.4e9),("ren","Ren",0.35e9),("bal","Balancer",0.33e9),
    ("yfi","yearn.finance",0.32e9),("sushi","SushiSwap",0.3e9),("uma","UMA",0.28e9),
    ("dgb","DigiByte",0.27e9),("sc","Siacoin",0.26e9),("zen","Horizen",0.25e9),
    ("ont","Ontology",0.24e9),("iost","IOST",0.23e9),("nano","Nano",0.22e9),
    ("storj","Storj",0.21e9),("lrc","Loopring",0.2e9),("ankr","Ankr",0.19e9),
    ("celr","Celer",0.18e9),("ctsi","Cartesi",0.17e9),("band","Band",0.16e9),
    ("reef","Reef",0.15e9),("ray","Raydium",0.14e9),("mngo","Mango",0.13e9),
    ("sol2","Solana2",0.1e9),("tia","Celestia",3.5e9),("sei","Sei",2.5e9),
    ("jup","Jupiter",2.2e9),("wif","dogwifhat",2e9),("bonk","Bonk",1.8e9),
    ("pyth","Pyth",1.5e9),("jto","Jito",1.3e9),("wen","Wen",0.5e9),
    ("blur","Blur",0.8e9),("pendle","Pendle",0.7e9),("rdnt","Radiant",0.4e9),
    ("gmx","GMX",0.6e9),("dydx","dYdX",0.5e9),("perp","Perpetual",0.2e9),
    ("people","ConstitutionDAO",0.3e9),("bico","Biconomy",0.25e9),
]

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def fetch_top_coins(limit: int = 300) -> list:
    """
    Try CoinGecko API first, fall back to hardcoded list.
    Returns list of dicts with symbol, name, market_cap.
    """
    # Try CoinGecko
    coins = []
    per_page = 250
    pages = (limit // per_page) + 1
    for page in range(1, pages + 1):
        url = (
            f"https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&order=market_cap_desc"
            f"&per_page={min(per_page, limit - len(coins))}"
            f"&page={page}&sparkline=false"
        )
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            if isinstance(data, list) and data:
                coins += data
                if len(coins) >= limit: break
                time.sleep(1.5)
            else:
                break
        except Exception:
            break

    if len(coins) >= 10:
        return coins[:limit]

    # Fallback: hardcoded list
    fallback = []
    for sym, name, mc in TOP_COINS_FALLBACK[:limit]:
        fallback.append({"symbol": sym, "name": name, "market_cap": mc})
    return fallback


def coin_to_yf(symbol: str) -> str:
    """Convert CoinGecko symbol to yfinance ticker."""
    # Special cases
    overrides = {
        "BTC": "BTC-USD", "ETH": "ETH-USD", "BNB": "BNB-USD",
        "SOL": "SOL-USD", "XRP": "XRP-USD", "ADA": "ADA-USD",
        "DOGE": "DOGE-USD", "DOT": "DOT-USD", "AVAX": "AVAX-USD",
        "MATIC": "MATIC-USD", "LINK": "LINK-USD", "UNI": "UNI-USD",
        "ATOM": "ATOM-USD", "LTC": "LTC-USD", "ETC": "ETC-USD",
        "XLM": "XLM-USD", "ALGO": "ALGO-USD", "VET": "VET-USD",
        "FIL": "FIL-USD", "TRX": "TRX-USD", "NEAR": "NEAR-USD",
        "FTM": "FTM-USD", "SAND": "SAND-USD", "MANA": "MANA-USD",
        "SHIB": "SHIB-USD", "CRO": "CRO-USD", "HBAR": "HBAR-USD",
        "EGLD": "EGLD-USD", "APE": "APE-USD", "OP": "OP-USD",
        "ARB": "ARB-USD", "SUI": "SUI-USD", "SEI": "SEI-USD",
        "INJ": "INJ-USD", "TIA": "TIA-USD", "JTO": "JTO-USD",
    }
    sym = symbol.upper()
    return overrides.get(sym, f"{sym}-USD")


# ── Daily data fetching ───────────────────────────────────────

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def fetch_daily(ticker: str, years: int = YEARS_DATA) -> pd.DataFrame:
    end   = datetime.today()
    start = end - timedelta(days=years * 365 + 30)
    try:
        df = yf.download(ticker, start=start, end=end, interval="1d",
                         auto_adjust=True, progress=False, threads=False)
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return pd.DataFrame()


# ── Indicators (daily) ────────────────────────────────────────

def _sma(s, w): return s.rolling(w).mean()

def _slope(s, lb):
    v = s.dropna().iloc[-lb:]
    if len(v) < lb: return np.nan
    slope, _ = np.polyfit(np.arange(len(v)), v.values, 1)
    return slope / (abs(v.iloc[-1]) or 1)

def _rs_line(a, b):
    c = pd.concat([a, b], axis=1).dropna()
    return c.iloc[:,0] / c.iloc[:,1]

def _rs_score(rs, w=RS_MA_DAYS):
    if len(rs) < w + 5: return np.nan
    rm = _sma(rs, w)
    if pd.isna(rm.iloc[-1]) or rm.iloc[-1] == 0: return np.nan
    above = (rs.iloc[-1] / rm.iloc[-1]) - 1
    past  = rs.iloc[-(w+1)]
    if past == 0 or pd.isna(past): return np.nan
    return round((above + (rs.iloc[-1]/past - 1)) * 100, 2)

def _detect_cross(price, ma, days):
    c = pd.concat([price, ma], axis=1).dropna().iloc[-(days+5):]
    if len(c) < 2: return -1
    above = (c.iloc[:,0] > c.iloc[:,1]).values
    for i in range(len(above)-1, 0, -1):
        if above[i] and not above[i-1]:
            d = len(above)-1-i
            return d if d <= days else -1
    return -1

def _base_days(close, ma, cross_d):
    if cross_d < 0:
        c = pd.concat([close, ma], axis=1).dropna()
        if c.empty: return 0
        days = 0
        for i in range(len(c)-1, -1, -1):
            p, m = c.iloc[i,0], c.iloc[i,1]
            if pd.isna(m) or m == 0: break
            if abs(p/m - 1) <= 0.12: days += 1
            else: break
        return days
    bx = len(close)-1-cross_d
    if bx < 5: return 0
    bp = float(close.iloc[bx])
    base_start = 0
    for i in range(bx-1, -1, -1):
        if float(close.iloc[i]) >= bp * 0.88:
            base_start = i; break
    return bx - base_start

def _calc_stop(close, ma):
    cp = float(close.iloc[-1]); cm = float(ma.iloc[-1])
    sl = float(close.iloc[-14:].min())
    cands = [v for v in [cm, sl] if v < cp and not pd.isna(v)]
    if not cands: return None, None
    stop = max(cands)
    return round(stop, 4), round((stop/cp - 1)*100, 1)

def _stage(price, ma, slope):
    if pd.isna(ma.iloc[-1]) or pd.isna(slope): return "Unknown"
    ab = price.iloc[-1] > ma.iloc[-1]
    if ab and slope > SLOPE_THRESHOLD:       return "Stage 2"
    if ab and slope <= SLOPE_THRESHOLD:      return "Stage 3"
    if not ab and slope < -SLOPE_THRESHOLD:  return "Stage 4"
    return "Stage 1"


# ── Evaluate (daily) ──────────────────────────────────────────

def evaluate_crypto(df: pd.DataFrame, btc_close: pd.Series, symbol: str = "") -> dict:
    r = dict(price=None, sma50d=None, pct_above=None,
             above_sma=False, sma_rising=False, rs_up=False,
             near_high=False, not_extended=False,
             rs=None, stage="Unknown", cross=-1,
             vol=None, vol_ok=False, base_d=0,
             stop=None, risk=None, score=0, label="Not Stage 2",
             early_sig=False, premium=False, symbol=symbol)

    if df.empty or len(df) < SMA_DAYS + 5: return r

    close  = df["Close"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series(dtype=float)

    ma50  = _sma(close, SMA_DAYS)
    cp, cm = float(close.iloc[-1]), float(ma50.iloc[-1])
    if pd.isna(cm): return r

    r["price"]     = round(cp, 6)
    r["sma50d"]    = round(cm, 6)
    pct            = (cp/cm) - 1
    r["pct_above"] = round(pct*100, 1)

    slope = _slope(ma50, SMA_SLOPE_LB)
    r["above_sma"]  = cp > cm
    r["sma_rising"] = not pd.isna(slope) and slope > SLOPE_THRESHOLD

    # RS vs BTC
    rs = _rs_line(close, btc_close)
    sc = _rs_score(rs)
    r["rs"]    = sc
    r["rs_up"] = not pd.isna(sc) and sc > 0

    # Near 1-year high
    wh = float(close.iloc[-BREAKOUT_LB:].max()) if len(close) >= BREAKOUT_LB else float(close.max())
    r["near_high"]    = (cp/wh)-1 >= -0.15
    r["not_extended"] = 0 < pct < MAX_ABOVE_SMA

    r["stage"] = _stage(close, ma50, slope)

    cross = _detect_cross(close, ma50, RECENT_CROSS_DAYS)
    r["cross"] = cross

    # Volume
    if not volume.empty and len(volume) >= VOL_AVG_DAYS + 5:
        if cross >= 0:
            idx = len(volume)-1-cross
            if idx >= VOL_AVG_DAYS:
                bv = float(volume.iloc[idx])
                bl = float(volume.iloc[idx-VOL_AVG_DAYS:idx].mean())
                r["vol"] = round(bv/bl, 2) if bl > 0 else None
        if r["vol"] is None:
            bl = float(volume.iloc[-(VOL_AVG_DAYS+5):-5].mean())
            rc = float(volume.iloc[-5:].mean())
            r["vol"] = round(rc/bl, 2) if bl > 0 else None
    r["vol_ok"] = r["vol"] is not None and r["vol"] >= VOL_BREAKOUT_MULT

    bd = _base_days(close, ma50, cross)
    r["base_d"] = bd
    r["stop"], r["risk"] = _calc_stop(close, ma50)

    r["score"] = sum([r["above_sma"], r["sma_rising"], r["rs_up"],
                      r["near_high"], r["not_extended"]])
    labels = {5:"STRONG Stage 2", 4:"Stage 2", 3:"Borderline"}
    r["label"]     = labels.get(r["score"], "Not Stage 2")
    r["early_sig"] = (cross >= 0 and cross <= RECENT_CROSS_DAYS
                      and r["sma_rising"] and r["rs_up"] and r["vol_ok"])
    r["premium"]   = r["early_sig"] and bd >= 30
    return r


def sig_icon_c(r):
    if r.get("premium"):      return "🟢 PREMIUM"
    if r.get("early_sig"):    return "🟡 EARLY"
    if r.get("score",0) >= 4: return "🔵 S2"
    return ""


# ── Cached full scan ──────────────────────────────────────────

@st.cache_data(ttl=7*24*3600, show_spinner=False)
def run_crypto_scan(symbols_json: str, btc_close_json: str, min_score: int = 0) -> list:
    symbols   = json.loads(symbols_json)
    btc_close = pd.read_json(StringIO(btc_close_json), typ="series")
    results   = []
    for sym, name, mc in symbols:
        yf_ticker = coin_to_yf(sym)
        df = fetch_daily(yf_ticker)
        if df.empty: continue
        ev = evaluate_crypto(df, btc_close, sym)
        if ev["score"] < min_score: continue
        ev["name"] = name
        ev["mcap"] = mc
        ev["yf_ticker"] = yf_ticker
        results.append(ev)
    results.sort(key=lambda x: (
        -int(x.get("premium", False)),
        -int(x.get("early_sig", False)),
        -x.get("score", 0),
        -(x.get("rs") or -99)
    ))
    return results


# ══════════════════════════════════════
# UI
# ══════════════════════════════════════

st.markdown("# ₿ Crypto Screener")
st.markdown(f"<p class='subtext'>Top 300 coins · 50-day SMA · Relative Strength vs BTC · Daily timeframe · Weinstein Stage Analysis</p>",
            unsafe_allow_html=True)
st.markdown("---")

# Controls
c1, c2, c3, c4 = st.columns(4)
with c1:
    n_coins = st.selectbox("Universe", [50, 100, 200, 300], index=1,
                            help="Top N coins by market cap")
with c2:
    min_score_c = st.selectbox("Min score", [0,1,2,3,4,5], index=2, key="crypto_min")
with c3:
    sig_filt = st.selectbox("Signal filter",
                             ["All","🟢+🟡 Best","🟢 Premium","🟡 EARLY","🔵 Stage 2+"],
                             key="crypto_sig")
with c4:
    mcap_min_c = st.number_input("Min market cap ($M)", min_value=0.0,
                                  value=100.0, step=50.0,
                                  help="Filter out micro-caps")

# BTC benchmark
st.markdown("---")
with st.spinner("Loading BTC benchmark…"):
    btc_df = fetch_daily(BENCHMARK)

if btc_df.empty:
    st.error("Could not load BTC data. Check your connection.")
    st.stop()

btc_close = btc_df["Close"]

# BTC status
btc_ev = evaluate_crypto(btc_df, btc_close, "BTC")
btc_sma = float(_sma(btc_close, SMA_DAYS).iloc[-1])

bm1,bm2,bm3,bm4,bm5 = st.columns(5)
bm1.metric("BTC Stage",    btc_ev["stage"])
bm2.metric("BTC Price",    f"${btc_ev['price']:,.0f}")
bm3.metric("50d SMA",      f"${btc_sma:,.0f}")
bm4.metric("% above SMA",  fmt(btc_ev["pct_above"],"%",1))
bm5.metric("Stage Score",  f"{btc_ev['score']}/5")

if "Stage 2" not in btc_ev["stage"]:
    st.markdown(f'<div class="wcard-warn">⚠ <strong>BTC not in Stage 2.</strong> Altcoin signals are less reliable in a BTC downtrend.</div>', unsafe_allow_html=True)
elif (btc_ev["pct_above"] or 0) > 20:
    st.markdown(f'<div class="wcard-warn" style="border-left-color:{C["YELLOW"]}">⚡ <strong>BTC extended</strong> ({btc_ev["pct_above"]:.1f}% above 50d SMA). Fresh entries carry higher reversal risk.</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="wcard-info">✓ <strong>BTC in Stage 2.</strong> Altcoin signals are valid.</div>', unsafe_allow_html=True)

st.markdown("---")

# Load coins
st.markdown("### Top Crypto by Market Cap")
with st.spinner(f"Fetching top {n_coins} coins from CoinGecko…"):
    coins = fetch_top_coins(n_coins)

if not coins:
    st.error("Could not load coin list from CoinGecko. API may be rate-limited — try again in a minute.")
    st.stop()

# Apply mcap filter
coins_filtered = [c for c in coins
                  if (c.get("market_cap") or 0) >= mcap_min_c * 1e6]

st.markdown(f"<p class='subtext'>{len(coins_filtered)} coins after ${mcap_min_c:.0f}M market cap filter</p>",
            unsafe_allow_html=True)

# Run scan
symbols_list = [(c["symbol"], c["name"], c.get("market_cap",0)) for c in coins_filtered]
btc_close_json = btc_close.to_json()

with st.spinner(f"Scanning {len(symbols_list)} coins… (cached 7 days after first run)"):
    results = run_crypto_scan(
        json.dumps(symbols_list),
        btc_close_json,
        min_score=min_score_c
    )

if not results:
    st.info("No coins found with current filters.")
    st.stop()

# Apply signal filter
df_crypto = pd.DataFrame(results)
if sig_filt == "🟢+🟡 Best":   df_crypto = df_crypto[df_crypto["premium"]|df_crypto["early_sig"]]
elif sig_filt == "🟢 Premium": df_crypto = df_crypto[df_crypto["premium"]]
elif sig_filt == "🟡 EARLY":   df_crypto = df_crypto[df_crypto["early_sig"]]
elif sig_filt == "🔵 Stage 2+":df_crypto = df_crypto[df_crypto["score"]>=4]

# Summary metrics
n_p = len(df_crypto[df_crypto["premium"]])
n_e = len(df_crypto[df_crypto["early_sig"]])
n_s = len(df_crypto[df_crypto["score"]>=4])

sm1,sm2,sm3,sm4,sm5 = st.columns(5)
sm1.metric("Coins shown",   len(df_crypto))
sm2.metric("🟢 Premium",    n_p)
sm3.metric("🟡 Early",      n_e)
sm4.metric("🔵 Stage 2+",   n_s)
sm5.metric("Scanned",       len(results))

# Signal cards
if n_p > 0 or n_e > 0:
    st.markdown("---")
    st.markdown("#### 🚨 Active Signals")
    for _, r in df_crypto[df_crypto["premium"]|df_crypto["early_sig"]].iterrows():
        tag  = "PREMIUM" if r["premium"] else "EARLY"
        cls  = "wcard-premium" if r["premium"] else "wcard-early"
        col  = C["GREEN"] if r["premium"] else C["YELLOW"]
        cross_str = f"{int(r['cross'])}d ago" if r.get("cross",-1)>=0 else "–"
        mc_str = f"${r['mcap']/1e9:.1f}B" if r.get("mcap",0)>=1e9 else f"${r['mcap']/1e6:.0f}M"
        st.markdown(f"""<div class="{cls}">
            <span style="color:{col};font-weight:700">{tag}</span> &nbsp;
            <strong>{r['symbol'].upper()}</strong> {r.get('name','')} &nbsp;·&nbsp;
            Crossed {cross_str} &nbsp;·&nbsp; Base {r['base_d']}d &nbsp;·&nbsp;
            RS vs BTC: {fmt(r['rs'],'',1)} &nbsp;·&nbsp;
            Vol: {fmt(r['vol'],'x',1)} &nbsp;·&nbsp;
            MCap: {mc_str}
        </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── Crypto RRG ────────────────────────────────────────────────
with st.expander("📡 Crypto Relative Rotation Graph — vs BTC", expanded=False):
    st.markdown(f"<p class='subtext'>X = RS 3M vs BTC · Y = Momentum (1W vs 3M trend) · Top 50 coins by market cap · Click to highlight</p>",
                unsafe_allow_html=True)

    rrg_coins = sorted(results, key=lambda x: x.get("mcap",0), reverse=True)[:50]
    rrg_coins = [r for r in rrg_coins if r.get("rs") is not None]

    if rrg_coins:
        @st.cache_data(ttl=7*24*3600, show_spinner=False)
        def get_coin_rs_data(tickers_json, btc_json):
            from io import StringIO as _SIO
            import json as _json
            tickers = _json.loads(tickers_json)
            btc = pd.read_json(_SIO(btc_json), typ="series")
            # Clean BTC index
            btc.index = pd.to_datetime(btc.index)
            try: btc.index = btc.index.tz_localize(None)
            except: 
                try: btc.index = btc.index.tz_convert(None)
                except: pass
            btc.index = btc.index.normalize()
            result = {}
            for tk in tickers:
                try:
                    df = yf.download(tk, period="4mo", interval="1d",
                                     auto_adjust=True, progress=False, threads=False)
                    if df.empty or len(df) < 10: continue
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                    close = df["Close"].copy()
                    close.index = pd.to_datetime(close.index)
                    try: close.index = close.index.tz_localize(None)
                    except:
                        try: close.index = close.index.tz_convert(None)
                        except: pass
                    close.index = close.index.normalize()
                    btc_a = btc.reindex(close.index, method="ffill").dropna()
                    close_a = close.reindex(btc_a.index).dropna()
                    if len(close_a) < 10: continue
                    n3 = min(63, len(close_a)-1); n1 = min(5, len(close_a)-1)
                    rs3m = ((close_a.iloc[-1]/close_a.iloc[-n3-1]) / (btc_a.iloc[-1]/btc_a.iloc[-n3-1]) - 1)*100
                    rs1w = ((close_a.iloc[-1]/close_a.iloc[-n1-1]) / (btc_a.iloc[-1]/btc_a.iloc[-n1-1]) - 1)*100
                    result[tk] = {"rs3m": round(float(rs3m),2), "rs1w": round(float(rs1w),2)}
                except: continue
            return result

        yf_tks = [coin_to_yf(r["symbol"]) for r in rrg_coins]
        with st.spinner("Computing RS momentum for top 50 coins…"):
            rs_data = get_coin_rs_data(json.dumps(yf_tks), btc_close.to_json())

        rrg_x,rrg_y,rrg_labels,rrg_colors = [],[],[],[]
        for r in rrg_coins:
            tk = coin_to_yf(r["symbol"])
            if tk not in rs_data: continue
            x = rs_data[tk]["rs3m"]
            y = rs_data[tk]["rs1w"] - (x/12)
            rrg_x.append(x); rrg_y.append(y)
            rrg_labels.append(r["symbol"].upper())
            rrg_colors.append(
                "rgba(74,222,128,0.9)"  if x>0 and y>0 else
                "rgba(251,191,36,0.9)"  if x>0 else
                "rgba(96,165,250,0.9)"  if y>0 else
                "rgba(248,113,113,0.9)")

        if rrg_x:
            mx=max(abs(v) for v in rrg_x+[1])*1.2; my=max(abs(v) for v in rrg_y+[1])*1.2
            fig_cr=go.Figure()
            for xr,yr,col in [(mx,my,"rgba(74,222,128,0.05)"),(mx,-my,"rgba(251,191,36,0.05)"),
                              (-mx,-my,"rgba(248,113,113,0.05)"),(-mx,my,"rgba(96,165,250,0.05)")]:
                fig_cr.add_shape(type="rect",x0=0 if xr>0 else xr,y0=0 if yr>0 else yr,
                    x1=xr if xr>0 else 0,y1=yr if yr>0 else 0,fillcolor=col,line_width=0)
            fig_cr.add_hline(y=0,line_color="#2d3149",line_width=1)
            fig_cr.add_vline(x=0,line_color="#2d3149",line_width=1)
            for lb,xp,yp in [("LEADING",0.75,0.85),("WEAKENING",0.75,-0.85),
                              ("IMPROVING",-0.75,0.85),("LAGGING",-0.75,-0.85)]:
                fig_cr.add_annotation(x=mx*xp,y=my*yp,text=lb,showarrow=False,
                    font=dict(size=9,color="#2d3149"),opacity=0.5)
            fig_cr.add_trace(go.Scatter(x=rrg_x,y=rrg_y,mode="markers+text",
                text=rrg_labels,textposition="top center",textfont=dict(size=9),
                marker=dict(color=rrg_colors,size=12,line=dict(width=1,color="#2d3149")),
                hovertemplate="<b>%{text}</b><br>RS 3M vs BTC: %{x:.1f}%<br>Momentum: %{y:.1f}<extra></extra>"))
            fig_cr.update_layout(height=500,margin=dict(l=0,r=0,t=10,b=0),
                paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter"),
                xaxis=dict(title="RS 3M vs BTC (%)",showgrid=True,gridcolor="#2d3149",zeroline=False),
                yaxis=dict(title="Momentum",showgrid=True,gridcolor="#2d3149",zeroline=False),
                showlegend=False)

            cr_event = st.plotly_chart(fig_cr, width="stretch",
                                        on_select="rerun", key="rrg_crypto")
            if cr_event and hasattr(cr_event,"selection") and cr_event.selection.get("points"):
                clicked = cr_event.selection["points"][0].get("text","")
                if clicked:
                    st.session_state["crypto_highlight"] = clicked
                    st.toast(f"📍 {clicked} highlighted in table below", icon="₿")

            leading = [(rrg_labels[i],rrg_x[i],rrg_y[i]) for i in range(len(rrg_x)) if rrg_x[i]>0 and rrg_y[i]>0]
            if leading:
                leading.sort(key=lambda x: x[1]+x[2], reverse=True)
                st.markdown("**🟢 Leading (outperforming BTC + positive momentum):** "
                           + ", ".join(f"**{c[0]}**" for c in leading[:10]))
            improving = [(rrg_labels[i],rrg_x[i],rrg_y[i]) for i in range(len(rrg_x)) if rrg_x[i]<=0 and rrg_y[i]>0]
            if improving:
                improving.sort(key=lambda x: x[2], reverse=True)
                st.markdown("**🔵 Improving (weak RS but recovering):** "
                           + ", ".join(f"**{c[0]}**" for c in improving[:8]))
        else:
            st.info("Not enough RS data to build RRG.")

st.markdown("---")

# Full table
st.markdown("#### Full Ranking")
rows = []
for _, r in df_crypto.iterrows():
    cross_str = f"{int(r['cross'])}d" if r.get("cross",-1)>=0 else "–"
    mc = r.get("mcap",0)
    mc_str = f"${mc/1e9:.1f}B" if mc>=1e9 else f"${mc/1e6:.0f}M" if mc>0 else "–"
    rows.append({
        "Signal":       sig_icon_c(r.to_dict()),
        "Symbol":       r["symbol"].upper(),
        "Name":         r.get("name",""),
        "Mkt Cap":      mc_str,
        "Price":        fmt(r["price"],"",4) if (r["price"] or 0) < 1 else fmt(r["price"],"",2),
        "%>50d SMA":    fmt(r["pct_above"],"%",1),
        "RS vs BTC":    fmt(r["rs"],"",1),
        "RS Trend":     rs_tag(r["rs"]),
        "Vol":          fmt(r["vol"],"x",1),
        "Base (days)":  r["base_d"],
        "Cross":        cross_str,
        "Stage":        r["stage"],
        "Score":        f"{r['score']}/5",
        "Stop":         fmt(r["stop"],"",4) if (r.get("stop") or 1) < 1 else fmt(r["stop"],"",2),
        "Risk":         fmt(r["risk"],"%",1),
    })

st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=600)

# Export
st.markdown("---")
st.markdown("#### 📤 Export")
ex1, ex2, ex3 = st.columns(3)

all_syms   = [r["symbol"].upper() for _, r in df_crypto.iterrows()]
best_syms  = [r["symbol"].upper() for _, r in df_crypto[df_crypto["premium"]|df_crypto["early_sig"]].iterrows()]
yf_tickers = [r.get("yf_ticker", coin_to_yf(r["symbol"])) for _, r in df_crypto.iterrows()]

with ex1:
    st.caption("All shown coins (yfinance)")
    st.code(export_tv(yf_tickers[:30]), language=None)
    st.download_button("⬇️ All (.txt)", export_tv_lines(yf_tickers),
                       file_name="TV_crypto_all.txt", mime="text/plain", key="dl_crypto_all")
with ex2:
    best_yf = [r.get("yf_ticker", coin_to_yf(r["symbol"])) for _, r in
               df_crypto[df_crypto["premium"]|df_crypto["early_sig"]].iterrows()]
    st.caption("PREMIUM + EARLY only")
    st.code(export_tv(best_yf) if best_yf else "–", language=None)
    if best_yf:
        st.download_button("⬇️ Best signals (.txt)", export_tv_lines(best_yf),
                           file_name="TV_crypto_best.txt", mime="text/plain", key="dl_crypto_best")
with ex3:
    st.caption("Symbol names only")
    st.code(",".join(all_syms[:30]), language=None)
    st.download_button("⬇️ Symbols (.txt)", "\n".join(all_syms),
                       file_name="crypto_symbols.txt", mime="text/plain", key="dl_crypto_sym")

# Legend
with st.expander("📖 Crypto Screener Guide"):
    st.markdown(f"""
| Term | Meaning |
|---|---|
| **50d SMA** | 50-day Simple Moving Average — same Weinstein principle as stocks but on daily bars |
| **RS vs BTC** | Relative Strength of the coin vs Bitcoin. Positive = outperforming BTC |
| **Stage 2** | Price above rising 50d SMA, RS vs BTC positive, near highs, not overextended |
| **PREMIUM** | Recent crossover (≤12 days) + SMA rising + RS positive + volume confirmed + base ≥30 days |
| **EARLY** | Recent crossover (≤12 days) + SMA rising + RS positive + volume confirmed |
| **Base (days)** | How long price consolidated before the current breakout |
| **Stop** | Max of 50d SMA and 14-day low |
| **Note** | Crypto is far more volatile than stocks. Stage analysis still works but moves are faster and larger. Always size positions accordingly. |
""")
    st.markdown(f"<p class='subtext'>Data: CoinGecko (coin list) + Yahoo Finance (prices) · Daily bars · Cached 7 days · Not financial advice</p>", unsafe_allow_html=True)
