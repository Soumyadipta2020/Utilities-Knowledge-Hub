"""
Automated Verification Test for 12-Stage Knowledge Harnessing Pipeline & Metrics.
"""

import sys
from pathlib import Path

# Force UTF-8 stdout encoding for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from app.config import KB_FILE_PATH, METRICS_FILE_PATH, ACCESS_FILE_PATH, OPERATIONS_FILE_PATH, DATA_DIR
from app.services.graph_service import KnowledgeGraphService
from app.services.data_service import DataService
from app.services.pipeline_service import KnowledgeHarnessingPipeline
from app.main import app


def test_pipeline_engine():
    print("--- 1. Testing KnowledgeHarnessingPipeline Engine ---")
    kg = KnowledgeGraphService(KB_FILE_PATH)
    ds = DataService(METRICS_FILE_PATH, ACCESS_FILE_PATH, OPERATIONS_FILE_PATH)
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

    # Test /api/pipeline/run
    full_res = client.post("/api/pipeline/run")
    assert full_res.status_code == 200
    fdata = full_res.get_json()
    assert fdata["success"] is True
    assert len(fdata["stages"]) == 12
    # Test /api/datasource/preview/Information_Harnessing_Source.xlsx
    ds_res = client.get("/api/datasource/preview/Information_Harnessing_Source.xlsx")
    assert ds_res.status_code == 200
    ds_data = ds_res.get_json()
    assert ds_data["success"] is True
    assert ds_data["total_rows"] > 0
    assert len(ds_data["columns"]) > 0
    print(f"[PASS] GET /api/datasource/preview/Information_Harnessing_Source.xlsx -> OK ({ds_data['total_rows']} rows, columns: {ds_data['columns']})")


if __name__ == "__main__":
    test_pipeline_engine()
    test_flask_endpoints()
    print("\n✅ ALL PIPELINE & HARNESSING TESTS PASSED PERFECTLY!")
