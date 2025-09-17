import streamlit as st
import requests
from PIL import Image

st.set_page_config(
    page_title="Image Upload Search",
    page_icon="🔎",
    layout="wide"
)
st.title("🔍 Reverse Image Search")

# === Upload ===
uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])

# === Search ===
if uploaded_file:
    st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)

    # Send image to API
    with st.spinner("Searching..."):
        try:
            response = requests.post(
                "https://api.anerijewels.com/api/image-search",
                files={"file": uploaded_file.getvalue()},
                headers = {"X-API-KEY": st.secrets["API_KEY"]},
                timeout=60
            )
            response.raise_for_status()
            results = response.json()["results"]

            st.subheader("Top Matches")

            max_results = 12
            cols_per_row = 4

            for i in range(0, min(len(results), max_results), cols_per_row):
                row = st.columns(cols_per_row)
                for j, col in enumerate(row):
                    if i + j < len(results):
                        result = results[i + j]
                        with col:
                            st.image(result["image_url"], caption=f'{result["style_cd"]} ({result["similarity"]:.2f})', use_container_width=True)

        except requests.exceptions.RequestException as e:
            st.error(f"API Error: {e}")
