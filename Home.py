import streamlit as st
from streamlit_auth import require_login, logout

st.set_page_config(page_title="Aneri Dashboard", layout="wide")

require_login()
user = st.session_state["user"]
role = st.session_state["role"]

st.sidebar.write(f"User — {user}")

# ----- Catalog: path, title, allowed_roles (empty => everyone), icon (optional)
page_roles = {
    "00_Signet_Sales.py": ["sales"],
    "01_Customer_Sales_Analysis.py": ["admin"],
    "05_Ecommerce_Dashboard.py": ["sales"],
    "06_Ecomm_Analysis_SQL.py": ["sales"],
    "10_Slow_Memo_Analysis.py": ["sales"],
    "11_Inventory_Analysis.py": ["admin"],
    "12_Testing.py": ["admin"],
    "15_Stock_Aging.py": ["admin"],
    "20_Image_Lookup.py": [],
    "21_Image_Upload_Search.py": [],
}

# ----- Catalog: path, title, allowed_roles (empty => everyone), icon (optional)
catalog = [
    ("pages/00_Signet_Sales.py",         "Signet Sales",            ["sales"],   "🧾"),
    ("pages/01_Customer_Sales_Analysis.py","Customer Sales Analysis",  ["admin"],   "🪙"),
    ("pages/05_Ecommerce_Dashboard.py",  "Ecommerce Dashboard",     ["admin"],   "📊"),
    ("pages/06_Ecomm_Analysis_SQL.py",   "Ecommerce SQL Analysis",  ["admin"],   "🛒"),
    ("pages/10_Slow_Memo_Analysis.py",   "Slow Memo Analysis",      ["sales"],   "🐢"),
    ("pages/11_Inventory_Analysis.py",   "Inventory Analysis",      ["admin"],   "🛠️"),
    ("pages/12_Testing.py",              "Testing",                 ["admin"],   "🔍"),
    ("pages/15_Stock_Aging.py",          "Stock Aging",             ["admin"],   "📦"),
    ("pages/20_Image_Lookup.py",         "Image Lookup",            [],          "🔎"),
    ("pages/21_Image_Upload_Search.py",  "Image Upload Search",     [],          "⬆️"),
]

# ----- Filter by role (admins see everything automatically)
allowed = [
    st.Page(path, title=title, icon=icon)
    for path, title, roles, icon in catalog
    if (not roles) or (role in roles) or (role == "admin")
]

# Optional: group into sections
nav = st.navigation(allowed)   # or: st.navigation({"Analytics": allowed_basic, "Admin": allowed_admin})

nav.run()

# Sidebar
if st.sidebar.button("Logout"):
    logout()
    st.rerun()  # <- valid here because this is *outside* the callback
