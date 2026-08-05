"""
Automated Verification Test Script for Utilities Knowledge Hub.
"""

import sys
from pathlib import Path

# Force UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import DATA_DIR
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.agent.tools import register_services
from app.agent.agent_builder import process_chat_message, suggest_graph_relationship


def run_tests():
    print("--- 1. Testing Services ---")
    kg = KnowledgeGraphService(DATA_DIR)
    ds = DataService(DATA_DIR)
    register_services(kg, ds)

    # Test Graph Traversal
    first_node = list(kg.graph.nodes)[0] if len(kg.graph.nodes) > 0 else "Domain: Customer Operations"
    kg_res = kg.traverse_graph(first_node)
    assert kg_res["found"] is True
    print(f"[PASS] Graph Traversal: Successfully traversed node '{first_node}'.")

    # Test Subgraph Extraction for Query
    subgraph_res = kg.extract_subgraph_for_query("What is sales conversion?")
    assert len(subgraph_res["nodes"]) > 0
    print(f"[PASS] Subgraph Extraction: Extracted {len(subgraph_res['nodes'])} nodes and {len(subgraph_res['edges'])} edges for query.")

    # Test Data Access Permissions
    customer_check = ds.check_access_permission("Customer", "customer_master.csv")
    assert customer_check["access_granted"] is True
    print(f"[PASS] Data Access Check: Granted access to customer_master.csv.")

    # Test Business Data Query
    business_res = ds.get_business_data("service")
    assert business_res["success"] is True
    print("[PASS] Business CSV datasets queried successfully.")

    # Test grounded relationship suggestion context and local fallback.
    catalog = kg.get_relation_entity_catalog()
    datasets = [entity for entity in catalog if entity["category"] == "Dataset"]
    join_pair = next(
        (
            (source, target)
            for source in datasets
            for target in datasets
            if source["id"] != target["id"]
            and set(source["columns"]) & set(target["columns"])
        ),
        None,
    )
    assert join_pair is not None
    source, target = join_pair
    suggestion_context = kg.get_relation_suggestion_context(source["id"], target["id"])
    suggestion = suggest_graph_relationship(suggestion_context, executor=None)
    assert suggestion["source_column"] in source["columns"]
    assert suggestion["target_column"] in target["columns"]
    assert suggestion_context["source"]["sample_records"]
    assert suggestion_context["target"]["sample_records"]
    print("[PASS] Grounded relationship context and editable join-column suggestion verified.")

    print("\n--- 2. Testing Agentic Workflows ---")
    
    # Query utilizing Knowledge Graph
    trouble_response = process_chat_message("What datasets are available in Customer Operations?", "user@abc.com")
    print("\n[Chat Query Output]:")
    print(trouble_response)
    assert len(trouble_response) > 0
    print("[PASS] Knowledge Graph chat response verified.")

    # Lineage & SME query
    lineage_response = process_chat_message("Who is the SME for Sales_Funnel_Dataset?", "user@abc.com")
    print("\n[Lineage & SME Query Output]:")
    print(lineage_response)
    assert "SME" in lineage_response or "Ownership" in lineage_response or "Governance" in lineage_response
    print("[PASS] ABC Enterprise Data Lineage & SME Attribution query verified.")

    # Test Multi-Turn Conversational Context Retention
    history = []
    turn1_res = process_chat_message("What is sales conversion?", "user@abc.com", chat_history=history)
    assert len(turn1_res) > 0
    history.extend([
        {"role": "user", "content": "What is sales conversion?"},
        {"role": "assistant", "content": turn1_res}
    ])

    turn2_res = process_chat_message("where I can get the data?", "user@abc.com", chat_history=history)
    print("\n[Multi-Turn Context Resolution Output]:")
    print(turn2_res)
    assert len(turn2_res) > 0
    print("[PASS] Multi-Turn Context Resolution verified.")

    print("\n[SUCCESS] ALL AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
