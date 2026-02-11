# pages/Ecommerce_SQL.py
# Ecommerce Dashboard (SQL-backed)

import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from utils.navbar import navbar
from streamlit_auth import require_login
from utils.db import get_sql_engine

require_login()

st.set_page_config(
    page_title="Ecommerce Dashboard (SQL)",
    page_icon="📦",
    layout="wide",
)

navbar()

# -----------------------------
# Data access
# -----------------------------
@st.cache_data(ttl=3600)
def load_ecomm_sales(
    company_id: str,
    start_dt: str,
    end_dt: str,
    style_suffix_s_only: bool = True,
):
    """
    Pulls line-level ecomm sales from dbo.vw_ecomm_sales_fact.
    Note: end_dt is inclusive from UI; SQL uses < end_dt_plus_1.
    """
    engine = get_sql_engine()

    # Inclusive end date handling (SQL Server): < DATEADD(day, 1, :end_dt)
    suffix_clause = "AND style_cd LIKE '%-S'" if style_suffix_s_only else ""

    sql = f"""
    SELECT
        company_id,
        order_no,
        order_dt,
        customer_id,
        customer_name AS customer,
        style_cd,
        sku_no,
        so_size,
        sales_qty,
        sales_amt,
        unit_price,
        diamond_wt,
        diamond_qlty
    FROM dbo.vw_ecomm_sales_fact
    WHERE company_id = :company_id
      AND order_dt >= :start_dt
      AND order_dt < DATEADD(day, 1, :end_dt)
      {suffix_clause}
    """

    with engine.connect() as conn:
        df = pd.read_sql_query(
            text(sql),
            conn,
            params={"company_id": company_id, "start_dt": start_dt, "end_dt": end_dt},
        )

    # Types
    if "order_dt" in df.columns:
        df["order_dt"] = pd.to_datetime(df["order_dt"], errors="coerce")

    for col in ["sales_qty", "sales_amt", "unit_price", "diamond_wt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


@st.cache_data(ttl=3600)
def load_customer_dim(company_id: str):
    """
    Customer list just from the view (fast + aligned with fact).
    """
    engine = get_sql_engine()
    sql = """
    SELECT DISTINCT customer_name AS customer
    FROM dbo.vw_ecomm_sales_fact
    WHERE company_id = :company_id
      AND order_dt >= '2023-01-01'
      AND customer_name IS NOT NULL
    ORDER BY customer_name
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(text(sql), conn, params={"company_id": company_id})
    return df["customer"].dropna().tolist()


# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.markdown("## Filters")

company_id = st.sidebar.selectbox("Company", ["DS02"], index=0)

style_suffix_s_only = st.sidebar.checkbox("Only styles ending in -S", value=True)

start_dt = st.sidebar.date_input("Start date", value=pd.Timestamp("2023-01-01").date())
end_dt = st.sidebar.date_input("End date", value=pd.Timestamp.today().date())

if end_dt < start_dt:
    st.sidebar.error("End date must be on/after start date.")
    st.stop()

customers = load_customer_dim(company_id)
customer_selected = st.sidebar.selectbox("Customer", customers)

# Optional: exclude known bad customer (kept from your current page behavior)
exclude_ben_bridge = st.sidebar.checkbox("Exclude Ben Bridge", value=True)


# -----------------------------
# Load / filter data
# -----------------------------
try:
    df_master = load_ecomm_sales(
        company_id=company_id,
        start_dt=str(start_dt),
        end_dt=str(end_dt),
        style_suffix_s_only=style_suffix_s_only,
    )
except Exception as e:
    st.error("Failed to load e-commerce sales from SQL.")
    st.code(str(e))
    st.stop()

if df_master.empty:
    st.warning("No rows returned for the selected filters.")
    st.stop()

if exclude_ben_bridge:
    df_master = df_master[df_master["customer"] != "Ben Bridge"]

df_filtered = df_master[df_master["customer"] == customer_selected].copy()

# Safety
df_filtered = df_filtered.drop_duplicates()

for col in ["sales_qty", "sales_amt", "unit_price", "diamond_wt"]:
    if col in df_filtered.columns:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").fillna(0)


# -----------------------------
# KPIs
# -----------------------------
total_sales = float(df_filtered["sales_amt"].sum()) if "sales_amt" in df_filtered.columns else 0.0
total_units = float(df_filtered["sales_qty"].sum()) if "sales_qty" in df_filtered.columns else 0.0
asp = (total_sales / total_units) if total_units else 0.0

st.title(f"{customer_selected} Ecommerce (SQL)")

st.caption(f"Date range: {start_dt} to {end_dt} | Company: {company_id}")

k1, k2, k3 = st.columns(3)
k1.metric("Total Sales", f"${total_sales:,.0f}")
k2.metric("Units Sold", f"{total_units:,.0f}")
k3.metric("Avg Selling Price", f"${asp:,.2f}")


# -----------------------------
# Trends
# -----------------------------
st.subheader("Sales over time")

if "order_dt" in df_filtered.columns and not df_filtered["order_dt"].isna().all():
    df_ts = (
        df_filtered.dropna(subset=["order_dt"])
        .assign(order_date=lambda x: x["order_dt"].dt.date)
        .groupby("order_date", as_index=False)[["sales_amt", "sales_qty"]]
        .sum()
    )

    fig_sales = px.line(
        df_ts,
        x="order_date",
        y="sales_amt",
        title="Daily Sales",
        labels={"order_date": "Date", "sales_amt": "Sales ($)"},
    )
    st.plotly_chart(fig_sales, use_container_width=True)

    fig_units = px.line(
        df_ts,
        x="order_date",
        y="sales_qty",
        title="Daily Units Sold",
        labels={"order_date": "Date", "sales_qty": "Units"},
    )
    st.plotly_chart(fig_units, use_container_width=True)
else:
    st.info("No order_dt available to plot time series.")


# -----------------------------
# Top styles
# -----------------------------
st.subheader("Top styles by sales")

style_col = "style_cd" if "style_cd" in df_filtered.columns else None
if style_col:
    top_styles = (
        df_filtered.groupby(style_col, as_index=False)[["sales_amt", "sales_qty"]]
        .sum()
        .sort_values("sales_amt", ascending=False)
        .head(50)
    )

    fig_top = px.bar(
        top_styles,
        x="sales_amt",
        y=style_col,
        orientation="h",
        title="Top 50 Styles by Sales ($)",
        labels={"sales_amt": "Sales ($)", style_col: "Style"},
        hover_data=["sales_qty"],
    )
    fig_top.update_layout(yaxis=dict(autorange="reversed"), xaxis_tickformat=",")
    st.plotly_chart(fig_top, use_container_width=True)
else:
    st.info("No style column found.")


# -----------------------------
# Diamonds (optional analysis)
# -----------------------------
st.subheader("Diamond lines (where available)")

if "diamond_wt" in df_filtered.columns:
    diamond_lines = df_filtered[df_filtered["diamond_wt"].fillna(0) > 0].copy()
    if diamond_lines.empty:
        st.info("No diamond weight populated for this customer in the selected range.")
    else:
        cols = [c for c in ["order_dt", "style_cd", "sku_no", "so_size", "sales_qty", "sales_amt", "unit_price", "diamond_wt", "diamond_qlty"] if c in diamond_lines.columns]
        st.dataframe(diamond_lines[cols].sort_values(["diamond_wt", "sales_amt"], ascending=False), use_container_width=True)
else:
    st.info("diamond_wt not available in dataset.")


# -----------------------------
# Detail table + download
# -----------------------------
st.subheader("Line detail")

detail_cols = [c for c in ["order_dt", "order_no", "customer", "style_cd", "sku_no", "so_size", "sales_qty", "sales_amt", "unit_price", "diamond_wt", "diamond_qlty"] if c in df_filtered.columns]
st.dataframe(df_filtered[detail_cols].sort_values("order_dt", ascending=False), use_container_width=True)

st.subheader("Download")
st.download_button(
    label="Download filtered CSV",
    data=df_filtered.to_csv(index=False),
    file_name=f"ecomm_sql_{customer_selected}_{start_dt}_to_{end_dt}.csv",
    mime="text/csv",
)
