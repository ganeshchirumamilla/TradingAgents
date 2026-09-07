#!/usr/bin/env python3
"""
Export PostgreSQL database from Docker container.
Dumps all data to SQL file for import into local PostgreSQL.
"""

import sys
import subprocess
import os
from pathlib import Path
from datetime import datetime

def run_command(cmd, description=""):
    """Run shell command and return output."""
    if description:
        print(f"\n[EXECUTE] {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            if description:
                print(f"[OK] {description}")
            return result.stdout
        else:
            print(f"[ERROR] {description}")
            print(f"  STDERR: {result.stderr}")
            return None
    except Exception as e:
        print(f"[ERROR] {description}: {e}")
        return None


def check_docker():
    """Check if Docker is available."""
    print("\n[CHECK] Docker availability...")
    result = subprocess.run("docker --version", shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[OK] {result.stdout.strip()}")
        return True
    else:
        print("[ERROR] Docker not found or not running")
        return False


def check_container():
    """Check if PostgreSQL container is running."""
    print("\n[CHECK] PostgreSQL container status...")
    result = subprocess.run("docker ps --filter name=trading-postgres", shell=True, capture_output=True, text=True)

    if "trading-postgres" in result.stdout:
        print("[OK] Container 'trading-postgres' is running")
        return True
    else:
        print("[WARNING] Container 'trading-postgres' not running")
        print("  Checking if container exists...")
        result = subprocess.run("docker ps -a --filter name=trading-postgres", shell=True, capture_output=True, text=True)
        if "trading-postgres" in result.stdout:
            print("[INFO] Container exists but is stopped")
            return True
        else:
            print("[ERROR] Container 'trading-postgres' not found")
            return False


def list_databases():
    """List all databases in Docker PostgreSQL."""
    print("\n[LIST] Databases in Docker PostgreSQL...")
    cmd = """docker exec trading-postgres psql -U trading -d tradingagents -c "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;" """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"[ERROR] Could not list databases: {result.stderr}")


def list_tables():
    """List all tables in the database."""
    print("\n[LIST] Tables in 'tradingagents' database...")
    cmd = """docker exec trading-postgres psql -U trading -d tradingagents -c "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY schemaname, tablename;" """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("[WARNING] Could not list tables (database might be empty)")


def export_database():
    """Export database to SQL file."""
    print("\n[EXPORT] Creating database dump...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_file = f"docker_postgres_backup_{timestamp}.sql"
    export_path = Path(export_file).absolute()

    # Use docker exec to dump the database
    cmd = f"""docker exec trading-postgres pg_dump -U trading -d tradingagents --verbose > "{export_path}" """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        file_size = export_path.stat().st_size / 1024 / 1024
        print(f"[OK] Database exported to: {export_path}")
        print(f"     File size: {file_size:.2f} MB")
        return export_path
    else:
        print(f"[ERROR] Export failed: {result.stderr}")
        return None


def export_tables_separately():
    """Export each table separately for easier viewing."""
    print("\n[EXPORT] Exporting tables separately...")

    export_dir = Path("docker_postgres_exports")
    export_dir.mkdir(exist_ok=True)

    # Get list of tables
    cmd = """docker exec trading-postgres psql -U trading -d tradingagents -t -c "SELECT schemaname || '.' || tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY schemaname, tablename;" """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print("[ERROR] Could not get table list")
        return None

    tables = [t.strip() for t in result.stdout.strip().split('\n') if t.strip()]
    print(f"[INFO] Found {len(tables)} tables to export")

    exported_files = []
    for table in tables:
        table_file = export_dir / f"{table.replace('.', '_')}.sql"
        cmd = f"""docker exec trading-postgres pg_dump -U trading -d tradingagents -t "{table}" > "{table_file}" """

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            file_size = table_file.stat().st_size / 1024
            print(f"  [OK] {table:50s} -> {file_size:8.1f} KB")
            exported_files.append(table_file)
        else:
            print(f"  [ERROR] {table}")

    return export_dir, exported_files


def get_db_stats():
    """Get database statistics."""
    print("\n[STATS] Database statistics...")

    # Count total records
    cmd = """docker exec trading-postgres psql -U trading -d tradingagents -c "SELECT schemaname, tablename, n_live_tup as row_count FROM pg_stat_user_tables ORDER BY schemaname, tablename;" """

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("[WARNING] Could not get statistics")


def create_import_guide(export_file):
    """Create guide for importing to local PostgreSQL."""
    print("\n[GUIDE] Creating import guide...")

    guide_file = Path("IMPORT_GUIDE.md")

    guide_content = f"""# Import PostgreSQL Database to Local Machine

## Prerequisites
1. PostgreSQL installed locally
2. Database name: `tagent`
3. Backup file: `{export_file.name}`

## Steps

### 1. Create Database (Windows Command Prompt)
\`\`\`cmd
REM Connect to local PostgreSQL
psql -U postgres

REM In psql prompt:
CREATE DATABASE tagent;
\\q
\`\`\`

### 2. Import Backup
\`\`\`cmd
REM Import the database dump
psql -U postgres -d tagent < {export_file.name}
\`\`\`

### 3. Verify Import
\`\`\`cmd
psql -U postgres -d tagent

REM In psql prompt:
SELECT datname FROM pg_database WHERE datname = 'tagent';
\\dt

REM Show table row counts:
SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables;
\`\`\`

## Update Configuration

After import, update your connection settings to use local database:

**download_config.yaml:**
\`\`\`yaml
database:
  host: "localhost"
  port: 5432
  name: "tagent"
  user: "postgres"
  password: <your_local_password>
\`\`\`

**Python scripts:**
\`\`\`python
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="tagent",
    user="postgres",
    password="<your_password>"
)
\`\`\`

## Backup File Information
- File: {export_file.name}
- Size: {export_file.stat().st_size / 1024 / 1024:.2f} MB
- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Source: Docker PostgreSQL container (trading-postgres)
- Original database: tradingagents

## Restore Later (if needed)
\`\`\`cmd
psql -U postgres -d tagent < {export_file.name}
\`\`\`
"""

    with open(guide_file, 'w') as f:
        f.write(guide_content)

    print(f"[OK] Import guide created: {guide_file}")
    return guide_file


def shutdown_docker():
    """Shutdown Docker containers."""
    print("\n[SHUTDOWN] Stopping Docker containers...")
    print("="*70)

    # Get list of running containers
    cmd = "docker ps --filter label=com.docker.compose.project=tradingagents -q"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout.strip():
        print("[INFO] Stopping containers...")
        cmd = "docker-compose down"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="C:\\Trading\\TradingAgents")

        if result.returncode == 0:
            print("[OK] Containers stopped successfully")
            print("\n[INFO] Data volumes preserved (not deleted)")
            print("       Containers can be restarted with: docker-compose up -d")
        else:
            print("[WARNING] Error stopping containers:")
            print(result.stderr)
    else:
        print("[INFO] No running containers to stop")


def main():
    """Main export process."""
    print("\n" + "="*70)
    print("DOCKER POSTGRESQL EXPORT AND MIGRATION SETUP")
    print("="*70)

    # Check Docker
    if not check_docker():
        print("\n[ERROR] Docker is required to export from container")
        sys.exit(1)

    # Check container
    if not check_container():
        print("\n[ERROR] PostgreSQL container not found")
        sys.exit(1)

    # List databases
    list_databases()

    # List tables
    list_tables()

    # Get statistics
    get_db_stats()

    # Export database
    export_file = export_database()
    if not export_file:
        sys.exit(1)

    # Export tables separately
    export_dir, exported_files = export_tables_separately()

    # Create import guide
    create_import_guide(export_file)

    # Ask about shutdown
    print("\n" + "="*70)
    print("[READY] Export complete!")
    print("="*70)
    print(f"\nBackup file:        {export_file.name}")
    print(f"Backup location:    {export_file.parent.absolute()}")
    print(f"Separate exports:   {export_dir}")
    print(f"Import guide:       IMPORT_GUIDE.md")

    response = input("\nShutdown Docker containers? (yes/no): ").strip().lower()
    if response == "yes":
        shutdown_docker()
    else:
        print("\n[INFO] Docker containers still running")
        print("       To shutdown later: docker-compose down")

    print("\n" + "="*70)
    print("Next steps:")
    print("  1. Review IMPORT_GUIDE.md")
    print("  2. Install local PostgreSQL if not already installed")
    print("  3. Create 'tagent' database")
    print("  4. Run: psql -U postgres -d tagent < " + export_file.name)
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
