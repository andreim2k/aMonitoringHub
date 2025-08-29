#!/bin/bash

# aWeatherStation Process Management Script
# Manages the GraphQL backend using nohup and background processes

set -e  # Exit on any error

# Configuration
PROJECT_ROOT="/root/aWeatherStation"
VENV_PATH="$PROJECT_ROOT/venv"
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

# Check if process is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Process is running
        else
            # PID file exists but process is not running
            rm -f "$PID_FILE"
            return 1  # Process is not running
        fi
    fi
    return 1  # PID file doesn't exist
}

# Get process status
get_status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        log_success "aWeatherStation server is running (PID: $pid)"
        
        # Show additional info
        echo "  GraphQL endpoint: http://192.168.50.2:5000/graphql"
        echo "  Frontend: http://192.168.50.2:5000/"
        echo "  SSE endpoint: http://192.168.50.2:5000/events"
        echo "  Log file: $LOG_FILE"
        
        # Show resource usage
        local mem_usage=$(ps -p "$pid" -o %mem --no-headers 2>/dev/null | tr -d ' ' || echo "N/A")
        local cpu_usage=$(ps -p "$pid" -o %cpu --no-headers 2>/dev/null | tr -d ' ' || echo "N/A")
        echo "  Memory usage: ${mem_usage}%"
        echo "  CPU usage: ${cpu_usage}%"
        
        return 0
    else
        log_warning "aWeatherStation server is not running"
        return 1
    fi
}

# Start the application
start_app() {
    log_info "Starting aWeatherStation server..."
    
    # Check if already running
    if is_running; then
        log_warning "Server is already running. Use 'restart' to restart it."
        return 1
    fi
    
    # Validate environment
    if [ ! -d "$VENV_PATH" ]; then
        log_error "Virtual environment not found at $VENV_PATH"
        log_info "Please run: python3 -m venv $VENV_PATH"
        return 1
    fi
    
    if [ ! -f "$BACKEND_PATH/app.py" ]; then
        log_error "Backend application not found at $BACKEND_PATH/app.py"
        return 1
    fi
    
    # Create logs directory if it doesn't exist
    mkdir -p "$LOGS_PATH"
    
    # Activate virtual environment and start the application with nohup
    log_info "Starting server with nohup in background..."
    
    # Change to the backend directory and start the application
    cd "$BACKEND_PATH"
    
    # Use nohup and background process as requested
    nohup "$VENV_PATH/bin/python" app.py \
        --host 0.0.0.0 \
        --port 5000 \
        > "$LOG_FILE" 2>&1 &
    
    # Save the PID
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    # Give the server a moment to start
    sleep 2
    
    # Verify it started successfully
    if is_running; then
        log_success "aWeatherStation server started successfully!"
        log_info "Server is running in background (PID: $pid)"
        log_info "Logs are being written to: $LOG_FILE"
        log_info "GraphQL endpoint: http://192.168.50.2:5000/graphql"
        log_info "Frontend: http://192.168.50.2:5000/"
        
        # Show last few log lines
        log_info "Last few log entries:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "No logs yet."
        
        return 0
    else
        log_error "Failed to start server. Check logs at: $LOG_FILE"
        if [ -f "$LOG_FILE" ]; then
            log_info "Last few log entries:"
            tail -10 "$LOG_FILE"
        fi
        return 1
    fi
}

# Stop the application
stop_app() {
    log_info "Stopping aWeatherStation server..."
    
    if ! is_running; then
        log_warning "Server is not running"
        return 0
    fi
    
    local pid=$(cat "$PID_FILE")
    log_info "Sending SIGTERM to process $pid..."
    
    # Try graceful shutdown first
    if kill "$pid" 2>/dev/null; then
        # Wait up to 10 seconds for graceful shutdown
        local count=0
        while [ $count -lt 10 ] && ps -p "$pid" > /dev/null 2>&1; do
            sleep 1
            count=$((count + 1))
        done
        
        # Check if process is still running
        if ps -p "$pid" > /dev/null 2>&1; then
            log_warning "Process didn't terminate gracefully, sending SIGKILL..."
            kill -9 "$pid" 2>/dev/null || true
            sleep 2
        fi
        
        # Clean up PID file
        rm -f "$PID_FILE"
        
        log_success "aWeatherStation server stopped"
        return 0
    else
        log_error "Failed to stop process $pid"
        # Clean up stale PID file anyway
        rm -f "$PID_FILE"
        return 1
    fi
}

