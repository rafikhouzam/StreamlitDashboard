import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import numpy as np
import requests
from io import BytesIO
from utils.navbar import navbar

# Page config
st.set_page_config(
    page_title="Inventory Analysis",
    page_icon="🪙",
    layout="wide"
)
navbar()
st.title("Inventory Analysis")

# Load dataset
@st.cache_data
def load_inventory():
    url = f"https://api.anerijewels.com/api/inventory"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

def load_local():
    # Fallback to local CSV for testing
    csv_path = st.secrets["LOCAL_INVENTORY_PATH"]
    return pd.read_csv(csv_path)

try:
    use_local = st.secrets.get("USE_LOCAL_INVENTORY_DATA", False)
    df = load_local() if use_local else load_inventory()
    #df.shape
except Exception as e:
    st.error("❌ Failed to load data.")
    st.text(f"Error: {e}")
    st.stop()

# ----------------------
# Helpers & Config
# ----------------------
DATE_COLS = ["update_dt", "price_update_dt", "style_dt", "approve_dt"]
NUMERIC_COLS_CANDIDATES = [
    "selling_price", "metal_cost", "diamond_cost", "overseas_diamond_cost",
    "domestic_diamond_cost", "overseas_labor_cost", "domestic_labor_cost",
    "total_labor_cost", "overseas_cost", "domestic_cost",
    "melt_value", "purchase_price", "semimount_price", "semimount_cost",
    "diamond_price", "gold_increment", "minimum_qty", "reorder_qty",
    "gross_wt", "cstone_wt", "ctrstone_wt", "diamond_wt", "old_cost",
    "total_metal_wt", "cs_size", "cstone_size",
    "shape1_min", "shape1_max", "shape2_min", "shape2_max", "shape3_min", "shape3_max",
    "center1_min", "center2_min", "center3_min",
]
LOCK_COLS = ["gold_lock", "silver_lock", "platinum_lock", "palladium_lock"]

def coerce_numeric(df: pd.DataFrame, columns):
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def parse_dates(df: pd.DataFrame, columns):
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def yesish_to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])

def safe_value_counts(df, col):
    vc = df[col].value_counts()
    out = vc.reset_index()
    out.columns = [col, "styles"]
    return out

df = coerce_numeric(df, NUMERIC_COLS_CANDIDATES)
df = parse_dates(df, DATE_COLS)

# ----------------------
# Sidebar Filters
# ----------------------
st.sidebar.header("Filters")

cats = sorted(df["style_category"].dropna().unique()) if "style_category" in df.columns else []
metals = sorted(df["metal_typ"].dropna().unique()) if "metal_typ" in df.columns else []
#vendors = sorted(df["vendor_id"].dropna().unique()) if "vendor_id" in df.columns else []

sel_cats = st.sidebar.multiselect("Category", cats, default=cats)
sel_metals = st.sidebar.multiselect("Metal Type", metals, default=metals)
#sel_vendors = st.sidebar.multiselect("Vendor", vendors, default=vendors)

if "selling_price" in df.columns and df["selling_price"].notna().any():
    pr_lo, pr_hi = st.sidebar.slider("Selling Price Range",
                                     min_value=float(df["selling_price"].min()),
                                     max_value=float(df["selling_price"].max()),
                                     value=(float(df["selling_price"].min()), float(df["selling_price"].max())))
else:
    pr_lo, pr_hi = (0.0, 0.0)

#stale_threshold = st.sidebar.slider("Stale if updated > N days", 0, 730, 180)

filtered = df.copy()

if sel_cats:
    filtered = filtered[filtered["style_category"].isin(sel_cats)]
if sel_metals:
    filtered = filtered[filtered["metal_typ"].isin(sel_metals)]
#if sel_vendors:
    #filtered = filtered[filtered["vendor_id"].isin(sel_vendors)]
if "selling_price" in filtered.columns and pr_hi > 0:
    filtered = filtered[filtered["selling_price"].between(pr_lo, pr_hi, inclusive="both")]

cap_outliers = st.sidebar.checkbox("Exclude top 1% outliers", value=True)
if cap_outliers:
    q_hi = filtered["selling_price"].quantile(0.99)
    filtered_viz = filtered[filtered["selling_price"] <= q_hi]
else:
    filtered_viz = filtered


# ----------------------
# KPIs (No margin)
# ----------------------

