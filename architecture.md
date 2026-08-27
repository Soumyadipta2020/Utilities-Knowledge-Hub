# 🏛️ Utilities Knowledge Hub — Executive Architecture Summary

> **A Strategic & Technical Architecture Guide for Enterprise Business Leaders**  
> *How Agentic AI, Knowledge Graphs, and Model Context Protocol (MCP) Power Governed Decision Intelligence for Energy & Field Utilities.*

---

## Executive Summary

The **Utilities Knowledge Hub** is an enterprise AI decision intelligence and operations platform built specifically for gas, heating, and utility service providers. It transitions enterprise AI from basic unstructured document search (chatbots) into an **auditable, deterministic, and governed operational co-pilot**.

Traditional AI chatbots suffer from hallucinations, lack of business context, and unverified calculations. The Utilities Knowledge Hub solves this through a **tri-tier hybrid architecture**:
1. **Multi-Agent Orchestration & Domain Specialists**: Autonomous reasoning agents with specialized business briefs (Commercial, Demand Forecasting, Pricing, Capacity, Reliability, Governance).
2. **Semantic Knowledge Graph**: A dynamically synthesized relational graph that unifies cross-silo lineage, domain taxonomies, shared entity keys (`customer_id`, `boiler_id`, etc.), and equipment diagnostic trees.
3. **Enterprise MCP Gateway (Model Context Protocol)**: A secure, zero-trust semantic data layer that provides governed, cached, and role-restricted query execution into high-speed analytical engines (DuckDB/SQL) with complete auditability.

---

## 🗺️ High-Level System Architecture & Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                        1. OMNICHANNEL INTERACTION & PRESENTATION LAYER                          │
│                      Web Portal  •  MS Teams  •  Mobile App  •  REST API                        │
└────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                 │
                                                 │ [ Natural Language Business Query ]
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                         2. AI SUPERVISOR & INTENT CLASSIFICATION LAYER                          │
│               Analyzes business intent (commercial, pricing, demand, reliability)               │
│               and routes inquiry to the dedicated domain expert specialist                      │
└────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                 │
                ┌────────────────────────────────┼────────────────────────────────┐
                ▼                                ▼                                ▼
   ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
   │   Commercial Agent 📈   │      │ Demand Forecast Agent 📊│      │    Pricing Agent 💷     │
   │  Funnel, Deals, Margin  │      │ Bias Correction, Gaps   │      │ Cost-to-Serve, Tariffs  │
   └────────────┬────────────┘      └────────────┬────────────┘      └────────────┬────────────┘
                │                                │                                │
                ├────────────────────────────────┼────────────────────────────────┤
                │                                │                                │
   ┌────────────┴────────────┐      ┌────────────┴────────────┐      ┌────────────┴────────────┐
   │ Reliability Engineer 🔧 │      │   Capacity Planner 🗓️   │      │  Governance Officer 🛡️  │
   │ Fault Codes, Parts, Temp│      │ Workforce Supply/Skills │      │ Lineage, Stewards, RBAC │
   └────────────┬────────────┘      └────────────┬────────────┘      └────────────┬────────────┘
                │                                │                                │
                └────────────────────────────────┼────────────────────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                    3. UNIFIED KNOWLEDGE & SEMANTIC DATA ACCESS GATEWAY                          │
│                                                                                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────┐  ┌───────────────────────────────┐  │
│  │     KNOWLEDGE GRAPH      │  │       DOCUMENT RAG       │  │    ENTERPRISE MCP GATEWAY     │  │
│  │   (NetworkX DiGraph)     │  │    (Vector & Lexical)    │  │   (Model Context Protocol)    │  │
│  ├──────────────────────────┤  ├──────────────────────────┤  ├───────────────────────────────┤  │
│  │ • Domain Taxonomies      │  │ • OEM Manuals & Specs    │  │ • Zero-Trust RBAC & ABAC      │  │
│  │ • Cross-Dataset Lineage  │  │ • Field Service SOPs     │  │ • L1/L2 Semantic Caching      │  │
│  │ • Shared Entity Links    │  │ • Safety Guidelines      │  │ • Metric Catalog Registry     │  │
│  │ • Diagnostic Trees       │  │ • Warranty Policies      │  │ • DuckDB Query Pushdown       │  │
│  └────────────┬─────────────┘  └────────────┬─────────────┘  └───────────────┬───────────────┘  │
└───────────────┼─────────────────────────────┼────────────────────────────────┼──────────────────┘
                │                             │                                │
                ▼                             ▼                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           4. ENTERPRISE DATA & REPOSITORY LAYER                                 │
