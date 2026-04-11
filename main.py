import os
import json
import time
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def load_dotenv_file(path=".env"):
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


load_dotenv_file()

import streamlit as st
import pandas as pd

API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
INITIAL_USD = 10000.0


# ─── Wallet ──────────────────────────────────────────────────────────────────

def load_wallet():
    default = {
        "usd": INITIAL_USD,
        "btc": 0.0,
        "eth": 0.0,
        "initial_value": INITIAL_USD,
        "trade_history": [],
        "portfolio_history": [
            {"timestamp": datetime.now(timezone.utc).isoformat(), "value": INITIAL_USD}
        ],
    }
    if os.path.exists("wallet.json"):
        data = json.load(open("wallet.json"))
        for k, v in default.items():
            if k not in data:
                data[k] = v
        return data
    return default


def save_wallet(wallet):
    with open("wallet.json", "w") as f:
        json.dump(wallet, f, indent=2)


def reset_wallet():
    wallet = {
        "usd": INITIAL_USD,
        "btc": 0.0,
        "eth": 0.0,
        "initial_value": INITIAL_USD,
        "trade_history": [],
        "portfolio_history": [
            {"timestamp": datetime.now(timezone.utc).isoformat(), "value": INITIAL_USD}
        ],
        "seeded": False,
    }
    save_wallet(wallet)
    return wallet


def seed_portfolio_history(wallet):
    """
    Pre-populate portfolio_history with 7 days of simulated trading on real
    BTC + ETH hourly prices (momentum strategy, no AI needed).
    This makes the performance chart look alive from the very first load.
    """
    try:
        # Hourly prices for the last 7 days (~168 points each)
        btc_h, _ = get_historical_prices("bitcoin", 7)
        eth_h, _ = get_historical_prices("ethereum", 7)
        if not btc_h or not eth_h or len(btc_h) < 10:
            return wallet

        n = min(len(btc_h), len(eth_h))
        sim = {"usd": INITIAL_USD, "btc": 0.0, "eth": 0.0}
        history = []
        trades = []

        for i in range(n):
            ts_ms, bp = btc_h[i]
            ep = eth_h[i][1]
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()

            if i >= 3:
                # Simple momentum: compare current price to 3 periods ago
                bp_prev = btc_h[i - 3][1]
                ep_prev = eth_h[i - 3][1]
                btc_mom = (bp - bp_prev) / bp_prev * 100
                eth_mom = (ep - ep_prev) / ep_prev * 100

                if btc_mom > 0.4 and sim["usd"] > 200:
                    spend = sim["usd"] * 0.5
                    bought = spend / bp
                    sim["usd"] -= spend
                    sim["btc"] += bought
                    trades.append({"timestamp": ts, "action": "BUY", "coin": "BTC",
                                   "amount": bought, "price": bp, "usd_value": spend})

                elif eth_mom > 0.5 and sim["usd"] > 200:
                    spend = sim["usd"] * 0.4
                    bought = spend / ep
                    sim["usd"] -= spend
                    sim["eth"] += bought
                    trades.append({"timestamp": ts, "action": "BUY", "coin": "ETH",
                                   "amount": bought, "price": ep, "usd_value": spend})

                elif btc_mom < -0.5 and sim["btc"] > 0:
                    sold = sim["btc"] * 0.5
                    gained = sold * bp
                    sim["btc"] -= sold
                    sim["usd"] += gained
                    trades.append({"timestamp": ts, "action": "SELL", "coin": "BTC",
                                   "amount": sold, "price": bp, "usd_value": gained})

                elif eth_mom < -0.6 and sim["eth"] > 0:
                    sold = sim["eth"] * 0.5
                    gained = sold * ep
                    sim["eth"] -= sold
                    sim["usd"] += gained
                    trades.append({"timestamp": ts, "action": "SELL", "coin": "ETH",
                                   "amount": sold, "price": ep, "usd_value": gained})

            total = sim["usd"] + sim["btc"] * bp + sim["eth"] * ep
            history.append({"timestamp": ts, "value": total})

        # Carry over the simulated state into the real wallet
        wallet["usd"] = sim["usd"]
        wallet["btc"] = sim["btc"]
        wallet["eth"] = sim["eth"]
        wallet["portfolio_history"] = history
        wallet["trade_history"] = trades
        wallet["seeded"] = True
        return wallet
    except Exception:
        wallet["seeded"] = True  # Don't retry on error
        return wallet


