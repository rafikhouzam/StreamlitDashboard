import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
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

# ----------------------------
# Load from SQL (enriched view)
# ----------------------------
# Load dataset
@st.cache_data
def load_memo():
    url = f"https://api.anerijewels.com/api/memo"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

@st.cache_data(ttl=60)
def fetch_memo_health():
    url = f"https://api.anerijewels.com/memo/health"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=300)
def fetch_memo(cust_code=None, department=None, ae=None, performance_category=None, limit=5000):
    """
    Reads memo data from the new FastAPI route:
      GET {API_BASE}/memo?limit=...
    Expected response:
      {"count": N, "rows": [ ... ]}
    """
    params = {"limit": limit}
    if cust_code: params["cust_code"] = cust_code
    if department: params["department"] = department
    if ae: params["ae"] = ae
    if performance_category: params["performance_category"] = performance_category

    url = f"https://api.anerijewels.com/api/memo"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}

    r = requests.get(url, headers=headers, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()

    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    meta = {
        "total": payload.get("count", len(rows)) if isinstance(payload, dict) else len(rows),
    }
    df = pd.DataFrame(rows)
    return meta, df

meta, df = fetch_memo(limit=5000)

# Optional: show freshness (kept lightweight)
try:
    health = fetch_memo_health()
    st.caption(f"API rows: {health.get('rows')} | cache_age_seconds: {health.get('cache_age_seconds')} | etag: {health.get('etag')}")
except Exception:
    pass

#st.write(f"Snapshot: {payload['snapshot_date']} | Rows returned: {len(df)} | Total: {payload['total']}")
#st.write(df.columns.tolist())
st.dataframe(df, use_container_width=True)
# ----------------------------
# Apply runtime merge (Style-level)
# ----------------------------
for c in ["RA_Issued"]:
    if c in df.columns:
        df[c] = df[c].fillna("")


RENAME_MAP = {
    "Div": "Div",
    "AE": "AE",
    "Buyer": "Buyer",
    "Department": "Department",
    "Cust Code": "Cust Code",
    "Customer": "Customer",
    "Style": "Style",
    "Style Description": "Style Description",
    "SKU No.": "SKU No.",
    "Metal Kt": "Metal Kt",
    "Inception Dt.": "Inception Dt.",
    "OM 1/1/24": "OM 1/1/24",

    # shipping / returns consolidation
    "Shipped_Qty": "Shipped Qty 2024-25",
    "Returned_Qty": "Returned Qty 2024-25",

    # sales
    "Net_Sales_2024": "Net Sales 2024",
    "Net_Sales_2025_YTD": "Net Sales 2025 YTD",
    "Net_Sales_2026": "Net Sales 2026",

    # memo + performance
    "Open_Memo_Qty": "Open Memo Qty",
    "Open_Memo_Amt": "Open Memo Amt",
    "Sell_Through_Pct": "Sell Through %",
    "Expected_Sales_6mo": "Expected Sales in next 6 months",
    "Excess": "Excess",

    # RA / misc
    "RA_Issued": "RA_Issued",
    "Date_RA_Issued": "Date_RA_Issued",
    "Disposition": "Disposition",
    "Comments": "Comments",
    "Performance_Category": "Performance_Category",
    "image_url": "image_url",
}

preferred_order = [
    "Div",
    "AE",
    "Buyer",
    "Department",
    "Cust Code",
    "Customer",
    "Style",
    "Style Description",
    "SKU No.",
    "Metal Kt",
    "Inception Dt.",
    "OM 1/1/24",
    "Shipped Qty 2024-25",
    "Returned Qty 2024-25",
    "Net Sales 2024",
    "Net Sales 2025 YTD",
    "Net Sales 2026",
    "Open Memo Qty",
    "Open Memo Amt",
    "Sell Through %",
    "Expected Sales in next 6 months",
    "Excess",
    "RA_Issued",
    "Date_RA_Issued",
    "Disposition",
    "Comments",
    "Performance_Category",
    "image_url",
]

#rename
#df = df.rename(columns={k: v for k, v in RENAME_MAP.items() if k in df.columns})
# reorder
df = df[[c for c in preferred_order if c in df.columns]]

# ----------------------------
# Type coercions (new column names)
# ----------------------------
money_cols = [
    "Open Memo Amt",
]
qty_cols = [
    "OM 1/1/24",
    "Shipped Qty 2024-25",
    "Returned Qty 2024-25",
    "Net Sales 2024",
    "Net Sales 2025 YTD",
    "Net Sales 2026",
    "Open Memo Qty",
    "Expected Sales in next 6 months",
    "Excess",
    "Sell Through %",  # keep numeric (0-1)
]

def normalize_disposition(s: pd.Series) -> pd.Series:
    """
    Canonicalize disposition values for consistent filtering + analytics.
    Output values are in this set:
      Unspecified, Perpetual Memo, Hold On Memo/Monitor, RTV - Closeout, RTV - Melt, <Other Title Cased>
    """
    s = (
        s.fillna("").astype(str).str.strip()
         .str.replace(r"\s+", " ", regex=True).str.lower()
    )

    canon = {
        "": "Unspecified",
        "unspecified": "Unspecified",
        "perpetual memo": "Perpetual Memo",
        "hold on memo/monitor": "Hold On Memo/Monitor",
        "hold on memo / monitor": "Hold On Memo/Monitor",
        "rtv closeout": "RTV - Closeout",
        "rtv - closeout": "RTV - Closeout",
        "rtv- closeout": "RTV - Closeout",
        "rtv melt": "RTV - Melt",
        "rtv - melt": "RTV - Melt",
        "rtv- melt": "RTV - Melt",
    }

    s = s.replace(canon)

    allowed = {"Unspecified", "Perpetual Memo", "Hold On Memo/Monitor", "RTV - Closeout", "RTV - Melt"}
    s = s.apply(lambda x: x if x in allowed else (x.title() if x else "Unspecified"))

    return s


def to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
         .str.replace(r"[\$,]", "", regex=True)
         .str.strip(),
        errors="coerce"
    )

