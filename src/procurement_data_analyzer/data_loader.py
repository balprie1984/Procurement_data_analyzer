"""Loading and normalizing Procurement Data Analyzer's CSV input files."""
from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
import re

import pandas as pd

REQUIRED_FILES = ("my_company.csv", "po_data.csv")
OPTIONAL_FILES = ("my_company_divisions.csv", "vendor.csv", "vendor_address.csv", "vendor_bank.csv")
ALL_FILES = REQUIRED_FILES + OPTIONAL_FILES


def _read_csv(source) -> pd.DataFrame:
    if isinstance(source, (bytes, bytearray)):
        return pd.read_csv(BytesIO(source), dtype=str, keep_default_na=False)
    if hasattr(source, "getvalue"):
        return pd.read_csv(BytesIO(source.getvalue()), dtype=str, keep_default_na=False)
    return pd.read_csv(source, dtype=str, keep_default_na=False)


def read_uploads(files: list) -> dict[str, pd.DataFrame]:
    """Map uploaded CSVs to recognized source roles using their filenames."""
    found: dict[str, pd.DataFrame] = {}
    for uploaded in files:
        name = Path(uploaded.name).name.lower()
        if name in ALL_FILES:
            found[name] = _read_csv(uploaded)
    return found


def load_sample(sample_dir: Path) -> dict[str, pd.DataFrame]:
    return {name: _read_csv(sample_dir / name) for name in ALL_FILES if (sample_dir / name).exists()}


def _col(frame: pd.DataFrame, *aliases: str) -> str | None:
    normalized = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in frame.columns}
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]", "", alias.lower())
        if key in normalized:
            return normalized[key]
    return None


def _clean_id(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def normalize_data(
    tables: Mapping[str, pd.DataFrame], *, include_invalid_dates: bool = False
) -> tuple[pd.DataFrame, list[str]]:
    """Join source tables into one row per PO line and return actionable warnings."""
    warnings: list[str] = []
    if "my_company.csv" not in tables or "po_data.csv" not in tables:
        raise ValueError("Both my_company.csv and po_data.csv are required.")

    companies = tables["my_company.csv"].copy()
    po = tables["po_data.csv"].copy()
    c_id, c_name = _col(companies, "Company_id", "company_id"), _col(companies, "Company Name", "company_name")
    if not c_id or not c_name:
        raise ValueError("my_company.csv needs Company_id and Company Name columns.")
    p_company = _col(po, "company_id")
    p_div = _col(po, "division_id")
    p_status = _col(po, "po_status", "PO Status", "status")
    p_amount = _col(po, "Total_line_amount", "total_line_amount", "line_amount", "amount")
    p_date = _col(po, "po_date", "PO Date", "order_date")
    p_vendor = _col(po, "vendor_id")
    p_vendor_address = _col(po, "vendor_address_id")
    p_category = _col(po, "spend_category", "Spend Category", "category")
    p_currency = _col(po, "Currency", "currency")
    if not all((p_company, p_amount, p_date)):
        raise ValueError("po_data.csv needs company_id, po_date, and Total_line_amount columns.")

    frame = po.copy()
    frame["PO Status"] = frame[p_status].astype(str).str.strip() if p_status else "Unspecified"
    frame["_company_key"] = _clean_id(frame[p_company])
    companies["_company_key"] = _clean_id(companies[c_id])
    frame = frame.merge(companies[["_company_key", c_name]], on="_company_key", how="left")
    frame = frame.rename(columns={c_name: "Company"})
    frame["Company"] = frame["Company"].fillna("").replace("", "Unknown company")

    divisions = tables.get("my_company_divisions.csv")
    if divisions is not None and p_div:
        d_id, d_name = _col(divisions, "division_id"), _col(divisions, "Division", "division_name")
        if d_id and d_name:
            divisions = divisions.copy()
            divisions["_division_key"] = _clean_id(divisions[d_id])
            frame["_division_key"] = _clean_id(frame[p_div])
            frame = frame.merge(divisions[["_division_key", d_name]], on="_division_key", how="left")
            frame["Division"] = frame[d_name].fillna("")
        else:
            frame["Division"] = ""
    else:
        division_text = _col(po, "Division", "division_name")
        frame["Division"] = frame[division_text].fillna("") if division_text else ""

    vendors = tables.get("vendor.csv")
    vendor_name_col = None
    vendor_type_col = None
    if vendors is not None and p_vendor:
        v_id, vendor_name_col = _col(vendors, "vendor_id"), _col(vendors, "vendor_name", "Vendor Name")
        if v_id and vendor_name_col:
            vendors = vendors.copy()
            vendors["_vendor_key"] = _clean_id(vendors[v_id])
            frame["_vendor_key"] = _clean_id(frame[p_vendor])
            vendor_type_col = _col(vendors, "Vendor_type", "vendor_type")
            vendor_columns = ["_vendor_key", vendor_name_col]
            if vendor_type_col:
                vendor_columns.append(vendor_type_col)
            frame = frame.merge(vendors[vendor_columns], on="_vendor_key", how="left")
            frame["Vendor"] = frame[vendor_name_col].fillna("")
    if "Vendor" not in frame:
        frame["Vendor"] = ""
    if p_vendor:
        frame["Vendor"] = frame["Vendor"].where(frame["Vendor"].astype(str).str.strip().ne(""), "Vendor " + _clean_id(frame[p_vendor]))
    else:
        frame["Vendor"] = "Vendor not specified"
    frame["Vendor Type"] = frame[vendor_type_col].fillna("") if vendor_type_col else ""

    addresses = tables.get("vendor_address.csv")
    if addresses is not None and p_vendor_address:
        address_id = _col(addresses, "Vendor_address_id", "vendor_address_id")
        country_col = _col(addresses, "Country", "vendor_country")
        if address_id and country_col:
            addresses = addresses.copy()
            addresses["_address_key"] = _clean_id(addresses[address_id])
            frame["_address_key"] = _clean_id(frame[p_vendor_address])
            frame = frame.merge(addresses[["_address_key", country_col]], on="_address_key", how="left")
            frame["Vendor Country"] = frame[country_col].fillna("")
        else:
            frame["Vendor Country"] = ""
    else:
        frame["Vendor Country"] = ""

    frame["Spend Category"] = frame[p_category].astype(str).str.strip() if p_category else "Uncategorized"
    frame["Spend Category"] = frame["Spend Category"].replace("", "Uncategorized")
    frame["Currency"] = frame[p_currency].astype(str).str.strip().str.upper() if p_currency else ""
    frame["Currency"] = frame["Currency"].replace("", "Unspecified")
    frame["PO Date"] = pd.to_datetime(frame[p_date], errors="coerce", dayfirst=True)
    frame["Spend"] = pd.to_numeric(frame[p_amount].astype(str).str.replace(r"[^0-9.-]", "", regex=True), errors="coerce")
    invalid = frame["PO Date"].isna().sum()
    if invalid:
        warnings.append(f"{invalid} row(s) have an invalid PO date and were excluded from charts.")
    invalid_amount = frame["Spend"].isna().sum()
    if invalid_amount:
        warnings.append(f"{invalid_amount} row(s) have an invalid Total_line_amount and were treated as zero.")
    frame["Spend"] = frame["Spend"].fillna(0)
    if not include_invalid_dates:
        frame = frame[frame["PO Date"].notna()].copy()
    return frame, warnings
