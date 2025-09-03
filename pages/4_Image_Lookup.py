import streamlit as st
import pandas as pd
import requests
import inspect
import numpy as np

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
def load_local_metadata():
    # Fallback to local CSV for testing
    csv_path = st.secrets.get("LOCAL_METADATA_PATH", "final_tagged_with_metadata_v2.csv")
    return pd.read_csv(csv_path)

try:
    use_local_meta = st.secrets.get("USE_LOCAL_METADATA_DATA", False)
    df = load_local_metadata() if use_local_meta else load_metadata()
except Exception as e:
    st.error("❌ Failed to load metadata.")
    st.text(f"Error: {e}")


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

shape_tokens = (
    df["diamond_shapes"]
    .dropna()
    .str.split(",")
    .explode()
    .str.strip()
    .dropna()
    .unique()
)
shape_tokens = sorted(shape_tokens)

ring_type = ""
earring_type = ""
hoop_subtype = ""
chain_type = ""

gender = st.sidebar.selectbox("Gender", [""] + sorted(df["gender"].dropna().unique()))
style_category = st.sidebar.multiselect("Style Category", [""] + sorted(df["style_category"].dropna().unique()))
collection = st.sidebar.selectbox("Collection", [""] + sorted(df["collection"].dropna().unique()))
metal_color = st.sidebar.multiselect("Metal Color",[""] + list(metal_color_map.keys()))
center_stone_shape = st.sidebar.selectbox("Center Stone Shape", [""] + sorted(df["center_stone_shape"].dropna().unique()))

selected_shapes = st.sidebar.multiselect("Diamond Shapes", shape_tokens)
shape_mode = st.sidebar.radio("Match Mode for Diamond Shapes", ["Any (OR)", "All (AND)"], index=0)
# Prepare a tokenized column (cached in-memory) for accurate matching
if "_shape_set" not in df.columns:
    df["_shape_set"] = (
        df["diamond_shapes"]
        .fillna("")
        .apply(lambda s: set(t.strip() for t in s.split(",") if t.strip()))
    )

diamond_type = st.sidebar.selectbox("Diamond Type", [""] + sorted(df["diamond_type"].dropna().unique()))

# Safeguards 
df["diamond_qty"] = pd.to_numeric(df["diamond_qty"], errors="coerce")
df["diamond_wt"] = pd.to_numeric(df["diamond_wt"], errors="coerce")

for col in ["diamond_qty", "diamond_wt"]:
    if col not in df.columns:
        df[col] = np.nan

# Compute UX-friendly ranges (95th percentile) and hard maxima
qty_p95 = int(df["diamond_qty"].quantile(0.95)) if df["diamond_qty"].notna().any() else 0
qty_hard_max = int(df["diamond_qty"].max()) if df["diamond_qty"].notna().any() else 0

wt_p95 = float(df["diamond_wt"].quantile(0.95)) if df["diamond_wt"].notna().any() else 0.0
wt_hard_max = float(df["diamond_wt"].max()) if df["diamond_wt"].notna().any() else 0.0

# track when the advanced checkbox toggles, so we can reset defaults cleanly
def toggled(key, default=False):
    prev_key = f"__prev_{key}"
    prev = st.session_state.get(prev_key, default)
    cur = st.session_state.get(key, default)
    st.session_state[prev_key] = cur
    return cur != prev