for c in money_cols + qty_cols:
    if c in df.columns:
        df[c] = to_number(df[c])

# Datetime coercion
if "Inception Dt." in df.columns:
    df["Inception Dt."] = pd.to_datetime(df["Inception Dt."], errors="coerce")

if "Date_RA_Issued" in df.columns:
    df["Date_RA_Issued"] = pd.to_datetime(df["Date_RA_Issued"], errors="coerce")

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters")

if "AE" in df.columns:
    ae_selected = st.sidebar.multiselect("Account Executive(s)", sorted(df["AE"].dropna().unique().tolist()))
    if ae_selected:
        df = df[df["AE"].isin(ae_selected)]

if "Customer" in df.columns:
    customer_selected = st.sidebar.multiselect("Customer(s)", sorted(df["Customer"].dropna().unique().tolist()))
    if customer_selected:
        df = df[df["Customer"].isin(customer_selected)]

if "Metal Kt" in df.columns:
    metal_selected = st.sidebar.multiselect("Metal Type(s)", sorted(df["Metal Kt"].dropna().unique().tolist()))
    if metal_selected:
        df = df[df["Metal Kt"].isin(metal_selected)]

# --- Disposition filter (normalized) ---
if "Disposition" in df.columns:
    df["_Disp"] = normalize_disposition(df["Disposition"])
    disp_options = ["All"] + sorted(df["_Disp"].dropna().unique().tolist())
    disp_selected = st.sidebar.multiselect("Disposition", disp_options, default=["All"])
    if disp_selected and "All" not in disp_selected:
        df = df[df["_Disp"].isin(disp_selected)]


if "Performance_Category" in df.columns:
    performance_selected = st.sidebar.multiselect(
        "Performance Category",
        sorted(df["Performance_Category"].dropna().unique().tolist())
    )
    if performance_selected:
        df = df[df["Performance_Category"].isin(performance_selected)]

