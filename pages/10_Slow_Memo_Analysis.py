import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import requests
from io import BytesIO
from utils.navbar import navbar
from streamlit_auth import require_login

require_login()


# Page config
st.set_page_config(
    page_title="Slow Moving Memo",
    page_icon="🪙",
    layout="wide"
)
navbar()
st.title("🪙 Slow Moving Memo Analysis")

# Load dataset
@st.cache_data
def load_memo():
    url = f"https://api.anerijewels.com/api/memo"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

def load_local():
    # Fallback to local CSV for testing
    csv_path = st.secrets["LOCAL_MEMO_PATH"]
    return pd.read_csv(csv_path)

try:
    use_local = st.secrets.get("USE_LOCAL_MEMO_DATA", False)
    df = load_local() if use_local else load_memo()
except Exception as e:
    st.error("❌ Failed to load updated data.")
    st.text(f"Error: {e}")

# === Sidebar Filters ===
st.sidebar.header("Filters")

# Filter: Account Executive
ae_selected = st.sidebar.multiselect("Account Executive(s)", df["AE"].unique())
if ae_selected:
    df = df[df["AE"].isin(ae_selected)]

# Filter: Customer
customer_selected = st.sidebar.multiselect("Customer(s)", df["Customer"].unique())
if customer_selected:
    df = df[df["Customer"].isin(customer_selected)]

# ✅ NEW: Filter by Metal
metal_selected = st.sidebar.multiselect("Metal Type(s)", df["Metal Kt"].unique())
if metal_selected:
    df = df[df["Metal Kt"].isin(metal_selected)]

# Filter: Performance Category
performance_selected = st.sidebar.multiselect("Performance Category", df["Performance_Category"].unique())
if performance_selected:
    df = df[df["Performance_Category"].isin(performance_selected)]

# --- Disposition filter (normalized) ---
def _normalize_disposition(s: pd.Series) -> pd.Series:
    s = (
        s.fillna("").astype(str).str.strip()
         .str.replace(r"\s+", " ", regex=True).str.lower()
    )
    canon = {
        "": "Unspecified",
        "unspecified": "Unspecified",
        "perpetual memo": "Perpetual Memo",
        "hold on memo/monitor": "Hold On Memo/Monitor",
        "rtv closeout": "RTV - Closeout",
        "rtv - closeout": "RTV - Closeout",
        "rtv- closeout": "RTV - Closeout",
        "rtv melt": "RTV - Melt",
        "rtv - melt": "RTV - Melt",
        "rtv- melt": "RTV - Melt",
    }
    s = s.replace(canon)
    s = s.apply(lambda x: x if x in {"Unspecified","Perpetual Memo","Hold On Memo/Monitor","RTV - Closeout","RTV - Melt"} else (x.title() if x else "Unspecified"))
    return s

if "Disposition" in df.columns:
    df["_Disp"] = _normalize_disposition(df["Disposition"])
    disp_options = ["All"] + sorted(df["_Disp"].dropna().unique().tolist())
    disp_selected = st.sidebar.multiselect("Disposition", disp_options, default=["All"])
    if disp_selected and "All" not in disp_selected:
        df = df[df["_Disp"].isin(disp_selected)]

st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# === KPI Display ===
st.subheader("🔢 Key Metrics")

col1, col2, col3 = st.columns(3)
col1.metric("Total Styles", f"{len(df):,}")
col2.metric("Open Memo Quantity", f"{(df['Open_Memo_Qty']).sum():,}")
col3.metric("Open Memo Value", f"${(df['Open_Memo_Amt']).sum():,.0f}")


# === Display Sorted Table ===
st.subheader("Detailed Memo Table (Sorted)")

sort_columns = {
    "Open Memo Qty": "Open_Memo_Qty",
    "Open Memo Amt ($)": "Open_Memo_Amt",
    "Net Sales 2025 YTD ($)": "Net_Sales_2025_YTD"
}

# Real pill-style selection
sort_display = st.radio(
    "Sort by Column:",
    options=list(sort_columns.keys()),
    index=0,
    horizontal=True,
)

# Map the display label back to the real column
sort_column = sort_columns[sort_display]

# Order selector (still native radio for now)
sort_order = st.radio(
    "Order:",
    options=["Descending", "Ascending"],
    index=0,
    horizontal=True,
)
ascending = sort_order == "Ascending"

