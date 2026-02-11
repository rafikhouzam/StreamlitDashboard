import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import requests
from utils.navbar import navbar
from streamlit_auth import require_login

require_login()

# ----------------------
# Page config
# ----------------------
st.set_page_config(
    page_title="Inventory Analysis",
    page_icon="🪙",
    layout="wide"
)

use_local = st.secrets.get("USE_LOCAL_INVENTORY_DATA", False)
if not use_local:
    navbar()

st.title("Inventory Analysis")

# NOTE: Leaving the BU selector for now – you said you'll come back to this later.
unit = st.selectbox("Select Business Unit", ["Sumit", "EDB", "Newlite"])

# ----------------------
# Data loading
# ----------------------
@st.cache_data
def load_inventory(unit: str) -> pd.DataFrame:
    url = f"https://api.anerijewels.com/api/inventory?unit={unit.lower()}"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

def load_local(unit: str) -> pd.DataFrame:
    if unit == "Sumit":
        csv_path = st.secrets["LOCAL_INVENTORY_SUMIT_PATH"]
    elif unit == "EDB":
        csv_path = st.secrets["LOCAL_INVENTORY_EDB_PATH"]
    elif unit == "Newlite":
        csv_path = st.secrets["LOCAL_INVENTORY_NEWLITE_PATH"]
    else:
        st.stop()
    return pd.read_csv(csv_path)

try:
    if use_local:
        df = load_local(unit)
    else:
        df = load_inventory(unit)
except Exception as e:
    st.error("❌ Failed to load data.")
    st.text(f"Error: {e}")
    st.stop()

# ---------------------------------------------------------------------
# Expecting columns (post-enrichment):
# ['Style no.', 'Style Image', 'Vendor', 'Customer', 'Jewelry Category',
#  'Jewelry Type', 'Casting Weight (g)', 'Metal Type', 'Diamond Shape',
#  'Diamond Quality', 'Diamond Size', 'CTTW', 'Labor Cost', 'Finding Cost',
#  'Metal Cost', 'Diamond Cost', 'Duty Cost', 'Current Cost', 'Selling Price',
#  'Created on', 'Units in Repair', 'Units in CRET', 'Units in QC',
#  'Units in RTS', 'Units on Memo', 'ECOMM', 'On hand $', 'On memo $', 'RTS $',
#  'Units sold in 2022', 'Units sold in 2023', 'Units sold in 2024',
#  'Units sold in 2025', '2025 Opening Units', 'Last sold date',
#  'Days since last sold']
# ---------------------------------------------------------------------

# ----------------------
# Helpers & Cleaning
# ----------------------
DATE_COLS = ["Created on", "Last sold date"]
NUMERIC_COLS = [
    "Casting Weight (g)", "CTTW",
    "Labor Cost", "Finding Cost", "Metal Cost", "Diamond Cost", "Duty Cost",
    "Current Cost", "Selling Price",
    "Units in Repair", "Units in CRET", "Units in QC",
    "Units in RTS", "Units on Memo",
    "On hand $", "On memo $", "RTS $",
    "Units sold in 2022", "Units sold in 2023", "Units sold in 2024",
    "Units sold in 2025", "2025 Opening Units",
    "Days since last sold"
]

def coerce_numeric(df: pd.DataFrame, columns) -> pd.DataFrame:
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def parse_dates(df: pd.DataFrame, columns) -> pd.DataFrame:
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def yesish_to_bool(series: pd.Series) -> pd.Series:
    # Handles Y/Yes/True/1 or keeps bools as-is
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.upper().isin(["Y", "YES", "TRUE", "1"])

# Standardize style column and drop rows without a style
if "Style no." in df.columns:
    df["Style no."] = df["Style no."].astype(str).str.strip()
    df = df[df["Style no."].notna() & (df["Style no."] != "")]
else:
    st.error("❌ 'Style no.' column not found in dataset.")
    st.stop()

# Coerce numeric & dates
df = coerce_numeric(df, NUMERIC_COLS)
df = parse_dates(df, DATE_COLS)

# ECOMM normalization
if "ECOMM" in df.columns:
    df["ECOMM"] = yesish_to_bool(df["ECOMM"])

