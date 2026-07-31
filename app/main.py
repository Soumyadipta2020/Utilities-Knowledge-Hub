"""
Main Entry Point for Utilities Knowledge Hub Flask Web Application.
"""

from flask import Flask, jsonify, render_template, request, session
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
data_service = DataService(METRICS_FILE_PATH, ACCESS_FILE_PATH, OPERATIONS_FILE_PATH)
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
        user_email = data.get("user_email", "user@centrica.com").strip() or "user@centrica.com"

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

        return jsonify({
            "success": True,
            "response": agent_response,
            "user_email": user_email,
            "access_required": access_required_flag,
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
