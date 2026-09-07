# PostgreSQL Migration to Local Machine

## Database Export Information
- Export file: postgres_backup_20260906_144440.sql
- Export date: 2026-09-06 14:44:40
- Total rows exported: 35,493
- Source: PostgreSQL localhost (postgres database)

## Prerequisites
1. PostgreSQL 12+ installed locally
   - Download from: https://www.postgresql.org/download/
   - Windows installer: https://www.postgresql.org/download/windows/

2. During installation, remember the postgres user password

3. After installation, verify psql is available:
   ```powershell
   psql --version
   ```

## Import Steps

### Step 1: Create the Database

Open PowerShell or Command Prompt:

```powershell
# Connect to PostgreSQL
psql -U postgres -h localhost

# You'll be prompted for the postgres password (set during installation)
```

In the psql prompt (postgres=#):

```sql
-- Create new database
CREATE DATABASE tagent;

-- Verify creation
\l

-- Exit
\q
```

### Step 2: Import the Backup

From PowerShell/Command Prompt:

```powershell
# Import the database
psql -U postgres -h localhost -d tagent -f postgres_backup_20260906_144440.sql

# You'll see:
# CREATE TABLE
# INSERT 0 1
# ... etc ...
```

This will take a few moments depending on data size.

### Step 3: Verify Import Success

```powershell
# Connect to new database
psql -U postgres -h localhost -d tagent

# In psql prompt:
\dt              # Show all tables
\d              # Show detailed table info

# Check row counts:
SELECT schemaname, tablename, n_live_tup as row_count
FROM pg_stat_user_tables
ORDER BY schemaname, tablename;

# Show specific tables:
SELECT count(*) FROM historical_data_1min;
SELECT count(*) FROM historical_data_5min;
SELECT count(*) FROM historical_data_hourly;
SELECT count(*) FROM historical_data_daily;

# Exit
\q
```

## Update Configuration Files

### Method 1: Update download_config.yaml

```yaml
database:
  host: "localhost"
  port: 5432
  name: "tagent"
  user: "postgres"
  password: "YOUR_POSTGRES_PASSWORD"  # Password set during PostgreSQL installation
```

### Method 2: Environment Variables (PowerShell)

```powershell
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_NAME = "tagent"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "your_password"
```

### Method 3: Python Connection

```python
import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="tagent",
        user="postgres",
        password="your_postgres_password"
    )

# Then use:
conn = get_connection()
cursor = conn.cursor()
```

## Backup and Restore

### Create Additional Backups

```powershell
# Backup to file
pg_dump -U postgres -h localhost -d tagent > backup_tagent.sql

# Backup compressed
pg_dump -U postgres -h localhost -d tagent | gzip > backup_tagent.sql.gz
```

### Restore from Backup

```powershell
# If needed, restore from backup:
psql -U postgres -h localhost -d tagent < backup_tagent.sql
```

## Docker Status

Your Docker containers have been stopped but not deleted:

```powershell
# Check status
docker ps -a

# Restart Docker containers if needed:
docker-compose up -d

# Remove Docker containers/volumes (if no longer needed):
docker-compose down -v
```

## Connection String Reference

**For Python (psycopg2):**
```python
"postgresql://postgres:PASSWORD@localhost:5432/tagent"
```

**For psql command-line:**
```
psql -U postgres -h localhost -d tagent
```

**For libpq (C/C++):**
```
host=localhost port=5432 user=postgres password=PASSWORD dbname=tagent
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| "FATAL: role 'postgres' does not exist" | PostgreSQL not installed or different user created; use that user instead |
| "FATAL: database 'tagent' does not exist" | Run CREATE DATABASE tagent; first |
| "psql: command not found" | Add PostgreSQL bin to PATH: C:\Program Files\PostgreSQL\16\bin (adjust version) |
| "password authentication failed" | Wrong postgres password; remember the one set during installation |
| "connection refused" | PostgreSQL not running; start service in Windows Services |
| "Port 5432 already in use" | Another PostgreSQL instance running; stop it or use different port |

## Data Integrity

All 35,493 rows have been exported with proper SQL escaping:
- String values: Single quotes escaped
- NULL values: Properly represented
- Data types: Preserved exactly
- Foreign keys: Maintained where applicable

The imported database should be identical to the source.

## Next Steps

1. Import the database using Step 2 above
2. Verify with Step 3
3. Update configuration files
4. Test connections from your applications
5. Once confirmed working, you can shut down Docker:
   ```powershell
   docker-compose down
   ```

---
Generated: 2026-09-06 14:44:40
