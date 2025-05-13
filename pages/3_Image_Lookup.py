import streamlit as st
import pandas as pd
import requests

st.set_page_config(
    page_title="Image Lookup",
    page_icon="🔎",
    layout="wide"
)

st.title("🔎 Image Lookup")

# === Load Data ===
@st.cache_data
def load_metadata():
    url = "https://api.anerijewels.com/api/metadata_1_8"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

df = load_metadata()

# === Search Bar ===
search_query = st.text_input("Search by Style Number or Description")

# === Sidebar Filters ===
st.sidebar.header("🔧 Filters")

style_category = st.sidebar.selectbox("Style Category", [""] + sorted(df["style_category"].dropna().unique()))
collection = st.sidebar.selectbox("Collection", [""] + sorted(df["collection"].dropna().unique()))
metal_color = st.sidebar.selectbox("Metal Color", [""] + sorted(df["metal_color"].dropna().unique()))
cstone_shape = st.sidebar.selectbox("Center Stone Shape", [""] + sorted(df["cstone_shape"].dropna().unique()))

# === Filter Logic ===
filtered_df = df.copy()

if search_query:
    search_query_upper = search_query.upper()
    filtered_df = filtered_df[
        filtered_df["style_cd"].str.contains(search_query_upper, na=False) |
        filtered_df["style_description"].str.contains(search_query_upper, na=False) |
        filtered_df["tag_line1"].str.contains(search_query_upper, na=False)
    ]

if style_category:
    filtered_df = filtered_df[filtered_df["style_category"] == style_category]

if collection:
    filtered_df = filtered_df[filtered_df["collection"] == collection]

if metal_color:
    filtered_df = filtered_df[filtered_df["metal_color"] == metal_color]

if cstone_shape:
    filtered_df = filtered_df[filtered_df["cstone_shape"] == cstone_shape]

# === Results ===
st.write(f"**Found {len(filtered_df)} matching items**")

# Pagination controls
PAGE_SIZE = 24
total_pages = (len(filtered_df) - 1) // PAGE_SIZE + 1
page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

start_idx = (page_num - 1) * PAGE_SIZE
end_idx = start_idx + PAGE_SIZE
page_df = filtered_df.iloc[start_idx:end_idx]

if filtered_df.empty:
    st.warning("No matching styles found. Try adjusting your search or filters.")
else:
    cols = st.columns(4)
    for i, (_, row) in enumerate(page_df.iterrows()):
        with cols[i % 4]:
            st.image(row["full_path"], use_column_width=True)
            st.markdown(f"**{row['style_cd']}**")
            st.caption(f"{row.get('style_category', '')} | {row.get('cstone_shape', '')} | {row.get('metal_color', '')}")
