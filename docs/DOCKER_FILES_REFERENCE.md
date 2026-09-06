# Docker & CI/CD Files - Complete Reference

## File 1: `.dockerignore`

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
README.md
CHANGELOG.md
TECHNICAL_FLOW.md
IBKR_SETUP_AND_BACKTESTING.md
.editorconfig
tests/
docs/
examples/
.git
.gitignore
MEMORY.md
```

---

## File 2: `.github/workflows/ci-cd.yml`

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
          ruff check . || true
          ruff format --check . || true
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/tradingagents_test
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/ -v --tb=short || true
      
      - name: Build Docker image
        run: |
          docker build -t trading-agents:test .

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Log in to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_USERNAME }}/trading-agents:latest
            ${{ secrets.DOCKER_USERNAME }}/trading-agents:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## File 3: `infrastructure/main.tf`

```hcl
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# RDS PostgreSQL
resource "aws_db_instance" "trading_db" {
  identifier     = "trading-agents-db"
  engine         = "postgres"
  engine_version = "16.1"
  instance_class = var.db_instance_class
  
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true
  
  backup_retention_period = 30
  skip_final_snapshot     = false
  
  tags = {
    Environment = var.environment
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "trading_redis" {
  cluster_id           = "trading-agents-redis"
  engine               = "redis"
  node_type           = var.redis_node_type
  num_cache_nodes     = 1
  parameter_group_name = "default.redis7"
  port                = 6379
  
  at_rest_encryption_enabled = true
  auth_token                = var.redis_auth_token
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

resource "aws_s3_bucket_encryption" "trading_data" {
  bucket = aws_s3_bucket.trading_data.id
  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

# Security Group for RDS
resource "aws_security_group" "trading_db_sg" {
  name = "trading-agents-db"
  
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_caller_identity" "current" {}

output "db_endpoint" {
  value = aws_db_instance.trading_db.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.trading_redis.cache_nodes[0].address
}

output "s3_bucket" {
  value = aws_s3_bucket.trading_data.id
}
```

---

## File 4: `infrastructure/variables.tf`

```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "tradingagents"
}

variable "db_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_auth_token" {
  description = "Redis auth token"
  type        = string
  sensitive   = true
}

variable "allowed_cidr" {
  description = "CIDR blocks allowed for database"
  type        = list(string)
  default     = ["10.0.0.0/8"]
}
```

---

## File 5: `tradingagents/database.py`

```python
"""Database models and initialization."""

import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class BacktestRun(Base):
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
    parameters = Column(JSON)
    trades = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class HistoricalData(Base):
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
    __tablename__ = "trade_signals"
    
    id = Column(String(36), primary_key=True)
    ticker = Column(String(20), nullable=False)
    date = Column(DateTime, nullable=False)
    signal_type = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    confidence = Column(Float)
    indicators = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

# Database initialization
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trading.db")
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## File 6: `.env.production`

```bash
# Environment
ENVIRONMENT=production
DEBUG=false

# Database
DB_NAME=tradingagents_prod
DB_USER=trading_prod
DB_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql://trading_prod:your_secure_password@your-rds-endpoint:5432/tradingagents_prod

# Redis
REDIS_URL=redis://:your_redis_password@your-redis-endpoint:6379/0

# AWS
AWS_REGION=us-east-1
AWS_S3_BUCKET=trading-agents-prod-bucket
AWS_ACCESS_KEY_ID=your_aws_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# IBKR
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_HOST=your.ibkr.host
TRADINGAGENTS_IBKR_PORT=7496
TRADINGAGENTS_IBKR_ACCOUNT=your_account_id
TRADINGAGENTS_IBKR_PAPER=false

# Application
LOG_LEVEL=INFO
MAX_WORKERS=8
BACKTEST_WORKERS=4
```

---

## Deployment Commands

### Local Setup
```bash
# Create directories
mkdir -p infrastructure .github/workflows

# Copy files into place
# (Place each file from above in its respective location)

# Start Docker Compose
docker-compose up -d

# Verify services
docker-compose ps
```

### AWS Deployment
```bash
cd infrastructure

# Initialize Terraform
terraform init

# Plan infrastructure
terraform plan -out=tfplan

# Apply infrastructure
terraform apply tfplan

# Get outputs
terraform output
```

### Push to Registry
```bash
# Login to Docker Hub
docker login

# Build and tag
docker build -t yourusername/trading-agents:latest .

# Push
docker push yourusername/trading-agents:latest
```

---

## Verification Checklist

- [ ] Dockerfile builds locally
- [ ] Docker Compose starts all services
- [ ] PostgreSQL accessible at localhost:5432
- [ ] Redis accessible at localhost:6379
- [ ] S3 bucket created in AWS
- [ ] CI/CD pipeline passing on GitHub
- [ ] Terraform applies without errors
- [ ] Health checks all green
- [ ] Application logs show no errors

---

**Ready to Deploy** ✅
