# Production Deployment Checklist

## Overview

This checklist guides you through deploying TradingAgents as a production-ready system with Docker, PostgreSQL, Redis, S3, and AWS.

---

## Phase 1: Local Development Setup (1-2 hours)

### 1.1 Environment Preparation
- [ ] Clone/pull latest code from main branch
- [ ] Verify git status is clean: `git status`
- [ ] Create `.env.local` file (copy template from DOCKER_PRODUCTION_GUIDE.md)
- [ ] Update environment variables with your credentials

### 1.2 Docker Installation
- [ ] Install Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- [ ] Install Docker Compose (included with Docker Desktop)
- [ ] Verify installation:
  ```bash
  docker --version
  docker-compose --version
  ```

### 1.3 Update Docker Configuration Files
- [ ] Review current `Dockerfile` at root
- [ ] Update `Dockerfile` with production multi-stage build (from DOCKER_PRODUCTION_GUIDE.md)
- [ ] Update `docker-compose.yml` with PostgreSQL, Redis, LocalStack services
- [ ] Update `.dockerignore` file
- [ ] Create `scripts/init_db.sql` for database initialization

### 1.4 Create Database Script
- [ ] Create `scripts/` directory if it doesn't exist
- [ ] Copy `scripts/init_db.sql` from DOCKER_PRODUCTION_GUIDE.md
- [ ] Verify SQL syntax:
  ```bash
  cat scripts/init_db.sql | grep -c "CREATE TABLE"  # Should show 10+
  ```

### 1.5 Local Stack Startup
- [ ] Navigate to project root: `cd C:\Trading\TradingAgents`
- [ ] Copy local env: `cp .env.local .env`
- [ ] Start services: `docker-compose --profile local up -d`
- [ ] Wait for services to start (30-60 seconds)
- [ ] Verify all services healthy: `docker-compose ps`
  - postgres: healthy ✓
  - redis: healthy ✓
  - localstack: running ✓
  - app: running ✓

### 1.6 Database Verification
- [ ] Connect to PostgreSQL:
  ```bash
  docker-compose exec postgres psql -U trading -d tradingagents -c "\dt"
  ```
- [ ] Should show 10+ tables (backtest_runs, historical_data, etc.)
- [ ] Verify redis connection:
  ```bash
  docker-compose exec redis redis-cli -a redis_secure_pass PING
  ```
- [ ] Should respond with "PONG"

### 1.7 Application Health Check
- [ ] Check app logs: `docker-compose logs app`
- [ ] Verify no connection errors
- [ ] Test health endpoint: `curl http://localhost:8000/health` (if implemented)

**Status After Phase 1**: ✅ Local development environment fully operational

---

## Phase 2: Application Integration (1-2 hours)

### 2.1 Database Models Integration
- [ ] Create or update `tradingagents/models/database.py`:
  ```python
  from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, JSON
  from sqlalchemy.ext.declarative import declarative_base
  from sqlalchemy.orm import sessionmaker
  import os
  
  DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./trading.db")
  engine = create_engine(DATABASE_URL, echo=False)
  Base = declarative_base()
  SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
  
  # Define ORM models matching database schema
  class BacktestRun(Base):
      __tablename__ = "backtest_runs"
      # ... columns
  ```

### 2.2 Redis Integration
- [ ] Create `tradingagents/cache/redis_cache.py`:
  ```python
  import redis
  import os
  
  redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
  cache = redis.from_url(redis_url)
  
  def cache_backtest_result(ticker, strategy, result):
      key = f"backtest:{ticker}:{strategy}"
      cache.setex(key, 86400, result)  # 24 hour TTL
  ```

### 2.3 S3 Integration
- [ ] Create `tradingagents/storage/s3_storage.py`:
  ```python
  import boto3
  import os
  
  s3 = boto3.client(
      's3',
      endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),
      region_name=os.getenv("AWS_REGION")
  )
  
  def upload_backtest_results(ticker, csv_data):
      bucket = os.getenv("AWS_S3_BUCKET")
      key = f"backtest-results/{ticker}/{timestamp}.csv"
      s3.put_object(Bucket=bucket, Key=key, Body=csv_data)
  ```