st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# ----------------------------
# KPIs
# ----------------------------
st.subheader("🔢 Key Metrics")

k1, k2, k3 = st.columns(3)
k1.metric("Total Styles", f"{len(df):,}")
k2.metric("Open Memo Quantity", f"{df['Open Memo Qty'].sum():,.0f}" if "Open Memo Qty" in df.columns else "—")
k3.metric("Open Memo Value", f"${df['Open Memo Amt'].sum():,.0f}" if "Open Memo Amt" in df.columns else "—")

# ----------------------------
# Table: sorting
# ----------------------------
st.subheader("Detailed Memo Table (Sorted)")

sort_columns = {
    "Open Memo Qty": "Open Memo Qty",
    "Open Memo Amt ($)": "Open Memo Amt",
    "Net Sales 2025 YTD (Qty)": "Net Sales 2025 YTD",
    "Excess (Qty)": "Excess",
    "Sell Through %": "Sell Through %"
}

sort_display = st.radio(
    "Sort by Column:",
    options=list(sort_columns.keys()),
    index=0,
    horizontal=True,
)

sort_column = sort_columns[sort_display]

sort_order = st.radio(
    "Order:",
    options=["Descending", "Ascending"],
    index=0,
    horizontal=True,
)
ascending = sort_order == "Ascending"

df_sorted = df.sort_values(by=sort_column, ascending=ascending)

# Columns to show
base_cols = [
    "Div", "AE", "Customer", "Buyer",
    "Style", "SKU No.", "Metal Kt",
    "Style Description", "Inception Dt.",
    "Performance_Category",
    "RA_Issued", "Date_RA_Issued",
]
metric_cols = [
    "OM 1/1/24",
    "Shipped Qty 2024-25",
    "Returned Qty 2024-25",
    "Net Sales 2024",
    "Net Sales 2025 YTD",
    "Net Sales 2026",
    "Open Memo Qty",
    "Open Memo Amt",
    "Sell Through %",
    "Expected Sales in next 6 months",
    "Excess",
]

cols_to_show = [c for c in (base_cols + metric_cols) if c in df_sorted.columns]

# Render
st.data_editor(
    df_sorted[cols_to_show],
    hide_index=True,
    use_container_width=True,
    column_config={
        "image_url": st.column_config.ImageColumn("Image", width="medium"),
        "Open Memo Amt": st.column_config.NumberColumn("Open Memo Amt ($)", format="dollar"),
        "Sell Through %": st.column_config.NumberColumn("Sell Through %", format="%.2f"),
        "Inception Dt.": st.column_config.DatetimeColumn("Inception Dt."),
        "Date_RA_Issued": st.column_config.DatetimeColumn("Date RA Issued"),
    },
)

df_filtered = df_sorted.copy()

# ----------------------------
# Pivots
# ----------------------------
def stacked_bar_from_pivot(pivot_df: pd.DataFrame, index_name: str, title: str, top_n: int | None = 10):
    df2 = pivot_df.copy()
    if "Total" in df2.columns:
        df2 = df2.drop(columns="Total")

    totals = df2.sum(axis=1)
    df2 = df2.loc[totals.sort_values(ascending=False).index]
    if top_n is not None:
        df2 = df2.head(top_n)

    df2 = df2.reset_index().rename(columns={df2.index.name or index_name: index_name})
    long_df = df2.melt(id_vars=index_name, var_name="Category", value_name="Count")
    long_df = long_df[long_df["Count"] > 0]

    fig = px.bar(
        long_df,
        x="Count", y=index_name, color="Category",
        orientation="h", barmode="stack",
        title=title,
        category_orders={"Category": ["Dead Weight", "Slow Mover", "Review"]},
    )
    st.plotly_chart(fig, use_container_width=True)

