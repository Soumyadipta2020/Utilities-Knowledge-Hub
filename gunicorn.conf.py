"""
Gunicorn configuration for production deployment (Render Free, PaaS, Containers).
Automatically picked up by Gunicorn regardless of the CLI start command.
"""
import os

# Port binding: Render injects $PORT (e.g. 10000)
port = os.getenv("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Free-tier resource optimization (512 MB RAM limit):
# 1 worker process with 4 threads avoids multi-process memory multiplication
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
