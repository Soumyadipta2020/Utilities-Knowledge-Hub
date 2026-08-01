"""Generate the local Excel silos used by the Utilities Knowledge Hub demo."""

from pathlib import Path

import pandas as pd


def generate_all_mock_data(data_dir: Path) -> None:
    """Create the knowledge, telemetry, access, and business-operation workbooks."""
    data_dir.mkdir(parents=True, exist_ok=True)
    kb_file = data_dir / "Knowledge_Base.xlsx"
    metrics_file = data_dir / "Live_Metrics.xlsx"
    access_file = data_dir / "Metadata_Access.xlsx"
    operations_file = data_dir / "Business_Operations.xlsx"

    knowledge_records = [
        ("ABC Enterprise Platform", "powers", "Agentic Knowledge Hub", "Unified AI-powered intelligence layer for ABC business knowledge, datasets, dashboards, and operational insights."),
        ("Sales_Funnel_Dataset", "managed_by_sme", "Sarah Jenkins (Head of Commercial Analytics)", "Owner of commercial sales funnel, lead attribution, and conversion metrics in Snowflake."),
        ("Sales_Funnel_Dataset", "lineage_source", "SAP IS-U & Salesforce CRM", "Aggregates raw customer leads and survey appointments from Salesforce into Snowflake data lake."),
        ("Live_Metrics_Dataset", "managed_by_sme", "David Ross (Lead Telemetry Engineer)", "Maintains IoT grid pressure and thermal telemetry sensors across UK regions."),
        ("Live_Metrics_Dataset", "lineage_source", "Grid Mon Substation IoT Network", "Real-time telemetry ingested via Kafka into Snowflake Operational Data Store."),
        ("Boiler_Installation_Forecast_v2", "managed_by_sme", "Marcus Vance (Principal Data Scientist)", "Predictive installation model using pipeline conversion, seasonal demand, and engineer capacity."),
        ("Boiler_Installation_Forecast_v2", "consumes_dataset", "Sales_Funnel_Dataset", "Uses qualified lead volume, kept appointment ratios, and quote conversion rates."),
        ("ABC_Executive_Dashboard", "managed_by_sme", "Claire Williams (VP Operations)", "PowerBI dashboard providing real-time visibility into sales conversion, telemetry alerts, and service activity."),
        ("ABC_Executive_Dashboard", "displays_metrics", "Sales Conversion & Grid Telemetry", "Unified view combining Commercial Sales Funnel and Live Telemetry Metrics."),
        ("Worcester Bosch 4000", "displays_error", "EA_Error", "Flame was not detected after an ignition attempt."),
        ("EA_Error", "requires_part", "Ignition Electrode", "Inspect the lead, clean the electrode, or replace it if worn."),
        ("EA_Error", "requires_part", "Gas Supply Valve", "Check inlet pressure and the solenoid valve coil resistance."),
        ("EA_Error", "caused_by", "Low Gas Pressure", "Gas pressure at the meter is below 18 mbar."),
        ("Low Gas Pressure", "remedy_step", "Check Emergency Control Valve", "Ensure the main valve handle is parallel to the pipe."),
        ("Worcester Bosch 4000", "displays_error", "224_Error", "The primary flue thermostat or safety limiter has tripped."),
        ("224_Error", "caused_by", "Overheating", "Water flow may be restricted or the pump may be air locked."),
        ("Overheating", "requires_part", "Circulating Pump", "Verify impeller movement and bleed trapped air."),
        ("Ideal Logic Combi", "displays_error", "F2_Error", "Flame loss during operation."),
        ("F2_Error", "requires_part", "Condensate Pipe", "Check for external ice blockage or a kinked discharge pipe."),
        ("Baxi 800 Combi", "displays_error", "E119_Error", "System pressure is below the minimum operating threshold."),
        ("E119_Error", "remedy_step", "Re-pressurise Filling Loop", "Repressurise the system gauge to 1.5 bar."),
        ("Home Energy Services", "provides", "Heating Installation", "Design and fit replacement boilers, heating controls, and compatible system upgrades."),
        ("Home Energy Services", "provides", "Heating Repair", "Diagnose and repair boiler, radiator, thermostat, and hot-water faults."),
        ("Home Energy Services", "provides", "Annual Maintenance", "Carry out planned appliance servicing and safety checks."),
        ("Home Energy Services", "provides", "Plumbing And Drains", "Repair leaks, taps, toilets, pipework, and common drainage issues."),
        ("Home Energy Services", "provides", "Electrical Support", "Provide domestic electrical checks, fault diagnosis, and selected repairs."),
        ("Home Energy Services", "provides", "Appliance Care", "Repair and maintain selected kitchen and laundry appliances."),
        ("EA_Error", "need_to_end_connection", "Worcester Bosch 4000", "Boiler must be isolated and power disconnected before any repair attempt — risk of electric shock and gas leak."),
        ("224_Error", "need_to_end_connection", "Worcester Bosch 4000", "Overheating fault requires immediate shutdown and full system isolation before engineer intervention."),
        ("E119_Error", "need_to_end_connection", "Baxi 800 Combi", "Low pressure fault — isolate system and depressurise before opening any filling loop connections."),
        ("Lead", "converts_to", "Net Appointment", "A qualified prospect that results in a kept consultation or survey appointment."),
        ("Net Appointment", "converts_to", "Net Sale", "A kept appointment that results in a completed, non-cancelled sale."),
        ("Net Sale", "measured_by", "Sales Conversion", "Net sales divided by qualified leads, expressed as a percentage."),
        ("Quote", "supports", "Net Sale", "A priced proposal issued for an installation, repair, or service plan."),
    ]
    pd.DataFrame(knowledge_records, columns=["source", "relationship", "target", "details"]).to_excel(kb_file, index=False)

    telemetry_records = [
        ("grid_pressure_psi", 42.5, "PSI", "Normal", "Main regional gas distribution pressure."),
        ("boiler_flame_current_ua", 4.2, "uA", "Normal", "Ionisation flame sensor current signal."),
        ("pump_flow_rate_lpm", 14.8, "L/min", "Optimal", "Primary heating-loop flow velocity."),
        ("system_temp_c", 68.2, "°C", "Normal", "Appliance flow-header temperature."),
        ("active_substation_alerts", 3, "Alerts", "Warning", "Active substation telemetry warnings in sector 4."),
        ("customer_outages_count", 0, "Outages", "Normal", "Active unplanned outages across the network."),
    ]
    pd.DataFrame(telemetry_records, columns=["metric_name", "value", "unit", "status", "description"]).to_excel(metrics_file, index=False)

    access_records = [
        ("Knowledge_Base", "Customer", "Read-Only", "Troubleshooting, service catalogue, and business metric definitions."),
        ("Knowledge_Base", "Employee", "Read-Only", "Troubleshooting, service catalogue, and business metric definitions."),
        ("Knowledge_Base", "Admin", "Read-Write", "Full knowledge graph administration."),
        ("Live_Metrics", "Employee", "Read-Only", "Operational telemetry and network readings."),
        ("Live_Metrics", "Admin", "Read-Write", "Full telemetry access."),
        ("Business_Operations", "Employee", "Read-Only", "Aggregated commercial, service, and sales-performance records."),
        ("Business_Operations", "Admin", "Read-Write", "Full operational dataset access."),
        ("Metadata_Access", "Admin", "Full-Access", "Access-policy administration and audit."),
        ("System_Logs", "Admin", "Full-Access", "Sensitive infrastructure system logs."),
    ]
    pd.DataFrame(access_records, columns=["data_source", "required_role", "access_level", "description"]).to_excel(access_file, index=False)

    funnel_records = [
        ("2026-07-01", "Heating Installation", "North", 126, 78, 31, 39, 24.6),
        ("2026-07-01", "Heating Repair", "North", 94, 62, 27, 18, 28.7),
        ("2026-07-01", "Annual Maintenance", "Central", 110, 81, 42, 36, 32.7),
        ("2026-07-01", "Plumbing And Drains", "Central", 88, 55, 19, 16, 21.6),
        ("2026-07-01", "Electrical Support", "South", 64, 41, 14, 11, 21.9),
        ("2026-07-01", "Appliance Care", "South", 72, 46, 17, 13, 18.1),
    ]
    activity_records = [
        ("2026-07-01", "Heating Installation", "Boiler installation", 24, 21, 3, "North"),
        ("2026-07-01", "Heating Repair", "Boiler breakdown repair", 57, 49, 8, "North"),
        ("2026-07-01", "Annual Maintenance", "Boiler service", 103, 98, 5, "Central"),
        ("2026-07-01", "Plumbing And Drains", "Plumbing repair", 68, 61, 7, "Central"),
        ("2026-07-01", "Electrical Support", "Electrical safety check", 38, 36, 2, "South"),
        ("2026-07-01", "Appliance Care", "Appliance repair", 46, 39, 7, "South"),
    ]
    definition_records = [
        ("leads", "Count", "New qualified prospects created in the reporting period."),
        ("net_appointments", "Count", "Kept consultation or survey appointments after exclusions and cancellations."),
        ("quotes_issued", "Count", "Priced customer proposals issued during the reporting period."),
        ("net_sales", "Count", "Completed sales after cancellations and reversals are removed."),
        ("sales_conversion_pct", "Percent", "Net sales divided by qualified leads, expressed as a percentage."),
        ("jobs_booked", "Count", "Service, repair, maintenance, and installation visits scheduled."),
        ("jobs_completed", "Count", "Booked jobs successfully completed in the reporting period."),
        ("jobs_requiring_follow_up", "Count", "Jobs requiring a return visit, parts, or additional customer contact."),
    ]
    with pd.ExcelWriter(operations_file) as writer:
        pd.DataFrame(funnel_records, columns=["report_date", "service_line", "region", "leads", "net_appointments", "quotes_issued", "net_sales", "sales_conversion_pct"]).to_excel(writer, sheet_name="Sales_Funnel", index=False)
        pd.DataFrame(activity_records, columns=["report_date", "service_line", "activity_type", "jobs_booked", "jobs_completed", "jobs_requiring_follow_up", "region"]).to_excel(writer, sheet_name="Service_Activity", index=False)
        pd.DataFrame(definition_records, columns=["metric_name", "unit", "definition"]).to_excel(writer, sheet_name="Metric_Definitions", index=False)

    for file_path in (kb_file, metrics_file, access_file, operations_file):
        print(f"Generated: {file_path}")


if __name__ == "__main__":
    generate_all_mock_data(Path(__file__).parent)
