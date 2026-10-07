#!/usr/bin/env bash
# ==============================================================================
# PolyTaste Recommendation App - AWS Infrastructure Setup Script
# Region: ap-south-1 (Mumbai)
#
# NOTE: This script provisions AWS resources. Ensure appropriate permissions
# and confirm budget before execution.
# ==============================================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME="recommendation-api"
CLUSTER_NAME="recommendation-cluster"
SERVICE_NAME="recommendation-api-service"
FRONTEND_BUCKET_NAME="polytaste-frontend-${AWS_ACCOUNT_ID}"
LOG_GROUP="/ecs/recommendation-api"

echo "=== PolyTaste AWS Setup ==="
echo "AWS Account ID: ${AWS_ACCOUNT_ID}"
echo "Region:         ${AWS_REGION}"

# 1. ECR Repository
echo "[1/7] Creating ECR Repository..."
aws ecr create-repository \
  --repository-name "${ECR_REPO_NAME}" \
  --region "${AWS_REGION}" \
  --image-scanning-configuration scanOnPush=true || true

# 2. CloudWatch Log Group
echo "[2/7] Creating CloudWatch Log Group..."
aws logs create-log-group \
  --log-group-name "${LOG_GROUP}" \
  --region "${AWS_REGION}" || true

# 3. S3 Bucket for Frontend
echo "[3/7] Creating Frontend S3 Bucket..."
aws s3api create-bucket \
  --bucket "${FRONTEND_BUCKET_NAME}" \
  --region "${AWS_REGION}" \
  --create-bucket-configuration LocationConstraint="${AWS_REGION}" || true

# Block Public Access on S3 (CloudFront OAC will access it)
aws s3api put-public-access-block \
  --bucket "${FRONTEND_BUCKET_NAME}" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 4. ECS Cluster
echo "[4/7] Creating ECS Cluster..."
aws ecs create-cluster \
  --cluster-name "${CLUSTER_NAME}" \
  --region "${AWS_REGION}"

# 5. Secrets Manager Placeholder
echo "[5/7] Creating Secrets Manager template..."
aws secretsmanager create-secret \
  --name "recommendation-api/secrets" \
  --description "PolyTaste Production Secrets" \
  --region "${AWS_REGION}" \
  --secret-string '{"DATABASE_URL":"","SESSION_SECRET_KEY":"","GOOGLE_CLIENT_ID":"","GOOGLE_CLIENT_SECRET":"","SPOTIFY_CLIENT_ID":"","SPOTIFY_CLIENT_SECRET":"","ANILIST_CLIENT_ID":"","ANILIST_CLIENT_SECRET":"","TMDB_API_KEY":"","YOUTUBE_API_KEY":""}' || true

# 6. ECR Login and Push Helper
echo "[6/7] ECR Login & Build instructions:"
echo "aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
echo "docker tag recommendation-api:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"
echo "docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

echo "=== AWS Setup Script Complete ==="
