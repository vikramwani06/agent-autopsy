# 🔍 Agent Autopsy Framework

> **"If the LLM is wrong, the autopsy is still correct."**

Post-execution semantic failure analysis for AI agent workflows. Supply a Langfuse trace ID — get a complete autopsy of what went wrong and why, even when the run was marked as successful.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](README-DOCKER.md)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone and setup
git clone <repository-url>
cd agent-autopsy
cp .env.example .env
# Edit .env with your Langfuse credentials

# Run with Docker
make run
# or
docker-compose up -d

# Access the application
# API: http://localhost:8000/docs
# UI:  http://localhost:8501
```

### Option 2: Local Development

```bash
# Install dependencies
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your Langfuse credentials

# Run the API server
uvicorn agent_autopsy.main:app --reload --port 8000

# Run the Streamlit UI (in another terminal)
cd client_app
streamlit run app.py --server.port 8501
```

### 4. Run an autopsy

```bash
curl -X POST http://localhost:8000/api/v1/autopsy \
  -H "Content-Type: application/json" \
  -d '{"provider": "langfuse", "trace_id": "your-trace-id-here"}'
```

---

## 🎯 Features

- **🔍 Silent Failure Detection**: Identifies workflows that appear successful but produce incorrect outputs
- **📊 Visual UI**: Modern Streamlit interface with metric cards and PDF downloads
- **🐳 Docker Ready**: Complete containerization with environment variable security
- **📄 Professional Reports**: 9.5/10 quality diagnostic reports with actionable insights
- **🔧 Extensible**: Add new detectors and providers without refactoring
- **🚀 Production Ready**: Health checks, monitoring, and multi-server deployment

---

## 🌐 Web Interface

The Agent Autopsy includes a modern web interface for analyzing traces:

- **Visual Summaries**: Color-coded status and severity cards
- **Interactive Reports**: Expandable sections with detailed evidence
- **PDF Downloads**: Professional formatted reports for sharing
- **Single Trace Focus**: Deep analysis one trace at a time

Access at: `http://localhost:8501` (when running locally)

---

## Architecture

```
agent_autopsy/
├── api/                  # HTTP endpoints, request/response schemas
│   ├── routes.py         # FastAPI routes (orchestration only)
│   └── schemas.py        # Pydantic request/response models
├── core/                 # Engine and domain models
│   ├── models.py         # Canonical trace representation + domain models
│   ├── engine.py         # Autopsy orchestration engine
│   └── report_generator.py  # Human-readable report generation
├── providers/            # Observability platform integrations
│   ├── base.py           # TraceProvider abstract base
│   ├── registry.py       # Provider resolution registry
│   └── langfuse_provider.py  # Langfuse implementation
├── detectors/            # Semantic failure detectors
│   ├── base.py           # FailureDetector abstract base
│   ├── registry.py       # Detector registration and execution
│   ├── state_drift.py
│   ├── silent_retry_masking.py
│   ├── false_terminal_success.py
│   └── retry_without_learning.py
├── explainers/           # Optional LLM explanation layer
│   ├── base.py           # Explainer abstract base
│   └── llm_explainer.py  # OpenAI-compatible LLM explainer
├── utils/                # Shared utilities
│   ├── diffing.py        # Value comparison and diffing
│   ├── ordering.py       # Span ordering and grouping
│   └── time_helpers.py   # Timestamp parsing and duration
├── config.py             # Central configuration (env-based)
└── main.py               # FastAPI application factory
```

---

## Design Principles

- **Post-execution only** — no runtime hooks, no interception, no retries
- **Read-only** — consumes traces, never alters execution state
- **Deterministic first** — rule-based detection; LLMs are optional and explanation-only
- **Single responsibility** — providers fetch, normalizers normalize, detectors detect
- **Extensible** — add new detectors or providers without refactoring

---

## Failure Detectors (v1)

| Detector | What It Finds |
|---|---|
| **State Drift** | Final output diverges from planning intent |
| **Silent Retry Masking** | Retries mask earlier failures without validation |
| **False Terminal Success** | Trace "succeeds" but output is empty/incomplete |
| **Retry Without Learning** | Identical retries with no corrective change |

### Adding a New Detector

1. Create a new file in `agent_autopsy/detectors/`
2. Implement the `FailureDetector` abstract base class
3. Register it in `agent_autopsy/detectors/registry.py`

---

## Adding a New Provider

1. Create a new file in `agent_autopsy/providers/`
2. Implement the `TraceProvider` abstract base class
3. Register it in `agent_autopsy/providers/registry.py`

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/autopsy` | Run an autopsy on a trace |
| `GET` | `/api/v1/health` | Health check |

### POST /api/v1/autopsy

**Request:**
```json
{
  "provider": "langfuse",
  "trace_id": "your-trace-id"
}
```

**Response:** Machine-readable result + human-readable markdown report + optional LLM narrative.

---

## LLM Explanation (Optional)

Set `LLM_ENABLED=true` in `.env` and provide an OpenAI-compatible API endpoint. The LLM generates a narrative explanation but **never influences detection results**. The autopsy is complete and correct without it.

---

## License

MIT
