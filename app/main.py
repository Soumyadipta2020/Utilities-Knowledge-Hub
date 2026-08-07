"""
Main Entry Point for Utilities Knowledge Hub Flask Web Application.
"""

from flask import Flask, jsonify, render_template, request, session
import pandas as pd
from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from pathlib import Path
import sys
import threading

# Add project root to python path to ensure imports work seamlessly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import (
    FLASK_HOST,
    FLASK_PORT,
    SECRET_KEY,
    TEMPLATES_DIR,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL_NAME,
    OPENROUTER_BASE_URL,
    DATA_DIR,
)
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.services.pipeline_service import KnowledgeHarnessingPipeline
from app.agent.tools import register_services
from app.agent.agent_builder import (
    build_agent_executor,
    process_chat_message,
    suggest_graph_relationship,
)

# Initialize Flask App
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=1024 * 1024,
)

# Ensure datasets are generated locally
if not (DATA_DIR / "customer_master.csv").exists():
    print("Local datasets not found. Generating...")
    try:
        from scripts.generate_datasets import generate_all_datasets
        generate_all_datasets(str(DATA_DIR))
    except Exception as e:
        print(f"Failed to generate datasets: {e}")

# Initialize Services & Inject dependencies into tools
graph_service = KnowledgeGraphService(DATA_DIR)
data_service = DataService(DATA_DIR)
pipeline_engine = KnowledgeHarnessingPipeline(DATA_DIR, graph_service, data_service)
register_services(graph_service, data_service)

# Build LangChain executor (if OpenRouter API key exists)
agent_executor = build_agent_executor(OPENROUTER_API_KEY, OPENROUTER_MODEL_NAME, OPENROUTER_BASE_URL)

# Privacy-safe, runtime-only security telemetry. Raw email addresses and query
# text are intentionally excluded. Production should replace this with an
# immutable, access-controlled audit store.
DATA_ACCESS_EVENTS = deque(maxlen=2000)
DATA_ACCESS_EVENTS_LOCK = threading.Lock()
DEFAULT_SECRET_KEY = "utilities-knowledge-hub-secret-key-2026"

# Illustrative historical baseline for the executive security demonstration.
# Live chat and preview activity is added to these values at runtime.
DEMO_ACCESS_BASELINE = [
    {"dataset": "customer_master", "touches": 184, "unique_users": 42, "access_requests": 18, "escalated": 4, "minutes_ago": 7},
    {"dataset": "boiler_telemetry_logs", "touches": 129, "unique_users": 31, "access_requests": 23, "escalated": 9, "minutes_ago": 12},
    {"dataset": "repair_history", "touches": 96, "unique_users": 27, "access_requests": 12, "escalated": 3, "minutes_ago": 19},
    {"dataset": "engineer_skill", "touches": 77, "unique_users": 19, "access_requests": 8, "escalated": 2, "minutes_ago": 28},
    {"dataset": "quotes_and_sales", "touches": 61, "unique_users": 16, "access_requests": 6, "escalated": 1, "minutes_ago": 41},
    {"dataset": "regional_demand_forecast", "touches": 54, "unique_users": 14, "access_requests": 5, "escalated": 1, "minutes_ago": 55},
]
DEMO_UNIQUE_PEOPLE = 73


def _matched_dataset_names(response_graph: dict) -> list[str]:
    """Return unique dataset filenames found in query lineage."""
    matched_sources = []
    seen_filenames = set()
    for node in response_graph.get("nodes", []):
        node_id = str(node.get("id", ""))
        if not node_id.startswith("Dataset: "):
            continue
        filename = node_id.replace("Dataset: ", "", 1)
        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)
        matched_sources.append(filename)
    return matched_sources


def _normalize_dataset_name(dataset: str) -> str:
    """Align local filenames and enterprise storage catalog dataset names."""
    name = Path(str(dataset)).name.strip()
    return name[:-4] if name.casefold().endswith(".csv") else name


def _infer_access_datasets(
    user_message: str,
    agent_response: str,
    response_graph: dict,
) -> list[str]:
    """Map chat access workflows to the enterprise storage catalog."""
    datasets = [_normalize_dataset_name(name) for name in _matched_dataset_names(response_graph)]
    combined = f"{user_message} {agent_response}".casefold()
    aliases = [
        (("live_metrics", "telemetry", "pressure", "flame", "outage"), "boiler_telemetry_logs"),
        (("business_operations", "sales funnel", "commercial operational"), "quotes_and_sales"),
        (("repair", "fault"), "repair_history"),
        (("engineer skill", "skill matrix"), "engineer_skill"),
        (("regional demand", "capacity forecast"), "regional_demand_forecast"),
    ]
    for terms, mapped_dataset in aliases:
        if any(term in combined for term in terms) and mapped_dataset not in datasets:
            datasets.append(mapped_dataset)
    return datasets


def _user_fingerprint(user_email: str) -> str:
    """Create a stable, non-reversible runtime identifier for unique-user counts."""
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        user_email.strip().casefold().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:12]


