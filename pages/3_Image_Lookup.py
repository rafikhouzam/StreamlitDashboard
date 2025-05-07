import streamlit as st

st.set_page_config(
    page_title="Image Lookup",
    page_icon="🔎",
    layout="wide"
    )

st.title("Image Lookup")

st.markdown("""
👋 This tool is under construction.

Soon, you'll be able to:
- Search for product images by style number
- Search for products just by description

Thanks for your patience!
""")
st.sidebar.markdown(
    "<h2 style='text-align: center; color: #4B0082;'>💎 Aneri Jewels 💎</h2>",
    unsafe_allow_html=True
)

# Disabled input fields and button
st.text_input(
    "Search by Style Number or Description", 
    placeholder="'e.g. R123456', '14K Engagement Ring Halo Oval'", 
    disabled=True)
st.button("Search", disabled=True)