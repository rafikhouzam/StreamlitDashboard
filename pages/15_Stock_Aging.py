from __future__ import annotations

import io
import os
import re
import numpy as np
import pandas as pd
import requests
import streamlit as st

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Stock Aging", page_icon="📦", layout="wide")
st.title("📦 Stock Aging Inventory")

@st.cache_data
def load_stock():
    """Load stock aging data from your protected API endpoint (JSON)."""
    url = "https://api.anerijewels.com/api/stock"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers, timeout=30)
    res.raise_for_status()
    return pd.DataFrame(res.json())

def load_stock_local():
    """Fallback to local CSV for testing (path in st.secrets['LOCAL_STOCK_PATH'])."""
    csv_path = st.secrets["LOCAL_STOCK_PATH"]
    return pd.read_csv(csv_path)

try:
    use_local = st.secrets.get("USE_LOCAL_STOCK_DATA", False)
    df_raw = load_stock_local() if use_local else load_stock()
    st.caption(f"Loaded **{len(df_raw):,}** rows from **{'local CSV' if use_local else 'API'}**")
except Exception as e:
    st.error(f"Failed to load stock data: {e}")
    st.stop()

def derive_category_from_description(desc: str) -> str:
    if not isinstance(desc, str):
        return "Unknown"
    d = desc.lower()
    # Order matters; first match wins
    patterns = [
        (r"\b(engagement|bridal)\b", "Engagement"),
        (r"\b(earring|stud|hoop)\b", "Earrings"),
        (r"\b(bracelet|tennis)\b", "Bracelets"),
        (r"\b(bangle)\b", "Bangles"),
        (r"\b(necklace|chain)\b", "Necklaces"),
        (r"\b(pendant|charm)\b", "Pendants"),
        (r"\b(ring)\b", "Rings"),
        (r"\b(anklet)\b", "Anklets"),
        (r"\b(set|box set)\b", "Box Sets"),
    ]
    for pat, label in patterns:
        if re.search(pat, d):
            return label
    return "Other"

def currency(x: float) -> str:
    try:
        return f"${x:,.0f}"
    except Exception:
        return "-"

col_item_id = "item_id"  # note leading space per preview; trim below
col_desc    = "Description"
col_qty     = "Stock"
col_cost    = "Wtd Cost"
col_amt     = "Amount"
col_was_dupe= "was_duplicate"

bucket_cols = ["30-Jan", "30 - 60", "60 - 90", "90 - 180", "> 180"]

# Normalize column names/values
_df = df_raw.copy()
# Strip whitespace from column headers just in case
_df.columns = [c.strip() for c in _df.columns]
# After strip, update names
col_item_id = "item_id"

# Ensure numeric types
for c in [col_qty, col_cost, col_amt] + bucket_cols:
    _df[c] = pd.to_numeric(_df[c], errors="coerce").fillna(0)

# Sanity: if Stock is missing, compute as row-wise sum of bucket cols
if _df[col_qty].isna().all() or (_df[col_qty] == 0).all():
    _df[col_qty] = _df[bucket_cols].sum(axis=1)

# Optional Category derived from Description keywords
if "Category" not in _df.columns:
    _df["Category"] = _df[col_desc].apply(derive_category_from_description)

if col_was_dupe not in _df.columns:
    _df[col_was_dupe] = False

# -----------------------------
# Filters
# -----------------------------
# Add a helpful per-row dominant bucket label for display
_df["Dominant_Bucket"] = _df[bucket_cols].idxmax(axis=1)

with st.sidebar:
    st.subheader("Filters")
    cats = sorted(_df["Category"].dropna().unique().tolist())
    sel_cats = st.multiselect("Category", cats)
    sel_buckets = st.multiselect("Aging Bucket (has units in)", bucket_cols)
    text_search = st.text_input("Search in Description")
    min_qty = st.number_input("Min Stock Qty", value=0, min_value=0)
    max_qty = st.number_input("Max Stock Qty", value=0, min_value=0, help="0 = no max filter")
    karat_options = ["10K", "14K", "SS"]
    sel_karats = st.multiselect("Karat", karat_options)

mask = pd.Series(True, index=_df.index)
if sel_cats:
    mask &= _df["Category"].isin(sel_cats)
if sel_buckets:
    # keep rows that have >0 units in any selected bucket
    mask &= (_df[sel_buckets].sum(axis=1) > 0)
if text_search:
    mask &= (
        _df[col_desc].astype(str).str.contains(text_search, case=False, na=False) |
        _df[col_item_id].astype(str).str.contains(text_search, case=False, na=False)
    )
if min_qty > 0:
    mask &= (_df[col_qty] >= min_qty)
