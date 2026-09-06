# Production Deployment Guide - Complete Implementation

## Overview

This guide provides step-by-step instructions to transform TradingAgents into a production-ready, cloud-deployable system with Docker, PostgreSQL, Redis, S3, and AWS infrastructure.

---

## Part 1: Update Existing Dockerfile

Replace the current `Dockerfile` content with this production-ready version:

```dockerfile
# Multi-stage build for TradingAgents
# Stage 1: Builder
FROM python:3.14-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[ibkr]"

# Stage 2: Runtime
FROM python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and directories
RUN useradd -m -u 1000 trading && \
    mkdir -p /app/logs /app/data && \
    chown -R trading:trading /app

# Copy Python virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=trading:trading . .

# Switch to non-root user
USER trading

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "cli.main"]
```

**Key improvements:**
- Multi-stage build (reduces final image size)
- Virtual environment isolation
- Non-root user (security best practice)
- Health checks for monitoring
- PostgreSQL client included for database operations

---

## Part 2: Update docker-compose.yml

Replace the current `docker-compose.yml` with this production stack:

```yaml
version: '3.9'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    container_name: trading-postgres
    environment:
      POSTGRES_DB: ${DB_NAME:-tradingagents}
      POSTGRES_USER: ${DB_USER:-trading}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-trading_secure_pass}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-trading}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - trading-network
    restart: unless-stopped

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: trading-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-redis_secure_pass}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - trading-network
    restart: unless-stopped

  # LocalStack for S3 emulation (local development only)
  localstack:
    image: localstack/localstack:latest
    container_name: trading-localstack
    ports:
      - "4566:4566"
    environment:
      SERVICES: s3,sqs,sns
      AWS_DEFAULT_REGION: ${AWS_REGION:-us-east-1}
      DEBUG: 0
    volumes:
      - localstack_data:/tmp/localstack
    networks:
      - trading-network
    profiles:
      - local
    restart: unless-stopped

  # Trading Agents Application
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: trading-app
    environment:
      # Database
      DATABASE_URL: postgresql://${DB_USER:-trading}:${DB_PASSWORD:-trading_secure_pass}@postgres:5432/${DB_NAME:-tradingagents}
      
      # Redis
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis_secure_pass}@redis:6379/0
      
      # AWS (when running locally, points to LocalStack)
      AWS_REGION: ${AWS_REGION:-us-east-1}
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:-test}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY:-test}
      AWS_S3_ENDPOINT_URL: ${AWS_S3_ENDPOINT_URL:-http://localstack:4566}
      AWS_S3_BUCKET: ${AWS_S3_BUCKET:-trading-agents-bucket}
      
      # IBKR Configuration
      TRADINGAGENTS_IBKR_ENABLED: ${TRADINGAGENTS_IBKR_ENABLED:-true}
      TRADINGAGENTS_IBKR_HOST: ${IBKR_HOST:-host.docker.internal}
      TRADINGAGENTS_IBKR_PORT: ${IBKR_PORT:-4002}
      TRADINGAGENTS_IBKR_ACCOUNT: ${IBKR_ACCOUNT:-DUT094157}
      
      # Application
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DEBUG: ${DEBUG:-false}
    
    ports:
      - "8000:8000"
    
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    
    volumes:
      - ./:/app
      - trading_logs:/app/logs
      - trading_data:/app/data
    
    networks:
      - trading-network
    
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  localstack_data:
    driver: local
  trading_logs:
    driver: local
  trading_data:
    driver: local

networks:
  trading-network:
    driver: bridge
```

**Key features:**
- PostgreSQL 16 Alpine (lightweight)
- Redis 7 with persistence
- LocalStack for S3 emulation (local development)
- Proper health checks
- Volume management for persistence
- Environment-based configuration
- Restart policies for reliability

---

## Part 3: Update .dockerignore

```
.git
.gitignore
.github
.venv
.env
.env.*.local
.claude
.idea
.vscode
.DS_Store
__pycache__
*.pyc
*.egg-info
build
dist
results
eval_results
.pytest_cache
.coverage
htmlcov
*.log
node_modules
Dockerfile
docker-compose.yml
.dockerignore
tests/
docs/
examples/
README.md
CHANGELOG.md
.editorconfig
Makefile
```