# Restart the application
restart_app() {
    log_info "Restarting aWeatherStation server..."
    
    if is_running; then
        stop_app
        if [ $? -ne 0 ]; then
            log_error "Failed to stop server, aborting restart"
            return 1
        fi
    fi
    
    # Wait a moment between stop and start
    sleep 2
    
    start_app
    return $?
}

# Show logs
show_logs() {
    local lines=${1:-50}  # Default to 50 lines
    
    if [ ! -f "$LOG_FILE" ]; then
        log_warning "No log file found at $LOG_FILE"
        return 1
    fi
    
    log_info "Showing last $lines lines from $LOG_FILE:"
    echo "----------------------------------------"
    tail -n "$lines" "$LOG_FILE"
    echo "----------------------------------------"
}

# Follow logs in real-time
follow_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        log_warning "No log file found at $LOG_FILE"
        return 1
    fi
    
    log_info "Following logs from $LOG_FILE (Ctrl+C to exit):"
    echo "----------------------------------------"
    tail -f "$LOG_FILE"
}

# Test the application
test_app() {
    log_info "Testing aWeatherStation server..."
    
    if ! is_running; then
        log_error "Server is not running. Please start it first."
        return 1
    fi
    
    # Test GraphQL endpoint
    log_info "Testing GraphQL endpoint..."
    
    # Simple health check query
    local health_query='{"query": "{ health { status timestamp database } }"}'
    
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$health_query" \
        http://localhost:5000/graphql \
        --connect-timeout 5 \
        --max-time 10 || echo "CURL_FAILED")
    
    if [ "$response" = "CURL_FAILED" ]; then
        log_error "Failed to connect to GraphQL endpoint"
        return 1
    fi
    
    # Check if response contains expected data
    if echo "$response" | grep -q '"status":"ok"'; then
        log_success "GraphQL endpoint is responding correctly"
        log_info "Health check response: $response"
    else
        log_error "GraphQL endpoint returned unexpected response: $response"
        return 1
    fi
    
    # Test SSE endpoint
    log_info "Testing SSE endpoint..."
    
    local sse_test=$(timeout 3 curl -s http://localhost:5000/events || echo "SSE_TIMEOUT")
    
    if [ "$sse_test" = "SSE_TIMEOUT" ]; then
        log_warning "SSE endpoint test timed out (this might be normal)"
    else
        log_success "SSE endpoint is accessible"
    fi
    
    log_success "Server tests completed successfully!"
    return 0
}

# Show usage information
show_usage() {
    echo "aWeatherStation Process Management Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start          Start the aWeatherStation server"
    echo "  stop           Stop the aWeatherStation server"
    echo "  restart        Restart the aWeatherStation server"
    echo "  status         Show server status"
    echo "  logs [LINES]   Show last N lines of logs (default: 50)"
    echo "  follow         Follow logs in real-time"
    echo "  test           Test server endpoints"
    echo "  help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start the server"
    echo "  $0 status             # Check if server is running"
    echo "  $0 logs 100           # Show last 100 log lines"
    echo "  $0 restart            # Restart the server"
    echo ""
    echo "Server URLs (when running):"
    echo "  Frontend:    http://192.168.50.2:5000/"
    echo "  GraphQL:     http://192.168.50.2:5000/graphql"
    echo "  SSE Events:  http://192.168.50.2:5000/events"
    echo ""
    echo "Log file: $LOG_FILE"
    echo "PID file: $PID_FILE"
}

# Main script logic
case "${1:-}" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        get_status
        ;;
    logs)
        show_logs "${2:-50}"
        ;;
    follow)
        follow_logs
        ;;
    test)
        test_app
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "Unknown command: ${1:-}"
        echo ""
        show_usage
        exit 1
        ;;
esac

exit $?
