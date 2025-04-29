import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Page config
st.set_page_config(page_title="Slow Moving Memo Analysis", layout="wide")

# Title
st.title("🪙 Slow Moving Memo Analysis (2024–2025)")

# Load cleaned dataset
@st.cache_data
def load_data():
    return pd.read_csv("Cleaned_SlowMemo_2024_2025.csv")

df = load_data()

# Sidebar filters
st.sidebar.header("Filters")
ae_selected = st.sidebar.multiselect('Account Executive(s)', options=df['AE'].unique())
customer_selected = st.sidebar.multiselect('Customer(s)', options=df['Customer'].unique())

if ae_selected:
    df = df[df['AE'].isin(ae_selected)]
if customer_selected:
    df = df[df['Customer'].isin(customer_selected)]

# KPIs
st.subheader("🔢 Key Metrics")
total_styles = len(df)
dead_weight = (df['Performance_Category'] == 'Dead Weight').sum()
slow_movers = (df['Performance_Category'] == 'Slow Mover').sum()
strong_sellers = (df['Performance_Category'] == 'Strong Seller').sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Styles", f"{total_styles:,}")
col2.metric("Dead Weight", f"{dead_weight:,}")
col3.metric("Slow Movers", f"{slow_movers:,}")
col4.metric("Strong Sellers", f"{strong_sellers:,}")

# Category breakdown chart
st.subheader("📊 Performance Category Breakdown")
category_counts = df['Performance_Category'].value_counts()
fig, ax = plt.subplots()
category_counts.plot(kind='barh', ax=ax, color=['#d62728', '#ff7f0e', '#1f77b4', '#2ca02c'])
ax.set_xlabel("Number of Styles")
ax.set_ylabel("Category")
ax.set_title("Performance Distribution")
st.pyplot(fig)

# Worst memo items
st.subheader("💀 Top 10 Worst Memo Styles (by $ value)")
worst_memos = df[df['Performance_Category'].isin(['Dead Weight', 'Slow Mover'])] \
    .sort_values(by='Open_Memo_Amt', ascending=False) \
    .head(10)

st.dataframe(
    worst_memos[[
        'AE', 'Customer', 'Style', 'Style Description', 'Performance_Category',
        'Open_Memo_Qty', 'Open_Memo_Amt', 'Net_Sales_2025_YTD', 'Expected_Sales_6mo'
    ]]
)

# Optional: export
st.download_button(
    label="📥 Download Full Dataset (CSV)",
    data=df.to_csv(index=False),
    file_name="Full_SlowMemo_Analysis.csv",
    mime="text/csv"
)
