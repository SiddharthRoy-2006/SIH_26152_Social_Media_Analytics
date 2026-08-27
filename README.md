# SocialIQ Analytics — AI-Driven Social Media Intelligence Platform
**Smart India Hackathon 2026 · Problem Statement 26152 · Team NEXORA**

SocialIQ Analytics is a full-stack, AI-powered social media intelligence platform providing real-time multi-platform monitoring, sentiment & emotion analysis, predictive trend forecasting, network propagation topology, audience demographic profiling, and cross-platform narrative tracking.

---

## Quick Start (One-Click Launch)

SocialIQ includes an auto-detecting full-stack launcher that starts the FastAPI backend (port 8001) and frontend HTTP server (port 5500), probes backend readiness, and opens the dashboard in your default browser:

```powershell
# From the project root:
python run_app.py
```

- **Frontend Dashboard**: `http://127.0.0.1:5500` (or `http://localhost:5500`)
- **Backend API & Health**: `http://127.0.0.1:8001/health`
- **Interactive OpenAPI Docs**: `http://127.0.0.1:8001/docs`

---

## 6-Platform Ingestion Architecture

SocialIQ ingests social media data from 6 major platforms into a normalized `SocialRecord` schema:

| Platform | Connector | Ingestion Mechanism | Capability Status |
| :--- | :--- | :--- | :--- |
| **YouTube** | `YouTubeConnector` | YouTube Data API v3 (Search, Videos, Comments) | Live / Configurable |
| **Telegram** | `TelegramConnector` | MTProto & Public Channel Web Directory | Live / Configurable |
| **Reddit** | `RedditConnector` | OAuth2 Client Credentials & Listing API | Live / Configurable |
| **Twitter / X** | `TwitterConnector` | X API v2 Bearer Token (Recent Search) | Live / Inline Notice |
| **Instagram** | `InstagramConnector` | Meta Graph API (Business Discovery) | Meta App Review Modal |
| **Facebook** | `FacebookConnector` | Meta Graph API (Page Public Access) | Meta App Review Modal |

---

## Data Modes

The platform supports three distinct runtime data modes controlled by the `SOCIALIQ_DATA_MODE` environment variable:

1. **`demo` (Default for presentation)**: Rich simulated intelligence across all platforms and topics, enabling immediate interactive evaluation without requiring paid external API credentials.
2. **`live`**: Ingests real data through configured API connectors with automated fallback and honest status badges (`Live Real Data`, `Limited Access`, `Not Configured`, `Unavailable`).
3. **`empty`**: Honest zero-data baseline for contract and compliance testing.

---

## Testing & Quality Assurance

Run the comprehensive 51-test verification suite:

```powershell
# Run in default mode:
.\.venv\Scripts\python.exe -m pytest

# Run with demo mode enabled:
$env:SOCIALIQ_DATA_MODE="demo"; .\.venv\Scripts\python.exe -m pytest
```

---

## Core AI & Analytics Modules

- `ml/sentiment_engine.py`: Sentiment scoring, fine-grained emotion classification, chronological sentiment timeline.
- `ml/trend_engine.py`: Predictive trend scoring, momentum index, velocity calculations.
- `ml/network_engine.py`: Community detection, graph topology (nodes, edges, communities), propagation paths.
- `ml/demographic_engine.py`: Age distribution, geographical heatmaps, language breakdown, interest segmentation.
- `ml/insight_engine.py`: Automated strategic recommendations, risk alerts, growth signals.

