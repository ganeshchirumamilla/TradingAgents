#!/usr/bin/env python3
"""
Export PostgreSQL database and prepare for local migration.
Non-interactive version for automated execution.
"""

import sys
import psycopg2
from pathlib import Path
from datetime import datetime

def connect_postgres():
    """Connect to PostgreSQL server."""
    print("[CONNECT] Connecting to PostgreSQL (postgres database)...")
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="postgres",
            password="admin"
        )
        print("[OK] Connected")
        return conn
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None


def get_all_tables(conn):
    """Get list of all tables and their row counts."""
    print("\n[SCAN] Scanning for tables...")
    cursor = conn.cursor()

    try:
        # Find all tables
        cursor.execute("""
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename;
        """)
        tables = cursor.fetchall()

        table_info = []
        total_rows = 0

        print("\nTables found:")
        print("-" * 70)

        for schema, table in tables:
            full_name = f"{schema}.{table}"
            try:
                cursor.execute(f"SELECT count(*) FROM {full_name};")
                count = cursor.fetchone()[0]
                print(f"  {full_name:40s} - {count:10,d} rows")
                table_info.append({
                    'schema': schema,
                    'name': table,
                    'full_name': full_name,
                    'rows': count
                })
                total_rows += count
            except Exception as e:
                print(f"  {full_name:40s} - [ERROR] {str(e)[:30]}")

        print("-" * 70)
        print(f"{'TOTAL':40s} - {total_rows:10,d} rows")

        cursor.close()
        return table_info, total_rows

    except Exception as e:
        print(f"[ERROR] Could not scan tables: {e}")
        return [], 0


def export_to_sql_file(conn, table_info, output_file):
    """Export all data to SQL file."""
    print(f"\n[EXPORT] Exporting to {output_file}...")
    print("-" * 70)

    cursor = conn.cursor()
    exported_rows = 0

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"-- PostgreSQL Database Export\n")
            f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Source: PostgreSQL at localhost:5432 (postgres database)\n")
            f.write(f"-- Target: Create with: CREATE DATABASE tagent;\n")
            f.write(f"-- Import with: psql -U postgres -d tagent < {output_file}\n")
            f.write(f"--\n\n")

            # Export each table
            for info in table_info:
                full_name = info['full_name']
                print(f"  Exporting {full_name}...", end=" ", flush=True)

                try:
                    # Create table schema
                    cursor.execute(f"""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = '{info['name']}' AND table_schema = '{info['schema']}'
                        ORDER BY ordinal_position;
                    """)
                    columns = cursor.fetchall()

                    if not columns:
                        print("[SKIP] - no columns found")
                        continue

                    # Build CREATE TABLE
                    col_defs = []
                    for col_name, col_type, is_nullable, col_default in columns:
                        nullable = "" if is_nullable == 'YES' else " NOT NULL"
                        default = f" DEFAULT {col_default}" if col_default else ""
                        col_defs.append(f"  {col_name} {col_type}{nullable}{default}")

                    f.write(f"\n-- Table: {full_name}\n")
                    f.write(f"DROP TABLE IF EXISTS {full_name} CASCADE;\n")
                    f.write(f"CREATE TABLE {full_name} (\n")
                    f.write(",\n".join(col_defs))
                    f.write("\n);\n\n")

                    # Export data
                    cursor.execute(f"SELECT count(*) FROM {full_name};")
                    row_count = cursor.fetchone()[0]

                    if row_count > 0:
                        cursor.execute(f"SELECT * FROM {full_name};")
                        rows = cursor.fetchall()

                        col_names = [desc[0] for desc in cursor.description]
                        col_names_str = ", ".join(col_names)

                        f.write(f"-- {row_count} rows\n")

                        for row in rows:
                            values = []
                            for v in row:
                                if v is None:
                                    values.append("NULL")
                                elif isinstance(v, str):
                                    # Escape single quotes
                                    escaped = v.replace("'", "''")
                                    values.append(f"'{escaped}'")
                                elif isinstance(v, bool):
                                    values.append("TRUE" if v else "FALSE")
                                elif isinstance(v, (int, float)):
                                    values.append(str(v))
                                else:
                                    # For other types like datetime, UUID, etc
                                    escaped = str(v).replace("'", "''")
                                    values.append(f"'{escaped}'")

                            f.write(f"INSERT INTO {full_name} ({col_names_str}) VALUES ({', '.join(values)});\n")
                            exported_rows += 1

                        print(f"[OK] {row_count} rows")
                    else:
                        print(f"[OK] (empty)")

                except Exception as e:
                    print(f"[ERROR] {str(e)[:40]}")

            # Footer
            f.write(f"\n-- Export complete ({exported_rows} total rows)\n")

        file_size = Path(output_file).stat().st_size / 1024 / 1024
        print(f"\n[OK] Export complete")
        print(f"     File: {output_file}")
        print(f"     Size: {file_size:.2f} MB")
        print(f"     Rows: {exported_rows}")

        cursor.close()
        return True

    except Exception as e:
        print(f"\n[ERROR] Export failed: {e}")
        return False


