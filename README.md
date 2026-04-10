# LazyTrader AI

**LazyTrader AI** is a simple Python trading agent that checks the current Bitcoin (BTC) price and asks a large language model (LLM) what to do — buy, sell, or hold — in a single sentence.

No complex charts. No fancy algorithms. Just real-time price data and straight AI advice.

## How it works

1. Fetches the live BTC/USD price from the free [CoinGecko API](https://www.coingecko.com/en/api).
2. Sends the price to Google's **Gemini 1.5 Flash** model via the `google-generativeai` library.
3. Prints the current price and the AI's one-sentence trading recommendation.

## Requirements

- Python 3.8+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

## Setup

```bash
pip install -r requirements.txt
```

Open `main.py` and replace `YOUR_API_KEY_HERE` with your actual Gemini API key.

## Usage

```bash
python main.py
```

**Example output:**

```
Current BTC Price: $68,432.00 USD
AI Advice: Given Bitcoin's current price, I would hold and wait for a clearer trend before making a move.
```
