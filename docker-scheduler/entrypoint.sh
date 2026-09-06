#!/bin/bash
# Data Pipeline Scheduler Entrypoint
# Runs daily data pipeline on schedule

set -e

LOG_DIR="/app/logs"
SCRIPT_DIR="/app/scripts"

# Create log directory
mkdir -p $LOG_DIR

echo "=================================="
echo "🚀 Data Pipeline Scheduler"
echo "=================================="
echo "Time: $(date)"
echo "Container ID: $(hostname)"
echo ""

# Function: Run pipeline
run_pipeline() {
    echo "📅 $(date '+%Y-%m-%d %H:%M:%S') - Starting daily pipeline..."

    # Step 1: Incremental download from IBKR
    echo "Step 1: Incremental download..."
    python3 $SCRIPT_DIR/incremental_ibkr_download.py >> $LOG_DIR/incremental.log 2>&1 || \
        echo "⚠️  Incremental download failed (IBKR may be offline)"

    # Step 2: Daily pipeline (purge + cache)
    echo "Step 2: Pipeline (purge + cache)..."
    python3 $SCRIPT_DIR/daily_data_pipeline.py >> $LOG_DIR/pipeline.log 2>&1 || \
        echo "❌ Pipeline failed"

    echo "✅ Daily pipeline complete"
    echo ""
}

# Function: Show logs
show_logs() {
    echo "📋 Recent logs:"
    echo ""

    if [ -f $LOG_DIR/daily_pipeline.log ]; then
        echo "=== Daily Pipeline ==="
        tail -20 $LOG_DIR/daily_pipeline.log
        echo ""
    fi

    if [ -f $LOG_DIR/incremental.log ]; then
        echo "=== Incremental Download ==="
        tail -20 $LOG_DIR/incremental.log
        echo ""
    fi
}

# Main logic
case "${1:-scheduler}" in
    scheduler)
        # Running as scheduler (continuous mode)
        echo "🔔 Scheduler mode - running daily at configured time"
        echo ""

        # Calculate seconds until next run time
        SCHEDULE_HOUR=${SCHEDULE_HOUR:-6}      # Default: 6 AM UTC
        SCHEDULE_MINUTE=${SCHEDULE_MINUTE:-0}   # Default: 00 minutes

        echo "📅 Scheduled time: ${SCHEDULE_HOUR}:${SCHEDULE_MINUTE} UTC"
        echo "⏰ Current time: $(date -u '+%H:%M UTC')"
        echo ""

        # Run once immediately on startup (optional)
        if [ "${RUN_ON_START:-false}" = "true" ]; then
            echo "▶️  Running on startup..."
            run_pipeline
        fi

        # Run as cron job (using alpine cron compatible approach)
        echo "⏳ Waiting for scheduled time..."

        while true; do
            CURRENT_TIME=$(date -u '+%H:%M')
            SCHEDULED_TIME=$(printf "%02d:%02d" $SCHEDULE_HOUR $SCHEDULE_MINUTE)

            if [ "$CURRENT_TIME" = "$SCHEDULED_TIME" ]; then
                run_pipeline
                # Sleep for 61 seconds to avoid running twice in the same minute
                sleep 61
            else
                # Check every 10 seconds
                sleep 10
            fi
        done
        ;;

    once)
        # Run pipeline once and exit
        echo "▶️  Running pipeline once..."
        run_pipeline
        show_logs
        ;;

    logs)
        # Show logs
        show_logs
        tail -f $LOG_DIR/*.log
        ;;

    *)
        echo "Usage: $0 {scheduler|once|logs}"
        echo ""
        echo "Modes:"
        echo "  scheduler - Run continuously (default)"
        echo "  once      - Run pipeline once and exit"
        echo "  logs      - Show logs and follow"
        exit 1
        ;;
esac