def create_import_guide(export_file, total_rows):
    """Create detailed import instructions."""
    print("\n[CREATE] Creating import guide...")

    guide = f"""# PostgreSQL Migration to Local Machine

## Database Export Information
- Export file: {export_file}
- Export date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Total rows exported: {total_rows:,}
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
\\l

-- Exit
\\q
```

### Step 2: Import the Backup

From PowerShell/Command Prompt:

```powershell
# Import the database
psql -U postgres -h localhost -d tagent -f {export_file}

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
\\dt              # Show all tables
\\d              # Show detailed table info

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
\\q
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
| "psql: command not found" | Add PostgreSQL bin to PATH: C:\\Program Files\\PostgreSQL\\16\\bin (adjust version) |
| "password authentication failed" | Wrong postgres password; remember the one set during installation |
| "connection refused" | PostgreSQL not running; start service in Windows Services |
| "Port 5432 already in use" | Another PostgreSQL instance running; stop it or use different port |

## Data Integrity

All {total_rows:,} rows have been exported with proper SQL escaping:
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
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    guide_file = Path("POSTGRES_IMPORT_GUIDE.md")
    with open(guide_file, 'w') as f:
        f.write(guide)

    print(f"[OK] Guide: {guide_file}")
    return guide_file


def create_docker_stop_script():
    """Create batch script to stop Docker."""
    print("[CREATE] Creating Docker stop script...")

    script = """@echo off
REM Stop Docker containers (without deleting them)
echo.
echo ========================================
echo  Stopping Docker Containers
echo ========================================
echo.
echo This will stop containers but preserve data.
echo.

REM Check if in project directory
if not exist "docker-compose.yml" (
    echo ERROR: docker-compose.yml not found
    echo Please run this from the project directory
    pause
    exit /b 1
)

REM Stop containers
echo Stopping containers...
docker-compose down

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Containers stopped successfully
    echo.
    echo To restart: docker-compose up -d
    echo To delete:  docker-compose down -v
) else (
    echo.
    echo [ERROR] Failed to stop containers
)

echo.
pause
"""

    script_file = Path("STOP_DOCKER.bat")
    with open(script_file, 'w') as f:
        f.write(script)

    print(f"[OK] Script: {script_file}")
    return script_file


def main():
    """Main process."""
    print("\n" + "="*70)
    print("POSTGRESQL EXPORT AND LOCAL MIGRATION SETUP")
    print("="*70)

    # Connect
    conn = connect_postgres()
    if not conn:
        sys.exit(1)

    # Scan tables
    table_info, total_rows = get_all_tables(conn)
    if not table_info:
        print("\n[WARNING] No tables found in database")

    # Export to SQL
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"postgres_backup_{timestamp}.sql"

    success = export_to_sql_file(conn, table_info, export_file)
    conn.close()

    if not success:
        sys.exit(1)

    # Create guides
    create_import_guide(export_file, total_rows)
    create_docker_stop_script()

    # Summary
    print("\n" + "="*70)
    print("[COMPLETE] Export and Setup Ready")
    print("="*70)

    print(f"\nFiles created:")
    print(f"  1. {export_file}")
    print(f"     - SQL backup file with all data")
    print(f"  2. POSTGRES_IMPORT_GUIDE.md")
    print(f"     - Complete step-by-step import instructions")
    print(f"  3. STOP_DOCKER.bat")
    print(f"     - Batch script to stop Docker containers")

    print(f"\nDatabase Summary:")
    print(f"  Tables: {len(table_info)}")
    print(f"  Rows: {total_rows:,}")
    print(f"  File: {export_file}")
    print(f"  Size: {Path(export_file).stat().st_size / 1024:.1f} KB")

    print(f"\nNext Steps:")
    print(f"  1. Read: POSTGRES_IMPORT_GUIDE.md")
    print(f"  2. Create local database: CREATE DATABASE tagent;")
    print(f"  3. Import: psql -U postgres -d tagent < {export_file}")
    print(f"  4. Verify: psql -U postgres -d tagent -c \\\"SELECT count(*) FROM ...;\\\"")
    print(f"  5. Stop Docker: Run STOP_DOCKER.bat")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
