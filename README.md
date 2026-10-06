# Procurement Data Analyzer

A local Streamlit dashboard for purchase order spend. Load the procurement CSV files, choose a company and optionally a division, then review quarterly spend, top vendors, top spend categories, and division spend.

## Features

- **Load Data** is the first page. Upload the CSV files or load the included sample set, then click **View Dashboard** to open the dashboard.
- Company is required on the dashboard. Division is optional; **All divisions** is the default.
- When a company contains more than one currency, choose a currency before viewing totals. Amounts in different currencies are never added together.
- A dark interface pairs high-contrast text with colorful charts and metrics.
- The Trinetri logo in `logos/` is the default app brand; upload a replacement from the Load Data page.
- Charts summarize PO line amounts. A ranked list shows the three largest vendors; the category chart shows the three largest category totals.
- The included Trinetri policy PDF can be used with the included sample CSV data to try policy review and local AI chat.
- Use the local Llama 3.1 chat for questions grounded in policy, company, division, vendor, and PO data.
- Uploaded data stays in the active app session; this app does not persist it or send it to a third-party service.

## Run with Docker

Docker Desktop / Docker Engine with Compose works on Windows, macOS, and Linux.

```sh
docker compose up --build
```

On first startup, Compose downloads the Llama 3.1 model into a Docker-managed volume. The download can take a while; later starts reuse the model. The model and weights are not stored in this Git project. Open [http://localhost:8501](http://localhost:8501). Stop the app with `Ctrl+C`; `docker compose down` stops containers but keeps the model volume.

## Run locally

Python 3.10 or newer is recommended.

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run src/procurement_data_analyzer/app.py
```

## Input files

Upload CSV files with these exact filenames. Headers are matched without regard to capitalization, spaces, underscores, and punctuation for the fields used by the dashboard. `my_company.csv` and `po_data.csv` are required; lookup files are recommended. All files should be UTF-8 CSV. Dates in `po_date` can use `DD-Mon-YYYY` (such as `03-Jan-2024`) or ISO `YYYY-MM-DD` format.

### `my_company.csv` — required

One row per company. Company IDs must match `company_id` in the PO file.

| Column | Purpose |
| --- | --- |
| `Company_id` | Company key, e.g. `1` |
| `Company Name` | Dashboard company label |
| `Division` | Source field retained for reference; PO line divisions are resolved by `division_id` |

### `po_data.csv` — required

One row per purchase order line. Amounts are summed from `Total_line_amount`; include every line as a separate row. Division names are joined through `division_id` and `my_company_divisions.csv`. The recommended schema is:

| Column | Purpose |
| --- | --- |
| `po_id` | PO record identifier |
| `po_number` | Human-readable PO number |
| `po_date` | PO date |
| `company_id` | Joins to `my_company.csv.Company_id` |
| `division_id` | Joins to `my_company_divisions.csv.division_id` |
| `po_status` | PO status, e.g. Approved or Cancelled |
| `vendor_id` | Joins to `vendor.csv.vendor_id` |
| `vendor_address_id` | Vendor address reference |
| `po_line_number` | Line number within the PO |
| `spend_category` | Category used in the top categories chart |
| `quantity ` | Quantity (the source header has trailing whitespace) |
| `unit_amount` | Unit price |
| `Currency` | Currency code (e.g. USD, CAD) |
| `Total_line_amount` | **Required spend value** for this line |
| `Spend Description` | Description of the purchase |
| `Creation_date` | Optional date the PO line was created; not used in spend charts |

All PO rows, including cancelled rows, are retained in the normalized data and the detail table. Each current spend calculation filters out rows whose `po_status` is `Cancelled` or `Canceled` (case-insensitive). A future calculation can include them by opting into `include_cancelled=True` in its calculation input helper. Other statuses are included.

### `my_company_divisions.csv` — recommended

One row per division. Division IDs in the PO file must match this lookup.

| Column | Purpose |
| --- | --- |
| `division_id` | Division key |
| `Division` | Division name shown in filters and charts |

### `vendor.csv` — recommended

One row per vendor. The vendor ID and name are used to label the top vendors chart.

| Column | Purpose |
| --- | --- |
| `vendor_id` | Vendor key referenced by `po_data.csv` |
| `vendor_name` | Vendor display name |
| `Vendor_number` | Business/vendor number |
| `Parent_vendor_id` | Parent vendor reference |
| `Vendor_type` | Supplier, Bank, Legal, etc. |
| `start_date_active` | Start of active period |
| `end_date_active` | End of active period; may be blank |
| `Tax_id` | Sensitive tax identifier; not used by the dashboard |

### `vendor_address.csv` — optional reference file

Accepted by the uploader but not used in spend calculations.

| Column | Purpose |
| --- | --- |
| `Vendor_address_id` | Address key referenced by PO/bank rows |
| `vendor_id` | Vendor key |
| `vendor_name` | Vendor display name |
| `Address_line_1`, `Address_line_2`, `Address_line_3` | Street address |
| `City` | City |
| `State/Province` | State or province |
| `Zip` | Postal code |
| `Country` | Country |
| `Start_date_active` | Start of active period |
| `end_date_active` | End of active period; may be blank |

### `vendor_bank.csv` — optional reference file

Accepted by the uploader but not used by the dashboard. Do not publish real banking data in a public repository.

| Column | Purpose |
| --- | --- |
| `Vendor_address_id` | Vendor address key |
| `vendor_id` | Vendor key |
| `vendor_name` | Vendor display name |
| `Country` | Bank country |
| `Vendor_bank` | Bank name |
| `Routing Number` | Sensitive bank routing identifier |
| `Account Number` | Sensitive bank account identifier |

### Relationships

```text
my_company.Company_id ─────────────── po_data.company_id
my_company_divisions.division_id ─── po_data.division_id
vendor.vendor_id ─────────────────── po_data.vendor_id
vendor_address.Vendor_address_id ─── po_data.vendor_address_id
vendor_bank.Vendor_address_id ────── vendor_address.Vendor_address_id
```

For your own exports, keep IDs consistent across files and use numeric amounts without currency symbols in `Total_line_amount`. Keep each currency in its own rows with the correct currency code. The dashboard excludes rows with unparseable PO dates and treats invalid line amounts as zero with a warning.

## Policy review and local AI chat

1. Load the PO CSV files. Loading the included sample CSVs also selects the included sample policy; for other data, upload a selectable-text procurement-policy PDF on the Load Data page.
2. Click **Prepare Llama RAG & Evaluate All POs**. This builds a local retrieval context from policy text and joined PO records, extracts testable policy conditions, and evaluates each PO against all extracted conditions in batches. It is retrieval-augmented generation, not model fine-tuning; model weights are unchanged.
3. Review the extracted conditions, potential violations, supporting PO evidence, and any cases Llama marked for manual review. Use **Open AI Chat** to ask questions about this policy and PO data.

Cancelled POs and POs with unparseable dates remain available to policy review. Standard dashboard calculations apply their own cancelled-PO filter; policy evaluation considers every retained PO row and provides department-quarter aggregates (including cancelled rows) for quarterly thresholds. For cross-border rules, add a company home-country field to `my_company.csv` (such as `Country` or `Company Country`); if the field is missing, the model is instructed to mark the finding for manual review instead of guessing. The AI chat refuses out-of-context questions with: `This question is out of context of this Model. I can answer only procurement queries related to policy and uploaded data`.

The PDF reader extracts embedded text; scanned PDFs need OCR before upload. PO and policy context remains in the app session and is sent only to the Ollama service in the local Docker Compose network. The RAG index includes PO line details plus company, division, vendor, and limited vendor-location lookup records from the loaded CSVs. Vendor tax IDs, street addresses, postal codes, and all vendor-bank fields are excluded from model context. Retrieval uses local lexical matching; the app does not download or store a separate embedding model.

### Included sample policy

`sample_data/Trinetri Procurement Policy.pdf` is the reference policy for the included CSVs. It contains a USD limit for procurement outside a company's home country and a quarterly USD spending limit per department. On **Load Data**, choose **Use included sample data** to load the CSVs and select this policy, or use **Use included sample policy** separately.

## Automated tests

Run the tests from the repository root with:

```sh
python -m unittest discover -s tests -v
```

The tests load the checked-in CSV sample and verify quarterly spend, top vendor, top categories, division spend, company/currency and division filtering, the default cancelled-PO calculation rule, and safe company/vendor/PO coverage in the RAG data context.

## App logo

The app uses `logos/trinetri-logo.jpg` as its default logo. The shared formatting and header functions in `src/procurement_data_analyzer/branding.py` fit the full logo inside a padded display canvas without clipping or stretching it; the original file is preserved. On the **Load Data** page, use **Branding → Upload a logo** to add a PNG or JPG; the app saves it in `logos/` and uses the same formatting function. The Docker Compose setup mounts this folder from the project directory, so uploaded logo files persist across container restarts. You can also place a PNG or JPG named `custom-logo.png` / `custom-logo.jpg` in `logos/` manually. The most recently updated custom logo takes precedence over the default.

## Included sample data

`sample_data/` contains the six source CSV filenames and their headers so contributors can use them as a starting point. The sample values are derived from the supplied example files. Sensitive values were removed from the public-ready copies: vendor tax IDs, street/ZIP details, bank names, routing numbers, and account numbers are blank. Replace these with your own controlled, non-sensitive sample values when adapting the files.

## Project structure

```text
.
├── Dockerfile
├── compose.yaml
├── LICENSE
├── README.md
├── requirements.txt
├── logos/
│   ├── trinetri-logo.jpg              # Original default logo
│   └── trinetri-logo-formatted-v3.png # Padded display version generated by branding.py
├── sample_data/                         # Reference CSVs and policy PDF
│   └── Trinetri Procurement Policy.pdf # Sample procurement policy
├── src/
│   └── procurement_data_analyzer/
│       ├── branding.py                 # Reusable logo formatting and rendering
│       ├── app.py                        # Streamlit UI and dashboard
│       ├── dashboard_data.py             # Testable dashboard filters and groupings
│       ├── data_loader.py                # CSV recognition and normalization
│       └── policy_assistant.py           # PDF RAG, PO checks, and local chat
└── tests/
    └── test_dashboard_data.py            # Sample-data dashboard and RAG tests
```

## License

MIT. See [LICENSE](LICENSE).
