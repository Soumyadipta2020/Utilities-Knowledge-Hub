"""
Knowledge Graph Service using NetworkX.
Loads entity-relationship data from Excel and provides graph traversal capabilities.
"""

from typing import Dict, List, Any, Optional
import networkx as nx
import pandas as pd
from pathlib import Path


class KnowledgeGraphService:
    """Service to construct and query a NetworkX Directed Graph from Excel data."""

    def __init__(self, excel_path: Path):
        self.excel_path = excel_path
        self.graph = nx.DiGraph()
        self.load_graph()

    def load_graph(self) -> None:
        """Read Knowledge_Base.xlsx and populate NetworkX DiGraph."""
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Knowledge Base Excel file not found at: {self.excel_path}")

        df = pd.read_excel(self.excel_path)
        self.graph.clear()

        for _, row in df.iterrows():
            source = str(row["source"]).strip()
            relationship = str(row["relationship"]).strip()
            target = str(row["target"]).strip()
            details = str(row.get("details", "")).strip()

            self.graph.add_node(source, entity_type="source")
            self.graph.add_node(target, entity_type="target")
            self.graph.add_edge(source, target, relationship=relationship, details=details)

    def find_matching_nodes(self, query: str) -> List[str]:
        """Case-insensitive search for node names matching a query string."""
        query_lower = query.lower().strip()
        matches = [node for node in self.graph.nodes if query_lower in node.lower()]
        return matches

    def traverse_graph(self, entity_name: str) -> Dict[str, Any]:
        """
        Traverse the graph starting from entity_name or matching nodes.
        Returns a structured dictionary of graph relationships and diagnostic paths.
        """
        matched_nodes = self.find_matching_nodes(entity_name)

        if not matched_nodes:
            return {
                "found": False,
                "queried_entity": entity_name,
                "message": f"No entity matching '{entity_name}' found in Knowledge Graph.",
                "available_entities": list(self.graph.nodes),
            }

        primary_node = matched_nodes[0]
        outgoing_edges = []
        incoming_edges = []
        path_summaries = []

        # Outgoing relationships
        for neighbor in self.graph.successors(primary_node):
            edge_data = self.graph.get_edge_data(primary_node, neighbor)
            rel = edge_data.get("relationship", "connected_to")
            details = edge_data.get("details", "")
            outgoing_edges.append({
                "from": primary_node,
                "relationship": rel,
                "to": neighbor,
                "details": details,
            })
            path_summaries.append(f"[{primary_node}] --({rel})--> [{neighbor}] ({details})")

            # 2nd level depth traversal
            for deep_neighbor in self.graph.successors(neighbor):
                deep_edge = self.graph.get_edge_data(neighbor, deep_neighbor)
                deep_rel = deep_edge.get("relationship", "connected_to")
                deep_details = deep_edge.get("details", "")
                outgoing_edges.append({
                    "from": neighbor,
                    "relationship": deep_rel,
                    "to": deep_neighbor,
                    "details": deep_details,
                })
                path_summaries.append(
                    f"  └-- [{neighbor}] --({deep_rel})--> [{deep_neighbor}] ({deep_details})"
                )

        # Incoming relationships
        for predecessor in self.graph.predecessors(primary_node):
            edge_data = self.graph.get_edge_data(predecessor, primary_node)
            rel = edge_data.get("relationship", "connected_to")
            details = edge_data.get("details", "")
            incoming_edges.append({
                "from": predecessor,
                "relationship": rel,
                "to": primary_node,
                "details": details,
            })
            path_summaries.append(f"[{predecessor}] --({rel})--> [{primary_node}] ({details})")

        return {
            "found": True,
            "queried_entity": entity_name,
            "matched_entity": primary_node,
            "all_matches": matched_nodes,
            "outgoing_edges": outgoing_edges,
            "incoming_edges": incoming_edges,
            "formatted_paths": path_summaries,
        }