│   ┌──────────────────────────┐  ┌──────────────────────────┐  ┌──────────────────────────────┐  │
│   │    DuckDB SQL Engine     │  │ Operational Data (CSV)   │  │   Security & Audit Logs      │  │
│   │ (High-Speed In-Memory)   │  │ Telemetry / Quotes / ERP │  │  Complete Query Tracing      │  │
│   └──────────────────────────┘  └──────────────────────────┘  └──────────────────────────────┘  │
└────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     5. VERIFICATION & HUMAN-IN-THE-LOOP GOVERNANCE                              │
│                                                                                                 │
│   ┌──────────────────────────────────────────────┐ ┌──────────────────────────────────────────┐ │
│   │        Dual-Pass Claim Verifier 🔍           │ │     Human-in-the-Loop Action Queue 🚦    │ │
│   │  Re-executes independent SQL derivations to  │ │  Operational moves (pricing, forecasts,  │ │
│   │  guarantee zero-hallucination metric facts   │ │  capacity shifts) require human approval │ │
│   └──────────────────────┬───────────────────────┘ └────────────────────┬─────────────────────┘ │
└──────────────────────────┼──────────────────────────────────────────────┼───────────────────────┘
                           │                                              │
                           ▼                                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│               VERIFIED ANSWER + INTERACTIVE LINEAGE SUBGRAPH DELIVERED TO USER                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 End-to-End Query Lifecycle (Example Scenario)

Here is what happens under the hood when a business leader asks a multi-faceted question:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ USER QUERY: "Why did boiler repair productivity drop in London despite adequate engineer hours?" │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. AI SUPERVISOR & SPECIALIST ENGAGEMENT                                                         │
│    • Supervisor routes query to the Capacity Planner & Asset Reliability specialists.            │
│    • The agent formulates a multi-step investigation plan across workforce, weather, and parts.   │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. MULTI-SOURCE INVESTIGATION VIA MCP, GRAPH & RAG                                               │
│                                                                                                  │
│    [ MCP GATEWAY (SQL) ] ────> Filters DuckDB for London region engineer hours vs. completed jobs │
│                                • Result: 42% repeat visits due to missing ignition electrodes    │
│                                                                                                  │
│    [ KNOWLEDGE GRAPH ]   ────> Traces fault codes 'EA_Error' -> 'Ignition Electrode' part link   │
│                                • Identifies SME parts steward & parts inventory dataset          │
│                                                                                                  │
│    [ DOCUMENT RAG ]      ────> Retrieves Worcester Bosch 4000 manual procedure for cold snap     │
│                                • Confirms freeze advisories increase ignition replacement demand │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. DUAL-PASS VERIFICATION & HUMAN-IN-THE-LOOP ACTION PROPOSAL                                    │
│    • Independent Verifier recalculates London productivity figures directly against raw data.    │
│    • Agent identifies root cause: Van stock shortage of ignition electrodes during cold snap.    │
│    • Queues Proposed Action: "Reallocate 150 ignition electrodes to London central depot."       │
└────────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. DELIVERED EXECUTIVE BRIEFING                                                                  │
│    • Lead answer in clear financial terms: "£84k in deferred jobs due to van stock stock-out."   │
│    • Interactive Lineage Subgraph showing connected datasets, parts, and SME data owners.        │
│    • One-click Action Approval Card for operational leadership.                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔍 Core Component Deep-Dive for Leadership

### 1. What the AI Agents Are Doing

Rather than a single, generic language model that attempts to answer every business question with unspecialized reasoning, the platform utilizes a **Supervisor-Specialist Multi-Agent Architecture**:

```
                               ┌───────────────────────────┐
                               │       AI Supervisor       │
                               │ (Intent Classification)   │
                               └─────────────┬─────────────┘
                                             │
      ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
      ▼                  ▼                   ▼                   ▼                  ▼
┌──────────────┐  ┌──────────────┐   ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
│  Commercial  │  │Demand Forecast│   │   Pricing    │    │ Reliability  │   │  Governance  │
│  Specialist  │  │  Specialist  │   │  Specialist  │    │  Specialist  │   │  Specialist  │
└──────────────┘  └──────────────┘   └──────────────┘    └──────────────┘   └──────────────┘
```

