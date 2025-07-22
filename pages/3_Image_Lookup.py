import streamlit as st
import pandas as pd
import requests
import inspect

st.set_page_config(
    page_title="Image Lookup",
    page_icon="🔎",
    layout="wide"
)

if "image_cart" not in st.session_state:
    st.session_state.image_cart = []

st.title("🔎 Image Lookup")

st.markdown("""
    <style>
    .image-box {
        width: 200px;
        height: 200px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        overflow: hidden;
        margin: auto;
    }

    .image-box img {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
    }
    </style>
""", unsafe_allow_html=True)


# === Load Data ===
@st.cache_data
def load_metadata():
    url = "https://api.anerijewels.com/api/metadata"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

@st.cache_data
def load_local():
    df = pd.read_csv('final_tagged_with_metadata_v2.csv')
    return df

df = load_metadata()

def safe_image(image_url, caption=None, width=250, height=250):
    sig = inspect.signature(st.image).parameters
    if "use_container_width" in sig:
        st.image(image_url, caption=caption, use_container_width=True)
    elif "use_column_width" in sig:
        st.image(image_url, caption=caption, use_column_width=True)
    else:
        st.image(image_url, caption=caption, width=width, height=height)

# === Search Bar ===
search_query = st.text_input("Search by Style Number or Description")

# === Sidebar Filters ===
st.sidebar.header("🔧 Filters")

metal_color_map = {
    "White": "W",
    "Yellow": "Y",
    "Yellow Vermeil": "YV",
    "Pink": "P",
    "Pink Vermeil": "PV",
    "Pink White": "PW",
    "Rose Gold": "R",  # Future-proof
    "Two Tone": "T",
    "Tri Color": "3",
    "N": "N"
}

ring_type = ""
earring_type = ""
hoop_subtype = ""
chain_type = ""

style_category = st.sidebar.multiselect("Style Category", [""] + sorted(df["style_category"].dropna().unique()))
collection = st.sidebar.selectbox("Collection", [""] + sorted(df["collection"].dropna().unique()))
metal_color = st.sidebar.multiselect("Metal Color",[""] + list(metal_color_map.keys()))
cstone_shape = st.sidebar.selectbox("Center Stone Shape", [""] + sorted(df["cstone_shape"].dropna().unique()))
diamond_type = st.sidebar.selectbox("Diamond Type", [""] + sorted(df["diamond_type"].dropna().unique()))

# === Conditional sidebar filters based on style_category selection ===
ring_type = []
earring_type = []

if any(cat in style_category for cat in ["NECKLACE", "BRACELET", "ANKLET"]):
    chain_type = st.sidebar.multiselect("Chain Type", [""] + sorted(df["chain_type"].dropna().unique()))

if "RING" in style_category:
    ring_type = st.sidebar.multiselect("Ring Type", sorted(df["ring_type"].dropna().unique()))

if "EARRING" in style_category:
    earring_type = st.sidebar.multiselect("Earring Type", sorted(df["earring_type"].dropna().unique()))

if "Hoop" in earring_type:
    hoop_subtype = st.sidebar.multiselect("Hoop Subtype", [""] + sorted(df["hoop_subtype"].dropna().unique()))

st.sidebar.markdown("### 🛒 Cart")

if st.session_state.image_cart:
    for i, item in enumerate(st.session_state.image_cart):
        st.sidebar.write(f"{item['style_cd']}")
        if st.sidebar.button(f"❌ Remove {item['style_cd']}", key=f"remove_{i}"):
            st.session_state.image_cart.pop(i)
            st.rerun()
    
    # Download cart CSV
    cart_df = pd.DataFrame(st.session_state.image_cart)
    st.sidebar.download_button("📥 Download Cart", cart_df.to_csv(index=False), file_name="cart_items.csv", mime="text/csv")
else:
    st.sidebar.caption("Cart is empty.")


st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# === Step 1: Apply search and filters ===
filtered_df = df.copy()

if search_query:
    q = search_query.upper()
    filtered_df = filtered_df[
        filtered_df["combined_text"].str.contains(q, na=False) |
        filtered_df["style_cd"].str.upper().str.contains(q, na=False)
    ]


if style_category:
    filtered_df = filtered_df[filtered_df["style_category"].isin(style_category)]

if collection:
    filtered_df = filtered_df[filtered_df["collection"] == collection]

if metal_color:
    selected_codes = [metal_color_map[color] for color in metal_color]
    filtered_df = filtered_df[filtered_df["metal_color"].isin(selected_codes)]

if cstone_shape:
    filtered_df = filtered_df[filtered_df["cstone_shape"] == cstone_shape]

