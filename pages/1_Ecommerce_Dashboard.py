import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import requests
import plotly.express as px

st.set_page_config(
    page_title="Ecommerce Dashboard",
    page_icon="📦",
    layout="wide"
)

@st.cache_data
def load_updated():
    IP = st.secrets["IP"]
    url = f"http://{IP}/api/updated"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

# Load the merged cleaned dataset (AFTER truth inventory merge)
try:
    df_master = load_updated()
except Exception as e:
    st.error("❌ Failed to load updated data.")
    st.text(f"Error: {e}")

# Sidebar - Customer selection
customer_names = {
    'A058': 'AAFES',
    'JC002': 'JCPenney',
    'K029': 'Kohls',
    'MA001': 'Macys',
    'QV001': 'QVC',
    'R2002': 'BlueNile - R2NET',
    'STERLING': 'Kay-Jared-Outlet',
    'Z011': 'Zales'
}

customer_codes = list(customer_names.keys())
customer_selected = st.sidebar.selectbox('Select Customer', customer_codes)

# Filter DataFrame
df_filtered = df_master[df_master['Customer'] == customer_selected]

# ---------------- KPIs ----------------
st.title(f"{customer_names[customer_selected]} Dashboard")

col1, col2, col3 = st.columns(3)
col1.metric("Total Sales", f"${df_filtered['sales_amt'].sum():,.0f}")
col2.metric("Units Sold", f"{df_filtered['sales_qty'].sum():,.0f}")
col3.metric("Profit", f"{df_filtered['profit'].sum():,.0f}%")

# --- Visualization 1: Performance by Style Category
st.subheader("Performance by Style Category")

category_summary = df_filtered.groupby(['style_category', 'Performance_Category']).size().unstack(fill_value=0)

fig1 = px.bar(
    category_summary.reset_index(),
    x='style_category',
    y=category_summary.columns.tolist(),
    title=f"{customer_names[customer_selected]} Performance by Style Category",
    labels={'value': 'Number of Styles', 'style_category': 'Style Category'},
)

fig1.update_layout(barmode='stack', height=500)
st.plotly_chart(fig1, use_container_width=True)


# --- Visualization 2: Overall Style Performance
st.subheader("Overall Style Performance")

category_counts = df_filtered['Performance_Category'].value_counts().sort_values(ascending=True)

fig2 = px.bar(
    category_counts.reset_index(),
    x='index',
    y='Performance_Category',
    title=f"{customer_names[customer_selected]} Overall Style Performance",
    labels={'index': 'Performance Category', 'Performance_Category': 'Number of Styles'},
)

fig2.update_layout(height=450)
st.plotly_chart(fig2, use_container_width=True)


# ---------------- Inventory Health ----------------

# ⚡ Potential Stockouts (based on real OnHand)
st.subheader("⚡ Potential Stockouts (High Opportunity)")

stockouts = df_filtered[
    (df_filtered['onhand'] <= 3) & (df_filtered['sales_qty'] >= 5)
]

st.dataframe(stockouts[['Item_id', 'style_category', 'sales_qty', 'onhand']])

# ❄️ Deadweight Inventory (using real OnHand)
st.subheader("❄️ Deadweight Styles (High Inventory, Low Sales)")

deadweight = df_filtered[
    (df_filtered['onhand'] >= 5) & (df_filtered['sales_qty'] <= 1)
]

st.dataframe(deadweight[['Item_id', 'style_category', 'sales_qty', 'onhand']])

# 🚨 Inventory Discrepancy Check
#st.subheader("🚨 Inventory Discrepancy Check (Internal vs True)")

# Add inventory difference calculation
#df_filtered['Inventory_Difference'] = df_filtered['Total_Qty'] - df_filtered['onhand']

#discrepancies = df_filtered[df_filtered['Inventory_Difference'].abs() >= 3]

#st.dataframe(discrepancies[['Item_id', 'style_category', 'Total_Qty', 'onhand', 'Inventory_Difference']])

# --- BONUS: Download Button
st.subheader("⬇️ Download Customer Data")

st.download_button(
    label="Download Filtered Customer CSV",
    data=df_filtered.to_csv(index=False),
    file_name=f'{customer_selected}_filtered_data.csv',
    mime='text/csv'
)
