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

from app.config import KB_FILE_PATH, METRICS_FILE_PATH, ACCESS_FILE_PATH
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.agent.tools import register_services
from app.agent.agent_builder import process_chat_message


def run_tests():
    print("--- 1. Testing Services ---")
    kg = KnowledgeGraphService(KB_FILE_PATH)
    ds = DataService(METRICS_FILE_PATH, ACCESS_FILE_PATH)
    register_services(kg, ds)

    # Test Graph Traversal
    kg_res = kg.traverse_graph("EA_Error")
    assert kg_res["found"] is True
    print(f"[PASS] Knowledge Graph traversal successful! Found entity: {kg_res['matched_entity']}")

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

    print("\n--- 2. Testing Agentic Workflows ---")
    
    # Customer asks for Live Metrics -> Must be DENIED & prompt for IT Ticket
    cust_response = process_chat_message("What is the grid pressure PSI?", "Customer", "customer@test.com")
    print("\n[Customer Query Output]:")
    print(cust_response)
    assert "Access Denied" in cust_response or "Access Denied!" in cust_response
    assert "IT access request" in cust_response or "raise an IT" in cust_response
    print("[PASS] Customer Access Denial & Ticket Offer verified.")

    # Employee asks for Live Metrics -> Must be GRANTED & return metric data
    emp_response = process_chat_message("What is the grid pressure PSI?", "Employee", "employee@test.com")
    print("\n[Employee Query Output]:")
    print(emp_response)
    assert "42.5 PSI" in emp_response or "grid_pressure_psi" in emp_response
    print("[PASS] Employee Access Grant & Metric telemetry output verified.")

    # Customer confirms IT Ticket creation -> Ticket generated
    ticket_response = process_chat_message("Yes please raise an IT access request ticket.", "Customer", "customer@test.com")
    print("\n[Ticket Creation Output]:")
    print(ticket_response)
    assert "TICK-" in ticket_response
    print("[PASS] Ticket Generation (TICK-XXXX) verified.")

    print("\n[SUCCESS] ALL AUTOMATED VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()
