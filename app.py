import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Load the master cleaned dataset
df_master = pd.read_csv('Complete_Cleaned_Ecomm.csv')

# Sidebar - Customer selection
customer_names = {
    'A058': 'AAFES',
    'JC002': 'JCPenney',
    'K029': 'Kohls',
    'MA001': 'Macys',
    'QV001': 'QVC',
    'STERLING': 'Kay-Jared-Outlet',
    'Z011': 'Zales'
}

customer_codes = list(customer_names.keys())
customer_selected = st.sidebar.selectbox('Select Customer', customer_codes)

# Filtered DataFrame
df_filtered = df_master[df_master['Customer'] == customer_selected]

# KPIs
st.title(f"{customer_names[customer_selected]} Dashboard")

col1, col2, col3 = st.columns(3)
col1.metric("Total Sales", f"${df_filtered['sales_amt'].sum():,.0f}")
col2.metric("Units Sold", f"{df_filtered['sales_qty'].sum():,.0f}")
col3.metric("Profit", f"{df_filtered['profit'].sum():,.0f}",'%')

# Visualization Section 1: Performance by Style Category
st.subheader("Performance by Style Category")

category_summary = df_filtered.groupby(['style_category', 'Performance_Category']).size().unstack(fill_value=0)

fig1, ax1 = plt.subplots(figsize=(12, 6))
category_summary.plot(kind='bar', stacked=True, ax=ax1)
ax1.set_title(f"{customer_names[customer_selected]} Performance by Style Category")
ax1.set_ylabel("Number of Styles")
ax1.set_xlabel("Style Category")
ax1.grid(axis='y', linestyle='--', linewidth=0.5, alpha=0.7)
st.pyplot(fig1)

# Visualization Section 2: Overall Performance
st.subheader("Overall Style Performance")

category_counts = df_filtered['Performance_Category'].value_counts().sort_values(ascending=True)

fig2, ax2 = plt.subplots(figsize=(8, 5))
category_counts.plot(kind='bar', ax=ax2, color='teal')
ax2.set_title(f"{customer_names[customer_selected]} Overall Style Performance")
ax2.set_ylabel("Number of Styles")
ax2.set_xlabel("Performance Category")
ax2.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)
st.pyplot(fig2)
