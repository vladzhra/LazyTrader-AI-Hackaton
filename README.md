# 🚀 LazyTrader AI

**LazyTrader AI** is an autonomous AI-powered crypto paper trading bot. It watches live Bitcoin and Ethereum prices, asks Google Gemini what to do, executes simulated trades, and tracks portfolio performance — all from a single interactive web dashboard.

One magic button. Full AI-driven trading session. No human judgment required.

---

## Features

- **⚡ Magic Auto-Trade** — one click triggers 3 consecutive AI-driven trading rounds with live animated updates
- **🔬 AI Backtest** — sends 30 days of real BTC + ETH price history to Gemini in a single prompt; simulates daily trades and compares the AI strategy against simple Buy & Hold
- **📈 Portfolio Chart** — live area chart of portfolio value growing over time
- **💼 Multi-asset** — trades both Bitcoin (BTC) and Ethereum (ETH)
- **📋 Trade History** — full log of every decision with price, amount, and timestamp
- **🔄 Reset** — wipe the portfolio back to $10,000 for a clean demo

---

## How it works

```
CoinGecko API  ──►  Live BTC + ETH prices
                         │
                         ▼
              Google Gemini (LLM)  ──►  ACTION: BUY_BTC | SELL_ETH | HOLD
                                              │
                                              ▼
                                   Paper trade executed
                                   wallet.json updated
                                              │
                                              ▼
                                   Streamlit dashboard refreshes
```

1. **Market Data** — fetches real-time BTC and ETH prices (24h change) from the free CoinGecko REST API.
2. **AI Analysis** — builds a structured prompt with current prices and portfolio state, sends it to Gemini, and parses a structured response (`ACTION / CONFIDENCE / REASON`).
3. **Paper Trading** — executes the trade on a simulated $10,000 portfolio stored in `wallet.json`. No real money involved.
4. **Backtest** — pulls 30 days of daily OHLC data, packs it all into one Gemini prompt, gets a decision per day, simulates the full sequence, and plots AI Strategy vs Buy & Hold.

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| **UI / App** | [Streamlit](https://streamlit.io/) | Instant Python web apps with zero frontend code |
| **AI / LLM** | [Google Gemini](https://ai.google.dev/) (`gemini-2.5-flash`) | Fast, cheap, strong reasoning for structured decisions |
| **Market Data** | [CoinGecko API](https://www.coingecko.com/en/api) | Free, no auth required, real-time crypto prices |
| **Data wrangling** | [pandas](https://pandas.pydata.org/) | DataFrame manipulation for charts and backtest simulation |
| **Storage** | JSON (`wallet.json`) | Simple, portable, human-readable portfolio persistence |
| **HTTP** | Python `urllib` (stdlib) | No extra dependency for API calls |
| **Config** | `.env` file | Keeps the API key out of source code |

---

## Requirements

- Python 3.8+
- A free [Google Gemini API key](https://aistudio.google.com/app/apikey)

---

## Setup

1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Add your Gemini API key** — create a `.env` file:
   ```dotenv
   GEMINI_API_KEY=your_actual_api_key_here
   ```

---

## Usage

```bash
streamlit run main.py
```

The app opens at `http://localhost:8501`.

**Demo flow:**
1. Click **🚀 Run AI Backtest** — watch Gemini analyze 30 days of real data and compare vs Buy & Hold
2. Click **⚡ MAGIC AUTO-TRADE** — 3 live AI trading rounds with real-time updates and balloons on profit
3. Watch the portfolio chart grow

---

## Project structure

```
.
├── main.py           # All app logic and UI
├── wallet.json       # Live portfolio state (auto-created)
├── requirements.txt  # Python dependencies
└── .env              # API key (not committed)
```
