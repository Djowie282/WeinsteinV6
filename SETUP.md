# Weinstein V6 — Setup Guide

## What's new in V6
- **Dashboard-first home**: market regime + top signals + RRG on login
- **Supabase scan cache**: results persist across restarts, app opens instantly
- **GitHub Actions**: auto-scan every Saturday 07:00 UTC
- **Daily tab**: 50d SMA for swing trade entries within weekly uptrends
- **Clean RRG**: 30 ETFs (removed duplicates, kept best per theme)
- **Alerts table**: infrastructure for email/Telegram alerts (V6.1)

## Folder Structure
```
WeinsteinV6/
├── app.py                        ← Dashboard home (V6 new)
├── requirements.txt
├── .github/
│   └── workflows/
│       └── weekly_scan.yml       ← Auto-scan every Saturday
├── pages/
│   ├── 1_Screener.py             ← Sectors + Industries + Daily + Stage 1
│   ├── 2_All_Stocks.py           ← Full market scan
│   ├── 3_Dashboard.py            ← Portfolio dashboard
│   └── 4_Crypto.py               ← Crypto screener
├── scripts/
│   ├── run_weekly_scan.py        ← GitHub Actions scan script
│   └── utils_standalone.py      ← Screener logic (no Streamlit)
└── utils/
    ├── theme.py                  ← CSS + colors
    ├── screener.py               ← Weinstein engine + daily
    └── db.py                     ← Supabase + cache + alerts
```

## Step 1: Supabase SQL

Run this in your Supabase SQL Editor:

```sql
-- Auth tables
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  username text unique not null,
  pw_hash text not null,
  role text default 'user',
  created_at timestamptz default now()
);
create table if not exists portfolios (
  id uuid primary key default gen_random_uuid(),
  username text not null, ticker text not null,
  shares float default 1, avg_cost float default 0,
  notes text default '', created_at timestamptz default now(),
  unique(username, ticker)
);
create table if not exists watchlists (
  id uuid primary key default gen_random_uuid(),
  username text not null, ticker text not null,
  tag text default 'watch', notes text default '',
  created_at timestamptz default now(),
  unique(username, ticker)
);
create table if not exists invite_codes (
  code text primary key, used boolean default false,
  created_by text, used_by text,
  created_at timestamptz default now()
);

-- V6 new tables
create table if not exists scan_cache (
  id text primary key,
  scan_type text not null,
  data jsonb not null,
  scan_date date not null,
  created_at timestamptz default now()
);
create table if not exists alerts (
  id uuid primary key default gen_random_uuid(),
  username text not null,
  ticker text not null,
  alert_type text default 'sma_cross',
  threshold float,
  active boolean default true,
  triggered_at timestamptz,
  created_at timestamptz default now()
);

-- Disable RLS (server-side app with service key)
alter table users disable row level security;
alter table portfolios disable row level security;
alter table watchlists disable row level security;
alter table invite_codes disable row level security;
alter table scan_cache disable row level security;
alter table alerts disable row level security;

-- Seed admin accounts
insert into users (username, pw_hash, role) values
  ('joey',  encode(sha256('weinstein2026'), 'hex'), 'admin'),
  ('roger', encode(sha256('roger123'),      'hex'), 'user')
on conflict (username) do nothing;
```

## Step 2: Streamlit Secrets

In Streamlit Cloud → Manage app → Secrets:
```toml
SUPABASE_URL = "https://rlcqstahxlktthspagoz.supabase.co"
SUPABASE_KEY = "your-service-role-key"
```

## Step 3: GitHub Actions Secrets

In GitHub → Settings → Secrets and variables → Actions → New repository secret:
- `SUPABASE_URL` = your Supabase project URL
- `SUPABASE_KEY` = your service role key

The workflow runs automatically every Saturday at 07:00 UTC.
You can also trigger it manually via Actions → Weekly Weinstein Scan → Run workflow.

## Step 4: Deploy to Streamlit Cloud

- Repository: `Djowie282/WeinsteinV6`
- Branch: `main`
- Main file: `app.py`

## How the cache works

1. GitHub Actions runs every Saturday at 07:00 UTC
2. Scans all sector ETFs + ~400 stocks, writes to `scan_cache` table
3. When you open the app, `get_spx_data()` checks Supabase first
4. If cache is fresh (≤7 days): instant load from DB
5. If cache is stale/missing: live scan from Yahoo Finance (with retry)

Result: app opens instantly on Monday morning instead of making you wait 10+ minutes.
