"""
app.py — Weinstein Screener V6
================================
Dashboard-first home page:
- Weekly market regime overview
- Top signals of the week
- RRG snapshot
- Quick links to all pages
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from datetime import datetime

from utils.theme import page_config, inject_css, get_colors
from utils.screener import (
    get_spx_data, scan_tickers, fmt, rs_tag, sig_icon, signal_card_html,
    SECTORS, SECTOR_STOCKS, export_tv_lines
)
from utils.db import (
    check_login, create_user, validate_invite, use_invite,
    user_exists, get_last_scan_date, is_admin
)

page_config("Weinstein V6")
inject_css()
C = get_colors()

# ── Session defaults ──────────────────────────────────────────
if "logged_in"  not in st.session_state: st.session_state.logged_in  = False
if "username"   not in st.session_state: st.session_state.username   = ""
if "dark_mode"  not in st.session_state: st.session_state.dark_mode  = False

user         = st.session_state.get("username","")
is_logged_in = st.session_state.get("logged_in", False)

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:16px 8px 8px">
      <div style="font-size:1.4rem;font-weight:800;letter-spacing:-0.03em">📈 Weinstein V6</div>
      <div style="font-size:0.72rem;color:{C['SUB']};margin-top:2px">Stage Analysis · RS · Volume</div>
    </div>""", unsafe_allow_html=True)
    st.divider()

    col_t, col_btn = st.columns([3,1])
    with col_t: st.markdown(f"<span style='color:{C['SUB']};font-size:0.82rem'>Appearance</span>", unsafe_allow_html=True)
    with col_btn:
        if st.button("🌙" if not st.session_state.dark_mode else "☀️", key="theme"):
            st.session_state.dark_mode = not st.session_state.dark_mode; st.rerun()

    st.divider()
    if is_logged_in:
        st.markdown(f"<span style='color:{C['SUB']};font-size:0.78rem'>Signed in as</span>", unsafe_allow_html=True)
        st.markdown(f"**{user}**")
        if st.button("Sign out", use_container_width=True):
            st.session_state.logged_in = False; st.session_state.username = ""; st.rerun()
    else:
        st.markdown(f"<span style='color:{C['SUB']};font-size:0.78rem'>Sign in for Dashboard access</span>", unsafe_allow_html=True)

# ══════════════════════════════════════
# LANDING PAGE
# ══════════════════════════════════════

if not is_logged_in:
    # ── Public landing ──
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("# 📈 Weinstein V6")
        st.markdown(f"<p style='color:{C['SUB']};font-size:1rem;line-height:1.8'>Built on Stan Weinstein's Stage Analysis. Scan sectors, industries, and 6000+ stocks for Stage 2 breakouts. Now with daily timeframe, RRG, and weekly background scans.</p>", unsafe_allow_html=True)

        # Feature grid
        features = [
            ("🏦","Sector & Industry Screener","RS-ranked with RRG, drill-down, and mini charts"),
            ("📅","Daily Timeframe","50d SMA for swing trade entries within weekly uptrends"),
            ("₿","Crypto Screener","Top 300 coins vs BTC with daily Stage Analysis"),
            ("🤖","Weekly Auto-Scan","GitHub Actions scans every Saturday — results instant on open"),
            ("🔒","Portfolio Dashboard","P&L, performance chart, treemap, Stage 4 alerts"),
            ("📤","TradingView Export","One-click watchlist export for any scan result"),
        ]
        cols = st.columns(2)
        for i, (icon, title, desc) in enumerate(features):
            with cols[i % 2]:
                st.markdown(f"""<div class="wcard" style="padding:12px 14px;margin:4px 0;display:flex;gap:12px">
                  <span style="font-size:1.2rem">{icon}</span>
                  <div><div style="font-weight:600;font-size:0.88rem">{title}</div>
                  <div style="color:{C['SUB']};font-size:0.75rem">{desc}</div></div>
                </div>""", unsafe_allow_html=True)

        st.markdown(f"<p style='color:{C['SUB']};font-size:0.75rem;margin-top:12px'>Data via Yahoo Finance · Weekly + daily bars · Not financial advice</p>", unsafe_allow_html=True)

    with c2:
        st.markdown(f"<h3 style='text-align:center'>Sign in</h3>", unsafe_allow_html=True)
        lt, rt = st.tabs(["Sign in","Create account"])
        with lt:
            with st.form("lf"):
                un = st.text_input("Username")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Sign in", use_container_width=True):
                    if check_login(un.strip(), pw):
                        st.session_state.logged_in = True; st.session_state.username = un.strip(); st.rerun()
                    else: st.error("Invalid username or password")
            st.caption("The screener is publicly accessible. Sign in for portfolio tracking.")
        with rt:
            with st.form("rf"):
                inv = st.text_input("Invite code")
                nu  = st.text_input("Username")
                np1 = st.text_input("Password", type="password")
                np2 = st.text_input("Repeat password", type="password")
                if st.form_submit_button("Create account", use_container_width=True):
                    if not validate_invite(inv): st.error("Invalid invite code")
                    elif len(nu) < 3: st.error("Username too short")
                    elif user_exists(nu): st.error("Username taken")
                    elif np1 != np2: st.error("Passwords don't match")
                    elif len(np1) < 6: st.error("Password too short")
                    else:
                        create_user(nu, np1); use_invite(inv, nu)
                        st.success(f"Account created! Sign in as {nu}")

