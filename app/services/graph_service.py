"""
Knowledge Graph Service using NetworkX.
Loads entity-relationship data from Excel and provides graph traversal capabilities.
"""

from typing import Dict, List, Any, Optional, Tuple
import networkx as nx
import pandas as pd
from pathlib import Path

from langchain_community.graphs.networkx_graph import NetworkxEntityGraph, KnowledgeTriple


class KnowledgeGraphService:
    """
    Service to construct and query a Knowledge Graph from Excel data.
    Powered by LangChain NetworkxEntityGraph for graph-based RAG and entity knowledge retrieval.
    """

    def __init__(self, excel_path: Path):
        self.excel_path = excel_path
        self.graph = nx.DiGraph()
        self.langchain_graph = NetworkxEntityGraph()
        self.df = None
        self.load_graph()

    def load_graph(self) -> None:
        """Read Knowledge_Base.xlsx and populate NetworkX DiGraph and LangChain NetworkxEntityGraph."""
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Knowledge Base Excel file not found at: {self.excel_path}")

        self.df = pd.read_excel(self.excel_path)
        self.graph.clear()
        self.langchain_graph = NetworkxEntityGraph()

        for _, row in self.df.iterrows():
            source = str(row["source"]).strip()
            relationship = str(row["relationship"]).strip()
            target = str(row["target"]).strip()
            details = str(row.get("details", "")).strip()

            # NetworkX graph representation
            self.graph.add_node(source, entity_type="source")
            self.graph.add_node(target, entity_type="target")
            self.graph.add_edge(source, target, relationship=relationship, details=details)

            # LangChain NetworkxEntityGraph representation using KnowledgeTriple
            self.langchain_graph.add_triple(KnowledgeTriple(source, relationship, target))

    def find_matching_nodes(self, query: str) -> List[str]:
        """Case-insensitive search for node names matching a query string."""
        import re
        clean_query = re.sub(r"[^\w\s]", " ", query).lower().strip()
        query_words = set(clean_query.split())
        query_words_singular = {w[:-1] if w.endswith('s') and len(w) > 3 else w for w in query_words}

        matches = []
        for node in self.graph.nodes:
            clean_node = re.sub(r"[^\w\s]", " ", node).lower().strip()
            node_words = set(clean_node.split())
            node_words_singular = {w[:-1] if w.endswith('s') and len(w) > 3 else w for w in node_words}
            
            # Exact substring match
            if clean_node in clean_query or clean_query in clean_node:
                matches.append(node)
                continue
                
            # Flexible word match (plural/singular)
            if node_words_singular and node_words_singular.issubset(query_words_singular):
                matches.append(node)
                continue
                
            # Partial overlap for multi-word nodes (at least 50% of node words match)
            if node_words_singular:
                overlap = len(node_words_singular.intersection(query_words_singular))
                if overlap > 0 and overlap >= len(node_words_singular) / 2:
                    matches.append(node)
                    
        return list(set(matches))

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

    def extract_subgraph_for_query(self, query: str) -> Dict[str, Any]:
        """
        Extract the exact sub-graph (nodes and edges) associated with a query / answer generation.
        Used to demonstrate how a specific response was generated from Knowledge Graph traversal.
        """
        sub_nodes = set()
        sub_edges = []

        hybrid = self.hybrid_graph_rag_search(query)
        rag_docs = hybrid.get("rag_context_documents", [])
        graph_traversals = hybrid.get("graph_traversals", [])

        # Process RAG items
        for item in rag_docs:
            src = item.get("source")
            tgt = item.get("target")
            rel = item.get("relationship", "connected_to")
            details = item.get("details", "")
            if src and tgt:
                sub_nodes.add(src)
                sub_nodes.add(tgt)
                sub_edges.append({
                    "source": src,
                    "target": tgt,
                    "relation": rel,
                    "details": details
                })

        # Process Graph Traversals
        for trav in graph_traversals:
            for edge in trav.get("outgoing_edges", []) + trav.get("incoming_edges", []):
                src = edge.get("from")
                tgt = edge.get("to")
                rel = edge.get("relationship", "connected_to")
                details = edge.get("details", "")
                if src and tgt:
                    sub_nodes.add(src)
                    sub_nodes.add(tgt)
                    sub_edges.append({
                        "source": src,
                        "target": tgt,
                        "relation": rel,
                        "details": details
                    })

        # Check for query keyword heuristics
        query_lower = query.lower()
        if any(w in query_lower for w in ["pressure", "psi", "flame", "temp", "telemetry", "flow"]):
            sub_nodes.update(["Live_Metrics_Dataset", "David Ross (Lead Telemetry Engineer)"])
            sub_edges.append({"source": "Live_Metrics_Dataset", "target": "David Ross (Lead Telemetry Engineer)", "relation": "managed_by_sme", "details": "Telemetry Owner"})
        elif any(w in query_lower for w in ["sales", "funnel", "lead", "quote", "appointment", "conversion", "job", "service"]):
            sub_nodes.update(["Sales_Funnel_Dataset", "Sarah Jenkins (Head of Commercial Analytics)"])
            sub_edges.append({"source": "Sales_Funnel_Dataset", "target": "Sarah Jenkins (Head of Commercial Analytics)", "relation": "managed_by_sme", "details": "Commercial SME"})

        nodes_list = []
        for n in sub_nodes:
            attrs = self.graph.nodes[n] if n in self.graph.nodes else {}
            nodes_list.append({
                "id": str(n),
                "label": str(n),
                "category": attrs.get("category", "Entity"),
                "description": attrs.get("description", "")
            })

        # Deduplicate edges
        unique_edges = []
        seen = set()
        for e in sub_edges:
            key = (e["source"], e["target"], e["relation"])
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        return {
            "query": query,
            "nodes": nodes_list,
            "edges": unique_edges
        }

    def get_decision_tree_metadata(self) -> Dict[str, Dict[str, Any]]:
        """
        Compute decision tree hierarchy metadata for graph nodes.
        Enforces clear tier levels:
          Tier 0: Root Systems & Equipment Models
          Tier 1: Fault Errors, Core Datasets & Service Lines
          Tier 2: Root Causes & Lineage Data Sources
          Tier 3: Remedy Actions, Required Parts & SME Owners
        Returns a mapping of node_id -> { tree_level, node_type, parents, children }.
        """
        metadata = {}
        for n in self.graph.nodes:
            nid_lower = n.lower()

            # Explicit categorical tier rules
            if any(k in nid_lower for k in ["sme", "jenkins", "david ross", "marcus vance", "claire williams", "valve", "electrode", "pump", "loop", "pipe", "remedy"]):
                lvl = 3
                node_type = "remedy_action"
            elif any(k in nid_lower for k in ["low gas pressure", "overheating", "sap is-u", "grid mon", "net sale", "telemetry"]):
                lvl = 2
                node_type = "root_cause"
            elif any(k in nid_lower for k in ["error", "dataset", "forecast", "dashboard", "hub", "heating", "maintenance", "plumbing", "electrical", "appliance", "appointment"]):
                lvl = 1
                node_type = "decision_fault"
            elif any(k in nid_lower for k in ["worcester", "ideal", "baxi", "platform", "home energy", "lead", "quote"]):
                lvl = 0
                node_type = "root"
            else:
                lvl = 1
                node_type = "decision_fault"

            parents = list(self.graph.predecessors(n))
            children = list(self.graph.successors(n))

            metadata[n] = {
                "tree_level": lvl,
                "node_type": node_type,
                "parents": parents,
                "children": children
            }

        return metadata

    def query_langchain_graph(self, query: str) -> List[str]:
        """
        Query the Knowledge Graph using LangChain NetworkxEntityGraph abstraction.
        Extracts entity knowledge triples for matched entities.
        """
        matched_nodes = self.find_matching_nodes(query)
        knowledge_list = []
        for node in matched_nodes:
            entity_facts = self.langchain_graph.get_entity_knowledge(node)
            for fact in entity_facts:
                if fact not in knowledge_list:
                    knowledge_list.append(fact)
        return knowledge_list

    def get_langchain_triples(self) -> List[Tuple[str, str, str]]:
        """Return all LangChain KnowledgeTriples loaded into the NetworkxEntityGraph."""
        return self.langchain_graph.get_triples()

