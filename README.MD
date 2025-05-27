# 💎 Jewelry Image Search & Tagging Platform

Aneri Jewels · 2025  
Built by: Rafi Khouzam

## 🚀 Overview

This system powers Aneri Jewels' internal tooling for managing, searching, and tagging product images at scale. It consolidates over 60,000 raw jewelry images into a clean, organized, and searchable database — complete with auto-tagging support, manual QA interface, and deep visual search via CLIP embeddings.

> Replaces years of manual chaos with a modern, production-ready pipeline — saving time, improving accuracy, and enabling smart product discovery.

---

## 🧱 Features

### ✅ Streamlit Dashboard
- Multi-page app hosted via EC2 + CloudFront
- Searchable by:
  - Style number
  - Description
  - Category
  - Metal color
  - Collection
  - Tag status (tagged/untagged/unsure)
- Tagging interface with dropdown-based QA and optional comments
- Team-based login and leaderboard system

### 🔍 CLIP Visual Search
- Deep learning similarity search powered by OpenAI's CLIP
- Users can find visually similar styles using an anchor image
- Optimized with FAISS for fast nearest-neighbor lookups

### 🧹 Image Cleanup Pipeline
- Renames ~60,000+ raw files to match `style_cd` metadata
- Drops duplicates, incorrect matches, and outdated photos
- Organizes all usable images into category-based folders
- Final cleaned set: ~13,000 high-quality, white background images

### 🧠 Metadata Mapping
- Combines multiple legacy datasets into one clean metadata source
- Maps images to:
  - `style_cd`, `style_description`
  - `metal_color`, `center_stone`, `collection`
  - `style_category`, `ring_type`, `chain_type`, etc.
- Enables downstream analysis and automated tagging

---

## 🗂️ Folder Structure

📁 final_whitebg_renamed_clean/ ← Cleaned, categorized images
📁 dev/ ← Experimental and WIP modules
📁 pages/ ← Streamlit multipage routes
📄 app.py ← Main entry point
📄 search_index.faiss ← CLIP vector index
📄 metadata.csv ← Clean metadata with tag fields


---

## ⚙️ Tech Stack

- **Python** · Streamlit · FastAPI (internal APIs)
- **AWS**: EC2, S3, CloudFront
- **CLIP**: Visual embeddings for image similarity
- **FAISS**: High-speed nearest neighbor search
- **Pandas/Numpy**: Heavy data wrangling
- **Shell/Git**: Remote EC2 orchestration

---

## 👥 Contributors

- Rafi Khouzam — Lead engineer, architect, & dashboard dev
- India tagging team — Manual QA and tagging support

---

## 🔮 Future Ideas

- Tag suggestion engine using NLP + CLIP embeddings
- External product recommendation widget
- Automated image approval pipeline for new styles
- Pricing engine using tag-based features

---

## 🏁 Status

✅ **Live in production**  
✅ **Actively used by internal teams**  
⏳ Iterative improvements ongoing
