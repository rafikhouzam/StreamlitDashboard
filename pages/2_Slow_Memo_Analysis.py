import streamlit as st
import pandas as pd
import requests

# Page config

st.set_page_config(
    page_title="Slow Moving Memo",
    page_icon="🪙",
    layout="wide"
)
st.title("🪙 Slow Moving Memo Analysis (2024–2025)")

# Load dataset
@st.cache_data
def load_memo():
    url = f"https://api.anerijewels.com/api/memo"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

try:
    df = load_memo()
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

st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# === KPI Display ===
st.subheader("🔢 Key Metrics")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Styles", f"{len(df):,}")
col2.metric("Dead Weight", f"{(df['Performance_Category'] == 'Dead Weight').sum():,}")
col3.metric("Slow Movers", f"{(df['Performance_Category'] == 'Slow Mover').sum():,}")
col4.metric("Strong Sellers", f"{(df['Performance_Category'] == 'Strong Seller').sum():,}")

# === Display Sorted Table ===
st.subheader("📋 Detailed Memo Table (Sorted)")

sort_columns = {
    "Open Memo Qty": "Open_Memo_Qty",
    "Open Memo Amt ($)": "Open_Memo_Amt",
    "Net Sales 2025 YTD ($)": "Net_Sales_2025_YTD"
}

# 🚀 Real pill-style selection
sort_display = st.radio(
    "Sort by Column:",
    options=list(sort_columns.keys()),
    index=0,
    horizontal=True,
)

# Map the display label back to the real column
sort_column = sort_columns[sort_display]

# 🔃 Order selector (still native radio for now)
sort_order = st.radio(
    "Order:",
    options=["Descending", "Ascending"],
    index=0,
    horizontal=True,
)
ascending = sort_order == "Ascending"

# Sort and display
df_sorted = df.sort_values(by=sort_column, ascending=ascending)

# Display top rows
st.dataframe(
    df_sorted[[
        "AE", "Customer", "Metal Kt", "Style", "Style Description",
        "Performance_Category", "Open_Memo_Qty", "Open_Memo_Amt",
        "Net_Sales_2025_YTD", "Expected_Sales_6mo"
    ]].style.format({
        "Open_Memo_Qty": "{:,}",
        "Open_Memo_Amt": "${:,.2f}",
        "Net_Sales_2025_YTD": "${:,.2f}",
        "Expected_Sales_6mo": "{:,}"
    })
)

# Optional: CSV download
st.download_button(
    label="📥 Download Filtered Dataset",
    data=df_sorted.to_csv(index=False),
    file_name="Filtered_SlowMemo.csv",
    mime="text/csv"
)
