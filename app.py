"""
Posit Connect Cloud Entry Point.
Imports Flask application instance from app.main.
"""
from app.main import app

if __name__ == "__main__":
    app.run()
