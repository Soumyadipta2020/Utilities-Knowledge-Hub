import pandas as pd
import numpy as np
from faker import Faker
import random
import os
from datetime import datetime, timedelta
import string

fake = Faker('en_GB')
Faker.seed(42)
random.seed(42)
np.random.seed(42)

NUM_CUSTOMERS = 500
NUM_ENGINEERS = 30
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
VISIT_STATUSES = ['Completed', 'No Access', 'Rescheduled', 'Parts Required']
FAULT_SEVERITY = ['Low', 'Medium', 'High', 'Critical']
JOB_CATEGORIES = ['Service', 'Repair', 'Installation']

def random_date(start, end):
    return start + timedelta(days=random.randint(0, int((end - start).days)))

output_dir = 'datasets'
os.makedirs(output_dir, exist_ok=True)

# 1. Reference Data
# -------------------------------------------------------------
# Product & Warranty Info (Reference for Boiler Master)
product_info = []
for i in range(NUM_BOILERS_REF):
    b_id = f"PROD{str(i+1).zfill(3)}"
    b_type = random.choice(BOILER_TYPES)
    manufacturer = random.choice(BOILER_MANUFACTURERS)
    product_info.append({
        'boiler_id': b_id,
        'boiler_type': b_type,
        'energy_rating': random.choice(ENERGY_RATINGS),
        'energy_consumption': random.randint(10000, 20000), # kWh/year
        'life_span': random.randint(10, 20),
        'manufacturer': manufacturer,
        'imported': random.choice(['Yes', 'No']),
        'warranty': random.randint(5, 12),
        'addition_warranty_purchased': random.choice(['Yes', 'No']),
    })
df_product_info = pd.DataFrame(product_info)
# Add end date if warranty purchased
df_product_info['addition_warranty_end_date'] = df_product_info.apply(
    lambda row: (datetime.now() + timedelta(days=random.randint(365, 365*5))).strftime('%Y-%m-%d') if row['addition_warranty_purchased'] == 'Yes' else None, axis=1)

# Fault Codes
fault_codes = []
for i in range(NUM_FAULTS_REF):
    fc = f"F{random.randint(10, 99)}"
    fault_codes.append({
        'fault_code': fc,
        'explanation_related_fault_codes': fake.sentence(nb_words=6),
        'severity': random.choice(FAULT_SEVERITY),
        'repair_cost': round(random.uniform(50, 500), 2)
    })
df_fault_codes = pd.DataFrame(fault_codes)

# Parts Replaced
parts_ref = []
for i in range(NUM_PARTS_REF):
    parts_ref.append({
        'part': f"Part_{fake.word().capitalize()}",
        'replacement_cost': round(random.uniform(20, 300), 2),
        'severity': random.choice(FAULT_SEVERITY),
        'average_life_span': random.randint(2, 10)
    })
df_parts = pd.DataFrame(parts_ref)

# Business Rules
business_rules = [
    {'rule_id': 'R1', 'rule_name': 'Warranty SLA', 'description': 'Repairs under warranty must be attended within 24 hours'},
    {'rule_id': 'R2', 'rule_name': 'Service Eligibility', 'description': 'Annual service required to maintain warranty'},
    {'rule_id': 'R3', 'rule_name': 'Standard SLA', 'description': 'Standard repairs must be attended within 48 hours'}
]
df_business_rules = pd.DataFrame(business_rules)

# Knowledge Base
kb_data = [
    {'doc_id': 'KB001', 'doc_type': 'Manual', 'title': 'Worcester Bosch Installation Guide', 'content': fake.text()},
    {'doc_id': 'KB002', 'doc_type': 'SOP', 'title': 'Standard Operating Procedure for Annual Service', 'content': fake.text()},
    {'doc_id': 'KB003', 'doc_type': 'Trouble shoot guide', 'title': 'Low Pressure Troubleshooting', 'content': fake.text()},
    {'doc_id': 'KB004', 'doc_type': 'Metric definitions', 'title': 'Productivity Metrics Definition', 'content': fake.text()},
    {'doc_id': 'KB005', 'doc_type': 'how buisness work for utilities in UK', 'title': 'UK Utilities Sector Overview', 'content': fake.text()}
]
df_kb = pd.DataFrame(kb_data)

# 2. Master Data (Engineers)
# -------------------------------------------------------------
engineers = []
for i in range(NUM_ENGINEERS):
    pay_id = f"ENG{str(i+1).zfill(3)}"
    engineers.append({
        'engineer_name': fake.name(),
        'pay_id': pay_id,
        'home_location': fake.city(),
        'work_location': random.choice(REGIONS),
        'joining_date': fake.date_between(start_date='-5y', end_date='today').strftime('%Y-%m-%d')
    })
df_engineer_master = pd.DataFrame(engineers)

