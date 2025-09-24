import requests
import streamlit as st

METALPRICE_API_KEY = st.secrets.get("METALPRICE_API_KEY")

@st.cache_data(ttl=43200)  # cache for 12 hours
def get_metal_prices():
    url = f"https://api.metalpriceapi.com/v1/latest?api_key={METALPRICE_API_KEY}&base=USD&currencies=XAG,XAU,XPT,XPD"
    response = requests.get(url)
    data = response.json()
    if not data.get("success"):
        raise Exception("Failed to fetch metal prices")
    return data["rates"]
