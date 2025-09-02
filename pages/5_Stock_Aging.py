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


def add_aging_bucket(df: pd.DataFrame, days_col: str) -> pd.DataFrame:
    # Buckets requested: `30-Jan` (interpreted as 0-30), `30-60`, `60-90`, `90-180`, `>180`
    bins = [-np.inf, 30, 60, 90, 180, np.inf]
    labels = ["0-30", "30-60", "60-90", "90-180", ">180"]
    df = df.copy()
    df["Aging_Bucket"] = pd.cut(df[days_col].astype(float), bins=bins, labels=labels, right=True)
    return df


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

mask = pd.Series(True, index=_df.index)
if sel_cats:
    mask &= _df["Category"].isin(sel_cats)
if sel_buckets:
    # keep rows that have >0 units in any selected bucket
    mask &= (_df[sel_buckets].sum(axis=1) > 0)
if text_search:
    mask &= _df[col_desc].astype(str).str.contains(text_search, case=False, na=False)
if min_qty > 0:
    mask &= (_df[col_qty] >= min_qty)

DF = _df.loc[mask].copy()

# -----------------------------
# 🔍 Step 1: Sanity Totals
# -----------------------------
st.markdown("## 🔍 Step 1: Sanity Totals")

# Total stock units, Total weighted cost (inventory at cost), Total amount (carried at in Diaspark)
units_total = float(DF[col_qty].sum(skipna=True))
cost_total = float(DF[col_cost].sum(skipna=True))
amount_total = float(DF[col_amt].sum(skipna=True))

kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.metric("Total Stock Units", f"{units_total:,.0f}")
with kpi2:
    st.metric("Total Weighted Cost", currency(cost_total))
with kpi3:
    st.metric("Total Amount (Carried)", currency(amount_total))

st.caption("These are your baseline totals.")

# -----------------------------
# 📊 Step 2: Aging Breakdown (Units only)
# -----------------------------
# Aggregate UNITS by bucket only (no $ allocation)
units_total = float(_df[col_qty].sum())


aging_units = (
    pd.DataFrame({
        "Aging_Bucket": bucket_cols,
        "Stock_Units": [float(_df[b].sum()) for b in bucket_cols],
    })
)
aging_units["% of Units"] = np.where(units_total > 0, aging_units["Stock_Units"] / units_total, 0.0)

c1, c2 = st.columns([1.1, 1])
with c1:
    st.dataframe(
        aging_units.assign(**{
            "% of Units": (aging_units["% of Units"]*100).round(1).astype(str) + "%",
        }),
        use_container_width=True,
        hide_index=True,
    )
with c2:
    st.bar_chart(aging_units.set_index("Aging_Bucket")["Stock_Units"], height=260)

st.caption("Unit-based aging only. Source does not provide bucketed $ amounts.")

# -----------------------------
# 🐌 Step 3: Slow-Moving Stock (>180)
# -----------------------------
slow_bucket = "> 180"

units_slow = float(_df[slow_bucket].sum())
units_total = float(_df[col_qty].sum())


k1 = st.columns(1)[0]
with k1:
    pct_units = (units_slow/units_total*100) if units_total else 0
    st.metric(">180d: % of Units", f"{pct_units:.1f}%")

st.subheader("Top 20 Styles by Units in >180d")
if units_slow > 0:
    top20_units = (
        _df[[col_item_id, col_desc, col_qty, col_amt, col_cost, slow_bucket, "Category", col_was_dupe]]
        .sort_values(slow_bucket, ascending=False)
        .head(20)
        .rename(columns={
            col_item_id: "Item_ID",
            col_desc: "Description",
            col_qty: "Stock",
            col_amt: "Amount",
            col_cost: "Wtd Cost",
            slow_bucket: ">180 Units",
        })
    )
    st.dataframe(top20_units, use_container_width=True, hide_index=True)
else:
    st.info("No units in the >180 bucket under current filters.")

# -----------------------------
# 💎 Step 4: Category / Description Insights
# -----------------------------
# Use the allocated slow/amount per item to compute category-level slow share
# Compute category-level share of slow units
by_cat_units = (
_df.groupby("Category", as_index=False)
.agg(
Units_Total=(col_qty, "sum"),
Units_Slow=(slow_bucket, "sum"),
)
)
by_cat_units["% Units Slow"] = np.where(by_cat_units["Units_Total"]>0, by_cat_units["Units_Slow"] / by_cat_units["Units_Total"], 0.0)


st.dataframe(
    by_cat_units.sort_values("% Units Slow", ascending=False)
        .assign(**{
            "% Units Slow": (by_cat_units["% Units Slow"]*100).round(1).astype(str) + "%",
        }),
    use_container_width=True,
    hide_index=True,
)

# -----------------------------
# 📈 Step 5 (Optional): Movement Opportunities
# -----------------------------
DF["Cost_to_Amount"] = np.where(DF[col_amt].abs()>0, DF[col_cost] / DF[col_amt], np.nan)

# include Dominant_Bucket for context
cols_common = [col_item_id, col_desc, col_qty, col_cost, col_amt, "Dominant_Bucket", "Category", col_was_dupe]

cA, cB = st.columns(2)
with cA:
    st.markdown("**High Cost-to-Amount (Potential Over-Carried)**")
    high_ratio = (
        DF[cols_common + ["Cost_to_Amount"]]
        .copy()
    )
    high_ratio = high_ratio[high_ratio["Cost_to_Amount"] >= 1.2].sort_values("Cost_to_Amount", ascending=False).head(20)
    if len(high_ratio):
        st.dataframe(high_ratio.rename(columns={col_item_id: "Item_ID", col_desc: "Description", col_qty: "Stock", col_cost: "Wtd Cost", col_amt: "Amount"}), use_container_width=True, hide_index=True)
    else:
        st.info("No items meet the current Cost/Amount threshold.")

with cB:
    st.markdown("**QA List: was_duplicate = True**")
    qa = DF[DF[col_was_dupe] == True][cols_common].copy()
    if len(qa):
        st.dataframe(qa.rename(columns={col_item_id: "Item_ID", col_desc: "Description", col_qty: "Stock", col_cost: "Wtd Cost", col_amt: "Amount"}).sort_values(col_amt, ascending=False).head(50), use_container_width=True, hide_index=True)
    else:
        st.caption("No flagged duplicates under current filters.")

# -----------------------------
# Raw preview + Download
# -----------------------------
st.markdown("---")
with st.expander("Preview Cleaned Data"):
    st.dataframe(DF.head(100), use_container_width=True)

csv_bytes = DF.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download filtered dataset (CSV)",
    data=csv_bytes,
    file_name="stock_aging_filtered.csv",
    mime="text/csv",
)

st.success("Stock Aging page ready. Hooked to your API with fixed schema & bucket logic.")
