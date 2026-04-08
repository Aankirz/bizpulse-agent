# 🫖 BizPulse AI
### Market Intelligence for Indian Small Business Owners

> *"Tell me your business. I'll tell you what's happening in your market — and what to do about it."*

BizPulse is a **multi-agent AI system** built on Google ADK + Gemini 2.5 Flash that delivers real-time market intelligence to small business owners in India. It collects your business profile, fetches live market news, generates a personalized intelligence briefing, and persists everything to AlloyDB — all through a single conversation.

---

## 🏗️ Architecture

```
User (Chat / API)
        ↓
   Root Agent (bizpulse)
        ↓
   ┌────────────────────────────────────────┐
   │  Greeter Agent                         │
   │  Collects business profile → AlloyDB   │
   └────────────────┬───────────────────────┘
                    ↓
   ┌────────────────────────────────────────┐
   │  BizPulse Workflow (SequentialAgent)   │
   │                                        │
   │  1. Research Agent                     │
   │     ├── NewsAPI (live market news)     │
   │     ├── Competitor intelligence        │
   │     └── Past briefings from AlloyDB    │
   │                                        │
   │  2. Briefing Agent                     │
   │     └── Generates personalized report  │
   │         with ALERT / HEADWINDS /       │
   │         TAILWINDS / ACTION THIS WEEK   │
   │                                        │
   │  3. Action Agent                       │
   │     └── Saves briefing + action        │
   │         to AlloyDB                     │
   └────────────────────────────────────────┘
```

---

## ✨ Features

- **Multi-Agent Coordination** — Primary agent delegates to 4 specialized sub-agents
- **Live Market Intelligence** — Real-time news via NewsAPI for your business type and city
- **Persistent Memory** — AlloyDB stores every business profile, briefing, and action item
- **Historical Context** — Second run includes trends from past briefings
- **Structured Briefing Format** — ALERT level, Headwinds, Tailwinds, Competitor Pulse, Action This Week
- **REST API** — Flask-based HTTP interface for easy integration
- **Cloud Native** — Deployed on Google Cloud Run with Vertex AI backend

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | Gemini 2.5 Flash via Vertex AI |
| Database | AlloyDB for PostgreSQL |
| News Data | NewsAPI |
| Backend | Flask + Gunicorn |
| Deployment | Google Cloud Run |
| Logging | Google Cloud Logging |

---

## 📁 Project Structure

```
bizpulse_agent_new/
├── agent.py          # All agents + tools defined here
├── main.py           # Flask API server (Cloud Run entry point)
├── __init__.py       # ADK package entry point
├── requirements.txt  # Python dependencies
├── Dockerfile        # Container configuration
├── .dockerignore     # Docker build exclusions
└── .env              # Environment variables (not committed)
```

---

## 🗄️ Database Schema

```sql
-- Business profiles
CREATE TABLE businesses (
    business_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type TEXT,
    city          TEXT,
    bestsellers   TEXT,
    daily_customers TEXT,
    biggest_challenge TEXT,
    monthly_revenue TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Intelligence briefings
CREATE TABLE briefings (
    briefing_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id   UUID REFERENCES businesses(business_id),
    alert_level   TEXT,   -- RED / YELLOW / GREEN
    briefing_text TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Action items
CREATE TABLE actions (
    action_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id   UUID REFERENCES businesses(business_id),
    action_text   TEXT,
    source        TEXT,
    status        TEXT DEFAULT 'pending',
    created_at    TIMESTAMP DEFAULT NOW()
);
```

---

## 🚀 Setup & Deployment

### Prerequisites
- Google Cloud Project with billing enabled
- AlloyDB cluster running
- Vertex AI API enabled
- NewsAPI key

### Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/bizpulse
cd bizpulse

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Fill in your values

# Run locally
python main.py
```

### Environment Variables

```bash
PROJECT_ID=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=TRUE
MODEL=gemini-2.5-flash
NEWS_API_KEY=your-newsapi-key
ALLOYDB_HOST=your-alloydb-ip
ALLOYDB_PORT=5432
ALLOYDB_DATABASE=postgres
ALLOYDB_USER=postgres
ALLOYDB_PASSWORD=your-password
```

### Deploy to Cloud Run

```bash
gcloud run deploy bizpulse \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 300 \
  --set-env-vars "PROJECT_ID=...,MODEL=gemini-2.5-flash,..."
```

---

## 📡 API Reference

### Health Check
```
GET /
```
```json
{"status": "BizPulse AI is running"}
```

### Chat
```
POST /chat
Content-Type: application/json
```

**Request:**
```json
{
  "message": "I run a chai stall in Bangalore",
  "session_id": "unique-session-id",
  "user_id": "optional-user-id"
}
```

**Response:**
```json
{
  "response": "Quick setup! Tell me:\n1. Top 2-3 items + prices...",
  "session_id": "unique-session-id",
  "user_id": "default_user"
}
```

### Multi-turn Conversation
Use the **same `session_id`** across requests to maintain conversation state:

```bash
# Turn 1
curl -X POST https://YOUR-CLOUD-RUN-URL/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I run a chai stall in Bangalore", "session_id": "s001"}'

# Turn 2 — same session_id continues the conversation
curl -X POST https://YOUR-CLOUD-RUN-URL/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Cutting chai 15rs, Masala chai 20rs. 150 customers. B. B", "session_id": "s001"}'
```

---

## 📊 Sample Briefing Output

```
BIZPULSE BRIEFING | Chai Stall | Bangalore

ALERT: YELLOW — Input costs rising, footfall stable

MARKET NEWS
- Economic Times: Tea prices up 8% YoY due to drought in Assam
- Business Standard: QSR chains expanding aggressively in Tier-1 cities
- Mint: UPI transactions at chai stalls up 34% in South India

HEADWINDS
- Milk prices up 12% in Karnataka this quarter
- Zomato/Swiggy now delivering chai from cloud kitchens at ₹12/cup
- Footpath vendor licenses under review in BBMP zones

TAILWINDS  
- Office reopening driving morning chai demand up 28%
- "Local chai" trend on Instagram — authenticity is premium
- Corporate bulk orders growing in Koramangala, Indiranagar

COMPETITOR PULSE
2 new chai chains opened in Koramangala last month. However 
3 smaller stalls shut down near MG Road due to rent hikes.

COST SIGNAL: HIGH
Your cutting chai at ₹15 has thin margins with milk at current prices.

TREND
Premiumization — customers paying ₹25-40 for "specialty chai" 
experiences. Your masala chai at ₹20 is underpriced vs market.

ACTION THIS WEEK
Raise masala chai to ₹25 and add one "special" variant at ₹30 
to test premium pricing — Indiranagar office crowd will pay it.

SAVED_ACTION: Raise masala chai price to ₹25 and pilot ₹30 special variant
```

---