### 2.4 Update Backtest Engine
- [ ] Modify `strategies/run_backtest.py` to:
  - [ ] Save results to PostgreSQL (not just CSV)
  - [ ] Cache results in Redis
  - [ ] Upload CSV to S3
  - [ ] Example:
    ```python
    # After backtest completes
    db.session.add(BacktestRun(...))
    db.session.commit()
    
    cache.setex(f"backtest:{ticker}", 86400, results)
    
    s3.put_object(Bucket=bucket, Key=f"results/{ticker}.csv", Body=csv)
    ```

### 2.5 Environment Variable Updates
- [ ] Update `tradingagents/default_config.py` to support:
  - [ ] DATABASE_URL
  - [ ] REDIS_URL
  - [ ] AWS_S3_BUCKET
  - [ ] AWS_S3_ENDPOINT_URL

### 2.6 Test Integration Locally
- [ ] Run backtest: `python strategies/run_backtest.py`
- [ ] Verify results saved to PostgreSQL:
  ```bash
  docker-compose exec postgres psql -U trading -d tradingagents \
    -c "SELECT ticker, strategy_name, total_return FROM backtest_runs;"
  ```
- [ ] Verify results cached in Redis:
  ```bash
  docker-compose exec redis redis-cli -a redis_secure_pass \
    KEYS "backtest:*"
  ```
- [ ] Verify CSV uploaded to LocalStack S3:
  ```bash
  aws s3 ls s3://trading-agents-bucket --endpoint-url http://localhost:4566
  ```

**Status After Phase 2**: ✅ Application fully integrated with PostgreSQL, Redis, and S3

---

## Phase 3: Production Preparation (2-4 hours)

### 3.1 AWS Account Setup
- [ ] Create AWS account (if needed)
- [ ] Create IAM user for deployment with:
  - [ ] AmazonEC2FullAccess
  - [ ] AmazonRDSFullAccess
  - [ ] AmazonElastiCacheFullAccess
  - [ ] AmazonS3FullAccess
  - [ ] AmazonECRFullAccess
- [ ] Generate access keys and save securely
- [ ] Verify credentials: `aws sts get-caller-identity`

### 3.2 Production Database Setup
- [ ] Create RDS PostgreSQL instance:
  ```bash
  aws rds create-db-instance \
    --db-instance-identifier trading-agents-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 16.1 \
    --allocated-storage 20 \
    --master-username trading_prod \
    --master-user-password "YOUR_SECURE_PASSWORD" \
    --db-name tradingagents_prod
  ```
- [ ] Wait for database to be available (~10-15 minutes)
- [ ] Note the endpoint URL
- [ ] Run initialization script:
  ```bash
  psql -h <rds-endpoint> -U trading_prod -d tradingagents_prod \
    -f scripts/init_db.sql
  ```

### 3.3 Production Redis Setup
- [ ] Create ElastiCache Redis cluster:
  ```bash
  aws elasticache create-cache-cluster \
    --cache-cluster-id trading-agents-redis \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --engine-version 7.0 \
    --num-cache-nodes 1
  ```
- [ ] Wait for cluster to be available (~5-10 minutes)
- [ ] Note the endpoint URL

### 3.4 Production S3 Setup
- [ ] Create S3 bucket:
  ```bash
  aws s3 mb s3://trading-agents-prod-bucket --region us-east-1
  ```
- [ ] Enable versioning:
  ```bash
  aws s3api put-bucket-versioning \
    --bucket trading-agents-prod-bucket \
    --versioning-configuration Status=Enabled
  ```
- [ ] Enable encryption:
  ```bash
  aws s3api put-bucket-encryption \
    --bucket trading-agents-prod-bucket \
    --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'
  ```
- [ ] Set lifecycle policy (optional, for auto-cleanup)

### 3.5 Production Environment File
- [ ] Create `.env.production` with:
  - [ ] RDS endpoint as DATABASE_URL
  - [ ] ElastiCache endpoint as REDIS_URL
  - [ ] S3 bucket name as AWS_S3_BUCKET
  - [ ] Secure passwords for all services
  - [ ] IBKR live trading credentials (when ready)