if ring_type:
    filtered_df = filtered_df[filtered_df["ring_type"].isin(ring_type)]

if earring_type:
    filtered_df = filtered_df[filtered_df["earring_type"].isin(earring_type)]

if diamond_type:
    filtered_df = filtered_df[filtered_df["diamond_type"] == diamond_type]

if chain_type:
    filtered_df = filtered_df[filtered_df["chain_type"].isin(chain_type)]

if hoop_subtype:
    filtered_df = filtered_df[filtered_df["hoop_subtype"].isin(hoop_subtype)]


# === Step 2: Drop rows with bad image_url only
filtered_df = filtered_df[
    filtered_df["image_url"].notna() &
    filtered_df["image_url"].astype(str).str.strip().ne("")
]

# Group all rows by style_cd and gather all associated images
grouped_df = (
    filtered_df
    .groupby("style_cd")
    .agg({
        "image_url": lambda x: list(x.dropna().unique()),
        "style_category": lambda x: list(set(x.dropna())),
        "cstone_shape": lambda x: list(set(x.dropna())),
        "metal_color": lambda x: list(set(x.dropna())),
        "center_setting": "first",
        "side_setting": "first",
        "combined_text": "first",
        "ring_type": "first",
        "earring_type": "first",
        "diamond_type": "first"
    })
    .reset_index()
)


grouped_df["sort_key"] = grouped_df["style_cd"]
grouped_df = grouped_df.sort_values("sort_key").reset_index(drop=True)

def render_pagination(page_num, total_pages, label):
    return st.number_input(
        label,
        min_value=1,
        max_value=total_pages,
        value=page_num,
        step=1,
        key=label  # unique key to distinguish top and bottom
    )

# === Step 4: Pagination
if len(grouped_df) > 0:
    PAGE_SIZE = 24
    total_pages = (len(grouped_df) - 1) // PAGE_SIZE + 1
    # Top pagination
    page_num = render_pagination(st.session_state.get("page_num", 1), total_pages, "Page")

    # Store in session so bottom control stays in sync
    st.session_state.page_num = page_num
    start_idx = (page_num - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_df = grouped_df.iloc[start_idx:end_idx]

    # === Step 5: Display results
    st.write(f"**Found {len(filtered_df)} matching visuals**")

    def to_multiline(val):
        if isinstance(val, list):
            return "<br>".join(val)
        return val

    def to_slash(val):
        if isinstance(val, list):
            return " / ".join(val)
        return val

    cols = st.columns(4)
    for i, row in page_df.iterrows():
        style_key = row["style_cd"]
        images = row["image_url"]
        session_key = f"carousel_idx_{style_key}"

        # Init index
        if session_key not in st.session_state:
            st.session_state[session_key] = 0

        idx = st.session_state[session_key]

        with cols[i % 4]:
            # === Image
            st.markdown(f'''
                <div class="image-box">
                    <img src="{images[idx]}" alt="Style image">
                </div>
            ''', unsafe_allow_html=True)

            # === Arrow Buttons in 3 Columns (left, center, right)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("◀", key=f"prev_{style_key}"):
                    st.session_state[session_key] = (idx - 1) % len(images)
                    st.rerun()
            with col3:
                if st.button("▶", key=f"next_{style_key}"):
                    st.session_state[session_key] = (idx + 1) % len(images)
                    st.rerun()

            # === Index Indicator and metadata
            st.caption(f"{idx + 1} / {len(images)}")
                        # === Add to Cart button
            if st.button("🛒 Add to Cart", key=f"add_cart_{style_key}"):
                already_in_cart = any(item['style_cd'] == style_key for item in st.session_state.image_cart)
                if not already_in_cart:
                    st.session_state.image_cart.append({
                        "style_cd": style_key,
                        "image_url": images[idx],
                        "style_category": to_slash(row['style_category']),
                        "cstone_shape": to_slash(row['cstone_shape']),
                        "metal_color": to_slash(row['metal_color']),
                        "combined_text": row.get("combined_text", ""),
                        "ring_type": to_slash(row.get('ring_type', '')),
                        "earring_type": to_slash(row.get('earring_type', '')),
                        "cstone_shape": to_slash(row.get('cstone_shape', '')),
                        "diamond_type": to_slash(row.get('diamond_type', ''))
                    })
                    st.success(f"Added {style_key} to cart.")

            st.markdown("**Styles:**<br>" + to_multiline(row["style_cd"]), unsafe_allow_html=True)
            st.caption(f"{to_slash(row['style_category'])} | {to_slash(row['cstone_shape'])} | {to_slash(row['metal_color'])}")
else:
    st.warning(f"No results found. Try a different search.")