# Total units sold across 2022–2025
year_cols = ["Units sold in 2022", "Units sold in 2023", "Units sold in 2024", "Units sold in 2025"]
present_year_cols = [c for c in year_cols if c in df.columns]
if present_year_cols:
    df["Total units sold (2022–2025)"] = df[present_year_cols].sum(axis=1)

# Total inventory value metric – we can treat total as on hand + memo + RTS
for c in ["On hand $", "On memo $", "RTS $"]:
    if c not in df.columns:
        df[c] = 0.0
df["Total inventory value $"] = df["On hand $"] + df["On memo $"] + df["RTS $"]

st.subheader("Data Preview")
st.dataframe(df.head(50), use_container_width=True)

# ----------------------
# Sidebar Filters
# ----------------------
st.sidebar.header("Filters")

cats = sorted(df["Jewelry Category"].dropna().unique()) if "Jewelry Category" in df.columns else []
metals = sorted(df["Metal Type"].dropna().unique()) if "Metal Type" in df.columns else []
vendors = sorted(df["Vendor"].dropna().unique()) if "Vendor" in df.columns else []

# Category filter
all_cats = ["All"] + cats
sel_cats = st.sidebar.multiselect("Jewelry Category", all_cats, default=["All"])
if ("All" in sel_cats) or (not sel_cats):
    sel_cats = cats

# Metal filter
all_metals = ["All"] + metals
sel_metals = st.sidebar.multiselect("Metal Type", all_metals, default=["All"])
if ("All" in sel_metals) or (not sel_metals):
    sel_metals = metals

# Vendor filter
all_vendors = ["All"] + vendors
sel_vendors = st.sidebar.multiselect("Vendor", all_vendors, default=["All"])
if ("All" in sel_vendors) or (not sel_vendors):
    sel_vendors = vendors

# ECOMM filter
ecomm_option = st.sidebar.selectbox("ECOMM filter", ["All", "ECOMM only", "Non-ECOMM"])

# Selling Price range
if "Selling Price" in df.columns and df["Selling Price"].notna().any():
    pr_lo, pr_hi = st.sidebar.slider(
        "Selling Price Range",
        min_value=float(df["Selling Price"].min()),
        max_value=float(df["Selling Price"].max()),
        value=(float(df["Selling Price"].min()), float(df["Selling Price"].max()))
    )
else:
    pr_lo, pr_hi = (0.0, 0.0)

cap_outliers = st.sidebar.checkbox("Exclude top 1% price outliers (for charts)", value=True)

# ----------------------
# Apply filters
# ----------------------
filtered = df.copy()

if sel_cats:
    filtered = filtered[filtered["Jewelry Category"].isin(sel_cats)]
if sel_metals:
    filtered = filtered[filtered["Metal Type"].isin(sel_metals)]
if sel_vendors:
    filtered = filtered[filtered["Vendor"].isin(sel_vendors)]

if ecomm_option == "ECOMM only":
    filtered = filtered[filtered["ECOMM"] == True]
elif ecomm_option == "Non-ECOMM":
    filtered = filtered[filtered["ECOMM"] == False]

if "Selling Price" in filtered.columns and pr_hi > 0:
    filtered = filtered[filtered["Selling Price"].between(pr_lo, pr_hi, inclusive="both")]

if cap_outliers and "Selling Price" in filtered.columns:
    q_hi = filtered["Selling Price"].quantile(0.99)
    filtered_viz = filtered[filtered["Selling Price"] <= q_hi]
else:
    filtered_viz = filtered

st.write(f"Filtered styles: {len(filtered):,}")

# ----------------------
# KPI Cards
# ----------------------
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Styles", f"{len(filtered):,}")
k2.metric("On Hand Value ($)", f"{filtered['On hand $'].sum():,.0f}")
k3.metric("On Memo Value ($)", f"{filtered['On memo $'].sum():,.0f}")
k4.metric("RTS Value ($)", f"{filtered['RTS $'].sum():,.0f}")
if "Total units sold (2022–2025)" in filtered.columns:
    k5.metric("Total Units Sold (2022–2025)", f"{int(filtered['Total units sold (2022–2025)'].sum()):,}")
