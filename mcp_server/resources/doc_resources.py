import os
from pathlib import Path
from fastmcp import FastMCP
import logging

logger = logging.getLogger(__name__)

def register_doc_resources(mcp: FastMCP) -> None:
    
    @mcp.resource("docs://knowledge_base/{doc_name}")
    def get_knowledge_base_doc(doc_name: str) -> str:
        """Secure knowledge base markdown access."""
        
        # Resolving relative to repo root dynamically
        repo_root = Path(__file__).resolve().parents[2]
        docs_dir = repo_root / "docs"
        
        # Ensure name ends with .md
        safe_name = doc_name
        if not safe_name.endswith(".md"):
            safe_name += ".md"
            
        try:
            # Resolve the absolute path
            doc_path = (docs_dir / safe_name).resolve()
            
            # Path traversal guard: Check if the resolved path is within docs_dir
            if not str(doc_path).startswith(str(docs_dir.resolve())):
                logger.warning(f"Path traversal attempt detected: {doc_name}")
                return "Error: Invalid document path."
                
            if not doc_path.exists() or not doc_path.is_file():
                return f"Documentation {safe_name} not found."
                
            with open(doc_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading document {doc_name}: {e}")
            return f"Error reading document: {e}"
