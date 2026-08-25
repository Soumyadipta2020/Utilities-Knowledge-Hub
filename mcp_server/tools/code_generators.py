from fastmcp import FastMCP

def register_code_generators_tool(mcp: FastMCP):

    @mcp.tool()
    def generate_delta_scd2_template(table_name: str, primary_key: str, effective_date: str) -> str:
        """
        Generates PySpark / Delta Lake template code for an SCD Type 2 merge.
        """
        
        template = f"""
from delta.tables import DeltaTable
from pyspark.sql.functions import col, lit, current_timestamp

def apply_scd2(spark, updates_df, target_table_path):
    # Load target Delta table
    target_table = DeltaTable.forPath(spark, target_table_path)
    
    # Identify records that need to be updated (existing active records matching PKs but differing in data)
    # This is a simplified pattern. For full SCD2, you often join updates to target to find changed rows.
    
    update_condition = \"updates.{primary_key} = target.{primary_key} AND target.is_active = true AND updates.{effective_date} > target.{effective_date}\"
    
    # ... boilerplate omitted for brevity ...
    
    # This generated code is a starting point for {table_name}.
    print("SCD2 Template for {table_name} generated.")
"""
        return template