if max_qty > 0:
    mask &= (_df[col_qty] <= max_qty)
if sel_karats:
    regex = "|".join(sel_karats)  # build OR regex: "10K|14K"
    mask &= (
        _df[col_item_id].astype(str).str.contains(regex, case=False, na=False)
    )

DF = _df.loc[mask].copy()

# -----------------------------
# Step 1: KPIs  (RESPECT FILTERS)
# -----------------------------
st.markdown("---")
st.subheader("🔢 Key Metrics")

units_total = float(DF[col_qty].sum())
units_slow = float(DF["> 180"].sum())
units_fresh = float(DF[["30-Jan", "30 - 60", "60 - 90"]].sum().sum())

k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Total Units", f"{units_total:,.0f}")
with k2:
    pct_slow = (units_slow / units_total * 100) if units_total else 0
    st.metric("% >180d", f"{pct_slow:.1f}%")
with k3:
    pct_fresh = (units_fresh / units_total * 100) if units_total else 0
    st.metric("% <90d", f"{pct_fresh:.1f}%")

# -----------------------------
# Step 2: Distribution Visualization (RESPECT FILTERS)
# -----------------------------
st.markdown("---")
st.subheader("📊 Units Distribution by Aging Bucket")

aging_units = pd.DataFrame({
    "Aging_Bucket": bucket_cols,
    "Units": [float(DF[b].sum()) for b in bucket_cols]
})
aging_units["% of Total"] = np.where(units_total > 0, aging_units["Units"] / units_total, 0)

st.bar_chart(aging_units.set_index("Aging_Bucket")["Units"], height=300)
st.dataframe(
    aging_units.assign(**{"% of Total": (aging_units["% of Total"] * 100).round(1).astype(str) + "%"}),
    hide_index=True,
    use_container_width=True,
)

# -----------------------------
# Step 3: Slow Movers Highlight (RESPECT FILTERS)
# -----------------------------
st.markdown("---")
st.subheader("🐌 Slow Movers (>180d)")

units_slow = float(DF["> 180"].sum())
st.info(f"You have **{units_slow:,.0f} units** sitting more than 180 days.")

slow_df = DF.sort_values("> 180", ascending=False).head(5)[[col_item_id, col_desc, "> 180", col_qty, "Category"]]
slow_df = slow_df.rename(columns={col_item_id: "Item_ID", col_desc: "Description", "> 180": "Units >180d", col_qty: "Total Units"})
st.dataframe(slow_df, hide_index=True, use_container_width=True)

# -----------------------------
# Step 4: Category Insights (RESPECT FILTERS)
# -----------------------------
st.markdown("---")
st.subheader("💎 Category Insights")

by_cat = DF.groupby("Category", as_index=False).agg(
    Units_Total=(col_qty, "sum"),
    Units_Slow=(" > 180".strip(), "sum")  # same as "> 180"
)
# If the above line confuses your linter, just use the literal:
# by_cat = DF.groupby("Category", as_index=False).agg(Units_Total=(col_qty,"sum"), Units_Slow=("> 180","sum"))

by_cat["% Slow"] = np.where(by_cat["Units_Total"] > 0, by_cat["Units_Slow"] / by_cat["Units_Total"], 0)
by_cat = by_cat.sort_values("% Slow", ascending=False)

st.bar_chart(by_cat.set_index("Category")["% Slow"], height=300)
st.dataframe(
    by_cat.assign(**{"% Slow": (by_cat["% Slow"] * 100).round(1).astype(str) + "%"}),
    hide_index=True,
    use_container_width=True,
)

# -----------------------------
# Step 5: Optional Deep Dives (RESPECT FILTERS)
# -----------------------------
st.markdown("---")
with st.expander("🔎 Detailed Tables"):
    st.markdown("**Top 20 Styles by >180d Units**")
    top20 = DF.sort_values("> 180", ascending=False).head(20)[[col_item_id, col_desc, col_qty, "> 180", "Category"]]
    st.dataframe(top20.rename(columns={col_item_id: "Item_ID", col_desc: "Description", col_qty: "Total Units", "> 180": "Units >180d"}), hide_index=True, use_container_width=True)

    st.markdown("**QA: Duplicates**")
    qa = DF[DF[col_was_dupe] == True][[col_item_id, col_desc, col_qty, "> 180", "Category"]]
    if not qa.empty:
        st.dataframe(qa.rename(columns={col_item_id: "Item_ID", col_desc: "Description", col_qty: "Total Units", "> 180": "Units >180d"}), hide_index=True, use_container_width=True)
    else:
        st.caption("No duplicates flagged.")

st.success("✅ Stock Aging dashboard ready with simplified layout (filters applied): KPIs → Distribution → Slow Movers → Category Insights → Details")
