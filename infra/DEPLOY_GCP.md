# Google Cloud Platform (GCP) Deployment Blueprint

This guide provides complete, production-ready specifications for deploying the **Fixdesk** system to Google Cloud Platform.

---

## 1. Architectural Component Mapping Table

| Local / Open-Source Component | Google Cloud Platform Managed Equivalent | Alternative GCP Architecture (Serverless Data Warehouse) |
| :--- | :--- | :--- |
| **Relational Database** | **Cloud SQL for PostgreSQL 16** (with `pgvector` extension enabled) | **BigQuery** (stores sales dataset partitioned by outlet/item) |
| **Vector Store (RAG)** | **Cloud SQL pgvector** (cosine distance `<=>`) | **Vertex AI Vector Search** (high-scale vector index) |
| **PySpark ETL Pipeline** | **Dataproc Serverless** (Spark batches without managing clusters) | **BigQuery Dataform** / SQL transformations |
| **Agent / Backend** | **Cloud Run** (FastAPI containerized service with auto-scaling to zero) | **Google Kubernetes Engine (GKE Autopilot)** |
| **Frontend UI** | **Cloud Run** (Next.js standalone container) or **Firebase App Hosting** | **Cloud Storage + Cloud CDN** (if static export) |
| **LLM & Embeddings** | **Vertex AI Gemini API** (`gemini-1.5-flash`, `text-embedding-004`) | **Self-hosted vLLM on GKE with L4 GPUs** |
| **Storage (CSV, Parquet, Docs)** | **Google Cloud Storage (GCS)** (Standard storage bucket) | **GCS with Lifecycle rules** (Archive / Nearline) |
| **Secrets & Keys** | **Secret Manager** (stores `GOOGLE_API_KEY` and DB credentials) | **KMS + Cloud IAM Workload Identity** |
| **CI/CD & Images** | **Artifact Registry** + **Cloud Build** | **GitHub Actions** with Google Workload Identity |

---

## 2. Infrastructure Setup Walkthrough

### Step 1: GCP Project Initialization & Service APIs
```bash
# Set default project and region
gcloud config set project YOUR_GCP_PROJECT_ID
export REGION="us-central1"

# Enable required Google Cloud APIs
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    dataproc.googleapis.com \
    aiplatform.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com
```

### Step 2: Database Provisioning (Cloud SQL PostgreSQL + pgvector)
```bash
# Create Cloud SQL PostgreSQL 16 instance
gcloud sql instances create fixdesk-db \
    --database-version=POSTGRES_16 \
    --tier=db-custom-2-7680 \
    --region=$REGION \
    --storage-size=20GB \
    --storage-type=SSD \
    --database-flags=cloudsql.enable_pgvector=on

# Create application database
gcloud sql databases create fixdesk --instance=fixdesk-db

# Set passwords and create read-only role
gcloud sql users set-password postgres --instance=fixdesk-db --password="STRONG_ADMIN_PASSWORD"
```

Connect via Cloud SQL Auth Proxy and execute `infra/init.sql` to initialize tables, enable `vector`, and configure the `sales_readonly` role.

### Step 3: PySpark ETL on Dataproc Serverless
```bash
# Upload raw CSV and PySpark script to Cloud Storage
gsutil cp data/BigMart_Sales.csv gs://fixdesk-data/raw/BigMart_Sales.csv
gsutil cp pipelines/clean_sales.py gs://fixdesk-data/scripts/clean_sales.py

# Submit serverless PySpark batch job
gcloud dataproc batches submit pyspark gs://fixdesk-data/scripts/clean_sales.py \
    --region=$REGION \
    --deps-bucket=gs://fixdesk-data/deps \
    --jars=gs://fixdesk-data/jars/postgresql-42.7.3.jar \
    --properties=spark.sql.shuffle.partitions=16
```

### Step 4: Build & Deploy Containers to Cloud Run
```bash
# Create Artifact Registry Docker repository
gcloud artifacts repositories create fixdesk-repo \
    --repository-format=docker \
    --location=$REGION

# Build and push Backend container
gcloud builds submit --tag $REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/backend:latest \
    -f infra/Dockerfile.backend .

# Deploy Backend to Cloud Run
gcloud run deploy fixdesk-backend \
    --image=$REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/backend:latest \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="LLM_MODEL=gemini-1.5-flash,EMBEDDING_MODEL=text-embedding-004" \
    --set-secrets="GOOGLE_API_KEY=google-api-key:latest,DATABASE_URL=db-url:latest,READONLY_DATABASE_URL=readonly-db-url:latest" \
    --add-cloudsql-instances=YOUR_GCP_PROJECT_ID:$REGION:fixdesk-db

# Build and push Frontend container
gcloud builds submit --tag $REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/frontend:latest \
    -f infra/Dockerfile.frontend frontend/

# Deploy Frontend to Cloud Run
gcloud run deploy fixdesk-frontend \
    --image=$REGION-docker.pkg.dev/YOUR_GCP_PROJECT_ID/fixdesk-repo/frontend:latest \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="NEXT_PUBLIC_API_URL=https://fixdesk-backend-XYZ-uc.a.run.app"
```

---

## 3. Vertex AI Integration Note
To switch from Google AI Studio API keys to enterprise IAM-governed Vertex AI:
1. Update `backend/agent/nodes.py` to initialize `ChatVertexAI(model_name="gemini-1.5-flash", project="YOUR_GCP_PROJECT_ID", location="us-central1")`.
2. Grant the Cloud Run service account the IAM role `roles/aiplatform.user`.
3. Eliminate API key tokens completely in favor of native Google Cloud IAM OAuth tokens.
