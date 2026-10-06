from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from procurement_data_analyzer.branding import display_branding  # noqa: E402
from procurement_data_analyzer.data_loader import load_sample, normalize_data, read_uploads  # noqa: E402
from procurement_data_analyzer.dashboard_data import dashboard_groupings, filter_dashboard_rows  # noqa: E402
from procurement_data_analyzer.policy_assistant import (  # noqa: E402
    OUT_OF_CONTEXT_REPLY,
    answer_question,
    build_rag_context,
    evaluate_all_pos,
    extract_policy_conditions,
    extract_policy_pages,
)

st.set_page_config(page_title="Procurement Data Analyzer", page_icon="📊", layout="wide")

st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp {
  background:
    radial-gradient(ellipse at 82% 0%, rgba(88, 28, 135, .18), transparent 34%),
    radial-gradient(ellipse at 6% 18%, rgba(8, 145, 178, .13), transparent 30%),
    #080b12;
}
.block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] { background: #0c111b; border-right: 1px solid #1d2735; }
.brand-title { color: #f4f7ff; font-size: 1.65rem; line-height: 1.2; font-weight: 750; letter-spacing: -.035em; text-align: left; }
.brand-caption { color: #91a1b8; font-size: .93rem; margin-top: 5px; text-align: left; }
.brand-copy { padding: 48px 0; }
.brand-divider { border-bottom: 1px solid #202b3b; margin: 15px 0 22px; }
h1, h2, h3 { letter-spacing: -.025em; }
h2 { margin-bottom: .35rem; }
[data-testid="stMetric"] { background: linear-gradient(145deg, #141d2a, #101620); border: 1px solid #253248; border-radius: 16px; padding: 18px 20px; box-shadow: 0 10px 30px rgba(0,0,0,.18); }
[data-testid="stMetricLabel"] { color: #9eacc2; }
[data-testid="stMetricValue"] { color: #f4f7ff; }
[data-testid="stVerticalBlockBorderWrapper"] { background: rgba(16, 23, 34, .66); border-color: #253248; border-radius: 16px; }
.stButton > button { border-radius: 10px; border: 1px solid #2b4057; font-weight: 650; min-height: 2.7rem; }
.stButton > button[kind="primary"] { background: linear-gradient(100deg, #0891b2, #4f46e5); border: 0; color: white; }
.stButton > button:hover { border-color: #22d3ee; color: #fff; }
[data-testid="stFileUploader"] { border: 1px dashed #33445b; border-radius: 14px; background: rgba(16, 23, 34, .45); padding: 8px; }
[data-testid="stSelectbox"] > div > div { background: #111a27; border-color: #2a374b; border-radius: 10px; }
hr { border-color: #202b3b; }
small, .stCaption { color: #8fa0b8 !important; }
</style>
""", unsafe_allow_html=True)


def _logo_path() -> Path:
    logo_dir = ROOT / "logos"
    uploaded = sorted(
        [*logo_dir.glob("uploaded-logo.*"), *logo_dir.glob("custom-logo.*")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return uploaded[0] if uploaded else logo_dir / "trinetri-logo.jpg"


def _show_brand() -> None:
    logo = _logo_path()
    display_branding(
        logo,
        title="Procurement Data Analyzer",
        subtitle="Procurement spend, made clear.",
        logo_width=220,
    )


_show_brand()

if "tables" not in st.session_state:
    st.session_state.tables = None
if "load_error" not in st.session_state:
    st.session_state.load_error = None
if "page" not in st.session_state:
    st.session_state.page = "Load Data"
if "policy_pdf_bytes" not in st.session_state:
    st.session_state.policy_pdf_bytes = None
if "policy_filename" not in st.session_state:
    st.session_state.policy_filename = None
if "rag_context" not in st.session_state:
    st.session_state.rag_context = None
if "policy_results" not in st.session_state:
    st.session_state.policy_results = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def _open_dashboard() -> None:
    st.session_state.page = "Dashboard"


def _open_load_data() -> None:
    st.session_state.page = "Load Data"


def _open_policy_review() -> None:
    st.session_state.page = "Policy Review"


def _open_ai_chat() -> None:
    st.session_state.page = "AI Chat"


with st.sidebar:
    st.header("Procurement insights")
    st.divider()
    st.caption("Load your purchase order files, then open the dashboard to explore spend.")

page = st.session_state.page
if page == "Load Data":
    st.header("Load data")
    st.write("Upload the procurement CSV files. The company and PO files are required; the other files enrich division and vendor labels.")
    uploads = st.file_uploader("Select CSV files", type=["csv"], accept_multiple_files=True)
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Load uploaded files", type="primary", disabled=not uploads):
            try:
                tables = read_uploads(uploads or [])
                missing = [n for n in ("my_company.csv", "po_data.csv") if n not in tables]
                if missing:
                    raise ValueError("Missing required file(s): " + ", ".join(missing))
                normalize_data(tables)
                st.session_state.tables = tables
                st.session_state.load_error = None
                st.session_state.rag_context = None
                st.session_state.policy_results = None
                st.session_state.chat_history = []
                st.success("Data loaded. Your dashboard is ready.")
            except Exception as exc:
                st.session_state.load_error = str(exc)
    with col2:
        if st.button("Use included sample data"):
            try:
                st.session_state.tables = load_sample(ROOT / "sample_data")
                normalize_data(st.session_state.tables)
                st.session_state.load_error = None
                st.session_state.rag_context = None
                st.session_state.policy_results = None
                st.session_state.chat_history = []
                sample_policy = ROOT / "sample_data" / "Trinetri Procurement Policy.pdf"
                if sample_policy.exists():
                    st.session_state.policy_pdf_bytes = sample_policy.read_bytes()
                    st.session_state.policy_filename = sample_policy.name
                st.success("Sample data loaded. Your dashboard is ready.")
            except Exception as exc:
                st.session_state.load_error = str(exc)
    if st.session_state.load_error:
        st.error(st.session_state.load_error)
    if st.session_state.tables:
        st.success(f"{len(st.session_state.tables)} file(s) currently loaded and ready.")
        st.button("View Dashboard →", type="primary", on_click=_open_dashboard, use_container_width=True)
    st.subheader("Expected files")
    st.markdown("""
    - **my_company.csv** — company IDs and names
    - **po_data.csv** — PO line item dates, company/division/vendor IDs, categories, and line amounts
    - **my_company_divisions.csv** — division IDs and names (recommended)
    - **vendor.csv** — vendor IDs and names (recommended)
    - **vendor_address.csv** and **vendor_bank.csv** — accepted for reference/compatibility; they are not needed for spend charts
    """)
    st.divider()
    st.subheader("Procurement policy review")
    policy_upload = st.file_uploader("Upload a procurement policy PDF", type=["pdf"], key="policy_pdf")
    if policy_upload is not None:
        policy_bytes = policy_upload.getvalue()
        if policy_bytes != st.session_state.policy_pdf_bytes:
            st.session_state.policy_pdf_bytes = policy_bytes
            st.session_state.policy_filename = policy_upload.name
            st.session_state.rag_context = None
            st.session_state.policy_results = None
            st.session_state.chat_history = []
        st.caption(f"Policy ready: {policy_upload.name}")
    elif st.session_state.policy_pdf_bytes:
        st.caption(f"Policy ready: {st.session_state.policy_filename or 'selected policy'}")
    if not st.session_state.policy_pdf_bytes:
        sample_policy = ROOT / "sample_data" / "Trinetri Procurement Policy.pdf"
        if sample_policy.exists() and st.button("Use included sample policy"):
            st.session_state.policy_pdf_bytes = sample_policy.read_bytes()
            st.session_state.policy_filename = sample_policy.name
            st.session_state.rag_context = None
            st.session_state.policy_results = None
            st.rerun()
    st.caption("Builds a local retrieval context with Llama 3.1. This does not fine-tune or modify model weights.")
    can_review = bool(st.session_state.tables and st.session_state.policy_pdf_bytes)
    if st.button("Prepare Llama RAG & Evaluate All POs", type="primary", disabled=not can_review):
        try:
            with st.spinner("Reading the policy PDF and preparing local RAG context with Llama 3.1…"):
                policy_pages = extract_policy_pages(st.session_state.policy_pdf_bytes)
                normalized_pos, _ = normalize_data(st.session_state.tables, include_invalid_dates=True)
                rag_context = build_rag_context(policy_pages, normalized_pos, st.session_state.tables)
                conditions = extract_policy_conditions(rag_context)
            st.info(f"Found {len(conditions)} policy conditions. Evaluating {len(rag_context['po_records'])} purchase orders…")
            progress = st.progress(0.0, text="Evaluating purchase orders")
            results = evaluate_all_pos(rag_context, progress=progress.progress)
            st.session_state.rag_context = rag_context
            st.session_state.policy_results = results
            st.session_state.page = "Policy Review"
            st.rerun()
        except Exception as exc:
            st.error(f"Policy review could not be completed: {exc}")
    if st.session_state.policy_results is not None:
        review_col, chat_col = st.columns(2)
        with review_col:
            st.button("View Policy Findings", on_click=_open_policy_review, use_container_width=True)
        with chat_col:
            st.button("Open AI Chat", on_click=_open_ai_chat, use_container_width=True)
    st.divider()
    st.subheader("Branding")
    logo_upload = st.file_uploader("Upload a logo (PNG or JPG)", type=["png", "jpg", "jpeg"], key="logo_upload")
    if logo_upload is not None:
        logo_dir = ROOT / "logos"
        logo_dir.mkdir(parents=True, exist_ok=True)
        extension = Path(logo_upload.name).suffix.lower()
        logo_path = logo_dir / f"uploaded-logo{extension}"
        logo_path.write_bytes(logo_upload.getvalue())
        st.success(f"Logo saved to logos/{logo_path.name}. It is now the app logo.")
elif page == "Dashboard":
    nav = st.columns(3 if st.session_state.policy_results is not None else 1)
    with nav[0]:
        st.button("← Back to Load Data", on_click=_open_load_data, use_container_width=True)
    if st.session_state.policy_results is not None:
        with nav[1]:
            st.button("Policy Findings", on_click=_open_policy_review, use_container_width=True)
        with nav[2]:
            st.button("Open AI Chat", on_click=_open_ai_chat, use_container_width=True)
    st.header("Procurement dashboard")
    if not st.session_state.tables:
        st.info("Start by loading files on the Load Data page, or use the included sample data.")
        st.stop()
    try:
        data, warnings = normalize_data(st.session_state.tables)
    except Exception as exc:
        st.error(f"Could not prepare dashboard data: {exc}")
        st.stop()
    for warning in warnings:
        st.warning(warning)

    companies = sorted(data["Company"].dropna().unique().tolist())
    if not companies:
        st.warning("No companies are available in the loaded data.")
        st.stop()
    filters = st.columns([2, 2, 2])
    with filters[0]:
        company = st.selectbox("Company *", companies)
    company_data = data[data["Company"] == company]
    with filters[1]:
        divisions = sorted(d for d in company_data["Division"].dropna().unique().tolist() if str(d).strip())
        division = st.selectbox("Division", ["All divisions"] + divisions)
    division_data = company_data if division == "All divisions" else company_data[company_data["Division"] == division]
    with filters[2]:
        currencies = sorted(division_data["Currency"].dropna().unique().tolist())
        currency = st.selectbox("Currency", currencies) if len(currencies) > 1 else currencies[0]

    filtered = division_data[division_data["Currency"] == currency].copy()
    if filtered.empty:
        st.info("No purchase order rows match these filters.")
        st.stop()

    calculation_rows = filter_dashboard_rows(
        data, company=company, division=division, currency=currency
    )
    groupings = dashboard_groupings(calculation_rows)
    currency_label = "" if currency == "Unspecified" else f" ({currency})"
    total_spend = calculation_rows["Spend"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Total PO spend" + currency_label, f"{total_spend:,.2f}")
    k2.metric("PO line items", f"{len(calculation_rows):,}")
    k3.metric("Vendors", f"{calculation_rows['Vendor'].nunique():,}")

    left, right = st.columns(2)
    quarterly = groupings["quarterly"]
    with left:
        st.subheader("Quarterly PO spend")
        fig = px.bar(quarterly, x="Quarter", y="Spend", labels={"Spend": f"Spend ({currency})" if currency != "Unspecified" else "Spend"},
                     color_discrete_sequence=["#3569a8"], title=None)
        fig.update_traces(marker_color="#22d3ee", marker_line_color="#67e8f9", marker_line_width=1)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#dbe5f5",
                          xaxis_title="Quarter", yaxis_title=f"Spend ({currency})" if currency != "Unspecified" else "Spend",
                          xaxis=dict(showgrid=False, zeroline=False), yaxis=dict(gridcolor="#273244", zeroline=False),
                          margin=dict(t=20, b=10), hoverlabel=dict(bgcolor="#182334", font_color="#f4f7ff"))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Top 3 vendors")
        top_vendors = groupings["top_vendors"]
        for rank, row in enumerate(top_vendors.itertuples(index=False), start=1):
            amount_label = f"{row.Spend:,.2f} {currency}" if currency != "Unspecified" else f"{row.Spend:,.2f}"
            st.markdown(
                f'<div style="background:linear-gradient(110deg,#172235,#111722);border:1px solid #2a374b;'
                f'border-radius:12px;padding:14px 16px;margin:10px 0;">'
                f'<span style="color:#22d3ee;font-weight:700;margin-right:12px">{rank:02}</span>'
                f'<strong>{row.Vendor}</strong><span style="float:right;color:#c4b5fd">{amount_label}</span></div>',
                unsafe_allow_html=True,
            )

    left, right = st.columns(2)
    with left:
        st.subheader("Top 3 spend categories")
        top_categories = groupings["top_categories"]
        fig = px.bar(top_categories, x="Spend", y="Spend Category", orientation="h", text_auto=".2s",
                     labels={"Spend": f"Spend ({currency})" if currency != "Unspecified" else "Spend"}, color_discrete_sequence=["#e39b3b"])
        fig.update_traces(marker_color=["#f472b6", "#fbbf24", "#a78bfa"][:len(top_categories)], marker_line_color="#f8fafc", marker_line_width=.6)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#dbe5f5",
                          yaxis_title="", xaxis_title=f"Spend ({currency})" if currency != "Unspecified" else "Spend",
                          xaxis=dict(gridcolor="#273244", zeroline=False), yaxis=dict(showgrid=False, zeroline=False),
                          margin=dict(t=20, b=10), hoverlabel=dict(bgcolor="#182334", font_color="#f4f7ff"))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Spend by division")
        by_division = groupings["divisions"]
        fig = px.pie(by_division, names="Division", values="Spend", hole=0.25, color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(marker_line_color="#111827", marker_line_width=2, textfont_color="#f8fafc")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#dbe5f5", margin=dict(t=20, b=10),
                          legend_title_text="Division", hoverlabel=dict(bgcolor="#182334", font_color="#f4f7ff"))
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("View filtered PO line items"):
        cols = [c for c in ("po_number", "PO Date", "Company", "Division", "Vendor", "PO Status", "Spend Category", "Spend", "Currency") if c in filtered.columns]
        st.dataframe(filtered[cols].sort_values("PO Date", ascending=False), use_container_width=True, hide_index=True)
elif page == "Policy Review":
    nav_left, nav_right = st.columns(2)
    with nav_left:
        st.button("← Back to Load Data", on_click=_open_load_data, use_container_width=True)
    with nav_right:
        st.button("Open AI Chat", on_click=_open_ai_chat, type="primary", use_container_width=True)
    st.header("Procurement policy findings")
    if not st.session_state.rag_context or st.session_state.policy_results is None:
        st.info("Upload a procurement policy PDF and PO files, then prepare the Llama RAG review.")
        st.stop()

    context = st.session_state.rag_context
    results = st.session_state.policy_results
    violations = [result for result in results if result.get("violations")]
    needs_review = [result for result in results if result.get("needs_review")]
    summary = st.columns(3)
    summary[0].metric("Policy conditions", f"{len(context['conditions']):,}")
    summary[1].metric("POs evaluated", f"{len(results):,}")
    summary[2].metric("POs with potential violations", f"{len(violations):,}")

    st.subheader("Important policy conditions")
    for condition in context["conditions"]:
        page_label = f" · page {condition['page']}" if condition.get("page") else ""
        with st.expander(f"{condition['id']} · {condition['condition']}{page_label}"):
            if condition.get("evidence"):
                st.write(f"Policy excerpt: {condition['evidence']}")

    st.subheader("Purchase orders flagged for policy violations")
    violation_rows = []
    for result in violations:
        for violation in result["violations"]:
            if not isinstance(violation, dict):
                continue
            violation_rows.append({
                "PO Number": result["po_number"],
                "Company": result["company"],
                "Date": result["po_date"],
                "Status": result["status"],
                "Vendor(s)": ", ".join(result["vendors"]),
                "Amount(s)": ", ".join(f"{amount:,.2f} {currency}" for currency, amount in result["amount_by_currency"].items()),
                "Condition": violation.get("condition_id", ""),
                "Violation reason": violation.get("reason", ""),
                "PO evidence": violation.get("evidence", ""),
            })
    if violation_rows:
        st.dataframe(pd.DataFrame(violation_rows), use_container_width=True, hide_index=True)
    else:
        st.success("Llama did not flag any purchase orders as policy violations.")
    if needs_review:
        st.subheader("POs needing manual review")
        review_rows = [{
            "PO Number": result["po_number"],
            "Company": result["company"],
            "Status": result["status"],
            "Reason": result["review_note"],
        } for result in needs_review]
        st.dataframe(pd.DataFrame(review_rows), use_container_width=True, hide_index=True)
    st.caption("Findings are generated by a local Llama model and should be reviewed against the cited policy text.")
elif page == "AI Chat":
    nav_left, nav_right = st.columns(2)
    with nav_left:
        st.button("← Policy Findings", on_click=_open_policy_review, use_container_width=True)
    with nav_right:
        st.button("Load Data", on_click=_open_load_data, use_container_width=True)
    st.header("Procurement AI chat")
    st.caption("Ask about the uploaded policy, companies, divisions, vendors, or purchase orders. Responses use the local Llama 3.1 model.")
    if not st.session_state.rag_context:
        st.info("Build a policy RAG context before starting a chat.")
        st.stop()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask a procurement policy or PO question…")
    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.spinner("Searching the uploaded policy and PO data with Llama 3.1…"):
            try:
                reply = answer_question(question, st.session_state.rag_context)
            except Exception as exc:
                reply = f"Local Llama request failed: {exc}"
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()
