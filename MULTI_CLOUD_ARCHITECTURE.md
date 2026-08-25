# Multi-Cloud and Databricks Architecture for Utilities Knowledge Hub

## 1. Overview

This application is a Flask-based enterprise AI chatbot that combines:

- a LangChain agent layer
- a knowledge graph / RAG layer
- structured data access
- role-based access checks
- AI-driven operational assistance

The current project structure already separates concerns into:

- app/main.py for the web app and orchestration
- app/services/data_service.py for dataset access
- app/services/sql_service.py for SQL query access
- app/services/graph_service.py for graph and retrieval logic

This makes it a strong candidate for deployment in Azure, AWS, and Databricks while keeping the same app logic intact.

---

## 2. Target architecture pattern

The right enterprise pattern is not to connect the chatbot directly to every raw system. Instead, use a governed data integration layer:

1. Source systems
   - PostgreSQL
   - Salesforce
   - Workday
   - Databricks / Unity Catalog
   - Azure Blob / ADLS / OneLake
   - AWS S3
   - Data lake / warehouse tables
2. Ingestion layer
   - Batch sync
   - CDC / incremental polling
   - API extraction
3. Raw landing zone
   - source-specific storage by timestamp
4. Curated / silver layer
   - normalized tables and dimensions
5. Gold / semantic layer
   - business-ready views for the app
6. AI application layer
   - Flask app queries only curated and governed data

This reduces risk, improves governance, and keeps the app scalable.

---

## 3. Azure deployment architecture

### Components

- App hosting: Azure App Service or Azure Container Apps
- Runtime: Python Flask app
- Data source connectivity:
  - Azure Database for PostgreSQL
  - Azure Data Factory for ingestion
  - Azure Blob Storage / ADLS Gen2
  - Microsoft Fabric / OneLake / Lakehouse
  - Databricks via Unity Catalog or JDBC
- Governance: Microsoft Purview
- Secrets: Azure Key Vault
- Identity: Microsoft Entra ID + Managed Identity

### Azure flow

```text
Salesforce / Workday / Postgres / Blob / OneLake
                 |
                 v
        Azure Data Factory / Azure Functions
                 |
                 v
          Raw landing zone (ADLS / Blob)
                 |
                 v
      Databricks / Synapse / Lakehouse / SQL
                 |
                 v
         Curated views and semantic tables
                 |
                 v
     Flask app + LangChain + RBAC + Graph/RAG
```

### Why this works

- Flexible source connectivity
- Strong enterprise identity and governance
- Easy integration with Microsoft ecosystem
- Controls for data residency and security

---

## 4. AWS deployment architecture

### Components

- App hosting: ECS Fargate, EKS, or Elastic Beanstalk
- Data sources:
  - RDS / Aurora PostgreSQL
  - Salesforce and Workday via Lambda + Step Functions
  - S3 raw storage
  - Glue Data Catalog
  - Athena / Redshift / Lake Formation
- Security: IAM, KMS, Secrets Manager, VPC
- Orchestration: AWS Glue ETL + Step Functions

### AWS flow

```text
Salesforce / Workday / Postgres / S3 / lakehouse
                 |
                 v
       Lambda / Step Functions / Glue ETL
                 |
                 v
           S3 landing + cataloged raw data
                 |
                 v
      Athena / Redshift / Glue curated tables
                 |
                 v
     Flask app + AI retrieval + governed views
```

### Why this works

- Mature lakehouse and ingestion capabilities
- Strong IAM-based governance
- Good fit for large-scale S3 and analytics workloads

---

## 5. Databricks implementation pattern

Databricks is an excellent fit for this app because the app already consumes multiple structured datasets and can benefit from a lakehouse architecture.

### Recommended Databricks pattern

1. Ingest source data into Databricks using:
   - Auto Loader for S3 / ADLS / OneLake files
   - JDBC connectors for PostgreSQL and other structured systems
   - Databricks REST API integrations for Salesforce / Workday
2. Land raw data into bronze tables
3. Transform into silver tables
4. Build gold business views for the chatbot
5. Expose curated views through Unity Catalog
6. Let the app access these views via:
   - Databricks SQL warehouse
   - JDBC/ODBC driver
   - API-based query service

### Example Databricks layer layout

```text
Bronze:
- salesforce_raw
- workday_raw
- postgres_raw
- blob_raw
- s3_raw

Silver:
- customer_dim
- work_order_fact
- employee_dim
- asset_dim
- service_history_fact

Gold:
- operational_dashboard_vw
- customer_service_view
- outage_summary_vw
- demand_forecast_vw
- access_policy_vw
```

### Databricks security model

- Unity Catalog for governance and access control
- Catalog / schema / table-level RBAC
- External locations for ADLS or S3
- Service principals for automated ingestion
- Secrets stored in Databricks Secret Scope or cloud secret manager

---

## 6. How to connect this app to Databricks

There are three practical patterns.

### Option A: App reads Databricks SQL warehouse directly

This is the simplest pattern for the current Flask app.

