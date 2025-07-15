import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.datavalidation import DataValidation

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

def load_local():
    # Fallback to local CSV if API fails
    return pd.read_csv("Cleaned_SlowMemo_July2025_v4.csv")

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

# Filter: Performance Category
performance_selected = st.sidebar.multiselect("Performance Category", df["Performance_Category"].unique())
if performance_selected:
    df = df[df["Performance_Category"].isin(performance_selected)]

st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# === KPI Display ===
st.subheader("🔢 Key Metrics")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Styles", f"{len(df):,}")
col2.metric("Dead Weight", f"{(df['Performance_Category'] == 'Dead Weight').sum():,}")
col3.metric("Slow Movers", f"{(df['Performance_Category'] == 'Slow Mover').sum():,}")
col4.metric("Strong Sellers", f"{(df['Performance_Category'] == 'Strong Seller').sum():,}")
col5.metric("Review", f"{(df['Performance_Category'] == 'Review').sum():,}")

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
        "AE", "Customer", "Metal Kt", "Style", "Style Description", "Inception Dt.",
        "Performance_Category", "Open_Memo_Qty", "Open_Memo_Amt",
        "Net_Sales_2025_YTD", "Expected_Sales_6mo"
    ]].style.format({
        "Open_Memo_Qty": "{:,}",
        "Open_Memo_Amt": "${:,.2f}",
        "Net_Sales_2025_YTD": "${:,.2f}",
        "Expected_Sales_6mo": "${:,}"
    })
)

# === Use your filtered DataFrame here
df_filtered = df_sorted.copy()

# === Insert new columns
new_columns = ['Date_RA_Issued', 'Disposition', 'Comments']
insert_after = 'RA_Issued'
if insert_after in df_filtered.columns:
    insert_loc = df_filtered.columns.get_loc(insert_after) + 1
    for i, col in enumerate(new_columns):
        df_filtered.insert(insert_loc + i, col, "")
else:
    for col in new_columns:
        df_filtered[col] = ""

# === Create Excel workbook
wb = Workbook()
ws = wb.active
ws.title = "SlowMemoExport"

# Write DataFrame to worksheet
for r in dataframe_to_rows(df_filtered, index=False, header=True):
    ws.append(r)

# === Add dropdown data validation for Disposition column
disp_col_idx = df_filtered.columns.get_loc('Disposition') + 1  # 1-based indexing
disp_col_letter = ws.cell(row=1, column=disp_col_idx).column_letter
dropdown_range = f"{disp_col_letter}2:{disp_col_letter}{len(df_filtered)+1}"
dv = DataValidation(
    type="list",
    formula1='"Perpetual memo,Hold on memo/Monitor,RTV - Closeout,RTV- Melt,Other"',
    allow_blank=True,
)
ws.add_data_validation(dv)
dv.add(dropdown_range)

# === Save to BytesIO buffer
excel_buffer = BytesIO()
wb.save(excel_buffer)
excel_buffer.seek(0)

# === Streamlit download button
st.download_button(
    label="📥 Download as Excel with Dropdowns",
    data=excel_buffer,
    file_name="Filtered_SlowMemo_With_Dropdown.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Optional: CSV download
#st.download_button(
 #   label="📥 Download Filtered Dataset",
  #  data=df_sorted.to_csv(index=False),
   # file_name="Filtered_SlowMemo.csv",
   # mime="text/csv"
#)