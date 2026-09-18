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
| **Frontend** | Next.js 16 / Tailwind v4 / React Force Graph 2D |
| **Intelligence** | FinBERT / HMM (hmmlearn) / scikit-learn |
| **LLM** | Ollama (local) with pluggable cloud fallback |
| **Databases** | PostgreSQL + TimescaleDB / Neo4j / Qdrant / Redis |
| **Streaming** | Redpanda (Kafka-compatible) |
| **DevOps** | Docker Compose / GitHub Actions |

## Run locally

### 1. Configure local services and credentials

Copy the template and replace the `CHANGE_ME_*` values. The backend loads its
settings at import time, so required variables must be present even when a
particular provider is not used yet.

```powershell
Copy-Item .env.example .env
```

Required service configuration:

| Setting | Needed for | Notes |
|---|---|---|
| PostgreSQL/TimescaleDB, Redis, Qdrant, Neo4j, Redpanda settings | Backend startup | Defaults in `.env.example` match `docker compose`. Replace all development passwords. |
| `FINNHUB_API_KEY` | Company news/profile ingestion | Register with Finnhub. |
| `ALPHAVANTAGE_API_KEY` | News-sentiment ingestion | Register with Alpha Vantage. |
| `FRED_API_KEY` | Macro indicator ingestion | Register with FRED. |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | Optional natural-language explanation | Start Ollama and pull the configured model, or configure `OPENAI_API_KEY` as fallback. |

No API key is needed to view the dashboard, run unit tests, or use the
in-memory graph. API keys are needed before collecting live provider data.

### 2. Start infrastructure and migrate the database

```powershell
docker compose up -d
Set-Location backend
python -m pip install -r requirements.txt
python -m alembic upgrade head
```

The initial migration is reproducible and creates the v2 relational schema,
including canonical events, multi-horizon outcomes, forecasts, and evaluation
records.

### 3. Seed the optional demo graph

The Neo4j seed graph is a **source-labelled, prior-based topology demo**. It
is useful for the TSMC pathway visualisation, but it does not supply learned
coefficients or empirical outcomes.

```powershell
$neo4jPassword = ((Get-Content .env | Where-Object { $_ -like "NEO4J_PASSWORD=*" }) -split "=", 2)[1]
Get-Content graph-seed/seed.cypher | docker exec -i stocker-neo4j cypher-shell -u neo4j -p $neo4jPassword
```

The graph deliberately marks its current edges as temporal approximations and
rigorous point-in-time backtests exclude them.

### 4. Bootstrap historical data

To compute the empirical baseline that the Market Impact Engine uses to forecast outcomes, run the bootstrap script. This downloads OHLCV data via `yfinance` for the last ~15 years and computes outcomes for 60 landmark events.

```powershell
Set-Location backend
python run_bootstrap.py
```

### 5. Run the applications

You will need four terminals to run the backend API, the background task worker (Celery), the task scheduler (Celery Beat), and the frontend UI.

**Terminal 1 (Backend API):**
```powershell
Set-Location backend
python -m uvicorn app.main:app --reload
```

**Terminal 2 (Celery Background Worker):**
```powershell
Set-Location backend
python -m celery -A app.worker.celery_app worker --loglevel=info --pool=solo
```

**Terminal 3 (Celery Beat Scheduler):**
```powershell
Set-Location backend
python -m celery -A app.worker.celery_app beat --loglevel=info
```

**Terminal 4 (Frontend UI):**
```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:3000` for the dashboard and `http://localhost:8000/docs`
for FastAPI documentation.

If the global `npm` launcher is unavailable on Windows but dependencies are
already installed, use the local Next binary instead:

```powershell
node node_modules/next/dist/bin/next dev
```

### 6. Verify

```powershell
Set-Location backend
python -m pytest tests -v --tb=short

Set-Location ../frontend
npm run build
```

## Data readiness and seeding

There are two intentionally separate types of seed material:

1. `graph-seed/seed.cypher` creates a small semiconductor graph. It is
   source-labelled but prior-based, so relationship types are channels only;
   they never determine a bullish or bearish result.
2. `backend/data/landmark_events.json` contains 60 event *candidates* marked
   `outcomes_uncollected`. It is not training data and is excluded from
   empirical calibration.

To obtain evidence-backed forecasts rather than intentional
insufficient-evidence responses, collect and verify all of the following:

- Canonical event articles with publication/source timestamps.
- Point-in-time-valid price outcomes for each affected ticker and horizon.
- Market and sector factor returns, so edge residual effects can be estimated.
- Evidence-backed relationships with source date and verification date.
- Held-out forecast/outcome pairs for reliability calibration.

Do **not** manually fill historical coefficients or returns. The application
uses a documented direction-neutral prior when comparable observations are
insufficient, lowers confidence, exposes sample count, and flags the result.

## Statistical scope

StockER is a probabilistic, historically calibrated system for identifying and
forecasting *potential* multi-hop market effects using historical evidence,
market context, and an evidence-backed causal graph. It does not claim to
predict all cascading effects. Probability of an outcome and reliability of
that estimate are reported separately.

## Project Structure

```
stockER/
├── backend/          # Python FastAPI — API + Intelligence Core
├── frontend/         # Next.js 16 — Dashboard UI
├── graph-seed/       # Neo4j initial data (companies, supply chains)
├── docker-compose.yml
└── .env.example
```

## License

MIT
