# Data Pipeline Scheduler Container
FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    postgresql-client \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 trading && \
    mkdir -p /app/logs && \
    chown -R trading:trading /app

# Copy requirements
COPY requirements-scheduler.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-scheduler.txt

# Copy scripts
COPY scripts/daily_data_pipeline.py /app/scripts/
COPY scripts/incremental_ibkr_download.py /app/scripts/
COPY scripts/multibar_data_manager.py /app/scripts/

# Copy entrypoint
COPY docker-scheduler/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Create cron directory
RUN mkdir -p /etc/cron.d

USER trading

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["scheduler"]
