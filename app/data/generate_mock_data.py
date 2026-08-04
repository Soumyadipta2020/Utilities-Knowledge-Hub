"""Generate the local Excel silos used by the Utilities Knowledge Hub demo."""

from pathlib import Path

import pandas as pd


def generate_all_mock_data(data_dir: Path) -> None:
    """Create the 6 Domain Harness System (DHS) Excel data sources."""
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 6 DHS Architecture Excel Sources
    info_file = data_dir / "Information_Harnessing_Source.xlsx"
    knowledge_file = data_dir / "Knowledge_Harnessing_Source.xlsx"
    inference_file = data_dir / "Inference_Harnessing_Source.xlsx"
    outcome_file = data_dir / "Outcome_Harnessing_Source.xlsx"
    benchmark_file = data_dir / "Benchmarking_Harnessing_Source.xlsx"
    governance_file = data_dir / "Governance_Security_Source.xlsx"

    # Legacy Aliases
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

    import numpy as np
    
    # Time ranges
    now = pd.Timestamp.now().normalize()
    past_730_dates = [d.strftime("%Y-%m-%d") for d in pd.date_range(end=now, periods=730, freq='D')]
    future_30_dates = [d.strftime("%Y-%m-%d") for d in pd.date_range(start=now, periods=30, freq='D')]
    past_24_months = pd.date_range(end=now, periods=24, freq='MS')
    future_24_months = pd.date_range(start=now, periods=24, freq='MS')

    regions = ["North", "South", "Central", "East", "West"]
    service_lines = ["Heating Installation", "Heating Repair", "Annual Maintenance", "Plumbing And Drains", "Electrical Support", "Appliance Care"]

    funnel_records = []
    for d in past_24_months:
        for sl in service_lines:
            for r in regions:
                leads = np.random.randint(50, 200)
                appts = int(leads * np.random.uniform(0.5, 0.8))
                quotes = int(appts * np.random.uniform(0.4, 0.7))
                sales = int(quotes * np.random.uniform(0.5, 0.9))
                conv = round((sales / leads) * 100, 1) if leads > 0 else 0
                funnel_records.append((d.strftime("%Y-%m-%d"), sl, r, leads, appts, quotes, sales, conv))
                
    activity_records = []
    for d in past_24_months:
        for sl in service_lines:
            for r in regions:
                booked = np.random.randint(20, 150)
                completed = int(booked * np.random.uniform(0.8, 0.98))
                follow_up = booked - completed
                activity_records.append((d.strftime("%Y-%m-%d"), sl, sl + " activity", booked, completed, follow_up, r))

    definition_records = [
        ("leads", "Count", "New qualified prospects created in the reporting period."),
        ("net_appointments", "Count", "Kept consultation or survey appointments after exclusions and cancellations."),
        ("quotes_issued", "Count", "Priced customer proposals issued during the reporting period."),
        ("net_sales", "Count", "Completed sales after cancellations and reversals are removed."),
        ("sales_conversion_pct", "Percent", "Net sales divided by qualified leads, expressed as a percentage."),
        ("jobs_booked", "Count", "Service, repair, maintenance, and installation visits scheduled."),
        ("jobs_completed", "Count", "Booked jobs successfully completed in the reporting period."),
        ("jobs_requiring_follow_up", "Count", "Jobs requiring a return visit, parts, or additional customer contact."),
        # Dataset Definitions
        ("Customer Master", "Dataset", "Contains core customer demographics, contact information, billing preferences, and primary account details."),
        ("Customer Holdings", "Dataset", "Tracks the specific products, appliances, and service plans actively owned or subscribed to by the customer."),
        ("Property Master", "Dataset", "Stores address details, structural characteristics, and access instructions for serviced properties."),
        ("Boiler Master", "Dataset", "Registry of all supported boiler makes, models, technical specifications, and expected lifecycles."),
        ("Installation History", "Dataset", "Historical log of new appliance and heating system installations, including dates and installer IDs."),
        ("Service History", "Dataset", "Log of all planned annual servicing and routine maintenance visits performed for a customer."),
        ("Repair History", "Dataset", "Record of all unplanned breakdowns, fault diagnoses, and the subsequent repair actions taken."),
        ("Visit Outcomes", "Dataset", "Final statuses, engineer notes, and customer signatures collected at the end of a property visit."),
        ("Fault Codes", "Dataset", "Repository of diagnostic error codes generated by appliances and their corresponding resolution steps."),
        ("Parts Replaced", "Dataset", "Inventory log of specific components and spare parts consumed during repair and maintenance visits."),
        ("Engineer Master", "Dataset", "HR records containing engineer profiles, home regions, and basic employment details."),
        ("Engineer Skills", "Dataset", "Matrix of specific technical competencies, gas safety accreditations, and appliance repair certifications."),
        ("Engineer Availability & Shifts", "Dataset", "Real-time schedules, shift patterns, rotas, and current working status of field engineers."),
        ("Engineer Productivity", "Dataset", "Aggregated performance metrics including jobs completed per day, first-time fix rates, and efficiency."),
        ("Appointment Schedule", "Dataset", "The master diary of booked customer visits, time slots, and assigned engineers."),
        ("Contact Centre Interactions", "Dataset", "Transcripts and logs of customer phone calls, web chats, and support tickets."),
        ("Product & Warranty Information", "Dataset", "Details of appliance terms, active coverage periods, and specific conditions for warranty claims."),
        ("Quotes & Sales", "Dataset", "Financial records of commercial proposals issued to customers and the resulting converted sales."),
        ("Regional Demand Forecast", "Dataset", "Machine learning predictive models forecasting upcoming service and installation volume by territory."),
        ("Regional Capacity Plans", "Dataset", "Strategic resource allocation models balancing available engineer coverage against forecasted demand."),
        ("Knowledge Base (manuals, SOPs, troubleshooting guides)", "Dataset", "The core document management system hosting OEM technical manuals, SOPs, and troubleshooting guides."),
        ("Inventory & Van Stock", "Dataset", "Live tracking of current spare part quantities across regional warehouses and individual engineer vehicles."),
        ("Weather Data", "Dataset", "Third-party meteorological data used to correlate severe weather events with spikes in heating demand."),
        ("EPC Property Data", "Dataset", "Energy Performance Certificate ratings and property efficiency details imported from public registries."),
        ("Business Rules (warranty, SLA, eligibility)", "Dataset", "Logic engine governing service entitlements, SLA compliance, and customer eligibility for repairs."),
    ]
    
    # Generate larger dimensional static data
    customers = [{"customer_id": f"C{i:03d}", "name": f"Customer {i}", "status": np.random.choice(["Active", "Inactive"])} for i in range(1, 101)]
    customer_ids = [c["customer_id"] for c in customers]
    properties = [{"property_id": f"P{i:03d}", "postcode": f"PC{i:03d}", "type": np.random.choice(["Terraced", "Detached", "Semi-Detached"])} for i in range(1, 101)]
    engineers = [{"engineer_id": f"E{i:02d}", "name": f"Engineer {i}", "region": np.random.choice(regions)} for i in range(1, 51)]
    engineer_ids = [e["engineer_id"] for e in engineers]
    
    # Time-series datasets (2 years history)
    install_history = [{"install_id": f"I{i:04d}", "customer_id": np.random.choice(customer_ids), "date": np.random.choice(past_730_dates)} for i in range(1000)]
    service_history = [{"service_id": f"S{i:04d}", "customer_id": np.random.choice(customer_ids), "date": np.random.choice(past_730_dates), "outcome": np.random.choice(["Pass", "Fail"])} for i in range(1500)]
    repair_history = [{"repair_id": f"R{i:04d}", "customer_id": np.random.choice(customer_ids), "date": np.random.choice(past_730_dates), "fault_code": np.random.choice(["EA_Error", "224_Error", "F2_Error"])} for i in range(800)]
    weather_data = [{"date": d, "region": r, "temp_c": round(np.random.normal(10, 5), 1), "condition": np.random.choice(["Sunny", "Cloudy", "Rain", "Snow"])} for d in past_730_dates for r in regions]
    
    # Time-series datasets (2 years future)
    demand_forecast = [{"region": r, "month": d.strftime("%Y-%m"), "predicted_jobs": np.random.randint(1000, 3000)} for d in future_24_months for r in regions]
    capacity_plans = [{"region": r, "month": d.strftime("%Y-%m"), "available_engineers": np.random.randint(20, 100)} for d in future_24_months for r in regions]
    future_appts = [{"appt_id": f"AF{i:04d}", "customer_id": np.random.choice(customer_ids), "engineer_id": np.random.choice(engineer_ids), "date": np.random.choice(future_30_dates)} for i in range(500)]

    mock_datasets = {
        "Customer Master": pd.DataFrame(customers),
        "Customer Holdings": pd.DataFrame([{"customer_id": c["customer_id"], "product": "Boiler Care", "status": "Active"} for c in customers]),
        "Property Master": pd.DataFrame(properties),
        "Boiler Master": pd.DataFrame([{"model_id": f"MOD{i}", "manufacturer": "OEM", "model_name": f"Model {i}"} for i in range(1, 10)]),
        "Installation History": pd.DataFrame(install_history),
        "Service History": pd.DataFrame(service_history),
        "Repair History": pd.DataFrame(repair_history),
        "Visit Outcomes": pd.DataFrame([{"visit_id": f"V{i:04d}", "date": np.random.choice(past_730_dates), "engineer": np.random.choice(engineer_ids), "status": "Completed"} for i in range(1000)]),
        "Fault Codes": pd.DataFrame([{"code": "EA_Error", "description": "Flame not detected", "remedy": "Check electrode"}]),
        "Parts Replaced": pd.DataFrame([{"visit_id": f"V{i:04d}", "date": np.random.choice(past_730_dates), "part_no": "PT123", "quantity": 1} for i in range(500)]),
        "Engineer Master": pd.DataFrame(engineers),
        "Engineer Skills": pd.DataFrame([{"engineer_id": e["engineer_id"], "skill": "Gas Safe", "level": "Expert"} for e in engineers]),
        "Engineer Availability": pd.DataFrame([{"engineer_id": e["engineer_id"], "date": d, "status": np.random.choice(["Working", "On Leave"], p=[0.9, 0.1])} for e in engineers for d in past_730_dates[-10:] + future_30_dates]),
        "Engineer Productivity": pd.DataFrame([{"engineer_id": e["engineer_id"], "jobs_completed": np.random.randint(500, 1000), "first_time_fix": f"{np.random.randint(80, 99)}%"} for e in engineers]),
        "Appointment Schedule": pd.DataFrame([{"appt_id": f"A{i:04d}", "customer_id": np.random.choice(customer_ids), "engineer_id": np.random.choice(engineer_ids), "date": np.random.choice(past_730_dates)} for i in range(1000)] + future_appts),
        "Contact Centre": pd.DataFrame([{"ticket_id": f"T{i:04d}", "date": np.random.choice(past_730_dates), "topic": "Broken", "status": "Closed"} for i in range(1000)]),
        "Product Warranty": pd.DataFrame([{"model_id": f"MOD{i}", "warranty_years": 10, "terms": "Parts"} for i in range(1, 10)]),
        "Quotes Sales": pd.DataFrame([{"quote_id": f"Q{i:04d}", "date": np.random.choice(past_730_dates), "value": np.random.randint(1000, 4000), "status": "Accepted"} for i in range(1000)]),
        "Demand Forecast": pd.DataFrame(demand_forecast),
        "Capacity Plans": pd.DataFrame(capacity_plans),
        "Knowledge Base Docs": pd.DataFrame([{"doc_id": "DOC1", "title": "Manual", "type": "PDF"}]),
        "Inventory Van Stock": pd.DataFrame([{"part_no": "PT123", "location": "Warehouse", "quantity": 500}]),
        "Weather Data": pd.DataFrame(weather_data),
        "EPC Property Data": pd.DataFrame([{"postcode": p["postcode"], "epc_rating": np.random.choice(["A", "B", "C", "D", "E"])} for p in properties]),
        "Business Rules": pd.DataFrame([{"rule_id": "BR1", "rule_name": "Next Day", "condition": "Vulnerable"}])
    }
    
    # Save to DHS 6-Stage Excel Data Sources
    pd.DataFrame(telemetry_records, columns=["metric_name", "value", "unit", "status", "description"]).to_excel(info_file, index=False)
    pd.DataFrame(knowledge_records, columns=["source", "relationship", "target", "details"]).to_excel(knowledge_file, index=False)
    
    # Inference Harnessing Source (Diagnostic decision trees, fault resolutions, RAG snippets)
    inference_records = [
        ("Worcester Bosch 4000", "EA_Error", "Ignition Flame Failure", "Inspect lead, clean electrode, check gas pressure > 18 mbar.", 99.4),
        ("Worcester Bosch 4000", "224_Error", "Primary Flue Thermostat Tripped", "Check water flow, bleed air from circulating pump.", 98.8),
        ("Ideal Logic Combi", "F2_Error", "Flame Loss During Operation", "Check external condensate pipe for ice or blockage.", 97.5),
        ("Baxi 800 Combi", "E119_Error", "System Water Pressure Low", "Repressurise filling loop to 1.5 bar.", 99.1),
    ]
    pd.DataFrame(inference_records, columns=["equipment", "error_code", "fault_diagnosis", "resolution_procedure", "confidence_score"]).to_excel(inference_file, index=False)

    # Benchmarking Harnessing Source (Golden Q&A evaluation datasets, F1 scores)
    benchmark_records = [
        ("Q001", "How to fix EA Error on Worcester Bosch?", "Check gas supply and electrode", "Pass", 0.99, "LLM-as-a-Judge"),
        ("Q002", "Who owns Sales_Funnel_Dataset?", "Sarah Jenkins (Head of Commercial Analytics)", "Pass", 1.00, "LLM-as-a-Judge"),
        ("Q003", "What is grid pressure PSI?", "42.5 PSI (Requires Live_Metrics permission)", "Pass", 0.98, "LLM-as-a-Judge"),
    ]
    pd.DataFrame(benchmark_records, columns=["query_id", "question", "golden_answer", "eval_status", "f1_score", "evaluator"]).to_excel(benchmark_file, index=False)

    # Governance & Security Source (Entra ID roles, Purview data governance policies)
    pd.DataFrame(access_records, columns=["data_source", "required_role", "access_level", "description"]).to_excel(governance_file, index=False)

    # Outcome Harnessing Source (Business operations, access tickets)
    with pd.ExcelWriter(outcome_file) as writer:
        pd.DataFrame(funnel_records, columns=["report_date", "service_line", "region", "leads", "net_appointments", "quotes_issued", "net_sales", "sales_conversion_pct"]).to_excel(writer, sheet_name="Sales_Funnel", index=False)
        pd.DataFrame(activity_records, columns=["report_date", "service_line", "activity_type", "jobs_booked", "jobs_completed", "jobs_requiring_follow_up", "region"]).to_excel(writer, sheet_name="Service_Activity", index=False)
        pd.DataFrame(definition_records, columns=["metric_name", "unit", "definition"]).to_excel(writer, sheet_name="Metric_Definitions", index=False)
        for sheet_name, df in mock_datasets.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

    # Write legacy files for 100% backward compatibility
    pd.DataFrame(knowledge_records, columns=["source", "relationship", "target", "details"]).to_excel(kb_file, index=False)
    pd.DataFrame(telemetry_records, columns=["metric_name", "value", "unit", "status", "description"]).to_excel(metrics_file, index=False)
    pd.DataFrame(access_records, columns=["data_source", "required_role", "access_level", "description"]).to_excel(access_file, index=False)
    import shutil
    shutil.copyfile(outcome_file, operations_file)

    dhs_all_files = [info_file, knowledge_file, inference_file, outcome_file, benchmark_file, governance_file]
    for file_path in dhs_all_files:
        print(f"Generated DHS Data Source: {file_path.name}")


if __name__ == "__main__":
    generate_all_mock_data(Path(__file__).parent)