else:
    k5.metric("Total Units Sold (2022–2025)", "N/A")

# ----------------------
# Tabs
# ----------------------
tab_overview, tab_value, tab_sales, tab_cost, tab_vendor_cust, tab_drill, tab_diamonds = st.tabs(
    [
        "Overview",
        "Inventory Value",
        "Sales & Velocity",
        "Cost Structure",
        "Vendors & Customers",
        "Style Drilldown",
        "Diamond Search",
    ]
)

# ---- Overview ----
with tab_overview:
    st.subheader("Category & Metal Mix")

    colA, colB = st.columns(2)

    # Category summary
    if {"Jewelry Category", "On hand $"}.issubset(filtered.columns):
        cat_summary = (
            filtered.groupby("Jewelry Category", as_index=False)
            .agg(
                Styles=("Style no.", "nunique"),
                On_Hand_Value=("On hand $", "sum"),
                On_Memo_Value=("On memo $", "sum"),
                RTS_Value=("RTS $", "sum")
            )
            .sort_values("On_Hand_Value", ascending=False)
        )
        colA.dataframe(
            cat_summary.style.format({
                "On_Hand_Value": "{:,.0f}",
                "On_Memo_Value": "{:,.0f}",
                "RTS_Value": "{:,.0f}",
            }),
            use_container_width=True,
        )
    else:
        colA.info("Jewelry Category / value columns not found.")

    # Metal summary
    if {"Metal Type", "On hand $"}.issubset(filtered.columns):
        metal_summary = (
            filtered.groupby("Metal Type", as_index=False)
            .agg(
                Styles=("Style no.", "nunique"),
                On_Hand_Value=("On hand $", "sum"),
                On_Memo_Value=("On memo $", "sum"),
                RTS_Value=("RTS $", "sum")
            )
            .sort_values("On_Hand_Value", ascending=False)
        )
        colB.dataframe(
            metal_summary.style.format({
                "On_Hand_Value": "{:,.0f}",
                "On_Memo_Value": "{:,.0f}",
                "RTS_Value": "{:,.0f}",
            }),
            use_container_width=True,
        )
    else:
        colB.info("Metal Type / value columns not found.")

    st.subheader("Top Styles by Total Inventory Value")

    n_styles = st.number_input(
        "Number of styles to show",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
        key="num_top_styles_enriched",
    )

    cols_for_top = [
        "Style no.",
        "Jewelry Category",
        "Jewelry Type",
        "Metal Type",
        "Vendor",
        "On hand $",
        "On memo $",
        "RTS $",
        "Total inventory value $",
        "Selling Price",
        "Current Cost",
    ]
    existing_cols_for_top = [c for c in cols_for_top if c in filtered.columns]

    top_styles = (
        filtered[existing_cols_for_top]
        .sort_values("Total inventory value $", ascending=False)
        .head(n_styles)
    )

    st.info("Tip: Click any column header to sort.")
    st.dataframe(
        top_styles.style.format({
            "On hand $": "{:,.0f}",
            "On memo $": "{:,.0f}",
            "RTS $": "{:,.0f}",
            "Total inventory value $": "{:,.0f}",
            "Selling Price": "{:,.2f}",
            "Current Cost": "{:,.2f}",
        }),
        use_container_width=True,
    )

# ---- Inventory Value ----
with tab_value:
    st.header("Inventory Value Analysis")

    # Total value by category
    if {"Jewelry Category", "Total inventory value $"}.issubset(filtered.columns):
        cat_val = (
            filtered.groupby("Jewelry Category", as_index=False)["Total inventory value $"]
            .sum()
            .sort_values("Total inventory value $", ascending=False)
        )

        fig_cat = px.bar(
            cat_val,
            x="Jewelry Category",
            y="Total inventory value $",
            title="Total Inventory Value by Category",
            text_auto=".2s",
            template="plotly_white",
        )
        fig_cat.update_layout(xaxis_title="", yaxis_title="Total Value ($)")
        st.plotly_chart(fig_cat, use_container_width=True)

    # Stacked value by category & metal
    if {"Jewelry Category", "Metal Type", "Total inventory value $"}.issubset(filtered.columns):
        cat_metal = (
            filtered.groupby(["Jewelry Category", "Metal Type"], as_index=False)["Total inventory value $"]
            .sum()
        )

        fig_cm = px.bar(
            cat_metal,
            x="Total inventory value $",
            y="Jewelry Category",
            color="Metal Type",
            orientation="h",
            title="Value by Category and Metal Type",
            template="plotly_white",
        )
        fig_cm.update_layout(xaxis_title="Total Value ($)", yaxis_title="")
        st.plotly_chart(fig_cm, use_container_width=True)

