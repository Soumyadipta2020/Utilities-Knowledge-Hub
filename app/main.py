"""
Main Entry Point for Utilities Knowledge Hub Flask Web Application.
"""

from flask import Flask, render_template, request, jsonify
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
    TEMPLATES_DIR,
    OPENAI_API_KEY,
    DEFAULT_MODEL_NAME,
    ensure_mock_data_exists,
)
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.agent.tools import register_services
from app.agent.agent_builder import build_agent_executor, process_chat_message

# Initialize Flask App
app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.secret_key = SECRET_KEY

# Ensure Excel mock data files exist
ensure_mock_data_exists()

# Initialize Services & Inject dependencies into tools
graph_service = KnowledgeGraphService(KB_FILE_PATH)
data_service = DataService(METRICS_FILE_PATH, ACCESS_FILE_PATH)
register_services(graph_service, data_service)

# Build LangChain executor (if API key exists)
agent_executor = build_agent_executor(OPENAI_API_KEY, DEFAULT_MODEL_NAME)


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
        user_role = data.get("user_role", "Customer").strip()
        user_email = data.get("user_email", "user@utilities-company.com").strip()

        if not user_message:
            return jsonify({"error": "Message payload cannot be empty."}), 400

        # Run agent interaction
        agent_response = process_chat_message(
            user_input=user_message,
            user_role=user_role,
            user_email=user_email,
            executor=agent_executor,
        )

        access_denied_flag = "Access Denied" in agent_response or "Access Denied!" in agent_response

        return jsonify({
            "success": True,
            "response": agent_response,
            "user_role": user_role,
            "access_denied": access_denied_flag,
        })

    except Exception as e:
        print(f"[API Error] Exception during chat processing: {e}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500


if __name__ == "__main__":
    print(f"🚀 Starting Utilities Knowledge Hub Chatbot Server on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
