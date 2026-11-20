# Amazon Web Services (AWS) Deployment Blueprint

This guide provides complete, production-ready specifications for deploying the **Business Assistant** system to AWS.

---

## 1. Architectural Component Mapping Table

| Local / Open-Source Component | AWS Managed Equivalent (Standard Cloud) | AWS Serverless / Alternative Architecture |
| :--- | :--- | :--- |
| **Relational Database** | **Amazon RDS for PostgreSQL 16** (with `pgvector` extension) | **Amazon Aurora PostgreSQL Serverless v2** |
| **Vector Store (RAG)** | **RDS PostgreSQL pgvector** (cosine distance `<=>`) | **Amazon OpenSearch Serverless** (Vector Engine) |
| **PySpark ETL Pipeline** | **AWS Glue 4.0** (Serverless Spark ETL job) | **Amazon EMR on EKS** or **EMR Serverless** |
| **Agent / Backend** | **AWS ECS on Fargate** or **AWS App Runner** (FastAPI) | **AWS Lambda** (Containerized image with FastAPI Mangum) |
| **Frontend UI** | **AWS ECS Fargate** or **AWS Amplify Hosting** | **Amazon S3 + CloudFront Distribution** |
| **LLM & Embeddings** | **Amazon Bedrock** (Claude 3.5 Sonnet / Titan Embeddings v2) or Gemini API | **Amazon SageMaker JumpStart Endpoints** |
| **Storage (CSV, Parquet, Docs)** | **Amazon S3** (Standard Storage Buckets) | **S3 Glacier Flexible Retrieval** (for archives) |
| **Secrets & Keys** | **AWS Secrets Manager** (stores DB passwords, API credentials) | **AWS Systems Manager Parameter Store** |
| **CI/CD & Images** | **Amazon ECR** + **AWS CodeBuild** | **GitHub Actions** with AWS OIDC IAM Roles |

---

## 2. Infrastructure Setup Walkthrough

### Step 1: Storage and Networking Provisioning
```bash
# Configure region
export AWS_REGION="us-east-1"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create S3 buckets for data lakes and document policies
aws s3 mb s3://business-assistant-datalake-$ACCOUNT_ID --region $AWS_REGION
aws s3 mb s3://business-assistant-docs-$ACCOUNT_ID --region $AWS_REGION

# Create ECR Docker container repositories
aws ecr create-repository --repository-name business-assistant-backend --region $AWS_REGION
aws ecr create-repository --repository-name business-assistant-frontend --region $AWS_REGION
```

### Step 2: Database Provisioning (Amazon RDS PostgreSQL with pgvector)
```bash
# Create RDS PostgreSQL DB instance with pgvector support
aws rds create-db-instance \
    --db-instance-identifier business-assistant-postgres \
    --db-instance-class db.t4g.medium \
    --engine postgres \
    --engine-version 16.2 \
    --allocated-storage 20 \
    --master-username postgres \
    --master-user-password "STRONG_POSTGRES_PASSWORD" \
    --db-name business_assistant \
    --vpc-security-group-ids sg-xxxxxx \
    --backup-retention-period 7 \
    --publicly-accessible false
```

Execute `infra/init.sql` using AWS Cloud9 or an EC2 bastion host to enable `CREATE EXTENSION vector;` and create the `sales_readonly` security role.

### Step 3: PySpark ETL on AWS Glue Serverless
```bash
# Upload PySpark script and raw CSV to Amazon S3
aws s3 cp pipelines/clean_sales.py s3://business-assistant-datalake-$ACCOUNT_ID/scripts/clean_sales.py
aws s3 cp data/BigMart_Sales.csv s3://business-assistant-datalake-$ACCOUNT_ID/raw/BigMart_Sales.csv
aws s3 cp pipelines/jars/postgresql-42.7.3.jar s3://business-assistant-datalake-$ACCOUNT_ID/jars/postgresql-42.7.3.jar

# Create AWS Glue 4.0 Spark job
aws glue create-job \
    --name "business-assistant-sales-cleaning" \
    --role "AWSGlueServiceRole-Default" \
    --command '{"Name":"glueetl","ScriptLocation":"s3://business-assistant-datalake-'$ACCOUNT_ID'/scripts/clean_sales.py","PythonVersion":"3"}' \
    --default-arguments '{"--extra-jars":"s3://business-assistant-datalake-'$ACCOUNT_ID'/jars/postgresql-42.7.3.jar","--job-language":"python"}' \
    --glue-version "4.0" \
    --number-of-workers 2 \
    --worker-type "G.1X"
```

### Step 4: Build, Push, and Deploy Containers to AWS ECS Fargate
```bash
# Authenticate Docker to Amazon ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push Backend image
docker build -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-backend:latest -f infra/Dockerfile.backend .
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-backend:latest

# Build and push Frontend image
docker build -t $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-frontend:latest -f infra/Dockerfile.frontend frontend/
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/business-assistant-frontend:latest

# Create ECS Fargate Cluster
aws ecs create-cluster --cluster-name business-assistant-cluster --region $AWS_REGION
```

Deploy the ECS Task Definitions and Services behind an Application Load Balancer (ALB) with HTTPS termination via AWS Certificate Manager (ACM).
