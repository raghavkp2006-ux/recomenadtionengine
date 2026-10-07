<#
.SYNOPSIS
    PolyTaste AWS Infrastructure Setup Script (PowerShell)
    Region: ap-south-1 (Mumbai)
#>

$ErrorActionPreference = "Stop"
$AwsRegion = if ($env:AWS_REGION) { $env:AWS_REGION } else { "ap-south-1" }

Write-Host "Fetching AWS Account Identity..."
$AwsAccountId = (aws sts get-caller-identity --query Account --output text).Trim()
$EcrRepoName = "recommendation-api"
$ClusterName = "recommendation-cluster"
$FrontendBucketName = "polytaste-frontend-$AwsAccountId"
$LogGroup = "/ecs/recommendation-api"

Write-Host "=== PolyTaste AWS Setup ===" -ForegroundColor Cyan
Write-Host "AWS Account ID: $AwsAccountId"
Write-Host "Region:         $AwsRegion"

# 1. ECR
Write-Host "[1/6] Creating ECR Repository..."
try {
    aws ecr create-repository --repository-name $EcrRepoName --region $AwsRegion --image-scanning-configuration scanOnPush=true
} catch {
    Write-Host "ECR repository may already exist." -ForegroundColor Yellow
}

# 2. CloudWatch Logs
Write-Host "[2/6] Creating CloudWatch Log Group..."
try {
    aws logs create-log-group --log-group-name $LogGroup --region $AwsRegion
} catch {
    Write-Host "Log group may already exist." -ForegroundColor Yellow
}

# 3. S3 Frontend
Write-Host "[3/6] Creating Frontend S3 Bucket..."
try {
    aws s3api create-bucket --bucket $FrontendBucketName --region $AwsRegion --create-bucket-configuration LocationConstraint=$AwsRegion
    aws s3api put-public-access-block --bucket $FrontendBucketName --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
} catch {
    Write-Host "S3 bucket may already exist." -ForegroundColor Yellow
}

# 4. ECS Cluster
Write-Host "[4/6] Creating ECS Cluster..."
try {
    aws ecs create-cluster --cluster-name $ClusterName --region $AwsRegion
} catch {
    Write-Host "ECS cluster may already exist." -ForegroundColor Yellow
}

# 5. Secrets Manager
Write-Host "[5/6] Creating Secrets Manager template..."
try {
    aws secretsmanager create-secret --name "recommendation-api/secrets" --region $AwsRegion --secret-string '{"DATABASE_URL":"","SESSION_SECRET_KEY":"","GOOGLE_CLIENT_ID":"","GOOGLE_CLIENT_SECRET":"","SPOTIFY_CLIENT_ID":"","SPOTIFY_CLIENT_SECRET":"","ANILIST_CLIENT_ID":"","ANILIST_CLIENT_SECRET":"","TMDB_API_KEY":"","YOUTUBE_API_KEY":""}'
} catch {
    Write-Host "Secret template may already exist." -ForegroundColor Yellow
}

Write-Host "[6/6] Build and Push Commands:" -ForegroundColor Green
Write-Host "aws ecr get-login-password --region $AwsRegion | docker login --username AWS --password-stdin $AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com"
Write-Host "docker tag recommendation-api:latest $AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/${EcrRepoName}:latest"
Write-Host "docker push $AwsAccountId.dkr.ecr.$AwsRegion.amazonaws.com/${EcrRepoName}:latest"
