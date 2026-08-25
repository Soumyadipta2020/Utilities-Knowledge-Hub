"""
WSGI entry point for Cloud Deployment (Render, Posit Connect Cloud, Gunicorn, PaaS).
"""
import os
from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", 5000)))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    app.run(host=host, port=port)
