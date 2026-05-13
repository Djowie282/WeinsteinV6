"""
utils/db.py — V6 Database layer
=================================
Supabase tables needed (run in SQL editor):

  -- Auth tables (same as V5)
  create table users (
    id uuid primary key default gen_random_uuid(),
    username text unique not null,
    pw_hash text not null,
    role text default 'user',
    created_at timestamptz default now()
  );
  create table portfolios (
    id uuid primary key default gen_random_uuid(),
    username text not null, ticker text not null,
    shares float default 1, avg_cost float default 0,
    notes text default '', created_at timestamptz default now(),
    unique(username, ticker)
  );
  create table watchlists (
    id uuid primary key default gen_random_uuid(),
    username text not null, ticker text not null,
    tag text default 'watch', notes text default '',
    created_at timestamptz default now(),
    unique(username, ticker)
  );
  create table invite_codes (
    code text primary key, used boolean default false,
    created_by text, used_by text,
    created_at timestamptz default now()
  );

  -- V6: Scan results cache
  create table scan_cache (
    id text primary key,
    scan_type text not null,
    data jsonb not null,
    scan_date date not null,
    created_at timestamptz default now()
  );

  -- V6: Alert preferences
  create table alerts (
    id uuid primary key default gen_random_uuid(),
    username text not null,
    ticker text not null,
    alert_type text default 'sma_cross',
    threshold float,
    active boolean default true,
    triggered_at timestamptz,
    created_at timestamptz default now()
  );

  -- Disable RLS
  alter table users disable row level security;
  alter table portfolios disable row level security;
  alter table watchlists disable row level security;
  alter table invite_codes disable row level security;
  alter table scan_cache disable row level security;
  alter table alerts disable row level security;

  -- Seed users
  insert into users (username, pw_hash, role) values
    ('joey',  encode(sha256('weinstein2026'), 'hex'), 'admin'),
    ('roger', encode(sha256('roger123'),      'hex'), 'user')
  on conflict (username) do nothing;
"""

import os
import json
import hashlib
import streamlit as st
from datetime import datetime, timedelta


# ── Supabase client ───────────────────────────────────────────

@st.cache_resource
def get_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY", "")
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ── In-memory fallback ────────────────────────────────────────

@st.cache_resource
def _mem():
    return {
        "users": {
            "joey":  {"pw": _hash("weinstein2026"), "role": "admin"},
            "roger": {"pw": _hash("roger123"),      "role": "user"},
        },
        "portfolios": {
            "joey": [
                {"ticker":"RIVN","shares":1,"avg_cost":0,"notes":"LEAPS 2027/2028"},
                {"ticker":"MU","shares":1,"avg_cost":0,"notes":""},
                {"ticker":"ARM","shares":1,"avg_cost":0,"notes":""},
                {"ticker":"RKLB","shares":1,"avg_cost":0,"notes":""},
            ],
            "roger": [],
        },
        "watchlists":   {},
        "invite_codes": {},
        "scan_cache":   {},
    }


# ── Auth ──────────────────────────────────────────────────────

def check_login(username: str, password: str) -> bool:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("users").select("pw_hash").eq("username", username).execute()
            if r.data: return r.data[0]["pw_hash"] == _hash(password)
        except Exception: pass
    u = _mem()["users"].get(username)
    return bool(u and u["pw"] == _hash(password))

def get_role(username: str) -> str:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("users").select("role").eq("username", username).execute()
            if r.data: return r.data[0]["role"]
        except Exception: pass
    return _mem()["users"].get(username, {}).get("role", "user")

def is_admin(username: str) -> bool:
    return get_role(username) == "admin"

def create_user(username: str, password: str, role: str = "user") -> bool:
    sb = get_supabase()
    if sb:
        try:
            sb.table("users").insert({"username": username, "pw_hash": _hash(password), "role": role}).execute()
            return True
        except Exception: pass
    mem = _mem()
    if username in mem["users"]: return False
    mem["users"][username] = {"pw": _hash(password), "role": role}
    mem["portfolios"][username] = []
    return True