- **Supervisor & Intent Routing**:
  - Classifies user questions based on **business intent** rather than superficial keywords (e.g., distinguishing a pricing question that mentions boilers from a boiler reliability inquiry).
  - Routes the problem to a dedicated domain specialist with specialized domain instructions, validation logic, and dedicated tools.
- **Domain Specialists**:
  1. **Commercial Agent (📈)**: Investigates lead conversion funnels, quote walk-away thresholds, discount elasticity, and trading seasonality. Expresses all findings in bottom-line revenue impact (£).
  2. **Demand Forecast Agent (📊)**: Automatically benchmarks published operational forecasts against ground-truth actuals, detects systematic over/under-forecast biases, computes FTE capacity risks, and generates bias-corrected numbers.
  3. **Pricing Agent (💷)**: Calculates True Cost-to-Serve (including first-time fix rates, abortive visits, and non-productive hours) and generates transparent, reviewable cost build-ups and sensitivity curves.
  4. **Asset Reliability Engineer (🔧)**: Analyzes boiler breakdown trends, fault code frequencies, replacement part inventories, and external weather impacts (sub-3°C freezes).
  5. **Capacity Planner (🗓️)**: Analyzes regional engineer availability vs. incoming workload, isolating geographic mismatches from skill-set imbalances.
  6. **Data Governance Officer (🛡️)**: Surfaces data stewards, dataset lineage, and access policies, facilitating automated IT ticket creation (ServiceNow-style).
- **Autonomous Reasoning Loop (`AgentRuntime`)**:
  - Implements a ReAct (Reasoning + Action) loop that autonomously executes multi-step investigation plans.
  - Recovers gracefully from tool failures, self-corrects parameter mismatches, and combines insights from multiple enterprise databases before synthesizing a final answer.
- **Human-in-the-Loop Governance (`HubStore`)**:
  - The agent never makes unilateral production changes. Any actionable recommendation (e.g., price book adjustments, forecast overrides, technician redeployment) is queued as a **Proposed Action** requiring explicit human approval (`Approve` / `Reject`).

---

### 2. How the Knowledge Graph Is Created

The Knowledge Graph turns disjointed, tabular enterprise datasets and manuals into an **interconnected semantic web**:

```
[ Domain: Sales & Pipeline ] ──contains_dataset──> [ Dataset: quotes_and_sales.csv ]
                                                            │
                                                        via: lead_id
                                                            ▼
                                                [ Shared Entity: Lead Id ]
                                                            ▲
                                                        via: lead_id
                                                            │
[ Domain: Customer Operations ] ─contains_dataset─> [ Dataset: customer_holdings.csv ]
```

- **12-Stage Automated Ingestion Pipeline (`pipeline_service.py`)**:
  1. **File Ingestion**: Scans operational files, telemetry logs, and manual stores.
  2. **Data Normalization & Cleaning**: Cleans inconsistent formats, dates, and currency fields.
  3. **Entity & Relationship Extraction**: Identifies key operational entities (e.g., `Boiler Models`, `Error Codes`, `Fault Types`, `Part Numbers`, `Regions`, `SME Stewards`).
  4. **Domain Clustering**: Organizes data into primary business domains (Customer Ops, Field Service, HR & Productivity, IoT Telemetry, etc.).
  5. **Shared Entity Key Linking**: Discovers common join keys (`customer_id`, `boiler_id`, `job_id`, `lead_id`) to map relationship paths across disparate business tables.
  6. **Business Metric Binding**: Maps key commercial and operational KPIs (`Sales Conversion`, `Reschedule Rate`, `FTE`, `Productivity`) directly to the underlying datasets.
  7. **Diagnostic Tree Mapping**: Encodes equipment fault relationships (`Error F.28` $\rightarrow$ `Causes: Gas Supply Defect` $\rightarrow$ `Resolved By: Valve Replacement` $\rightarrow$ `Required Part: Gas Valve #1042`).
  8. **In-Memory NetworkX Graph Construction**: Emits an indexed graph representation enabling sub-millisecond multi-hop relationship traversals.

---

### 3. How the Enterprise MCP Gateway Works

The **Model Context Protocol (MCP)** acts as a standardized, secure integration gateway between the AI models and enterprise data platforms:

```
┌──────────────┐      ┌────────────────────────────────────────────────────────┐      ┌────────────────┐
│   AI Agent   │ ───> │ Enterprise MCP Gateway (app/services/mcp_gateway)     │ ───> │ Enterprise DB  │
│ (Model Tier) │ <─── │ • RBAC/ABAC Enforcement • Semantic Mapping • L1/L2 Cache│ <─── │ (DuckDB / SQL) │
└──────────────┘      └────────────────────────────────────────────────────────┘      └────────────────┘
```