# ---- Sales & Velocity ----
with tab_sales:
    st.header("Sales & Velocity")

    # Units sold by year
    if present_year_cols:
        sales_long = filtered.melt(
            id_vars=["Style no."],
            value_vars=present_year_cols,
            var_name="Year",
            value_name="Units sold"
        )
        sales_long["Units sold"] = pd.to_numeric(sales_long["Units sold"], errors="coerce").fillna(0)

        year_summary = (
            sales_long.groupby("Year", as_index=False)["Units sold"]
            .sum()
            .sort_values("Year")
        )

        st.subheader("Units sold by year")
        st.dataframe(year_summary, use_container_width=True)

        fig_year = px.bar(
            year_summary,
            x="Year",
            y="Units sold",
            title="Total Units Sold by Year",
            template="plotly_white",
        )
        st.plotly_chart(fig_year, use_container_width=True)

    # Distribution of days since last sold
    if "Days since last sold" in filtered.columns:
        st.subheader("Recency (Days since last sold)")
        fig_age = px.histogram(
            filtered,
            x="Days since last sold",
            nbins=30,
            title="Distribution of Days Since Last Sold",
            template="plotly_white",
        )
        st.plotly_chart(fig_age, use_container_width=True)

    # Price vs CTTW
    if {"CTTW", "Selling Price"}.issubset(filtered_viz.columns):
        st.subheader("Selling Price vs CTTW")
        fig_cttw = px.scatter(
            filtered_viz,
            x="CTTW",
            y="Selling Price",
            color="Jewelry Category" if "Jewelry Category" in filtered_viz.columns else None,
            hover_data=["Style no.", "Vendor"],
            title="Selling Price vs CTTW",
            template="plotly_white",
        )
        st.plotly_chart(fig_cttw, use_container_width=True)

# ---- Cost Structure ----
with tab_cost:
    st.header("Cost Structure")

    cost_cols = [c for c in ["Labor Cost", "Finding Cost", "Metal Cost", "Diamond Cost", "Duty Cost", "Current Cost"] if c in filtered.columns]

    if cost_cols and "Jewelry Category" in filtered.columns:
        st.subheader("Median Cost Components by Category")

        comp_summary = (
            filtered.groupby("Jewelry Category")[cost_cols]
            .median()
            .reset_index()
        )

        st.dataframe(
            comp_summary.style.format({c: "${:,.2f}" for c in cost_cols}),
            use_container_width=True,
        )

    if "Selling Price" in filtered_viz.columns and "Current Cost" in filtered_viz.columns:
        st.subheader("Selling Price vs Current Cost")

        fig_sc = px.scatter(
            filtered_viz,
            x="Current Cost",
            y="Selling Price",
            color="Jewelry Category" if "Jewelry Category" in filtered_viz.columns else None,
            hover_data=["Style no.", "Vendor"],
            title="Selling Price vs Current Cost",
            template="plotly_white",
        )
        st.plotly_chart(fig_sc, use_container_width=True)

    # Distributions
    st.subheader("Cost Distributions")
    for col in cost_cols:
        fig_hist = px.histogram(
            filtered_viz,
            x=col,
            nbins=40,
            title=f"Distribution of {col}",
            template="plotly_white",
        )
        st.plotly_chart(fig_hist, use_container_width=True)

