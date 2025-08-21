#!/bin/bash

# MongoDB Replication Management System - Master Runner
# Author: AI Generator
# Version: 1.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="accounts.json"
LOG_DIR="logs"
PID_DIR="pids"

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check dependencies
check_dependencies() {
    log "Checking system dependencies..."
    
    local deps=("python3" "pip3" "jq" "ssh" "scp" "wget" "curl")
    for dep in "${deps[@]}"; do
        if ! command -v $dep &> /dev/null; then
            error "$dep is required but not installed"
        fi
    done
    
    log "All system dependencies are available"
}

# Install Python dependencies
install_python_deps() {
    log "Installing Python dependencies..."
    
    if [[ ! -f "requirements.txt" ]]; then
        error "requirements.txt not found"
    fi
    
    pip3 install -r requirements.txt
    
    log "Python dependencies installed successfully"
}

# Create necessary directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p $LOG_DIR
    mkdir -p $PID_DIR
    
    log "Directories created successfully"
}

# Check configuration
check_config() {
    log "Checking configuration..."
    
    if [[ ! -f $CONFIG_FILE ]]; then
        error "Configuration file $CONFIG_FILE not found"
    fi
    
    # Validate JSON
    if ! jq empty $CONFIG_FILE 2>/dev/null; then
        error "Invalid JSON in $CONFIG_FILE"
    fi
    
    # Check required fields
    local required_fields=("nodes" "replica_set_name" "database_name")
    for field in "${required_fields[@]}"; do
        if ! jq -e ".$field" $CONFIG_FILE >/dev/null 2>&1; then
            error "Missing required field: $field in $CONFIG_FILE"
        fi
    done
    
    log "Configuration validated successfully"
}

# Install MongoDB on all nodes
install_mongodb() {
    log "Installing MongoDB on all nodes..."
    
    if [[ ! -f "install_mongodb.sh" ]]; then
        error "install_mongodb.sh not found"
    fi
    
    chmod +x install_mongodb.sh
    ./install_mongodb.sh
    
    log "MongoDB installation completed"
}

# Generate dummy data
generate_data() {
    log "Generating dummy HR data..."
    
    if [[ ! -f "generate_dummy_data.py" ]]; then
        error "generate_dummy_data.py not found"
    fi
    
    python3 generate_dummy_data.py
    
    log "Data generation completed"
}

# Run load testing
run_load_test() {
    log "Running load testing..."
    
    if [[ ! -f "load_testing.py" ]]; then
        error "load_testing.py not found"
    fi
    
    # Run load test with default parameters
    python3 load_testing.py --threads 20 --duration 120 --output "load_test_results.csv"
    
    log "Load testing completed"
}

# Start web dashboard
start_dashboard() {
    log "Starting web dashboard..."
    
    if [[ ! -f "web_dashboard.py" ]]; then
        error "web_dashboard.py not found"
    fi
    
    # Start dashboard in background
    nohup python3 web_dashboard.py > $LOG_DIR/dashboard.log 2>&1 &
    echo $! > $PID_DIR/dashboard.pid
    
    log "Web dashboard started (PID: $(cat $PID_DIR/dashboard.pid))"
    log "Access dashboard at: http://localhost:5000"
}

# Stop web dashboard
stop_dashboard() {
    if [[ -f $PID_DIR/dashboard.pid ]]; then
        local pid=$(cat $PID_DIR/dashboard.pid)
        if kill -0 $pid 2>/dev/null; then
            log "Stopping web dashboard (PID: $pid)..."
            kill $pid
            rm $PID_DIR/dashboard.pid
            log "Web dashboard stopped"
        else
            warn "Dashboard process not running"
        fi
    else
        warn "Dashboard PID file not found"
    fi
}

# Show status
show_status() {
    log "System Status:"
    echo "=================="
    
    # Check dashboard
    if [[ -f $PID_DIR/dashboard.pid ]]; then
        local pid=$(cat $PID_DIR/dashboard.pid)
        if kill -0 $pid 2>/dev/null; then
            echo "✓ Web Dashboard: Running (PID: $pid)"
        else
            echo "✗ Web Dashboard: Not running"
        fi
    else
        echo "✗ Web Dashboard: Not started"
    fi
    
    # Check MongoDB nodes
    if [[ -f $CONFIG_FILE ]]; then
        echo ""
        echo "MongoDB Nodes:"
        jq -r '.nodes[] | "  \(.hostname) (\(.ip)) - \(.role)"' $CONFIG_FILE
    fi
    
    # Show recent logs
    if [[ -d $LOG_DIR ]]; then
        echo ""
        echo "Recent Logs:"
        ls -la $LOG_DIR/ 2>/dev/null || echo "  No logs found"
    fi
}

# Cleanup
cleanup() {
    log "Cleaning up..."
    
    # Stop dashboard
    stop_dashboard
    
    # Remove PID files
    rm -f $PID_DIR/*.pid
    
    log "Cleanup completed"
}

# Show help
show_help() {
    echo "MongoDB Replication Management System"
    echo "====================================="
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install     - Install MongoDB on all nodes and setup replication"
    echo "  data        - Generate dummy HR data"
    echo "  test        - Run load testing"
    echo "  dashboard   - Start web dashboard"
    echo "  stop        - Stop web dashboard"
    echo "  status      - Show system status"
    echo "  cleanup     - Clean up processes and temporary files"
    echo "  all         - Run complete setup (install + data + dashboard)"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 install     # Install MongoDB on all nodes"
    echo "  $0 all         # Complete setup and start dashboard"
    echo "  $0 status      # Check system status"
    echo ""
}

# Main execution
main() {
    case "${1:-help}" in
        "install")
            check_dependencies
            install_python_deps
            setup_directories
            check_config
            install_mongodb
            ;;
        "data")
            check_config
            generate_data
            ;;
        "test")
            check_config
            run_load_test
            ;;
        "dashboard")
            check_config
            start_dashboard
            ;;
        "stop")
            stop_dashboard
            ;;
        "status")
            show_status
            ;;
        "cleanup")
            cleanup
            ;;
        "all")
            check_dependencies
            install_python_deps
            setup_directories
            check_config
            install_mongodb
            generate_data
            start_dashboard
            log "Complete setup finished!"
            log "Access dashboard at: http://localhost:5000"
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Handle Ctrl+C
trap cleanup EXIT

# Run main function
main "$@"