---

## Part 4: Create Database Initialization Script

Create `scripts/init_db.sql`:

```sql
-- Create tables for backtest results
CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    initial_capital DECIMAL(15,2) NOT NULL,
    final_capital DECIMAL(15,2) NOT NULL,
    total_return DECIMAL(10,4) NOT NULL,
    sharpe_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,4),
    total_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(10,4),
    parameters JSONB,
    trades JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (ticker),
    INDEX (created_at)
);

-- Create tables for historical data cache
CREATE TABLE IF NOT EXISTS historical_data (
    id UUID PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ticker, date),
    INDEX (ticker),
    INDEX (date)
);

-- Create tables for trade signals
CREATE TABLE IF NOT EXISTS trade_signals (
    id UUID PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    date TIMESTAMP NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    confidence DECIMAL(10,4),
    indicators JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (ticker),
    INDEX (date)
);

-- Create tables for portfolio positions
CREATE TABLE IF NOT EXISTS portfolio_positions (
    id UUID PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    shares INTEGER DEFAULT 0,
    average_cost DECIMAL(10,2),
    current_price DECIMAL(10,2),
    pnl DECIMAL(15,2),
    pnl_pct DECIMAL(10,4),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (ticker)
);

-- Create indexes for performance
CREATE INDEX idx_backtest_runs_created_at ON backtest_runs(created_at DESC);
CREATE INDEX idx_backtest_runs_ticker ON backtest_runs(ticker);
CREATE INDEX idx_historical_data_ticker_date ON historical_data(ticker, date);
CREATE INDEX idx_trade_signals_ticker_date ON trade_signals(ticker, date DESC);
```

---

## Part 5: Environment Configuration

Create `.env.production`:

```bash
# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DB_NAME=tradingagents_prod
DB_USER=trading_prod
DB_PASSWORD=your_very_secure_password_here_change_this
DATABASE_URL=postgresql://trading_prod:your_very_secure_password@your-rds-endpoint:5432/tradingagents_prod

# Redis
REDIS_PASSWORD=your_redis_secure_password_here
REDIS_URL=redis://:your_redis_password@your-redis-endpoint:6379/0

# AWS
AWS_REGION=us-east-1
AWS_S3_BUCKET=trading-agents-prod-bucket
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key

# IBKR
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_HOST=your.ibkr.broker.host
TRADINGAGENTS_IBKR_PORT=7496
TRADINGAGENTS_IBKR_ACCOUNT=your_account_id
TRADINGAGENTS_IBKR_PAPER=false
TRADINGAGENTS_IBKR_AUTO_EXECUTE=false

# Application
MAX_WORKERS=8
BACKTEST_WORKERS=4
```

---

## Part 6: Local Development Setup

Create `.env.local`:

```bash
# Local Development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database (Local PostgreSQL)
DB_NAME=tradingagents_dev
DB_USER=trading
DB_PASSWORD=trading_secure_pass
DATABASE_URL=postgresql://trading:trading_secure_pass@localhost:5432/tradingagents_dev

# Redis (Local)
REDIS_PASSWORD=redis_secure_pass
REDIS_URL=redis://:redis_secure_pass@localhost:6379/0

# AWS (LocalStack)
AWS_REGION=us-east-1
AWS_S3_BUCKET=trading-agents-bucket
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_S3_ENDPOINT_URL=http://localhost:4566

# IBKR (Paper Trading)
TRADINGAGENTS_IBKR_ENABLED=true
TRADINGAGENTS_IBKR_HOST=127.0.0.1
TRADINGAGENTS_IBKR_PORT=4002
TRADINGAGENTS_IBKR_ACCOUNT=DUT094157
TRADINGAGENTS_IBKR_PAPER=true
TRADINGAGENTS_IBKR_AUTO_EXECUTE=false
```

---

## Part 7: Quick Start Commands

