# 📊 Aneri Jewels — Internal BI & Product Intelligence Platform

**Built by: Rafi Khouzam · Aneri Jewels · 2025–2026**

> The central hub for Aneri Jewels' business intelligence, product data, and imagery operations. Built from scratch to replace scattered Excel sheets and Dropbox folders with a unified, automated, production-grade internal platform.

---

## 🚀 Overview

This platform serves as the **backbone of Aneri Jewels' internal BI suite** — consolidating inventory data, sales analytics, product imagery, and operational reporting into a single, always-fresh, role-gated dashboard.

Key pillars:
- **Live BI dashboards** backed by SQL with automated data refresh
- **Inventory and product management** views connected directly to the company database
- **CLIP-powered visual search** across 18,000+ clean product images
- **Image tagging pipeline** for building ML-ready datasets
- **Fully deployed** on AWS EC2 + CloudFront, used daily by internal teams

---

## 🧱 Core Features

### 📈 Business Intelligence Suite
- Multi-page Streamlit dashboard covering:
  - Sales performance and revenue breakdowns
  - Cost analysis and department-level reporting
  - Inventory levels and product availability
  - Style-level data enriched with imagery and metadata
- **Role-based authentication** — different views for management vs. operations vs. QA teams
- All data views are **live and automatically refreshed** — no manual exports needed

### ⚙️ Automated Data Pipeline (SQL + Cron)
- Data updates are fully automated via:
  - **SQL stored procedures** — encapsulating transformation and aggregation logic at the database level
  - **SQL Server Agent jobs** — scheduled execution of proc chains tied to business events
  - **Cron jobs on EC2** — triggering Python sync scripts to pull, clean, and push data to the dashboard layer
- Dashboard always reflects current inventory and sales state with zero manual intervention

### 🔍 CLIP-Powered Visual Search
- Visual similarity search using OpenAI's CLIP model
- Search by image to find visually similar styles across the catalog
- Powered by FAISS with sub-second latency at 18k image scale
- Duplicate detection and low-confidence match handling included

### 🧹 Image Cleanup & Cataloging Pipeline
- Processed and renamed **60,000+ raw product images** using:
  - Regex matching on `style_cd`, `vendor_sku`, and image suffix patterns
  - Deduplication and quality filtering logic
- Output: **~18,000 clean, reliable white-background product images**, organized by category:
  - `anklets`, `bangles`, `bracelets`, `box_sets`, `earrings`, `necklaces`, `pendants`, `rings`

### 🏷️ Manual Tagging Interface
- Streamlit-based tagging UI for internal QA teams
- Dropdown-only inputs to enforce consistent metadata
- Session locking, autosave, progress tracking, and a team leaderboard
- Backed by S3 for image delivery; persists to CSV/SQL

### 🧠 Metadata Enrichment
- Consolidated style-level metadata from multiple internal sources
- Final schema includes: `style_cd`, `style_description`, `metal_color`, `center_stone`, `style_category`, `ring_type`, `chain_type`, `collection`, and more
- Every cleaned image is mapped to its full metadata record — enabling search, clustering, and downstream ML tasks

---

## ⚙️ Tech Stack

| Layer | Tools |
|---|---|
| **Frontend** | Streamlit multipage app |
| **Backend** | FastAPI microservices |
| **Data Automation** | SQL stored procedures, SQL Server Agent, cron (Linux), Python sync scripts |
| **Infrastructure** | AWS EC2, S3, CloudFront, Linux (systemd) |
| **ML / Search** | OpenAI CLIP, FAISS vector index |
| **Auth** | Role-based session auth (Streamlit) |
| **Data** | Pandas, NumPy, regex pipelines, CSV + SQL |
| **DevOps** | Git (3 branches, 5 releases), SSH/SCP, bash scripting |

---

## 🗂️ Folder Structure

```
📁 pages/          # Streamlit multi-page routes (BI views, search, tagging)
📁 utils/          # Shared helpers: DB connectors, S3 loaders, auth logic
📄 Home.py         # Main Streamlit entry point + auth gate
📄 streamlit_auth.py   # Role-based access control
```

---

## 👥 Contributors

- **Rafi Khouzam** — Sole architect and developer. Designed the full system from data model through deployment: SQL automation, backend services, ML infra, and frontend.
- **India Back Office Tagging Team** — Manual QA and tagging support

---

## 🏁 Status

✅ **Live in production** (EC2 + CloudFront)  
✅ **Used daily** by internal operations and QA teams  
✅ **18,000+ tagged and searchable product images**  
✅ **Fully automated data refresh** — no manual exports or updates  
⏳ **Ongoing:** auto-tagging via embeddings, generative model integration, vendor onboarding pipeline
