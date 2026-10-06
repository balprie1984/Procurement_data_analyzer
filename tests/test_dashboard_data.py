"""Regression coverage for dashboard groupings using the checked-in sample data."""
from pathlib import Path
import sys
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from procurement_data_analyzer.dashboard_data import dashboard_groupings, filter_dashboard_rows  # noqa: E402
from procurement_data_analyzer.data_loader import load_sample, normalize_data  # noqa: E402
from procurement_data_analyzer.policy_assistant import build_rag_context, extract_policy_pages  # noqa: E402


class DashboardGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = load_sample(ROOT / "sample_data")
        cls.data, _ = normalize_data(cls.tables)

    def test_company_currency_quarter_vendor_category_and_division_groupings(self):
        rows = filter_dashboard_rows(self.data, company="Bhairavi Corp", currency="USD")
        groups = dashboard_groupings(rows)

        self.assertEqual(dict(zip(groups["quarterly"]["Quarter"], groups["quarterly"]["Spend"])), {
            "2024Q1": 70500, "2024Q2": 142000, "2024Q3": 45000, "2024Q4": 48000,
        })
        self.assertEqual(groups["top_vendors"].iloc[0].to_dict(), {"Vendor": "Fidelity Inc.", "Spend": 67000})
        self.assertEqual(
            dict(zip(groups["top_categories"]["Spend Category"], groups["top_categories"]["Spend"])),
            {"Legal services": 55000, "Software/License Purchase": 70000, "Marketing Campaign": 110000},
        )
        self.assertEqual(
            dict(zip(groups["divisions"]["Division"], groups["divisions"]["Spend"])),
            {"Finance": 70500, "IT support and services": 45000, "Legal": 55000,
             "Marketing": 110000, "Software Development": 25000},
        )
        self.assertEqual(rows["Spend"].sum(), 305500)

    def test_division_filter_and_default_cancelled_po_exclusion(self):
        rows = filter_dashboard_rows(
            self.data, company="Bhairavi Corp", division="IT support and services", currency="USD"
        )
        self.assertEqual(rows["Spend"].sum(), 45000)
        self.assertFalse(rows["PO Status"].str.casefold().isin({"cancelled", "canceled"}).any())

        cancelled = filter_dashboard_rows(
            self.data, company="Bhairavi Corp", division="IT support and services", currency="USD",
            include_cancelled=True,
        )
        self.assertEqual(cancelled["Spend"].sum(), 295000)

    def test_sample_policy_and_joined_lookup_files_are_available(self):
        policy = ROOT / "sample_data" / "Trinetri Procurement Policy.pdf"
        self.assertTrue(policy.is_file())
        pages = extract_policy_pages(policy.read_bytes())
        policy_text = re.sub(r"\s+", " ", " ".join(page["text"] for page in pages))
        self.assertIn("25,000 USD", policy_text)
        self.assertIn("50,000 USD", policy_text)
        self.assertIn("my_company.csv", self.tables)
        self.assertIn("my_company_divisions.csv", self.tables)
        self.assertIn("vendor.csv", self.tables)

    def test_rag_context_includes_company_division_vendor_and_po_records(self):
        context = build_rag_context(
            extract_policy_pages((ROOT / "sample_data" / "Trinetri Procurement Policy.pdf").read_bytes()),
            self.data,
            self.tables,
        )
        policy_context = re.sub(r"\s+", " ", "\n".join(chunk["text"] for chunk in context["policy_chunks"]))
        self.assertIn("25,000 USD", policy_context)
        kinds = {chunk["kind"] for chunk in context["data_chunks"]}
        self.assertTrue({"purchase_order", "company", "division", "vendor", "vendor_location", "company_division"}.issubset(kinds))
        joined_context = "\n".join(chunk["text"] for chunk in context["data_chunks"])
        self.assertIn("Amazon Inc.", joined_context)
        self.assertIn("Software Development", joined_context)
        self.assertIn("PO101", joined_context)
        cancelled_po = next(record for record in context["po_records"] if record["po_number"] == "PO108")
        self.assertEqual(cancelled_po["status"], "Cancelled")
        self.assertIn({
            "division": "IT support and services", "quarter": "2024Q3", "currency": "USD",
            "department_quarter_spend": 250000.0,
        }, cancelled_po["department_quarter_totals"])
        self.assertEqual(cancelled_po["company_countries"], [])
        self.assertNotIn("Tax_id", joined_context)
        self.assertNotIn("Routing Number", joined_context)
        self.assertNotIn("Account Number", joined_context)


if __name__ == "__main__":
    unittest.main()
