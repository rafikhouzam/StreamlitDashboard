import streamlit as st
import pandas as pd
import torch
import clip
import faiss
import requests
import numpy as np
from PIL import Image

# === Load Metadata ===
@st.cache_data
def load_metadata():
    url = "https://api.anerijewels.com/api/metadata"
    headers = {"X-API-KEY": st.secrets["API_KEY"]}
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return pd.DataFrame(res.json())

df = load_metadata()

# === Load CLIP + FAISS ===
@st.cache_resource
def load_clip_and_faiss():
    model, preprocess = clip.load("ViT-B/32", device="cpu")
    index = faiss.read_index("search_index.faiss")
    style_lookup = np.load("style_lookup.npy", allow_pickle=True)
    return model, index, style_lookup

model, faiss_index, style_lookup = load_clip_and_faiss()

# === Text Input ===
st.title("🧠 Semantic + Metadata Image Search")
query = st.text_input("Search for jewelry (e.g. 'gold teardrop earrings'):")

if query:
    # Step 1: Encode the text semantically
    tokens = clip.tokenize([query]).to("cpu")
    with torch.no_grad():
        text_embed = model.encode_text(tokens)
        text_embed /= text_embed.norm(dim=-1, keepdim=True)
        text_embed = text_embed.cpu().numpy().astype("float32")

    # Step 2: CLIP similarity search
    D, I = faiss_index.search(text_embed, k=50)
    retrieved_styles = [style_lookup[i] for i in I[0]]

    # Step 3: Scoring boost based on metadata
    def score_row(style_cd):
        row = df[df["style_cd"] == style_cd]
        if row.empty:
            return 0
        row = row.iloc[0]
        score = 0
        q = query.lower()

        if "gold" in q:
            if row["metal_color"] in ["Y", "W", "P", "R"]:
                score += 1
        if "yellow" in q and row["metal_color"] == "Y":
            score += 1
        if "white" in q and row["metal_color"] == "W":
            score += 1
        if "rose" in q and row["metal_color"] in ["P", "R"]:
            score += 1

        for keyword, cat in {
            "ring": "rings",
            "earring": "earrings",
            "bracelet": "bracelets",
            "bangle": "bangles",
            "pendant": "pendants",
            "necklace": "necklaces",
            "anklet": "anklets",
        }.items():
            if keyword in q and row["style_category"] == cat:
                score += 2

        return score

    # Step 4: Sort by metadata boost
    ranked_styles = sorted(retrieved_styles, key=score_row, reverse=True)[:10]

    # Step 5: Display results
    st.markdown("### 🔍 Top Results:")
    for style_cd in ranked_styles:
        row = df[df["style_cd"] == style_cd]
        if not row.empty:
            row = row.iloc[0]
            st.image(row["image_url"], caption=f"{style_cd} | {row['style_category']} | {row['metal_color']}")
