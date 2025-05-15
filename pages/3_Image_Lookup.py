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
    url = "https://api.anerijewels.com/api/metadata"
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

# === Step 1: Apply search and filters ===
filtered_df = df.copy()

if search_query:
    q = search_query.upper()
    filtered_df = filtered_df[
        filtered_df["combined_text"].str.contains(q, na=False)
    ]

if style_category:
    filtered_df = filtered_df[filtered_df["style_category"] == style_category]

if collection:
    filtered_df = filtered_df[filtered_df["collection"] == collection]

if metal_color:
    filtered_df = filtered_df[filtered_df["metal_color"] == metal_color]

if cstone_shape:
    filtered_df = filtered_df[filtered_df["cstone_shape"] == cstone_shape]

# === Step 2: Drop rows with bad image_url only
filtered_df = filtered_df[
    filtered_df["image_url"].notna() &
    filtered_df["image_url"].astype(str).str.strip().ne("")
]

# === Clean up invalid or blank visual_ids
filtered_df["visual_id"] = filtered_df["visual_id"].astype(str).str.strip()
filtered_df.loc[filtered_df["visual_id"] == "", "visual_id"] = pd.NA


# === Step 3: Group SUMIT rows by visual_id, keep SAMPL rows as-is
has_visual = (filtered_df['source'] != 'SAMPL')  # True only for SUMIT rows

grouped_sumit = (
    filtered_df[has_visual]
    .groupby("visual_id")
    .agg({
        "image_url": "first",
        "style_cd": lambda x: list(x),
        "style_category": lambda x: list(set(x.dropna())),
        "cstone_shape": lambda x: list(set(x.dropna())),
        "metal_color": lambda x: list(set(x.dropna()))
    })
    .reset_index()
)

# Treat SAMPL rows as their own groups
grouped_sampl = (
    filtered_df[~has_visual]
    .assign(visual_id=lambda df: df["style_cd"])  # overwrite fallback
    .groupby("visual_id")
    .agg({
        "image_url": "first",
        "style_cd": lambda x: list(x),
        "style_category": lambda x: list(set(x.dropna())),
        "cstone_shape": lambda x: list(set(x.dropna())),
        "metal_color": lambda x: list(set(x.dropna()))
    })
    .reset_index()
)

grouped_df = pd.concat([grouped_sumit, grouped_sampl], ignore_index=True)



# === Step 4: Pagination
PAGE_SIZE = 24
total_pages = (len(grouped_df) - 1) // PAGE_SIZE + 1
page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
start_idx = (page_num - 1) * PAGE_SIZE
end_idx = start_idx + PAGE_SIZE
page_df = grouped_df.iloc[start_idx:end_idx]

# === Step 5: Display results
st.write(f"**Found {len(grouped_df)} matching visuals**")
cols = st.columns(4)
for i, row in page_df.iterrows():
    with cols[i % 4]:
        st.image(row["image_url"], use_container_width=True)
        st.markdown("**Styles:**<br>" + "<br>".join(row["style_cd"]), unsafe_allow_html=True)
        st.caption(f"{' / '.join(row['style_category'])} | {' / '.join(row['cstone_shape'])} | {' / '.join(row['metal_color'])}")
