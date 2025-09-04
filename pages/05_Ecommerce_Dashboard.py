# Ecommerce Streamlit Dashboard

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
def load_api():
    url = f"https://api.anerijewels.com/api/updated"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

@st.cache_data
def load_local():
    df = pd.read_csv('ecomm_extended_cost_fixed.csv')
    return df

try:
    df_master = load_api()
except Exception as e:
    st.error("❌ Failed to load Ecomm data.")
    st.text(f"Error: {e}")

# Sidebar - Customer selection
customer_names = {
    'A058': 'AAFES',
    'JC002': 'JCPenney',
    'K029': 'Kohls',
    'MA001': 'Macys',
    'QV001': 'QVC',
    'R2002': 'BlueNile - R2NET',
    'KA002': 'Kay-Jared-Outlet',
    'ST001': 'Kay-Jared-Outlet',
    'ST004': 'Kay-Jared-Outlet',
    'Z011': 'Zales'
}

customer_groups = {
    'AAFES': ['A058'],
    'JCPenney': ['JC002'],
    'Kohl’s': ['K029'],
    'Macy’s': ['MA001'],
    'QVC': ['QV001'],
    'BlueNile - R2NET': ['R2002'],
    'Kay/Jared/Outlet': ['KA002', 'ST001', 'ST004'],
    'Zales': ['Z011']
}

customer_codes = list(customer_names.keys())
customer_selected = st.sidebar.selectbox('Select Customer', customer_codes)

st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# Filter DataFrame
df_filtered = df_master[df_master['customer_id'] == customer_selected]

df_filtered = df_filtered.drop_duplicates()

# Calculate Profit Margin
total_profit = df_filtered["profit"].sum()
total_sales = df_filtered["sales_amt"].sum()
profit_pct = total_profit / total_sales * 100 if total_sales > 0 else 0

# KPIs
st.title(f"{customer_names[customer_selected]} Dashboard (1/1/2023 - 6/9/2025)")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Sales", f"${df_filtered['sales_amt'].sum():,.0f}")
col2.metric("Units Sold", f"{df_filtered['sales_qty'].sum():,.0f}")
col3.metric("Profit Margin", f"{profit_pct:.1f}%")
col4.metric("Inventory Value", f"${df_filtered['extended_cost'].sum():,.0f}")

# Visualization 1: Performance by Style Category
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

# Visualization 2: Overall Style Performance
st.subheader("Overall Style Performance")

category_counts = df_filtered['Performance_Category'].value_counts().sort_values(ascending=True)
df_bar = category_counts.reset_index()
df_bar.columns = ['Performance Category', 'Number of Styles']

fig2 = px.bar(
    df_bar,
    x='Performance Category',
    y='Number of Styles',
    labels={'Performance Category': 'Performance Category', 'Number of Styles': 'Number of Styles'},
    title=f"{customer_names[customer_selected]} Overall Style Performance",
    color_discrete_sequence=['teal']
)

fig2.update_layout(
 #   plot_bgcolor='white',
  #  xaxis=dict(showgrid=True, gridcolor='lightgray'),
    xaxis=dict(showgrid=True)
)

st.plotly_chart(fig2, use_container_width=True)

#Visualization 3: Extended Cost Pie Chart by Category
st.subheader("Extended Cost by Style Category")
category_costs = (
    df_filtered[df_filtered['extended_cost'].notna()]
    .groupby('style_category')['extended_cost']
    .sum()
    .reset_index()
    .sort_values(by='extended_cost', ascending=False)
)

fig_pie = px.pie(
    category_costs,
    names='style_category',
    values='extended_cost',
    title='Share of Inventory Value by Category'
)
st.plotly_chart(fig_pie)

# Visualization 4: Top 50 Styles by Inventory Value
top_styles = (
    df_filtered[df_filtered['extended_cost'].notna()]
    .sort_values(by='extended_cost', ascending=False)
    .head(50)
)

fig = px.bar(
    top_styles,
    x='extended_cost',
    y='style_cd',
    orientation='h',
    title='Top Styles by Inventory Value',
    labels={'extended_cost': 'Extended Cost ($)', 'style_cd': 'Style Code'},
    hover_data=['Total_Qty']
)

fig.update_layout(
    yaxis=dict(autorange="reversed"),  # ensures highest value at the top
    xaxis_tickformat=',.0f'  # use ',.0s' for '5k', '10k' format instead
)

st.plotly_chart(fig)


# Inventory Health
st.subheader("⚡ Potential Stockouts (High Opportunity)")
stockouts = df_filtered[(df_filtered['Total_Qty'] <= 3) & (df_filtered['sales_qty'] >= 5)]
stockouts_sorted = stockouts.sort_values(by="sales_qty", ascending=False)
st.dataframe(stockouts_sorted[['style_cd', 'style_category', 'sales_qty',  'sales_amt', 'Total_Qty', 'avg_unit_cost', 'avg_unit_price', 'extended_cost']])

st.subheader("❄️ Deadweight Styles (High Inventory, Low Sales)")
deadweight = df_filtered[(df_filtered['Total_Qty'] >= 5) & (df_filtered['sales_qty'] <= 1)]
deadweight_sorted = deadweight.sort_values(by="Total_Qty", ascending=False)
st.dataframe(deadweight_sorted[['style_cd', 'style_category', 'sales_qty','Total_Qty', 'avg_unit_cost', 'avg_unit_price', 'extended_cost']])

# Download
st.subheader("⬇️ Download Customer Data")
st.download_button(
    label="Download Filtered Customer CSV",
    data=df_filtered.to_csv(index=False),
    file_name=f'{customer_selected}_filtered_data.csv',
    mime='text/csv'
)
