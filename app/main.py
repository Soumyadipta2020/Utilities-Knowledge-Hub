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
    KB_FILE_PATH,
    METRICS_FILE_PATH,
    ACCESS_FILE_PATH,
    OPERATIONS_FILE_PATH,
    TEMPLATES_DIR,
    OPENROUTER_API_KEY,
    OPENROUTER_MODEL_NAME,
    OPENROUTER_BASE_URL,
    DATA_DIR,
    ensure_mock_data_exists,
)
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.services.pipeline_service import KnowledgeHarnessingPipeline
from app.agent.tools import register_services
from app.agent.agent_builder import build_agent_executor, process_chat_message

# Initialize Flask App
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.secret_key = SECRET_KEY

# Ensure Excel mock data files exist
ensure_mock_data_exists()

# Initialize Services & Inject dependencies into tools
graph_service = KnowledgeGraphService(KB_FILE_PATH)
data_service = DataService(METRICS_FILE_PATH, ACCESS_FILE_PATH, OPERATIONS_FILE_PATH)
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
            from app.data.generate_mock_data import generate_all_mock_data
            generate_all_mock_data(DATA_DIR)

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
        from app.data.generate_mock_data import generate_all_mock_data
        generate_all_mock_data(DATA_DIR)

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


def classify_node_category(node_id: str) -> tuple[str, str]:
    """Classify node into executive domain category and icon."""
    nid = str(node_id).lower()
    if any(k in nid for k in ["sme", "jenkins", "david ross", "marcus vance", "claire williams", "head of", "lead telemetry", "data scientist", "vp operations"]):
        return "SME", "👤"
    if any(k in nid for k in ["dataset", "snowflake", "sap", "crm", "platform", "dashboard", "network", "xlsx"]):
        return "Dataset", "📊"
    if any(k in nid for k in ["error", "low gas", "overheating", "electrode", "valve", "pump", "pipe"]):
        return "Error", "⚠️"
    if any(k in nid for k in ["worcester", "ideal", "baxi", "combi", "home energy services"]):
        return "Equipment", "🔧"
    return "Metric", "📈"


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
            cat, icon = classify_node_category(node_id)
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
@app.route("/api/datasource/preview/<filename>", methods=["GET"])
def preview_datasource_api(filename: str):
    """
    API endpoint to preview content, columns, total row count, and sample records
    from any of the 6 DHS Excel data sources.
    """
    try:
        # Sanitize filename
        safe_filename = Path(filename).name
        filepath = DATA_DIR / safe_filename

        if not filepath.exists():
            return jsonify({"success": False, "error": f"File {safe_filename} not found."}), 404

        df = pd.read_excel(filepath)
        df_clean = df.fillna("")

        columns = list(df_clean.columns)
        total_rows = len(df_clean)
        records = df_clean.head(15).to_dict(orient="records")

        # Map metadata description per DHS source file
        descriptions = {
            "Information_Harnessing_Source.xlsx": "Raw ingestion streams, operational manual chunks, Data Factory connector states, and IoT telemetry metrics.",
            "Knowledge_Harnessing_Source.xlsx": "Extracted subject-predicate-object knowledge graph triples, SME attribution mappings, and ontology nodes.",
            "Inference_Harnessing_Source.xlsx": "Diagnostic decision trees, fault resolution paths, model routing confidence scores, and error handling rules.",
            "Outcome_Harnessing_Source.xlsx": "Commercial sales activity, automated IT access ticket outcomes, resolution metrics, and SLA performance.",
            "Benchmarking_Harnessing_Source.xlsx": "Golden Q&A evaluation datasets, F1 precision scores (0.99), LLM-as-a-Judge ratings, and hallucination guardrails.",
            "Governance_Security_Source.xlsx": "Azure Entra ID role permissions matrix, Microsoft Purview data lineage tags, and Key Vault secret policies."
        }

        return jsonify({
            "success": True,
            "filename": safe_filename,
            "description": descriptions.get(safe_filename, "DHS Enterprise Excel Data Source."),
            "total_rows": total_rows,
            "columns": columns,
            "records": records
        })
    except Exception as e:
        print(f"[Datasource Preview Error]: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print(f"🚀 Starting Utilities Knowledge Hub Chatbot Server on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