def user_exists(username: str) -> bool:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("users").select("username").eq("username", username).execute()
            return bool(r.data)
        except Exception: pass
    return username in _mem()["users"]

def list_users() -> list:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("users").select("username,role,created_at").execute()
            return r.data or []
        except Exception: pass
    return [{"username": k, "role": v["role"]} for k, v in _mem()["users"].items()]


# ── Invite codes ──────────────────────────────────────────────

def gen_invite(created_by: str) -> str:
    import secrets
    code = secrets.token_urlsafe(8)
    sb = get_supabase()
    if sb:
        try:
            sb.table("invite_codes").insert({"code": code, "used": False, "created_by": created_by}).execute()
            return code
        except Exception: pass
    _mem()["invite_codes"][code] = {"used": False, "created_by": created_by}
    return code

def validate_invite(code: str) -> bool:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("invite_codes").select("used").eq("code", code).execute()
            return bool(r.data) and not r.data[0]["used"]
        except Exception: pass
    e = _mem()["invite_codes"].get(code)
    return bool(e and not e["used"])

def use_invite(code: str, used_by: str):
    sb = get_supabase()
    if sb:
        try:
            sb.table("invite_codes").update({"used": True, "used_by": used_by}).eq("code", code).execute()
            return
        except Exception: pass
    e = _mem()["invite_codes"].get(code)
    if e: e["used"] = True

def list_invites() -> list:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("invite_codes").select("*").execute()
            return r.data or []
        except Exception: pass
    return [{"code": k, **v} for k, v in _mem()["invite_codes"].items()]


# ── Portfolio ─────────────────────────────────────────────────

def get_portfolio(username: str) -> list:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("portfolios").select("*").eq("username", username).execute()
            return r.data or []
        except Exception: pass
    return _mem()["portfolios"].get(username, [])

def upsert_position(username: str, ticker: str, shares: float, avg_cost: float, notes: str = ""):
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("portfolios").select("*").eq("username", username).eq("ticker", ticker).execute()
            if r.data:
                e = r.data[0]
                ns = e["shares"] + shares
                na = (e["shares"]*e["avg_cost"] + shares*avg_cost)/ns if avg_cost > 0 and e["avg_cost"] > 0 else (avg_cost or e["avg_cost"])
                sb.table("portfolios").update({"shares": ns, "avg_cost": round(na,4), "notes": notes or e["notes"]}).eq("username", username).eq("ticker", ticker).execute()
            else:
                sb.table("portfolios").insert({"username": username, "ticker": ticker, "shares": shares, "avg_cost": avg_cost, "notes": notes}).execute()
            return
        except Exception: pass
    port = _mem()["portfolios"].setdefault(username, [])
    e = next((p for p in port if p["ticker"] == ticker), None)
    if e:
        ns = e["shares"] + shares
        na = (e["shares"]*e["avg_cost"] + shares*avg_cost)/ns if avg_cost > 0 and e["avg_cost"] > 0 else (avg_cost or e["avg_cost"])
        e["shares"] = ns; e["avg_cost"] = round(na,4)
        if notes: e["notes"] = notes
    else:
        port.append({"ticker": ticker, "shares": shares, "avg_cost": avg_cost, "notes": notes})

def sell_shares(username: str, ticker: str, shares: float):
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("portfolios").select("shares").eq("username", username).eq("ticker", ticker).execute()
            if r.data:
                rem = r.data[0]["shares"] - shares
                if rem <= 0.001: sb.table("portfolios").delete().eq("username", username).eq("ticker", ticker).execute()
                else: sb.table("portfolios").update({"shares": round(rem,4)}).eq("username", username).eq("ticker", ticker).execute()
            return
        except Exception: pass
    port = _mem()["portfolios"].get(username, [])
    e = next((p for p in port if p["ticker"] == ticker), None)
    if e:
        rem = e["shares"] - shares
        if rem <= 0.001: port.remove(e)
        else: e["shares"] = round(rem, 4)

