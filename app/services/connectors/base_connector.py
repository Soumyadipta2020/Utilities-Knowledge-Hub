from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseDataConnector(ABC):
    """
    Abstract base class for all enterprise data connectors.
    Provides a unified interface so the application layer doesn't need to know
    whether data lives in CSV, Postgres, Databricks, etc.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    def list_tables(self) -> List[str]:
        """Return a list of available tables or datasets."""
        pass

    @abstractmethod
    def get_schema(self, table_name: str) -> Dict[str, Any]:
        """Return schema information for a specific table."""
        pass

    @abstractmethod
    def query(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Execute a raw query against the data source."""
        pass

    @abstractmethod
    def read_table(self, table_name: str, limit: int = 100, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Read structured data from a table with optional filters and limits."""
        pass

    @abstractmethod
    def validate_access(self, user_role: str, table_name: str) -> bool:
        """Validate if a role can access this table."""
        pass