k1, k2, k3, k4 = st.columns(4)
k1.metric("Styles", f"{len(filtered):,}")
if "selling_price" in filtered.columns:
    k2.metric("Median Price", f"${filtered['selling_price'].median():,.2f}")
    k3.metric("Mean Price", f"${filtered['selling_price'].mean():,.2f}")
else:
    k2.metric("Median Price", "—")
    k3.metric("Mean Price", "—")
k4.metric("Image Coverage", f"{(filtered['has_image'].mean()*100 if 'has_image' in filtered.columns else 0):.1f}%")
st.info("Images coming soon")
# ----------------------
# Tabs
# ----------------------
tab_overview, tab_comp, tab_vendor, tab_pricing, tab_drill = st.tabs(
    ["Overview", "Cost Components", "Vendors", "Pricing Bands", "Style Drilldown"]
)

# ---- Overview ----
with tab_overview:
    st.subheader("Distribution by Category & Metal")
    colA, colB = st.columns(2)
    if "style_category" in filtered.columns:
        cat_counts = safe_value_counts(filtered, "style_category")
        colA.dataframe(cat_counts, use_container_width=True)
    else:
        colA.info("No style_category column.")
    if "metal_typ" in filtered.columns:
        metal_counts = safe_value_counts(filtered, "metal_typ")
        colB.dataframe(metal_counts, use_container_width=True)
    else:
        colB.info("No metal_typ column.")

    st.markdown("### Top Styles by Price (no cost/margin involved)")
    if "selling_price" in filtered.columns:
        top_price = filtered.sort_values("selling_price", ascending=False).head(50)
        st.dataframe(top_price[["style_cd", "style_category", "metal_typ", "vendor_id", "selling_price"]],
                     use_container_width=True)
    else:
        st.info("No selling_price available.")

# ---- Cost Components (absolute, not shares) ----
with tab_comp:
    st.subheader("Cost Components (Absolute Values Only)")
    comp_cols = [c for c in ["metal_cost", "diamond_cost", "total_labor_cost"]
                 if c in filtered.columns]
    if comp_cols:
        if "style_category" in filtered.columns:
            comp_summary = (filtered_viz.groupby("style_category")[comp_cols]
                            .median().reset_index().rename(columns={c: f"median_{c}" for c in comp_cols}))
            st.dataframe(comp_summary, use_container_width=True)
        if "selling_price" in filtered.columns:
            c1, c2 = st.columns(2)
            for i, col in enumerate(comp_cols[:2]):
                fig = px.scatter(filtered_viz, x=col, y="selling_price",
                                 color="style_category" if "style_category" in filtered.columns else None,
                                 hover_data=["style_cd", "vendor_id"] if "style_cd" in filtered.columns else None,
                                 title=f"Selling Price vs {col}")
                (c1 if i == 0 else c2).plotly_chart(fig, use_container_width=True)
        st.markdown("#### Component Distributions")
        for col in comp_cols:
            fig = px.histogram(filtered_viz, x=col, nbins=40, title=f"Distribution of {col}")
            fig.update_layout(bargap=0.2)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No component columns (metal_cost, diamond_cost, melt_value, total_labor_cost).")

# ---- Vendors ----
with tab_vendor:
    st.subheader("Vendor Summary")
    if "vendor_id" in filtered.columns:
        extra = [c for c in ["selling_price", "metal_cost", "diamond_cost", "total_labor_cost"] if c in filtered.columns]
        agg_dict = {"style_cd": "count"}
        for c in extra:
            agg_dict[c] = "median"
        vendor_summary = (filtered.groupby("vendor_id").agg(agg_dict)
                          .rename(columns={"style_cd": "styles"}).reset_index()
                          .sort_values("styles", ascending=False))
        st.dataframe(vendor_summary, use_container_width=True)
        if "styles" in vendor_summary.columns:
            fig = px.bar(vendor_summary.head(25), x="vendor_id", y="styles", title="Top Vendors by Style Count")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No vendor_id column.")

