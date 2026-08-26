from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class SemanticField(BaseModel):
    name: str
    physical_name: str
    type: str
    description: str
    is_sensitive: bool = False

class SemanticEntity(BaseModel):
    name: str
    physical_dataset: str
    description: str
    fields: Dict[str, SemanticField]
    default_limit: int = 100

class SemanticRegistry:
    """
    Business layer abstraction.
    Maps high-level semantic concepts (like 'Engineer') to physical datasets.
    Provides definitions, sensitive fields tracking, and metadata for the LLM.
    """
    def __init__(self):
        self._entities: Dict[str, SemanticEntity] = {}
        self._load_defaults()

    def _load_defaults(self):
        # Register Engineer Productivity
        self.register_entity(SemanticEntity(
            name="EngineerProductivity",
            physical_dataset="engineer_productivity",
            description="Metrics tracking productivity, available hours, and completion rates of engineers.",
            fields={
                "engineer_id": SemanticField(name="engineer_id", physical_name="engineer_id", type="string", description="Unique ID of the engineer"),
                "region": SemanticField(name="region", physical_name="region", type="string", description="Operating region"),
                "productivity": SemanticField(name="productivity", physical_name="productivity_score", type="float", description="Calculated productivity score (completed_jobs / available_hours)"),
                "available_hours": SemanticField(name="available_hours", physical_name="available_hours", type="int", description="Total hours available in period"),
                "completed_jobs": SemanticField(name="completed_jobs", physical_name="completed_jobs", type="int", description="Number of jobs completed")
            }
        ))
        
        # Register Regional Demand
        self.register_entity(SemanticEntity(
            name="RegionalDemand",
            physical_dataset="regional_demand_forecast",
            description="Forecasted demand for services by region and period.",
            fields={
                "region": SemanticField(name="region", physical_name="region", type="string", description="Operating region"),
                "period": SemanticField(name="period", physical_name="period", type="string", description="Time period for the forecast (e.g., 2026-Q2)"),
                "demand": SemanticField(name="demand", physical_name="forecasted_demand", type="int", description="Forecasted demand volume")
            }
        ))
        
        # Register Engineer Capacity
        self.register_entity(SemanticEntity(
            name="EngineerCapacity",
            physical_dataset="engineer_skill",
            description="Skills and total capacity of engineers per region.",
            fields={
                "region": SemanticField(name="region", physical_name="region", type="string", description="Operating region"),
                "skill": SemanticField(name="skill", physical_name="primary_skill", type="string", description="Primary engineering skill")
            }
        ))

    def register_entity(self, entity: SemanticEntity):
        self._entities[entity.name] = entity

    def get_entity(self, name: str) -> Optional[SemanticEntity]:
        return self._entities.get(name)

    def resolve_physical_dataset(self, entity_name: str) -> Optional[str]:
        entity = self.get_entity(entity_name)
        return entity.physical_dataset if entity else None

    def get_all_entities(self) -> List[SemanticEntity]:
        return list(self._entities.values())

semantic_registry = SemanticRegistry()
