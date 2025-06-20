import argparse
import yfinance as yf

import pandas as pd

def fetch_stock_data(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch historical data for a ticker from Yahoo Finance."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    return hist

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute common statistics for the equity."""
    df = df.copy()
    df["Daily Return"] = df["Close"].pct_change()
    df["50MA"] = df["Close"].rolling(window=50).mean()
    df["200MA"] = df["Close"].rolling(window=200).mean()
    return df

def generate_summary(ticker: str, df: pd.DataFrame) -> str:
    last = df.iloc[-1]
    summary = f"""# {ticker} Equity Report

- Last Close: {last['Close']:.2f}
- Volume: {int(last['Volume'])}

## Moving Averages
- 50-day MA: {last['50MA']:.2f}
- 200-day MA: {last['200MA']:.2f}
"""
    return summary

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a simple equity report")
    parser.add_argument("ticker", help="Ticker symbol. Use the .NS suffix for NSE.")
    parser.add_argument("--period", default="1y", help="Data period to download")
    parser.add_argument("--output", default="report.md", help="Output markdown file")
    args = parser.parse_args()

    hist = fetch_stock_data(args.ticker, period=args.period)
    hist = compute_metrics(hist)
    summary = generate_summary(args.ticker, hist)
    with open(args.output, "w") as f:
        f.write(summary)
    print(f"Report written to {args.output}")

if __name__ == "__main__":
    main()
