"""
Mock Data Generator Script for Utilities Knowledge Hub.
Generates Knowledge_Base.xlsx, Live_Metrics.xlsx, and Metadata_Access.xlsx.
"""

from pathlib import Path
import pandas as pd


def generate_all_mock_data(data_dir: Path) -> None:
    """Generate Excel mock files inside data_dir if they do not exist."""
    data_dir.mkdir(parents=True, exist_ok=True)

    kb_file = data_dir / "Knowledge_Base.xlsx"
    metrics_file = data_dir / "Live_Metrics.xlsx"
    access_file = data_dir / "Metadata_Access.xlsx"

    # 1. Knowledge Base Data (Graph Nodes & Relationships)
    kb_data = [
        {
            "source": "Worcester Bosch 4000",
            "relationship": "displays_error",
            "target": "EA_Error",
            "details": "Flame not detected after ignition attempt.",
        },
        {
            "source": "EA_Error",
            "relationship": "requires_part",
            "target": "Ignition Electrode",
            "details": "Inspect lead connection, clean electrode or replace if worn.",
        },
        {
            "source": "EA_Error",
            "relationship": "requires_part",
            "target": "Gas Supply Valve",
            "details": "Check gas inlet pressure and solenoid valve coil resistance.",
        },
        {
            "source": "EA_Error",
            "relationship": "caused_by",
            "target": "Low Gas Pressure",
            "details": "Gas supply pressure at meter is below 18 mbar.",
        },
        {
            "source": "Low Gas Pressure",
            "relationship": "remedy_step",
            "target": "Check Emergency Control Valve",
            "details": "Ensure main ECV valve handle is aligned parallel to gas pipe.",
        },
        {
            "source": "Worcester Bosch 4000",
            "relationship": "displays_error",
            "target": "224_Error",
            "details": "Primary flue thermostat or safety limiter tripped (>105°C).",
        },
        {
            "source": "224_Error",
            "relationship": "caused_by",
            "target": "Overheating",
            "details": "System water flow restricted or pump air locked.",
        },
        {
            "source": "Overheating",
            "relationship": "requires_part",
            "target": "Circulating Pump",
            "details": "Verify pump impeller spin and clear air bleed valve.",
        },
        {
            "source": "Ideal Logic Combi",
            "relationship": "displays_error",
            "target": "F2_Error",
            "details": "Flame loss during operation.",
        },
        {
            "source": "F2_Error",
            "relationship": "requires_part",
            "target": "Condensate Pipe",
            "details": "Check for external ice blockage or kinked discharge pipe.",
        },
        {
            "source": "Baxi 800 Combi",
            "relationship": "displays_error",
            "target": "E119_Error",
            "details": "System operating pressure below minimum threshold (<0.5 bar).",
        },
        {
            "source": "E119_Error",
            "relationship": "remedy_step",
            "target": "Re-pressurise Filling Loop",
            "details": "Attach filling loop hose and repressurise system gauge to 1.5 bar.",
        },
    ]

    pd.DataFrame(kb_data).to_excel(kb_file, index=False)
    print(f"Generated: {kb_file}")

    # 2. Live Metrics Data
    metrics_data = [
        {
            "metric_name": "grid_pressure_psi",
            "value": 42.5,
            "unit": "PSI",
            "status": "Normal",
            "description": "Main regional gas distribution pressure.",
        },
        {
            "metric_name": "boiler_flame_current_ua",
            "value": 4.2,
            "unit": "uA",
            "status": "Normal",
            "description": "Ionization flame sensor current signal.",
        },
        {
            "metric_name": "pump_flow_rate_lpm",
            "value": 14.8,
            "unit": "L/min",
            "status": "Optimal",
            "description": "Primary central heating loop flow velocity.",
        },
        {
            "metric_name": "system_temp_c",
            "value": 68.2,
            "unit": "°C",
            "status": "Normal",
            "description": "Appliance flow header temperature.",
        },
        {
            "metric_name": "active_substation_alerts",
            "value": 3,
            "unit": "Alerts",
            "status": "Warning",
            "description": "Substation telemetry warnings active in Sector 4.",
        },
        {
            "metric_name": "customer_outages_count",
            "value": 0,
            "unit": "Outages",
            "status": "Normal",
            "description": "Active unplanned outage count across network.",
        },
    ]

    pd.DataFrame(metrics_data).to_excel(metrics_file, index=False)
    print(f"Generated: {metrics_file}")

    # 3. Metadata Access Data
    # Rules: Customer -> KB only. Employee -> KB + basic metrics. Admin -> All access.
    access_data = [
        {
            "data_source": "Knowledge_Base",
            "required_role": "Customer",
            "access_level": "Read-Only",
            "description": "Public troubleshooting & user manual graph",
        },
        {
            "data_source": "Knowledge_Base",
            "required_role": "Employee",
            "access_level": "Read-Only",
            "description": "Public troubleshooting & user manual graph",
        },
        {
            "data_source": "Knowledge_Base",
            "required_role": "Admin",
            "access_level": "Read-Write",
            "description": "Full access to edit knowledge base graph",
        },
        {
            "data_source": "Live_Metrics",
            "required_role": "Employee",
            "access_level": "Read-Only",
            "description": "Operational live telemetry & grid pressure metrics",
        },
        {
            "data_source": "Live_Metrics",
            "required_role": "Admin",
            "access_level": "Read-Write",
            "description": "Full access to live metrics telemetry",
        },
        {
            "data_source": "System_Logs",
            "required_role": "Admin",
            "access_level": "Full-Access",
            "description": "Sensitive infrastructure system logs",
        },
    ]

    pd.DataFrame(access_data).to_excel(access_file, index=False)
    print(f"Generated: {access_file}")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    generate_all_mock_data(base_dir)
