"""
WSGI entry point for Cloud Deployment (Posit Connect Cloud, Gunicorn, PaaS).
"""
from app.main import app

if __name__ == "__main__":
    app.run()
