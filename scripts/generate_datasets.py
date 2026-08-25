import pandas as pd
import numpy as np
import random
import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
import string

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
scripts_dir = Path(__file__).resolve().parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

np.random.seed(42)
random.seed(42)

# Per-week base counts optimized for ±3 months window and lightweight memory profile
BASE_LEADS = 1200
BASE_APPTS = 900
BASE_SALES = 450
BASE_INSTALLS = 300
BASE_REPAIRS = 3500
BASE_SERVICES = 9000
NUM_ENGINEERS = 800

NUM_BOILERS_REF = 10
NUM_FAULTS_REF = 15
NUM_PARTS_REF = 20

REGIONS = ['London', 'South East', 'South West', 'Midlands', 'North West', 'North East', 'Yorkshire', 'Wales', 'Scotland']
CITIES = ['London', 'Manchester', 'Birmingham', 'Leeds', 'Glasgow', 'Southampton', 'Liverpool', 'Newcastle', 'Sheffield', 'Bristol']
TERRAINS = ['Urban', 'Suburban', 'Rural', 'Coastal']
BOILER_TYPES = ['Combi', 'System', 'Conventional']
BOILER_MANUFACTURERS = ['Worcester Bosch', 'Vaillant', 'Baxi', 'Ideal', 'Viessmann', 'Glow-worm']
ENERGY_RATINGS = ['A', 'B', 'C', 'D']
PROPERTY_TYPES = ['Detached', 'Semi-Detached', 'Terraced', 'Flat', 'Bungalow']
CONTACT_MODES = ['Call', 'Visit', 'Email', 'App']
FAULT_SEVERITY = ['Low', 'Medium', 'High', 'Critical']
JOB_CATEGORIES = ['Service', 'Repair', 'Installation']


