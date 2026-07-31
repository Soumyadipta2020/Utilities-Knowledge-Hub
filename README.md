# 🔧 Utilities Knowledge Hub

> **An AI-powered enterprise chatbot for utilities companies** — combining Knowledge Graph traversal, RAG document retrieval, dataset access governance, and automated IT ticket escalation into a single intelligent interface.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web%20App-lightgrey?logo=flask)](https://flask.palletsprojects.com)
[![LangChain](https://img.shields.io/badge/LangChain-Agentic%20AI-green)](https://langchain.com)
[![NetworkX](https://img.shields.io/badge/NetworkX-Knowledge%20Graph-orange)](https://networkx.org)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-LLM%20Gateway-purple)](https://openrouter.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running Locally](#running-locally)
- [Usage](#-usage)
  - [Chat Interface](#chat-interface)
  - [Example Queries](#example-queries)
- [API Reference](#-api-reference)
- [Dataset Schema](#-dataset-schema)
- [Agent Tools](#-agent-tools)
- [Knowledge Graph Pipeline](#-knowledge-graph-pipeline)
- [Access Control Model](#-access-control-model)
- [Testing](#-testing)
- [Deployment](#-deployment)
  - [Render (Recommended)](#render-recommended)
  - [Posit Connect Cloud](#posit-connect-cloud)
- [Configuration Reference](#-configuration-reference)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌐 Overview

The **Utilities Knowledge Hub** is an enterprise-grade AI chatbot designed for utilities companies (gas, heating, energy services). It serves as a unified knowledge portal for project teams — enabling them to:

- **Troubleshoot** equipment faults and boiler error codes using a semantically-indexed Knowledge Graph.
- **Discover** enterprise datasets, data lineage, and Subject Matter Expert (SME) attribution.
- **Request access** to restricted operational datasets via automated IT ticket generation (ServiceNow-style).
- **Query live telemetry** metrics and business operations data with role-based access control.

The system operates in two modes:
1. **Deterministic fallback engine** — works fully offline without an LLM API key, using rule-based routing over the Knowledge Graph.
2. **LLM-augmented mode** — when an OpenRouter/OpenAI API key is provided, a LangChain-powered language model synthesizes natural language answers grounded in verified local evidence.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🕸️ **Knowledge Graph RAG** | NetworkX + LangChain `NetworkxEntityGraph` for hybrid document + graph retrieval |
| 🤖 **AI Agentic Chatbot** | LangChain-powered agent with 9 custom tools and a deterministic fallback engine |
| 🔒 **Role-Based Access Control** | `Customer / Employee / Admin` permission tiers enforced per dataset |
| 🎫 **IT Ticket Automation** | Auto-generates ServiceNow-style access request tickets (TICK-XXXX) |
| 📊 **Live Telemetry Queries** | Reads live metrics (pressure PSI, flame current, flow rate) from Excel datasets |
| 🏭 **12-Stage Pipeline Visualizer** | Interactive OEM Knowledge Base ingestion pipeline with 12 flex-expanding stage cards |
| 🗂️ **Data Lineage & SME Attribution** | Tracks which SME owns each enterprise dataset and its governance policy |
| 📈 **Installation Forecasting** | Directional boiler installation forecasts from sales pipeline conversion data |
| 💬 **Multi-Turn Conversation Memory** | Session-scoped chat history with context-aware follow-up resolution |
| 🚀 **Zero-Config Startup** | Auto-generates Excel mock datasets on first launch if files are missing |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser / Client UI                          │
│              (Single-page chat interface - index.html)          │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP / REST
┌──────────────────────▼──────────────────────────────────────────┐
│                    Flask Web Application                        │
│                         (app/main.py)                           │
│                                                                 │
│   POST /api/chat          GET /api/graph/data                   │
│   POST /api/pipeline/run  GET /                                 │
└──────────┬───────────────────────┬──────────────────────────────┘
           │                       │
┌──────────▼───────────┐  ┌────────▼──────────────────────────────┐
│   Agent Layer        │  │   Graph Data Export API               │
│  (agent_builder.py)  │  │   Nodes + Edges → JSON                │
│                      │  └───────────────────────────────────────┘
│  ┌───────────────┐   │
│  │  Deterministic│   │
│  │  Rule Engine  │   │
│  └───────┬───────┘   │
│          │           │
│  ┌───────▼───────┐   │
│  │  LangChain    │   │
│  │  LLM (opt.)   │   │
│  └───────────────┘   │
└──────────┬───────────┘
           │ Tool Calls
┌──────────▼───────────────────────────────────────────────────────┐
│                        Tools Layer (tools.py)                   │
│                                                                  │
│  query_knowledge_graph   search_knowledge_base_rag               │
│  query_graph_rag         query_live_metrics                      │
│  query_business_ops      query_metric_definitions                │
│  forecast_installations  check_data_access                       │
│  raise_access_request                                            │
└──────────┬────────────────────┬─────────────────────────────────┘
           │                    │
┌──────────▼───────────┐ ┌──────▼────────────────────────────────┐
│  KnowledgeGraphService│ │  DataService                          │
│  (graph_service.py)   │ │  (data_service.py)                    │
│                        │ │                                       │
│  NetworkX DiGraph       │ │  Live_Metrics.xlsx                   │
│  LangChain EntityGraph  │ │  Business_Operations.xlsx            │
│  Knowledge_Base.xlsx    │ │  Metadata_Access.xlsx                │
└───────────────────────┘ └───────────────────────────────────────┘
```

---

## 📂 Project Structure

```
Utilities-Knowledge-Hub/
│
├── app.py                      # Entry point (Posit Connect Cloud / gunicorn)
├── wsgi.py                     # WSGI entry point
├── Procfile                    # Heroku-style process file
├── render.yaml                 # Render.com deployment config
├── requirements.txt            # Python dependencies
├── test_app.py                 # Automated verification test suite
├── .env.example                # Environment variable template
│
└── app/
    ├── __init__.py
    ├── main.py                 # Flask app, routes, and service initialization
    ├── config.py               # Environment config, paths, and mock data bootstrap
    │
    ├── agent/
    │   ├── agent_builder.py    # LangChain executor, deterministic fallback engine, chat processor
    │   └── tools.py            # 9 custom LangChain tools with service injection
    │
    ├── services/
    │   ├── graph_service.py    # NetworkX + LangChain Knowledge Graph (RAG, traversal, hybrid search)
    │   └── data_service.py     # Excel dataset access: metrics, operations, access permissions
    │
    ├── data/
    │   ├── Knowledge_Base.xlsx       # Entity-relationship knowledge graph data
    │   ├── Live_Metrics.xlsx         # Live telemetry readings
    │   ├── Business_Operations.xlsx  # Commercial funnel data
    │   ├── Metadata_Access.xlsx      # Dataset access permission policies per role
    │   └── generate_mock_data.py     # Auto-generates all Excel datasets with realistic mock data
    │
    └── templates/
        └── index.html          # Single-page chat UI with Knowledge Graph visualisation
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Web Framework** | Flask |
| **AI / Agent** | LangChain (`langchain`, `langchain-openai`, `langchain-community`) |
| **LLM Gateway** | OpenRouter (compatible with any OpenAI-spec endpoint) |
| **Knowledge Graph** | NetworkX (`nx.DiGraph`) + LangChain `NetworkxEntityGraph` |
| **Data Storage** | Excel (`.xlsx`) via `pandas` + `openpyxl` |
| **WSGI Server** | Gunicorn |
| **Env Management** | `python-dotenv` |
| **Frontend** | Vanilla HTML/CSS/JS (single `index.html`) |

---

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- `pip` (or `uv` for faster installs)
- An **OpenRouter API key** _(optional — the app runs fully offline in deterministic mode without one)_

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/Soumyadipta2020/Utilities-Knowledge-Hub.git
cd Utilities-Knowledge-Hub
```

**2. Create and activate a virtual environment**
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

### Configuration

**1. Copy the environment variable template**
```bash
cp .env.example .env
```

**2. Edit `.env` and fill in your values**
```env
# Required for LLM-augmented mode (optional — app works without this)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Default model — any OpenRouter-compatible model ID
OPENROUTER_MODEL_NAME=openai/gpt-4o-mini

# OpenRouter API base URL
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

> **Note:** If `OPENROUTER_API_KEY` is omitted or set to the placeholder value, the application automatically falls back to the deterministic rule-based engine. All core features (Knowledge Graph, RAG, access requests, ticket generation) work fully offline.

### Running Locally

```bash
python app.py
```

The server starts at **http://127.0.0.1:5000** by default.

> On first launch, the app automatically generates all required Excel mock data files if they are missing.

---

## 💬 Usage

### Chat Interface

Navigate to `http://127.0.0.1:5000` in your browser. The single-page interface provides:

- **Executive Dark + Amber Orange Theme** — high-contrast modern interface styled with modern vector SVG icons
- **Conversational Chat Panel** — compact, gap-free message bubbles with real-time markdown formatting
- **Interactive Knowledge Graph Visualizer** — dynamic canvas explorer with cluster regions and inspectable nodes/edges
- **12-Stage Pipeline Visualizer** — flex-expanding stage cards providing no-scroll OEM Knowledge Base progress tracking
- **Role & Access Governance** — session email identification and permission tier enforcement

### Example Queries

| Query | What happens |
|---|---|
| `How do I fix an EA Error on Worcester Bosch 4000?` | RAG + Graph traversal returns error code details, components, and remedy steps |
| `Who is the SME for Sales_Funnel_Dataset?` | Graph-RAG returns SME attribution and data lineage paths |
| `What is the grid pressure PSI?` | Identifies `Live_Metrics` dataset, notifies of access restriction, offers IT ticket |
| `Yes, please raise an IT access request` | Generates `TICK-XXXX` ServiceNow-style access ticket |
| `What is sales conversion?` | Retrieves metric definition from Knowledge Base |
| `Where can I get the sales data?` | Context-aware: resolves prior conversation turn to `Business_Operations` dataset |
| `Show me installation forecast` | Returns directional installation forecast from sales pipeline |
| `What can you do?` | Returns capability overview |

---

## 📡 API Reference

### `POST /api/chat`

Send a chat message and receive an AI-grounded response.

**Request Body:**
```json
{
  "message": "How do I fix EA Error on Worcester Bosch 4000?",
  "user_email": "engineer@abc.com"
}
```

**Response:**
```json
{
  "success": true,
  "response": "🤖 ABC AI Knowledge Retrieval (Graph-RAG):\n\n...",
  "user_email": "engineer@abc.com",
  "access_required": false,
  "graph": {
    "query": "...",
    "nodes": [...],
    "edges": [...]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `message` | `string` | User's query text |
| `user_email` | `string` | User identifier (used for session scoping and ticket generation) |

---

### `POST /api/pipeline/run`

Trigger the 12-stage OEM Knowledge Base ingestion pipeline. Regenerates all mock datasets and reloads the Knowledge Graph.

**Response:**
```json
{
  "success": true,
  "title": "OEM Knowledge Base",
  "overall_progress": 100,
  "knowledge_base_updated": true,
  "stages": [
    { "id": 1, "name": "File Upload", "icon": "📥", "status": "done", "log": "..." }
  ],
  "total_nodes": 42,
  "total_edges": 85
}
```

---

### `GET /api/graph/data`

Export the full Knowledge Graph as nodes and edges for frontend rendering.

**Response:**
```json
{
  "success": true,
  "total_nodes": 42,
  "total_edges": 85,
  "nodes": [
    { "id": "EA_Error", "label": "EA_Error", "category": "Error", "icon": "⚠️", "description": "..." }
  ],
  "edges": [
    { "source": "Worcester Bosch 4000", "target": "EA_Error", "relation": "has_error_code", "details": "..." }
  ]
}
```

**Node Categories:**

| Category | Icon | Examples |
|---|---|---|
| `SME` | 👤 | David Ross, Sarah Jenkins, Marcus Vance |
| `Dataset` | 📊 | Snowflake, SAP, Sales_Funnel_Dataset |
| `Error` | ⚠️ | EA_Error, F2_Error, E9_Error |
| `Equipment` | 🔧 | Worcester Bosch 4000, Baxi Combi |
| `Metric` | 📈 | Grid Pressure, Flame Current |

---

## 📊 Dataset Schema

All datasets are stored as `.xlsx` files in `app/data/` and auto-generated on first launch.

### `Knowledge_Base.xlsx`

| Column | Type | Description |
|---|---|---|
| `source` | string | Source entity (e.g. `Worcester Bosch 4000`) |
| `relationship` | string | Edge label (e.g. `has_error_code`, `managed_by`) |
| `target` | string | Target entity (e.g. `EA_Error`) |
| `details` | string | Human-readable description of the relationship |

### `Live_Metrics.xlsx`

| Column | Description |
|---|---|
| `metric_name` | Metric identifier (e.g. `grid_pressure_psi`) |
| `value` | Current reading |
| `unit` | Unit of measurement (e.g. `PSI`, `°C`, `L/min`) |
| `status` | `Normal` / `Warning` / `Critical` |
| `description` | Human-readable metric description |

### `Business_Operations.xlsx`

| Column | Description |
|---|---|
| `dataset` | Source dataset name |
| `metric` | Metric name (e.g. `total_leads`, `net_sales`) |
| `value` | Numeric value |
| `period` | Reporting period |

### `Metadata_Access.xlsx`

| Column | Description |
|---|---|
| `user_role` | `Customer` / `Employee` / `Admin` |
| `data_source` | Dataset name |
| `access_granted` | `True` / `False` |
| `description` | Policy description |
| `reason` | Denial reason (if applicable) |

---

## 🔨 Agent Tools

The agent is equipped with **9 custom LangChain tools** defined in `app/agent/tools.py`:

| Tool | Description |
|---|---|
| `query_knowledge_graph` | Traverse NetworkX graph for boiler models, error codes, and components |
| `search_knowledge_base_rag` | RAG keyword search over Knowledge Base records |
| `query_graph_rag` | **Hybrid** Graph-RAG: combines RAG retrieval + graph traversal + LangChain triples |
| `query_live_metrics` | Fetch live telemetry readings (requires access check first) |
| `query_business_operations` | Fetch sales funnel and commercial data (requires access check first) |
| `query_metric_definitions` | Return metric definitions (leads, quotes, conversion, sales) |
| `forecast_boiler_installations` | Directional installation forecast from pipeline conversion rate |
| `check_data_access` | Validate `user_role` vs `data_source` access permission |
| `raise_access_request` | Generate a `TICK-XXXX` IT access request ticket |

---

## 🏭 Knowledge Graph Pipeline

The **12-Stage OEM Knowledge Base Harnessing Pipeline** (triggerable via `POST /api/pipeline/run`):

| Stage | Name | Description |
|---|---|---|
| 1 | 📥 File Upload | Upload and validate OEM technical manuals and datasets |
| 2 | 📑 Ingestion & Extraction | Extract text, error codes, and structured content |
| 3 | 🧹 Cleaning & Normalisation | Remove duplicates and normalise text |
| 4 | ✂️ Chunking & Segmentation | Chunk documents into semantic segments |
| 5 | 🏷️ Metadata Intelligence | Enrich metadata, SME ownership, and source attribution |
| 6 | 🔗 Entity & Relationship | Extract entities, relationships, and fault diagnostic paths |
| 7 | 🧬 Semantic Learning | Train domain embeddings and semantic context |
| 8 | 📊 EDA Intelligence | Exploratory telemetry metrics analysis |
| 9 | ✅ ML Validation & Accuracy | Validate diagnostic tree accuracy (99.4% precision) |
| 10 | 🏛️ Ontology & Governance | Apply dataset security policies and ServiceNow mapping |
| 11 | ✳️ Canonicalisation | Map duplicate entities to canonical enterprise nodes |
| 12 | 🕸️ Knowledge Graph | Build final NetworkX graph with all entities and relationships |

---

## 🔒 Access Control Model

Three-tier **Role-Based Access Control (RBAC)**:

| Role | Knowledge Base | Live Metrics | Business Operations | System Logs |
|---|---|---|---|---|
| **Customer** | ✅ Read | ❌ Denied | ❌ Denied | ❌ Denied |
| **Employee** | ✅ Read | ✅ Read | ✅ Read | ❌ Denied |
| **Admin** | ✅ Read/Write | ✅ Read/Write | ✅ Read/Write | ✅ Read/Write |

When a user without sufficient access asks about a restricted dataset, the agent:
1. Identifies the relevant dataset
2. Notifies the user of the access restriction
3. Offers to raise an IT access request on their behalf
4. Upon confirmation, generates a `TICK-XXXX` ServiceNow-style ticket

---

## 🧪 Testing

Run the full automated verification test suite:

```bash
python test_app.py
```

The suite covers:

- ✅ Knowledge Graph traversal (EA_Error entity lookup)
- ✅ RAG document retrieval (keyword scoring + substring matching)
- ✅ Hybrid Graph-RAG search
- ✅ Role-based access permission checks (Customer → denied, Employee → granted)
- ✅ Live metrics dataset query
- ✅ Business operations and metric definition queries
- ✅ End-to-end troubleshooting agent response (RAG + Graph)
- ✅ Dataset access restriction detection and IT ticket offer
- ✅ IT access ticket generation (`TICK-XXXX` format)
- ✅ Data lineage and SME attribution query
- ✅ Multi-turn conversational context resolution

**Expected output:**
```
--- 1. Testing Services ---
[PASS] RAG Search retrieved N context documents. ...
[PASS] Hybrid Graph-RAG Search retrieved context documents & graph traversal paths.
[PASS] Policy Check (Customer -> Live_Metrics): Denied as expected
[PASS] Policy Check (Employee -> Live_Metrics): Granted as expected
[PASS] Live Metrics Query: grid_pressure_psi = ...
[PASS] Business Operations and metric-definition datasets queried successfully.

--- 2. Testing Agentic Workflows ---
[PASS] RAG + Knowledge Graph query response verified.
[PASS] Dataset Access Requirement & Ticket Offer verified.
[PASS] Ticket Generation (TICK-XXXX) verified.
[PASS] ABC Enterprise Data Lineage & SME Attribution query verified.
[PASS] Multi-Turn Context Resolution verified

[SUCCESS] ALL AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!
```

---

## 🌍 Deployment

### Render (Recommended)

The repository includes a `render.yaml` for one-click deployment to [Render.com](https://render.com):

```yaml
services:
  - type: web
    name: utilities-knowledge-hub
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
```

**Steps:**
1. Fork this repository to your GitHub account.
2. Go to [Render Dashboard](https://dashboard.render.com) → **New Web Service**.
3. Connect your GitHub repo.
4. Add the following **Environment Variables** in Render:
   - `OPENROUTER_API_KEY` — your OpenRouter API key
   - `OPENROUTER_MODEL_NAME` — (optional) e.g. `openai/gpt-4o-mini`
5. Deploy — Render will use `render.yaml` automatically.

### Posit Connect Cloud

`app.py` serves as the entry point for [Posit Connect Cloud](https://connect.posit.cloud/) deployment:

```python
from app.main import app

if __name__ == "__main__":
    app.run()
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | `""` | OpenRouter (or OpenAI) API key. If unset, deterministic fallback is used. |
| `OPENROUTER_MODEL_NAME` | `openai/gpt-4o-mini` | LLM model ID for OpenRouter |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL (OpenAI-compatible) |
| `FLASK_HOST` | `127.0.0.1` | Host address for the Flask dev server |
| `FLASK_PORT` | `5000` | Port for the Flask dev server |
| `SECRET_KEY` | *(auto-generated)* | Flask session secret key |

> **Tip:** The app is fully compatible with direct OpenAI API keys. Set `OPENROUTER_API_KEY` to your `sk-...` OpenAI key and `OPENROUTER_BASE_URL` to `https://api.openai.com/v1`.

---

## 🤝 Contributing

1. **Fork** the repository.
2. **Create a feature branch**: `git checkout -b feature/my-new-feature`
3. **Make your changes** and ensure all tests pass: `python test_app.py`
4. **Commit** your changes: `git commit -m "feat: add my new feature"`
5. **Push** to your branch: `git push origin feature/my-new-feature`
6. **Open a Pull Request** — describe your change and link any related issues.

### Development Guidelines

- Follow PEP 8 style conventions.
- Add docstrings to all new functions and classes.
- Ensure `test_app.py` passes before submitting a PR.
- New agent tools should be registered in `get_all_tools()` in `tools.py`.
- New datasets should be added to both `generate_mock_data.py` and `data_service.py`.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

<div align="center">

**Built with ❤️ for the utilities industry**

[⭐ Star this repo](https://github.com/Soumyadipta2020/Utilities-Knowledge-Hub) · [🐛 Report a Bug](https://github.com/Soumyadipta2020/Utilities-Knowledge-Hub/issues) · [💡 Request a Feature](https://github.com/Soumyadipta2020/Utilities-Knowledge-Hub/issues)

</div>
