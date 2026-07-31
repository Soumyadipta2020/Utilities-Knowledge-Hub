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
        self.df = None
        self.load_graph()

    def load_graph(self) -> None:
        """Read Knowledge_Base.xlsx and populate NetworkX DiGraph."""
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Knowledge Base Excel file not found at: {self.excel_path}")

        self.df = pd.read_excel(self.excel_path)
        self.graph.clear()

        for _, row in self.df.iterrows():
            source = str(row["source"]).strip()
            relationship = str(row["relationship"]).strip()
            target = str(row["target"]).strip()
            details = str(row.get("details", "")).strip()

            self.graph.add_node(source, entity_type="source")
            self.graph.add_node(target, entity_type="target")
            self.graph.add_edge(source, target, relationship=relationship, details=details)

    def find_matching_nodes(self, query: str) -> List[str]:
        """Case-insensitive search for node names matching a query string."""
        import re
        clean_query = re.sub(r"[^\w\s]", " ", query).lower().strip()
        query_words = set(clean_query.split())

        matches = []
        for node in self.graph.nodes:
            clean_node = re.sub(r"[^\w\s]", " ", node).lower().strip()
            node_words = set(clean_node.split())
            if node_words and (node_words.issubset(query_words) or clean_node in clean_query or clean_query in clean_node):
                matches.append(node)
        return matches

    def rag_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        RAG (Retrieval-Augmented Generation) document search over Knowledge Base records.
        Scores each record by keyword overlap and substring matching with query tokens.
        """
        if self.df is None or self.df.empty:
            return []

        query_tokens = set(query.lower().strip().split())
        scored_records = []

        for _, row in self.df.iterrows():
            source = str(row.get("source", ""))
            relationship = str(row.get("relationship", ""))
            target = str(row.get("target", ""))
            details = str(row.get("details", ""))

            full_text = f"{source} {relationship} {target} {details}".lower()
            text_tokens = set(full_text.split())

            # Score based on token overlap & substring matching
            overlap_score = len(query_tokens.intersection(text_tokens))
            substring_bonus = sum(2 for t in query_tokens if t in full_text and len(t) > 2)
            total_score = overlap_score + substring_bonus

            if total_score > 0:
                scored_records.append((total_score, {
                    "source": source,
                    "relationship": relationship,
                    "target": target,
                    "details": details,
                    "content": f"Entity '{source}' {relationship} '{target}'. Details: {details}",
                    "score": total_score,
                }))

        scored_records.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in scored_records[:top_k]]

    def hybrid_graph_rag_search(self, query: str) -> Dict[str, Any]:
        """
        Perform unified Graph-RAG retrieval: combines RAG context retrieval with Knowledge Graph path traversal.
        """
        rag_results = self.rag_search(query, top_k=5)

        # Identify entities for graph traversal
        matched_nodes = self.find_matching_nodes(query)
        graph_results = []
        seen_entities = set()

        if matched_nodes:
            for node in matched_nodes[:3]:
                if node not in seen_entities:
                    seen_entities.add(node)
                    t_res = self.traverse_graph(node)
                    if t_res.get("found"):
                        graph_results.append(t_res)

        # Fallback to candidate entities from RAG results if no direct node match found
        if not graph_results and rag_results:
            for item in rag_results[:3]:
                node_candidate = item.get("source")
                if node_candidate and node_candidate not in seen_entities:
                    seen_entities.add(node_candidate)
                    t_res = self.traverse_graph(node_candidate)
                    if t_res.get("found"):
                        graph_results.append(t_res)

        return {
            "query": query,
            "rag_context_documents": rag_results,
            "graph_traversals": graph_results,
        }

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
