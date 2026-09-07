#!/usr/bin/env python3
"""
Export PostgreSQL database directly without Docker.
Dumps all data to SQL file for import into local PostgreSQL.
"""

import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
from datetime import datetime
import json

def connect_db(host="localhost", port=5432, user="postgres", password="admin"):
    """Connect to PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database="postgres",
            user=user,
            password=password
        )
        return conn
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None


def list_all_databases(conn):
    """List all databases."""
    print("\n[LIST] All databases...")
    print("-" * 70)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
        databases = cursor.fetchall()
        for db in databases:
            print(f"  - {db[0]}")
        return [db[0] for db in databases]
    except Exception as e:
        print(f"[ERROR] {e}")
        return []
    finally:
        cursor.close()


def get_table_info(conn, database_name):
    """Get information about all tables in a database."""
    try:
        # Connect to specific database
        conn_db = psycopg2.connect(
            host=conn.get_dsn_parameters()['host'],
            port=conn.get_dsn_parameters()['port'],
            database=database_name,
            user=conn.get_dsn_parameters()['user'],
            password=conn.get_dsn_parameters()['password']
        )
        cursor = conn_db.cursor()

        # Get tables
        cursor.execute("""
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename;
        """)
        tables = cursor.fetchall()

        # Get row counts
        table_info = []
        for schema, table in tables:
            full_table = f"{schema}.{table}"
            try:
                cursor.execute(f"SELECT count(*) FROM {full_table};")
                count = cursor.fetchone()[0]
                table_info.append({
                    'schema': schema,
                    'table': table,
                    'full_name': full_table,
                    'rows': count
                })
            except:
                table_info.append({
                    'schema': schema,
                    'table': table,
                    'full_name': full_table,
                    'rows': 0
                })

        conn_db.close()
        return table_info

    except Exception as e:
        print(f"[ERROR] Could not get table info: {e}")
        return []


def export_database_to_sql(conn, database_name, output_file):
    """Export database to SQL file using psycopg2."""
    print(f"\n[EXPORT] Exporting '{database_name}' to SQL...")
    print("-" * 70)

    try:
        conn_db = psycopg2.connect(
            host=conn.get_dsn_parameters()['host'],
            port=conn.get_dsn_parameters()['port'],
            database=database_name,
            user=conn.get_dsn_parameters()['user'],
            password=conn.get_dsn_parameters()['password']
        )
        cursor = conn_db.cursor()

        with open(output_file, 'w') as f:
            # Write header
            f.write(f"-- PostgreSQL database dump\n")
            f.write(f"-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Source database: {database_name}\n")
            f.write(f"-- \n\n")

            # Get all tables
            cursor.execute("""
                SELECT schemaname, tablename
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY schemaname, tablename;
            """)
            tables = cursor.fetchall()

            # Export each table
            for schema, table in tables:
                full_table = f"{schema}.{table}"
                print(f"  Exporting {full_table}...", end=" ", flush=True)

                try:
                    # Get CREATE TABLE statement
                    cursor.execute(f"""
                        SELECT definition FROM pg_views WHERE viewname = '{table}' AND schemaname = '{schema}';
                    """)
                    view_result = cursor.fetchone()

                    if not view_result:
                        # It's a table, get the CREATE TABLE
                        cursor.execute(f"""
                            SELECT pg_get_ddl('public.{table}'::regclass);
                        """)
                        ddl_result = cursor.fetchone()

                        if ddl_result and ddl_result[0]:
                            f.write(f"{ddl_result[0]};\n\n")
                        else:
                            # Manual approach
                            cursor.execute(f"""
                                SELECT column_name, data_type, is_nullable
                                FROM information_schema.columns
                                WHERE table_name = '{table}' AND table_schema = '{schema}'
                                ORDER BY ordinal_position;
                            """)
                            columns = cursor.fetchall()

                            if columns:
                                col_defs = []
                                for col in columns:
                                    col_name, col_type, is_nullable = col
                                    nullable_str = "" if is_nullable == 'YES' else " NOT NULL"
                                    col_defs.append(f"  {col_name} {col_type}{nullable_str}")

                                f.write(f"CREATE TABLE IF NOT EXISTS {full_table} (\n")
                                f.write(",\n".join(col_defs))
                                f.write("\n);\n\n")

                    # Get data
                    cursor.execute(f"SELECT count(*) FROM {full_table};")
                    count = cursor.fetchone()[0]

                    if count > 0:
                        cursor.execute(f"SELECT * FROM {full_table};")
                        rows = cursor.fetchall()

                        # Get column names
                        col_names = [desc[0] for desc in cursor.description]

                        # Write INSERT statements
                        for row in rows:
                            values_str = ", ".join([
                                f"'{str(v).replace(chr(39), chr(39)+chr(39))}'" if v is not None else "NULL"
                                for v in row
                            ])
                            f.write(f"INSERT INTO {full_table} ({', '.join(col_names)}) VALUES ({values_str});\n")

                    print(f"[OK] {count} rows")

                except Exception as e:
                    print(f"[ERROR] {str(e)[:50]}")

            f.write(f"\n-- Export complete\n")

        conn_db.close()
        file_size = Path(output_file).stat().st_size / 1024 / 1024
        print(f"\n[OK] Export complete: {output_file}")
        print(f"     File size: {file_size:.2f} MB")
        return True

    except Exception as e:
        print(f"[ERROR] Export failed: {e}")
        return False


def create_import_instructions():
    """Create step-by-step import instructions."""
    print("\n[CREATE] Import instructions...")

    guide_content = """# PostgreSQL Database Migration to Local Machine