if {"AE", "Performance_Category", "Style"}.issubset(df_filtered.columns):
    ae_pivot = df_filtered.pivot_table(
        index="AE", columns="Performance_Category", values="Style", aggfunc="size", fill_value=0
    )
    ae_group_sorted = ae_pivot.assign(Total=ae_pivot.sum(axis=1)).sort_values("Total", ascending=False)
    stacked_bar_from_pivot(ae_group_sorted, "AE", "AEs by Performance Category", top_n=None)

top_n = st.slider("Top N Customers", 5, 30, 10, step=1)

if {"Customer", "Performance_Category", "Style"}.issubset(df_filtered.columns):
    customer_pivot = df_filtered.pivot_table(
        index="Customer", columns="Performance_Category", values="Style", aggfunc="size", fill_value=0
    )
    customer_group_sorted = customer_pivot.assign(Total=customer_pivot.sum(axis=1)).sort_values("Total", ascending=False)
    stacked_bar_from_pivot(customer_group_sorted, "Customer", "Top Customers by Count", top_n=top_n)
# ----------------------------
# Dispositions Analytics (ported from old page)
# ----------------------------
st.subheader("Dispositions Analytics")

if "Disposition" not in df_filtered.columns:
    st.info("No 'Disposition' column found in the current dataset.")
