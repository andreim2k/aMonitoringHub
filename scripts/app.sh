#!/bin/bash

# aMonitoringHub Process Management Script
# Manages the GraphQL backend using nohup and background processes

set -e  # Exit on any error

# Configuration - Use relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/backend/venv"
BACKEND_PATH="$PROJECT_ROOT/backend"
LOGS_PATH="$PROJECT_ROOT/logs"
PID_FILE="$LOGS_PATH/app.pid"
LOG_FILE="$LOGS_PATH/backend.out"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        log_error "Virtual environment not found at $VENV_PATH"
        log_info "Please run: python3 -m venv $VENV_PATH"
        exit 1
    fi
}

# Check if backend exists
check_backend() {
    if [ ! -f "$BACKEND_PATH/app.py" ]; then
        log_error "Backend application not found at $BACKEND_PATH/app.py"
        exit 1
    fi
}

# Create logs directory if it doesn't exist
ensure_logs_dir() {
    mkdir -p "$LOGS_PATH"
}

# Start the application
start_app() {
    log_info "Starting aMonitoringHub..."
    
    check_venv
    check_backend
    ensure_logs_dir
    
    # Check if already running
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log_warning "Application is already running (PID: $PID)"
            return 0
        else
            log_info "Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    cd "$BACKEND_PATH"
    nohup "$VENV_PATH/bin/python" app.py \
        > "$LOG_FILE" 2>&1 &
    
    APP_PID=$!
    echo $APP_PID > "$PID_FILE"
    
    sleep 2
    if ps -p $APP_PID > /dev/null 2>&1; then
        log_success "aMonitoringHub started successfully (PID: $APP_PID)"
        log_info "Check logs: tail -f $LOG_FILE"
    else
        log_error "Failed to start application"
        return 1
    fi
}

# Stop the application
stop_app() {
    log_info "Stopping aMonitoringHub..."
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            rm -f "$PID_FILE"
            log_success "Application stopped"
        else
            log_warning "Application was not running"
            rm -f "$PID_FILE"
        fi
    else
        log_warning "No PID file found, attempting to kill by process name"
        pkill -f "python.*app.py" || log_info "No processes found to kill"
    fi
}

# Show application status
show_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            log_success "Application is running (PID: $PID)"
            return 0
        else
            log_error "PID file exists but process not found"
            return 1
        fi
    else
        log_error "Application is not running"
        return 1
    fi
}

# Show logs
show_logs() {
    LINES=${1:-50}
    if [ -f "$LOG_FILE" ]; then
        tail -n $LINES "$LOG_FILE"
    else
        log_error "Log file not found: $LOG_FILE"
    fi
}

# Follow logs
follow_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        log_error "Log file not found: $LOG_FILE"
    fi
}

# Show help
show_help() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start          Start the aMonitoringHub server"
    echo "  stop           Stop the aMonitoringHub server"
    echo "  restart        Restart the aMonitoringHub server"
    echo "  status         Show server status"
    echo "  logs [LINES]   Show last N lines of logs (default: 50)"
    echo "  follow         Follow logs in real-time"
    echo "  help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs 100"
    echo "  $0 follow"
}

# Main script logic
case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        stop_app
        sleep 2
        start_app
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    follow)
        follow_logs
        ;;
    help|--help|-h)
        show_help
        ;;

    prod-start)
        export LOG_LEVEL=INFO
        check_venv
        check_backend
        ensure_logs_dir
        cd "$BACKEND_PATH"
        nohup "$VENV_PATH/bin/gunicorn" -w 2 -k gthread -t 60 -b 0.0.0.0:5000             --log-level info --access-logfile "$LOGS_PATH/access.log" --error-logfile "$LOGS_PATH/error.log"             backend.wsgi:application > "$LOG_FILE" 2>&1 &
        APP_PID=$!
        echo $APP_PID > "$PID_FILE"
        sleep 2
        if ps -p $APP_PID > /dev/null 2>&1; then
            log_success "aMonitoringHub (gunicorn) started successfully (PID: $APP_PID)"
        else
            log_error "Failed to start gunicorn"
        fi
        ;;
    prod-restart)
        $0 stop
        sleep 2
        $0 prod-start
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
