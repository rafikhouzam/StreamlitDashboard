
# 💎 Jewelry Image Search & Tagging Platform

**Aneri Jewels · 2025**  
Built by: Rafi Khouzam

## 🚀 Overview

This platform powers Aneri Jewels’ entire internal workflow for organizing, cleaning, tagging, and searching product images at scale. It transformed a chaotic archive of 60,000+ raw photos into a reliable, structured, and searchable dataset — complete with auto-tagging infrastructure, manual QA tools, and deep visual search powered by CLIP embeddings.

> Replaced disorganized Dropbox folders and Excel sheets with a clean, automated system that is now the foundation of Aneri’s product imagery operations.

---

## 🧱 Core Features

### ✅ Streamlit Dashboard
- Fully deployed multi-page app (EC2 + CloudFront)
- Advanced filtering by:
  - `style_cd`, `description`, `style_category`
  - `metal_color`, `collection`, `tag status`
- Manual tagging interface:
  - Dropdown-based tags only (to reduce user error)
  - Optional comment field
- Built-in session management and leaderboard for tagging QA teams

### 🔍 CLIP-Powered Visual Search
- Visual similarity search using OpenAI’s CLIP model
- Search by image to find visually similar styles
- Powered by FAISS with subsecond latency
- Duplicate and low-confidence match handling included

### 🧹 Image Cleanup & Renaming Pipeline
- Renamed over 60,000 raw product images using:
  - Strict regex matching on `style_cd`, `vendor_sku`, and other fields
  - Suffix-based filtering to isolate usable images
- Removed duplicates, bad crops, incorrect items
- Final cleaned image set: **~18,000 reliable white background images**, organized into:
  - `anklets`, `bangles`, `bracelets`, `box_sets`, `earrings`, `necklaces`, `pendants`, `rings`

### 🧠 Metadata Mapping & Enrichment
- Consolidated style-level metadata from multiple sources
- Final metadata includes:
  - `style_cd`, `style_description`, `metal_color`, `center_stone`
  - `style_category`, `ring_type`, `chain_type`, `collection`, etc.
- Mapped each cleaned image to complete metadata
- Enables image-level search, clustering, tagging, and future ML tasks

---

## 🗂️ Folder Structure

```bash
📁 pages/                         # Streamlit multi-page routes  
📄 Home.py                         # Main Streamlit entry point  
```

---

## ⚙️ Tech Stack

- **Frontend**: Streamlit multipage app (hosted on EC2, served via CloudFront)
- **Backend**: FastAPI microservices (internal use only)
- **Storage & Infra**: AWS EC2, S3, CloudFront, Linux (systemd)
- **ML Infra**: OpenAI CLIP, FAISS for vector search
- **Data**: Pandas, NumPy, regex-based filename logic, CSV pipelines
- **DevOps**: Git, SCP, SSH, bash scripting for EC2 orchestration

---

## 👥 Contributors

- **Rafi Khouzam** — Lead architect, full-stack dev, image pipeline designer  
- **India Back Office Tagging Team** — Manual QA and tagging support

---

## 🔮 Future Directions

- LoRA fine-tuning of CLIP on jewelry-specific tags  
- AI-based tag suggestion system using embeddings + NLP  
- Style-level price prediction using tags and embeddings  
- External-facing product recommendation and search widget  
- Onboarding pipeline for auto-approving new style images from vendors

---

## 🏁 Status

✅ **Live in production**  
✅ **Used daily by internal QA teams**  
✅ **13,000+ clean, tagged images**  
⏳ **Ongoing improvements (auto-tagging, generative models, search UX)**