else:
    df_analytics = df_filtered.copy()
    df_analytics["_Disposition"] = normalize_disposition(df_analytics["Disposition"])

    # Amount column in your new schema
    amt_col = "Open Memo Amt" if "Open Memo Amt" in df_analytics.columns else None
    if amt_col:
        df_analytics["_Amt"] = pd.to_numeric(df_analytics[amt_col], errors="coerce")
    else:
        df_analytics["_Amt"] = 0.0

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

    metric = st.radio("Metric", ["Count", "Open Memo Amt ($)"], horizontal=True, index=0)
    value_col = "Count" if metric == "Count" else "Amt"

    g_disp = (
        df_analytics.groupby("_Disposition", dropna=False)
        .agg(Count=("Style", "size"), Amt=("_Amt", "sum"))
        .reset_index()
        .sort_values(value_col, ascending=False)
    )

    pie = px.pie(
        g_disp,
        names="_Disposition",
        values=value_col,
        hole=0.35,
        title=f"Disposition Mix — {metric}"
    )
    st.plotly_chart(pie, use_container_width=True)

    if "AE" in df_analytics.columns:
        g_ae = (
            df_analytics.groupby(["AE", "_Disposition"], dropna=False)
            .agg(Count=("Style", "size"), Amt=("_Amt", "sum"))
            .reset_index()
        )
        bar = px.bar(
            g_ae,
            x="AE",
            y=value_col,
            color="_Disposition",
            barmode="stack",
            title=f"Dispositions by AE — {metric}"
        )
        st.plotly_chart(bar, use_container_width=True)

    show_pending = st.checkbox("Show Table of Items Requiring Disposition", value=False)
    pending = df_analytics[df_analytics["_Disposition"] == "Unspecified"]

    if pending.empty:
        st.success("All items have a disposition. ✅")
    elif show_pending:
        st.markdown("#### Items Requiring Disposition")

        cols_show = [c for c in [
            "AE", "Customer", "Style", "Style Description",
            "Open Memo Qty", "Open Memo Amt", "Inception Dt.", "RA_Issued"
        ] if c in pending.columns]

        st.dataframe(pending[cols_show], use_container_width=True)

        st.download_button(
            "📥 Download Unspecified Items (CSV)",
            data=pending[cols_show].to_csv(index=False),
            file_name=f"SlowMemo_Unspecified_{datetime.today().strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )

# ----------------------------
# RA Activity
# ----------------------------
st.subheader("RA Activity")

if "Date_RA_Issued" not in df_filtered.columns:
    st.info("No Date_RA_Issued column available.")
else:
    ra_df = df_filtered.loc[df_filtered["Date_RA_Issued"].notna()].copy()

    c1, c2, c3 = st.columns(3)
    total_ras = len(ra_df)
    ras_30d = len(ra_df.loc[ra_df["Date_RA_Issued"] >= (pd.Timestamp.today().normalize() - pd.Timedelta(days=30))])

    c1.metric("Total RAs (dated)", f"{total_ras:,}")
    c2.metric("RAs last 30 days", f"{ras_30d:,}")

    if "Open Memo Amt" in ra_df.columns:
        c3.metric("Open Memo Value (RA styles)", f"${ra_df['Open Memo Amt'].sum():,.0f}")
    else:
        c3.metric("Open Memo Value (RA styles)", "—")

    granularity = st.radio("Granularity", ["Daily", "Monthly"], horizontal=True)

    if total_ras == 0:
        st.info("No valid RA dates found in Date_RA_Issued yet.")
    else:
        if granularity == "Daily":
            series = (
                ra_df
                .groupby(ra_df["Date_RA_Issued"].dt.date)
                .agg(
                    RA_Count=("Date_RA_Issued", "size"),
                    RA_Value=("Open Memo Amt", "sum") if "Open Memo Amt" in ra_df.columns else ("Date_RA_Issued", "size")
                )
                .reset_index()
                .rename(columns={"Date_RA_Issued": "Date"})
            )
            fig = px.bar(
                series,
                x="Date",
                y="RA_Count",
                hover_data={"RA_Count": True, "RA_Value": ":$,.0f", "Date": True}
            )
            fig.update_layout(yaxis_title="RAs", xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        else:
            series = (
                ra_df
                .assign(Month=ra_df["Date_RA_Issued"].dt.to_period("M").dt.to_timestamp())
                .groupby("Month")
                .agg(
                    RA_Count=("Date_RA_Issued", "size"),
                    RA_Value=("Open Memo Amt", "sum") if "Open Memo Amt" in ra_df.columns else ("Date_RA_Issued", "size")
                )
                .reset_index()
            )
            fig = px.bar(
                series,
                x="Month",
                y="RA_Count",
                hover_data={"RA_Count": True, "RA_Value": ":$,.0f", "Month": True}
            )
            fig.update_layout(yaxis_title="RAs", xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
# ----------------------------
# Worklist (Disposition-only)
# ----------------------------
st.subheader("Worklist (Disposition-only)")

work_cols_pref = [
    "AE", "Customer", "Style", "image_url", "Style Description",
    "Inception Dt.", "RA_Issued", "Performance_Category",
    "Disposition", "Comments"
]
work_cols = [c for c in work_cols_pref if c in df_filtered.columns]

work_df = df_filtered.copy()
if "Disposition" in work_df.columns:
    work_df["_Disp"] = normalize_disposition(work_df["Disposition"])

hide_unspecified = st.checkbox("Hide Unspecified", value=False)

if "Disposition" in work_df.columns and hide_unspecified:
    hidden = int((work_df["_Disp"] == "Unspecified").sum())
    work_df = work_df[work_df["_Disp"] != "Unspecified"]
    st.caption(f"Filtered out {hidden:,} Unspecified rows.")

sort_keys = [c for c in ["AE", "Customer", "Style"] if c in work_df.columns]
if sort_keys:
    work_df = work_df.sort_values(by=sort_keys)

if work_cols:
    st.data_editor(
        work_df[work_cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "image_url": st.column_config.ImageColumn("Image", width="medium")
        } if "image_url" in work_df.columns else None,
    )

    st.download_button(
        "📥 Download Worklist (CSV)",
        data=work_df[work_cols].to_csv(index=False),
        file_name=f"SlowMemo_Worklist_{datetime.today().strftime('%Y-%m-%d')}.csv",
        mime="text/csv"
    )
else:
    st.info("No disposition-related columns available to show in Worklist.")

# ----------------------------
# Export
# ----------------------------
st.subheader("📥 Export current view")

csv_name = f"SlowMemo_filtered_{datetime.today().strftime('%Y-%m-%d')}.csv"
st.download_button(
    label="Download filtered CSV",
    data=df_filtered.to_csv(index=False),
    file_name=csv_name,
    mime="text/csv"
)
