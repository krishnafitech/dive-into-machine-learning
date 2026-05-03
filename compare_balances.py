#!/usr/bin/env python3
"""Compare Workday trial balance and Adaptive balance sheet exports.

The tool compares two datasets by company, period, and account and highlights:
- Missing accounts by source
- Duplicate rows in each source
- Sign differences for matched records
- Variance by account (Workday - Adaptive)

Results are exported to a multi-sheet Excel workbook.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


KEY_COLUMNS = ["company", "period", "account"]
AMOUNT_COLUMN = "amount"


def normalize_columns(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Normalize required columns and numeric amount."""
    renamed = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=renamed)

    required = set(KEY_COLUMNS + [AMOUNT_COLUMN])
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {', '.join(missing)}")

    for col in KEY_COLUMNS:
        df[col] = df[col].astype(str).str.strip()

    df[AMOUNT_COLUMN] = pd.to_numeric(df[AMOUNT_COLUMN], errors="coerce")
    if df[AMOUNT_COLUMN].isna().any():
        bad_rows = df[df[AMOUNT_COLUMN].isna()].index.tolist()[:10]
        raise ValueError(
            f"{name} has non-numeric amount values. Example row indexes: {bad_rows}"
        )

    return df[KEY_COLUMNS + [AMOUNT_COLUMN]].copy()


def find_duplicates(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    dupes = df[df.duplicated(subset=KEY_COLUMNS, keep=False)].copy()
    if dupes.empty:
        return pd.DataFrame(columns=["source", *KEY_COLUMNS, AMOUNT_COLUMN, "duplicate_count"])

    counts = (
        dupes.groupby(KEY_COLUMNS, as_index=False)
        .size()
        .rename(columns={"size": "duplicate_count"})
    )
    dupes = dupes.merge(counts, on=KEY_COLUMNS, how="left")
    dupes.insert(0, "source", source_name)
    return dupes.sort_values(KEY_COLUMNS + [AMOUNT_COLUMN]).reset_index(drop=True)


def aggregate_balances(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(KEY_COLUMNS, as_index=False)[AMOUNT_COLUMN]
        .sum()
        .sort_values(KEY_COLUMNS)
        .reset_index(drop=True)
    )


def sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def compare_datasets(workday: pd.DataFrame, adaptive: pd.DataFrame) -> dict[str, pd.DataFrame]:
    wd_agg = aggregate_balances(workday)
    ad_agg = aggregate_balances(adaptive)

    merged = wd_agg.merge(
        ad_agg,
        on=KEY_COLUMNS,
        how="outer",
        suffixes=("_workday", "_adaptive"),
        indicator=True,
    )

    missing_in_workday = merged[merged["_merge"] == "right_only"][
        KEY_COLUMNS + ["amount_adaptive"]
    ].rename(columns={"amount_adaptive": "amount"})

    missing_in_adaptive = merged[merged["_merge"] == "left_only"][
        KEY_COLUMNS + ["amount_workday"]
    ].rename(columns={"amount_workday": "amount"})

    matches = merged[merged["_merge"] == "both"].copy()
    matches["variance"] = matches["amount_workday"] - matches["amount_adaptive"]
    matches["workday_sign"] = matches["amount_workday"].map(sign)
    matches["adaptive_sign"] = matches["amount_adaptive"].map(sign)
    sign_differences = matches[
        (matches["workday_sign"] != matches["adaptive_sign"])
        & (matches["amount_workday"] != 0)
        & (matches["amount_adaptive"] != 0)
    ][KEY_COLUMNS + ["amount_workday", "amount_adaptive", "variance", "workday_sign", "adaptive_sign"]]

    variance_by_account = (
        matches.groupby("account", as_index=False)[["amount_workday", "amount_adaptive", "variance"]]
        .sum()
        .sort_values("variance", key=lambda s: s.abs(), ascending=False)
        .reset_index(drop=True)
    )

    full_comparison = matches[
        KEY_COLUMNS
        + [
            "amount_workday",
            "amount_adaptive",
            "variance",
            "workday_sign",
            "adaptive_sign",
        ]
    ].sort_values(KEY_COLUMNS)

    return {
        "workday_aggregated": wd_agg,
        "adaptive_aggregated": ad_agg,
        "missing_in_workday": missing_in_workday,
        "missing_in_adaptive": missing_in_adaptive,
        "duplicate_rows": pd.concat(
            [find_duplicates(workday, "workday"), find_duplicates(adaptive, "adaptive")],
            ignore_index=True,
        ),
        "sign_differences": sign_differences.sort_values(KEY_COLUMNS).reset_index(drop=True),
        "variance_by_account": variance_by_account,
        "full_comparison": full_comparison.reset_index(drop=True),
    }


def read_input(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported file type for {path}. Use CSV or Excel.")


def write_excel(results: dict[str, pd.DataFrame], output_file: Path) -> None:
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sheet_name, frame in results.items():
            frame.to_excel(writer, index=False, sheet_name=sheet_name[:31])


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Workday trial balance and Adaptive balance sheet files."
    )
    parser.add_argument("--workday", required=True, help="Path to Workday CSV/XLSX file")
    parser.add_argument("--adaptive", required=True, help="Path to Adaptive CSV/XLSX file")
    parser.add_argument(
        "--output",
        default="balance_comparison.xlsx",
        help="Output Excel file path (default: balance_comparison.xlsx)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    workday_raw = read_input(Path(args.workday))
    adaptive_raw = read_input(Path(args.adaptive))

    workday = normalize_columns(workday_raw, "Workday")
    adaptive = normalize_columns(adaptive_raw, "Adaptive")

    results = compare_datasets(workday, adaptive)
    write_excel(results, Path(args.output))
    print(f"Comparison complete. Results written to {args.output}")


if __name__ == "__main__":
    main()
