import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import requests
from utils.navbar import navbar

# Page config
st.set_page_config(
    page_title="Inventory Analysis",
    page_icon="🪙",
    layout="wide"
)

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

    if use_local:
        df = load_local()
    else:
        df = load_inventory()
        navbar()

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

# Department columns relevant for quantity/value computation
dept_cols = [
    "SO", "SOSTK", "PR", "PO", "POSM", "WB", "SEMI", "CNTR",
    "CAST", "QC", "LAB", "INTR", "REP", "VNDR", "SCRP", "CRET",
    "SCL", "RTS", "OM"
]

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
deps = sorted([c for c in dept_cols if c in df.columns])

#vendors = sorted(df["vendor_id"].dropna().unique()) if "vendor_id" in df.columns else []

# --- Sidebar Filters with "All" Option ---

# 1️⃣ Category filter
all_cats = ["All"] + cats
sel_cats = st.sidebar.multiselect("Category", all_cats, default=["All"])
if ("All" in sel_cats) or (not sel_cats):
    sel_cats = cats

# 2️⃣ Metal Type filter
all_metals = ["All"] + metals
sel_metals = st.sidebar.multiselect("Metal Type", all_metals, default=["All"])
if ("All" in sel_metals) or (not sel_metals):
    sel_metals = metals

# 3️⃣ Department filter
all_deps = ["All"] + deps
sel_deps = st.sidebar.multiselect("Departments", all_deps, default=["All"])
if ("All" in sel_deps) or (not sel_deps):
    sel_deps = deps
# 4️⃣ Vendor filter
#all_vendors = ["All"] + vendors
#sel_vendors = st.sidebar.multiselect("Vendor", all_vendors, default=["All"])
#if ("All" in sel_vendors) or (not sel_vendors):
#    sel_vendors = vendors``

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
if sel_deps:
    dep_num = filtered[sel_deps].apply(pd.to_numeric, errors="coerce")
    # choose > 0 to ignore negatives/returns, or != 0 to include them
    mask = dep_num.fillna(0).ne(0).any(axis=1)  # (ne(0) == != 0)
    filtered = filtered[mask]
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

available_cols = [c for c in dept_cols if c in filtered.columns]