# Sort and display
df_sorted = df.sort_values(by=sort_column, ascending=ascending)

# Display top rows (now includes Disposition/Comments if present)
base_cols = [
    "AE", "Customer", "Metal Kt", "Style", "image_url", "Style Description", "Inception Dt.",
    "Performance_Category"
]
extra_cols = [c for c in ["Disposition", "Comments"] if c in df_sorted.columns]
metric_cols = ["Open_Memo_Qty", "Open_Memo_Amt", "Net_Sales_2025_YTD", "Expected_Sales_6mo"]

cols_to_show = [c for c in (base_cols + extra_cols + metric_cols) if c in df_sorted.columns]


# Display with images
st.data_editor(
    df_sorted[cols_to_show],
    hide_index=True,
    use_container_width=True,
    column_config={
        "image_url": st.column_config.ImageColumn(
            "Image",
            help="Thumbnail",
            width="medium"
        ),
        "Open_Memo_Qty": st.column_config.NumberColumn(
            "Open Memo Qty",
            format=None 
        ),
        "Open_Memo_Amt": st.column_config.NumberColumn(
            "Open Memo Amt ($)",
            format="dollar"  
        ),
        "Net_Sales_2025_YTD": st.column_config.NumberColumn(
            "Net Sales 2025 YTD ($)",
            format="dollar"
        ),
        "Expected_Sales_6mo": st.column_config.NumberColumn(
            "Expected Sales (6mo)",
            format=None
        ),
    },
)


# === Use your filtered DataFrame here
df_filtered = df_sorted.copy()

# === Pivot helper ===
def stacked_bar_from_pivot(pivot_df: pd.DataFrame, index_name: str, title: str, top_n: int = 10):
    # Drop any 'Total' col if present, sort by total
    df2 = pivot_df.copy()
    if "Total" in df2.columns:
        df2 = df2.drop(columns="Total")
    totals = df2.sum(axis=1)
    df2 = df2.loc[totals.sort_values(ascending=False).index].head(top_n)

    # Convert to long form for Plotly
    df2 = df2.reset_index().rename(columns={df2.index.name or index_name: index_name})
    long_df = df2.melt(id_vars=index_name, var_name="Category", value_name="Count")
    long_df = long_df[long_df["Count"] > 0]

    fig = px.bar(
        long_df,
        x="Count", y=index_name, color="Category",
        orientation="h", barmode="stack",
        title=title,
        category_orders={"Category": ["Dead Weight", "Slow Mover", "Review"]},  # adjust if more
        color_discrete_map={
            "Dead Weight": "#ef4444",  # red
            "Slow Mover": "#f59e0b",   # amber
            "Review": "#6b7280",       # gray
        }
    )
    st.plotly_chart(fig, width='stretch')


# === Build pivots from df_filtered ===
if "AE" in df_filtered.columns:
    ae_pivot = df_filtered.pivot_table(
        index="AE", columns="Performance_Category", values="Style", aggfunc="size", fill_value=0
    )
    ae_group_sorted = ae_pivot.assign(Total=ae_pivot.sum(axis=1)).sort_values("Total", ascending=False)
    stacked_bar_from_pivot(ae_group_sorted, "AE", "AEs by Performance Category", top_n=None)

top_n = st.slider("Top N Customers", 5, 20, 10, step=1)

if "Customer" in df_filtered.columns:
    customer_pivot = df_filtered.pivot_table(
        index="Customer", columns="Performance_Category", values="Style", aggfunc="size", fill_value=0
    )
    customer_group_sorted = customer_pivot.assign(Total=customer_pivot.sum(axis=1)).sort_values("Total", ascending=False)
    stacked_bar_from_pivot(customer_group_sorted, "Customer", "Top Customers by Count", top_n=top_n)


# === Dispositions Analytics ===
st.subheader("Dispositions Analytics")

# Guard: if Disposition not present, show info and skip
if "Disposition" not in df_filtered.columns:
    st.info("No 'Disposition' column found in the current dataset.")