with st.sidebar.expander("💎 Diamond Filters", expanded=False):
    # ---- Slider (P95) ----
    qty_range = st.slider(
        "Diamond Quantity (common range)",
        min_value=0, max_value=max(int(qty_p95), 1),
        value=(0, max(int(qty_p95), 1)), step=1, key="qty_slider"
    )

    use_qty_manual = st.checkbox("Advanced: include outliers (custom min/max)", key="qty_adv")
    if use_qty_manual:
        hard_max_qty = int(qty_hard_max)

        # On toggle ON, initialize manual inputs to full hard bounds
        if toggled("qty_adv", default=False):
            st.session_state["qty_min_manual_val"] = 0
            st.session_state["qty_max_manual_val"] = hard_max_qty

        c1, c2 = st.columns(2)
        with c1:
            qty_min_manual = st.number_input(
                "Min qty",
                min_value=0,
                max_value=hard_max_qty,
                value=st.session_state.get("qty_min_manual_val", 0),
                step=1,
                key=f"qty_min_manual_{hard_max_qty}",
            )
        with c2:
            qty_max_manual = st.number_input(
                "Max qty",
                min_value=int(qty_min_manual),
                max_value=hard_max_qty,
                value=st.session_state.get("qty_max_manual_val", hard_max_qty),
                step=1,
                key=f"qty_max_manual_{hard_max_qty}",
            )

        # persist current manual values
        st.session_state["qty_min_manual_val"] = int(qty_min_manual)
        st.session_state["qty_max_manual_val"] = int(qty_max_manual)

        qty_min, qty_max = int(qty_min_manual), int(qty_max_manual)
    else:
        qty_min, qty_max = int(qty_range[0]), int(qty_range[1])

    # ---------- Weight ----------
    wt_range = st.slider(
        "Diamond Weight (ct, common range)",
        min_value=0.0,
        max_value=float(round(max(wt_p95, 0.01), 2)),
        value=(0.0, float(round(max(wt_p95, 0.01), 2))),
        step=0.01,
        format="%.2f",
        key="wt_slider"
    )

    use_wt_manual = st.checkbox("Advanced: include outliers (custom min/max)", key="wt_adv")
    if use_wt_manual:
        hard_max_wt = float(wt_hard_max)

        if toggled("wt_adv", default=False):
            st.session_state["wt_min_manual_val"] = 0.0
            st.session_state["wt_max_manual_val"] = hard_max_wt

        c3, c4 = st.columns(2)
        with c3:
            wt_min_manual = st.number_input(
                "Min ct",
                min_value=0.0,
                max_value=hard_max_wt,
                value=st.session_state.get("wt_min_manual_val", 0.0),
                step=0.001,
                format="%.3f",
                key=f"wt_min_manual_{int(hard_max_wt*1000)}",
            )
        with c4:
            wt_max_manual = st.number_input(
                "Max ct",
                min_value=float(wt_min_manual),
                max_value=hard_max_wt,
                value=st.session_state.get("wt_max_manual_val", hard_max_wt),
                step=0.001,
                format="%.3f",
                key=f"wt_max_manual_{int(hard_max_wt*1000)}",
            )

        st.session_state["wt_min_manual_val"] = float(wt_min_manual)
        st.session_state["wt_max_manual_val"] = float(wt_max_manual)

        wt_min, wt_max = float(wt_min_manual), float(wt_max_manual)
    else:
        wt_min, wt_max = float(wt_range[0]), float(wt_range[1])

#st.sidebar.caption(f"P95 qty={qty_p95}, MAX qty={qty_hard_max} | P95 wt={wt_p95:.3f}, MAX wt={wt_hard_max:.3f}")

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


# ==== Apply filters ====
# (Fill NaNs to be inclusive of lower bounds)
filtered_df = filtered_df[
    filtered_df["diamond_qty"].fillna(0).between(qty_min, qty_max)
]
filtered_df = filtered_df[
    filtered_df["diamond_wt"].fillna(0.0).between(wt_min, wt_max)
]
if gender:
    filtered_df = filtered_df[filtered_df["gender"] == gender]
if style_category:
    filtered_df = filtered_df[filtered_df["style_category"].isin(style_category)]

if collection:
    filtered_df = filtered_df[filtered_df["collection"] == collection]

if metal_color:
    selected_codes = [metal_color_map[color] for color in metal_color]
    filtered_df = filtered_df[filtered_df["metal_color"].isin(selected_codes)]

if center_stone_shape:
    filtered_df = filtered_df[filtered_df["center_stone_shape"] == center_stone_shape]

if selected_shapes:
    sel_set = set(selected_shapes)
    if shape_mode == "Any (OR)":
        mask = df["_shape_set"].apply(lambda s: bool(s & sel_set))      # intersection non-empty
    else:  # "All (AND)"
        mask = df["_shape_set"].apply(lambda s: sel_set.issubset(s))    # all selected present
    filtered_df = df[mask]

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
        "center_stone_shape": "first",
        "diamond_shapes": lambda x: list(set(x.dropna())),
        "metal_color": lambda x: list(set(x.dropna())),
        "center_setting": "first",
        "side_setting": "first",
        "combined_text": "first",
        "ring_type": "first",
        "earring_type": "first",
        "diamond_type": "first",
        "diamond_wt": "first"
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
                        "center_stone_shape": to_slash(row['center_stone_shape']),
                        "metal_color": to_slash(row['metal_color']),
                        "combined_text": row.get("combined_text", ""),
                        "ring_type": to_slash(row.get('ring_type', '')),
                        "earring_type": to_slash(row.get('earring_type', '')),
                        "center_stone_shape": to_slash(row.get('center_stone_shape', '')),
                        "diamond_type": to_slash(row.get('diamond_type', ''))
                    })
                    st.success(f"Added {style_key} to cart.")
                    st.rerun()

            st.markdown("**Styles:**<br>" + to_multiline(row["style_cd"]), unsafe_allow_html=True)
            st.caption(f"{to_slash(row['style_category'])} | {to_slash(row['center_stone_shape'])} | {to_slash(row['diamond_wt'])} | {to_slash(row['metal_color'])}")
else:
    st.warning(f"No results found. Try a different search.")