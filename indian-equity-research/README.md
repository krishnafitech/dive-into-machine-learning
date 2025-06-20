# Indian Equity Research Automation

This example shows how to generate a simple research report for an Indian equity using Python.

The script relies on the [`yfinance`](https://pypi.org/project/yfinance/) package to fetch historical price data from Yahoo Finance. Metrics like daily returns and moving averages are computed with `pandas` and written to a Markdown file.

## Requirements

```bash
pip install yfinance pandas
```

## Usage

```bash
python generate_report.py RELIANCE.NS --period 6mo --output reliance_report.md
```

This command downloads six months of price data for Reliance Industries (ticker `RELIANCE.NS`) and writes a basic Markdown report to `reliance_report.md`.