eng_skills = []
for eng in engineers:
    pay_id = eng['pay_id']
    eng_skills.append({
        'pay_id': pay_id,
        'direct_labour_or_contractor': random.choice(['Direct Labour', 'Contractor']),
        'training_result': random.choice(['Pass', 'Merit', 'Distinction']),
        'profiency': random.choice(['Beginner', 'Intermediate', 'Expert']),
        'multi_skill_or_single_skill': random.choice(['Multi Skill', 'Single Skill']),
        'primary_skill': random.choice(JOB_CATEGORIES),
        'secondary_skill': random.choice(JOB_CATEGORIES + ['None'])
    })
df_eng_skills = pd.DataFrame(eng_skills)

# 3. Master Data (Customers)
# -------------------------------------------------------------
customer_master = []
customer_holdings = []
property_master = []
boiler_master = []
epc_data = []

customer_ids = [f"CUST{str(i+1).zfill(5)}" for i in range(NUM_CUSTOMERS)]

for cust_id in customer_ids:
    has_boiler = random.choice(['Yes', 'No'])
    has_insurance = random.choice(['Yes', 'No'])
    registration_date = fake.date_between(start_date='-10y', end_date='today')
    
    # Customer Master
    customer_master.append({
        'customer_id': cust_id,
        'customer_name': fake.name(),
        'boiler_history': has_boiler,
        'boiler_company': random.choice(BOILER_MANUFACTURERS) if has_boiler == 'Yes' else None,
        'registration_date': registration_date.strftime('%Y-%m-%d'),
        'have_insurance': has_insurance
    })
    
    # Customer Holdings
    pincode = fake.postcode()
    customer_holdings.append({
        'customer_id': cust_id,
        'city': random.choice(CITIES),
        'pincode': pincode,
        'region': random.choice(REGIONS),
        'terrian': random.choice(TERRAINS)
    })
    
    # Property Master & EPC
    prop_type = random.choice(PROPERTY_TYPES)
    property_master.append({
        'customer_id': cust_id,
        'property_type': prop_type,
        'number_of_floors': random.randint(1, 4),
        'rooms': random.randint(2, 8),
        'have_gas_pipeline': random.choice(['Yes', 'No']),
        'external_or_internal_electricity_source': random.choice(['Company Provided', 'Solar', 'Grid + Solar']),
        'property_built_date': fake.date_between(start_date='-50y', end_date='-1y').strftime('%Y-%m-%d')
    })
    
    epc_data.append({
        'pincode': pincode,
        'customer_id': cust_id,
        'epc_rating': random.choice(['A', 'B', 'C', 'D', 'E', 'F', 'G']),
        'current_energy_efficiency': random.randint(1, 100),
        'potential_energy_efficiency': random.randint(50, 100)
    })

    # Boiler Master
    if has_boiler == 'Yes':
        prod = random.choice(product_info)
        install_date = fake.date_between(start_date=registration_date, end_date='today')
        last_service = install_date + timedelta(days=random.randint(100, 365))
        if last_service > datetime.now().date():
            last_service = None
        else:
            last_service = last_service.strftime('%Y-%m-%d')
            
        boiler_master.append({
            'customer_id': cust_id,
            'boiler_id': prod['boiler_id'],
            'installation_date': install_date.strftime('%Y-%m-%d'),
            'boiler_type': prod['boiler_type'],
            'boiler_manufacturer': prod['manufacturer'],
            'model': f"{prod['manufacturer']} Model {random.choice(string.ascii_uppercase)}",
            'energy_rating': prod['energy_rating'],
            'voltage': '230V',
            'have_insurance': has_insurance,
            'last_service_date': last_service,
            'fault_history': random.choice(['None', 'F22', 'F75', 'EA', 'Ignition Failure'])
        })

df_customer_master = pd.DataFrame(customer_master)
df_customer_holdings = pd.DataFrame(customer_holdings)
df_property_master = pd.DataFrame(property_master)
df_boiler_master = pd.DataFrame(boiler_master)
df_epc = pd.DataFrame(epc_data)

# 4. Transactional Data (History & Jobs)
# -------------------------------------------------------------
installation_history = []
quotes_and_sales = []
service_history = []
repair_history = []
visit_outcome = []
contact_center = []
appointment_schedule = []

lead_counter = 1
job_counter = 1

