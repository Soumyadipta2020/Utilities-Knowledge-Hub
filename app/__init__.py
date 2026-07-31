"""
App Package Initialization.
Exposes Flask application instance 'app' for WSGI servers like Gunicorn on Render.
"""
from app.main import app