def delete_position(username: str, ticker: str):
    sb = get_supabase()
    if sb:
        try:
            sb.table("portfolios").delete().eq("username", username).eq("ticker", ticker).execute()
            return
        except Exception: pass
    port = _mem()["portfolios"].get(username, [])
    _mem()["portfolios"][username] = [p for p in port if p["ticker"] != ticker]


# ── Watchlist ─────────────────────────────────────────────────

def get_watchlist(username: str) -> list:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("watchlists").select("*").eq("username", username).execute()
            return r.data or []
        except Exception: pass
    return _mem()["watchlists"].get(username, [])

def add_to_watchlist(username: str, ticker: str, tag: str = "watch", notes: str = ""):
    sb = get_supabase()
    if sb:
        try:
            sb.table("watchlists").upsert({"username": username, "ticker": ticker, "tag": tag, "notes": notes}).execute()
            return
        except Exception: pass
    wl = _mem()["watchlists"].setdefault(username, [])
    if not any(w["ticker"] == ticker for w in wl):
        wl.append({"ticker": ticker, "tag": tag, "notes": notes})

def remove_from_watchlist(username: str, ticker: str):
    sb = get_supabase()
    if sb:
        try:
            sb.table("watchlists").delete().eq("username", username).eq("ticker", ticker).execute()
            return
        except Exception: pass
    wl = _mem()["watchlists"].get(username, [])
    _mem()["watchlists"][username] = [w for w in wl if w["ticker"] != ticker]


# ── Scan cache (V6 key feature) ───────────────────────────────

def get_cached_scan(scan_type: str, max_age_days: int = 8) -> list | None:
    """
    Retrieve cached scan results from Supabase.
    Returns None if no cache or cache is too old.
    """
    sb = get_supabase()
    if not sb: return None
    try:
        r = sb.table("scan_cache").select("data,scan_date").eq("id", f"{scan_type}_latest").execute()
        if not r.data: return None
        scan_date = datetime.strptime(r.data[0]["scan_date"], "%Y-%m-%d")
        if (datetime.now() - scan_date).days > max_age_days:
            return None  # Too old
        data = r.data[0]["data"]
        if isinstance(data, str): return json.loads(data)
        return data
    except Exception:
        return None

def save_cached_scan(scan_type: str, data: list) -> bool:
    """Save scan results to Supabase cache."""
    sb = get_supabase()
    if not sb: return False
    try:
        scan_date = datetime.now().strftime("%Y-%m-%d")
        sb.table("scan_cache").upsert({
            "id": f"{scan_type}_latest",
            "scan_type": scan_type,
            "data": json.dumps(data, default=str),
            "scan_date": scan_date,
        }).execute()
        return True
    except Exception:
        return False

def get_last_scan_date() -> str | None:
    """Get the date of the most recent scan."""
    sb = get_supabase()
    if not sb: return None
    try:
        r = sb.table("scan_cache").select("scan_date").eq("id", "signals_latest").execute()
        if r.data: return r.data[0]["scan_date"]
    except Exception: pass
    return None


# ── Alerts (V6) ───────────────────────────────────────────────

def get_alerts(username: str) -> list:
    sb = get_supabase()
    if sb:
        try:
            r = sb.table("alerts").select("*").eq("username", username).eq("active", True).execute()
            return r.data or []
        except Exception: pass
    return []

def add_alert(username: str, ticker: str, alert_type: str = "sma_cross", threshold: float = None):
    sb = get_supabase()
    if sb:
        try:
            sb.table("alerts").upsert({
                "username": username, "ticker": ticker,
                "alert_type": alert_type, "threshold": threshold, "active": True
            }).execute()
        except Exception: pass

def remove_alert(username: str, ticker: str):
    sb = get_supabase()
    if sb:
        try:
            sb.table("alerts").update({"active": False}).eq("username", username).eq("ticker", ticker).execute()
        except Exception: pass