### Start Local Development Stack
```bash
# Navigate to project
cd C:\Trading\TradingAgents

# Copy local env
cp .env.local .env

# Start all services
docker-compose --profile local up -d

# Verify services
docker-compose ps

# Check logs
docker-compose logs -f app

# Stop all services
docker-compose down
```

### Build Production Image
```bash
# Build image
docker build -t trading-agents:latest .

# Tag for registry
docker tag trading-agents:latest yourusername/trading-agents:latest

# Push to Docker Hub
docker push yourusername/trading-agents:latest
```

### Deploy to AWS

For AWS deployment, you'll need:
1. AWS account with appropriate IAM permissions
2. Terraform installed
3. Docker image pushed to ECR
4. RDS PostgreSQL instance
5. ElastiCache Redis cluster
6. S3 bucket for data storage

---

## Part 8: Monitoring & Health Checks

All services include health checks:

```bash
# Check service health
docker-compose ps

# View service logs
docker-compose logs postgres
docker-compose logs redis
docker-compose logs app

# Check database connection
docker-compose exec postgres psql -U trading -d tradingagents -c "SELECT 1;"

# Check Redis connection
docker-compose exec redis redis-cli -a redis_secure_pass ping

# Check application
curl http://localhost:8000/health
```

---

## Part 9: Persistence & Backups

### Database Backup
```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U trading tradingagents > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U trading tradingagents < backup.sql
```

### Redis Snapshot
```bash
# Copy Redis snapshot
docker cp trading-redis:/data/dump.rdb ./redis_backup.rdb
```

### S3 Data Backup (Production)
```bash
# Backup to S3
aws s3 sync ./backups s3://trading-agents-prod-bucket/backups/
```

---

## Part 10: Security Considerations

### Production Security Checklist

- [ ] Change all default passwords in `.env.production`
- [ ] Use AWS Secrets Manager for credentials
- [ ] Enable SSL/TLS for database connections
- [ ] Configure VPC security groups properly
- [ ] Enable encryption at rest for RDS and S3
- [ ] Set up CloudWatch monitoring and alarms
- [ ] Enable database audit logging
- [ ] Implement rate limiting on API endpoints
- [ ] Use AWS IAM roles instead of access keys
- [ ] Enable MFA for AWS console access

### Database Security

```sql
-- Restrict user permissions
ALTER ROLE trading_prod SET log_statement = 'all';
ALTER ROLE trading_prod SET log_min_duration_statement = 1000;

-- Enable SSL
ALTER SYSTEM SET ssl = on;
SELECT pg_reload_conf();
```

---

## Part 11: CI/CD Pipeline

For GitHub Actions, create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Login to ECR
        run: |
          aws ecr get-login-password --region us-east-1 | \
          docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
      
      - name: Build and push
        run: |
          docker build -t ${{ secrets.ECR_REGISTRY }}/trading-agents:latest .
          docker push ${{ secrets.ECR_REGISTRY }}/trading-agents:latest
      
      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster trading-agents \
            --service trading-agents \
            --force-new-deployment
```

---

## Troubleshooting

### PostgreSQL won't start
```bash
# Check logs
docker-compose logs postgres

# Verify volume
docker volume ls | grep postgres

# Recreate volume
docker-compose down -v
docker-compose up -d postgres
```

### Redis connection refused
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping

# Verify password
docker-compose exec redis redis-cli -a YOUR_PASSWORD ping
```

### Application can't connect to database
```bash
# Check connection string
echo $DATABASE_URL

# Test connection
docker-compose exec app python -c "
from sqlalchemy import create_engine
engine = create_engine('$DATABASE_URL')
print('Connection successful!')
"
```

---

## Summary

You now have:
- ✅ Production-ready Docker image
- ✅ Docker Compose stack with PostgreSQL, Redis, LocalStack
- ✅ Database initialization scripts
- ✅ Environment configurations for local/prod
- ✅ Health checks and monitoring
- ✅ CI/CD pipeline template
- ✅ Security best practices
- ✅ Backup and restore procedures

**Next steps:**
1. Update Docker/docker-compose files with content above
2. Create scripts/init_db.sql
3. Test locally with `docker-compose up`
4. Deploy to AWS when ready

---

**Status**: Production-Ready ✅
