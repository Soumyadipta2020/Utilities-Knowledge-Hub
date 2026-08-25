import duckdb
import os
import re
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)

class DuckDBEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DuckDBEngine, cls).__new__(cls)
                cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        # Thread-safe in-memory duckdb connection.
        # duckdb allows multiple threads to use the same connection if check_same_thread=False
        # is used in sqlite, but in duckdb for in-memory, we just connect.
        self.conn = duckdb.connect(':memory:')
        self._load_csvs()

    def _sanitize_view_name(self, filename: str) -> str:
        # Strip extension
        name = os.path.splitext(filename)[0]
        # Replace non-alphanumeric with underscores
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it doesn't start with a number
        if name[0].isdigit():
            name = f"v_{name}"
        return name

    def _load_csvs(self):
        # Dynamic absolute path relative to repo root
        # This file is in mcp_server/engine/duckdb_engine.py
        repo_root = Path(__file__).resolve().parents[2]
        data_dir = repo_root / "data"
        
        if not data_dir.exists():
            logger.warning(f"Data directory not found at {data_dir}")
            return
            
        logger.info(f"Scanning for CSVs in {data_dir}")
        for filepath in data_dir.glob("*.csv"):
            view_name = self._sanitize_view_name(filepath.name)
            safe_path = str(filepath).replace("'", "''")
            
            # Using robust read_csv_auto settings
            sql = f"""
                CREATE OR REPLACE VIEW {view_name} AS 
                SELECT * FROM read_csv_auto('{safe_path}', all_varchar=False, union_by_name=True, sample_size=-1)
            """
            try:
                self.conn.execute(sql)
                logger.info(f"Loaded view {view_name} from {filepath.name}")
            except Exception as e:
                logger.error(f"Failed to load {filepath.name} into view {view_name}: {e}")

    def execute_query(self, sql: str) -> list:
        # Use a cursor for thread safety if necessary, though duckdb connection is thread-safe
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return {"columns": columns, "data": data}
        finally:
            cursor.close()

# Singleton instance export
duckdb_engine = DuckDBEngine()
