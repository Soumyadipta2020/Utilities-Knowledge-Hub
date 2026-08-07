"""
Knowledge Graph Service using NetworkX.
Loads entity-relationship data from Excel and provides graph traversal capabilities.
"""

from typing import Dict, List, Any, Optional, Tuple
import json
import re
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

    def get_relation_entity_catalog(self) -> List[Dict[str, Any]]:
        """Return every graph object, its tier/category, and optional CSV columns."""
        dataset_columns = {
            dataset["node_id"]: dataset["columns"]
            for dataset in self.get_dataset_catalog()
        }
        tree_metadata = self.get_decision_tree_metadata()
        catalog = []
        for node_id, attrs in self.graph.nodes(data=True):
            metadata = tree_metadata.get(str(node_id), {})
            catalog.append({
                "id": str(node_id),
                "label": str(node_id),
                "category": attrs.get("category", "Entity"),
                "tree_level": metadata.get("tree_level", 3),
                "columns": dataset_columns.get(str(node_id), []),
            })
        return sorted(
            catalog,
            key=lambda entity: (
                entity["tree_level"],
                entity["category"].casefold(),
                entity["label"].casefold(),
            ),
        )

    @staticmethod
    def _safe_context_value(value: Any) -> Any:
        """Convert dataframe and graph values into compact JSON-safe prompt context."""
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if isinstance(value, (str, int, float, bool)):
            safe_value = value
        else:
            safe_value = str(value)
        if isinstance(safe_value, str):
            return safe_value[:160]
        return safe_value

    def get_relation_object_context(
        self,
        node_id: str,
        sample_rows: int = 4,
        max_columns: int = 30,
    ) -> Dict[str, Any]:
        """Build bounded metadata, graph, schema, and data context for one object."""
        if node_id not in self.graph:
            raise ValueError(f"Object '{node_id}' does not exist in the Knowledge Graph.")

        attrs = dict(self.graph.nodes[node_id])
        tree_metadata = self.get_decision_tree_metadata().get(node_id, {})
        context: Dict[str, Any] = {
            "id": node_id,
            "category": str(attrs.get("category", "Entity")),
            "entity_type": str(attrs.get("entity_type", "Entity")),
            "tree_level": tree_metadata.get("tree_level", 3),
            "metadata": {
                str(key): self._safe_context_value(value)
                for key, value in attrs.items()
                if key not in {"category", "entity_type"}
            },
            "columns": [],
            "column_profiles": [],
            "sample_records": [],
            "neighboring_relationships": [],
        }

        neighbor_rows = []
        for _, target, edge in self.graph.out_edges(node_id, data=True):
            neighbor_rows.append({
                "direction": "outgoing",
                "other_object": str(target),
                "relationship": str(edge.get("relationship", "connected_to"))[:160],
                "details": str(edge.get("details", ""))[:240],
            })
        for source, _, edge in self.graph.in_edges(node_id, data=True):
            neighbor_rows.append({
                "direction": "incoming",
                "other_object": str(source),
                "relationship": str(edge.get("relationship", "connected_to"))[:160],
                "details": str(edge.get("details", ""))[:240],
            })
        context["neighboring_relationships"] = neighbor_rows[:16]

        if not node_id.startswith("Dataset: "):
            return context

        filename, _, all_columns = self._normalize_dataset(node_id)
        context["columns"] = all_columns
        csv_path = self.data_dir / filename
        try:
            sample_df = pd.read_csv(csv_path, nrows=max(sample_rows, 24))
        except Exception as error:
            context["metadata"]["sample_error"] = str(error)[:200]
            return context

        prompt_columns = list(sample_df.columns)[:max_columns]
        sample_subset = sample_df[prompt_columns].head(sample_rows)
        context["sample_records"] = [
            {
                str(column): self._safe_context_value(value)
                for column, value in record.items()
            }
            for record in sample_subset.to_dict(orient="records")
        ]

        profiles = []
        for column in prompt_columns:
            series = sample_df[column].dropna()
            unique_values = []
            seen_values = set()
            for raw_value in series.tolist():
                safe_value = self._safe_context_value(raw_value)
                marker = str(safe_value).casefold()
                if marker in seen_values:
                    continue
                seen_values.add(marker)
                unique_values.append(safe_value)
                if len(unique_values) == 6:
                    break
            profiles.append({
                "name": str(column),
                "dtype": str(sample_df[column].dtype),
                "non_null_in_sample": int(series.shape[0]),
                "unique_in_sample": int(series.nunique(dropna=True)),
                "sample_values": unique_values,
            })
        context["column_profiles"] = profiles
        return context

    @staticmethod
    def _normalized_column_name(column: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(column).casefold())

    def get_relation_join_candidates(
        self,
        source_context: Dict[str, Any],
        target_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Rank grounded join-column candidates using names and sampled values."""
        source_profiles = {
            item["name"]: item
            for item in source_context.get("column_profiles", [])
        }
        target_profiles = {
            item["name"]: item
            for item in target_context.get("column_profiles", [])
        }
        candidates = []
        generic_tokens = {"id", "key", "code", "number", "no", "name", "date", "type", "status"}

        for source_column in source_context.get("columns", []):
            for target_column in target_context.get("columns", []):
                source_normalized = self._normalized_column_name(source_column)
                target_normalized = self._normalized_column_name(target_column)
                score = 0.0
                reasons = []

                if str(source_column).casefold() == str(target_column).casefold():
                    score = 1.0
                    reasons.append("exact column-name match")
                elif source_normalized and source_normalized == target_normalized:
                    score = 0.96
                    reasons.append("normalized column-name match")
                else:
                    source_tokens = {
                        token for token in re.split(r"[^a-z0-9]+", str(source_column).casefold())
                        if token and token not in generic_tokens
                    }
                    target_tokens = {
                        token for token in re.split(r"[^a-z0-9]+", str(target_column).casefold())
                        if token and token not in generic_tokens
                    }
                    meaningful_overlap = source_tokens & target_tokens
                    if meaningful_overlap:
                        score = 0.82
                        reasons.append(f"shared name token: {', '.join(sorted(meaningful_overlap))}")

                source_values = {
                    str(value).strip().casefold()
                    for value in source_profiles.get(source_column, {}).get("sample_values", [])
                    if value is not None and str(value).strip()
                }
                target_values = {
                    str(value).strip().casefold()
                    for value in target_profiles.get(target_column, {}).get("sample_values", [])
                    if value is not None and str(value).strip()
                }
                shared_values = source_values & target_values
                if len(shared_values) >= 2:
                    overlap_ratio = len(shared_values) / max(1, min(len(source_values), len(target_values)))
                    if overlap_ratio >= 0.5:
                        score = max(score, min(0.94, 0.68 + (overlap_ratio * 0.26)))
                        reasons.append(f"{len(shared_values)} overlapping sampled values")

                if score >= 0.68:
                    candidates.append({
                        "source_column": str(source_column),
                        "target_column": str(target_column),
                        "score": round(score, 2),
                        "reason": "; ".join(reasons),
                    })

        return sorted(
            candidates,
            key=lambda item: (-item["score"], item["source_column"].casefold(), item["target_column"].casefold()),
        )[:12]

    def get_relation_suggestion_context(self, source: str, target: str) -> Dict[str, Any]:
        """Return both bounded object contexts and locally grounded join candidates."""
        if source == target:
            raise ValueError("Source and target objects must be different.")
        source_context = self.get_relation_object_context(source)
        target_context = self.get_relation_object_context(target)
        return {
            "source": source_context,
            "target": target_context,
            "join_candidates": self.get_relation_join_candidates(source_context, target_context),
        }

    def _normalize_custom_relation_record(self, relation: Dict[str, Any]) -> Dict[str, str]:
        """Convert current or legacy dataset-only records to the generic schema."""
        if "source" in relation and "target" in relation:
            return {
                "source": str(relation.get("source") or "").strip(),
                "target": str(relation.get("target") or "").strip(),
                "relationship": str(relation.get("relationship") or "related_to").strip(),
                "source_column": str(relation.get("source_column") or "").strip(),
                "target_column": str(relation.get("target_column") or "").strip(),
            }

        upstream = str(relation.get("upstream_dataset") or "").strip()
        downstream = str(relation.get("downstream_dataset") or "").strip()
        if upstream and not upstream.startswith("Dataset: "):
            upstream = f"Dataset: {Path(upstream).name}"
        if downstream and not downstream.startswith("Dataset: "):
            downstream = f"Dataset: {Path(downstream).name}"
        return {
            "source": upstream,
            "target": downstream,
            "relationship": "maps",
            "source_column": str(relation.get("upstream_column") or "").strip(),
            "target_column": str(relation.get("downstream_column") or "").strip(),
        }

    def get_custom_relations(self) -> List[Dict[str, str]]:
        """Load persisted manual relationships using the generic entity schema."""
        if not self.custom_relations_path.exists():
            return []
        try:
            data = json.loads(self.custom_relations_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return [
                normalized
                for item in data
                if isinstance(item, dict)
                for normalized in [self._normalize_custom_relation_record(item)]
                if normalized["source"] and normalized["target"]
            ]
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

    def _get_entity_columns(self, node_id: str) -> List[str]:
        """Return columns for dataset nodes; other graph objects have no columns."""
        if not node_id.startswith("Dataset: "):
            return []
        _, _, columns = self._normalize_dataset(node_id)
        return columns

    @staticmethod
    def _format_custom_relationship(relation: Dict[str, str]) -> str:
        """Build the edge label shown by the graph visualizer."""
        relationship = relation["relationship"]
        source_column = relation.get("source_column", "")
        target_column = relation.get("target_column", "")
        if source_column or target_column:
            source_label = source_column or "object"
            target_label = target_column or "object"
            return f"{relationship}: {source_label} → {target_label}"
        return relationship

    def _validate_custom_relation(self, relation: Dict[str, str]) -> None:
        """Validate entity existence, direction, relationship label, and columns."""
        source = relation["source"]
        target = relation["target"]
        if source not in self.graph:
            raise ValueError(f"Source object '{source}' does not exist in the Knowledge Graph.")
        if target not in self.graph:
            raise ValueError(f"Target object '{target}' does not exist in the Knowledge Graph.")
        if source == target:
            raise ValueError("Source and target objects must be different.")
        if not relation["relationship"]:
            raise ValueError("A relationship label is required.")
        if len(relation["relationship"]) > 80:
            raise ValueError("Relationship label must be 80 characters or fewer.")

        source_column = relation.get("source_column", "")
        target_column = relation.get("target_column", "")
        source_columns = self._get_entity_columns(source)
        target_columns = self._get_entity_columns(target)
        if source_column and source_column not in source_columns:
            raise ValueError(f"Column '{source_column}' does not exist on '{source}'.")
        if target_column and target_column not in target_columns:
            raise ValueError(f"Column '{target_column}' does not exist on '{target}'.")

    def _apply_custom_relation(self, relation: Dict[str, str]) -> None:
        """Apply one generic manual relationship to both graph representations."""
        relation = self._normalize_custom_relation_record(relation)
        self._validate_custom_relation(relation)
        source = relation["source"]
        target = relation["target"]
        existing_edge = self.graph.get_edge_data(source, target) or {}
        manual_relationships = list(existing_edge.get("manual_relationships", [])) if existing_edge.get("is_custom") else []
        is_new_mapping = relation not in manual_relationships
        if is_new_mapping:
            manual_relationships.append(relation)

        relationship_labels = [
            self._format_custom_relationship(item)
            for item in manual_relationships
        ]
        relationship = " | ".join(relationship_labels)
        details = f"Manual relationships: {', '.join(relationship_labels)}"
        self.graph.add_edge(
            source,
            target,
            relationship=relationship,
            details=details,
            is_custom=True,
            source_column=relation.get("source_column", ""),
            target_column=relation.get("target_column", ""),
            upstream_column=relation.get("source_column", ""),
            downstream_column=relation.get("target_column", ""),
            manual_relationships=manual_relationships,
            column_mappings=[
                {
                    "upstream_column": item.get("source_column", ""),
                    "downstream_column": item.get("target_column", ""),
                }
                for item in manual_relationships
                if item.get("source_column") or item.get("target_column")
            ],
        )
        if is_new_mapping:
            relationship_label = self._format_custom_relationship(relation)
            self.langchain_graph.add_triple(KnowledgeTriple(source, relationship_label, target))
            if self.df is None:
                self.df = pd.DataFrame(columns=["source", "relationship", "target", "details"])
            self.df.loc[len(self.df)] = {
                "source": source,
                "relationship": relationship_label,
                "target": target,
                "details": f"Manually defined relationship: {relationship_label}",
            }

    def add_custom_relation(
        self,
        source: str,
        target: str,
        relationship: str,
        source_column: str = "",
        target_column: str = "",
    ) -> Dict[str, str]:
        """Validate, persist, and apply a directional relationship between graph objects."""
        relation = self._normalize_custom_relation_record({
            "source": source,
            "target": target,
            "relationship": relationship,
            "source_column": source_column,
            "target_column": target_column,
        })
        self._validate_custom_relation(relation)
        relations = self.get_custom_relations()
        if relation not in relations:
            relations.append(relation)
        self._save_custom_relations(relations)

        self._apply_custom_relation(relation)
        return {
            **relation,
            "display_relationship": self._format_custom_relationship(relation),
        }

    def delete_custom_relation(
        self,
        source: str,
        target: str,
        relationship: str,
        source_column: str = "",
        target_column: str = "",
    ) -> Optional[Dict[str, str]]:
        """Delete one exact generic manual relationship and rebuild the live graph."""
        relation = self._normalize_custom_relation_record({
            "source": source,
            "target": target,
            "relationship": relationship,
            "source_column": source_column,
            "target_column": target_column,
        })

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
        clean_text = re.sub(r"[^\w\s]", " ", query).lower().strip()
        text_words = set(clean_text.split())
        text_words_singular = {w[:-1] if w.endswith('s') and len(w) > 3 else w for w in text_words}

        matches = []
        category_words = {"dataset", "datasets", "domain", "domains", "metric", "metrics", "shared", "entity", "entities", "csv"}

        for node in self.graph.nodes:
            clean_node = re.sub(r"[^\w\s]", " ", str(node)).lower().strip()
            node_words = set(clean_node.split())
            node_words_singular = {w[:-1] if w.endswith('s') and len(w) > 3 else w for w in node_words}
            
            # Exact substring match on full node name
            if clean_node in clean_text or clean_text in clean_node:
                matches.append(node)
                continue

            # Core name extraction without prefixes
            core = str(node)
            for prefix in ["Domain: ", "Dataset: ", "Metric: ", "Shared Entity: "]:
                if core.startswith(prefix):
                    core = core.replace(prefix, "", 1)
                    break
            if core.lower().endswith(".csv"):
                core = core[:-4]

            clean_core = re.sub(r"[^\w\s]", " ", core).lower().strip()
            core_snake = clean_core.replace(" ", "_")

            if clean_core and (clean_core in clean_text or core_snake in clean_text or any(core_snake in w for w in text_words)):
                matches.append(node)
                continue

            core_words = set(clean_core.split()) - category_words
            core_words_singular = {w[:-1] if w.endswith('s') and len(w) > 3 else w for w in core_words}

            if core_words_singular and core_words_singular.issubset(text_words_singular):
                matches.append(node)
                continue

            if core_words_singular:
                overlap = len(core_words_singular.intersection(text_words_singular))
                if overlap > 0 and overlap >= len(core_words_singular) / 2:
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

    def extract_subgraph_for_query(self, query: str, response: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract the exact sub-graph (nodes and edges) associated with a query and generated response.
        Maps Query / Response -> Domain -> Dataset -> Shared Entity.
        """
        sub_nodes = set()
        sub_edges = []
        
        tree_metadata = self.get_decision_tree_metadata()

        header_text = query[:40] if len(query) <= 40 else query[:37] + "..."
        query_node_id = f"Query: {header_text}"
        nodes_list = [{
            "id": query_node_id,
            "label": query_node_id,
            "category": "Query",
            "icon": "",
            "description": f"User query: {query}",
            "tree_level": 0,
            "node_type": "root",
            "parents": [],
            "children": []
        }]

        search_text = f"{query}\n{response}" if response else query
        matched_nodes = self.find_matching_nodes(search_text)
        seen_entities = set()
        
        for node in matched_nodes:
            # Link query directly to domains, datasets, shared entities, or metrics that match
            if node.startswith("Domain: ") or node.startswith("Shared Entity: ") or node.startswith("Dataset: ") or node.startswith("Metric: "):
                sub_nodes.add(node)
                sub_edges.append({
                    "source": query_node_id,
                    "target": node,
                    "relation": "grounded_in" if response else "asks_about",
                    "details": "Response & Query grounding match" if response else "Keyword match"
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

            # Carry the decision-tree hierarchy through so the visualiser can lay
            # the reply lineage out across its tier columns instead of piling
            # every grounding node into Tier 0.
            meta = tree_metadata.get(str(n), {})

            nodes_list.append({
                "id": str(n),
                "label": str(n).replace("Domain: ", "").replace("Dataset: ", "").replace("Shared Entity: ", "").replace("Metric: ", ""),
                "category": category,
                "description": attrs.get("details", ""),
                "tree_level": meta.get("tree_level", 3),
                "node_type": meta.get("node_type", "remedy_action"),
                "parents": meta.get("parents", []),
                "children": meta.get("children", [])
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
            "response": response,
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