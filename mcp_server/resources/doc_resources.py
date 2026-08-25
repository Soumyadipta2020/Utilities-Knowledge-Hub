import os
from pathlib import Path
from fastmcp import FastMCP

DOCS_DIR = Path("docs")

def register_doc_resources(mcp: FastMCP):
    
    @mcp.resource("docs://knowledge_base/{doc_name}")
    def get_knowledge_base_doc(doc_name: str) -> str:
        """Secure knowledge base markdown access."""
        # Prevent path traversal
        safe_name = os.path.basename(doc_name)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
            
        doc_path = DOCS_DIR / safe_name
        
        if not doc_path.exists():
            return f"Documentation {safe_name} not found."
            
        try:
            with open(doc_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading document: {e}"