# ---- Pricing Bands ----
with tab_pricing:
    st.subheader("Pricing Bands & Mix")
    if "selling_price" in filtered_viz.columns:
        bins = st.selectbox("Price Bins", ["$50", "$100", "$250", "$500", "$1000", "Custom"], index=2)
        preset = {"$50": 50, "$100": 100, "$250": 250, "$500": 500, "$1000": 1000}
        if bins == "Custom":
            step = st.number_input("Custom bin size ($)", min_value=10, max_value=5000, value=250, step=10)
        else:
            step = preset[bins]

        max_price = int(np.nanmax(filtered_viz["selling_price"])) if filtered_viz["selling_price"].notna().any() else 0
        edges = list(range(0, max_price + step, step)) if max_price else [0, step]
        labels = [f"${edges[i]}–${edges[i+1]-1}" for i in range(len(edges)-1)]
        filtered_viz["price_band"] = pd.cut(filtered_viz["selling_price"], bins=edges, labels=labels, include_lowest=True)

        band_counts = (filtered_viz.groupby(["price_band", "style_category"])["style_cd"]
                       .count().reset_index().rename(columns={"style_cd": "styles"}))
        # aggregate across categories to find the busiest 10 bins
        top_bins = (
            band_counts.groupby("price_band")["styles"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .index
        )

        # keep only those bins
        band_counts = band_counts[band_counts["price_band"].isin(top_bins)]        
        st.dataframe(band_counts.pivot_table(index="style_category", columns="price_band", values="styles", fill_value=0),
                     use_container_width=True)
        fig = px.bar(band_counts, x="price_band", y="styles", color="style_category",
                     title="Styles per Price Band by Category")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No selling_price column.")

# ---- QA / Staleness ----
# with tab_qa:
#     st.subheader("Data Quality & Staleness")
#     issues = {}
#     if "style_cd" in filtered.columns:
#         issues["blank_style_cd"] = int((filtered["style_cd"].astype(str).str.strip() == "").sum())
#     if "selling_price" in filtered.columns:
#         issues["missing_price"] = int(filtered["selling_price"].isna().sum())
#         issues["zero_or_negative_price"] = int((filtered["selling_price"] <= 0).sum())
#     #if "style_photo" in filtered.columns:
#         #issues["missing_image"] = int((filtered["has_image"] == False).sum())

#     if "days_since_update" in filtered.columns and filtered["days_since_update"].notna().any():
#         stale = filtered["days_since_update"] > stale_threshold
#         issues["stale_styles"] = int(stale.sum())
#         st.metric(f"Stale Styles (>{stale_threshold} days)", f"{issues['stale_styles']:,}")
#         fig = px.histogram(filtered, x="days_since_update", nbins=40, title="Days Since Last Update")
#         st.plotly_chart(fig, use_container_width=True)

#     if "lock_active" in filtered.columns:
#         st.metric("Lock Active", f"{int(filtered['lock_active'].sum()):,} styles")

#     st.markdown("#### Issue Counts")
#     st.json(issues)

#     flagged = filtered.copy()
#     masks = []
#     if "style_cd" in flagged.columns:
#         masks.append(flagged["style_cd"].astype(str).str.strip() == "")
#     if "selling_price" in flagged.columns:
#         masks.append(flagged["selling_price"].isna() | (flagged["selling_price"] <= 0))
#     if "has_image" in flagged.columns:
#         masks.append(flagged["has_image"] == False)
#     if "days_since_update" in flagged.columns and flagged["days_since_update"].notna().any():
#         masks.append(flagged["days_since_update"] > stale_threshold)
#     if "lock_active" in flagged.columns:
#         masks.append(flagged["lock_active"])

#     if masks:
#         bad = flagged[np.column_stack(masks).any(axis=1)] if len(masks) > 1 else flagged[masks[0]]
#         st.download_button("⬇️ Download Flagged Styles (CSV)",
#                            bad.to_csv(index=False).encode("utf-8"),
#                            file_name="flagged_styles.csv",
#                            mime="text/csv")

# ---- Style Drilldown ----
with tab_drill:
    st.subheader("Style Drilldown")
    q = st.text_input("Search style_cd")
    if q:
        qdf = filtered[filtered["style_cd"].str.contains(q.strip().upper(), na=False)]
    else:
        qdf = filtered.head(200)

    cols = [c for c in ["style_cd", "style_desc", "style_category", "metal_typ", "vendor_id",
                        "selling_price", "metal_cost", "diamond_cost", "total_labor_cost",
                        "melt_value"] if c in filtered.columns]
    st.dataframe(qdf[cols], use_container_width=True)
    
st.caption("Note: No margin or total_cost calculations. This app focuses on inventory mix, pricing distributions, vendor/category breakdowns, locks, and data quality.")
