import streamlit as st

st.set_page_config(
    page_title="Home",
    page_icon="🏠",
    layout="wide"
)


# Configure the page
#st.set_page_config(page_title="Aneri Jewels Analytics", layout="wide")

# --- Top Section: Logo / Title ---
# Optional: Add a logo if you have one
# st.image("your_logo.png", width=300)
st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)


st.markdown(
    "<h1 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels Analytics Portal 💎</h1>",
    unsafe_allow_html=True
)

st.markdown("---")

# --- Welcome Message ---
st.subheader("Welcome to the internal analytics portal!")
st.write("""
This platform provides insights into our ecommerce performance and memo inventory management.

Use the sidebar to navigate between:
- 📦 **Ecommerce Product Performance**
- 🪙 **Slow Moving Memo Analysis**
- 🔎 **Image Lookup**
- 🔍 **Reverse Image Search**

More dashboards and features are coming soon as we expand the system.
""")

# --- Highlights / Updates Section ---
# --- Highlights / Updates Section ---
st.info("🚀 Reverse Image Search live! Upload any image to find visually similar styles using CLIP.")
st.info("🖼️ New: Results displayed in a 4-column grid for faster browsing.")
st.info("💡 Coming soon: Filters, clustering, and smarter tagging.")
st.info("For any questions or development suggestions, feel free to email me at rafi@anerijewels.com")

# Optional: future feature teaser
# st.warning("📅 Coming Soon: Style Search and Visual Lookup Tool!")

# --- Footer Divider ---
st.markdown("---")

# --- Optional: Centered Footer Text ---
st.markdown(
    "<p style='text-align: center; color: gray;'>© 2025 Aneri Jewels. All Rights Reserved.</p>",
    unsafe_allow_html=True
)