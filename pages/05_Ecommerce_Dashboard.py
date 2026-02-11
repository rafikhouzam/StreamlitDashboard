# Ecommerce Streamlit Dashboard

import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from utils.navbar import navbar
from streamlit_auth import require_login
import pyodbc
from utils.db import get_sql_engine

require_login()

st.set_page_config(
    page_title="Ecommerce Dashboard",
    page_icon="📦",
    layout="wide"
)
navbar()
# ---------------- Load dataset ----------------
@st.cache_data
def load_ecomm():
    url = "https://api.anerijewels.com/api/updated"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

@st.cache_data
def load_local():
    csv_path = st.secrets["LOCAL_ECOMM_PATH"]
    return pd.read_csv(csv_path)

@st.cache_data(ttl=3600)
def load_ecomm_sql():
    engine = get_sql_engine()

    sql = """
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
    WHERE company_id = 'DS02'
      AND order_dt >= '2023-01-01'
    """

    df = pd.read_sql(sql, engine)

    # enforce numeric safety
    for col in ["sales_qty", "sales_amt", "unit_price", "diamond_wt"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["order_dt"] = pd.to_datetime(df["order_dt"])

    return df

try:
    use_local = st.secrets.get("USE_LOCAL_ECOMM_DATA", False)
    df_master = load_local() if use_local else load_ecomm_sql()
except Exception as e:
    st.error("❌ Failed to load e-commerce data.")
    st.text(f"Error: {e}")
    st.stop()

# remove Ben Bridge data since its poor
df_master = df_master[df_master["customer"] != "Ben Bridge"]
# standardize naming so the rest of your page doesn't change
if "customer_name" in df_master.columns and "customer" not in df_master.columns:
    df_master["customer"] = df_master["customer_name"]


# ---------------- Sidebar ----------------
# Use the new dataset's customer names directly
customers = sorted(df_master["customer"].dropna().unique().tolist())
customer_selected = st.sidebar.selectbox("Customer", customers)

st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# ---------------- Filter & numeric safety ----------------
df_filtered = df_master[df_master["customer"] == customer_selected].copy()
df_filtered = df_filtered.drop_duplicates()

# Numeric-safe fields (only convert if present)
for col in ["sales_qty", "sales_amt", "profit", "extended_cost",
            "avg_unit_price", "avg_unit_cost", "total_inv"]:
    if col in df_filtered.columns:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").fillna(0)

# ---------------- KPIs ----------------
total_sales = df_filtered["sales_amt"].sum() if "sales_amt" in df_filtered else 0
total_units = df_filtered["sales_qty"].sum() if "sales_qty" in df_filtered else 0
total_profit = df_filtered["profit"].sum() if "profit" in df_filtered else 0

# Recalculate profit row by row
if {"sales_amt", "sales_qty", "avg_unit_cost"} <= set(df_filtered.columns):
    df_filtered["profit_calc"] = df_filtered["sales_amt"] - (df_filtered["sales_qty"] * df_filtered["avg_unit_cost"])
    total_profit = df_filtered["profit_calc"].sum()
else:
    total_profit = df_filtered.get("profit", pd.Series([0])).sum()

profit_pct = (total_profit / total_sales * 100) if total_sales > 0 else 0

inv_value = df_filtered["extended_cost"].sum() if "extended_cost" in df_filtered else 0

st.title(f"{customer_selected} Dashboard (1/1/2023 - 9/9/2025)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Sales", f"${total_sales:,.0f}")
col2.metric("Units Sold", f"{total_units:,.0f}")
col3.metric("Profit Margin", f"{profit_pct:.1f}%")
col4.metric("Inventory Value", f"${inv_value:,.0f}")

# ---------------- Viz 1: Performance by Style Category ----------------
if "style_category" in df_filtered.columns and "Performance_Category" in df_filtered.columns:
    st.subheader("Performance by Style Category")
    category_summary = (
        df_filtered.groupby(['style_category', 'Performance_Category'])
        .size().unstack(fill_value=0)
    )
    fig1 = px.bar(
        category_summary.reset_index(),
        x='style_category',
        y=category_summary.columns.tolist(),
        title=f"{customer_selected} Performance by Style Category",
        labels={'value': 'Number of Styles', 'style_category': 'Style Category'},
    )
    fig1.update_layout(barmode='stack', height=500)
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.info("No `style_category` and/or `Performance_Category` to show category performance.")

# ---------------- Viz 2: Overall Style Performance ----------------
st.subheader("Overall Style Performance")
if "Performance_Category" in df_filtered.columns:
    counts = df_filtered["Performance_Category"].value_counts().sort_values(ascending=True)
    df_bar = counts.reset_index()
    df_bar.columns = ['Performance Category', 'Number of Styles']
    fig2 = px.bar(
        df_bar,
        x='Performance Category',
        y='Number of Styles',
        title=f"{customer_selected} Overall Style Performance",
        color_discrete_sequence=['teal']
    )
    fig2.update_layout(xaxis=dict(showgrid=True))
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No `Performance_Category` column found.")

# ---------------- Viz 3: Extended Cost Pie by Category ----------------
st.subheader("Extended Cost by Style Category")
if "style_category" in df_filtered.columns and "extended_cost" in df_filtered.columns:
    category_costs = (
        df_filtered[df_filtered['extended_cost'].notna()]
        .groupby('style_category')['extended_cost']
        .sum()
        .reset_index()
        .sort_values(by='extended_cost', ascending=False)
    )
    if not category_costs.empty:
        fig_pie = px.pie(
            category_costs,
            names='style_category',
            values='extended_cost',
            title='Share of Inventory Value by Category'
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No extended cost data to plot.")
else:
    st.info("Need `style_category` and `extended_cost` to show the pie chart.")

# ---------------- Viz 4: Top 50 Styles by Inventory Value ----------------
st.subheader("Top 50 Styles by Inventory Value")
y_code = 'style_cd' if 'style_cd' in df_filtered.columns else None
if y_code and "extended_cost" in df_filtered.columns:
    top_styles = (
        df_filtered[df_filtered['extended_cost'].notna()]
        .sort_values(by='extended_cost', ascending=False)
        .head(50)
    )
    fig = px.bar(
        top_styles,
        x='extended_cost',
        y=y_code,
        orientation='h',
        title='Top Styles by Inventory Value',
        labels={'extended_cost': 'Extended Cost ($)', y_code: 'Style Code'},
        hover_data=[c for c in ['total_inv'] if c in top_styles.columns]
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis_tickformat=',.0f')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Need `style_cd` and `extended_cost` to show top styles.")

# ---------------- Inventory Health ----------------
stock_qty_col = 'total_inv' if 'total_inv' in df_filtered.columns else None

st.subheader("⚡ Potential Stockouts (High Opportunity)")
if stock_qty_col and "sales_qty" in df_filtered.columns:
    stockouts = df_filtered[(df_filtered[stock_qty_col] <= 3) & (df_filtered['sales_qty'] >= 5)]
    stockouts_sorted = stockouts.sort_values(by="sales_qty", ascending=False)
    cols = [c for c in ['style_cd','style_category','sales_qty','sales_amt',
                        stock_qty_col,'avg_unit_cost','avg_unit_price','extended_cost']
            if c in stockouts_sorted.columns]
    st.dataframe(stockouts_sorted[cols])
else:
    st.info("Need `total_inv` and `sales_qty` for stockout analysis.")

st.subheader("❄️ Deadweight Styles (High Inventory, Low Sales)")
if stock_qty_col and "sales_qty" in df_filtered.columns:
    deadweight = df_filtered[(df_filtered[stock_qty_col] >= 5) & (df_filtered['sales_qty'] <= 1)]
    deadweight_sorted = deadweight.sort_values(by=stock_qty_col, ascending=False)
    cols = [c for c in ['style_cd','style_category','sales_qty',stock_qty_col,
                        'avg_unit_cost','avg_unit_price','extended_cost']
            if c in deadweight_sorted.columns]
    st.dataframe(deadweight_sorted[cols])
else:
    st.info("Need `total_inv` and `sales_qty` for deadweight analysis.")

# ---------------- Download ----------------
st.subheader("⬇️ Download Customer Data")
st.download_button(
    label="Download Filtered Customer CSV",
    data=df_filtered.to_csv(index=False),
    file_name=f'{customer_selected}_filtered_data.csv',
    mime='text/csv'
)
