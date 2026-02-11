import unicodedata
from calendar import monthrange
from utils.navbar import navbar
import datetime as dt
import pandas as pd
import streamlit as st
import plotly.express as px
import requests
from sqlalchemy import text
from utils.db import get_sql_engine

# Page config
st.set_page_config(
    page_title="Customer Sales Analysis",
    page_icon="🪙",
    layout="wide"
)
navbar()
st.title("General Customer Sales")

# Load dataset
@st.cache_data
def load_sales():
    url = f"https://api.anerijewels.com/api/customersales"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

def load_local():
    # Fallback to local CSV for testing
    csv_path = st.secrets["LOCAL_CUS_SALES_PATH"]
    return pd.read_csv(csv_path)


@st.cache_data(ttl=120)
def load_sales_sql(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    """
    Pull only what you need from SQL.
    end_date is treated as inclusive in your UI; convert to < next_day for SQL.
    """
    engine = get_sql_engine()

    end_exclusive = (end_date + pd.Timedelta(days=1)).normalize()

    sql = """
    SELECT customer_code, customer_name, trans_dt, qty, sales
    FROM aneri_reporting.vw_sales_dashboard
    WHERE trans_dt >= :start_date
      AND trans_dt <  :end_exclusive
    """
    params = {"start_date": start_date, "end_exclusive": end_exclusive}

    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params=params)

    return df

# -------------------------
# Sidebar filters
# -------------------------
st.sidebar.header("Filters")

today = pd.Timestamp.today().normalize()
default_start = today - pd.Timedelta(days=30)

start_date = st.sidebar.date_input("Start date", value=default_start.date())
end_date   = st.sidebar.date_input("End date", value=today.date())

start_date = pd.to_datetime(start_date)
end_date   = pd.to_datetime(end_date)

if start_date > end_date:
    st.warning("Start date cannot be after end date.")
    st.stop()
# -------------------------

try:
    use_local = st.secrets.get("USE_LOCAL_CUS_SALES_DATA", False)
    if use_local:
        df = load_local()
    else:
        df = load_sales_sql(start_date, end_date)   # SQL only pulls selected range
except Exception as e:
    st.error("❌ Failed to load updated data.")
    st.text(f"Error: {e}")
    st.stop()



# -------------------------
# Basic prep (lightweight)
# -------------------------
# Ensure correct dtypes
df["trans_dt"] = pd.to_datetime(df["trans_dt"])
df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0)
df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0)

# Month bucket for MoM chart
df["month"] = df["trans_dt"].dt.to_period("M").dt.to_timestamp()


# -------------------------
# Filtered period view
# -------------------------
#mask = (df["trans_dt"] >= start_date) & (df["trans_dt"] <= end_date)
#df_period = df.loc[mask].copy()

df_period = df.copy()

if df_period.empty:
    st.warning("No data in the selected date range.")
    st.stop()

# Aggregate by customer
df_cust = (
    df_period
    .groupby(["customer_code", "customer_name"], as_index=False)
    .agg(
        qty=("qty", "sum"),
        sales=("sales", "sum"),
    )
    .sort_values("sales", ascending=False)
)
df_cust["qty"] = df_cust["qty"].round(0).astype("int64")
df_cust["sales"] = df_cust["sales"].round(0).astype("int64")

# -------------------------
# KPIs
# -------------------------
total_sales = df_cust["sales"].sum()
total_qty = df_cust["qty"].sum()
n_customers = df_cust["customer_code"].nunique()

c1, c2, c3 = st.columns(3)
c1.metric("Total Sales", f"${total_sales:,.0f}")
c2.metric("Total Units", f"{total_qty:,.0f}")
c3.metric("Active Customers", f"{n_customers:,}")

st.caption(
    f"Selected period: {start_date.date()} → {end_date.date()}"
)

# -------------------------
# Customer breakdown table
# -------------------------
st.subheader("Customer Breakdown (Selected Period)")
cust_config = {
    "customer_code": st.column_config.TextColumn("Customer Code"),
    "customer_name": st.column_config.TextColumn("Customer Name"),
    "qty": st.column_config.NumberColumn("Total Units Sold", format="localized"),
    "sales": st.column_config.NumberColumn("Total Sales", format="dollar"),
}

st.dataframe(df_cust, column_config=cust_config)

# --------------------------
# Month-over-Month trend
# -------------------------
st.subheader("Month-over-Month Sales Trend")

# Overall MoM (full history)
mom = (
    df
    .groupby("month", as_index=False)
    .agg(sales=("sales", "sum"))
    .sort_values("month")
)

fig = px.line(
    mom,
    x="month",
    y="sales",
    markers=True,
    labels={"month": "Month", "sales": "Total Sales"},
    title="Total Sales by Month",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Month-over-Month Sales Trend (Selected Range)")

mom_range = (
    df_period
    .groupby("month", as_index=False)
    .agg(sales=("sales", "sum"))
    .sort_values("month")
)

fig_range = px.bar(
    mom_range,
    x="month",
    y="sales",
    labels={"month": "Month", "sales": "Sales (Selected Range)"},
    title="Sales by Month (Selected Date Range)",
)
st.plotly_chart(fig_range, use_container_width=True)