# ---- Vendors & Customers ----
with tab_vendor_cust:
    st.header("Vendors & Customers")

    # Vendor summary
    if "Vendor" in filtered.columns:
        st.subheader("Vendor Summary")

        vendor_agg = (
            filtered.groupby("Vendor", as_index=False)
            .agg(
                Styles=("Style no.", "nunique"),
                On_Hand_Value=("On hand $", "sum"),
                On_Memo_Value=("On memo $", "sum"),
                RTS_Value=("RTS $", "sum"),
            )
            .sort_values("On_Hand_Value", ascending=False)
        )

        st.dataframe(
            vendor_agg.style.format({
                "On_Hand_Value": "{:,.0f}",
                "On_Memo_Value": "{:,.0f}",
                "RTS_Value": "{:,.0f}",
            }),
            use_container_width=True,
        )

        fig_v = px.bar(
            vendor_agg.head(25),
            x="Vendor",
            y="On_Hand_Value",
            title="Top Vendors by On Hand Value",
            template="plotly_white",
        )
        st.plotly_chart(fig_v, use_container_width=True)

    # Customer summary
    if "Customer" in filtered.columns:
        st.subheader("Customer Summary")

        cust_agg = (
            filtered.groupby("Customer", as_index=False)
            .agg(
                Styles=("Style no.", "nunique"),
                On_Hand_Value=("On hand $", "sum"),
                On_Memo_Value=("On memo $", "sum"),
                RTS_Value=("RTS $", "sum"),
            )
            .sort_values("On_Hand_Value", ascending=False)
        )

        st.dataframe(
            cust_agg.head(50).style.format({
                "On_Hand_Value": "{:,.0f}",
                "On_Memo_Value": "{:,.0f}",
                "RTS_Value": "{:,.0f}",
            }),
            use_container_width=True,
        )

