"""
Knowledge Graph Service using NetworkX.
Loads entity-relationship data from Excel and provides graph traversal capabilities.
"""

from typing import Dict, List, Any, Optional, Tuple
import json
import networkx as nx
import pandas as pd
from pathlib import Path

from langchain_community.graphs.networkx_graph import NetworkxEntityGraph, KnowledgeTriple


class KnowledgeGraphService:
    """
    Service to construct and query a Knowledge Graph from Excel data.
    Powered by LangChain NetworkxEntityGraph for graph-based RAG and entity knowledge retrieval.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.custom_relations_path = data_dir / "custom_relations.json"
        self.graph = nx.DiGraph()
        self.langchain_graph = NetworkxEntityGraph()
        self.df = None
        self.load_graph()

    def _add_triple(self, source: str, relationship: str, target: str, details: str = "") -> None:
        self.graph.add_node(source, entity_type="source")
        self.graph.add_node(target, entity_type="target")
        self.graph.add_edge(source, target, relationship=relationship, details=details)
        self.langchain_graph.add_triple(KnowledgeTriple(source, relationship, target))
        if self.df is None:
            self.df = pd.DataFrame(columns=["source", "relationship", "target", "details"])
        self.df.loc[len(self.df)] = {"source": source, "relationship": relationship, "target": target, "details": details}

    def load_graph(self) -> None:
        """Read CSV datasets and populate NetworkX DiGraph with executive-friendly semantic lineage."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found at: {self.data_dir}")

        self.graph.clear()
        self.langchain_graph = NetworkxEntityGraph()
        self.df = pd.DataFrame(columns=["source", "relationship", "target", "details"])

        # Define Business Domains based on filename patterns
        domain_mapping = {
            "customer": "Domain: Customer Operations",
            "property": "Domain: Customer Operations",
            "boiler": "Domain: Assets & Equipment",
            "quote": "Domain: Sales & Pipeline",
            "installation": "Domain: Sales & Pipeline",
            "appointment": "Domain: Field Service",
            "service": "Domain: Field Service",
            "repair": "Domain: Field Service",
            "engineer": "Domain: HR & Productivity",
            "weather": "Domain: External Operations",
            "business_rules": "Domain: Enterprise Governance",
            "iot": "Domain: IoT Telemetry"
        }

        # Create Domain Nodes
        domains = set(domain_mapping.values())
        for domain in domains:
            self.graph.add_node(domain, entity_type="Domain", category="Domain Cluster", details="High-level business function")

        try:
            for csv_file in self.data_dir.glob("*.csv"):
                dataset_name = csv_file.name
                dataset_node = f"Dataset: {dataset_name}"
                
                # Classify Domain
                assigned_domain = "Domain: General Operations"
                for key, dom in domain_mapping.items():
                    if key in dataset_name.lower():
                        assigned_domain = dom
                        break
                        
                if not self.graph.has_node(assigned_domain):
                    self.graph.add_node(assigned_domain, entity_type="Domain", category="Domain Cluster", details="High-level business function")
                    
                self.graph.add_node(dataset_node, entity_type="Dataset", category="Dataset", details=f"Source File: {dataset_name}")
                self._add_triple(assigned_domain, "contains_dataset", dataset_node, details="Domain taxonomy mapping")
                
                # Detect common info (Shared Entities)
                try:
                    df_sample = pd.read_csv(csv_file, nrows=0)
                    columns = list(df_sample.columns)
                except:
                    columns = []
                    
                shared_keys = ["customer_id", "boiler_id", "job_id", "pay_id", "lead_id"]
                for col in columns:
                    if col in shared_keys:
                        entity_name = f"Shared Entity: {col.replace('_', ' ').title()}"
                        if not self.graph.has_node(entity_name):
                            self.graph.add_node(entity_name, entity_type="Shared_Entity", category="Key Info Link", details=f"Cross-dataset linkage key: {col}")
                        
                        # Dataset -> Shared Entity
                        self._add_triple(dataset_node, f"via: {col}", entity_name, details=f"Linked by column '{col}'")
                        
                # Define Business Metrics mapping
                metric_mapping = {
                    "quotes_and_sales": ["Net Sales", "Leads", "Net Appt", "Sales Conversion", "Revenue"],
                    "installation_history": ["Installations"],
                    "repair_history": ["Repair"],
                    "service_history": ["Service"],
                    "appointment_schedule": ["Reschedule Rate"],
                    "engineer_productivity": ["FTE", "Gross Hours", "Workload Hours", "Productivity per week"]
                }
                
                # Attach metrics to datasets
                for key, metrics in metric_mapping.items():
                    if key in dataset_name.lower():
                        for metric in metrics:
                            metric_node = f"Metric: {metric}"
                            if not self.graph.has_node(metric_node):
                                self.graph.add_node(metric_node, entity_type="Metric", category="Business Metric", details=f"KPI derived from {dataset_name}")
                            self._add_triple(dataset_node, "calculates_metric", metric_node, details="Metric calculation derivation")
                            
            # Direct Dataset-to-Dataset connections for Dataset connection view
            all_dataset_nodes = [n for n in self.graph.nodes if n.startswith("Dataset: ")]
            dataset_keys = {}
            for dnode in all_dataset_nodes:
                dname = dnode.replace("Dataset: ", "")
                csv_path = self.data_dir / dname
                if csv_path.exists():
                    try:
                        df_s = pd.read_csv(csv_path, nrows=0)
                        dataset_keys[dnode] = set(df_s.columns)
                    except Exception:
                        dataset_keys[dnode] = set()

            shared_keys = ["customer_id", "boiler_id", "job_id", "pay_id", "lead_id"]
            d_list = list(dataset_keys.keys())
            for i in range(len(d_list)):
                node_a = d_list[i]
                keys_a = dataset_keys[node_a]
                for j in range(i + 1, len(d_list)):
                    node_b = d_list[j]
                    keys_b = dataset_keys[node_b]
                    common = [k for k in shared_keys if k in keys_a and k in keys_b]
                    for key in common:
                        self._add_triple(node_a, f"via: {key}", node_b, details=f"Direct dataset connection via '{key}'")
                        
        except Exception as e:
            print(f"Error loading graph from CSVs: {e}")

        # Manual relationships are re-applied after every graph rebuild so they
        # remain visible after pipeline execution and application restarts.
        for relation in self.get_custom_relations():
            try:
                self._apply_custom_relation(relation)
            except ValueError as error:
                print(f"Skipping invalid custom relation: {error}")

    def get_dataset_catalog(self) -> List[Dict[str, Any]]:
        """Return CSV dataset names and columns for the manual relation editor."""
        catalog = []
        for csv_file in sorted(self.data_dir.glob("*.csv"), key=lambda path: path.name.casefold()):
            try:
                columns = list(pd.read_csv(csv_file, nrows=0).columns)
            except Exception:
                columns = []
            catalog.append({
                "name": csv_file.stem,
                "filename": csv_file.name,
                "node_id": f"Dataset: {csv_file.name}",
                "columns": columns,
            })
        return catalog

    def get_custom_relations(self) -> List[Dict[str, str]]:
        """Load persisted manual dataset relationships from disk."""
        if not self.custom_relations_path.exists():
            return []
        try:
            data = json.loads(self.custom_relations_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not load custom relations: {error}")
            return []

    def _save_custom_relations(self, relations: List[Dict[str, str]]) -> None:
        """Atomically persist the complete manual relationship collection."""
        temp_path = self.custom_relations_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(relations, indent=2), encoding="utf-8")
        temp_path.replace(self.custom_relations_path)

    def _normalize_dataset(self, dataset_name: str) -> Tuple[str, str, List[str]]:
        """Resolve a UI dataset value to its canonical CSV filename and graph node."""
        normalized = str(dataset_name or "").strip()
        if normalized.startswith("Dataset: "):
            normalized = normalized.replace("Dataset: ", "", 1)
        normalized = Path(normalized).name
        if not normalized.lower().endswith(".csv"):
            normalized += ".csv"

        csv_path = self.data_dir / normalized
        if not csv_path.exists():
            raise ValueError(f"Dataset '{normalized}' does not exist.")

        columns = list(pd.read_csv(csv_path, nrows=0).columns)
        return normalized, f"Dataset: {normalized}", columns

    def _apply_custom_relation(self, relation: Dict[str, str]) -> None:
        """Apply one validated persisted relation to both graph representations."""
        upstream_file, upstream_node, upstream_columns = self._normalize_dataset(relation.get("upstream_dataset", ""))
        downstream_file, downstream_node, downstream_columns = self._normalize_dataset(relation.get("downstream_dataset", ""))
        upstream_column = relation.get("upstream_column", "")
        downstream_column = relation.get("downstream_column", "")

        if upstream_column not in upstream_columns:
            raise ValueError(f"Column '{upstream_column}' does not exist in '{upstream_file}'.")
        if downstream_column not in downstream_columns:
            raise ValueError(f"Column '{downstream_column}' does not exist in '{downstream_file}'.")

        mapping = {
            "upstream_column": upstream_column,
            "downstream_column": downstream_column,
        }
        existing_edge = self.graph.get_edge_data(upstream_node, downstream_node) or {}
        mappings = list(existing_edge.get("column_mappings", [])) if existing_edge.get("is_custom") else []
        is_new_mapping = mapping not in mappings
        if is_new_mapping:
            mappings.append(mapping)

        mapping_labels = [
            f"{item['upstream_column']} → {item['downstream_column']}"
            for item in mappings
        ]
        relationship = f"maps: {' | '.join(mapping_labels)}"
        details = (
            f"Manual column mappings from {upstream_file} to {downstream_file}: "
            f"{', '.join(mapping_labels)}"
        )
        self.graph.add_edge(
            upstream_node,
            downstream_node,
            relationship=relationship,
            details=details,
            is_custom=True,
            upstream_column=upstream_column,
            downstream_column=downstream_column,
            column_mappings=mappings,
        )
        if is_new_mapping:
            self.langchain_graph.add_triple(KnowledgeTriple(upstream_node, relationship, downstream_node))
            if self.df is None:
                self.df = pd.DataFrame(columns=["source", "relationship", "target", "details"])
            self.df.loc[len(self.df)] = {
                "source": upstream_node,
                "relationship": relationship,
                "target": downstream_node,
                "details": details,
            }

    def add_custom_relation(
        self,
        upstream_dataset: str,
        upstream_column: str,
        downstream_dataset: str,
        downstream_column: str,
    ) -> Dict[str, str]:
        """Validate, persist, and apply a directional table-column relationship."""
        upstream_file, upstream_node, upstream_columns = self._normalize_dataset(upstream_dataset)
        downstream_file, downstream_node, downstream_columns = self._normalize_dataset(downstream_dataset)

        if upstream_node == downstream_node:
            raise ValueError("Upstream and downstream datasets must be different.")
        if upstream_column not in upstream_columns:
            raise ValueError(f"Column '{upstream_column}' does not exist in '{upstream_file}'.")
        if downstream_column not in downstream_columns:
            raise ValueError(f"Column '{downstream_column}' does not exist in '{downstream_file}'.")

        relation = {
            "upstream_dataset": upstream_file,
            "upstream_column": upstream_column,
            "downstream_dataset": downstream_file,
            "downstream_column": downstream_column,
        }
        relations = self.get_custom_relations()
        if relation not in relations:
            relations.append(relation)
            self._save_custom_relations(relations)

        self._apply_custom_relation(relation)
        return {
            **relation,
            "source": upstream_node,
            "target": downstream_node,
            "relationship": f"maps: {upstream_column} → {downstream_column}",
        }

    def delete_custom_relation(
        self,
        upstream_dataset: str,
        upstream_column: str,
        downstream_dataset: str,
        downstream_column: str,
    ) -> Optional[Dict[str, str]]:
        """Delete one exact manual mapping and rebuild the live graph."""
        upstream_file, _, _ = self._normalize_dataset(upstream_dataset)
        downstream_file, _, _ = self._normalize_dataset(downstream_dataset)
        relation = {
            "upstream_dataset": upstream_file,
            "upstream_column": upstream_column,
            "downstream_dataset": downstream_file,
            "downstream_column": downstream_column,
        }

        relations = self.get_custom_relations()
        if relation not in relations:
            return None

        relations.remove(relation)
        self._save_custom_relations(relations)
        self.load_graph()
        return relation

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
        Maps Query -> Domain -> Dataset -> Shared Entity.
        """
        sub_nodes = set()
        sub_edges = []
        
        query_node_id = f"Query: {query[:30]}..."
        nodes_list = [{
            "id": query_node_id,
            "label": query_node_id,
            "category": "Query",
            "description": f"User query: {query}"
        }]

        matched_nodes = self.find_matching_nodes(query)
        seen_entities = set()
        
        for node in matched_nodes[:3]:
            # Link query directly to domains, datasets, shared entities, or metrics that match
            if node.startswith("Domain: ") or node.startswith("Shared Entity: ") or node.startswith("Dataset: ") or node.startswith("Metric: "):
                sub_nodes.add(node)
                sub_edges.append({
                    "source": query_node_id,
                    "target": node,
                    "relation": "asks_about",
                    "details": "Keyword match"
                })
                
                # Traverse outwards (incoming and outgoing to catch dataset links)
                if node not in seen_entities:
                    seen_entities.add(node)
                    t_res = self.traverse_graph(node)
                    if t_res.get("found"):
                        for edge in t_res.get("outgoing_edges", []) + t_res.get("incoming_edges", []):
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

        for n in sub_nodes:
            attrs = self.graph.nodes[n] if n in self.graph.nodes else {}
            category = "Entity"
            if n.startswith("Domain: "): category = "Domain Cluster"
            elif n.startswith("Dataset: "): category = "Dataset"
            elif n.startswith("Shared Entity: "): category = "Key Info Link"
            elif n.startswith("Metric: "): category = "Business Metric"
            elif "category" in attrs: category = attrs["category"]
            
            nodes_list.append({
                "id": str(n),
                "label": str(n).replace("Domain: ", "").replace("Dataset: ", "").replace("Shared Entity: ", "").replace("Metric: ", ""),
                "category": category,
                "description": attrs.get("details", "")
            })

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
        Enforces clear executive tier levels:
          Tier 0: Domains (Top level cluster)
          Tier 1: Datasets (Middle level containers)
          Tier 2: Shared Entities (Bottom level linkages)
        """
        metadata = {}
        for n in self.graph.nodes:
            if n.startswith("Domain: "):
                lvl = 0
                node_type = "root"
            elif n.startswith("Dataset: "):
                lvl = 1
                node_type = "decision_fault"
            elif n.startswith("Shared Entity: "):
                lvl = 2
                node_type = "root_cause"
            elif n.startswith("Metric: "):
                lvl = 3
                node_type = "remedy_action"
            else:
                lvl = 3
                node_type = "remedy_action"

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