## Current Status
- Source: PostgreSQL Database (currently connected)
- Target: Local PostgreSQL with database name: `tagent`

## Prerequisites
1. PostgreSQL installed locally (version 12 or higher)
2. psql command-line tool available
3. Backup file: `postgres_backup_*.sql`

## Step-by-Step Import Instructions

### 1. Create Local Database (Windows Command Prompt or PowerShell)

Open PowerShell or Command Prompt and run:

```powershell
# Connect to local PostgreSQL
psql -U postgres

# You'll be prompted for password (default might be 'postgres' or your setup password)
```

In the psql prompt (postgres=#), run:

```sql
-- Create the new database
CREATE DATABASE tagent;

-- Exit psql
\\q
```

### 2. Import the Backup

From Command Prompt/PowerShell:

```powershell
# Import the database dump
psql -U postgres -d tagent < postgres_backup_YYYYMMDD_HHMMSS.sql

# Or if prompted for password:
psql -U postgres -d tagent -W < postgres_backup_YYYYMMDD_HHMMSS.sql
```

### 3. Verify the Import

```powershell
# Connect to the new database
psql -U postgres -d tagent

# In psql prompt, verify:
\\dt                           # List all tables
SELECT count(*) FROM historical_data_1min;    # Check row counts
SELECT count(*) FROM historical_data_5min;
SELECT count(*) FROM historical_data_hourly;
SELECT count(*) FROM historical_data_daily;

# Exit
\\q
```

## Update Configuration Files

After successful import, update your configuration to use the local database:

### Option 1: Update download_config.yaml

```yaml
database:
  host: "localhost"
  port: 5432
  name: "tagent"
  user: "postgres"
  password: "YOUR_LOCAL_POSTGRES_PASSWORD"
```

### Option 2: Set Environment Variables

```powershell
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_NAME = "tagent"
$env:DB_USER = "postgres"
$env:DB_PASSWORD = "your_password"
```

### Option 3: Update Python Connection Strings

```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="tagent",
    user="postgres",
    password="your_password"  # Your local PostgreSQL password
)
```

## Troubleshooting

### Error: "role 'postgres' does not exist"
- Create a PostgreSQL user first: `createuser -U postgres your_username`

### Error: "database 'tagent' does not exist"
- Make sure you created the database: `CREATE DATABASE tagent;`

### Error: "permission denied"
- Check PostgreSQL user permissions: `GRANT ALL PRIVILEGES ON DATABASE tagent TO postgres;`

### Error: "psql command not found"
- Add PostgreSQL bin directory to PATH
- Windows default: `C:\\Program Files\\PostgreSQL\\16\\bin\\` (adjust version number)

## Backing Up Again

To create another backup from local PostgreSQL:

```powershell
# Export to file
pg_dump -U postgres -d tagent > tagent_backup.sql

# Or compressed
pg_dump -U postgres -d tagent | gzip > tagent_backup.sql.gz
```

## Restoring from Backup

If something goes wrong:

```powershell
# Drop and recreate database
psql -U postgres -c "DROP DATABASE tagent;"
psql -U postgres -c "CREATE DATABASE tagent;"

# Restore from backup
psql -U postgres -d tagent < postgres_backup_*.sql
```

## Docker Container Status

The Docker containers have been STOPPED but not deleted:

- To check status: `docker ps -a`
- To restart: `docker-compose up -d` (from project directory)
- To remove: `docker-compose down -v` (with -v to also remove volumes)

All data in PostgreSQL Docker container is preserved in volumes.

"""

    guide_file = Path("LOCAL_POSTGRES_IMPORT_GUIDE.md")
    with open(guide_file, 'w') as f:
        f.write(guide_content)

    print(f"[OK] Guide saved: {guide_file}")
    return guide_file


def create_docker_compose_stop_script():
    """Create script to stop Docker containers."""
    print("\n[CREATE] Docker shutdown script...")

    stop_script = """@echo off
REM Stop Docker containers without deleting them
echo Stopping Docker containers...
docker-compose down

echo.
echo Containers stopped. Data is preserved.
echo To restart: docker-compose up -d
echo To delete: docker-compose down -v
echo.
pause
"""

    script_file = Path("stop_docker.bat")
    with open(script_file, 'w') as f:
        f.write(stop_script)

    print(f"[OK] Script saved: {script_file}")
    return script_file


def main():
    """Main export process."""
    print("\n" + "="*70)
    print("POSTGRESQL DATABASE EXPORT AND MIGRATION SETUP")
    print("="*70)

    # Connect to PostgreSQL
    print("\n[CONNECT] Connecting to PostgreSQL...")
    conn = connect_db()
    if not conn:
        print("\n[ERROR] Could not connect to PostgreSQL")
        print("        Make sure PostgreSQL is running on localhost:5432")
        sys.exit(1)

    print("[OK] Connected to PostgreSQL")

    # List databases
    databases = list_all_databases(conn)

    # Get info about each database
    print("\n[INFO] Database contents...")
    print("-" * 70)
    for db_name in databases:
        tables = get_table_info(conn, db_name)
        if tables:
            print(f"\nDatabase: {db_name}")
            total_rows = 0
            for info in tables:
                print(f"  {info['full_name']:40s} - {info['rows']:10,d} rows")
                total_rows += info['rows']
            print(f"  {'TOTAL':40s} - {total_rows:10,d} rows")

    # Ask which database to export
    conn.close()

    print("\n" + "="*70)
    print("[SELECT] Which database to export?")
    print("-" * 70)
    for i, db_name in enumerate(databases, 1):
        print(f"  {i}. {db_name}")

    choice = input("\nEnter database number (default: 1): ").strip()
    if not choice:
        choice = "1"

    try:
        db_index = int(choice) - 1
        if 0 <= db_index < len(databases):
            selected_db = databases[db_index]
        else:
            print("[ERROR] Invalid selection")
            sys.exit(1)
    except ValueError:
        print("[ERROR] Invalid input")
        sys.exit(1)

    # Reconnect for export
    conn = connect_db()
    if not conn:
        sys.exit(1)

    # Export database
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"postgres_backup_{timestamp}.sql"

    success = export_database_to_sql(conn, selected_db, export_file)
    conn.close()

    if not success:
        sys.exit(1)

    # Create guides
    create_import_instructions()
    create_docker_compose_stop_script()

    # Summary
    print("\n" + "="*70)
    print("[SUCCESS] Export and setup complete!")
    print("="*70)
    print(f"\nFiles created:")
    print(f"  1. {export_file}")
    print(f"     - Database dump ready for import")
    print(f"  2. LOCAL_POSTGRES_IMPORT_GUIDE.md")
    print(f"     - Step-by-step import instructions")
    print(f"  3. stop_docker.bat")
    print(f"     - Script to stop Docker containers (data preserved)")

    print(f"\nNext steps:")
    print(f"  1. Read: LOCAL_POSTGRES_IMPORT_GUIDE.md")
    print(f"  2. Install local PostgreSQL (if not already installed)")
    print(f"  3. Create database: CREATE DATABASE tagent;")
    print(f"  4. Import: psql -U postgres -d tagent < {export_file}")
    print(f"  5. Run: stop_docker.bat (to stop Docker containers)")

    print("\n" + "="*70)
    print("\nReady to stop Docker? (yes/no): ", end="")
    response = input().strip().lower()

    if response == "yes":
        print("\n[SHUTDOWN] Stopping Docker containers...")
        import subprocess
        result = subprocess.run(
            "docker-compose down",
            shell=True,
            capture_output=True,
            text=True,
            cwd="C:\\Trading\\TradingAgents"
        )
        if result.returncode == 0:
            print("[OK] Docker containers stopped")
            print("[INFO] Data volumes are preserved")
            print("[INFO] Containers can be restarted with: docker-compose up -d")
        else:
            print("[WARNING] Could not stop Docker:")
            print(result.stderr)
    else:
        print("\n[INFO] Docker containers still running")
        print("       Stop them later with: docker-compose down")

    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