def _record_data_access_activity(
    user_email: str,
    user_message: str,
    agent_response: str,
    response_graph: dict,
    access_required: bool,
) -> None:
    """Record privacy-safe dataset touch activity for the security dashboard."""
    datasets = _infer_access_datasets(user_message, agent_response, response_graph)
    request_submitted = (
        "access escalation procedure initiated" in agent_response.casefold()
        or "tick-" in agent_response.casefold()
    )
    if not datasets and (access_required or request_submitted):
        datasets = ["Unmapped restricted dataset"]
    if not datasets:
        return

    access_terms = {
        "access", "download", "export", "raw", "records", "sample", "show", "view", "request"
    }
    query_terms = set(user_message.casefold().replace("_", " ").split())
    event_type = "Access request" if access_required or request_submitted or access_terms.intersection(query_terms) else "Data query"
    if request_submitted:
        decision = "Request submitted"
    elif access_required:
        decision = "Escalated for confirmation"
    else:
        decision = "Observed under demo policy"
    _append_data_access_events(user_email, datasets, event_type, decision)


def _append_data_access_events(
    user_identity: str,
    datasets: list[str],
    event_type: str,
    decision: str,
) -> None:
    """Append one normalized security event per dataset."""
    timestamp = datetime.now(timezone.utc).isoformat()
    fingerprint = _user_fingerprint(user_identity)

    with DATA_ACCESS_EVENTS_LOCK:
        for dataset in datasets:
            DATA_ACCESS_EVENTS.append({
                "timestamp": timestamp,
                "user": fingerprint,
                "dataset": _normalize_dataset_name(dataset),
                "event_type": event_type,
                "decision": decision,
            })


def _access_activity_summary() -> dict:
    """Combine seeded demo history with runtime events without exposing identities."""
    with DATA_ACCESS_EVENTS_LOCK:
        events = list(DATA_ACCESS_EVENTS)

    by_dataset: dict[str, dict] = {}
    for event in events:
        item = by_dataset.setdefault(event["dataset"], {
            "dataset": event["dataset"],
            "touches": 0,
            "unique_users": set(),
            "access_requests": 0,
            "escalated": 0,
            "last_activity": None,
        })
        item["touches"] += 1
        item["unique_users"].add(event["user"])
        if event["event_type"] == "Access request":
            item["access_requests"] += 1
        if event["decision"] == "Escalated for confirmation":
            item["escalated"] += 1
        item["last_activity"] = max(item["last_activity"] or event["timestamp"], event["timestamp"])

    live_rows = []
    for item in by_dataset.values():
        item["unique_users"] = len(item["unique_users"])
        live_rows.append(item)

    now = datetime.now(timezone.utc)
    combined: dict[str, dict] = {}
    for baseline in DEMO_ACCESS_BASELINE:
        combined[baseline["dataset"]] = {
            "dataset": baseline["dataset"],
            "touches": baseline["touches"],
            "unique_users": baseline["unique_users"],
            "access_requests": baseline["access_requests"],
            "escalated": baseline["escalated"],
            "last_activity": (now - timedelta(minutes=baseline["minutes_ago"])).isoformat(),
            "has_live_activity": False,
        }

    for live in live_rows:
        item = combined.setdefault(live["dataset"], {
            "dataset": live["dataset"],
            "touches": 0,
            "unique_users": 0,
            "access_requests": 0,
            "escalated": 0,
            "last_activity": None,
            "has_live_activity": False,
        })
        item["touches"] += live["touches"]
        item["unique_users"] += live["unique_users"]
        item["access_requests"] += live["access_requests"]
        item["escalated"] += live["escalated"]
        item["last_activity"] = max(item["last_activity"] or live["last_activity"], live["last_activity"])
        item["has_live_activity"] = True

    provider_map = {}
    for provider in globals().get("STORAGE_PROVIDERS_DATA", []):
        for dataset in provider.get("hosted_datasets", []):
            provider_map[_normalize_dataset_name(dataset)] = provider["name"]

    dataset_rows = list(combined.values())
    for item in dataset_rows:
        item["storage_provider"] = provider_map.get(item["dataset"], "Storage mapping pending")
    dataset_rows.sort(key=lambda item: (-item["touches"], item["dataset"].casefold()))

    return {
        "scope": "Seeded demonstration history plus live activity from this application process",
        "total_touches": sum(item["touches"] for item in dataset_rows),
        "unique_users": DEMO_UNIQUE_PEOPLE + len({event["user"] for event in events}),
        "access_requests": sum(item["access_requests"] for item in dataset_rows),
        "escalated": sum(item["escalated"] for item in dataset_rows),
        "datasets": dataset_rows,
        "privacy_note": "Baseline figures are illustrative. Live additions use keyed fingerprints; email addresses and query text are not stored.",
    }


