from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseClient(ABC):
    @abstractmethod
    async def execute_query(self, sql_statement: str, row_limit: int = 50) -> Dict[str, Any]:
        """
        Execute a SQL query against the target engine.
        """
        pass
        
    @abstractmethod
    async def explain_query(self, sql_statement: str) -> str:
        """
        Generate an EXPLAIN plan for the query.
        """
        pass