def generate_all_datasets(output_dir='data'):
    os.makedirs(output_dir, exist_ok=True)
    # 1. References
    print("Generating Reference Data...")
    product_info = []
    for i in range(NUM_BOILERS_REF):
        product_info.append({
            'boiler_id': f"PROD{str(i+1).zfill(3)}",
            'boiler_type': random.choice(BOILER_TYPES),
            'energy_rating': random.choice(ENERGY_RATINGS),
            'energy_consumption': random.randint(10000, 20000),
            'life_span': random.randint(10, 20),
            'manufacturer': random.choice(BOILER_MANUFACTURERS),
            'imported': random.choice(['Yes', 'No']),
            'warranty': random.randint(5, 12),
            'addition_warranty_purchased': random.choice(['Yes', 'No']),
        })
    df_product_info = pd.DataFrame(product_info)
    df_product_info['addition_warranty_end_date'] = df_product_info.apply(
        lambda row: (datetime.now() + timedelta(days=random.randint(90, 365*3))).strftime('%Y-%m-%d') if row['addition_warranty_purchased'] == 'Yes' else None, axis=1)

    fault_codes = []
    for i in range(NUM_FAULTS_REF):
        fault_codes.append({
            'fault_code': f"F{random.randint(10, 99)}",
            'explanation_related_fault_codes': "System error occurred due to component failure",
            'severity': random.choice(FAULT_SEVERITY),
            'repair_cost': round(random.uniform(50, 500), 2)
        })
    df_fault_codes = pd.DataFrame(fault_codes)

    parts_ref = []
    for i in range(NUM_PARTS_REF):
        parts_ref.append({
            'part': f"Part_{random.choice(string.ascii_uppercase)}{i}",
            'replacement_cost': round(random.uniform(20, 300), 2),
            'severity': random.choice(FAULT_SEVERITY),
            'average_life_span': random.randint(2, 10)
        })
    df_parts = pd.DataFrame(parts_ref)

    business_rules = [
        {'rule_id': 'R1', 'rule_name': 'Warranty SLA', 'description': 'Repairs under warranty must be attended within 24 hours'},
        {'rule_id': 'R2', 'rule_name': 'Service Eligibility', 'description': 'Annual service required to maintain warranty'},
        {'rule_id': 'R3', 'rule_name': 'Standard SLA', 'description': 'Standard repairs must be attended within 48 hours'}
    ]
    df_business_rules = pd.DataFrame(business_rules)

    kb_data = [
        {'doc_id': f'KB{str(i).zfill(3)}', 'doc_type': 'Manual', 'title': 'Guide', 'content': 'Sample content'} for i in range(1, 6)
    ]
    df_kb = pd.DataFrame(kb_data)

    # 2. Events & Targets Generation: ±3 Months Window from Current Date
    print("Generating Events (Leads, Services, Repairs) for ±3 Months window...")

    today = datetime.now().date()
    # Historical window: ~13.5 weeks before today (~3 months)
    CURRENT_START = today - timedelta(days=95)
    CURRENT_END   = today

    # Future window: ~15 weeks after today (ensures 13 full 7-day forecast weeks)
    FUTURE_END = today + timedelta(days=105)

    # Date ranges
    current_dates = pd.date_range(start=CURRENT_START, end=CURRENT_END, freq='D')
    future_dates_range = pd.date_range(start=CURRENT_END + timedelta(days=1), end=FUTURE_END, freq='D')
    all_dates_range = pd.date_range(start=CURRENT_START, end=FUTURE_END, freq='D')

    start_date = CURRENT_START
    end_date   = CURRENT_END
    dates      = current_dates

    week_starts = pd.date_range(start=CURRENT_START, end=CURRENT_END, freq='W-MON')
    WEEKS_HIST  = len(week_starts)

    all_leads = []
    all_quotes = []
    all_services = []
    all_repairs = []
    all_appointments = []
    all_visits = []
    all_contacts = []

    lead_counter = 1
    job_counter = 1
    cust_counter = 1

    def generate_weekly_counts(base, weeks, variance=0.05):
        return [int(base * (1 + random.uniform(-variance, variance))) for _ in range(weeks)]

    weekly_leads    = generate_weekly_counts(BASE_LEADS,    WEEKS_HIST)
    weekly_appts    = generate_weekly_counts(BASE_APPTS,    WEEKS_HIST)
    weekly_sales    = generate_weekly_counts(BASE_SALES,    WEEKS_HIST)
    weekly_installs = generate_weekly_counts(BASE_INSTALLS, WEEKS_HIST)
    weekly_repairs  = generate_weekly_counts(BASE_REPAIRS,  WEEKS_HIST)
    weekly_services = generate_weekly_counts(BASE_SERVICES, WEEKS_HIST)

    for w in range(WEEKS_HIST):
        week_start = week_starts[w].date()
        week_end   = min(week_start + timedelta(days=6), CURRENT_END)
        week_dates = pd.date_range(start=week_start, end=week_end, freq='D').date

        # Generate Leads
        l_count = weekly_leads[w]
        a_count = min(weekly_appts[w], l_count)
        s_count = min(weekly_sales[w], a_count)
        i_count = min(weekly_installs[w], s_count)

        w_customers = l_count + weekly_repairs[w] + weekly_services[w]
        w_cust_ids = [f"CUST{str(c).zfill(8)}" for c in range(cust_counter, cust_counter + w_customers)]
        cust_counter += w_customers

        idx = 0
        # Process leads
        for i in range(l_count):
            c_id = w_cust_ids[idx]
            idx += 1

            has_appt = i < a_count
            has_sale = i < s_count
            has_install = i < i_count

            l_date = random.choice(week_dates)
            a_date = l_date + timedelta(days=random.randint(1, 3)) if has_appt else None
            s_date = a_date + timedelta(days=1) if has_sale else None
            i_date = s_date + timedelta(days=random.randint(2, 7)) if has_install else None

            lead_id = f"LD{str(lead_counter).zfill(8)}"
            lead_counter += 1
            job_id = f"JOB{str(job_counter).zfill(8)}" if has_install else ""
            if has_install:
                job_counter += 1

            all_leads.append({
                'job_id': job_id,
                'customer_id': c_id,
                'lead_id': lead_id,
                'lead_date': l_date,
                'mode_of_conversation_with_customer': random.choice(CONTACT_MODES),
                'appointment_date': a_date if a_date else '',
                'appointment_happened': 'Yes' if has_appt else 'No',
                'sale_date': s_date if s_date else '',
                'sale_happened': 'Yes' if has_sale else 'No',
                'installation_date': i_date if i_date else '',
                'installation_happened': 'Yes' if has_install else 'No',
                'insurance_purchased': random.choice(['Yes', 'No']) if has_sale else 'No'
            })

            all_quotes.append({
                'lead_id': lead_id,
                'primary_qutation': round(random.uniform(1500, 3000), 2),
                'secondary_quotation': round(random.uniform(1200, 2500), 2),
                'final_quotation': round(random.uniform(1400, 2800), 2)
            })

            if has_install:
                all_appointments.append({
                    'job_id': job_id,
                    'appointment_date': i_date,
                    'job_category': 'Installation',
                    'severity': 'Medium'
                })
                all_visits.append({
                    'job_id': job_id,
                    'customer_id': c_id,
                    'visit_date': i_date,
                    'visit_status': 'Completed',
                    'customer_feedback': random.choice(['Excellent', 'Good', 'Average'])
                })

        # Process services
        for _ in range(weekly_services[w]):
            c_id = w_cust_ids[idx]
            idx += 1
            s_date = random.choice(week_dates)
            job_id = f"JOB{str(job_counter).zfill(8)}"
            job_counter += 1
            all_services.append({
                'job_id': job_id,
                'customer_id': c_id,
                'service_date': s_date,
                'service_type': 'Annual Maintenance',
                'parts_serviced': 'Burner, Heat Exchanger'
            })
            all_appointments.append({
                'job_id': job_id,
                'appointment_date': s_date,
                'job_category': 'Service',
                'severity': 'Low'
            })
            all_visits.append({
                'job_id': job_id,
                'customer_id': c_id,
                'visit_date': s_date,
                'visit_status': 'Completed',
                'customer_feedback': random.choice(['Good', 'Average', 'Poor'])
            })
            all_contacts.append({
                'job_id': job_id,
                'job_registration_datetime': f"{s_date} 09:00:00",
                'contact_center_agent_id': f"CCA{random.randint(100, 150)}",
                'mode_of_contact': random.choice(CONTACT_MODES)
            })

        # Process repairs
        for _ in range(weekly_repairs[w]):
            c_id = w_cust_ids[idx]
            idx += 1
            r_date = random.choice(week_dates)
            fault = random.choice(fault_codes)
            job_id = f"JOB{str(job_counter).zfill(8)}"
            job_counter += 1
            all_repairs.append({
                'job_id': job_id,
                'customer_id': c_id,
                'repair_date': r_date,
                'repair_type': 'Emergency',
                'parts_changed': random.choice(parts_ref)['part'],
                'fault_code': fault['fault_code'],
                'fault_reason': fault['explanation_related_fault_codes']
            })
            all_appointments.append({
                'job_id': job_id,
                'appointment_date': r_date,
                'job_category': 'Repair',
                'severity': fault['severity']
            })
            all_visits.append({
                'job_id': job_id,
                'customer_id': c_id,
                'visit_date': r_date,
                'visit_status': random.choice(['Completed', 'Parts Required']),
                'customer_feedback': random.choice(['Good', 'Average', 'Poor'])
            })
            all_contacts.append({
                'job_id': job_id,
                'job_registration_datetime': f"{r_date} 08:30:00",
                'contact_center_agent_id': f"CCA{random.randint(100, 150)}",
                'mode_of_contact': random.choice(CONTACT_MODES)
            })

    df_installation = pd.DataFrame(all_leads)
    df_quotes = pd.DataFrame(all_quotes)
    df_service = pd.DataFrame(all_services)
    df_repair = pd.DataFrame(all_repairs)
    df_appointment = pd.DataFrame(all_appointments)
    df_visit = pd.DataFrame(all_visits)
    df_contact = pd.DataFrame(all_contacts)

    # 3. Generating Master Data for Active Customers
    print("Generating Master Data...")
    active_customers = list(set(
        df_installation['customer_id'].tolist() + 
        df_service['customer_id'].tolist() + 
        df_repair['customer_id'].tolist()
    ))

    n_cust = len(active_customers)
    df_customer_master = pd.DataFrame({
        'customer_id': active_customers,
        'customer_name': [f"Customer_{i}" for i in range(n_cust)],
        'boiler_history': 'Yes',
        'boiler_company': np.random.choice(BOILER_MANUFACTURERS, n_cust),
        'registration_date': np.random.choice(pd.date_range(start=CURRENT_START - timedelta(days=365*3), end=start_date), n_cust),
        'have_insurance': np.random.choice(['Yes', 'No'], n_cust)
    })

    df_customer_holdings = pd.DataFrame({
        'customer_id': active_customers,
        'city': np.random.choice(CITIES, n_cust),
        'pincode': [f"PC{np.random.randint(1000, 9999)}" for _ in range(n_cust)],
        'region': np.random.choice(REGIONS, n_cust),
        'terrian': np.random.choice(TERRAINS, n_cust)
    })

    df_property_master = pd.DataFrame({
        'customer_id': active_customers,
        'property_type': np.random.choice(PROPERTY_TYPES, n_cust),
        'number_of_floors': np.random.randint(1, 4, n_cust),
        'rooms': np.random.randint(2, 8, n_cust),
        'have_gas_pipeline': np.random.choice(['Yes', 'No'], n_cust),
        'external_or_internal_electricity_source': np.random.choice(['Company Provided', 'Solar', 'Grid + Solar'], n_cust),
        'property_built_date': np.random.choice(pd.date_range(start='1970-01-01', end='2020-01-01'), n_cust)
    })

    df_epc = pd.DataFrame({
        'pincode': df_customer_holdings['pincode'],
        'customer_id': active_customers,
        'epc_rating': np.random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G'], n_cust),
        'current_energy_efficiency': np.random.randint(1, 100, n_cust),
        'potential_energy_efficiency': np.random.randint(50, 100, n_cust)
    })

    df_boiler_master = pd.DataFrame({
        'customer_id': active_customers,
        'boiler_id': np.random.choice([p['boiler_id'] for p in product_info], n_cust),
        'installation_date': np.random.choice(pd.date_range(start=CURRENT_START - timedelta(days=365*3), end=start_date), n_cust),
        'boiler_type': np.random.choice(BOILER_TYPES, n_cust),
        'boiler_manufacturer': np.random.choice(BOILER_MANUFACTURERS, n_cust),
        'model': 'Model X',
        'energy_rating': np.random.choice(ENERGY_RATINGS, n_cust),
        'voltage': '230V',
        'have_insurance': np.random.choice(['Yes', 'No'], n_cust),
        'last_service_date': '',
        'fault_history': np.random.choice(['None', 'F22', 'F75', 'EA', 'Ignition Failure'], n_cust)
    })

    # 4. Engineers
    print(f"Generating Engineers ({NUM_ENGINEERS})...")
    engineers = []
    for i in range(NUM_ENGINEERS):
        engineers.append({
            'engineer_name': f"Engineer_{i}",
            'pay_id': f"ENG{str(i+1).zfill(5)}",
            'home_location': random.choice(CITIES),
            'work_location': random.choice(REGIONS),
            'joining_date': (datetime.now() - timedelta(days=random.randint(30, 1000))).strftime('%Y-%m-%d')
        })
    df_engineer_master = pd.DataFrame(engineers)
    pay_ids = df_engineer_master['pay_id'].tolist()

    df_eng_skills = pd.DataFrame({
        'pay_id': pay_ids,
        'direct_labour_or_contractor': np.random.choice(['Direct Labour', 'Contractor'], NUM_ENGINEERS),
        'training_result': np.random.choice(['Pass', 'Merit', 'Distinction'], NUM_ENGINEERS),
        'profiency': np.random.choice(['Beginner', 'Intermediate', 'Expert'], NUM_ENGINEERS),
        'multi_skill_or_single_skill': np.random.choice(['Multi Skill', 'Single Skill'], NUM_ENGINEERS),
        'primary_skill': np.random.choice(JOB_CATEGORIES, NUM_ENGINEERS),
        'secondary_skill': np.random.choice(JOB_CATEGORIES + ['None'], NUM_ENGINEERS)
    })

    # Assign appointments to engineers
    df_appointment['assigned_pay_id'] = np.random.choice(pay_ids, len(df_appointment))

    dates_repeated = np.tile(dates, NUM_ENGINEERS)
    eng_repeated = np.repeat(pay_ids, len(dates))

    df_eng_avail = pd.DataFrame({
        'pay_id': eng_repeated,
        'shift_date': dates_repeated,
        'shift_start_time': '08:00:00',
        'shift_end': '16:00:00',
        'lunch_start': '12:00:00',
        'lunch_end': '13:00:00',
        'non_productive_event_start_time': np.random.choice(['15:00:00', None], len(eng_repeated), p=[0.2, 0.8]),
    })
    df_eng_avail['non_productive_event_end_time'] = df_eng_avail['non_productive_event_start_time'].apply(lambda x: '16:00:00' if x else None)

    df_eng_prod = pd.DataFrame({
        'pay_id': eng_repeated,
        'shift_date': dates_repeated,
        'productivity': np.random.uniform(4.0, 8.0, len(eng_repeated)).round(2)
    })

    # Forecasting & Inventory & Weather
    print("Generating Forecasts and Inventory...")
    forecast_dates = future_dates_range

    daily_service_per_region = int((BASE_SERVICES / 7 / len(REGIONS)) * 0.92)
    daily_repair_per_region = int((BASE_REPAIRS / 7 / len(REGIONS)) * 0.90)

    reg_demand = []
    reg_capacity = []
    for r in REGIONS:
        for d in forecast_dates:
            for job_cat in ['Service', 'Repair']:
                if job_cat == 'Service':
                    num_jobs = max(0, int(np.random.normal(daily_service_per_region, max(5, int(daily_service_per_region * 0.08)))))
                    det_cat = 'Annual Service'
                else:
                    num_jobs = max(0, int(np.random.normal(daily_repair_per_region, max(3, int(daily_repair_per_region * 0.12)))))
                    det_cat = random.choice(['Boiler Breakdown', 'Leak'])

                reg_demand.append({
                    'date': d, 'region': r, 'job_type': job_cat,
                    'detailed_category': det_cat,
                    'number_of_jobs': num_jobs, 'jobs_hours': int(num_jobs * random.uniform(1.5, 2.5))
                })

            gross_h = random.randint(500, 750)
            npe_h = random.randint(30, 80)
            ot_h = random.randint(0, 50)
            avail_h = gross_h - npe_h + ot_h

            reg_capacity.append({
                'date': d, 'region': r, 'eng_skill_type': random.choice(JOB_CATEGORIES),
                'gross_hours': gross_h, 'non_productive_event': npe_h,
                'overtime': ot_h, 'available_hours': avail_h
            })
    df_reg_demand = pd.DataFrame(reg_demand)
    df_reg_capacity = pd.DataFrame(reg_capacity)

    inventory = []
    locations = ['Central Hub', 'Van 1', 'Van 2', 'Van 3', 'North Depot']
    for p in parts_ref:
        for l in locations:
            inventory.append({
                'location': l, 'part_category': 'Boiler Parts', 'manufacturer': random.choice(BOILER_MANUFACTURERS),
                'part_type': p['part'], 'in_stock': random.randint(0, 500), 'recycled': random.choice(['Yes', 'No'])
            })
    df_inventory = pd.DataFrame(inventory)

    weather = []
    for d in all_dates_range:
        weather.append({
            'pincode': 'ALL', 'date': d,
            'temperature': round(random.uniform(-5.0, 30.0), 1),
            'humidity': random.randint(40, 95),
            'rain': round(random.uniform(0, 20.0), 1),
            'wind': round(random.uniform(5.0, 40.0), 1),
            'solar_radiation': random.randint(100, 800),
            'atmospheric_pressure': random.randint(980, 1030)
        })
    df_weather = pd.DataFrame(weather)

    exports = {
        'customer_master': df_customer_master,
        'customer_holdings': df_customer_holdings,
        'property_master': df_property_master,
        'boiler_master': df_boiler_master,
        'product_and_warranty_info': df_product_info,
        'installation_history': df_installation,
        'quotes_and_sales': df_quotes,
        'service_history': df_service,
        'repair_history': df_repair,
        'visit_outcome': df_visit,
        'fault_codes': df_fault_codes,
        'parts_replaced': df_parts,
        'engineer_master': df_engineer_master,
        'engineer_availability_and_shifts': df_eng_avail,
        'engineer_skill': df_eng_skills,
        'engineer_productivity': df_eng_prod,
        'appointment_schedule': df_appointment,
        'contact_center_interaction': df_contact,
        'regional_demand_forecast': df_reg_demand,
        'regional_capacity_forecast': df_reg_capacity,
        'inventory_and_van_stock': df_inventory,
        'weather': df_weather,
        'epc_property_data': df_epc,
        'business_rules': df_business_rules
    }

    print("Exporting datasets...")
    for name, df in exports.items():
        file_path = os.path.join(output_dir, f"{name}.csv")
        df.to_csv(file_path, index=False)
        print(f"Exported {file_path} ({len(df)} rows)")

    print("Injecting demo signals (weather event & sales conversion dip)...")
    try:
        from scripts.inject_demo_signal import inject
        inject(Path(output_dir), week_start=None)
        print("Demo signals injected successfully!")
    except Exception as e:
        print(f"Demo signal injection note: {e}")

    print("All datasets generated successfully!")

if __name__ == '__main__':
    generate_all_datasets()