@app.route("/")
def index():
    """Render main enterprise chat interface."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat_api():
    """
    API endpoint for chat interaction.
    Payload JSON:
    {
      "message": "...",
      "user_role": "Customer" | "Employee" | "Admin",
      "user_email": "..."
    }
    """
    try:
        data = request.get_json() or {}
        user_message = data.get("message", "").strip()
        user_email = data.get("user_email", "user@abc.com").strip() or "user@abc.com"

        if not user_message:
            return jsonify({"error": "Message payload cannot be empty."}), 400

        conversation_scope = f"{user_email.casefold()}"
        if session.get("conversation_scope") != conversation_scope:
            session["conversation_scope"] = conversation_scope
            session["chat_history"] = []
        chat_history = session.get("chat_history", [])

        # Run the dataset access router and grounded LLM response.
        agent_response = process_chat_message(
            user_input=user_message,
            user_email=user_email,
            executor=agent_executor,
            chat_history=chat_history,
        )

        chat_history.extend([
            {"role": "user", "content": user_message[:700]},
            {"role": "assistant", "content": agent_response[:700]},
        ])
        session["chat_history"] = chat_history[-6:]

        access_required_flag = "Dataset Access & Entitlement Check" in agent_response or "Access Escalation Procedure Initiated" in agent_response or "Dataset Access Required" in agent_response or "Access Denied" in agent_response
        response_graph = graph_service.extract_subgraph_for_query(user_message, response=agent_response)
        _record_data_access_activity(
            user_email,
            user_message,
            agent_response,
            response_graph,
            access_required_flag,
        )

        return jsonify({
            "success": True,
            "response": agent_response,
            "user_email": user_email,
            "access_required": access_required_flag,
            "graph": response_graph,
        })

    except Exception as e:
        print(f"[API Error] Exception during chat processing: {e}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500


@app.route("/api/trust/summary", methods=["GET"])
def get_trust_summary_api():
    """Return security posture without exposing credentials or personal identifiers."""
    openrouter_configured = bool(
        OPENROUTER_API_KEY
        and OPENROUTER_API_KEY != "your_openrouter_api_key_here"
        and not OPENROUTER_API_KEY.lower().startswith("replace")
    )
    flask_secret_is_default = SECRET_KEY == DEFAULT_SECRET_KEY
    provider_storage = [
        {
            "name": provider["name"],
            "status": provider["status"],
            "severity": "protected" if provider["status"] in {"Operational", "Connected"} else "warning",
            "detail": (
                f"{provider['type']} · {provider['volume']} · {provider['record_count']} records · "
                f"hosts {', '.join(provider['hosted_datasets'])}."
            ),
            "protection": provider["governance"],
            "category": provider["category"],
            "is_demonstration": True,
        }
        for provider in STORAGE_PROVIDERS_DATA
    ]

    return jsonify({
        "success": True,
        "summary": {
            "overall_status": "Demo safeguards active; production hardening required",
            "credentials": [
                {
                    "name": "OpenRouter API key",
                    "environment_variable": "OPENROUTER_API_KEY",
                    "status": "Configured" if openrouter_configured else "Not configured",
                    "severity": "protected" if openrouter_configured else "informational",
                    "detail": (
                        "Stored server-side and never returned by the security API or browser UI."
                        if openrouter_configured
                        else "No external LLM credential is loaded; the deterministic fallback is active."
                    ),
                },
                {
                    "name": "Flask session signing secret",
                    "environment_variable": "SECRET_KEY",
                    "status": "Default value in use" if flask_secret_is_default else "Custom value configured",
                    "severity": "warning" if flask_secret_is_default else "protected",
                    "detail": (
                        "Replace the repository default before deployment; it signs browser sessions."
                        if flask_secret_is_default
                        else "A custom server-side secret signs session cookies and is not exposed to the client."
                    ),
                },
            ],
            "storage": provider_storage,
            "access_activity": _access_activity_summary(),
            "protections": [
                {"name": "Server-side secret isolation", "status": "Active", "severity": "protected", "detail": "Credential values are read on the server and never included in API responses."},
                {"name": "Privacy-safe access counting", "status": "Active", "severity": "protected", "detail": "Unique-user metrics use keyed fingerprints; raw email addresses and query text are not retained in security telemetry."},
                {"name": "Dataset filename validation", "status": "Active", "severity": "protected", "detail": "Data-preview requests strip directory components and permit CSV files only."},
                {"name": "Request size limit", "status": "Active", "severity": "protected", "detail": "Incoming request bodies are limited to 1 MB."},
                {"name": "Role-based data authorization", "status": "Demo policy only", "severity": "warning", "detail": "Current DataService checks are permissive; production requires SSO-backed RBAC and dataset entitlements."},
                {"name": "Provider storage controls", "status": "Mapped", "severity": "protected", "detail": "Each enterprise storage location displays its configured IAM, encryption, masking, firewall, or audit controls from Storage & Governance."},
                {"name": "Immutable audit retention", "status": "Runtime only", "severity": "warning", "detail": "Access counters reset when the process restarts. Production requires durable, tamper-evident audit storage."},
                {"name": "TLS and secure cookies", "status": "Deployment dependent", "severity": "warning", "detail": "HTTPS termination and Secure cookies must be enabled by the production hosting environment."},
            ],
        },
    })


@app.route("/api/pipeline/run-stage/<int:stage_id>", methods=["POST", "GET"])
def run_pipeline_stage_api(stage_id: int):
    """
    Execute a specific stage (1-12) of the Knowledge Harnessing pipeline on real backend data.
    Returns calculated stage metrics, duration_ms, status, and live log.
    """
    try:
        if stage_id == 1:
            pass # mock generation logic was here

        stage_result = pipeline_engine.execute_stage(stage_id)
        harnessing_metrics = pipeline_engine.get_harnessing_metrics()

        return jsonify({
            "success": True,
            "stage": stage_result,
            "overall_progress": round((stage_id / 12) * 100),
            "harnessing_metrics": harnessing_metrics,
            "total_nodes": len(graph_service.graph.nodes),
            "total_edges": len(graph_service.graph.edges)
        })
    except Exception as e:
        print(f"[Pipeline Stage Error] Stage {stage_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/pipeline/run", methods=["POST"])
def run_pipeline_api():
    """
    API endpoint to trigger and return the 12-stage OEM Knowledge Base Harnessing pipeline.
    Runs all 12 backend stages and returns live execution results and metrics.
    """
    try:
        # mock generation logic was here

        stages = pipeline_engine.execute_full_pipeline()
        harnessing_metrics = pipeline_engine.get_harnessing_metrics()

        return jsonify({
            "success": True,
            "title": "OEM Knowledge Base",
            "overall_progress": 100,
            "knowledge_base_updated": True,
            "stages": stages,
            "harnessing_metrics": harnessing_metrics,
            "total_nodes": len(graph_service.graph.nodes),
            "total_edges": len(graph_service.graph.edges)
        })

    except Exception as e:
        print(f"[Pipeline Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/harnessing/metrics", methods=["GET"])
def get_harnessing_metrics_api():
    """
    API endpoint to return dynamic real-time Harnessing metrics for all tabs:
    Information, Knowledge, Inference, Outcome, Benchmarking, Storage.
    """
    try:
        metrics = pipeline_engine.get_harnessing_metrics()
        return jsonify({
            "success": True,
            "metrics": metrics
        })
    except Exception as e:
        print(f"[Harnessing Metrics Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dataset/sample/<path:dataset_name>", methods=["GET"])
def get_dataset_snippet_api(dataset_name: str):
    """
    API endpoint to retrieve a sample snippet (5 rows) for a given dataset name.
    Supports clean names ('customer_master') or prefixed names ('Dataset: appointment_schedule.csv').
    """
    try:
        cleaned = dataset_name.replace("Dataset:", "").replace("dataset:", "").strip()
        if not cleaned.endswith(".csv"):
            cleaned_file = cleaned + ".csv"
        else:
            cleaned_file = cleaned
            cleaned = cleaned[:-4]

        # 1. Try reading from data_service
        sample_res = data_service.get_dataset_sample(cleaned_file)
        if sample_res.get("success") and sample_res.get("sample"):
            records = sample_res["sample"]
            columns = list(records[0].keys()) if records else []
            return jsonify({
                "success": True,
                "dataset": cleaned,
                "filename": cleaned_file,
                "columns": columns,
                "rows": records,
                "total_preview_rows": len(records)
            })

        # 2. Grounded mock previews for connected enterprise datasets if CSV file is not on disk
        mock_previews = {
            "customer_master": [
                {"customer_id": "CUST-901", "account_name": "British Gas Commercial", "account_type": "Enterprise", "contact_email": "accounts@bg.co.uk", "region": "Greater London"},
                {"customer_id": "CUST-902", "account_name": "Thames Water Substation", "account_type": "Industrial", "contact_email": "ops@thameswater.co.uk", "region": "South East"},
                {"customer_id": "CUST-903", "account_name": "National Grid North", "account_type": "Transmission", "contact_email": "grid-ops@natgrid.co.uk", "region": "North West"},
                {"customer_id": "CUST-904", "account_name": "Centrica Energy Retail", "account_type": "Commercial", "contact_email": "energy@centrica.com", "region": "Midlands"},
                {"customer_id": "CUST-905", "account_name": "Scottish Power Grid", "account_type": "Distribution", "contact_email": "support@scottishpower.co.uk", "region": "Scotland"}
            ],
            "appointment_schedule": [
                {"appointment_id": "APT-1042", "engineer_id": "ENG-44", "visit_date": "2026-08-05", "slot": "Morning", "job_type": "Boiler Inspection", "status": "Scheduled"},
                {"appointment_id": "APT-1043", "engineer_id": "ENG-12", "visit_date": "2026-08-05", "slot": "Afternoon", "job_type": "Gas Leak Audit", "status": "In Progress"},
                {"appointment_id": "APT-1044", "engineer_id": "ENG-89", "visit_date": "2026-08-06", "slot": "Morning", "job_type": "Smart Meter Retrofit", "status": "Confirmed"},
                {"appointment_id": "APT-1045", "engineer_id": "ENG-03", "visit_date": "2026-08-06", "slot": "Evening", "job_type": "Heat Pump Commissioning", "status": "Assigned"},
                {"appointment_id": "APT-1046", "engineer_id": "ENG-51", "visit_date": "2026-08-07", "slot": "Morning", "job_type": "Emergency Substation Repair", "status": "Pending"}
            ],
            "boiler_telemetry_logs": [
                {"log_id": "TLM-8841", "boiler_id": "WCH-4000-A", "pressure_psi": 14.8, "flame_current_ua": 14.2, "status_code": "OK", "timestamp": "2026-08-05 14:22:01"},
                {"log_id": "TLM-8842", "boiler_id": "WCH-8000-B", "pressure_psi": 15.1, "flame_current_ua": 13.9, "status_code": "OK", "timestamp": "2026-08-05 14:22:05"},
                {"log_id": "TLM-8843", "boiler_id": "BOS-GREEN-12", "pressure_psi": 12.3, "flame_current_ua": 8.4, "status_code": "E04_WARN", "timestamp": "2026-08-05 14:22:10"},
                {"log_id": "TLM-8844", "boiler_id": "IDEAL-LOGIC-9", "pressure_psi": 16.0, "flame_current_ua": 15.0, "status_code": "OK", "timestamp": "2026-08-05 14:22:15"},
                {"log_id": "TLM-8845", "boiler_id": "BAXI-DUO-55", "pressure_psi": 14.5, "flame_current_ua": 14.1, "status_code": "OK", "timestamp": "2026-08-05 14:22:20"}
            ],
            "inventory_and_van_stock": [
                {"part_id": "PRT-3301", "part_name": "Flame Sensor Rod", "stock_qty": 42, "unit_cost_gbp": 18.50, "van_assigned": "VAN-04", "reorder_point": 10},
                {"part_id": "PRT-3302", "part_name": "Diverter Valve Actuator", "stock_qty": 18, "unit_cost_gbp": 64.00, "van_assigned": "VAN-12", "reorder_point": 5},
                {"part_id": "PRT-3303", "part_name": "Heat Exchanger Gasket", "stock_qty": 85, "unit_cost_gbp": 8.20, "van_assigned": "VAN-08", "reorder_point": 20},
                {"part_id": "PRT-3304", "part_name": "PCB Main Board v4", "stock_qty": 7, "unit_cost_gbp": 145.00, "van_assigned": "VAN-01", "reorder_point": 3},
                {"part_id": "PRT-3305", "part_name": "Pressure Relief Valve", "stock_qty": 31, "unit_cost_gbp": 22.00, "van_assigned": "VAN-15", "reorder_point": 8}
            ]
        }

        key_name = cleaned.lower()
        if key_name in mock_previews:
            records = mock_previews[key_name]
        else:
            records = [
                {"record_id": 101, "entity_name": f"{cleaned}_sample_1", "domain_category": "Operational", "governance_status": "Active", "last_updated": "2026-08-05"},
                {"record_id": 102, "entity_name": f"{cleaned}_sample_2", "domain_category": "Telemetry", "governance_status": "Active", "last_updated": "2026-08-05"},
                {"record_id": 103, "entity_name": f"{cleaned}_sample_3", "domain_category": "Governance", "governance_status": "Validated", "last_updated": "2026-08-05"},
                {"record_id": 104, "entity_name": f"{cleaned}_sample_4", "domain_category": "Operational", "governance_status": "Active", "last_updated": "2026-08-05"},
                {"record_id": 105, "entity_name": f"{cleaned}_sample_5", "domain_category": "Audit", "governance_status": "Verified", "last_updated": "2026-08-05"}
            ]

        columns = list(records[0].keys())
        return jsonify({
            "success": True,
            "dataset": cleaned,
            "filename": cleaned_file,
            "columns": columns,
            "rows": records,
            "total_preview_rows": len(records)
        })

    except Exception as e:
        print(f"[Dataset Snippet Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dataset/ownership", methods=["GET"])
@app.route("/api/dataset/ownership/<path:dataset_name>", methods=["GET"])
def get_dataset_ownership_api(dataset_name: str | None = None):
    """
    API endpoint to retrieve dataset ownership master file records.
    Returns all dataset owners if dataset_name is omitted, or specific owner metadata.
    """
    try:
        res = data_service.get_dataset_ownership(dataset_name)
        return jsonify(res)
    except Exception as e:
        print(f"[Dataset Ownership API Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


STORAGE_PROVIDERS_DATA = [
    {
        "id": "databricks_uc",
        "name": "Databricks UC Database",
        "category": "Databases & Catalogs",
        "type": "Unity Catalog / Delta Lake",
        "volume": "48.2 TB",
        "record_count": "120,000,000",
        "status": "Operational",
        "color": "#FF3621",
        "icon_class": "fa-solid fa-cubes",
        "description": "Unity Catalog metastore for enterprise Delta Lake tables, ACID transactions, and governed AI pipelines.",
        "hosted_datasets": ["boiler_master", "telemetry_logs", "engineer_productivity"],
        "governance": "Azure Entra ID, Delta Sharing, Column-Level Masking"
    },
    {
        "id": "onelake",
        "name": "Microsoft OneLake",
        "category": "Cloud Data Lakes",
        "type": "Fabric Lakehouse / Delta Parquet",
        "volume": "32.5 TB",
        "record_count": "85,000,000",
        "status": "Operational",
        "color": "#008080",
        "icon_class": "fa-solid fa-water",
        "description": "Unified SaaS data lake for Microsoft Fabric, providing multi-cloud data mesh access across utility domains.",
        "hosted_datasets": ["epc_property_data", "regional_demand_forecast", "regional_capacity_forecast"],
        "governance": "Microsoft Purview Tags, DirectLake Access Control"
    },
    {
        "id": "salesforce",
        "name": "Salesforce CRM",
        "category": "Enterprise SaaS & ERP",
        "type": "Cloud CRM / SOQL API",
        "volume": "1.8 TB",
        "record_count": "4,500,000",
        "status": "Connected",
        "color": "#00A1E0",
        "icon_class": "fa-brands fa-salesforce",
        "description": "Cloud CRM objects for customer accounts, sales opportunities, contact center logs, and commercial quotes.",
        "hosted_datasets": ["customer_master", "contact_center_interaction", "quotes_and_sales", "customer_holdings"],
        "governance": "Salesforce Shield, OAuth 2.0, Field-Level Security"
    },
    {
        "id": "workday",
        "name": "Workday HCM & Finance",
        "category": "Enterprise SaaS & ERP",
        "type": "HCM RaaS API / REST",
        "volume": "620 GB",
        "record_count": "850,000",
        "status": "Connected",
        "color": "#E28743",
        "icon_class": "fa-solid fa-user-gear",
        "description": "Enterprise workforce management, engineer shifts, skill matrix, certifications, and HR productivity metrics.",
        "hosted_datasets": ["engineer_master", "engineer_availability_and_shifts", "engineer_skill"],
        "governance": "Workday Enterprise Security, Role-Based Access"
    },
    {
        "id": "sap",
        "name": "SAP S/4HANA ERP",
        "category": "Enterprise SaaS & ERP",
        "type": "ERP Core / OData Gateway",
        "volume": "14.8 TB",
        "record_count": "28,000,000",
        "status": "Connected",
        "color": "#0FAEFF",
        "icon_class": "fa-solid fa-boxes-stacked",
        "description": "Enterprise ERP system hosting material master, van inventory stock, parts replaced, and appliance warranty records.",
        "hosted_datasets": ["inventory_and_van_stock", "parts_replaced", "product_and_warranty_info"],
        "governance": "SAP SSO, Key Vault Encryption, Audit Logging"
    },
    {
        "id": "data_lake",
        "name": "Enterprise Data Lake",
        "category": "Cloud Data Lakes",
        "type": "Parquet / ADLS Lakehouse",
        "volume": "85.0 TB",
        "record_count": "210,000,000",
        "status": "Operational",
        "color": "#A855F7",
        "icon_class": "fa-solid fa-layer-group",
        "description": "Centralized Parquet and ORC file storage for historical weather trends, service history logs, and installations.",
        "hosted_datasets": ["weather", "service_history", "installation_history"],
        "governance": "Apache Atlas Lineage, KMS Encryption"
    },
    {
        "id": "azure_container",
        "name": "Azure Blob Container",
        "category": "Cloud Data Lakes",
        "type": "Azure Blob / ADLS Gen2",
        "volume": "64.2 TB",
        "record_count": "160,000,000",
        "status": "Operational",
        "color": "#0078D4",
        "icon_class": "fa-brands fa-microsoft",
        "description": "ADLS Gen2 blob storage containers storing IoT fault codes, raw boiler telemetry feeds, and smart meter logs.",
        "hosted_datasets": ["fault_codes", "boiler_telemetry_logs"],
        "governance": "Azure Storage Firewalls, SAS Tokens, Entra RBAC"
    },
    {
        "id": "sql_server",
        "name": "Microsoft SQL Server",
        "category": "Databases & Catalogs",
        "type": "RDBMS / T-SQL",
        "volume": "8.4 TB",
        "record_count": "42,000,000",
        "status": "Connected",
        "color": "#CC292B",
        "icon_class": "fa-solid fa-database",
        "description": "Relational database cluster hosting repair histories, visit outcomes, and engineer appointment schedules.",
        "hosted_datasets": ["repair_history", "visit_outcome", "appointment_schedule"],
        "governance": "Windows Auth, Always Encrypted DB, Row Level Security"
    },
    {
        "id": "aws_s3",
        "name": "AWS S3 Buckets",
        "category": "Cloud Data Lakes",
        "type": "Object Storage / S3",
        "volume": "124.0 TB",
        "record_count": "350,000,000",
        "status": "Operational",
        "color": "#FF9900",
        "icon_class": "fa-brands fa-aws",
        "description": "Primary object storage buckets retaining raw uploaded files, un-structured PDFs, and knowledge bases.",
        "hosted_datasets": ["knowledge_base", "business_rules", "epc_pdf_archive"],
        "governance": "AWS IAM Policies, S3 KMS Key Encryption"
    }
]



@app.route("/api/storage/providers", methods=["GET"])
def get_storage_providers_api():
    """
    API endpoint to return enterprise data storage providers metadata & status.
    Includes Databricks UC database, OneLake, Salesforce, Workday, SAP, Data Lake, Azure Container, SQL Server, AWS S3.
    """
    return jsonify({
        "success": True,
        "total_providers": len(STORAGE_PROVIDERS_DATA),
        "providers": STORAGE_PROVIDERS_DATA
    })



def classify_node_category(node_id: str) -> tuple[str, str]:
    """Classify node into executive domain category and icon."""
    nid = str(node_id).lower()
    if any(k in nid for k in ["sme", "jenkins", "david ross", "marcus vance", "claire williams", "head of", "lead telemetry", "data scientist", "vp operations"]):
        return "SME", "\uf007" # fa-user
    if any(k in nid for k in ["dataset", "snowflake", "sap", "crm", "platform", "dashboard", "network"]):
        return "Dataset", "\uf1c0" # fa-database
    if "xlsx" in nid:
        return "File", "\uf15c" # fa-file-lines
    if any(k in nid for k in ["error", "low gas", "overheating", "electrode", "valve", "pump", "pipe"]):
        return "Error", "\uf071" # fa-triangle-exclamation
    if any(k in nid for k in ["worcester", "ideal", "baxi", "combi", "home energy services"]):
        return "Equipment", "\uf0ad" # fa-wrench
    return "Metric", "\uf201" # fa-chart-line


@app.route("/api/graph/data", methods=["GET"])
def get_graph_data_api():
    """
    API endpoint to export NetworkX Knowledge Graph nodes and edges for visual rendering.
    Enriched with decision tree hierarchy levels and node classifications.
    """
    try:
        dt_meta = graph_service.get_decision_tree_metadata()
        nodes = []
        for node_id, attrs in graph_service.graph.nodes(data=True):
            fallback_cat, fallback_icon = classify_node_category(node_id)
            cat = attrs.get("category", fallback_cat)
            
            # Map icons if category is set explicitly
            icon = fallback_icon
            if cat == "Dataset" and "category" in attrs: icon = "\uf1c0"
            if cat == "File" and "category" in attrs: icon = "\uf15c"
            
            meta = dt_meta.get(str(node_id), {})
            nodes.append({
                "id": str(node_id),
                "label": str(node_id),
                "category": cat,
                "icon": icon,
                "description": attrs.get("details", attrs.get("description", f"Enterprise {cat} Entity Node")),
                "tree_level": meta.get("tree_level", 0),
                "node_type": meta.get("node_type", "root"),
                "parents": meta.get("parents", []),
                "children": meta.get("children", [])
            })

        edges = []
        for src, tgt, attrs in graph_service.graph.edges(data=True):
            relation = attrs.get("relationship", attrs.get("relation", "connected_to"))
            details = attrs.get("details", "")
            edges.append({
                "source": str(src),
                "target": str(tgt),
                "relation": relation,
                "details": details,
                "is_custom": bool(attrs.get("is_custom", False)),
                "upstream_column": attrs.get("upstream_column", ""),
                "downstream_column": attrs.get("downstream_column", ""),
                "source_column": attrs.get("source_column", ""),
                "target_column": attrs.get("target_column", ""),
                "column_mappings": attrs.get("column_mappings", []),
                "manual_relationships": attrs.get("manual_relationships", []),
            })

        return jsonify({
            "success": True,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes": nodes,
            "edges": edges
        })
    except Exception as e:
        print(f"[Graph Data Error]: {e}")


@app.route("/api/datasets", methods=["GET"])
def get_datasets_api():
    """
    Return the CSV dataset catalog and column schemas used by the manual
    relationship editor.
    """
    try:
        dataset_details = graph_service.get_dataset_catalog()
        return jsonify({
            "success": True,
            "datasets": [dataset["name"] for dataset in dataset_details],
            "dataset_details": dataset_details,
        })
    except Exception as e:
        print(f"[Datasets API Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
@app.route("/api/datasource/preview/<filename>", methods=["GET"])
def preview_datasource_api(filename: str):
    """
    API endpoint to preview content, columns, total row count, and sample records
    from any of the CSV data sources.
    """
    try:
        # Sanitize filename
        safe_filename = Path(filename).name
        if not safe_filename.endswith(".csv"):
            safe_filename += ".csv"
        filepath = DATA_DIR / safe_filename

        if not filepath.exists():
            return jsonify({"success": False, "error": f"File {safe_filename} not found."}), 404

        df = pd.read_csv(filepath)
        df_clean = df.fillna("")

        columns = list(df_clean.columns)
        total_rows = len(df_clean)
        records = df_clean.head(15).to_dict(orient="records")

        audit_identity = session.get("conversation_scope") or (
            f"anonymous:{request.remote_addr}:{str(request.user_agent.string or 'unknown')[:120]}"
        )
        _append_data_access_events(
            audit_identity,
            [safe_filename],
            "Direct preview",
            "Allowed by demo preview endpoint",
        )

        return jsonify({
            "success": True,
            "filename": safe_filename,
            "description": f"Synthetic dataset: {safe_filename}",
            "total_rows": total_rows,
            "columns": columns,
            "records": records
        })
    except Exception as e:
        print(f"[Datasource Preview Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/graph/relation/suggest", methods=["POST"])
def suggest_graph_relation_api():
    """Draft an editable relationship using bounded metadata and data samples."""
    try:
        data = request.get_json() or {}
        source = str(data.get("source") or "").strip()
        target = str(data.get("target") or "").strip()
        if not source or not target:
            return jsonify({
                "success": False,
                "error": "Select both a source and target object before requesting a suggestion.",
            }), 400

        context = graph_service.get_relation_suggestion_context(source, target)
        suggestion = suggest_graph_relationship(context, executor=agent_executor)

        def summarize_object(object_context):
            return {
                "id": object_context["id"],
                "category": object_context["category"],
                "column_count": len(object_context.get("columns", [])),
                "sample_record_count": len(object_context.get("sample_records", [])),
                "neighbor_count": len(object_context.get("neighboring_relationships", [])),
            }

        return jsonify({
            "success": True,
            "suggestion": suggestion,
            "context_summary": {
                "source": summarize_object(context["source"]),
                "target": summarize_object(context["target"]),
                "join_candidates_considered": len(context.get("join_candidates", [])),
            },
        })
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print(f"[Relationship Suggestion Error]: {error}")
        return jsonify({"success": False, "error": str(error)}), 500


@app.route("/api/graph/relation", methods=["POST", "GET", "DELETE"])
def add_graph_relation_api():
    """
    List, save, or delete directional relationships between any graph objects.
    Dataset endpoints may optionally include source/target columns.
    """
    try:
        if request.method == "GET":
            return jsonify({
                "success": True,
                "relations": graph_service.get_custom_relations(),
                "entities": graph_service.get_relation_entity_catalog(),
            })

        data = request.get_json() or {}
        source = str(data.get("source") or "").strip()
        target = str(data.get("target") or "").strip()
        relationship = str(data.get("relationship") or "").strip()
        source_column = str(data.get("source_column") or "").strip()
        target_column = str(data.get("target_column") or "").strip()

        # Backwards-compatible parsing for the earlier dataset-only editor.
        if not source and data.get("upstream_dataset"):
            source = f"Dataset: {Path(str(data['upstream_dataset'])).name}"
            source_column = str(data.get("upstream_column") or "").strip()
        if not target and data.get("downstream_dataset"):
            target = f"Dataset: {Path(str(data['downstream_dataset'])).name}"
            target_column = str(data.get("downstream_column") or "").strip()
        if not relationship and source and target:
            relationship = "maps" if source_column or target_column else "related_to"

        if not all([source, target, relationship]):
            return jsonify({
                "success": False,
                "error": "Source object, target object, and relationship label are required.",
            }), 400

        if request.method == "DELETE":
            deleted_relation = graph_service.delete_custom_relation(
                source=source,
                target=target,
                relationship=relationship,
                source_column=source_column,
                target_column=target_column,
            )
            if deleted_relation is None:
                return jsonify({
                    "success": False,
                    "error": "Manual relationship was not found.",
                }), 404
            return jsonify({
                "success": True,
                "message": "Manual relationship deleted from the Knowledge Graph.",
                "relation": deleted_relation,
                "total_nodes": len(graph_service.graph.nodes),
                "total_edges": len(graph_service.graph.edges),
            })

        relation = graph_service.add_custom_relation(
            source=source,
            target=target,
            relationship=relationship,
            source_column=source_column,
            target_column=target_column,
        )

        return jsonify({
            "success": True,
            "message": "Manual relationship saved to the Knowledge Graph.",
            "relation": relation,
            "total_nodes": len(graph_service.graph.nodes),
            "total_edges": len(graph_service.graph.edges),
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        print(f"[Add Relation Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print(f"🚀 Starting Utilities Knowledge Hub Chatbot Server on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
