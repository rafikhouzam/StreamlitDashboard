# pages/00_Signet_Sales.py
import os
import pandas as pd
import streamlit as st
import requests
import altair as alt
import plotly.express as px
from utils.navbar import navbar
from streamlit_auth import require_login

require_login()

st.set_page_config(page_title="Signet Sales", layout="wide")
navbar()

# ---------- Config ----------
API_URL = "https://api.anerijewels.com/api/signet"  # FastAPI GET endpoint
API_KEY = st.secrets.get("API_KEY", None)
USE_LOCAL = st.secrets.get("USE_LOCAL_SIGNET_DATA", False)
LOCAL_PATH = st.secrets.get("LOCAL_SIGNET_PATH", "data/signet/master.parquet")

# ---------- Helpers ----------
def _to_num(s, dtype="float"):
    x = pd.to_numeric(s, errors="coerce")
    if dtype == "int":
        return x.fillna(0).astype(int)
    return x

def _ensure_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if "margin_pct" not in df.columns and {"retail", "cost"} <= set(df.columns):
        df["retail"] = _to_num(df.get("retail"))
        df["cost"] = _to_num(df.get("cost"))
        with pd.option_context("mode.use_inf_as_na", True):
            df["margin_pct"] = (df["retail"] - df["cost"]) / df["retail"]
    if "sell_through" not in df.columns and {"total_monthly_sales", "total_on_hand_units"} <= set(df.columns):
        sales = _to_num(df.get("total_monthly_sales"))
        onhand = _to_num(df.get("total_on_hand_units"))
        df["sell_through"] = (sales / onhand.replace(0, pd.NA)).astype(float)
    return df

