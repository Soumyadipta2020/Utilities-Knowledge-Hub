from fastmcp import FastMCP

def register_energy_prompts(mcp: FastMCP):

    @mcp.prompt()
    def customer_churn_analysis(customer_id: str) -> str:
        """
        Generates a specialized workflow prompt for Customer Churn Analysis.
        """
        return f"""
        You are tasked with analyzing the churn risk for customer {customer_id}.
        
        Step 1: Use the `get_table_schema` resource to understand the `customer_profiles` table.
        Step 2: Use the `run_federated_analytics_query` tool to fetch recent billing data and complaints for {customer_id}.
        Step 3: Analyze the `avg_half_hourly_kwh` metric using the `get_energy_metric` resource to see if their consumption has dropped.
        Step 4: Synthesize the findings into a churn risk assessment.
        """

    @mcp.prompt()
    def tariff_audit() -> str:
        """
        Generates a specialized workflow prompt for Tariff Auditing.
        """
        return """
        You are tasked with auditing the current tariff calculations.
        
        Step 1: Read the `docs://knowledge_base/tariff_calculations.md` resource to understand the business logic.
        Step 2: Check the `tariff_rates` table schema using `get_table_schema`.
        Step 3: Query the recent rates from `tariff_rates` using `run_federated_analytics_query` with a limit of 10.
        Step 4: Identify any anomalies based on the documentation rules.
        """