else:
    # ══════════════════════════════════════
    # DASHBOARD HOME (logged in)
    # ══════════════════════════════════════

    st.markdown(f"# 👋 Good {'morning' if datetime.now().hour < 12 else 'afternoon'}, {user.title()}")

    # Last scan date
    last_scan = get_last_scan_date()
    if last_scan:
        from datetime import date
        days_ago = (date.today() - datetime.strptime(last_scan, "%Y-%m-%d").date()).days
        freshness = "🟢 Fresh" if days_ago <= 2 else "🟡 Recent" if days_ago <= 7 else "🔴 Stale"
        st.markdown(f"<p class='subtext'>{freshness} · Last background scan: {last_scan} ({days_ago}d ago) · Next scan: Saturday 07:00 UTC</p>", unsafe_allow_html=True)
    else:
        st.markdown(f"<p class='subtext'>No background scan yet. Data loads live on first visit.</p>", unsafe_allow_html=True)

    st.markdown("---")

    # Load market data
    with st.spinner("Loading market data…"):
        spx_ev, sec_df, spx_close_json = get_spx_data()

    if spx_ev is None:
        st.error("Could not load market data. Yahoo Finance may be rate-limiting.")
        if st.button("🔄 Retry"):
            st.cache_data.clear(); st.rerun()
        st.stop()

    # ── Market Regime ──────────────────────────────────────────
    st.markdown("### 📊 Market Regime")
    pct = spx_ev.get("pct_above") or 0
    stage = spx_ev.get("stage","")

    r1,r2,r3,r4,r5 = st.columns(5)
    r1.metric("SPY Stage",   stage)
    r2.metric("Price",       fmt(spx_ev["price"]))
    r3.metric("50w SMA",     fmt(spx_ev["sma50w"]))
    r4.metric("% above SMA", fmt(pct,"%",1))
    r5.metric("Score",       f"{spx_ev['score']}/5")

    if "Stage 2" not in stage:
        st.markdown(f'<div class="wcard-warn">⚠ <strong>SPY not in Stage 2.</strong> Per Weinstein: no new buys until market recovers.</div>', unsafe_allow_html=True)
    elif pct > 10:
        st.markdown(f'<div class="wcard-warn" style="border-left-color:{C["YELLOW"]}">⚡ <strong>SPY extended</strong> ({pct:.1f}% above SMA). Pullback likely before next leg up.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="wcard-info">✓ <strong>SPY in Stage 2.</strong> Buy signals are valid.</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Weekly Top Signals ─────────────────────────────────────
    signal_col, rrg_col = st.columns([1, 1])

    with signal_col:
        st.markdown("### 🚨 Top Signals This Week")

        # Load signals from cache or scan
        try:
            from utils.db import get_cached_scan
            cached_signals = get_cached_scan("signals")
        except: cached_signals = None

        if cached_signals:
            signals_df = pd.DataFrame(cached_signals)
            premium = [r for r in cached_signals if r.get("premium")]
            early   = [r for r in cached_signals if r.get("early_sig") and not r.get("premium")]

            sp1,sp2,sp3 = st.columns(3)
            sp1.metric("🟢 Premium", len(premium))
            sp2.metric("🟡 Early",   len(early))
            sp3.metric("Total S2+",  len(cached_signals))

            # Show top 8 signals
            for r in (premium + early)[:8]:
                tag = "PREMIUM" if r.get("premium") else "EARLY"
                cls = "wcard-premium" if r.get("premium") else "wcard-early"
                col = C["GREEN"] if r.get("premium") else C["YELLOW"]
                cross = f"{int(r['cross'])}w ago" if r.get("cross",-1)>=0 else "–"
                sec   = r.get("sector","")
                st.markdown(f"""<div class="{cls}">
                    <span style="color:{col};font-weight:700">{tag}</span> &nbsp;
                    <strong>{r['ticker']}</strong>
                    {f"<span style='color:{C['SUB']};font-size:0.75rem'>· {sec}</span>" if sec else ""}
                    &nbsp;·&nbsp; {cross} &nbsp;·&nbsp; RS {fmt(r.get('rs'),'',1)}
                    &nbsp;·&nbsp; Base {r.get('base_w',0)}w
                </div>""", unsafe_allow_html=True)

            if len(premium) + len(early) > 8:
                st.caption(f"+ {len(premium)+len(early)-8} more signals → see Screener page")
        else:
            with st.spinner("Scanning for signals…"):
                all_sigs = []
                for sec_tk, stocks in list(SECTOR_STOCKS.items())[:5]:
                    df = scan_tickers(json.dumps(stocks), spx_close_json)
                    if df.empty: continue
                    for _, r in df[df["score"]>=4].iterrows():
                        rd = r.to_dict(); rd["sector"] = SECTORS.get(sec_tk,"")
                        all_sigs.append(rd)

            if all_sigs:
                for r in sorted(all_sigs, key=lambda x: (-x.get("premium",0), -x.get("early_sig",0), -x.get("score",0)))[:6]:
                    st.markdown(signal_card_html(r, r.get("sector",""), C), unsafe_allow_html=True)
            else:
                st.info("No signals in top sectors. Enable Full NYSE scan in Screener.")

    with rrg_col:
        st.markdown("### 🔄 Sector Rotation (RRG)")

        if sec_df is not None and not sec_df.empty:
            rrg_x,rrg_y,rrg_labels,rrg_colors = [],[],[],[]
            qc = {"Leading":C["GREEN"],"Weakening":C["YELLOW"],"Lagging":C["RED"],"Improving":C["BLUE"]}

            for _, sec in sec_df.iterrows():
                rs = sec.get("rs")
                if rs is None or (isinstance(rs,float) and np.isnan(rs)): continue
                x = float(rs)
                y = float(sec.get("pct_above") or 0) * (1 if sec.get("sma_rising") else -1)
                rrg_x.append(x); rrg_y.append(y)
                rrg_labels.append(sec.get("name", sec["ticker"])[:12])
                q = "Leading" if x>0 and y>0 else "Weakening" if x>0 else "Improving" if y>0 else "Lagging"
                rrg_colors.append(qc[q])

            if rrg_x:
                mx = max(abs(v) for v in rrg_x+[1])*1.3
                my = max(abs(v) for v in rrg_y+[1])*1.3
                fig = go.Figure()
                for xr,yr,col in [(mx,my,"rgba(74,222,128,0.07)"),(mx,-my,"rgba(251,191,36,0.07)"),
                                  (-mx,-my,"rgba(248,113,113,0.07)"),(-mx,my,"rgba(96,165,250,0.07)")]:
                    fig.add_shape(type="rect",x0=0 if xr>0 else xr,y0=0 if yr>0 else yr,
                        x1=xr if xr>0 else 0,y1=yr if yr>0 else 0,fillcolor=col,line_width=0)
                for lb,xp,yp in [("LEADING",0.7,0.85),("WEAKENING",0.7,-0.85),
                                  ("IMPROVING",-0.7,0.85),("LAGGING",-0.7,-0.85)]:
                    fig.add_annotation(x=mx*xp,y=my*yp,text=lb,showarrow=False,
                        font=dict(size=8,color=C["BORDER"]),opacity=0.6)
                fig.add_hline(y=0,line_color=C["BORDER"],line_width=1)
                fig.add_vline(x=0,line_color=C["BORDER"],line_width=1)
                fig.add_trace(go.Scatter(x=rrg_x,y=rrg_y,mode="markers+text",
                    text=rrg_labels,textposition="top center",
                    textfont=dict(size=9,color=C["TEXT"]),
                    marker=dict(color=rrg_colors,size=12,line=dict(width=1,color=C["BORDER"])),
                    hovertemplate="<b>%{text}</b><br>RS: %{x:.1f}<br>Mom: %{y:.1f}<extra></extra>"))
                fig.update_layout(height=380,margin=dict(l=0,r=0,t=10,b=0),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=C["TEXT"],family="Inter"),
                    xaxis=dict(title="RS Score",showgrid=True,gridcolor=C["BORDER"],color=C["SUB"],zeroline=False),
                    yaxis=dict(title="Momentum",showgrid=True,gridcolor=C["BORDER"],color=C["SUB"],zeroline=False),
                    showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Quick Navigation ───────────────────────────────────────
    st.markdown("### 🧭 Quick Navigation")
    nc1,nc2,nc3,nc4,nc5 = st.columns(5)
    nc1.page_link("pages/1_Screener.py",  label="🏦 Screener",   use_container_width=True)
    nc2.page_link("pages/2_All_Stocks.py",label="📋 All Stocks",  use_container_width=True)
    nc3.page_link("pages/3_Dashboard.py", label="🔒 Dashboard",   use_container_width=True)
    nc4.page_link("pages/4_Crypto.py",    label="₿ Crypto",       use_container_width=True)

    if is_admin(user):
        with nc5:
            if st.button("🔄 Force cache refresh", use_container_width=True):
                st.cache_data.clear()
                st.success("Cache cleared — reloading…")
                st.rerun()

    st.markdown(f"<p class='subtext'>Weinstein V6 · {datetime.now().strftime('%A %d %B %Y')} · Data cached 7 days</p>", unsafe_allow_html=True)
