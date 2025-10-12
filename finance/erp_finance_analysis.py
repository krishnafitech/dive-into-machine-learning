"""Utilities for analyzing ERP finance data.

This module contains helper functions to clean, normalize, and analyze
Enterprise Resource Planning (ERP) financial exports.  The functions are
pure-Python/pandas so they can run locally in notebooks or be scheduled in a
batch job.  The goal is to provide repeatable analysis to surface accounting
insights such as profitability trends, anomalous postings, and outstanding
invoices.

Example
-------
>>> from pathlib import Path
>>> from finance.erp_finance_analysis import (
...     ERPFinanceConfig,
...     load_erp_data,
...     normalize_currency,
...     compute_period_summary,
...     detect_posting_anomalies,
...     build_aging_report,
... )
>>> config = ERPFinanceConfig(base_currency="USD", exchange_rates={"EUR": 1.1})
>>> df = load_erp_data(Path("erp_export.csv"))
>>> normalized = normalize_currency(df, config)
>>> summary = compute_period_summary(normalized, config)
>>> anomalies = detect_posting_anomalies(normalized, config)
>>> aging = build_aging_report(normalized, config)

All functions are resilient to missing optional columns and provide
informative error messages when required fields are absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd


__all__ = [
    "ERPFinanceConfig",
    "load_erp_data",
    "normalize_currency",
    "compute_period_summary",
    "detect_posting_anomalies",
    "build_aging_report",
    "profitability_by_dimension",
    "run_analysis",
    "main",
]


@dataclass(slots=True)
class ERPFinanceConfig:
    """Configuration describing column names and conversion settings.

    Parameters
    ----------
    date_column:
        Name of the column that stores posting dates.  Values must be
        convertible to pandas ``datetime64``.
    amount_column:
        Column representing the signed monetary value of a posting.
    currency_column:
        Column describing the transaction currency.  Used alongside
        :attr:`exchange_rates` to normalize values into :attr:`base_currency`.
    company_column, cost_center_column, account_column:
        Column names that define the organizational and GL context of the
        entry.  They are optional but unlock richer aggregations when present.
    document_column:
        Column used to uniquely identify an ERP document.  Helpful for
        deduplication and anomaly explanations.
    base_currency:
        Target currency used for normalization.
    exchange_rates:
        Mapping from source currency code to the rate for converting a unit of
        that currency into :attr:`base_currency`.  The rate for
        :attr:`base_currency` is assumed to be 1.
    """

    date_column: str = "posting_date"
    amount_column: str = "amount"
    currency_column: str = "currency"
    company_column: str = "company_code"
    cost_center_column: str = "cost_center"
    account_column: str = "account"
    document_column: str = "document_number"
    base_currency: str = "USD"
    exchange_rates: Mapping[str, float] = field(default_factory=dict)


def _require_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing columns in ERP dataset: {', '.join(missing)}")


def load_erp_data(
    path: Path | str,
    *,
    dtype: Optional[Mapping[str, str]] = None,
    parse_dates: Optional[Sequence[str]] = None,
    na_values: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Load a raw ERP export from CSV/Parquet.

    Parameters
    ----------
    path:
        Path to a CSV or Parquet file.  The file type is inferred from the
        suffix.
    dtype, parse_dates, na_values:
        Passed through to :func:`pandas.read_csv` when applicable.

    Returns
    -------
    pandas.DataFrame
        A dataframe containing the loaded ERP data.
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, dtype=dtype, parse_dates=parse_dates, na_values=na_values)
    return df


def normalize_currency(df: pd.DataFrame, config: ERPFinanceConfig) -> pd.DataFrame:
    """Convert postings to the base currency defined in ``config``.

    The function leaves the original dataframe untouched by operating on a
    copy.  When a posting currency is not present in the provided exchange rate
    table the observation is flagged in a ``conversion_status`` column.

    Returns
    -------
    pandas.DataFrame
        DataFrame containing the normalized ``amount_base`` column and a
        ``conversion_status`` diagnostic flag.
    """

    df = df.copy()
    _require_columns(df, [config.amount_column, config.currency_column])

    exchange_rates = {config.base_currency: 1.0, **dict(config.exchange_rates)}
    df["exchange_rate"] = df[config.currency_column].map(exchange_rates)

    df["conversion_status"] = np.where(
        df["exchange_rate"].notna(), "converted", "missing_rate"
    )
    df["amount_base"] = df[config.amount_column] * df["exchange_rate"].fillna(np.nan)
    return df


def compute_period_summary(
    df: pd.DataFrame,
    config: ERPFinanceConfig,
    *,
    freq: str = "M",
    measures: Optional[Mapping[str, str]] = None,
) -> pd.DataFrame:
    """Aggregate normalized postings into financial statements.

    Parameters
    ----------
    df:
        Dataframe containing at least the columns specified in ``config`` and
        the ``amount_base`` column created by :func:`normalize_currency`.
    freq:
        A pandas offset string controlling the aggregation period (``"M"`` for
        month-end, ``"Q"`` for quarter-end, etc.).
    measures:
        Optional mapping from output column names to aggregation functions.
        Defaults to computing total revenue, expenses, and net amount.

    Returns
    -------
    pandas.DataFrame
        Indexed by period with aggregated metrics and optionally company and
        cost center breakdowns.
    """

    _require_columns(df, [config.date_column, "amount_base"])
    working = df.copy()
    working[config.date_column] = pd.to_datetime(working[config.date_column])

    groupers: List[str] = []
    for column in (config.company_column, config.cost_center_column):
        if column in working.columns:
            groupers.append(column)

    working.set_index(config.date_column, inplace=True)

    if measures is None:
        measures = {
            "revenue": (config.amount_column, lambda s: s[s > 0].sum()),
            "expenses": (config.amount_column, lambda s: s[s < 0].sum()),
            "net_amount": (config.amount_column, "sum"),
            "net_amount_base": ("amount_base", "sum"),
        }

    aggregations = {
        name: pd.NamedAgg(column=column, aggfunc=agg)
        for name, (column, agg) in measures.items()
    }

    summary = (
        working
        .assign(**{config.amount_column: working["amount_base"]})
        .groupby(groupers + [pd.Grouper(freq=freq)])
        .agg(**aggregations)
        .reset_index()
        .rename(columns={config.date_column: "period"})
    )
    return summary


def detect_posting_anomalies(
    df: pd.DataFrame,
    config: ERPFinanceConfig,
    *,
    z_threshold: float = 3.0,
    min_postings: int = 30,
) -> pd.DataFrame:
    """Detect anomalous postings using a z-score heuristic.

    The function computes the distribution of absolute ``amount_base`` values
    per account (and optionally cost center).  Postings with a z-score larger
    than ``z_threshold`` are flagged as anomalies.  Accounts with insufficient
    volume (``min_postings``) are ignored to avoid noisy scores.
    """

    required = [config.account_column, "amount_base"]
    _require_columns(df, required)

    if config.cost_center_column in df.columns:
        group_cols = [config.account_column, config.cost_center_column]
    else:
        group_cols = [config.account_column]

    working = df.copy()
    working["abs_amount"] = working["amount_base"].abs()

    stats = (
        working.groupby(group_cols)["abs_amount"].agg(["mean", "std", "count"])
    )
    stats = stats.rename(
        columns={"mean": "group_mean", "std": "group_std", "count": "group_count"}
    )
    stats["group_std"] = stats["group_std"].replace(0, np.nan)

    working = working.join(stats, on=group_cols)
    working = working[working["group_count"] >= min_postings]
    working = working[working["group_std"].notna()]
    working["z_score"] = (working["abs_amount"] - working["group_mean"]) / working["group_std"]
    anomalies = working[working["z_score"].abs() >= z_threshold].copy()

    if config.document_column in anomalies.columns:
        sort_cols = [config.account_column, "z_score", config.document_column]
    else:
        sort_cols = [config.account_column, "z_score"]
    anomalies.sort_values(by=sort_cols, ascending=[True, False] + [True] * (len(sort_cols) - 2), inplace=True)
    return anomalies


def build_aging_report(
    df: pd.DataFrame,
    config: ERPFinanceConfig,
    *,
    due_date_column: str = "due_date",
    status_column: str = "status",
    open_statuses: Optional[Sequence[str]] = None,
    aging_buckets: Sequence[int] = (0, 30, 60, 90, 120),
) -> pd.DataFrame:
    """Generate an accounts receivable aging analysis.

    Parameters
    ----------
    due_date_column:
        Name of the column with invoice due dates.
    status_column:
        Column describing invoice status.  Only invoices whose status matches
        ``open_statuses`` are considered outstanding.
    open_statuses:
        Iterable of status values considered open.  When ``None`` all invoices
        are treated as open.
    aging_buckets:
        Boundaries for the age buckets in days.  The final bucket captures any
        invoice older than the last threshold.
    """

    _require_columns(df, [config.date_column, due_date_column, "amount_base"])
    working = df.copy()
    working[config.date_column] = pd.to_datetime(working[config.date_column])
    working[due_date_column] = pd.to_datetime(working[due_date_column])

    if open_statuses is not None:
        _require_columns(working, [status_column])
        working = working[working[status_column].isin(set(open_statuses))]

    working["days_past_due"] = (working[config.date_column] - working[due_date_column]).dt.days
    working["days_past_due"] = working["days_past_due"].clip(lower=0)

    bucket_labels = [
        f"{aging_buckets[i]}-{aging_buckets[i + 1]}"
        for i in range(len(aging_buckets) - 1)
    ] + [f">={aging_buckets[-1]}"]

    working["aging_bucket"] = pd.cut(
        working["days_past_due"],
        bins=[-np.inf, *aging_buckets, np.inf],
        labels=bucket_labels,
        right=False,
    )

    groupers = ["aging_bucket"]
    for column in (config.company_column, config.cost_center_column):
        if column in working.columns:
            groupers.append(column)

    summary = (
        working.groupby(groupers)["amount_base"].sum().reset_index().rename(
            columns={"amount_base": "open_amount"}
        )
    )
    return summary


def profitability_by_dimension(
    df: pd.DataFrame,
    config: ERPFinanceConfig,
    dimension: str,
) -> pd.DataFrame:
    """Compute profitability metrics for a single categorical dimension."""

    _require_columns(df, [dimension, "amount_base"])
    metrics = (
        df.groupby(dimension)["amount_base"]
        .agg(total_amount="sum", mean_amount="mean", postings="count")
        .reset_index()
    )
    total_abs = metrics["total_amount"].abs().sum()
    if total_abs == 0:
        metrics["profit_margin"] = 0.0
    else:
        metrics["profit_margin"] = metrics["total_amount"] / total_abs
    return metrics.sort_values(by="total_amount", ascending=False)


def run_analysis(
    path: Path | str,
    config: ERPFinanceConfig,
    *,
    freq: str = "M",
    open_statuses: Optional[Sequence[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """Convenience wrapper that runs the full ERP finance workflow."""

    df = load_erp_data(path, parse_dates=[config.date_column])
    normalized = normalize_currency(df, config)
    period_summary = compute_period_summary(normalized, config, freq=freq)
    anomalies = detect_posting_anomalies(normalized, config)
    aging = build_aging_report(normalized, config, open_statuses=open_statuses)

    results = {
        "normalized": normalized,
        "period_summary": period_summary,
        "anomalies": anomalies,
        "aging": aging,
    }

    if config.cost_center_column in normalized.columns:
        results["profitability_cost_center"] = profitability_by_dimension(
            normalized, config, config.cost_center_column
        )

    if config.account_column in normalized.columns:
        results["profitability_account"] = profitability_by_dimension(
            normalized, config, config.account_column
        )

    return results


def _format_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    """Return a Markdown preview of a dataframe."""

    if df.empty:
        return "*(no rows)*"
    return df.head(max_rows).to_markdown(index=False)


def _print_report(results: Mapping[str, pd.DataFrame]) -> None:
    """Pretty-print analysis results to stdout."""

    for name, frame in results.items():
        print(f"\n=== {name.replace('_', ' ').title()} ===")
        print(_format_table(frame))


def main(args: Optional[Sequence[str]] = None) -> None:
    """Entry point for command line execution.

    Usage
    -----
    $ python -m finance.erp_finance_analysis path/to/export.csv \
        --base-currency USD --exchange-rate EUR=1.09 --exchange-rate GBP=1.27
    """

    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to the ERP export (CSV or Parquet).")
    parser.add_argument("--date-column", default=ERPFinanceConfig.date_column)
    parser.add_argument("--amount-column", default=ERPFinanceConfig.amount_column)
    parser.add_argument("--currency-column", default=ERPFinanceConfig.currency_column)
    parser.add_argument("--company-column", default=ERPFinanceConfig.company_column)
    parser.add_argument("--cost-center-column", default=ERPFinanceConfig.cost_center_column)
    parser.add_argument("--account-column", default=ERPFinanceConfig.account_column)
    parser.add_argument("--document-column", default=ERPFinanceConfig.document_column)
    parser.add_argument("--base-currency", default=ERPFinanceConfig.base_currency)
    parser.add_argument(
        "--exchange-rate",
        action="append",
        default=[],
        metavar="CURRENCY=RATE",
        help="Add a currency conversion rate to the base currency.",
    )
    parser.add_argument(
        "--freq",
        default="M",
        help="Aggregation frequency (pandas offset alias, e.g. M, Q, Y).",
    )
    parser.add_argument(
        "--open-status",
        action="append",
        default=None,
        help="Invoice status considered open; repeat for multiple values.",
    )

    parsed = parser.parse_args(args=args)

    exchange_rates: Dict[str, float] = {}
    for entry in parsed.exchange_rate:
        try:
            currency, value = entry.split("=", 1)
            exchange_rates[currency.upper()] = float(value)
        except ValueError as exc:  # pragma: no cover - user input validation
            raise ValueError(
                "Exchange rates must be provided as CURRENCY=RATE (e.g. EUR=1.09)"
            ) from exc

    config = ERPFinanceConfig(
        date_column=parsed.date_column,
        amount_column=parsed.amount_column,
        currency_column=parsed.currency_column,
        company_column=parsed.company_column,
        cost_center_column=parsed.cost_center_column,
        account_column=parsed.account_column,
        document_column=parsed.document_column,
        base_currency=parsed.base_currency,
        exchange_rates=exchange_rates,
    )

    results = run_analysis(
        parsed.path,
        config,
        freq=parsed.freq,
        open_statuses=parsed.open_status,
    )
    _print_report(results)


if __name__ == "__main__":  # pragma: no cover - CLI behaviour
    main()