- Create a Databricks SQL warehouse
- Expose curated views in Unity Catalog
- Use a SQLAlchemy connector or JDBC driver in the app
- Replace or supplement the local CSV-based access layer

This fits the current design well because the app already centralizes data access in service layer classes.

### Option B: Databricks produces curated Delta tables and the app consumes them via API

- Databricks notebooks prepare curated tables
- A REST endpoint or SQL warehouse exposes the final views
- The app calls a secure API or SQL warehouse endpoint to retrieve only the required records

This is useful when the app needs a more controlled and governed query pipeline.

### Option C: Hybrid model

- Keep the AI app in Python
- Keep the heavy transformations in Databricks
- Use the app only for orchestration, RAG, chat, and role-based access

This is the recommended architecture for an enterprise AI assistant.

---

## 7. Suggested implementation for this repo

The repo is already organized in a way that makes this feasible without a complete rewrite.

### Step 1: Create a source abstraction layer

Add a new package like:

```text
app/services/connectors/
  __init__.py
  base_connector.py
  postgres_connector.py
  salesforce_connector.py
  workday_connector.py
  s3_connector.py
  blob_connector.py
  onelake_connector.py
  databricks_connector.py
```

Each connector should expose methods like:

- connect()
- list_tables()
- read_table()
- read_incremental()
- get_schema()
- validate_access()

### Step 2: Keep current app service as the facade

Refactor the existing service layer so that:

- local CSV access remains the fallback
- cloud-native connectors are used when configured
- data source selection is controlled by environment settings

Example approach:

```python
class UnifiedDataService:
    def __init__(self, config):
        self.sources = {
            "postgres": PostgresConnector(config),
            "salesforce": SalesforceConnector(config),
            "workday": WorkdayConnector(config),
            "s3": S3Connector(config),
            "blob": BlobConnector(config),
            "databricks": DatabricksConnector(config),
        }
```

### Step 3: Add Databricks config settings

Environment variables could include:

```bash
DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
DATABRICKS_TOKEN=***
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
DATABRICKS_CATALOG=main
DATABRICKS_SCHEMA=utilities
```

Also add:

- source enable/disable flags
- warehouse names
- access control settings
- staging and curated table names

### Step 4: Create a curated warehouse model

Your app should query a model like:

- `customer_master`
- `work_order_fact`
- `engineer_skill`
- `install_history`
- `regional_demand_forecast`
- `repair_history`

This is already aligned with the current CSV dataset patterns in the repo.

---

## 8. Databricks workflow example

A typical job flow can look like this:

```text
Notebook 1: Ingest raw data from Salesforce, Workday, and Postgres
Notebook 2: Normalize to bronze schema
Notebook 3: Clean and deduplicate to silver tables
Notebook 4: Create gold views for the chatbot
Notebook 5: Publish a curated access layer
Notebook 6: Trigger refresh for app queries
```

### Example notebook stages

- `00_raw_ingest`
- `01_bronze_load`
- `02_silver_transform`
- `03_gold_curated_views`
- `04_security_and_access`
- `05_refresh_metrics`

---

## 9. Data governance and access control

This app already includes access checks and role-based concepts. In a production multi-source environment, this should be expanded with:

- row-level security
- table-level restrictions
- purpose-based access
- audit logging for every retrieval
- classification of sensitive data

The same principle should apply in Databricks with Unity Catalog:

- only approved roles can query sensitive tables
- restricted datasets are masked or filtered
- access events are logged centrally

---

## 10. Recommended architecture for this project

### Best overall design

For this specific application, the strongest production design is:

- Flask app stays as the user-facing brain
- Databricks becomes the data engineering and lakehouse layer
- Azure or AWS provides the cloud hosting and identity layer
- App queries curated tables and views, not raw sources
- RBAC and data governance are enforced centrally

### Example end-state architecture

```text
User / Browser
      |
      v
Flask app (Azure App Service or AWS ECS)
      |
      +--> LangChain agent / RAG / graph logic
      |
      +--> Unified data service
                 |
                 +--> Databricks SQL / Delta Tables
                 +--> Postgres
                 +--> Salesforce
                 +--> Workday
                 +--> S3 / Blob / OneLake
```

---

## 11. Final recommendation

If you are building this for an enterprise utilities environment, use the following standard:

- Azure-first if your enterprise is Microsoft-centric
- AWS-first if your platform already uses S3, Glue, and Redshift
- Databricks as the governing lakehouse engine for ingestion, transformation, and curated business data
- Flask app as the secure user-facing AI layer

This gives you the best mix of:

- governance
- scalability
- multi-source data integration
- enterprise-grade security
- AI-powered analytics and retrieval

---

## 12. Next implementation steps

1. Standardize source schemas into common domain tables
2. Build bronze/silver/gold in Databricks
3. Connect the Flask app to Databricks SQL or curated APIs
4. Add RBAC and audit logging
5. Deploy app to Azure App Service or AWS ECS
6. Add automated refresh jobs for source ingestion

This is the cleanest path from a demo project to a production multi-cloud data platform.
