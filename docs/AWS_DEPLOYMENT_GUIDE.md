# PolyTaste - Production AWS Deployment Guide

This guide details the step-by-step production deployment of the **PolyTaste Multi-Module Recommendation Engine** on Amazon Web Services (AWS) in the **ap-south-1 (Mumbai)** region.

---

## 1. Architecture Overview

```mermaid
graph TD
    Client[Browser / Mobile / Extension] -->|HTTPS| CF[Amazon CloudFront]
    Client -->|API Requests: https://api.domain.com| ALB[Application Load Balancer]
    
    CF -->|Static Assets| S3[S3 Bucket: polytaste-frontend]
    ALB -->|Target Group :8080 /health| ECS[ECS Fargate: recommendation-api]
    
    ECS -->|SQLAlchemy| RDS[(Amazon RDS PostgreSQL)]
    ECS -->|Pulls secrets| SM[AWS Secrets Manager]
    ECS -->|Logs stdout/stderr| CW[Amazon CloudWatch Logs]
```

### Infrastructure Components

| Component | AWS Service | Sizing / Configuration |
| :--- | :--- | :--- |
| **Frontend** | Amazon S3 + CloudFront | S3 private bucket, CloudFront OAC, SSL (ACM), SPA redirect (403/404 → `/index.html`) |
| **Backend API** | Amazon ECS (AWS Fargate) | 0.5 vCPU, 1 GB RAM, Container Port: `8080`, Health check: `/health` |
| **Load Balancer** | Application Load Balancer (ALB) | Public-facing ALB, HTTPS listener (ACM cert) forwarding to Target Group on port 8080 |
| **Database** | Amazon RDS PostgreSQL | PostgreSQL 16, `db.t4g.micro` or `db.t4g.small` (Multi-AZ optional for prod) |
| **Secrets & Config**| AWS Secrets Manager | `recommendation-api/secrets` storing DB credentials, OAuth secrets, session key |
| **Container Registry**| Amazon ECR | Private repository: `recommendation-api` |
| **Logging** | Amazon CloudWatch Logs | Log group: `/ecs/recommendation-api` (Retention: 30 days) |
| **CI/CD** | GitHub Actions (OIDC) | Keyless authentication to AWS via IAM Role with OpenID Connect |

---

## 2. Critical Operational Constraint: Scheduler Scalability

> [!WARNING]
> **INITIAL DEPLOYMENT TASK COUNT MUST BE 1 (`desiredCount: 1`).**
> 
> The application lifespan (`main.py`) initializes the Spotify background APScheduler on process startup:
> ```python
> @asynccontextmanager
> async def lifespan(app: FastAPI):
>     tables = init_db()
>     start_scheduler()
>     yield
>     stop_scheduler()
> ```
> If ECS task count is scaled horizontally (> 1 replicas), **every API replica would execute its own scheduler**, causing redundant database polling, Spotify rate limits, and concurrent sync collisions.
>
> **Long-term Roadmap for Horizontal Scaling:**
> Before enabling ECS autoscaling:
> 1. Separate the scheduler worker from `main.py` into a standalone worker container or an AWS EventBridge scheduled rule triggering an ECS Task / Lambda.
> 2. Gate the scheduler in `main.py` behind an environment variable (e.g. `ENABLE_BACKGROUND_SCHEDULER=true`).

---

## 3. Production Environment Variables & Secrets

Store sensitive variables in **AWS Secrets Manager** (`recommendation-api/secrets`):

| Variable | Description | Example / Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/polytaste` |
| `SESSION_SECRET_KEY` | Signed cookie encryption key | 64-char random string (e.g. `openssl rand -hex 32`) |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | `...apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | Secret from Google Cloud Console |
| `SPOTIFY_CLIENT_ID` | Spotify App Client ID | Client ID from Spotify Dev Dashboard |
| `SPOTIFY_CLIENT_SECRET` | Spotify App Client Secret | Client Secret from Spotify Dev Dashboard |
| `ANILIST_CLIENT_ID` | AniList OAuth Client ID | Numeric ID from AniList Developer Settings |
| `ANILIST_CLIENT_SECRET` | AniList OAuth Client Secret | Secret from AniList Developer Settings |
| `TMDB_API_KEY` | TMDB API v3 Key | TMDB Developer API Key |
| `YOUTUBE_API_KEY` | YouTube Data API v3 Key | Google Cloud YouTube API Key |

Set non-sensitive variables directly in the **ECS Task Definition** (`deploy/aws/task-definition.json`):