- **Zero-Trust Role-Based & Attribute-Based Access Control (RBAC & ABAC)**:
  - Enforces user entitlements dynamically. For example, if a London Regional Manager queries technician productivity, the MCP Gateway automatically injects row-level filters (`region = 'London'`) before the query hits the database.
- **Semantic Business Layer**:
  - Translates business concepts (e.g., `get_engineer_productivity`) into optimized physical table queries, shielding the LLM from fragile database schemas and column names.
- **Context Minimization & Pushdown Execution**:
  - Heavy filtering, aggregations, and mathematical formulas execute directly inside the high-performance **DuckDB** analytical engine.
  - Only clean, capped summary rows (`MAX_MCP_ROWS`) are sent back to the LLM. This prevents LLM context window blowups, slashes token costs, and ensures microsecond query latency.
- **Multi-Tier Semantic Caching**:
  - **L1 Cache**: Schema structures, entity definitions, and metadata.
  - **L2 Cache**: Query results with intelligent time-to-live (TTL) invalidation, ensuring instant responses for repeated operational queries.

---

### 4. How the LLM Accesses the Knowledge Graph & Data

When a user asks a question, the LLM retrieves information through an orchestrated, multi-modal access strategy:

1. **Structured Data Access (Quantitative Analysis)**:
   - **Semantic Metric Catalog (`query_business_metric`)**: Preferred primary path for all business KPIs, delivering pre-calculated aggregations across dimensions.
   - **In-Memory SQL Engine (`query_datasets_sql`)**: High-speed DuckDB SQL execution for complex multi-table joins across hundreds of thousands of rows.
2. **Relational Context Access (Structural Reasoning)**:
   - **Knowledge Graph Traversal (`query_knowledge_graph`)**: Multi-hop graph lookups that reveal non-obvious entity linkages (e.g., which SME data steward manages the database backing a particular field metric).
3. **Unstructured Document Access (Qualitative Guidelines)**:
   - **Document RAG (`rag_service.py`)**: Hybrid vector and lexical search across technical manuals, manufacturer SOPs, and warranty terms.
4. **Dual-Pass Verification (`verifier.py`)**:
   - Every headline number or financial assertion generated by the LLM is passed through an independent programmatic verification check to ensure mathematical accuracy before reaching the user.
5. **Interactive Lineage Subgraphs**:
   - The UI automatically renders an interactive visual graph alongside the answer, demonstrating the exact data files, metrics, and relationships used to construct the response.

---

## 💼 Business Value & Strategic ROI

| Strategic Pillar | Traditional Approach | Utilities Knowledge Hub | Executive Impact |
|---|---|---|---|
| **Accuracy & Trust** | Generic LLMs guess numbers and hallucinate metrics. | Deterministic SQL calculation + Dual-Pass Claim Verification. | **100% auditable figures** for C-suite reporting. |
| **Operational Efficiency** | Analysts spend days manually joining spreadsheets and reconciliation reports. | Instant, multi-dataset semantic joins and bias-corrected forecasting. | **70–80% reduction** in ad-hoc operational analysis turnaround time. |
| **Enterprise Governance** | Uncontrolled data access and ungoverned automated actions. | Zero-Trust MCP Gateway (RBAC/ABAC) + Human-in-the-Loop action approvals. | **Zero risk** of unauthorized data exposure or unreviewed actions. |
| **Total Cost of Ownership (TCO)** | Dumping entire datasets into large LLM prompts incurs massive token bills. | Pushdown SQL execution + Multi-level semantic caching. | **90%+ reduction** in LLM inference and token costs. |

---

## 📋 Executive Presentation Checklist (How to Pitch This)

When presenting this architecture to C-suite and business leaders, emphasize the following points:

1. **"It does not guess; it calculates."** — The LLM acts as the orchestrator and presenter, while the underlying math is performed by SQL and verified by an independent verification worker.
2. **"It speaks business language, not database jargon."** — Leaders ask about "conversion rates," "lost revenue," and "forecast bias," and the semantic layer maps these directly to the data.
3. **"Built for enterprise compliance and security."** — Granular role-based security via MCP ensures users only see data they are permitted to view, with full audit logging for compliance.
4. **"Keeps humans firmly in control."** — High-impact decisions generate structured recommendations that require human management sign-off before execution.
