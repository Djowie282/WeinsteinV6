"""pages/4_Dashboard.py — Private portfolio dashboard"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import json
from datetime import datetime, timedelta
from io import StringIO
from utils.theme import page_config, inject_css, get_colors
from utils.screener import get_spx_data, scan_tickers, fmt, rs_tag, sig_icon
from utils.db import (
    get_portfolio, upsert_position, sell_shares, delete_position,
    get_alerts, add_alert, remove_alert,
    get_watchlist, add_to_watchlist, remove_from_watchlist,
    gen_invite, list_invites, list_users, is_admin, validate_invite
)

page_config("Dashboard · Weinstein V6")
inject_css()
C = get_colors()

# ── Auth gate ─────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    st.markdown("# 🔒 Private Dashboard")
    st.info("Please sign in from the home page to access your dashboard.")
    st.page_link("app.py", label="← Go to sign in")
    st.stop()

user = st.session_state.username

# ── Load market data ──────────────────────────────────────────
with st.spinner("Loading…"):
    spx_ev, sec_df, spx_close_json = get_spx_data()

if spx_ev is None:
    st.error("Yahoo Finance is rate-limiting this server. Please wait 30 seconds and refresh the page.")
    if st.button("🔄 Retry now"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# ── Header ────────────────────────────────────────────────────
hdr, logout_col = st.columns([5, 1])
with hdr:
    st.markdown(f"# 🏛 Dashboard — {user.title()}")
with logout_col:
    if st.button("Sign out"):
        st.session_state.logged_in = False
        st.session_state.username  = ""
        st.rerun()

# ── Admin panel ───────────────────────────────────────────────
if is_admin(user):
    with st.expander("⚙️ Admin — Invites & Users"):
        ac1, ac2 = st.columns(2)
        with ac1:
            st.markdown("**Generate invite code**")
            if st.button("🔗 New invite code"):
                code = gen_invite(user)
                st.session_state["last_invite"] = code
            if st.session_state.get("last_invite"):
                st.code(st.session_state["last_invite"])
                st.caption("Single-use. Share this with the person you want to invite.")
        with ac2:
            st.markdown("**Active codes**")
            for inv in list_invites():
                status = "✅ used" if inv.get("used") else "⏳ pending"
                st.markdown(f"`{inv['code']}` — {status}")
        st.markdown("**Users**")
        for u in list_users():
            st.markdown(f"• `{u['username']}` ({u.get('role','user')})")

# ── Manage positions ──────────────────────────────────────────
portfolio = get_portfolio(user)

with st.expander("➕ Manage positions"):
    st.markdown("**Buy / Add shares**")
    ba, bb, bc, bd = st.columns(4)
    new_tk   = ba.text_input("Ticker").upper().strip()
    new_sh   = bb.number_input("Shares", min_value=0.01, step=0.01, value=1.0)
    new_cost = bc.number_input("Avg cost ($)", min_value=0.0, step=0.01, value=0.0)
    new_note = bd.text_input("Notes")
    if st.button("➕ Add / Buy", width="stretch"):
        if new_tk:
            upsert_position(user, new_tk, new_sh, new_cost, new_note)
            st.success(f"Updated {new_tk}")
            st.rerun()

    st.markdown("---")
    st.markdown("**Sell shares**")
    tickers_in = [p["ticker"] for p in portfolio]
    if tickers_in:
        sc1, sc2, sc3 = st.columns(3)
        sell_tk = sc1.selectbox("Ticker", tickers_in, key="sell_tk")
        pos     = next((p for p in portfolio if p["ticker"] == sell_tk), None)
        max_sh  = pos["shares"] if pos else 1.0
        sell_sh = sc2.number_input(f"Shares (max {max_sh:.2f})", 0.01, float(max_sh), float(max_sh), 0.01)
        sell_all = sc3.checkbox("Sell entire position")

        if st.button("🔴 Sell", width="stretch"):
            if sell_all or sell_sh >= max_sh:
                st.session_state[f"confirm_{sell_tk}"] = True
            else:
                sell_shares(user, sell_tk, sell_sh)
                st.success(f"Sold {sell_sh:.2f} sh of {sell_tk}")
                st.rerun()

        if st.session_state.get(f"confirm_{sell_tk}"):
            st.warning(f"Remove **{sell_tk}** entirely?")
            y, n = st.columns(2)
            if y.button("✅ Yes", key=f"y_{sell_tk}"):
                delete_position(user, sell_tk)
                st.session_state.pop(f"confirm_{sell_tk}", None)
                st.rerun()
            if n.button("❌ No", key=f"n_{sell_tk}"):
                st.session_state.pop(f"confirm_{sell_tk}", None)
                st.rerun()

    st.markdown("---")
    st.markdown("**Current positions**")
    for i, pos in enumerate(portfolio):
        c1,c2,c3,c4,c5 = st.columns([2,1,2,3,1])
        c1.markdown(f"**{pos['ticker']}**")
        c2.markdown(f"{pos['shares']:.2f} sh")
        c3.markdown(f"Avg ${pos['avg_cost']:.2f}" if pos['avg_cost'] > 0 else "–")
        c4.markdown(pos.get("notes",""))
        if c5.button("🗑", key=f"del_{i}_{pos['ticker']}"):
            st.session_state[f"confirm_del_{i}"] = True
        if st.session_state.get(f"confirm_del_{i}"):
            st.warning(f"Remove {pos['ticker']}?")
            y2, n2 = st.columns(2)
            if y2.button("Yes", key=f"yd_{i}"):
                delete_position(user, pos["ticker"])
                st.session_state.pop(f"confirm_del_{i}", None)
                st.rerun()
            if n2.button("No", key=f"nd_{i}"):
                st.session_state.pop(f"confirm_del_{i}", None)
                st.rerun()

# ── Portfolio analysis ────────────────────────────────────────
portfolio = get_portfolio(user)
if not portfolio:
    st.info("Add positions above to get started.")
    st.stop()

tickers  = [p["ticker"] for p in portfolio]
cost_map = {p["ticker"]: (p["shares"], p["avg_cost"]) for p in portfolio}

with st.spinner("Analysing portfolio…"):
    port_df = scan_tickers(json.dumps(tickers), spx_close_json)

if port_df.empty:
    st.warning("Could not load portfolio data.")
    st.stop()

# Compute P&L
position_data = []
total_value = 0; total_cost = 0
for _, r in port_df.iterrows():
    tk = r["ticker"]
    sh, ac = cost_map.get(tk, (1, 0))
    price  = r["price"] or 0
    val    = price * sh
    cost   = ac * sh
    pnl    = val - cost if ac > 0 else None
    pnl_pct = (val/cost - 1)*100 if (ac > 0 and cost > 0) else None
    total_value += val
    if ac > 0: total_cost += cost
    position_data.append({"r": r.to_dict(), "sh": sh, "ac": ac, "val": val, "pnl": pnl, "pnl_pct": pnl_pct})

total_pnl     = total_value - total_cost if total_cost > 0 else None
total_pnl_pct = (total_value/total_cost - 1)*100 if total_cost > 0 else None

# ── Performance metrics ───────────────────────────────────────
st.markdown("---")

@st.cache_data(ttl=3600)
def get_port_history(tickers_json):
    tks = json.loads(tickers_json)
    end   = datetime.today()
    start = end - timedelta(days=365*5)
    try:
        all_tks = list(set(tks + ["SPY"]))
        raw = yf.download(all_tks, start=start, end=end, auto_adjust=False,
                          progress=False, threads=False)["Close"]
        if isinstance(raw, pd.Series): raw = raw.to_frame(all_tks[0])
        if len(raw) > 1 and raw.index[-1].date() == datetime.today().date():
            raw = raw.iloc[:-1]
        return raw.ffill()
    except: return pd.DataFrame()

hist = get_port_history(json.dumps(tickers))

def period_ret(hist, label):
    if hist.empty: return None
    now = hist.index[-1]
    cuts = {"1D":1,"1W":5,"1M":21,"3M":63,"YTD":None}
    n = cuts.get(label)
    if label == "YTD":
        start_prices = hist[hist.index >= pd.Timestamp(now.year, 1, 1)].iloc[0] if not hist[hist.index >= pd.Timestamp(now.year, 1, 1)].empty else None
        if start_prices is None: return None
    elif n:
        if len(hist) < n+1: return None
        start_prices = hist.iloc[-(n+1)]
    end_prices = hist.iloc[-1]
    ts = te = 0
    for tk in tickers:
        if tk not in hist.columns: continue
        sh, ac = cost_map.get(tk, (1,1))
        sp = float(start_prices.get(tk,0)) if tk in start_prices.index else 0
        ep = float(end_prices.get(tk,0)) if tk in end_prices.index else 0
        if sp > 0 and ep > 0: ts += sp*sh; te += ep*sh
    return (te/ts - 1)*100 if ts > 0 else None

# Metrics row
n_s2 = sum(1 for pd_ in position_data if pd_["r"]["score"] >= 4)
n_s4 = sum(1 for pd_ in position_data if "Stage 4" in pd_["r"]["stage"])
cols = st.columns(7)
cols[0].metric("Positions",   len(portfolio))
cols[1].metric("Total Value", f"${total_value:,.0f}" if not st.session_state.get("hide_vals") else "—")
if total_pnl is not None and not st.session_state.get("hide_vals"):
    cols[2].metric("Total P&L", f"${total_pnl:+,.0f}", f"{total_pnl_pct:+.1f}%")
for i, p in enumerate(["1D","1W","1M","YTD"]):
    ret = period_ret(hist, p)
    cols[3+i].metric(p, f"{ret:+.2f}%" if ret else "–")

st.markdown("---")

# ── Controls ──────────────────────────────────────────────────
ct1, ct2, ct3 = st.columns([3,2,1])
with ct1:
    chart_period = st.radio("", ["1W","1M","YTD","1Y","5Y","Max"], index=3,
                             horizontal=True, label_visibility="collapsed")
with ct2:
    cmp_spx = st.checkbox("Compare vs S&P 500", value=True)
with ct3:
    hide_vals = st.toggle("Hide $", value=False, key="hide_vals")

# ── Chart + Distribution ──────────────────────────────────────
ch_col, dist_col = st.columns([3, 2])

with ch_col:
    st.markdown("#### Performance")
    if not hist.empty and total_cost > 0:
        now = pd.Timestamp.today()
        cuts = {"1W": now-pd.Timedelta(weeks=1), "1M": now-pd.DateOffset(months=1),
                "YTD": pd.Timestamp(now.year,1,1), "1Y": now-pd.DateOffset(years=1),
                "5Y": now-pd.DateOffset(years=5), "Max": hist.index[0]}
        cut = cuts.get(chart_period, hist.index[0])
        h = hist[hist.index >= cut]
        if h.empty: h = hist

        daily_vals = pd.Series(0.0, index=h.index)
        for tk in tickers:
            if tk not in h.columns: continue
            sh, ac = cost_map.get(tk,(1,0))
            if ac > 0: daily_vals += h[tk].ffill() * sh

        sv = float(daily_vals.iloc[0])
        pct_s = ((daily_vals/sv)-1)*100 if sv > 0 else daily_vals*0
        win = max(1, len(pct_s)//30)
        pct_s = pct_s.rolling(win, min_periods=1, center=True).mean().round(2)

        end_val   = float(pct_s.iloc[-1])
        lc = C["GREEN"] if end_val >= 0 else C["RED"]
        fc = f"rgba(74,222,128,0.07)" if end_val >= 0 else "rgba(248,113,113,0.07)"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pct_s.index, y=pct_s.values, mode="lines", name="Portfolio",
            line=dict(color=lc, width=2.5, shape="spline", smoothing=0.8),
            fill="tozeroy", fillcolor=fc,
            hovertemplate="%{x|%b %d %Y}<br><b>%{y:+.2f}%</b><extra></extra>",
        ))
        if cmp_spx and "SPY" in h.columns:
            spy = h["SPY"].ffill()
            spy_pct = ((spy/float(spy.iloc[0]))-1)*100
            spy_s   = spy_pct.rolling(win, min_periods=1, center=True).mean().round(2)
            fig.add_trace(go.Scatter(
                x=spy_s.index, y=spy_s.values, mode="lines", name="S&P 500",
                line=dict(color=C["SUB"], width=1.5, shape="spline", smoothing=0.8, dash="dot"),
                hovertemplate="%{x|%b %d %Y}<br>SPX <b>%{y:+.2f}%</b><extra></extra>",
            ))
        fig.add_hline(y=0, line_dash="dash", line_color=f"{C['BORDER']}", line_width=1)

        yax = dict(showgrid=True, gridcolor=C["BORDER"], zeroline=False,
                   tickformat="+.1f", ticksuffix="%", color=C["SUB"], tickfont=dict(size=11))
        if hide_vals: yax["showticklabels"] = False

        fig.update_layout(
            height=300, margin=dict(l=0,r=0,t=10,b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=C["TEXT"], family="Inter"),
            xaxis=dict(showgrid=False, color=C["SUB"], tickfont=dict(size=10), zeroline=False),
            yaxis=yax,
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C["TEXT"], size=11),
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Add avg costs to positions to see the performance chart.")

with dist_col:
    dh, dt = st.columns([2,1])
    with dh: st.markdown("#### Distribution")
    with dt:
        dist_mode = st.radio("", ["P&L","Today"], horizontal=True, label_visibility="collapsed")

    if position_data:
        tree_labels = [pd_["r"]["ticker"] for pd_ in position_data if pd_["val"] > 0]
        tree_values = [pd_["val"] for pd_ in position_data if pd_["val"] > 0]

        if dist_mode == "Today":
            today_ch = []
            for pd_ in position_data:
                if pd_["val"] <= 0: continue
                try:
                    fi   = yf.Ticker(pd_["r"]["ticker"]).fast_info
                    prev = getattr(fi,"previous_close",None)
                    last = getattr(fi,"last_price",None)
                    today_ch.append(round((float(last)/float(prev)-1)*100,2) if prev and last and float(prev)>0 else 0.0)
                except: today_ch.append(0.0)
            colors = today_ch
            labels = [f"{c:+.2f}%" for c in today_ch]
        else:
            pnls   = [pd_["pnl_pct"] for pd_ in position_data if pd_["val"] > 0]
            colors = [p if p is not None else 0 for p in pnls]
            labels = [f"{p:+.1f}%" if p is not None else "–" for p in pnls]
            if hide_vals: labels = ["" for _ in labels]

        fig2 = go.Figure(go.Treemap(
            labels=tree_labels, parents=[""]*len(tree_labels), values=tree_values,
            customdata=[[l] for l in labels],
            texttemplate="<b>%{label}</b><br>%{customdata[0]}",
            marker=dict(colors=colors,
                        colorscale=[[0,"#7f1d1d"],[0.45,C["CARD2"] if "CARD2" in C else "#1c1f2e"],[1,"#14532d"]],
                        cmid=0, showscale=False),
        ))
        fig2.update_layout(height=300, margin=dict(l=0,r=0,t=0,b=0),
                           paper_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="white", family="Inter", size=12))
        st.plotly_chart(fig2, width="stretch")

st.markdown("---")

# ── Position Grid ─────────────────────────────────────────────
st.markdown("#### Positions")
sorted_pos = sorted(position_data, key=lambda x: (x["r"]["score"], x["r"].get("rs") or -99), reverse=True)
cols3 = st.columns(3)

for i, pd_ in enumerate(sorted_pos):
    r       = pd_["r"]
    tk      = r["ticker"]
    stage   = r["stage"]
    pnl     = pd_["pnl"]
    pnl_pct = pd_["pnl_pct"]

    if "Stage 2" in stage:   s_color, s_dot = C["GREEN"],  "🟢"
    elif "Stage 3" in stage: s_color, s_dot = C["YELLOW"], "🟡"
    elif "Stage 4" in stage: s_color, s_dot = C["RED"],    "🔴"
    else:                    s_color, s_dot = C["BLUE"],   "🔵"

    pnl_html = ""
    if pnl is not None and not hide_vals:
        pc   = C["GREEN"] if pnl >= 0 else C["RED"]
        sign = "+" if pnl >= 0 else ""
        pnl_html = f'<span style="color:{pc};font-weight:700">{sign}${pnl:,.0f} ({pnl_pct:+.1f}%)</span>'

    price_str = "———" if hide_vals else f"${r['price'] or 0:,.2f}"
    sig = sig_icon(r)

    with cols3[i % 3]:
        st.markdown(f"""
        <div class="wcard" style="padding:14px 16px;margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-size:1.05rem;font-weight:800">{s_dot} {tk}</span>
            <span style="color:{C['SUB']};font-size:0.78rem">{pd_['sh']:.0f} sh</span>
          </div>
          <div style="font-size:1.35rem;font-weight:700;margin-bottom:2px">{price_str}</div>
          <div style="font-size:0.82rem;margin-bottom:8px">{pnl_html}</div>
          <div style="font-size:0.76rem;color:{C['SUB']};line-height:1.7">
            <span style="color:{s_color};font-weight:600">{stage}</span> · {r['score']}/5<br>
            RS {fmt(r['rs'],'',1)} · {fmt(r['pct_above'],'%',1)} vs SMA<br>
            Stop: {fmt(r['stop'])} ({fmt(r['risk'],'%',1)})<br>
            {'<strong style="color:' + C["GREEN"] + '">' + sig + '</strong>' if sig else ''}
          </div>
        </div>""", unsafe_allow_html=True)

# ── Stage 4 warnings ─────────────────────────────────────────
s4 = [pd_ for pd_ in position_data if "Stage 4" in pd_["r"]["stage"]]
if s4:
    st.markdown("---")
    st.markdown("#### ⚠️ Action Required")
    for pd_ in s4:
        r  = pd_["r"]
        rs = r.get("rs")
        note = ""
        if rs and not (isinstance(rs, float) and pd.isna(rs)) and rs > 5:
            note = f" · High RS ({rs:+.0f}) = bounce in downtrend, not a reversal."
        st.markdown(f"""<div class="wcard-warn">
            <strong style="color:{C['RED']}">STAGE 4 — EXIT</strong> &nbsp;
            <strong>{r['ticker']}</strong> · ${r['price'] or 0:,.2f} ·
            {fmt(r['pct_above'],'%',1)} vs SMA · RS {fmt(rs,'',1)} ({rs_tag(rs)}){note}
        </div>""", unsafe_allow_html=True)

# ── Watchlist (enriched with Weinstein data + alerts) ─────────
st.markdown("---")
st.markdown("### 👁 Watchlist & Alerts")

wl = get_watchlist(user)
alerts_list = get_alerts(user)
alert_tickers = {a["ticker"] for a in alerts_list}

# Quick add
qa_c1, qa_c2, qa_c3 = st.columns([2, 1, 1])
with qa_c1:
    new_wl_tk = st.text_input("Add ticker", placeholder="e.g. NVDA, ARM…",
                              label_visibility="collapsed", key="quick_add_wl")
with qa_c2:
    new_wl_tag = st.selectbox("Tag", ["watch","stage1","analyzed","signal"],
                              label_visibility="collapsed", key="quick_add_tag")
with qa_c3:
    if st.button("➕ Add", use_container_width=True, key="quick_add_btn"):
        if new_wl_tk.strip():
            add_to_watchlist(user, new_wl_tk.strip().upper(), new_wl_tag)
            st.rerun()

if wl:
    from utils.screener import scan_tickers, fmt, sig_icon
    import json as _json

    wl_tickers = [w["ticker"] for w in wl]
    with st.spinner("Loading Weinstein data for watchlist…"):
        wl_scan = scan_tickers(_json.dumps(wl_tickers), spx_close_json)

    if not wl_scan.empty:
        # Check for triggered alerts (Stage 1 → Stage 2 transitions)
        triggered = []
        for w in wl:
            tk = w["ticker"]
            match = wl_scan[wl_scan["ticker"] == tk]
            if not match.empty:
                r = match.iloc[0].to_dict()
                if r.get("early_sig") or r.get("premium"):
                    if w.get("tag") == "stage1" or tk in alert_tickers:
                        triggered.append({"ticker": tk, "stage": r["stage"],
                                          "early": r.get("early_sig"), "premium": r.get("premium")})

        if triggered:
            st.markdown("#### 🚨 Alert Triggers")
            for t in triggered:
                level = "🟢 PREMIUM" if t["premium"] else "🟡 EARLY"
                st.markdown(f"<div class='wcard-premium'><strong>{level}</strong> — "
                           f"<strong>{t['ticker']}</strong> just hit {t['stage']}! Check the Screener.</div>",
                           unsafe_allow_html=True)
            st.markdown("---")

        # Build enriched table
        st.markdown("#### Your Watchlist")
        wl_rows = []
        for w in wl:
            tk = w["ticker"]
            match = wl_scan[wl_scan["ticker"] == tk]
            if not match.empty:
                r = match.iloc[0].to_dict()
                cross = f"{int(r['cross'])}w" if r.get("cross",-1)>=0 else "–"
                wl_rows.append({
                    "Tag":     w.get("tag","watch"),
                    "Ticker":  tk,
                    "Signal":  sig_icon(r),
                    "Stage":   r["stage"],
                    "Score":   f"{r['score']}/5",
                    "RS":      fmt(r["rs"],"",1),
                    "Price":   fmt(r["price"]),
                    "%>SMA":   fmt(r["pct_above"],"%",1),
                    "Base":    f"{r['base_w']}w",
                    "Cross":   cross,
                    "Alert":   "🔔" if tk in alert_tickers else "—",
                })
            else:
                wl_rows.append({"Tag": w.get("tag","watch"), "Ticker": tk,
                                "Signal": "", "Stage": "—", "Score": "—", "RS": "—",
                                "Price": "—", "%>SMA": "—", "Base": "—", "Cross": "—",
                                "Alert": "🔔" if tk in alert_tickers else "—"})

        if wl_rows:
            df_wl = pd.DataFrame(wl_rows)
            st.dataframe(df_wl, width="stretch", hide_index=True, height=min(420, 50+len(df_wl)*36))

    # Manage actions
    mgmt1, mgmt2 = st.columns(2)
    with mgmt1:
        with st.expander("🔔 Manage alerts"):
            st.caption("Get a flag in the watchlist when a ticker hits Stage 2 (early or premium signal).")
            al_tk = st.selectbox("Toggle alert for", ["–"] + [w["ticker"] for w in wl], key="alert_pick")
            if al_tk != "–":
                if al_tk in alert_tickers:
                    if st.button(f"🔕 Disable alert for {al_tk}", key="al_disable"):
                        remove_alert(user, al_tk); st.rerun()
                else:
                    if st.button(f"🔔 Enable alert for {al_tk}", key="al_enable"):
                        add_alert(user, al_tk, "sma_cross"); st.rerun()
    with mgmt2:
        with st.expander("🗑 Remove from watchlist"):
            rm_tk = st.selectbox("Pick ticker to remove", ["–"] + [w["ticker"] for w in wl], key="rm_pick")
            if rm_tk != "–" and st.button(f"Remove {rm_tk}", key="rm_btn"):
                remove_from_watchlist(user, rm_tk)
                if rm_tk in alert_tickers: remove_alert(user, rm_tk)
                st.rerun()
else:
    st.info("Your watchlist is empty. Add tickers via the Screener or use the search above.")
