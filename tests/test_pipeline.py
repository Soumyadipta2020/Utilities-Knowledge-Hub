"""
Automated Verification Test for 12-Stage Knowledge Harnessing Pipeline & Metrics.
"""

import sys
from pathlib import Path

# Force UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import DATA_DIR
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.services.pipeline_service import KnowledgeHarnessingPipeline
from app.main import app


def test_pipeline_engine():
    print("--- 1. Testing KnowledgeHarnessingPipeline Engine ---")
    kg = KnowledgeGraphService(DATA_DIR)
    ds = DataService(DATA_DIR)
    pipeline = KnowledgeHarnessingPipeline(DATA_DIR, kg, ds)

    for stage_id in range(1, 13):
        res = pipeline.execute_stage(stage_id)
        assert res["status"] == "done"
        assert "duration_ms" in res
        assert "log" in res
        assert "metrics" in res
        print(f"[PASS] Stage {stage_id} ({res['name']}): Completed in {res['duration_ms']} ms -> {res['log']}")

    metrics = pipeline.get_harnessing_metrics()
    assert "knowledge_harnessing" in metrics
    assert "information_harnessing" in metrics
    assert "inference_harnessing" in metrics
    assert "outcome_harnessing" in metrics
    assert "benchmarking" in metrics
    assert "storage" in metrics
    print("\n[PASS] Harnessing metrics generated successfully across all 6 domain areas.")


def test_flask_endpoints():
    print("\n--- 2. Testing Flask API Endpoints ---")
    client = app.test_client()

    # Test /api/pipeline/run-stage/1
    stage1_res = client.post("/api/pipeline/run-stage/1")
    assert stage1_res.status_code == 200
    data1 = stage1_res.get_json()
    assert data1["success"] is True
    assert data1["stage"]["id"] == 1
    print(f"[PASS] POST /api/pipeline/run-stage/1 -> OK (Overall progress: {data1['overall_progress']}%)")

    # Test /api/harnessing/metrics
    metrics_res = client.get("/api/harnessing/metrics")
    assert metrics_res.status_code == 200
    mdata = metrics_res.get_json()
    assert mdata["success"] is True
    print("[PASS] GET /api/harnessing/metrics -> OK")

    # Security Center starts with a non-zero illustrative baseline and uses the
    # same enterprise provider topology as Storage & Governance.
    baseline_res = client.get("/api/trust/summary")
    assert baseline_res.status_code == 200
    baseline_security = baseline_res.get_json()["summary"]
    baseline_activity = baseline_security["access_activity"]
    assert baseline_activity["total_touches"] > 0
    assert baseline_activity["unique_users"] > 0
    assert len(baseline_activity["datasets"]) >= 6
    assert len(baseline_security["storage"]) == 9
    assert any(store["name"] == "Databricks UC Database" for store in baseline_security["storage"])
    assert all(store["is_demonstration"] is True for store in baseline_security["storage"])
    baseline_telemetry = next(
        row for row in baseline_activity["datasets"]
        if row["dataset"] == "boiler_telemetry_logs"
    )

    # A new access request entered through chat increments its dataset row.
    chat_res = client.post("/api/chat", json={
        "message": "I need access to restricted operational telemetry for Project Apollo",
        "user_email": "test.user@abc.com",
    })
    assert chat_res.status_code == 200
    chat_data = chat_res.get_json()
    assert chat_data["success"] is True
    assert "trust" not in chat_data
    updated_security = client.get("/api/trust/summary").get_json()["summary"]
    updated_telemetry = next(
        row for row in updated_security["access_activity"]["datasets"]
        if row["dataset"] == "boiler_telemetry_logs"
    )
    assert updated_telemetry["touches"] > baseline_telemetry["touches"]
    assert updated_telemetry["access_requests"] > baseline_telemetry["access_requests"]
    assert updated_telemetry["has_live_activity"] is True
    print("[PASS] POST /api/chat -> new access request added to telemetry row")

    confirm_res = client.post("/api/chat", json={
        "message": "Yes please raise the access request",
        "user_email": "test.user@abc.com",
    })
    assert confirm_res.status_code == 200
    confirmed_activity = client.get("/api/trust/summary").get_json()["summary"]["access_activity"]
    confirmed_telemetry = next(
        row for row in confirmed_activity["datasets"]
        if row["dataset"] == "boiler_telemetry_logs"
    )
    assert confirmed_telemetry["access_requests"] > updated_telemetry["access_requests"]
    print("[PASS] Confirmed chat access ticket also increments the dataset row")

    # Security Center reports credentials, enterprise storage, access counts, and controls.
    trust_res = client.get("/api/trust/summary")
    assert trust_res.status_code == 200
    trust_data = trust_res.get_json()
    assert trust_data["success"] is True
    security = trust_data["summary"]
    assert security["credentials"]
    assert all("value" not in credential for credential in security["credentials"])
    assert security["storage"]
    assert any(store["name"] == "Microsoft OneLake" for store in security["storage"])
    assert security["access_activity"]["total_touches"] > 0
    assert security["access_activity"]["unique_users"] > 0
    assert security["access_activity"]["datasets"]
    assert security["protections"]
    print("[PASS] GET /api/trust/summary -> security posture and access counts verified")

    # The architecture tab is removed and the focused Security Center is rendered.
    page_res = client.get("/")
    page_html = page_res.get_data(as_text=True)
    assert 'id="tab-architecture"' not in page_html
    assert 'Business & Technology Architecture' not in page_html
    assert 'id="tab-trust"' in page_html
    assert 'id="securityCredentials"' in page_html
    assert 'id="securityAccessTable"' in page_html
    assert 'id="securityProtectionRegister"' in page_html
    assert 'id="trustDrawer"' not in page_html
    print("[PASS] Focused application Security Center UI rendered")

    # Test /api/pipeline/run
    full_res = client.post("/api/pipeline/run")
    assert full_res.status_code == 200
    fdata = full_res.get_json()
    assert fdata["success"] is True
    assert len(fdata["stages"]) == 12
    # Test /api/datasource/preview/customer_master.csv
    ds_res = client.get("/api/datasource/preview/customer_master.csv")
    assert ds_res.status_code == 200
    ds_data = ds_res.get_json()
    assert ds_data["success"] is True
    assert ds_data["total_rows"] > 0
    assert len(ds_data["columns"]) > 0
    print(f"[PASS] GET /api/datasource/preview/customer_master.csv -> OK ({ds_data['total_rows']} rows, columns: {ds_data['columns']})")

    # Direct dataset previews are also reflected in per-dataset security counts.
    post_preview_security = client.get("/api/trust/summary").get_json()["summary"]["access_activity"]
    customer_activity = next(
        row for row in post_preview_security["datasets"]
        if row["dataset"] == "customer_master"
    )
    assert customer_activity["touches"] > 184
    assert customer_activity["storage_provider"] == "Salesforce CRM"
    print("[PASS] Direct dataset preview included in security access activity")


if __name__ == "__main__":
    test_pipeline_engine()
    test_flask_endpoints()
    print("\n✅ ALL PIPELINE & HARNESSING TESTS PASSED PERFECTLY!")
