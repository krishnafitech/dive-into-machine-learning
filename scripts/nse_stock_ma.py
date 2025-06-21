import argparse
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
try:
    from nsepy import get_history
except ImportError as e:
    raise SystemExit("This script requires the 'nsepy' package. Install it via pip.")


def parse_args():
    parser = argparse.ArgumentParser(description="Plot 50- and 200-day moving averages for NSE stock data")
    parser.add_argument("symbol", help="Stock symbol, e.g. INFY")
    parser.add_argument("start", help="Start date in YYYY-MM-DD format")
    parser.add_argument("end", help="End date in YYYY-MM-DD format")
    return parser.parse_args()


def fetch_data(symbol: str, start: str, end: str) -> pd.DataFrame:
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    df = get_history(symbol=symbol, start=start_date, end=end_date)
    if df.empty:
        raise ValueError("No data returned. Check symbol and date range")
    return df


def compute_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_index()
    df["MA50"] = df["Close"].rolling(window=50).mean()
    df["MA200"] = df["Close"].rolling(window=200).mean()
    return df


def plot_data(df: pd.DataFrame, symbol: str):
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df["Close"], label="Close")
    plt.plot(df.index, df["MA50"], label="50-day MA")
    plt.plot(df.index, df["MA200"], label="200-day MA")
    plt.title(f"{symbol} closing price with moving averages")
    plt.xlabel("Date")
    plt.ylabel("Price (INR)")
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    args = parse_args()
    df = fetch_data(args.symbol, args.start, args.end)
    df = compute_moving_averages(df)
    plot_data(df, args.symbol)


if __name__ == "__main__":
    main()