# Coerce *all* available dept columns to numeric for correct summing
dep_all_num = filtered[available_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

# Compute total quantity and total value for the filtered subset
filtered = filtered.copy()
dep_num = filtered[sel_deps].apply(pd.to_numeric, errors="coerce").fillna(0)
filtered["total_quantity"] = dep_num.sum(axis=1)
filtered["total_value"] = filtered["total_quantity"] * filtered["total_cost"]

# ----------------------
# KPIs (No margin)
# ----------------------

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Styles", f"{len(filtered):,}")
k2.metric("Total Pieces", f"{filtered['total_quantity'].sum():,.0f}")
k3.metric("Avg Cost / Piece", f"${filtered['total_cost'].mean():,.2f}")
k4.metric("Median Cost / Piece", f"${filtered['total_cost'].median():,.2f}")
total_value = filtered["total_value"].sum()
k5.metric("Total Value", f"${total_value:,.0f}")

# ----------------------
# Tabs
# ----------------------
tab_overview, tab_value, tab_comp, tab_dept, tab_costcomp, tab_vendor, tab_pricing, tab_drill = st.tabs(
    ["Overview", "Value Analysis", "Cost Components", "Department", "Cost Composition", "Vendors", "Pricing Bands", "Style Search"]
)

# ---- Overview ----
with tab_overview:
    st.subheader("Distribution by Category & Metal")
    colA, colB = st.columns(2)
    # --- Style Category Summary ---
    if {"style_category", "total_quantity"}.issubset(filtered.columns):
        cat_summary = (
            filtered.groupby("style_category", as_index=False)
            .agg(
                Count=("style_cd", "nunique"),
                Total_Quantity=("total_quantity", "sum")
            )
            .sort_values("Total_Quantity", ascending=False)
        )
        cat_summary["Total_Quantity"] = cat_summary["Total_Quantity"].round(0).astype(int)
        colA.dataframe(
            cat_summary.style.format({"Total_Quantity": "{:,}"}),
            use_container_width=True,
        )
    else:
        colA.info("No style_category or total_quantity column found.")

    # --- Metal Type Summary ---
    if {"metal_typ", "total_quantity"}.issubset(filtered.columns):
        metal_summary = (
            filtered.groupby("metal_typ", as_index=False)
            .agg(
                Count=("style_cd", "nunique"),
                Total_Quantity=("total_quantity", "sum")
            )
            .sort_values("Total_Quantity", ascending=False)
        )
        metal_summary["Total_Quantity"] = metal_summary["Total_Quantity"].round(0).astype(int)
        colB.dataframe(
            metal_summary.style.format({"Total_Quantity": "{:,}"}),
            use_container_width=True,
        )
    else:
        colB.info("No metal_typ or total_quantity column found.")


    st.subheader("Top Styles by Value")

    styles = st.number_input(
        "Number of styles to show",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
        key="num_top_styles"
    )

    if {"total_cost", "selling_price", "total_value", "total_quantity"}.issubset(filtered.columns):
        top_styles = (
            filtered[
                [
                    "style_cd",
                    "style_category",
                    "metal_typ",
                    "total_quantity",
                    "selling_price",
                    "total_cost",
                    "total_value",
                ]
            ]
            .sort_values("total_value", ascending=False)
            .head(styles)
        )

        st.info("💡 Tip: Click any column header to sort by it.")

        st.dataframe(
            top_styles.style.format({
                "selling_price": "${:,.2f}",
                "total_cost": "${:,.2f}",
                "total_value": "${:,.0f}",
                "total_quantity": "{:,.0f}"
            }),
            use_container_width=True,
        )

    else:
        st.info("Required columns ('total_cost', 'selling_price', 'total_value', 'total_quantity') not found.")

with tab_value:
    st.header("Value Analysis")

    # --- Breakdown by Style Category ---
    cat_summary = (
        filtered.groupby("style_category")["total_value"]
        .sum()
        .reset_index()
        .sort_values("total_value", ascending=False)
    )

    fig_cat = px.bar(
        cat_summary,
        x="style_category",
        y="total_value",
        title="Total Value by Style Category",
        text_auto=".2s",
        template="plotly_white",
        height=550,
    )
    fig_cat.update_traces(textposition="outside")
    fig_cat.update_layout(
        xaxis_title="Style Category",
        yaxis_title="Total Value ($)",
        uniformtext_minsize=8,
        uniformtext_mode="hide",
    )
    st.plotly_chart(fig_cat, use_container_width=True)
    
    # --- Stacked Breakdown by Style Category and Metal Type ---
    if {"style_category", "metal_typ", "total_value"}.issubset(filtered.columns):
        cat_metal_summary = (
            filtered.groupby(["style_category", "metal_typ"], as_index=False)["total_value"]
            .sum()
            .sort_values("total_value", ascending=False)
        )

        fig_cat_metal = px.bar(
            cat_metal_summary,
            x="total_value",
            y="style_category",
            color="metal_typ",
            orientation="h",
            title="Total Value by Style Category and Metal Type",
            template="plotly_white",
        )
        
        fig_cat_metal.update_layout(
            xaxis_title="Total Value ($)",
            yaxis_title=None,
            legend_title="Metal Type",
            barmode="stack",
        )

        st.plotly_chart(fig_cat_metal, use_container_width=True)
    else:
        st.info("Required columns ('style_category', 'metal_typ', 'total_value') not found.")

# ---- Cost Components ----
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

# ---- Department Breakdown ----
with tab_dept:
    st.header("Department Breakdown")
    st.caption("Analyze total inventory value distribution across departments and style categories.")

    # --- Department Mapping ---
    dept_mapping = {
        "SO": "Sales Order",
        "SOSTK": "Sales Order Stock",
        "PR": "Production Request",
        "PO": "Purchase Order",
        "POSM": "Purchase Order Semi Mount",
        "WB": "Workbag",
        "SEMI": "Semi Mount",
        "CNTR": "Contractor",
        "CAST": "Casting",
        "QC": "QC",
        "LAB": "LAB",
        "INTR": "In Transit",
        "REP": "Repair",
        "VNDR": "Vendor",
        "SCRP": "Scrap",
        "CRET": "CRET",
        "SCL": "Sales Closeout",
        "RTS": "RTS",
        "OM": "Open Memo",
        # "TSHP": "To Ship"
    }

    # --- Determine which department columns to use ---
    available_cols = [c for c in dept_mapping.keys() if c in filtered.columns]

    # Respect the sidebar filter: use only selected departments that exist in filtered
    active_deps = [d for d in sel_deps if d in available_cols]

    if not active_deps:
        st.warning("No matching department columns found for your current selection.")
    else:
        # --- Compute Total Value per Department & Style Category ---
        dept_style_data = []
        for dept in active_deps:
            tmp = (
                filtered
                .groupby("style_category", as_index=False)
                .apply(lambda g: (pd.to_numeric(g[dept], errors="coerce").fillna(0) * g["total_cost"]).sum())
                .reset_index()
            )
            tmp.columns = ["_", "style_category", "Total Value"]
            tmp["Department"] = dept
            dept_style_data.append(tmp[["Department", "style_category", "Total Value"]])

        dept_style_df = pd.concat(dept_style_data, ignore_index=True)
        dept_style_df["Full Name"] = dept_style_df["Department"].map(dept_mapping)

        # --- Aggregate for Department Totals ---
        dept_summary = (
            dept_style_df.groupby(["Department", "Full Name"], as_index=False)["Total Value"]
            .sum()
            .sort_values("Total Value", ascending=False)
        )
        dept_summary["% of Total"] = (
            dept_summary["Total Value"] / dept_summary["Total Value"].sum() * 100
        ).round(2)

        # --- Visualization: Stacked Bar by Style Category ---
        fig_stacked = px.bar(
            dept_style_df,
            x="Total Value",
            y="Full Name",
            color="style_category",
            orientation="h",
            title="Total Value by Department (Stacked by Style Category)",
            template="plotly_white",
        )
        fig_stacked.update_layout(
            xaxis_title="Total Value ($)",
            yaxis_title=None,
            legend_title="Style Category",
            barmode="stack",
        )
        st.plotly_chart(fig_stacked, use_container_width=True)

        # --- Table Summary ---
        st.subheader("Department Summary")
        st.dataframe(
            dept_summary[["Department", "Total Value", "% of Total"]]
            .style.format({"Total Value": "${:,.0f}", "% of Total": "{:.2f}%"}),
            use_container_width=True,
        )

        # --- Legend ---
        with st.expander("View Department Legend"):
            legend_df = pd.DataFrame.from_dict(
                dept_mapping, orient="index", columns=["Full Name"]
            ).reset_index().rename(columns={"index": "Abbreviation"})
            st.dataframe(legend_df, use_container_width=True)

# ---- Cost Composition Breakdown ----
with tab_costcomp:
    st.header("Cost Composition Breakdown")

    st.caption("Interactive cost breakdown by style. Toggle cost components to see adjusted totals.")

    # --- Define columns ---
    base_cols = [
        "dept", 
        "style_cd", 
        "style_desc", 
        "total_metal_wt",
        "diamond_wt",
        "total_quantity"]
    cost_cols = [
        "metal_cost",
        "diamond_cost",
        "total_labor_cost",
        "costfor_duty1",
        "finding_cost",  # placeholder
        "image_cost",    # placeholder
    ]

    # --- Build a local working copy (no mutation) ---
    df_local = filtered.copy(deep=True)

    available_cols = [c for c in cost_cols if c in df_local.columns]

    # --- Column selector ---
    selected_costs = st.multiselect(
        "Select cost components to include in total:",
        available_cols,
        default=available_cols,
    )

    # --- Compute total dynamically (on copy only) ---
    if selected_costs:
        numeric_subset = df_local[selected_costs].select_dtypes(include=["number"])
        df_local["Total_Amount"] = numeric_subset.sum(axis=1)
    else:
        df_local["Total_Amount"] = 0

    # --- Build final display table ---
    cols_to_display = [c for c in base_cols if c in df_local.columns] + selected_costs + ["Total_Amount"]
    table = df_local[cols_to_display].copy()

    # --- Subtotals row (aligned with all columns) ---
    subtotal_values = table.select_dtypes(include=["number"]).sum()
    subtotal = pd.DataFrame([subtotal_values], columns=subtotal_values.index)
    subtotal.index = ["Subtotal"]

    # Add missing non-numeric columns with blanks (ensures same order)
    for c in table.columns:
        if c not in subtotal.columns:
            subtotal[c] = ""

    # Reorder subtotal columns to match table
    subtotal = subtotal[table.columns]

    # Place subtotal at top
    table_with_total = pd.concat([subtotal, table], ignore_index=True)


    # --- Formatting ---
    numeric_fmt = {
        "total_quantity": "{:,.0f}",
        "total_metal_wt": "{:,.2f}",
        "metal_cost": "${:,.2f}",
        "diamond_wt": "{:,.2f}",
        "diamond_cost": "${:,.2f}",
        "total_labor_cost": "${:,.2f}",
        "finding_cost": "${:,.2f}",
        "costfor_duty1": "${:,.2f}",
        "image_cost": "${:,.2f}",
        "Total_Amount": "${:,.2f}",
    }

    st.dataframe(
        table_with_total.style.format(numeric_fmt, na_rep="-"),
        use_container_width=True,
    )

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