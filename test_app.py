"""
Automated Verification Test Script for Utilities Knowledge Hub.
"""

import sys
from pathlib import Path

# Force UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import KB_FILE_PATH, METRICS_FILE_PATH, ACCESS_FILE_PATH, OPERATIONS_FILE_PATH
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.agent.tools import register_services
from app.agent.agent_builder import process_chat_message


def run_tests():
    print("--- 1. Testing Services ---")
    kg = KnowledgeGraphService(KB_FILE_PATH)
    ds = DataService(METRICS_FILE_PATH, ACCESS_FILE_PATH, OPERATIONS_FILE_PATH)
    register_services(kg, ds)

    # Test Graph Traversal
    kg_res = kg.traverse_graph("EA_Error")
    assert kg_res["found"] is True
    # Test RAG Search & Hybrid Graph-RAG
    rag_docs = kg.rag_search("Worcester Bosch EA error electrode")
    assert len(rag_docs) > 0
    print(f"[PASS] RAG Search retrieved {len(rag_docs)} context documents. Top match: {rag_docs[0]['source']} -> {rag_docs[0]['target']}")

    hybrid_res = kg.hybrid_graph_rag_search("How to fix EA Error on Worcester Bosch?")
    assert len(hybrid_res["rag_context_documents"]) > 0 or len(hybrid_res["graph_traversals"]) > 0
    print(f"[PASS] Hybrid Graph-RAG Search retrieved context documents & graph traversal paths.")

    # Test Data Access Permissions
    customer_check = ds.check_access_permission("Customer", "Live_Metrics")
    assert customer_check["access_granted"] is False
    print(f"[PASS] Policy Check (Customer -> Live_Metrics): Denied as expected ({customer_check['status']})")

    employee_check = ds.check_access_permission("Employee", "Live_Metrics")
    assert employee_check["access_granted"] is True
    print(f"[PASS] Policy Check (Employee -> Live_Metrics): Granted as expected ({employee_check['status']})")

    # Test Metrics
    metrics_res = ds.get_live_metrics("grid_pressure_psi")
    assert metrics_res["success"] is True
    print(f"[PASS] Live Metrics Query: {metrics_res['metrics'][0]['metric_name']} = {metrics_res['metrics'][0]['value']} {metrics_res['metrics'][0]['unit']}")

    business_res = ds.get_business_data("boiler installation")
    assert business_res["success"] is True
    definition_res = ds.get_metric_definitions("What is sales conversion?")
    assert definition_res["success"] is True
    print("[PASS] Business Operations and metric-definition datasets queried successfully.")

    print("\n--- 2. Testing Agentic Workflows ---")
    
    # Troubleshooting query utilizing RAG + Knowledge Graph
    trouble_response = process_chat_message("How do I troubleshoot EA Error on Worcester Bosch 4000?", "user@centrica.com")
    print("\n[Troubleshooting RAG + Graph Query Output]:")
    print(trouble_response)
    assert "RAG Document Snippets" in trouble_response or "Knowledge Graph" in trouble_response or "EA_Error" in trouble_response
    print("[PASS] RAG + Knowledge Graph query response verified.")

    # User asks for Live Metrics -> Must require dataset access & prompt for IT Ticket
    metrics_req_response = process_chat_message("What is the grid pressure PSI?", "user@centrica.com")
    print("\n[Dataset Access Required Output]:")
    print(metrics_req_response)
    assert "Dataset Access Required" in metrics_req_response or "IT access request" in metrics_req_response
    print("[PASS] Dataset Access Requirement & Ticket Offer verified.")

    # User confirms IT Ticket creation -> Ticket generated
    ticket_response = process_chat_message("Yes please raise an IT access request ticket.", "user@centrica.com")
    print("\n[Ticket Creation Output]:")
    print(ticket_response)
    assert "TICK-" in ticket_response
    print("[PASS] Ticket Generation (TICK-XXXX) verified.")

    # Lineage & SME query
    lineage_response = process_chat_message("Who is the SME for Sales_Funnel_Dataset?", "user@centrica.com")
    print("\n[Lineage & SME Query Output]:")
    print(lineage_response)
    assert "Sarah Jenkins" in lineage_response or "Sales_Funnel_Dataset" in lineage_response
    print("[PASS] Centrica Enterprise Data Lineage & SME Attribution query verified.")

    print("\n[SUCCESS] ALL AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
