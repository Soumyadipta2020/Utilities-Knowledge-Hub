"""
Posit Connect Cloud & Local Entry Point.
Imports Flask application instance from app.main.
"""
import os
from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", 5000)))
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    app.run(host=host, port=port)
