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
        
        # Additional Datasets integrated with Knowledge Base
        ("Agentic Knowledge Hub", "powers", "Enterprise Knowledge Base", "The central repository connecting all operational datasets."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Customer Master", "Core customer demographic and account records."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Customer Holdings", "Products, appliances, and services owned by the customer."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Property Master", "Address and structural details of serviced properties."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Boiler Master", "Registry of boiler models, specifications, and lifecycles."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Installation History", "Historical records of new appliance and system installations."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Service History", "Logs of annual servicing and maintenance visits."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Repair History", "Historical breakdowns, fault diagnoses, and resolution actions."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Visit Outcomes", "Final statuses and notes from engineer property visits."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Fault Codes", "Diagnostic error codes and corresponding resolutions."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Parts Replaced", "Inventory of components consumed during repair visits."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Engineer Master", "Profiles, regions, and certifications of field engineers."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Engineer Skills", "Specific technical competencies and appliance accreditations."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Engineer Availability & Shifts", "Schedules, rotas, and current working status of engineers."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Engineer Productivity", "Metrics on job completion rates, first-time fix, and efficiency."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Appointment Schedule", "Diary of booked customer visits and time slots."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Contact Centre Interactions", "Logs of customer calls, chats, and support tickets."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Product & Warranty Information", "Terms, coverage periods, and conditions for appliances."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Quotes & Sales", "Commercial proposals, converted sales, and revenue data."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Regional Demand Forecast", "Predictive models for upcoming service and installation volumes."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Regional Capacity Plans", "Resource allocation and engineer coverage per territory."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Knowledge Base (manuals, SOPs, troubleshooting guides)", "Core repository of technical documentation and procedures."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Inventory & Van Stock", "Current levels of spare parts in warehouses and engineer vehicles."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Weather Data", "Meteorological information impacting heating demand and travel."),
        ("Enterprise Knowledge Base", "integrated_dataset", "EPC Property Data", "Energy Performance Certificate ratings and property efficiency details."),
        ("Enterprise Knowledge Base", "integrated_dataset", "Business Rules (warranty, SLA, eligibility)", "Logic governing service entitlements and operational compliance."),
        
        # Definitions and Availability
        ("Customer Master", "has_definition", "Customer Master Definition", "Contains core customer demographics, contact information, billing preferences, and primary account details."),
        ("Customer Master", "available_in", "SAP IS-U", "Central billing and customer information system."),
        ("Customer Holdings", "has_definition", "Customer Holdings Definition", "Tracks the specific products, appliances, and service plans actively owned or subscribed to by the customer."),
        ("Customer Holdings", "available_in", "SAP IS-U", "Central billing and customer information system."),
        ("Property Master", "has_definition", "Property Master Definition", "Stores address details, structural characteristics, and access instructions for serviced properties."),
        ("Property Master", "available_in", "SAP IS-U", "Central billing and customer information system."),
        ("Boiler Master", "has_definition", "Boiler Master Definition", "Registry of all supported boiler makes, models, technical specifications, and expected lifecycles."),
        ("Boiler Master", "available_in", "SAP ERP", "Enterprise Resource Planning system."),
        ("Installation History", "has_definition", "Installation History Definition", "Historical log of new appliance and heating system installations, including dates and installer IDs."),
        ("Installation History", "available_in", "Salesforce CRM", "Customer Relationship Management system."),
        ("Service History", "has_definition", "Service History Definition", "Log of all planned annual servicing and routine maintenance visits performed for a customer."),
        ("Service History", "available_in", "Salesforce Service Cloud", "Service management and tracking system."),
        ("Repair History", "has_definition", "Repair History Definition", "Record of all unplanned breakdowns, fault diagnoses, and the subsequent repair actions taken."),
        ("Repair History", "available_in", "Salesforce Service Cloud", "Service management and tracking system."),
        ("Visit Outcomes", "has_definition", "Visit Outcomes Definition", "Final statuses, engineer notes, and customer signatures collected at the end of a property visit."),
        ("Visit Outcomes", "available_in", "Field Service Lightning", "Field service and dispatch management system."),
        ("Fault Codes", "has_definition", "Fault Codes Definition", "Repository of diagnostic error codes generated by appliances and their corresponding resolution steps."),
        ("Fault Codes", "available_in", "SharePoint", "Enterprise document management and intranet portal."),
        ("Parts Replaced", "has_definition", "Parts Replaced Definition", "Inventory log of specific components and spare parts consumed during repair and maintenance visits."),
        ("Parts Replaced", "available_in", "SAP ERP", "Enterprise Resource Planning system."),
        ("Engineer Master", "has_definition", "Engineer Master Definition", "HR records containing engineer profiles, home regions, and basic employment details."),
        ("Engineer Master", "available_in", "Workday", "Human Capital Management system."),
        ("Engineer Skills", "has_definition", "Engineer Skills Definition", "Matrix of specific technical competencies, gas safety accreditations, and appliance repair certifications."),
        ("Engineer Skills", "available_in", "Workday", "Human Capital Management system."),
        ("Engineer Availability & Shifts", "has_definition", "Engineer Availability Definition", "Real-time schedules, shift patterns, rotas, and current working status of field engineers."),
        ("Engineer Availability & Shifts", "available_in", "Field Service Lightning", "Field service and dispatch management system."),
        ("Engineer Productivity", "has_definition", "Engineer Productivity Definition", "Aggregated performance metrics including jobs completed per day, first-time fix rates, and efficiency."),
        ("Engineer Productivity", "available_in", "Snowflake Analytics", "Enterprise data warehouse and analytics platform."),
        ("Appointment Schedule", "has_definition", "Appointment Schedule Definition", "The master diary of booked customer visits, time slots, and assigned engineers."),
        ("Appointment Schedule", "available_in", "Field Service Lightning", "Field service and dispatch management system."),
        ("Contact Centre Interactions", "has_definition", "Contact Centre Interactions Definition", "Transcripts and logs of customer phone calls, web chats, and support tickets."),
        ("Contact Centre Interactions", "available_in", "Amazon Connect", "Cloud contact centre and telephony system."),
        ("Product & Warranty Information", "has_definition", "Product & Warranty Information Definition", "Details of appliance terms, active coverage periods, and specific conditions for warranty claims."),
        ("Product & Warranty Information", "available_in", "Salesforce CRM", "Customer Relationship Management system."),
        ("Quotes & Sales", "has_definition", "Quotes & Sales Definition", "Financial records of commercial proposals issued to customers and the resulting converted sales."),
        ("Quotes & Sales", "available_in", "Salesforce CRM", "Customer Relationship Management system."),
        ("Regional Demand Forecast", "has_definition", "Regional Demand Forecast Definition", "Machine learning predictive models forecasting upcoming service and installation volume by territory."),
        ("Regional Demand Forecast", "available_in", "Snowflake Analytics", "Enterprise data warehouse and analytics platform."),
        ("Regional Capacity Plans", "has_definition", "Regional Capacity Plans Definition", "Strategic resource allocation models balancing available engineer coverage against forecasted demand."),
        ("Regional Capacity Plans", "available_in", "Snowflake Analytics", "Enterprise data warehouse and analytics platform."),
        ("Knowledge Base (manuals, SOPs, troubleshooting guides)", "has_definition", "Knowledge Base Definition", "The core document management system hosting OEM technical manuals, SOPs, and troubleshooting guides."),
        ("Knowledge Base (manuals, SOPs, troubleshooting guides)", "available_in", "SharePoint", "Enterprise document management and intranet portal."),
        ("Inventory & Van Stock", "has_definition", "Inventory & Van Stock Definition", "Live tracking of current spare part quantities across regional warehouses and individual engineer vehicles."),
        ("Inventory & Van Stock", "available_in", "SAP ERP", "Enterprise Resource Planning system."),
        ("Weather Data", "has_definition", "Weather Data Definition", "Third-party meteorological data used to correlate severe weather events with spikes in heating demand."),
        ("Weather Data", "available_in", "Snowflake Data Lake", "Enterprise data warehouse and analytics platform."),
        ("EPC Property Data", "has_definition", "EPC Property Data Definition", "Energy Performance Certificate ratings and property efficiency details imported from public registries."),
        ("EPC Property Data", "available_in", "Snowflake Data Lake", "Enterprise data warehouse and analytics platform."),
        ("Business Rules (warranty, SLA, eligibility)", "has_definition", "Business Rules Definition", "Logic engine governing service entitlements, SLA compliance, and customer eligibility for repairs."),
        ("Business Rules (warranty, SLA, eligibility)", "available_in", "Salesforce", "Customer Relationship Management system."),
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

        mock_datasets = {
            "Customer Master": pd.DataFrame([{"customer_id": "C001", "name": "John Doe", "status": "Active"}, {"customer_id": "C002", "name": "Jane Smith", "status": "Inactive"}]),
            "Customer Holdings": pd.DataFrame([{"customer_id": "C001", "product": "Boiler Care", "status": "Active"}, {"customer_id": "C002", "product": "Home Cover", "status": "Expired"}]),
            "Property Master": pd.DataFrame([{"property_id": "P001", "postcode": "NW1 6XE", "type": "Terraced"}, {"property_id": "P002", "postcode": "E1 8QS", "type": "Semi-Detached"}]),
            "Boiler Master": pd.DataFrame([{"model_id": "WB4000", "manufacturer": "Worcester Bosch", "model_name": "4000 25kW"}, {"model_id": "BX800", "manufacturer": "Baxi", "model_name": "800 Combi"}]),
            "Installation History": pd.DataFrame([{"install_id": "I001", "customer_id": "C001", "model_id": "WB4000", "date": "2024-01-15"}, {"install_id": "I002", "customer_id": "C002", "model_id": "BX800", "date": "2023-11-02"}]),
            "Service History": pd.DataFrame([{"service_id": "S001", "customer_id": "C001", "date": "2025-01-16", "outcome": "Pass"}, {"service_id": "S002", "customer_id": "C002", "date": "2024-11-05", "outcome": "Fail"}]),
            "Repair History": pd.DataFrame([{"repair_id": "R001", "customer_id": "C002", "fault_code": "EA_Error", "date": "2024-12-10"}]),
            "Visit Outcomes": pd.DataFrame([{"visit_id": "V001", "engineer": "E01", "status": "Completed", "notes": "Replaced electrode"}]),
            "Fault Codes": pd.DataFrame([{"code": "EA_Error", "description": "Flame not detected", "remedy": "Check electrode"}]),
            "Parts Replaced": pd.DataFrame([{"visit_id": "V001", "part_no": "PT123", "quantity": 1}]),
            "Engineer Master": pd.DataFrame([{"engineer_id": "E01", "name": "David Ross", "region": "North"}, {"engineer_id": "E02", "name": "Sarah Jenkins", "region": "South"}]),
            "Engineer Skills": pd.DataFrame([{"engineer_id": "E01", "skill": "Gas Safe Registered", "level": "Expert"}, {"engineer_id": "E02", "skill": "Electrical Support", "level": "Intermediate"}]),
            "Engineer Availability": pd.DataFrame([{"engineer_id": "E01", "date": "2026-07-01", "status": "Working"}, {"engineer_id": "E02", "date": "2026-07-01", "status": "On Leave"}]),
            "Engineer Productivity": pd.DataFrame([{"engineer_id": "E01", "jobs_completed": 5, "first_time_fix": "95%"}, {"engineer_id": "E02", "jobs_completed": 4, "first_time_fix": "85%"}]),
            "Appointment Schedule": pd.DataFrame([{"appt_id": "A001", "customer_id": "C001", "engineer_id": "E01", "date": "2026-07-01"}]),
            "Contact Centre": pd.DataFrame([{"ticket_id": "T001", "customer_id": "C001", "topic": "Boiler broken", "status": "Closed"}]),
            "Product Warranty": pd.DataFrame([{"model_id": "WB4000", "warranty_years": 10, "terms": "Parts and labour"}]),
            "Quotes Sales": pd.DataFrame([{"quote_id": "Q001", "customer_id": "C001", "value": 2500, "status": "Accepted"}]),
            "Demand Forecast": pd.DataFrame([{"region": "North", "month": "2026-07", "predicted_jobs": 1500}]),
            "Capacity Plans": pd.DataFrame([{"region": "North", "month": "2026-07", "available_engineers": 45}]),
            "Knowledge Base Docs": pd.DataFrame([{"doc_id": "DOC1", "title": "Worcester Bosch 4000 Manual", "type": "PDF"}]),
            "Inventory Van Stock": pd.DataFrame([{"part_no": "PT123", "location": "Van E01", "quantity": 5}]),
            "Weather Data": pd.DataFrame([{"date": "2026-07-01", "region": "North", "temp_c": 18, "condition": "Cloudy"}]),
            "EPC Property Data": pd.DataFrame([{"postcode": "NW1 6XE", "epc_rating": "C", "potential": "B"}]),
            "Business Rules": pd.DataFrame([{"rule_id": "BR1", "rule_name": "Next Day Guarantee", "condition": "Vulnerable Customer"}])
        }
        for sheet_name, df in mock_datasets.items():
            # Ensure sheet names don't exceed 31 chars
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    for file_path in (kb_file, metrics_file, access_file, operations_file):
        print(f"Generated: {file_path}")


if __name__ == "__main__":
    generate_all_mock_data(Path(__file__).parent)