else:
    # Normalize Disposition to canonical labels
    disp_raw = (
        df_filtered["Disposition"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.lower()
    )
    canon_map = {
        "": "Unspecified",
        "unspecified": "Unspecified",
        "perpetual memo": "Perpetual Memo",
        "hold on memo/monitor": "Hold on Memo/Monitor",
        "rtv closeout": "RTV - Closeout",
        "rtv - closeout": "RTV - Closeout",
        "rtv- closeout": "RTV - Closeout",
        "rtv melt": "RTV - Melt",
        "rtv- melt": "RTV - Melt",
        "rtv - melt": "RTV - Melt",
        # keep anything else title-cased except 'RTV'
    }
    disp_canon = disp_raw.replace(canon_map)
    # Title-case *other* values without breaking RTV
    disp_canon = disp_canon.apply(lambda s: "RTV - Closeout" if s == "rtv - closeout"
                                  else "RTV - Melt" if s == "rtv - melt"
                                  else s.title() if s not in ["RTV - Closeout", "RTV - Melt", "Unspecified"] else s)
    df_analytics = df_filtered.copy()
    df_analytics["_Disposition"] = disp_canon

    # Coerce amount for safer sums
    amt_col = "Open_Memo_Amt" if "Open_Memo_Amt" in df_analytics.columns else None
    if amt_col:
        df_analytics["_Amt"] = pd.to_numeric(df_analytics[amt_col], errors="coerce")
    else:
        df_analytics["_Amt"] = 0.0
    # KPIs
    total_lines = len(df_analytics)
    unspecified_ct = int((df_analytics["_Disposition"] == "Unspecified").sum())
    assigned_ct = total_lines - unspecified_ct
    completion = 0 if total_lines == 0 else round(100 * assigned_ct / total_lines, 1)

    rtv_mask = df_analytics["_Disposition"].str.startswith("RTV", na=False)
    rtv_ct = int(rtv_mask.sum())
    rtv_amt = float(df_analytics.loc[rtv_mask, "_Amt"].sum())

    hold_ct = int((df_analytics["_Disposition"] == "Hold On Memo/Monitor").sum())
    hold_amt = float(df_analytics.loc[df_analytics["_Disposition"] == "Hold On Memo/Monitor", "_Amt"].sum())

    perp_ct = int((df_analytics["_Disposition"] == "Perpetual Memo").sum())
    perp_amt = float(df_analytics.loc[df_analytics["_Disposition"] == "Perpetual Memo", "_Amt"].sum())

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Lines", f"{total_lines:,}")
    k2.metric("Completion", f"{completion}%", f"-{unspecified_ct:,} Unspecified", delta_color="off")
    k3.metric("RTV", f"{rtv_ct:,}", f"${rtv_amt:,.0f}", delta_color="off")
    k4.metric("Hold/Monitor", f"{hold_ct:,}", f"${hold_amt:,.0f}", delta_color="off")
    k5.metric("Perpetual Memo", f"{perp_ct:,}", f"${perp_amt:,.0f}", delta_color="off")

    # Metric toggle
    metric = st.radio("Metric", ["Count", "Open_Memo_Amt ($)"], horizontal=True, index=0)
    value_col = "Count" if metric == "Count" else "Amt"

    # Grouped data
    g_disp = (
        df_analytics.groupby("_Disposition", dropna=False)
        .agg(Count=("Style", "size"), Amt=("_Amt", "sum"))
        .reset_index()
        .sort_values(value_col, ascending=False)
    )

    g_ae = (
        df_analytics.groupby(["AE", "_Disposition"], dropna=False)
        .agg(Count=("Style", "size"), Amt=("_Amt", "sum"))
        .reset_index()
    ) if "AE" in df_analytics.columns else pd.DataFrame()

    # Pie: disposition mix
    pie = px.pie(
        g_disp,
        names="_Disposition",
        values=value_col,
        hole=0.35,
        title=f"Disposition Mix — {metric}"
    )
    st.plotly_chart(pie, width='stretch')

    # Stacked bar by AE
    if not g_ae.empty:
        bar = px.bar(
            g_ae,
            x="AE",
            y=value_col,
            color="_Disposition",
            barmode="stack",
            title=f"Dispositions by AE — {metric}"
        )
        st.plotly_chart(bar, width='stretch')

    hide_unspecified_table = st.checkbox("Show Table of Items Requiring Disposition", value=False)
    pending = df_analytics[df_analytics["_Disposition"] == "Unspecified"]
    if pending.empty:
            st.success("All items have a disposition. ✅")
    # Items needing attention
    elif hide_unspecified_table:
        st.markdown("#### Items Requiring Disposition")
        cols_show = [c for c in ["AE", "Customer", "Style", "Style Description", "Open_Memo_Qty", "Open_Memo_Amt", "Inception Dt.", "RA_Issued"] if c in pending.columns]
        st.dataframe(
            pending[cols_show].style.format({
                "Open_Memo_Qty": "{:,}" if "Open_Memo_Qty" in pending.columns else "{:}",
                "Open_Memo_Amt": "${:,.2f}" if "Open_Memo_Amt" in pending.columns else "{:}",
            })
        )
        st.download_button(
            "📥 Download Unspecified Items (CSV)",
            data=pending[cols_show].to_csv(index=False),
            file_name=f"SlowMemo_Unspecified_{datetime.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )

# === Simple export for edits (no extra cols, no dropdowns) ===
st.subheader("📥 Export current view")

# CSV download button
csv_name = f"SlowMemo_filtered_{datetime.today().strftime('%Y-%m-%d')}.csv"
st.download_button(
    label="Download filtered CSV",
    data=df_filtered.to_csv(index=False),
    file_name=csv_name,
    mime="text/csv"
)

# === Worklist (Disposition-only) ===
st.subheader(" Worklist (Disposition-only)")

work_cols_pref = [
    "AE", "Customer", "Style","image_url", "Style Description",
    "Inception Dt.", "RA_Issued", "Performance_Category",
    "Disposition", "Comments"
]
work_cols = [c for c in work_cols_pref if c in df_filtered.columns]

# Default: show unresolved first
if "Disposition" in df_filtered.columns:
    disp_norm = _normalize_disposition(df_filtered["Disposition"])
    work_df = df_filtered.assign(_Disp=disp_norm).copy()
    # Replace the "Show Unspecified first" logic with this:
    hide_unspecified = st.checkbox("Hide Unspecified", value=False)

    work_df = df_filtered.copy()
    if "Disposition" in work_df.columns:
        work_df["_Disp"] = _normalize_disposition(work_df["Disposition"])
        if hide_unspecified:
            hidden = int((work_df["_Disp"] == "Unspecified").sum())
            work_df = work_df[work_df["_Disp"] != "Unspecified"]
            st.caption(f"Filtered out {hidden:,} Unspecified rows.")
        # Optional: keep a stable sort for review
        sort_keys = [c for c in ["AE", "Customer", "Style"] if c in work_df.columns]
        if sort_keys:
            work_df = work_df.sort_values(by=sort_keys)
else:
    work_df = df_filtered.copy()

if work_cols:
    st.data_editor(
    work_df[work_cols],
    hide_index=True,
    use_container_width=True,
    column_config={
        # Example: uncomment or add as needed
        "image_url": st.column_config.ImageColumn("Image", width="medium")
    },
)

    st.download_button(
        "📥 Download Worklist (CSV)",
        data=work_df[work_cols].to_csv(index=False),
        file_name=f"SlowMemo_Worklist_{datetime.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv"
    )
else:
    st.info("No disposition-related columns available to show in Worklist.")


# def build_disposition_template_legacy(df_in):
#     """Legacy: creates Excel with Disposition dropdowns (not used now)."""
#     from io import BytesIO
#     from openpyxl import Workbook
#     from openpyxl.utils.dataframe import dataframe_to_rows
#     from openpyxl.worksheet.datavalidation import DataValidation

#     df_out = df_in.copy()
#     for col in ['Date_RA_Issued', 'Disposition', 'Comments']:
#         if col not in df_out.columns:
#             df_out[col] = ""

#     wb = Workbook()
#     ws = wb.active
#     ws.title = "SlowMemoExport"
#     for r in dataframe_to_rows(df_out, index=False, header=True):
#         ws.append(r)

#     if "Disposition" in df_out.columns:
#         idx = list(df_out.columns).index("Disposition") + 1
#         col_letter = ws.cell(row=1, column=idx).column_letter
#         rng = f"{col_letter}2:{col_letter}{len(df_out)+1}"
#         dv = DataValidation(
#             type="list",
#             formula1='"Perpetual memo,Hold on memo/Monitor,RTV - Closeout,RTV- Melt,Other"',
#             allow_blank=True,
#         )
#         ws.add_data_validation(dv); dv.add(rng)

#     buf = BytesIO(); wb.save(buf); buf.seek(0)
#     return buf, f"SlowMemo_template_{datetime.today().strftime('%Y-%m-%d')}.xlsx"

# (not called)
