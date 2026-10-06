# Automated tests

From the project root, run:

```sh
python -m unittest discover -s tests -v
```

`test_dashboard_data.py` loads the checked-in sample CSV files and policy PDF. It checks dashboard quarter, vendor, category, and division totals; company, currency, and division filtering; cancelled-PO handling; policy text extraction; and inclusion of company, division, vendor, location, and PO records in the RAG context. It also checks that tax and banking columns are not placed in that context.
