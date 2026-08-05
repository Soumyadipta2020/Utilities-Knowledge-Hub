"""
Main Entry Point for Utilities Knowledge Hub Flask Web Application.
"""

from flask import Flask, jsonify, render_template, request, session
import pandas as pd
from pathlib import Path
import sys

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
from app.agent.agent_builder import build_agent_executor, process_chat_message

# Initialize Flask App
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.secret_key = SECRET_KEY

# Initialize Services & Inject dependencies into tools
graph_service = KnowledgeGraphService(DATA_DIR)
data_service = DataService(DATA_DIR)
pipeline_engine = KnowledgeHarnessingPipeline(DATA_DIR, graph_service, data_service)
register_services(graph_service, data_service)

# Build LangChain executor (if OpenRouter API key exists)
agent_executor = build_agent_executor(OPENROUTER_API_KEY, OPENROUTER_MODEL_NAME, OPENROUTER_BASE_URL)


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

        access_required_flag = "Dataset Access Required" in agent_response or "Access Denied" in agent_response
        response_graph = graph_service.extract_subgraph_for_query(user_message)

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
                "details": details
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
    API endpoint to retrieve all available datasets.
    Includes datasets defined in the Knowledge Graph and CSV files in data_dir.
    """
    try:
        datasets = set()
        
        # 1. Get Datasets from graph categories
        for node_id, attrs in graph_service.graph.nodes(data=True):
            fallback_cat, _ = classify_node_category(node_id)
            cat = attrs.get("category", fallback_cat)
            if cat == "Dataset":
                datasets.add(str(node_id))
                
        # 2. Get Datasets from CSV files
        if DATA_DIR.exists():
            for csv_file in DATA_DIR.glob("*.csv"):
                datasets.add(csv_file.stem)


        return jsonify({
            "success": True,
            "datasets": sorted(list(datasets))
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


@app.route("/api/graph/relation", methods=["POST"])
def add_graph_relation_api():
    """
    API endpoint to save a new relation between two datasets.
    """
    try:
        data = request.get_json() or {}
        source = data.get("source")
        target = data.get("target")
        details = data.get("details", "")

        if not source or not target:
            return jsonify({"success": False, "error": "Source and target datasets are required."}), 400

        graph_service.add_custom_relation(source, target, details)

        return jsonify({
            "success": True,
            "message": "Relation saved to Knowledge Graph."
        })
    except Exception as e:
        print(f"[Add Relation Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print(f"🚀 Starting Utilities Knowledge Hub Chatbot Server on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