- [ ] Store securely (AWS Secrets Manager recommended)
- [ ] DO NOT commit to git

### 3.6 Build Production Image
- [ ] Build Docker image:
  ```bash
  docker build -t trading-agents:latest .
  docker tag trading-agents:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/trading-agents:latest
  ```
- [ ] Login to ECR:
  ```bash
  aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
  ```
- [ ] Create ECR repository:
  ```bash
  aws ecr create-repository --repository-name trading-agents --region us-east-1
  ```
- [ ] Push image:
  ```bash
  docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/trading-agents:latest
  ```

**Status After Phase 3**: ✅ AWS infrastructure ready, image in ECR

---

## Phase 4: Production Deployment (1-2 hours)

### 4.1 Create ECS Cluster
- [ ] Create ECS cluster:
  ```bash
  aws ecs create-cluster --cluster-name trading-agents
  ```

### 4.2 Create Task Definition
- [ ] Create task definition JSON
- [ ] Register task:
  ```bash
  aws ecs register-task-definition --cli-input-json file://task-definition.json
  ```

### 4.3 Create ECS Service
- [ ] Create service:
  ```bash
  aws ecs create-service \
    --cluster trading-agents \
    --service-name trading-agents-service \
    --task-definition trading-agents:1 \
    --desired-count 2
  ```

### 4.4 Configure Monitoring
- [ ] Enable CloudWatch logs:
  ```bash
  aws logs create-log-group --log-group-name /ecs/trading-agents
  ```
- [ ] Set up CloudWatch alarms for:
  - [ ] Database CPU > 80%
  - [ ] Database storage > 80%
  - [ ] Redis CPU > 80%
  - [ ] ECS task failures
  - [ ] Application error rate > 5%

### 4.5 Setup CI/CD
- [ ] Create `.github/workflows/deploy.yml`
- [ ] Add GitHub Secrets:
  - [ ] AWS_ACCESS_KEY_ID
  - [ ] AWS_SECRET_ACCESS_KEY
  - [ ] ECR_REGISTRY
  - [ ] ECS_CLUSTER
  - [ ] ECS_SERVICE

### 4.6 First Production Deployment
- [ ] Push code to main branch
- [ ] GitHub Actions should trigger deployment
- [ ] Monitor deployment progress:
  ```bash
  aws ecs describe-services \
    --cluster trading-agents \
    --services trading-agents-service
  ```
- [ ] Check task logs:
  ```bash
  aws logs tail /ecs/trading-agents --follow
  ```

**Status After Phase 4**: ✅ Production deployment live and monitored

---

## Phase 5: Validation & Testing (1-2 hours)

### 5.1 Application Health
- [ ] Verify application is running: `curl <app-url>/health`
- [ ] Check logs for errors: `aws logs tail /ecs/trading-agents`
- [ ] Test database connection:
  ```python
  from sqlalchemy import create_engine
  engine = create_engine(os.getenv('DATABASE_URL'))
  print(engine.execute('SELECT 1'))
  ```
- [ ] Test Redis connection:
  ```python
  import redis
  r = redis.from_url(os.getenv('REDIS_URL'))
  print(r.ping())
  ```
- [ ] Test S3 access:
  ```python
  import boto3
  s3 = boto3.client('s3')
  print(s3.head_bucket(Bucket=os.getenv('AWS_S3_BUCKET')))
  ```

### 5.2 Backtest Execution
- [ ] Run backtest: `python strategies/run_backtest.py`
- [ ] Verify results saved to PostgreSQL
- [ ] Verify results cached in Redis
- [ ] Verify CSV uploaded to S3
- [ ] Test with different tickers and date ranges
- [ ] Monitor performance (should complete in < 5 minutes)

### 5.3 Data Persistence
- [ ] Verify database backup:
  ```bash
  aws rds create-db-snapshot \
    --db-instance-identifier trading-agents-db \
    --db-snapshot-identifier trading-agents-backup-$(date +%s)
  ```
- [ ] Verify S3 files persist after container restart
- [ ] Test disaster recovery (restore from backup)

