# StockER — Event-Driven Market Intelligence Platform

> An event-driven market intelligence platform that identifies historically similar market conditions, quantifies probable outcomes, and explains the reasoning with verifiable evidence.

## Architecture

The intelligence lives in the **Statistical Similarity Engine** and the **Causal Event Graph**. The LLM is a presentation layer — it translates structured analysis into human-readable explanations with citations. It never makes the prediction itself.

```
News / Data Feeds
       ↓
  Event Detection & Classification
       ↓
  Event Ontology (Structured Metadata)
       ↓
  Causal Event Graph (Neo4j)
       ↓
  Historical Event Database (Qdrant + TimescaleDB)
       ↓
  Statistical Similarity Engine (Hybrid Scoring)
       ↓
  Market Impact Engine (Regime-Aware)
       ↓
  LLM Explains Results (Ollama — local, private)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12+ / FastAPI / PydanticAI / Celery |
| **Frontend** | Next.js 15 / Tailwind v4 / shadcn/ui / TradingView Charts |
| **Intelligence** | FinBERT / HMM (hmmlearn) / scikit-learn |
| **LLM** | Ollama (local) with pluggable cloud fallback |
| **Databases** | PostgreSQL + TimescaleDB / Neo4j / Qdrant / Redis |
| **Streaming** | Redpanda (Kafka-compatible) |
| **DevOps** | Docker Compose / GitHub Actions |

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/stockER.git
cd stockER

# 2. Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# 3. Start all services
docker compose up -d

# 4. Start backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 5. Start frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
stockER/
├── backend/          # Python FastAPI — API + Intelligence Core
├── frontend/         # Next.js 15 — Dashboard UI
├── graph-seed/       # Neo4j initial data (companies, supply chains)
├── docker-compose.yml
└── .env.example
```

## License

MIT
