# signet/cleaner.py
import os, re
from datetime import datetime
import pandas as pd

RENAME_MAP = {
    "LOGO": "logo", "SKU": "sku", "DESCRIPTION": "description", "NAME": "name",
    "STYLE": "style", "COST": "cost", "RETAIL": "retail", "MERCH CATEGORY": "merch_category",
    "OWNERSHIP": "ownership", "TY UNITS": "total_monthly_sales",
    "TTL OH U": "total_on_hand_units", "LY TTL OH U": "ly_total_on_hand_units",
    "Store TTL Units": "store_total_units",
}
KEEP_COLS = list(RENAME_MAP.keys())
DTYPE_MAP = {
    "sku": "string", "total_monthly_sales": "Int64", "total_on_hand_units": "Int64",
    "ly_total_on_hand_units": "Int64", "store_total_units": "Int64",
}
TEXT_COLS = ["logo","sku","description","name","style","merch_category","ownership"]

def _normalize_money(s: pd.Series) -> pd.Series:
    # Strip $, commas, spaces; coerce blanks/garbage to NaN
    s = (
        s.astype(str)
         .str.replace(r"[\$,]", "", regex=True)   # remove $ and commas
         .str.strip()
         .replace({"": None, "nan": None, "NA": None, "N/A": None})
    )
    return pd.to_numeric(s, errors="coerce")      # float64 with NaN
    # If you prefer pandas nullable float: 
    # return pd.to_numeric(s, errors="coerce").astype("Float64")

def infer_report_month(path_or_name: str) -> str:
    name = os.path.basename(path_or_name)
    m = re.search(r"(20\d{2})[-_](0[1-9]|1[0-2])", name)
    if m: return f"{m.group(1)}-{m.group(2)}"
    m2 = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[ _-]?(20\d{2})", name, re.I)
    if m2:
        mm = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
              "jul":"07","aug":"08","sep":"09","sept":"09","oct":"10","nov":"11","dec":"12"}[m2.group(1)[:3].lower()]
        return f"{m2.group(2)}-{mm}"
    return datetime.now().strftime("%Y-%m")

class SignetCleaner:
    def load_raw(self, path: str) -> pd.DataFrame:
        return pd.read_excel(path) if path.lower().endswith((".xlsx",".xls")) else pd.read_csv(path)

    def clean(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df = df_raw.copy()
        df.columns = df.columns.str.strip()
        missing = [c for c in KEEP_COLS if c not in df.columns]
        if missing: raise ValueError(f"Missing expected columns: {missing}")
        df = df[KEEP_COLS].rename(columns=RENAME_MAP)

        df["cost"] = _normalize_money(df["cost"])
        df["retail"] = _normalize_money(df["retail"])

        for col, target in DTYPE_MAP.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype(target) if target=="Int64" else df[col].astype(target)
        for c in TEXT_COLS:
            if c in df.columns: df[c] = df[c].astype("string").str.strip()

        with pd.option_context("mode.use_inf_as_na", True):
            df["margin_abs"] = (df["retail"] - df["cost"]).astype(float)
            df["margin_pct"] = (df["retail"] - df["cost"]) / df["retail"]
            denom = df["total_on_hand_units"].replace(0, pd.NA)
            df["sell_through"] = (df["total_monthly_sales"] / denom).astype(float)
        
            columns_to_fill = [
                "total_monthly_sales",
                "total_on_hand_units",
                "ly_total_on_hand_units",
                "store_total_units"
            ]
        df[columns_to_fill] = df[columns_to_fill].fillna(0).astype(int)
        df["sell_through"] = df["sell_through"].fillna(0).astype(float)
        df['sku'] = df['sku'].str.strip('.0')
            
        return df

    def dedupe_within_month(self, df: pd.DataFrame) -> pd.DataFrame:
        d = df.copy()
        d["sku_filled"] = d["sku"].fillna("")
        key = ["report_month","sku"] if not d["sku_filled"].eq("").all() else ["report_month","style","name","logo"]
        return d.drop_duplicates(subset=key, keep="last").drop(columns=["sku_filled"], errors="ignore")