### 5.4 Security Validation
- [ ] Verify database credentials are NOT in logs
- [ ] Verify API keys NOT exposed
- [ ] Run security scan:
  ```bash
  docker run --rm aquasec/trivy image <account>.dkr.ecr.us-east-1.amazonaws.com/trading-agents:latest
  ```
- [ ] Verify SSL/TLS encryption for database connections
- [ ] Check AWS security groups restrict access properly

**Status After Phase 5**: ✅ Production system validated and secure

---

## Phase 6: Optimization & Documentation (1-2 hours)

### 6.1 Performance Tuning
- [ ] Monitor CloudWatch metrics
- [ ] Adjust RDS instance class if needed
- [ ] Optimize database queries (add indexes)
- [ ] Enable Redis clustering if throughput is high
- [ ] Implement caching strategies

### 6.2 Cost Optimization
- [ ] Review AWS billing
- [ ] Set up cost alerts: `aws ce put-anomaly-monitor`
- [ ] Right-size EC2 instance
- [ ] Use Reserved Instances for long-term savings
- [ ] Enable S3 Intelligent-Tiering

### 6.3 Documentation
- [ ] Document production URLs and credentials (in secure location)
- [ ] Document disaster recovery procedures
- [ ] Create runbooks for common operations:
  - [ ] How to scale up
  - [ ] How to deploy new version
  - [ ] How to rollback
  - [ ] How to troubleshoot
  - [ ] How to backup/restore
- [ ] Document monitoring and alerting setup

### 6.4 Team Training
- [ ] Train team on deployment procedures
- [ ] Document on-call procedures
- [ ] Share CloudWatch dashboard access
- [ ] Create incident response playbook

**Status After Phase 6**: ✅ Production system optimized and fully documented

---

## Ongoing Maintenance

### Weekly
- [ ] Review CloudWatch metrics
- [ ] Check error logs
- [ ] Verify backups completed
- [ ] Monitor cost trends

### Monthly
- [ ] Run security scan
- [ ] Review and update dependencies
- [ ] Test disaster recovery procedures
- [ ] Capacity planning review

### Quarterly
- [ ] Performance optimization review
- [ ] Security audit
- [ ] Cost optimization review
- [ ] Architecture review for improvements

---

## Troubleshooting Reference

### Common Issues

**PostgreSQL Connection Timeout**
```bash
# Check RDS security groups
aws ec2 describe-security-groups --region us-east-1

# Test connection
psql -h <rds-endpoint> -U trading_prod -d tradingagents_prod
```

**Redis Connection Refused**
```bash
# Verify ElastiCache endpoint
aws elasticache describe-cache-clusters --show-cache-node-info

# Test connection
redis-cli -h <redis-endpoint> -a <password> ping
```

**S3 Access Denied**
```bash
# Verify IAM permissions
aws iam get-user

# Test S3 access
aws s3 ls s3://trading-agents-prod-bucket
```

**ECS Task Failing**
```bash
# Check task logs
aws logs tail /ecs/trading-agents --follow

# Check task definition
aws ecs describe-tasks --cluster trading-agents --tasks <task-arn>

# Update task definition and redeploy
aws ecs update-service --cluster trading-agents --service trading-agents-service --force-new-deployment
```

---

## Success Criteria

✅ All services running and healthy  
✅ Database connected and initialized  
✅ Redis cache operational  
✅ S3 bucket accessible  
✅ Backtest engine integrated  
✅ CI/CD pipeline working  
✅ Monitoring and alerts configured  
✅ Documentation complete  
✅ Team trained  

---

## Timeline Estimate

| Phase | Duration | Total |
|-------|----------|-------|
| Local Dev Setup | 1-2 hours | 1-2 hours |
| App Integration | 1-2 hours | 2-4 hours |
| Prod Preparation | 2-4 hours | 4-8 hours |
| Prod Deployment | 1-2 hours | 5-10 hours |
| Validation | 1-2 hours | 6-12 hours |
| Optimization | 1-2 hours | 7-14 hours |
| **Total** | | **7-14 hours** |

---

**Status**: Ready for Implementation ✅  
**Created**: 2026-09-05  
**Next Step**: Follow Phase 1 checklist to begin
