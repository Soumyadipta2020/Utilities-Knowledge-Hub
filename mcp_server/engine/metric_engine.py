import yaml
from pathlib import Path
import sqlglot
from sqlglot import exp
import logging

logger = logging.getLogger(__name__)

class MetricEngine:
    def __init__(self):
        self.metrics = {}
        self.load_config()

    def load_config(self):
        repo_root = Path(__file__).resolve().parents[2]
        config_path = repo_root / "config" / "metrics.yaml"
        if not config_path.exists():
            logger.warning(f"Metrics configuration not found at {config_path}")
            return

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                if data and "metrics" in data:
                    for metric in data["metrics"]:
                        self.metrics[metric["name"]] = metric
            logger.info(f"Loaded {len(self.metrics)} metrics from config.")
        except Exception as e:
            logger.error(f"Failed to load metrics configuration: {e}")

    def get_catalog(self) -> dict:
        return self.metrics

    def generate_metric_sql(self, metric_name: str, dimensions: list[str] = None, time_grain: str = None, filters: dict = None) -> str:
        if metric_name not in self.metrics:
            raise ValueError(f"Metric '{metric_name}' not found in catalog.")
        
        metric_def = self.metrics[metric_name]
        model = metric_def["model"]
        metric_type = metric_def.get("type", "count").lower()
        sql_expr = metric_def.get("sql", "*")
        timestamp_col = metric_def.get("timestamp_column")

        select_exprs = []
        group_by_exprs = []

        if time_grain and timestamp_col:
            trunc_expr = f"DATE_TRUNC('{time_grain}', CAST({timestamp_col} AS TIMESTAMP))"
            select_exprs.append(f"{trunc_expr} AS time_period")
            group_by_exprs.append("time_period")

        if dimensions:
            for dim in dimensions:
                select_exprs.append(dim)
                group_by_exprs.append(dim)

        if metric_type == "count":
            agg_expr = f"COUNT({sql_expr}) AS {metric_name}"
        elif metric_type == "sum":
            agg_expr = f"SUM({sql_expr}) AS {metric_name}"
        elif metric_type == "avg":
            agg_expr = f"AVG({sql_expr}) AS {metric_name}"
        else:
            agg_expr = f"{metric_type}({sql_expr}) AS {metric_name}"
            
        select_exprs.append(agg_expr)

        query = exp.select(*select_exprs).from_(model)

        if filters:
            for k, v in filters.items():
                if isinstance(v, str):
                    query = query.where(f"{k} = '{v}'")
                elif isinstance(v, (int, float, bool)):
                    query = query.where(f"{k} = {v}")
                else:
                     query = query.where(f"{k} = '{str(v)}'")

        if group_by_exprs:
            query = query.group_by(*group_by_exprs)
            
        if time_grain and timestamp_col:
            query = query.order_by("time_period DESC")

        return query.sql(dialect="duckdb")

metric_engine = MetricEngine()