for idx, cust in df_customer_master.iterrows():
    cust_id = cust['customer_id']
    
    # 1. Lead / Installation
    if cust['boiler_history'] == 'Yes':
        lead_id = f"LD{str(lead_counter).zfill(5)}"
        lead_counter += 1
        
        boiler_row = df_boiler_master[df_boiler_master['customer_id'] == cust_id].iloc[0]
        install_date_str = boiler_row['installation_date']
        install_date = datetime.strptime(install_date_str, '%Y-%m-%d').date()
        lead_date = install_date - timedelta(days=random.randint(10, 30))
        appt_date = install_date - timedelta(days=random.randint(1, 5))
        
        installation_history.append({
            'customer_id': cust_id,
            'lead_id': lead_id,
            'lead_date': lead_date.strftime('%Y-%m-%d'),
            'mode_of_conversation_with_customer': random.choice(CONTACT_MODES),
            'appointment_date': appt_date.strftime('%Y-%m-%d'),
            'appointment_happened': 'Yes',
            'sale_date': (appt_date + timedelta(days=1)).strftime('%Y-%m-%d'),
            'sale_happened': 'Yes',
            'installation_date': install_date_str,
            'installation_happened': 'Yes',
            'insurance_purchased': cust['have_insurance']
        })
        
        # Quotes and Sales
        quotes_and_sales.append({
            'lead_id': lead_id,
            'primary_qutation': round(random.uniform(1500, 3000), 2),
            'secondary_quotation': round(random.uniform(1200, 2500), 2),
            'final_quotation': round(random.uniform(1400, 2800), 2)
        })
        
        # Appointment for Installation
        job_id = f"JOB{str(job_counter).zfill(6)}"
        job_counter += 1
        appt_pay_id = random.choice(engineers)['pay_id']
        appointment_schedule.append({
            'job_id': job_id,
            'appointment_date': install_date_str,
            'job_category': 'Installation',
            'severity': 'Medium',
            'assigned_pay_id': appt_pay_id
        })
        
        visit_outcome.append({
            'customer_id': cust_id,
            'visit_date': install_date_str,
            'visit_status': 'Completed',
            'customer_feedback': random.choice(['Excellent', 'Good', 'Average'])
        })

    # 2. Services & Repairs
    # Generate 0-2 services per customer if they have a boiler
    if cust['boiler_history'] == 'Yes':
        num_services = random.randint(0, 2)
        for _ in range(num_services):
            srv_date = fake.date_between(start_date='-2y', end_date='today')
            service_history.append({
                'customer_id': cust_id,
                'service_date': srv_date.strftime('%Y-%m-%d'),
                'service_type': 'Annual Maintenance',
                'parts_serviced': 'Burner, Heat Exchanger'
            })
            
            job_id = f"JOB{str(job_counter).zfill(6)}"
            job_counter += 1
            appt_pay_id = random.choice(engineers)['pay_id']
            appointment_schedule.append({
                'job_id': job_id,
                'appointment_date': srv_date.strftime('%Y-%m-%d'),
                'job_category': 'Service',
                'severity': 'Low',
                'assigned_pay_id': appt_pay_id
            })
            
            visit_outcome.append({
                'customer_id': cust_id,
                'visit_date': srv_date.strftime('%Y-%m-%d'),
                'visit_status': 'Completed',
                'customer_feedback': random.choice(['Good', 'Average', 'Poor'])
            })
            
            contact_center.append({
                'job_id': job_id,
                'job_registration_datetime': (srv_date - timedelta(days=random.randint(5, 20))).strftime('%Y-%m-%d %H:%M:%S'),
                'contact_center_agent_id': f"CCA{random.randint(100, 150)}",
                'mode_of_contact': random.choice(CONTACT_MODES)
            })

    # Generate 0-1 repairs per customer
    num_repairs = random.randint(0, 1)
    for _ in range(num_repairs):
        rep_date = fake.date_between(start_date='-1y', end_date='today')
        fault = random.choice(fault_codes)
        part = random.choice(parts_ref)
        repair_history.append({
            'customer_id': cust_id,
            'repair_date': rep_date.strftime('%Y-%m-%d'),
            'repair_type': 'Emergency',
            'parts_changed': part['part'],
            'fault_code': fault['fault_code'],
            'fault_reason': fault['explanation_related_fault_codes']
        })
        
        job_id = f"JOB{str(job_counter).zfill(6)}"
        job_counter += 1
        appt_pay_id = random.choice(engineers)['pay_id']
        appointment_schedule.append({
            'job_id': job_id,
            'appointment_date': rep_date.strftime('%Y-%m-%d'),
            'job_category': 'Repair',
            'severity': fault['severity'],
            'assigned_pay_id': appt_pay_id
        })
        
        visit_outcome.append({
            'customer_id': cust_id,
            'visit_date': rep_date.strftime('%Y-%m-%d'),
            'visit_status': random.choice(['Completed', 'Parts Required']),
            'customer_feedback': random.choice(['Good', 'Average', 'Poor'])
        })
        
        contact_center.append({
            'job_id': job_id,
            'job_registration_datetime': (rep_date - timedelta(hours=random.randint(2, 48))).strftime('%Y-%m-%d %H:%M:%S'),
            'contact_center_agent_id': f"CCA{random.randint(100, 150)}",
            'mode_of_contact': random.choice(CONTACT_MODES)
        })

