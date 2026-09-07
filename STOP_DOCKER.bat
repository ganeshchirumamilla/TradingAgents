@echo off
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
