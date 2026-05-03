#!/usr/bin/env python3
"""Reconcile ERP (Workday) and EPM (Adaptive) balances from Excel files."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


KEY_COLUMNS = ["company", "period", "account"]


REQUIRED_COLUMNS = {
    "workday": KEY_COLUMNS + ["amount"],
    "adaptive": KEY_COLUMNS + ["amount"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def _validate_columns(df: pd.DataFrame, source_name: str) -> None:
    required = set(REQUIRED_COLUMNS[source_name])
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"{source_name.title()} file is missing required columns: {', '.join(missing)}. "
            f"Expected columns include: {', '.join(REQUIRED_COLUMNS[source_name])}."
        )


def _aggregate(df: pd.DataFrame, amount_column_name: str) -> pd.DataFrame:
    grouped = (
        df.groupby(KEY_COLUMNS, dropna=False, as_index=False)["amount"]
        .sum(min_count=1)
        .rename(columns={"amount": amount_column_name})
    )
    return grouped


def reconcile(workday_path: Path, adaptive_path: Path) -> pd.DataFrame:
    workday_raw = _normalize_columns(pd.read_excel(workday_path))
    adaptive_raw = _normalize_columns(pd.read_excel(adaptive_path))

    _validate_columns(workday_raw, "workday")
    _validate_columns(adaptive_raw, "adaptive")

    workday_raw["amount"] = pd.to_numeric(workday_raw["amount"], errors="coerce")
    adaptive_raw["amount"] = pd.to_numeric(adaptive_raw["amount"], errors="coerce")

    workday = _aggregate(workday_raw, "workday_amount")
    adaptive = _aggregate(adaptive_raw, "adaptive_amount")

    merged = workday.merge(adaptive, how="outer", on=KEY_COLUMNS, indicator=True)

    merged["variance"] = merged["workday_amount"].fillna(0) - merged["adaptive_amount"].fillna(0)
    merged["missing_in_workday"] = merged["workday_amount"].isna()
    merged["missing_in_adaptive"] = merged["adaptive_amount"].isna()

    both_present = (~merged["missing_in_workday"]) & (~merged["missing_in_adaptive"])
    merged["possible_sign_reversal"] = (
        both_present
        & (merged["workday_amount"].abs() == merged["adaptive_amount"].abs())
        & (merged["workday_amount"].mul(merged["adaptive_amount"]) < 0)
    )

    merged["status"] = "Matched"
    merged.loc[merged["variance"] != 0, "status"] = "Variance"
    merged.loc[merged["missing_in_workday"], "status"] = "Missing in Workday"
    merged.loc[merged["missing_in_adaptive"], "status"] = "Missing in Adaptive"
    merged.loc[merged["possible_sign_reversal"], "status"] = "Possible Sign Reversal"

    merged = merged.sort_values(KEY_COLUMNS).reset_index(drop=True)

    return merged[
        KEY_COLUMNS
        + [
            "workday_amount",
            "adaptive_amount",
            "variance",
            "missing_in_workday",
            "missing_in_adaptive",
            "possible_sign_reversal",
            "status",
        ]
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Workday trial balance and Adaptive balance sheet using company, period, "
            "and account keys, then export reconciliation results to Excel."
        )
    )
    parser.add_argument("workday_file", type=Path, help="Path to Workday trial balance Excel file")
    parser.add_argument("adaptive_file", type=Path, help="Path to Adaptive balance sheet Excel file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("reconciliation_output.xlsx"),
        help="Output Excel file path (default: reconciliation_output.xlsx)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = reconcile(args.workday_file, args.adaptive_file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(args.output) as writer:
        result.to_excel(writer, index=False, sheet_name="reconciliation")

    print(f"Reconciliation complete. Rows: {len(result)}. Output: {args.output}")


if __name__ == "__main__":
    main()
