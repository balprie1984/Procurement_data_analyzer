"""Pure dashboard filters and spend groupings, shared by the UI and tests."""
from __future__ import annotations

import pandas as pd


def filter_dashboard_rows(
    rows: pd.DataFrame,
    *,
    company: str,
    division: str | None = None,
    currency: str | None = None,
    include_cancelled: bool = False,
) -> pd.DataFrame:
    """Filter rows to dashboard selections, excluding cancelled POs by default."""
    filtered = rows.loc[rows["Company"].astype(str).eq(company)].copy()
    if division and division != "All divisions":
        filtered = filtered.loc[filtered["Division"].astype(str).eq(division)]
    if currency:
        filtered = filtered.loc[filtered["Currency"].astype(str).eq(currency)]
    if not include_cancelled and "PO Status" in filtered:
        cancelled = filtered["PO Status"].astype(str).str.strip().str.casefold().isin({"cancelled", "canceled"})
        filtered = filtered.loc[~cancelled]
    return filtered


def dashboard_groupings(rows: pd.DataFrame, *, top_n: int = 3) -> dict[str, pd.DataFrame]:
    """Return the four dashboard groupings for already filtered rows."""
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    valid_dates = rows.loc[rows["PO Date"].notna()].copy()
    quarterly = (
        valid_dates.assign(Quarter=valid_dates["PO Date"].dt.to_period("Q").astype(str))
        .groupby("Quarter", as_index=False)["Spend"].sum()
        .sort_values("Quarter")
        .reset_index(drop=True)
    )

    def top_group(column: str) -> pd.DataFrame:
        grouped = rows.groupby(column, as_index=False, dropna=False)["Spend"].sum()
        return grouped.sort_values("Spend", ascending=False, kind="stable").head(top_n).reset_index(drop=True)

    top_categories = top_group("Spend Category").sort_values("Spend", ascending=True, kind="stable").reset_index(drop=True)

    divisions = rows.groupby("Division", as_index=False, dropna=False)["Spend"].sum()
    divisions["Division"] = divisions["Division"].fillna("").replace("", "Unspecified")
    divisions = divisions.reset_index(drop=True)
    return {
        "quarterly": quarterly,
        "top_vendors": top_group("Vendor"),
        "top_categories": top_categories,
        "divisions": divisions,
    }
