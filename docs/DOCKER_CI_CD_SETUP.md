# Docker, CI/CD, and AWS Deployment Setup

## Complete Production-Ready Setup Guide

This guide covers containerization, CI/CD pipeline, PostgreSQL, Redis, S3, and AWS deployment for TradingAgents.

---

## 1. Dockerfile

Create `Dockerfile` in project root:

```dockerfile
FROM python:3.14-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[ibkr]"

FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 trading && \
    mkdir -p /app/logs /app/data && \
    chown -R trading:trading /app

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --chown=trading:trading . .

USER trading

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

CMD ["python", "-m", "cli.main"]
```

---

## 2. Docker Compose for Local Development

Create `docker-compose.yml`:

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    container_name: trading-postgres
    environment:
      POSTGRES_DB: ${DB_NAME:-tradingagents}
      POSTGRES_USER: ${DB_USER:-trading}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-trading_password}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-trading}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - trading-network

  redis:
    image: redis:7-alpine
    container_name: trading-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-redis_password}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - trading-network

  localstack:
    image: localstack/localstack:latest
    container_name: trading-localstack
    ports:
      - "4566:4566"
    environment:
      SERVICES: s3,sqs,sns,cloudwatch
      AWS_DEFAULT_REGION: ${AWS_REGION:-us-east-1}
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
    volumes:
      - localstack_data:/tmp/localstack
    networks:
      - trading-network

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: trading-app
    environment:
      DATABASE_URL: postgresql://${DB_USER:-trading}:${DB_PASSWORD:-trading_password}@postgres:5432/${DB_NAME:-tradingagents}
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis_password}@redis:6379/0
      AWS_REGION: ${AWS_REGION:-us-east-1}
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
      AWS_S3_BUCKET: trading-agents-bucket
      TRADINGAGENTS_IBKR_ENABLED: "true"
      TRADINGAGENTS_IBKR_HOST: ${IBKR_HOST:-127.0.0.1}
      TRADINGAGENTS_IBKR_PORT: ${IBKR_PORT:-4002}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
    networks:
      - trading-network

volumes:
  postgres_data:
  redis_data:
  localstack_data:

networks:
  trading-network:
    driver: bridge
```

---

## 3. .dockerignore

Create `.dockerignore`:

```
.git
.github
.gitignore
.dockerignore
.env.local
.env.*.local
.vscode
.idea
*.pyc
__pycache__
*.egg-info
.pytest_cache
.coverage
htmlcov
dist
build
*.log
node_modules
.DS_Store
.env.example
README.md
CHANGELOG.md
TECHNICAL_FLOW.md
IBKR_SETUP_AND_BACKTESTING.md
.editorconfig
Makefile
tests/
docs/
examples/
```

---

## 4. GitHub Actions CI/CD Pipeline

Create `.github/workflows/ci-cd.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: trading-agents
  IMAGE_TAG: ${{ github.sha }}

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.14'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,ibkr]"
      
      - name: Lint with ruff
        run: |
          ruff check .
          ruff format --check .
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/tradingagents_test
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/ -v --cov=tradingagents --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Login to Amazon ECR
        run: |
          aws ecr get-login-password --region ${{ env.AWS_REGION }} | \
          docker login --username AWS --password-stdin ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ env.AWS_REGION }}.amazonaws.com
      
      - name: Build and push Docker image
        run: |
          docker build -t ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ env.AWS_REGION }}.amazonaws.com/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }} .
          docker push ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ env.AWS_REGION }}.amazonaws.com/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }}
      
      - name: Update ECS task definition
        run: |
          aws ecs update-service \
            --cluster trading-agents-cluster \
            --service trading-agents-service \
            --force-new-deployment

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Wait for deployment
        run: |
          aws ecs wait services-stable \
            --cluster trading-agents-cluster \
            --services trading-agents-service
      
      - name: Health check
        run: |
          curl -f http://trading-agents.example.com/health || exit 1
```

---

## 5. Database Models (PostgreSQL)

Create `tradingagents/models/database.py`:

```python
"""Database models for persistence."""

from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class BacktestRun(Base):
    """Backtest execution record."""
    __tablename__ = "backtest_runs"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False)
    strategy_name = Column(String(100), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    initial_capital = Column(Float, nullable=False)
    final_capital = Column(Float, nullable=False)
    total_return = Column(Float, nullable=False)
    sharpe_ratio = Column(Float)
    max_drawdown = Column(Float)
    total_trades = Column(Integer, default=0)
    win_rate = Column(Float)
    parameters = Column(JSON)  # Strategy parameters
    trades = Column(JSON)  # Trade history
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HistoricalData(Base):
    """Cached historical market data."""
    __tablename__ = "historical_data"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class TradeSignal(Base):
    """Generated trade signals."""
    __tablename__ = "trade_signals"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False)
    date = Column(DateTime, nullable=False)
    signal_type = Column(String(20), nullable=False)  # BUY, SELL, HOLD
    price = Column(Float, nullable=False)
    confidence = Column(Float)
    indicators = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class PortfolioPosition(Base):
    """Current portfolio positions."""
    __tablename__ = "portfolio_positions"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False, unique=True)
    shares = Column(Integer, default=0)
    average_cost = Column(Float)
    current_price = Column(Float)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 6. AWS Infrastructure (Terraform)