df_installation = pd.DataFrame(installation_history)
df_quotes = pd.DataFrame(quotes_and_sales)
df_service = pd.DataFrame(service_history)
df_repair = pd.DataFrame(repair_history)
df_visit = pd.DataFrame(visit_outcome)
df_contact = pd.DataFrame(contact_center)
df_appointment = pd.DataFrame(appointment_schedule)

# 5. Engineer Availability & Shifts & Productivity
# -------------------------------------------------------------
eng_availability = []
eng_productivity = []

start_date = datetime.now().date() - timedelta(days=30)
for eng in engineers:
    pay_id = eng['pay_id']
    for i in range(30):
        shift_date = start_date + timedelta(days=i)
        # Skip some weekends
        if shift_date.weekday() >= 5 and random.random() < 0.8:
            continue
            
        shift_start = "08:00:00"
        shift_end = "16:00:00"
        lunch_start = "12:00:00"
        lunch_end = "13:00:00"
        
        npe_start = "15:00:00" if random.random() < 0.2 else None
        npe_end = "16:00:00" if npe_start else None
        
        eng_availability.append({
            'pay_id': pay_id,
            'shift_date': shift_date.strftime('%Y-%m-%d'),
            'shift_start_time': shift_start,
            'shift_end': shift_end,
            'lunch_start': lunch_start,
            'lunch_end': lunch_end,
            'non_productive_event_start_time': npe_start,
            'non_productive_event_end_time': npe_end
        })
        
        avail_hrs = 7.0 if npe_start is None else 6.0
        workload_hrs = round(random.uniform(3.0, avail_hrs), 1)
        productivity = (workload_hrs / avail_hrs) * 8
        eng_productivity.append({
            'pay_id': pay_id,
            'shift_date': shift_date.strftime('%Y-%m-%d'),
            'productivity': round(productivity, 2)
        })

df_eng_avail = pd.DataFrame(eng_availability)
df_eng_prod = pd.DataFrame(eng_productivity)

# 6. Forecasting & Inventory & Weather
# -------------------------------------------------------------
reg_demand = []
reg_capacity = []

for r in REGIONS:
    for i in range(30):
        d_date = start_date + timedelta(days=i)
        
        reg_demand.append({
            'date': d_date.strftime('%Y-%m-%d'),
            'region': r,
            'job_type': random.choice(['Service', 'Repair']),
            'detailed_category': random.choice(['Annual Service', 'Boiler Breakdown', 'Leak']),
            'number_of_jobs': random.randint(10, 50),
            'jobs_hours': random.randint(20, 100)
        })
        
        reg_capacity.append({
            'date': d_date.strftime('%Y-%m-%d'),
            'region': r,
            'eng_skill_type': random.choice(JOB_CATEGORIES),
            'gross_hours': random.randint(100, 300),
            'non_productive_event': random.randint(10, 30),
            'overtime': random.randint(0, 20),
            'available_hours': random.randint(80, 280)
        })

df_reg_demand = pd.DataFrame(reg_demand)
df_reg_capacity = pd.DataFrame(reg_capacity)

inventory = []
locations = ['Central Hub', 'Van 1', 'Van 2', 'Van 3', 'North Depot']
for p in parts_ref:
    for l in locations:
        inventory.append({
            'location': l,
            'part_category': 'Boiler Parts',
            'manufacturer': random.choice(BOILER_MANUFACTURERS),
            'part_type': p['part'],
            'in_stock': random.randint(0, 50),
            'recycled': random.choice(['Yes', 'No'])
        })
df_inventory = pd.DataFrame(inventory)

weather = []
# Just generate some weather data for a few pincodes
unique_pincodes = df_customer_holdings['pincode'].unique()[:20]
for pin in unique_pincodes:
    for i in range(10):
        w_date = start_date + timedelta(days=i)
        weather.append({
            'pincode': pin,
            'date': w_date.strftime('%Y-%m-%d'),
            'temperature': round(random.uniform(-5.0, 30.0), 1),
            'humidity': random.randint(40, 95),
            'rain': round(random.uniform(0, 20.0), 1),
            'wind': round(random.uniform(5.0, 40.0), 1),
            'solar_radiation': random.randint(100, 800),
            'atmospheric_pressure': random.randint(980, 1030)
        })
df_weather = pd.DataFrame(weather)


# 7. Export all to CSV
# -------------------------------------------------------------
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
    'knowledge_base': df_kb,
    'inventory_and_van_stock': df_inventory,
    'weather': df_weather,
    'epc_property_data': df_epc,
    'business_rules': df_business_rules
}

for name, df in exports.items():
    file_path = os.path.join(output_dir, f"{name}.csv")
    df.to_csv(file_path, index=False)
    print(f"Exported {file_path} ({len(df)} rows)")

print("All datasets generated successfully!")
