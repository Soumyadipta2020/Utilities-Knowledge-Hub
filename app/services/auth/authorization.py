from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class UserContext(BaseModel):
    user_id: str
    role: str
    region: Optional[str] = None
    department: Optional[str] = None

class AuthorizationResult(BaseModel):
    allowed: bool
    reason: str
    filters: Dict[str, Any] = {} # Row-level filters imposed by ABAC

class AuthorizationManager:
    """
    Handles both Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC).
    """
    
    def __init__(self):
        # RBAC definitions
        self.role_permissions = {
            "admin": ["*"],
            "executive": ["metrics", "aggregated_data", "regional_demand", "engineer_productivity"],
            "operations_manager": ["operational_data", "engineer_capacity", "work_orders", "engineer_productivity", "regional_demand"],
            "customer_service": ["customer_profile", "customer_history"],
            "engineer": ["own_work_orders", "knowledge_base"],
            "analyst": ["aggregated_data", "regional_demand"]
        }
        
    def authorize_tool(self, user_context: UserContext, tool_name: str, args: Dict[str, Any]) -> AuthorizationResult:
        """
        Authorize if a user can execute a specific business tool with the given arguments.
        """
        role = user_context.role.lower()
        if role == "admin":
            return AuthorizationResult(allowed=True, reason="Admin has full demo access.")
            
        allowed_tools = self.role_permissions.get(role, [])
        
        # Simple RBAC check (mapping tools to categories could be more complex in a real system)
        tool_category_map = {
            "get_engineer_productivity": "engineer_productivity",
            "get_regional_demand": "regional_demand",
            "get_engineer_capacity": "engineer_capacity",
            "get_customer_profile": "customer_profile"
        }
        
        required_category = tool_category_map.get(tool_name)
        if required_category and required_category not in allowed_tools and "*" not in allowed_tools:
            return AuthorizationResult(allowed=False, reason=f"Role '{role}' is not permitted to access '{required_category}'.")
            
        # ABAC checks (e.g., Operations Manager can only access their assigned region)
        abac_filters = {}
        if role == "operations_manager" and user_context.region:
            requested_region = args.get("region")
            if requested_region and requested_region.lower() != user_context.region.lower():
                return AuthorizationResult(allowed=False, reason=f"Operations Manager can only access region '{user_context.region}'.")
            # Automatically impose a filter if region wasn't explicitly requested but ABAC demands it
            if not requested_region:
                abac_filters["region"] = user_context.region
                
        return AuthorizationResult(allowed=True, reason="Authorized by RBAC and ABAC policies.", filters=abac_filters)

auth_manager = AuthorizationManager()
