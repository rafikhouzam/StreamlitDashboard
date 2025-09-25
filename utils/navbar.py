import streamlit as st
from utils.get_metal_prices import get_metal_prices
from datetime import datetime

def navbar():
    rates = get_metal_prices()

    gold = rates.get("USDXAU", 0)
    silver = rates.get("USDXAG", 0)
    platinum = rates.get("USDXPT", 0)
    palladium = rates.get("USDXPD", 0)
    st.subheader("💰 Live Metal Prices")
    cols = st.columns(4)
    cols[0].metric("Gold (USD)", f"${gold:,.2f}")
    cols[1].metric("Silver (USD)", f"${silver:,.2f}")
    cols[2].metric("Platinum (USD)", f"${platinum:,.2f}")
    cols[3].metric("Palladium (USD)", f"${palladium:,.2f}")

    # optional: show when these were last pulled from API
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"⏱ Last updated: {last_updated} (API refreshes once daily)")