Create `infrastructure/main.tf`:

```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "trading-agents-terraform"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

# ECR Repository
resource "aws_ecr_repository" "trading_agents" {
  name                 = "trading-agents"
  image_tag_mutability = "IMMUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  encryption_configuration {
    encryption_type = "KMS"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "trading_db" {
  identifier     = "trading-agents-db"
  engine         = "postgres"
  engine_version = "16.1"
  instance_class = var.db_instance_class
  
  db_name  = "tradingagents"
  username = var.db_username
  password = var.db_password
  
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true
  
  multi_az = true
  
  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  
  skip_final_snapshot = false
  final_snapshot_identifier = "trading-agents-db-final-snapshot"
  
  tags = {
    Environment = var.environment
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "trading_redis" {
  cluster_id           = "trading-agents-redis"
  engine               = "redis"
  node_type           = "cache.t3.micro"
  num_cache_nodes     = 1
  parameter_group_name = "default.redis7"
  port                = 6379
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                = var.redis_auth_token
  
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_logs.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
  }
}

# S3 Bucket
resource "aws_s3_bucket" "trading_data" {
  bucket = "trading-agents-${var.environment}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "trading_data" {
  bucket = aws_s3_bucket.trading_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "trading_data" {
  bucket = aws_s3_bucket.trading_data.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "trading_agents" {
  name = "trading-agents-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "redis_logs" {
  name              = "/aws/elasticache/trading-redis"
  retention_in_days = 7
}

data "aws_caller_identity" "current" {}

output "ecr_repository_url" {
  value = aws_ecr_repository.trading_agents.repository_url
}

output "db_endpoint" {
  value = aws_db_instance.trading_db.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.trading_redis.cache_nodes[0].address
}

output "s3_bucket_name" {
  value = aws_s3_bucket.trading_data.id
}
```

---

## 7. Environment Configuration

Create `.env.docker`:

```bash
# Docker Environment
ENVIRONMENT=production
DEBUG=false

# Database
DB_NAME=tradingagents
DB_USER=trading
DB_PASSWORD=secure_password_here
DATABASE_URL=postgresql://trading:secure_password@postgres:5432/tradingagents

# Redis
REDIS_URL=redis://:redis_password@redis:6379/0
REDIS_PASSWORD=redis_password

# AWS
AWS_REGION=us-east-1
AWS_S3_BUCKET=trading-agents-bucket

# IBKR
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_HOST=host.docker.internal
TRADINGAGENTS_IBKR_PORT=4002
TRADINGAGENTS_IBKR_ACCOUNT=DUT094157
TRADINGAGENTS_IBKR_PAPER=true

# Application
LOG_LEVEL=INFO
MAX_WORKERS=4
```

---

## 8. Quick Start

### Local Development

```bash
# Clone and setup
git clone <repo>
cd TradingAgents

# Create .env
cp .env.docker .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Run migrations
docker-compose exec app python -m alembic upgrade head

# Stop services
docker-compose down
```

### AWS Deployment

```bash
# Setup Terraform
cd infrastructure
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker build -t trading-agents:latest .
docker tag trading-agents:latest <account>.dkr.ecr.us-east-1.amazonaws.com/trading-agents:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/trading-agents:latest
```

---

## Key Features

✅ **Multi-stage Docker build** - Optimized image size  
✅ **PostgreSQL persistence** - Backtest results, signals, positions  
✅ **Redis caching** - Fast data retrieval  
✅ **S3 object storage** - Historical data, reports  
✅ **CI/CD automation** - GitHub Actions pipeline  
✅ **AWS infrastructure** - Terraform IaC  
✅ **Health checks** - Service monitoring  
✅ **Logging** - CloudWatch integration  
✅ **Security** - Non-root user, encryption  

---

## Files to Create

1. `Dockerfile` - Container image
2. `docker-compose.yml` - Local development stack
3. `.dockerignore` - Docker build optimization
4. `.github/workflows/ci-cd.yml` - CI/CD pipeline
5. `tradingagents/models/database.py` - ORM models
6. `infrastructure/main.tf` - AWS infrastructure
7. `infrastructure/variables.tf` - Terraform variables
8. `.env.docker` - Environment configuration

---

**Status**: Ready for implementation ✅