# ─── Market Data ─────────────────────────────────────────────────────────────

def get_market_data():
    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
        )
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        return (
            data["bitcoin"]["usd"],
            data["bitcoin"].get("usd_24h_change", 0.0),
            data["ethereum"]["usd"],
            data["ethereum"].get("usd_24h_change", 0.0),
        )
    except Exception:
        return 85000.0, 0.0, 3000.0, 0.0


def get_historical_prices(coin="bitcoin", days=30):
    """Returns (prices_list, error_str). On success error_str is None."""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    last_err = None
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
            return [(p[0], p[1]) for p in data["prices"]], None
        except Exception as e:
            last_err = str(e)
            if "429" in last_err or "Too Many" in last_err:
                time.sleep(2 * (attempt + 1))
                continue
            return [], last_err
    return [], f"Rate limited by CoinGecko: {last_err}"


# ─── Gemini ───────────────────────────────────────────────────────────────────

def _list_gemini_models():
    """Return available generateContent model names from the API."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        names = []
        for m in data.get("models", []):
            name = m.get("name", "")  # e.g. "models/gemini-1.5-flash"
            supported = m.get("supportedGenerationMethods", [])
            if "generateContent" in supported and name.startswith("models/"):
                names.append(name.replace("models/", ""))
        return names
    except Exception:
        return []


def call_gemini(prompt):
    if API_KEY == "YOUR_API_KEY_HERE":
        return None, "GEMINI_API_KEY not set"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    # Preferred models in order; fall back to whatever the API reports
    preferred = [
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.0-pro",
    ]
    # Append any models returned by the API that aren't already in the list
    for m in _list_gemini_models():
        if m not in preferred and "flash" in m.lower():
            preferred.append(m)

    last_err = None
    for model in preferred:
        for api_version in ("v1beta", "v1"):
            endpoint = (
                f"https://generativelanguage.googleapis.com/{api_version}/models/"
                f"{model}:generateContent?key={API_KEY}"
            )
            req = Request(
                endpoint,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urlopen(req, timeout=30) as r:
                    resp = json.loads(r.read().decode())
                candidates = resp.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip(), None
            except Exception as e:
                last_err = e
                break  # 404/403 on this model → try next model
    return None, str(last_err)


# ─── Trading Logic ────────────────────────────────────────────────────────────

def get_trading_advice(btc_price, btc_change, eth_price, eth_change, wallet):
    total = wallet["usd"] + wallet["btc"] * btc_price + wallet["eth"] * eth_price
    prompt = (
        f"You are a sharp crypto trading AI. Live market snapshot:\n"
        f"  Bitcoin  (BTC): ${btc_price:,.2f}  (24h: {btc_change:+.2f}%)\n"
        f"  Ethereum (ETH): ${eth_price:,.2f}  (24h: {eth_change:+.2f}%)\n\n"
        f"My portfolio:\n"
        f"  Cash : ${wallet['usd']:,.2f} USD\n"
        f"  BTC  : {wallet['btc']:.6f} ({wallet['btc'] * btc_price:,.2f} USD)\n"
        f"  ETH  : {wallet['eth']:.6f} ({wallet['eth'] * eth_price:,.2f} USD)\n"
        f"  Total: ${total:,.2f} USD\n\n"
        f"Respond in this EXACT format (3 lines, no extra text):\n"
        f"ACTION: <BUY_BTC|BUY_ETH|SELL_BTC|SELL_ETH|HOLD>\n"
        f"CONFIDENCE: <HIGH|MEDIUM|LOW>\n"
        f"REASON: <one sentence>\n"
    )
    text, err = call_gemini(prompt)
    if text:
        return text
    return f"ACTION: HOLD\nCONFIDENCE: LOW\nREASON: {err or 'AI unavailable.'}"


def parse_advice(text):
    action, confidence, reason = "HOLD", "MEDIUM", ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("CONFIDENCE:"):
            confidence = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return action, confidence, reason


def execute_trade(action, btc_price, eth_price, wallet):
    ts = datetime.now(timezone.utc).isoformat()
    before = wallet["usd"] + wallet["btc"] * btc_price + wallet["eth"] * eth_price
    trade_log = None
    result = "HOLD — no transaction."

    if action == "BUY_BTC" and wallet["usd"] > 100:
        spend = wallet["usd"] * 0.50
        bought = spend / btc_price
        wallet["usd"] -= spend
        wallet["btc"] += bought
        result = f"Bought {bought:.6f} BTC for ${spend:,.2f}"
        trade_log = {"action": "BUY", "coin": "BTC", "amount": bought, "price": btc_price, "usd_value": spend}

    elif action == "BUY_ETH" and wallet["usd"] > 100:
        spend = wallet["usd"] * 0.50
        bought = spend / eth_price
        wallet["usd"] -= spend
        wallet["eth"] += bought
        result = f"Bought {bought:.6f} ETH for ${spend:,.2f}"
        trade_log = {"action": "BUY", "coin": "ETH", "amount": bought, "price": eth_price, "usd_value": spend}

    elif action == "SELL_BTC" and wallet["btc"] > 0:
        sold = wallet["btc"] * 0.60
        gained = sold * btc_price
        wallet["btc"] -= sold
        wallet["usd"] += gained
        result = f"Sold {sold:.6f} BTC for ${gained:,.2f}"
        trade_log = {"action": "SELL", "coin": "BTC", "amount": sold, "price": btc_price, "usd_value": gained}

    elif action == "SELL_ETH" and wallet["eth"] > 0:
        sold = wallet["eth"] * 0.60
        gained = sold * eth_price
        wallet["eth"] -= sold
        wallet["usd"] += gained
        result = f"Sold {sold:.6f} ETH for ${gained:,.2f}"
        trade_log = {"action": "SELL", "coin": "ETH", "amount": sold, "price": eth_price, "usd_value": gained}

    after = wallet["usd"] + wallet["btc"] * btc_price + wallet["eth"] * eth_price

    if trade_log:
        trade_log.update({"timestamp": ts, "portfolio_value": after, "pnl": after - before})
        wallet["trade_history"].append(trade_log)

    wallet["portfolio_history"].append({"timestamp": ts, "value": after})
    return result, after


# ─── Backtest ─────────────────────────────────────────────────────────────────

def run_backtest(btc_hist, eth_hist):
    n = min(len(btc_hist), len(eth_hist), 30)
    btc_hist, eth_hist = btc_hist[:n], eth_hist[:n]

    rows = ""
    for i in range(n):
        date = datetime.fromtimestamp(btc_hist[i][0] / 1000).strftime("%Y-%m-%d")
        rows += f"Day {i+1} ({date}): BTC=${btc_hist[i][1]:,.0f}, ETH={eth_hist[i][1]:,.0f}\n"

    prompt = (
        "You are a crypto trading AI running a 30-day backtest on real historical prices.\n\n"
        f"Daily closing prices:\n{rows}\n"
        "Starting capital: $10,000 USD, 0 BTC, 0 ETH.\n"
        "Trade rules (fixed, you cannot change them):\n"
        "  BUY_BTC  → spend 25% of current USD on BTC\n"
        "  BUY_ETH  → spend 25% of current USD on ETH\n"
        "  SELL_BTC → sell 40% of current BTC holding\n"
        "  SELL_ETH → sell 40% of current ETH holding\n"
        "  HOLD     → do nothing\n\n"
        "Analyze the trends carefully. Your goal: maximize final portfolio value.\n"
        "Respond ONLY with a valid JSON array — no markdown, no code fences:\n"
        '[{"day":1,"action":"HOLD","reason":"brief reason"}, ...]\n'
        "Valid actions: BUY_BTC, BUY_ETH, SELL_BTC, SELL_ETH, HOLD"
    )

    text, err = call_gemini(prompt)
    if not text:
        return None, f"Gemini error: {err}"

    try:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        decisions = json.loads(m.group() if m else text)
    except Exception:
        return None, f"Could not parse AI JSON. Response: {text[:300]}"

    # Simulate
    w = {"usd": 10000.0, "btc": 0.0, "eth": 0.0}
    history = [{"day": 0, "date": "Start", "value": 10000.0, "action": "—"}]

    for i, dec in enumerate(decisions):
        if i >= n:
            break
        bp, ep = btc_hist[i][1], eth_hist[i][1]
        date = datetime.fromtimestamp(btc_hist[i][0] / 1000).strftime("%m/%d")
        a = str(dec.get("action", "HOLD")).upper()

        if a == "BUY_BTC" and w["usd"] > 100:
            sp = w["usd"] * 0.25; w["btc"] += sp / bp; w["usd"] -= sp
        elif a == "BUY_ETH" and w["usd"] > 100:
            sp = w["usd"] * 0.25; w["eth"] += sp / ep; w["usd"] -= sp
        elif a == "SELL_BTC" and w["btc"] > 0:
            w["usd"] += w["btc"] * 0.4 * bp; w["btc"] *= 0.6
        elif a == "SELL_ETH" and w["eth"] > 0:
            w["usd"] += w["eth"] * 0.4 * ep; w["eth"] *= 0.6

        total = w["usd"] + w["btc"] * bp + w["eth"] * ep
        history.append({"day": i + 1, "date": date, "value": total, "action": a, "reason": dec.get("reason", "")})

    # Buy-and-hold BTC benchmark
    bh_btc = 10000.0 / btc_hist[0][1]
    bh_final = bh_btc * btc_hist[n - 1][1]

    return {
        "history": history,
        "decisions": decisions,
        "final_value": history[-1]["value"],
        "buy_hold_value": bh_final,
        "n_days": n,
    }, None


# ─── UI ───────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="LazyTrader AI",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; }
        h1 { font-size: 2.6rem !important; }
        .stMetric label { font-size: 0.85rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🚀 LazyTrader AI")
    st.caption("Autonomous AI-powered crypto trading · Powered by Google Gemini")

    wallet = load_wallet()

    # Seed history only once per session (never blocks subsequent interactions)
    if not st.session_state.get("seeded_done") and not wallet.get("seeded", False):
        st.session_state.seeded_done = True
        with st.spinner("📊 Preparing portfolio with 7 days of real market history…"):
            wallet = seed_portfolio_history(wallet)
            save_wallet(wallet)
    else:
        st.session_state.seeded_done = True

    # Cache market data for 60 s
    now = time.time()
    if "mkt" not in st.session_state or now - st.session_state.get("mkt_t", 0) > 60:
        btc_price, btc_chg, eth_price, eth_chg = get_market_data()
        st.session_state.mkt = (btc_price, btc_chg, eth_price, eth_chg)
        st.session_state.mkt_t = now
    else:
        btc_price, btc_chg, eth_price, eth_chg = st.session_state.mkt

    total = wallet["usd"] + wallet["btc"] * btc_price + wallet["eth"] * eth_price
    init = wallet.get("initial_value", INITIAL_USD)
    pnl = total - init
    pnl_pct = pnl / init * 100

    # ── Top KPIs ──
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("₿ Bitcoin", f"${btc_price:,.0f}", f"{btc_chg:+.2f}%")
    k2.metric("Ξ Ethereum", f"${eth_price:,.0f}", f"{eth_chg:+.2f}%")
    k3.metric("💼 Portfolio", f"${total:,.2f}", f"{pnl_pct:+.2f}%")
    k4.metric("💰 P&L", f"{'+'if pnl>=0 else ''}${pnl:,.2f}")
    k5.metric("📊 Trades", str(len(wallet.get("trade_history", []))))
    k6.metric("💵 Cash", f"${wallet['usd']:,.2f}")

    st.divider()



    # ── Two-column layout ──
    left, right = st.columns([1, 1], gap="large")

    with left:
        st.subheader("🤖 AI Trading Engine")

        # ── Auto-trade toggle ──
        auto_on = st.toggle(
            "🔄 Auto-Trade Mode — Gemini trades every 60 seconds",
            value=st.session_state.get("auto_on", False),
        )
        st.session_state.auto_on = auto_on

        c1, c2 = st.columns(2)
        single = c1.button("⚡ Trade Now", use_container_width=True, type="primary")
        reset = c2.button("🔄 Reset Portfolio", use_container_width=True)

        if reset:
            wallet = reset_wallet()
            st.session_state.pop("mkt", None)
            st.session_state.pop("last_auto_t", None)
            st.success("Portfolio reset to $10,000!")
            time.sleep(0.8)
            st.rerun()

        status = st.empty()

        # Persistent last-trade result (survives reruns)
        if st.session_state.get("last_trade_msg"):
            st.success(st.session_state.last_trade_msg)

        # ── Auto-trade logic: fires every 60 s while toggle is ON ──
        if auto_on:
            last_t = st.session_state.get("last_auto_t", 0)
            elapsed = time.time() - last_t
            remaining = max(0, 60 - elapsed)

            if elapsed >= 60 or last_t == 0:
                status.info("🤖 Auto-trade triggered — asking Gemini…")
                btc_price, btc_chg, eth_price, eth_chg = get_market_data()
                st.session_state.mkt = (btc_price, btc_chg, eth_price, eth_chg)

                raw = get_trading_advice(btc_price, btc_chg, eth_price, eth_chg, wallet)
                action, conf, reason = parse_advice(raw)
                conf_dot = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(conf, "⚪")

                trade_msg, new_total = execute_trade(action, btc_price, eth_price, wallet)
                save_wallet(wallet)
                st.session_state.last_auto_t = time.time()

                cur_pnl = new_total - init
                cur_pct = cur_pnl / init * 100
                sign = "+" if cur_pnl >= 0 else ""
                st.session_state.last_trade_msg = (
                    f"**AI:** `{action}` {conf_dot} {conf} — _{reason}_\n\n"
                    f"✅ {trade_msg} · Portfolio: **${new_total:,.2f}** ({sign}{cur_pct:.2f}%)"
                )
                if cur_pnl >= 0:
                    st.balloons()
                st.rerun()
            else:
                status.info(f"⏱ Next AI trade in **{remaining:.0f}s** · Auto-Trade ON")
                time.sleep(1)
                st.rerun()

        # ── Manual single trade ──
        elif single:
            status.info("🧠 Gemini is analyzing…")
            btc_price, btc_chg, eth_price, eth_chg = get_market_data()
            st.session_state.mkt = (btc_price, btc_chg, eth_price, eth_chg)

            raw = get_trading_advice(btc_price, btc_chg, eth_price, eth_chg, wallet)
            action, conf, reason = parse_advice(raw)
            conf_dot = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(conf, "⚪")

            trade_msg, new_total = execute_trade(action, btc_price, eth_price, wallet)
            save_wallet(wallet)

            cur_pnl = new_total - init
            cur_pct = cur_pnl / init * 100
            sign = "+" if cur_pnl >= 0 else ""
            st.session_state.last_trade_msg = (
                f"**AI:** `{action}` {conf_dot} {conf} — _{reason}_\n\n"
                f"✅ {trade_msg} · Portfolio: **${new_total:,.2f}** ({sign}{cur_pct:.2f}%)"
            )
            if cur_pnl >= 0:
                st.balloons()
            st.rerun()

    with right:
        st.subheader("📋 Trade History")
        trades = wallet.get("trade_history", [])
        if trades:
            for t in reversed(trades[-12:]):
                dot = "🟢" if t["action"] == "BUY" else "🔴"
                ts = t.get("timestamp", "")[:10]
                st.write(
                    f"{dot} **{t['action']} {t['coin']}** · "
                    f"{t['amount']:.5f} @ ${t['price']:,.0f} · "
                    f"${t['usd_value']:,.2f} · {ts}"
                )
        else:
            st.info("No trades yet — press the Magic Auto-Trade button!")

    st.divider()

    # ── Backtest section ──
    st.subheader("🔬 AI Strategy Backtest — Last 30 Days of Real Data")
    st.caption(
        "Sends 30 days of real BTC + ETH prices to Gemini in **one shot**. "
        "The AI decides what to do each day, then we compare against simple Buy & Hold."
    )

    if st.button("🚀 Run AI Backtest (30 days)", use_container_width=True):
        with st.spinner("Fetching 30 days of BTC + ETH price history from CoinGecko…"):
            btc_h, btc_err = get_historical_prices("bitcoin", 30)
            eth_h, eth_err = get_historical_prices("ethereum", 30)

        fetch_err = btc_err or eth_err
        if not btc_h or not eth_h:
            st.error(f"Could not fetch historical data: {fetch_err}")
        else:
            with st.spinner("🧠 Gemini is analyzing 30 days of data — this takes ~10 seconds…"):
                result, err = run_backtest(btc_h, eth_h)

            if err:
                st.error(f"Backtest error: {err}")
            else:
                fv = result["final_value"]
                bh = result["buy_hold_value"]
                ai_pct = (fv - 10000) / 10000 * 100
                bh_pct = (bh - 10000) / 10000 * 100
                alpha = ai_pct - bh_pct

                r1, r2, r3 = st.columns(3)
                r1.metric("🤖 AI Strategy", f"${fv:,.2f}", f"{ai_pct:+.2f}%")
                r2.metric("📈 Buy & Hold BTC", f"${bh:,.2f}", f"{bh_pct:+.2f}%")
                r3.metric("⚡ AI Alpha", f"{alpha:+.2f}%", "vs Buy & Hold")

                if alpha > 0:
                    st.success(f"🏆 AI OUTPERFORMED Buy & Hold by **{alpha:.2f}%** over 30 days!")
                else:
                    msg = "gained" if ai_pct >= 0 else "lost"
                    st.info(f"AI strategy {msg} **{abs(ai_pct):.2f}%** over 30 days (Buy & Hold: {bh_pct:+.2f}%).")

                # Build comparison chart
                hist_bt = result["history"]
                df_bt = pd.DataFrame(hist_bt).set_index("day")
                start_btc = btc_h[0][1]
                df_bt["Buy & Hold BTC"] = [
                    10000.0 * (btc_h[min(i, len(btc_h) - 1)][1] / start_btc)
                    for i in range(len(df_bt))
                ]
                df_bt.rename(columns={"value": "AI Strategy"}, inplace=True)
                st.line_chart(df_bt[["AI Strategy", "Buy & Hold BTC"]], height=320)

                with st.expander("📊 View AI Daily Decisions"):
                    for d in result["decisions"][:30]:
                        a = d.get("action", "HOLD")
                        emoji = {
                            "BUY_BTC": "🟢₿", "BUY_ETH": "🟢Ξ",
                            "SELL_BTC": "🔴₿", "SELL_ETH": "🔴Ξ",
                            "HOLD": "⚪",
                        }.get(a, "⚪")
                        st.write(f"Day {d.get('day','?')}: {emoji} **{a}** — {d.get('reason','')}")

    st.divider()
    st.caption("⚡ AI by Google Gemini · Market data by CoinGecko · Built for the AI Hackathon")


if __name__ == "__main__":
    main()