# ---------- Data loaders ----------
@st.cache_data(show_spinner=False)
def load_signet(month: str | None = None) -> pd.DataFrame:
    """Load from API (JSON) with optional month filter."""
    headers = {
        "Authorization": f"Bearer {st.session_state['token']}",
        "X-API-KEY": st.secrets["API_KEY"]
    }    
    params = {"month": month} if month else {}
    r = requests.get(API_URL, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    return _ensure_metrics(df)

def load_signet_local(path: str) -> pd.DataFrame:
    """Load from local file or directory (parquet dataset supported)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"LOCAL_SIGNET_PATH not found: {path}")
    if os.path.isdir(path):
        df = pd.read_parquet(path)  # parquet dataset directory
    else:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".parquet", ".pq"):
            try:
                df = pd.read_parquet(path)
            except Exception:
                # last resort: try fastparquet if installed
                df = pd.read_parquet(path, engine="fastparquet")
        elif ext in (".csv", ".txt"):
            df = pd.read_csv(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            # attempt parquet then csv
            try:
                df = pd.read_parquet(path)
            except Exception:
                df = pd.read_csv(path)
    return _ensure_metrics(df)

# ---------- Load ----------
try:
    if USE_LOCAL:
        df = load_signet_local(LOCAL_PATH)
        src = f"local ({'dir' if os.path.isdir(LOCAL_PATH) else os.path.splitext(LOCAL_PATH)[1].lstrip('.')})"
    else:
        df = load_signet()
        src = "API"
    st.caption(f"Loaded **{len(df):,}** rows from **{src}**")
except Exception as e:
    st.error(f"Load error: {e}")
    st.stop()

if df.empty:
    st.info("No Signet data available yet.")
    st.stop()

# ---------- Filters ----------
months = sorted(df.get("report_month", pd.Series([], dtype=str)).dropna().unique().tolist())
logos = sorted(df.get("logo", pd.Series([], dtype=str)).dropna().unique().tolist())
cats = sorted(df.get("merch_category", pd.Series([], dtype=str)).dropna().unique().tolist())

month_choice = st.sidebar.selectbox("Month", ["All"] + months, index=(len(months) if months else 0))
logo_choice = st.sidebar.selectbox("Logo", ["All"] + logos, index=0)
cat_choice = st.sidebar.selectbox("Category", ["All"] + cats, index=0)
if not USE_LOCAL and month_choice != "All":
    # pull filtered directly from API to avoid big payloads
    df = load_signet(month_choice)

# Apply local filters
dfv = df.copy()
if logo_choice != "All":
    dfv = dfv[dfv.get("logo").eq(logo_choice)]
if cat_choice != "All":
    dfv = dfv[dfv.get("merch_category").eq(cat_choice)]
if month_choice != "All" and USE_LOCAL:
    dfv = dfv[dfv.get("report_month").eq(month_choice)]

# ---------- KPIs ----------
sales_units = _to_num(dfv.get("total_monthly_sales"), "int").sum() if "total_monthly_sales" in dfv else 0
onhand_units = _to_num(dfv.get("total_on_hand_units"), "int").sum() if "total_on_hand_units" in dfv else 0
avg_margin = float(dfv.get("margin_pct", pd.Series(dtype=float)).mean(skipna=True) or 0.0) * 100
uniq_cats = int(dfv.get("merch_category", pd.Series(dtype=object)).nunique())

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Rows", f"{len(dfv):,}")
k2.metric("Sales Units", f"{sales_units:,}")
k3.metric("On-hand Units", f"{onhand_units:,}")
k4.metric("Categories", f"{uniq_cats}")
k5.metric("Avg Signet Margin %", f"{avg_margin:.1f}%")

# ---------- Monthly summary ----------
if "report_month" in dfv.columns:
    ms = (
        dfv.groupby("report_month", dropna=True)
           .agg(
               total_sales=("total_monthly_sales", "sum"),
               on_hand=("total_on_hand_units", "sum"),
               avg_margin_pct=("margin_pct", "mean"),
           )
           .reset_index()
           .sort_values("report_month")
    )
    st.markdown("### Monthly Summary")
    st.dataframe(ms,hide_index=True)
    if not ms.empty:
        st.bar_chart(ms.set_index("report_month")[["total_sales", "on_hand"]], height=240)

# ---------- Category breakdown ----------
def render_plotly_chart(df: pd.DataFrame, label_col: str, value_col: str, title: str, key: str):
    if not ({label_col, value_col} <= set(df.columns)):
        st.info(f"Missing columns for {title}: need {label_col}, {value_col}")
        return

    agg = (
        df.groupby(label_col, dropna=False)[value_col]
          .sum()
          .reset_index()
          .sort_values(value_col, ascending=False)
    )
    #agg[label_col] = agg[label_col].fillna("Unknown")
    agg = agg[agg[value_col] != 0]


    chart_type = st.radio("Chart type", ["Bar", "Pie"], horizontal=True, key=key)

    if chart_type == "Bar":
        fig = px.bar(
            agg,
            x=label_col,
            y=value_col,
            text_auto=True,
            title=title,
            labels={label_col: label_col.replace("_", " ").title(),
                    value_col: value_col.replace("_", " ").title()},
        )
        fig.update_layout(uniformtext_minsize=8, uniformtext_mode="hide")
        st.plotly_chart(fig, width='stretch')

    else:  # Pie
        fig = px.pie(
            agg,
            names=label_col,
            values=value_col,
            title=title,
            hole=0.3,
        )
        fig.update_traces(textinfo="label+percent", hovertemplate="%{label}<br>%{value:,}")
        st.plotly_chart(fig, width='stretch')


# Units by merch_category (toggle bar/pie)
if {"merch_category", "total_monthly_sales"} <= set(dfv.columns):
    render_plotly_chart(
        df=dfv,
        label_col="merch_category",
        value_col="total_monthly_sales",
        title="Unit Sales by Merch Category",
        key="plotly_units_by_cat"
    )

# Vendor revenue by inferred style_category (toggle bar/pie)
if {"style_category", "vendor_revenue"} <= set(dfv.columns):
    render_plotly_chart(
        df=dfv,
        label_col="style_category",
        value_col="vendor_revenue",
        title="Vendor Revenue by Style Category",
        key="plotly_revenue_by_style"
    )

if {"style_category", "total_monthly_sales"} <= set(dfv.columns):
    render_plotly_chart(
        df=dfv,
        label_col="style_category",
        value_col="total_monthly_sales",
        title="Unit Sales by Style Category",
        key="plotly_units_by_style"
    )

if {"logo", "total_monthly_sales"} <= set(dfv.columns):
    st.markdown("### Unit Sales by Logo")

    agg = (
        dfv.groupby("logo", dropna=False)["total_monthly_sales"]
           .sum()
           .reset_index()
           .sort_values("total_monthly_sales", ascending=False)
    )
    agg["logo"] = agg["logo"].fillna("Unknown")
    agg = agg[agg["total_monthly_sales"] != 0]  # 👈 drop zeros

    fig = px.bar(
        agg,
        x="logo",
        y="total_monthly_sales",
        text_auto=True,
        title="Unit Sales by Logo",
        labels={
            "logo": "Logo",
            "total_monthly_sales": "Units Sold"
        },
    )
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode="hide")
    st.plotly_chart(fig, width='stretch')



import plotly.express as px

if {"style_category", "signet_gross_margin_pct"} <= set(dfv.columns):
    fig = px.box(
        dfv,
        x="style_category",
        y="signet_gross_margin_pct",
        #points="all",   # shows individual points (optional)
        title="Gross Margin % by Style Category"
    )
    
    # Custom y-axis max
    fig.update_yaxes(range=[0, 1])

    # Custom axis labels
    fig.update_layout(
        yaxis_title="Gross Margin (%)",
        xaxis_title="Style Category",
    )
    
    st.plotly_chart(fig, width='stretch')

# ---------- Top styles ----------
required = {"name", "style", "total_monthly_sales"}
group_cols = ["name", "style", "sku"]

if required <= set(dfv.columns):
    if "logo" in dfv.columns:
        group_cols.insert(0, "logo")  # put logo first in grouping

    st.markdown("### Top Styles by Units")

    agg_dict = {"total_monthly_sales": "sum"}
    if "vendor_revenue" in dfv.columns:
        agg_dict["vendor_revenue"] = "sum"

    top_styles = (
        dfv.groupby(group_cols, dropna=False)
           .agg(agg_dict)
           .sort_values("total_monthly_sales", ascending=False)
           .head(25)
           .reset_index()
           .rename(columns={
               "total_monthly_sales": "units_sold",
           })
    )

    column_config = {
        "units_sold": st.column_config.NumberColumn("Units Sold", format="%d"),
    }
    if "vendor_revenue" in top_styles.columns:
        column_config["vendor_revenue"] = st.column_config.NumberColumn("Vendor Revenue", format="$%d")

    st.dataframe(
        top_styles,
        hide_index=True,
        column_config=column_config,
    )

# ---------- Table preview + download ----------
with st.expander("Preview (first 200 rows)"):
    st.dataframe(dfv.head(200), hide_index=True)

st.download_button(
    "Download current view (CSV)",
    data=dfv.to_csv(index=False).encode("utf-8"),
    file_name="signet_current_view.csv",
    mime="text/csv",
)

# ---------- Cache control ----------
with st.sidebar:
    if st.button("🔁 Refresh data (clear cache)"):
        st.cache_data.clear()
        st.success("Cache cleared. Re-run the page.")
