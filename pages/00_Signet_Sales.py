# pages/00_Signet_Sales.py
import os
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Signet Sales", layout="wide")

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
    headers = {"X-API-KEY": API_KEY} if API_KEY else {}
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

colf1, colf2, colf3, colf4 = st.columns([1,1,1,2])
month_choice = colf1.selectbox("Month", ["All"] + months, index=(len(months) if months else 0))
logo_choice = colf2.selectbox("Logo", ["All"] + logos, index=0)
cat_choice = colf3.selectbox("Category", ["All"] + cats, index=0)
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
k5.metric("Avg Margin %", f"{avg_margin:.1f}%")

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
    st.dataframe(ms, use_container_width=True, hide_index=True)
    if not ms.empty:
        st.bar_chart(ms.set_index("report_month")[["total_sales", "on_hand"]], height=240)

# ---------- Category breakdown ----------
if {"merch_category", "total_monthly_sales"} <= set(dfv.columns):
    st.markdown("### Sales by Category")
    by_cat = (
        dfv.groupby("merch_category")["total_monthly_sales"]
            .sum()
            .sort_values(ascending=False)
    )
    st.bar_chart(by_cat, height=240)

# ---------- Top styles ----------
if {"name", "style", "total_monthly_sales"} <= set(dfv.columns):
    st.markdown("### Top Styles (by Units)")
    top_styles = (
        dfv.groupby(["name", "style", "sku"], dropna=False)["total_monthly_sales"]
           .sum()
           .sort_values(ascending=False)
           .head(25)
           .reset_index()
    )
    st.dataframe(top_styles, use_container_width=True, hide_index=True)

# ---------- Table preview + download ----------
with st.expander("Preview (first 200 rows)"):
    st.dataframe(dfv.head(200), use_container_width=True, hide_index=True)

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