# ---- Diamond Search ----
with tab_diamonds:
    st.header("Diamond Search (Reuse / Remount)")

    ddf = filtered.copy()

    # Available filters based on existing columns
    shapes = sorted(ddf["Diamond Shape"].dropna().unique()) if "Diamond Shape" in ddf.columns else []
    qualities = sorted(ddf["Diamond Quality"].dropna().unique()) if "Diamond Quality" in ddf.columns else []

    col_f1, col_f2 = st.columns(2)

    with col_f1:
        sel_shapes = st.multiselect("Diamond Shape", shapes)
        sel_qualities = st.multiselect("Diamond Quality", qualities)

        in_stock_only = st.checkbox(
            "Only show styles with inventory (On hand or On memo)",
            value=True,
        )

    with col_f2:
        # --- Diamond Size slider (coerce to numeric safely) ---
        size_lo = size_hi = None
        if "Diamond Size" in ddf.columns:
            size_series = pd.to_numeric(ddf["Diamond Size"], errors="coerce").dropna()
            if not size_series.empty:
                size_min = float(size_series.min())
                size_max = float(size_series.max())
                size_lo, size_hi = st.slider(
                    "Diamond Size range (ct)",
                    min_value=round(size_min, 3),
                    max_value=round(size_max, 3),
                    value=(round(size_min, 3), round(size_max, 3)),
                )

        # --- CTTW slider (coerce to numeric safely) ---
        cttw_lo = cttw_hi = None
        if "CTTW" in ddf.columns:
            cttw_series = pd.to_numeric(ddf["CTTW"], errors="coerce").dropna()
            if not cttw_series.empty:
                cttw_min = float(cttw_series.min())
                cttw_max = float(cttw_series.max())
                cttw_lo, cttw_hi = st.slider(
                    "CTTW range (total carat weight)",
                    min_value=round(cttw_min, 3),
                    max_value=round(cttw_max, 3),
                    value=(round(cttw_min, 3), round(cttw_max, 3)),
                )

    # Apply filters
    res = ddf.copy()

    if sel_shapes and "Diamond Shape" in res.columns:
        res = res[res["Diamond Shape"].isin(sel_shapes)]

    if sel_qualities and "Diamond Quality" in res.columns:
        res = res[res["Diamond Quality"].isin(sel_qualities)]

    # Apply numeric filters using the same coercion
    if size_lo is not None and "Diamond Size" in res.columns:
        size_series = pd.to_numeric(res["Diamond Size"], errors="coerce")
        res = res[size_series.between(size_lo, size_hi, inclusive="both")]

    if cttw_lo is not None and "CTTW" in res.columns:
        cttw_series = pd.to_numeric(res["CTTW"], errors="coerce")
        res = res[cttw_series.between(cttw_lo, cttw_hi, inclusive="both")]

    if in_stock_only:
        for c in ["On hand $", "On memo $"]:
            if c not in res.columns:
                res[c] = 0.0
        res = res[(res["On hand $"] > 0) | (res["On memo $"] > 0)]

    st.write(f"Matching styles: {len(res):,}")

    # Table of matching styles
    cols_to_show = [
        "Style no.",
        "Jewelry Category",
        "Metal Type",
        #"Vendor",
        #"Customer",
        "Diamond Shape",
        "Diamond Quality",
        "Diamond Size",
        "CTTW",
        #"Selling Price",
        #"On hand $",
        #"On memo $",
        #"RTS $",
        "Last sold date",
        "Days since last sold",
    ]
    cols_to_show = [c for c in cols_to_show if c in res.columns]

    st.dataframe(
        res[cols_to_show].style.format({
            "Selling Price": "${:,.2f}",
            "On hand $": "${:,.0f}",
            "On memo $": "${:,.0f}",
            "RTS $": "${:,.0f}",
        }),
        use_container_width=True,
    )

    # Quick visual: Price vs Diamond Size / CTTW
    st.subheader("Price vs Diamond Size / CTTW")

    hover_cols = [c for c in ["Style no.", "Jewelry Category", "Vendor"] if c in res.columns]

    # Coerce again for plotting safety
    res_plot = res.copy()
    if "Diamond Size" in res_plot.columns:
        res_plot["Diamond Size"] = pd.to_numeric(res_plot["Diamond Size"], errors="coerce")
    if "CTTW" in res_plot.columns:
        res_plot["CTTW"] = pd.to_numeric(res_plot["CTTW"], errors="coerce")

    if {"Diamond Size", "Selling Price"}.issubset(res_plot.columns):
        fig_ds = px.scatter(
            res_plot.dropna(subset=["Diamond Size", "Selling Price"]),
            x="Diamond Size",
            y="Selling Price",
            color="Diamond Shape" if "Diamond Shape" in res_plot.columns else None,
            hover_data=hover_cols or None,
            title="Selling Price vs Diamond Size",
            template="plotly_white",
        )
        st.plotly_chart(fig_ds, use_container_width=True)

    if {"CTTW", "Selling Price"}.issubset(res_plot.columns):
        fig_cttw2 = px.scatter(
            res_plot.dropna(subset=["CTTW", "Selling Price"]),
            x="CTTW",
            y="Selling Price",
            color="Diamond Shape" if "Diamond Shape" in res_plot.columns else None,
            hover_data=hover_cols or None,
            title="Selling Price vs Total Carat Weight (CTTW)",
            template="plotly_white",
        )
        st.plotly_chart(fig_cttw2, use_container_width=True)

# ---- Style Drilldown ----
with tab_drill:
    st.header("Style Drilldown")

    q = st.text_input("Search Style no.")
    if q:
        qdf = filtered[filtered["Style no."].str.contains(q.strip(), case=False, na=False)]
    else:
        qdf = filtered.head(200)

    cols_to_show = [
        "Style no.",
        "Jewelry Category",
        "Jewelry Type",
        "Metal Type",
        "Vendor",
        "Customer",
        "CTTW",
        "Selling Price",
        "Current Cost",
        "On hand $",
        "On memo $",
        "RTS $",
        "Units sold in 2022",
        "Units sold in 2023",
        "Units sold in 2024",
        "Units sold in 2025",
        "Last sold date",
        "Days since last sold",
    ]
    cols_to_show = [c for c in cols_to_show if c in qdf.columns]

    st.dataframe(
        qdf[cols_to_show].style.format({
            "Selling Price": "{:,.2f}",
            "Current Cost": "{:,.2f}",
            "On hand $": "{:,.0f}",
            "On memo $": "{:,.0f}",
            "RTS $": "{:,.0f}",
        }),
        use_container_width=True,
    )