| Variable | Value | Notes |
| :--- | :--- | :--- |
| `ENV` | `production` | Enforces HTTPS session cookies and secure secrets |
| `PORT` | `8080` | Internal container listening port |
| `FRONTEND_URL` | `https://your-frontend-domain.com` | Origin for CORS and OAuth frontend redirects |
| `ALLOWED_ORIGINS` | `https://your-frontend-domain.com` | Comma-separated CORS allowed origins |
| `GOOGLE_REDIRECT_URI` | `https://api.your-domain.com/auth/google/callback` | **Must match backend route `/auth/google/callback`** |
| `SPOTIFY_REDIRECT_URI` | `https://api.your-domain.com/spotify/callback` | **Must match backend route `/spotify/callback`** |
| `ANILIST_REDIRECT_URI` | `https://api.your-domain.com/anilist/callback` | **Must match backend route `/anilist/callback`** |

---

## 4. ALB Health Check Configuration

Configure the ALB Target Group:
- **Protocol:** HTTP
- **Port:** 8080
- **Health check path:** `/health`
- **Success codes:** `200`
- **Healthy threshold:** 2
- **Unhealthy threshold:** 3
- **Interval:** 30 seconds
- **Timeout:** 5 seconds

The `/health` endpoint executes a lightweight verification without running heavy scikit-learn models or external third-party API calls.

---

## 5. Step-by-Step Deployment Instructions

### Step 1: Pre-flight Verification
Ensure the following tools are installed locally:
- AWS CLI (`aws --version`)
- Docker Desktop (`docker --version`)

Verify AWS authentication:
```bash
aws sts get-caller-identity
```

### Step 2: Initialize Infrastructure (One-time)
Run the automated setup script to provision ECR, S3, CloudWatch Logs, and Secrets Manager:
- **On Linux/macOS:**
  ```bash
  chmod +x deploy/aws/setup-aws-infrastructure.sh
  ./deploy/aws/setup-aws-infrastructure.sh
  ```
- **On Windows PowerShell:**
  ```powershell
  .\deploy\aws\setup-aws-infrastructure.ps1
  ```

### Step 3: Populate Secrets
Update the secret values in AWS Secrets Manager:
```bash
aws secretsmanager put-secret-value \
  --secret-id "recommendation-api/secrets" \
  --secret-string file://my-secrets.json \
  --region ap-south-1
```

### Step 4: Provision RDS PostgreSQL Database
Create an Amazon RDS PostgreSQL instance:
```bash
aws rds create-db-instance \
  --db-instance-identifier "recommendation-db" \
  --db-instance-class "db.t4g.micro" \
  --engine "postgres" \
  --engine-version "16.1" \
  --master-username "app_user" \
  --master-user-password "<ChooseStrongPassword>" \
  --allocated-storage 20 \
  --vpc-security-group-ids "<RDS_SECURITY_GROUP_ID>" \
  --db-name "polytaste" \
  --region ap-south-1
```

### Step 5: Build and Push Backend Docker Image
```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com

docker build -t recommendation-api .
docker tag recommendation-api:latest ${AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/recommendation-api:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.ap-south-1.amazonaws.com/recommendation-api:latest
```

### Step 6: Deploy Frontend to S3 + CloudFront
```bash
cd frontend
npm ci
VITE_API_BASE=https://api.your-domain.com npm run build
aws s3 sync dist/ s3://polytaste-frontend-${AWS_ACCOUNT_ID} --delete
aws cloudfront create-invalidation --distribution-id <DISTRIBUTION_ID> --paths "/*"
```

---

## 6. GitHub Actions CI/CD Setup

To enable automated deployment on Git push via GitHub OIDC:
1. In AWS IAM, configure an Identity Provider for `token.actions.githubusercontent.com`.
2. Create an IAM Role `GitHubActionsDeployRole` with trust policy allowing `repo:raghavkp2006-ux/recomenadtionengine:*`.
3. Add the following repository secrets in GitHub:
   - `AWS_ROLE_TO_ASSUME`: `arn:aws:iam::<ACCOUNT_ID>:role/GitHubActionsDeployRole`
   - `VITE_API_BASE`: `https://api.your-domain.com`
   - `S3_FRONTEND_BUCKET`: `polytaste-frontend-<ACCOUNT_ID>`
   - `CLOUDFRONT_DISTRIBUTION_ID`: `<DISTRIBUTION_ID>`
4. Pushing to `main` will automatically test, build, push Docker image to ECR, update ECS, build frontend, and sync to S3.
