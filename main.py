import os
import requests
import google.generativeai as genai

# Replace with your actual Gemini API key, or set the GEMINI_API_KEY environment variable
API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")


def get_btc_price():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin", "vs_currencies": "usd"}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data["bitcoin"]["usd"]


def get_trading_advice(price):
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = (
        f"The current Bitcoin price is ${price:,.2f} USD. "
        "In one sentence, should I buy, sell, or hold? Give a brief reason."
    )
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Could not retrieve AI advice: {e}"


def main():
    price = get_btc_price()
    print(f"Current BTC Price: ${price:,.2f} USD")

    advice = get_trading_advice(price)
    print(f"AI Advice: {advice}")


if __name__ == "__main__":
    main()
