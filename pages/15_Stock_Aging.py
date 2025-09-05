from __future__ import annotations

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
    """Fallback to local CSV for testing."""
    csv_path = st.secrets["LOCAL_STOCK_PATH"]
    return pd.read_csv(csv_path)

try:
    use_local = st.secrets.get("USE_LOCAL_STOCK_DATA", False)
    df_raw = load_stock_local() if use_local else load_stock()
    st.caption(f"Loaded **{len(df_raw):,}** rows from **{'local CSV' if use_local else 'API'}**")
except Exception as e:
    st.error(f"Failed to load stock data: {e}")
    st.stop()

# -----------------------------
# Schema
# -----------------------------
col_item_id = "item_id"
col_desc    = "Description"
col_qty     = "Stock"
col_cost    = "Wtd Cost"
col_amt     = "Amount"
col_cat     = "style_category"
col_was_dupe= "was_duplicate"
bucket_cols = ["30-Jan", "30 - 60", "60 - 90", "90 - 180", "> 180"]

# -----------------------------
# Normalize numeric fields
# -----------------------------
_df = df_raw.copy()
_df.columns = [c.strip() for c in _df.columns]

for c in [col_qty, col_cost, col_amt] + bucket_cols:
    _df[c] = pd.to_numeric(_df[c], errors="coerce")

# If Stock missing, compute as row-wise sum of buckets
if _df[col_qty].isna().all() or (_df[col_qty] == 0).all():
    _df[col_qty] = _df[bucket_cols].sum(axis=1)

if col_was_dupe not in _df.columns:
    _df[col_was_dupe] = False

# -----------------------------
# Filters
# -----------------------------
_df["Dominant_Bucket"] = (
    _df[bucket_cols]
    .fillna(-np.inf)      # make NaNs safe
    .idxmax(axis=1)       # now works without warning
    .replace(-np.inf, np.nan)  # if all were NaN, stays NaN
)


with st.sidebar:
    st.subheader("Filters")
    cats = sorted(_df[col_cat].dropna().unique().tolist())
    sel_cats = st.multiselect("Category", cats)
    sel_buckets = st.multiselect("Aging Bucket (has units in)", bucket_cols)
    text_search = st.text_input("Search in Description or Item ID")
    min_qty = st.number_input("Min Stock Qty", value=0, min_value=0)
    max_qty = st.number_input("Max Stock Qty", value=0, min_value=0, help="0 = no max filter")
    karat_options = ["10K", "14K", "SS"]
    sel_karats = st.multiselect("Karat", karat_options)

mask = pd.Series(True, index=_df.index)
if sel_cats:
    mask &= _df[col_cat].isin(sel_cats)
if sel_buckets:
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
    regex = "|".join(sel_karats)
    mask &= _df[col_item_id].astype(str).str.contains(regex, case=False, na=False)

DF = _df.loc[mask].copy()

# -----------------------------
# Step 1: KPIs
# -----------------------------
st.markdown("---")
st.subheader("🔢 Key Metrics")

units_total = float(DF[col_qty].sum())
units_slow  = float(DF["> 180"].sum())
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
# Step 2: Distribution
# -----------------------------
st.markdown("---")
st.subheader("📊 Units Distribution by Aging Bucket")

aging_units = pd.DataFrame({
    "Aging_Bucket": bucket_cols,
    "Units": [float(DF[b].sum()) for b in bucket_cols]
})
aging_units["% of Total"] = np.where(units_total > 0, aging_units["Units"]/units_total, 0)

st.bar_chart(aging_units.set_index("Aging_Bucket")["Units"], height=300)
st.dataframe(
    aging_units.assign(**{"% of Total": (aging_units["% of Total"]*100).round(1).astype(str)+"%"}),
    hide_index=True
)

# -----------------------------
# Step 3: Slow Movers
# -----------------------------
st.markdown("---")
st.subheader("🐌 Slow Movers (>180d)")
st.info(f"You have **{units_slow:,.0f} units** sitting more than 180 days.")

slow_df = DF.sort_values("> 180", ascending=False).head(10)[[col_item_id,col_desc,"> 180",col_qty,col_cat]]
slow_df = slow_df.rename(columns={col_item_id:"Style Number", col_desc:"Description","> 180":"Units >180d", col_qty:"Total Units", col_cat:"Category"})
st.dataframe(slow_df, hide_index=True, width='stretch')

# -----------------------------
# Step 4: Category Insights
# -----------------------------
st.markdown("---")
st.subheader("💎 Category Insights")

by_cat = DF.groupby(col_cat, as_index=False).agg(
    Units_Total=(col_qty,"sum"),
    Units_Slow=("> 180","sum")
)
by_cat["% Slow"] = np.where(by_cat["Units_Total"] > 0, by_cat["Units_Slow"]/by_cat["Units_Total"],0)
by_cat = by_cat.sort_values("% Slow", ascending=False)

st.bar_chart(by_cat.set_index(col_cat)["% Slow"], height=300)
st.dataframe(
    by_cat.assign(**{"% Slow": (by_cat["% Slow"]*100).round(1).astype(str)+"%"}),
    hide_index=True,
    width='stretch',
)

# -----------------------------
# Step 5: Missing Values by Category
# -----------------------------
st.markdown("---")
st.subheader("🚨 Missing Values by Category")

missing_summary = DF.groupby(col_cat).agg(
    rows_total=("item_id","count"),
    rows_missing_cost=(col_cost, lambda x: x.isna().sum()),
    stock_total=(col_qty,"sum"),
    stock_missing_cost=(col_cost, lambda x: DF.loc[x.index, col_qty][x.isna()].sum())
)
missing_summary["% rows missing"] = (missing_summary["rows_missing_cost"]/missing_summary["rows_total"]*100).round(1)
missing_summary["% stock missing"] = (missing_summary["stock_missing_cost"]/missing_summary["stock_total"]*100).round(1)

st.dataframe(missing_summary.reset_index(), width='stretch', hide_index=True)

# -----------------------------
# Step 6: Deep Dives
# -----------------------------
st.markdown("---")
with st.expander("🔎 Detailed Tables"):
    st.markdown("**Top 20 Styles by >180d Units**")
    top20 = DF.sort_values("> 180", ascending=False).head(20)[[col_item_id,col_desc,col_qty,"> 180",col_cat]]
    st.dataframe(top20
        .rename(
        columns={col_item_id:"Item_ID", 
        col_desc:"Description",
        col_qty:"Total Units","> 180":"Units >180d",
        col_cat:"Category"}
        ),
        hide_index=True, 
        width='stretch')