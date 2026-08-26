import sys
from pathlib import Path

# Ensure repo root is in sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import pytest
from app.services.semantic.registry import semantic_registry
from app.services.auth.authorization import auth_manager, UserContext
from app.services.cache.semantic_cache import SemanticCache
from app.services.query_planner.planner import QueryPlanner

def test_semantic_registry():
    entity = semantic_registry.get_entity("EngineerProductivity")
    assert entity is not None
    assert entity.physical_dataset == "engineer_productivity"
    assert "productivity" in entity.fields
    assert entity.fields["productivity"].physical_name == "productivity_score"

def test_authorization_manager():
    # Admin context
    admin_ctx = UserContext(user_id="admin1", role="admin")
    result = auth_manager.authorize_tool(admin_ctx, "get_engineer_productivity", {})
    assert result.allowed is True
    
    # Customer Service context
    cs_ctx = UserContext(user_id="cs1", role="customer_service")
    result = auth_manager.authorize_tool(cs_ctx, "get_engineer_productivity", {})
    assert result.allowed is False
    
    # Operations Manager ABAC (Region filter)
    op_ctx = UserContext(user_id="op1", role="operations_manager", region="London")
    
    # 1. Requests same region
    res1 = auth_manager.authorize_tool(op_ctx, "get_regional_demand", {"region": "London"})
    assert res1.allowed is True
    
    # 2. Requests different region
    res2 = auth_manager.authorize_tool(op_ctx, "get_regional_demand", {"region": "North"})
    assert res2.allowed is False
    
    # 3. Requests no region (should impose ABAC filter)
    res3 = auth_manager.authorize_tool(op_ctx, "get_regional_demand", {})
    assert res3.allowed is True
    assert res3.filters["region"] == "London"

def test_semantic_cache():
    cache = SemanticCache()
    # Test L2 Cache
    cache.set_query_result("test_tool", {"region": "London"}, {"data": "test"})
    
    # Hit
    assert cache.get_query_result("test_tool", {"region": "London"}) == {"data": "test"}
    # Miss due to args
    assert cache.get_query_result("test_tool", {"region": "North"}) is None

def test_query_planner():
    planner = QueryPlanner()
    plan = planner.create_plan("Why did productivity decline in London despite sufficient capacity?")
    
    assert plan.intent == "productivity_analysis_and_capacity_analysis"
    assert "EngineerProductivity" in plan.entities
    assert "EngineerCapacity" in plan.entities
    assert plan.parallel is True
    
    # Ensure region filter was extracted
    has_london = False
    for tool in plan.tools:
        if tool["args"].get("region") == "London":
            has_london = True
    assert has_london is True
