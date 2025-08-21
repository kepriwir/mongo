#!/bin/bash

# MongoDB Replication Automation - Master Script
# Author: AI Generator
# Version: 1.0
# Description: Complete automation script for MongoDB replication setup, data generation, and monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="accounts.json"
LOG_FILE="automation_master.log"
DASHBOARD_PORT=5000
DASHBOARD_HOST="0.0.0.0"

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a $LOG_FILE
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a $LOG_FILE
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a $LOG_FILE
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a $LOG_FILE
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}" | tee -a $LOG_FILE
}

step() {
    echo -e "${PURPLE}[STEP] $1${NC}" | tee -a $LOG_FILE
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Please run as a regular user with sudo privileges."
    fi
}

# Check dependencies
check_dependencies() {
    step "Checking system dependencies..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        error "pip3 is required but not installed"
    fi
    
    # Check SSH
    if ! command -v ssh &> /dev/null; then
        error "SSH client is required but not installed"
    fi
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        log "Installing jq..."
        sudo apt-get update
        sudo apt-get install -y jq
    fi
    
    success "All system dependencies are available"
}

# Install Python dependencies
install_python_deps() {
    step "Installing Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt
        success "Python dependencies installed successfully"
    else
        error "requirements.txt not found"
    fi
}

# Check configuration file
check_config() {
    step "Checking configuration file..."
    
    if [ ! -f "$CONFIG_FILE" ]; then
        error "Configuration file $CONFIG_FILE not found"
    fi
    
    # Validate JSON format
    if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
        error "Invalid JSON format in $CONFIG_FILE"
    fi
    
    # Check required fields
    local config=$(cat "$CONFIG_FILE")
    
    # Check if nodes array exists and has at least 3 nodes
    local node_count=$(echo "$config" | jq '.nodes | length')
    if [ "$node_count" -lt 3 ]; then
        error "At least 3 nodes are required in configuration"
    fi
    
    # Check if primary node exists
    local primary_count=$(echo "$config" | jq '.nodes[] | select(.role == "primary") | length')
    if [ "$primary_count" -eq 0 ]; then
        error "No primary node found in configuration"
    fi
    
    success "Configuration file is valid"
}

# Test SSH connections
test_ssh_connections() {
    step "Testing SSH connections to all nodes..."
    
    local config=$(cat "$CONFIG_FILE")
    local failed_connections=0
    
    while IFS= read -r node; do
        local ip=$(echo "$node" | jq -r '.ip')
        local ssh_user=$(echo "$node" | jq -r '.ssh_user')
        local ssh_key_path=$(echo "$node" | jq -r '.ssh_key_path')
        local hostname=$(echo "$node" | jq -r '.hostname')
        
        log "Testing SSH connection to $hostname ($ip)..."
        
        if ssh -i "$ssh_key_path" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$ssh_user@$ip" "echo 'SSH connection successful'" &>/dev/null; then
            success "SSH connection to $hostname ($ip) successful"
        else
            warning "SSH connection to $hostname ($ip) failed"
            failed_connections=$((failed_connections + 1))
        fi
    done < <(echo "$config" | jq -c '.nodes[]')
    
    if [ $failed_connections -gt 0 ]; then
        error "$failed_connections SSH connection(s) failed. Please check your SSH configuration."
    fi
    
    success "All SSH connections tested successfully"
}

# Install MongoDB and setup replication
install_mongodb() {
    step "Installing MongoDB and setting up replication..."
    
    if [ ! -f "install_mongodb.sh" ]; then
        error "install_mongodb.sh script not found"
    fi
    
    chmod +x install_mongodb.sh
    
    log "Running MongoDB installation script..."
    if ./install_mongodb.sh; then
        success "MongoDB installation and replication setup completed"
    else
        error "MongoDB installation failed. Check mongodb_setup.log for details."
    fi
}

# Generate dummy data
generate_data() {
    step "Generating dummy HR management data..."
    
    if [ ! -f "generate_dummy_data.py" ]; then
        error "generate_dummy_data.py script not found"
    fi
    
    # Ask user for data generation parameters
    echo -e "${CYAN}Data Generation Configuration:${NC}"
    read -p "Number of companies (default: 100): " num_companies
    num_companies=${num_companies:-100}
    
    read -p "Employees per company (default: 50): " employees_per_company
    employees_per_company=${employees_per_company:-50}
    
    read -p "Save to MongoDB? (y/n, default: y): " save_to_mongodb
    save_to_mongodb=${save_to_mongodb:-y}
    
    log "Generating data for $num_companies companies with $employees_per_company employees each..."
    
    if [ "$save_to_mongodb" = "y" ] || [ "$save_to_mongodb" = "Y" ]; then
        python3 generate_dummy_data.py --companies "$num_companies" --employees "$employees_per_company" --mongodb
    else
        python3 generate_dummy_data.py --companies "$num_companies" --employees "$employees_per_company" --output "hr_dummy_data.json"
    fi
    
    success "Data generation completed"
}

# Run load testing
run_load_test() {
    step "Running load testing..."
    
    if [ ! -f "load_testing.py" ]; then
        error "load_testing.py script not found"
    fi
    
    # Ask user for load testing parameters
    echo -e "${CYAN}Load Testing Configuration:${NC}"
    read -p "Read threads (default: 10): " read_threads
    read_threads=${read_threads:-10}
    
    read -p "Write threads (default: 5): " write_threads
    write_threads=${write_threads:-5}
    
    read -p "Analytics threads (default: 3): " analytics_threads
    analytics_threads=${analytics_threads:-3}
    
    read -p "Test duration in seconds (default: 60): " duration
    duration=${duration:-60}
    
    log "Running load test with $read_threads read threads, $write_threads write threads, $analytics_threads analytics threads for $duration seconds..."
    
    python3 load_testing.py --read-threads "$read_threads" --write-threads "$write_threads" --analytics-threads "$analytics_threads" --duration "$duration"
    
    success "Load testing completed. Results saved to load_test_results.json"
}

# Start web dashboard
start_dashboard() {
    step "Starting web dashboard..."
    
    if [ ! -f "web_dashboard.py" ]; then
        error "web_dashboard.py script not found"
    fi
    
    # Check if port is available
    if netstat -tlnp 2>/dev/null | grep -q ":$DASHBOARD_PORT "; then
        warning "Port $DASHBOARD_PORT is already in use. Dashboard may not start properly."
    fi
    
    log "Starting web dashboard on http://$DASHBOARD_HOST:$DASHBOARD_PORT"
    log "Press Ctrl+C to stop the dashboard"
    
    # Start dashboard in background
    python3 web_dashboard.py --host "$DASHBOARD_HOST" --port "$DASHBOARD_PORT" &
    local dashboard_pid=$!
    
    # Wait a moment for dashboard to start
    sleep 3
    
    # Check if dashboard is running
    if kill -0 $dashboard_pid 2>/dev/null; then
        success "Web dashboard started successfully (PID: $dashboard_pid)"
        log "Dashboard URL: http://$DASHBOARD_HOST:$DASHBOARD_PORT"
        log "Dashboard PID: $dashboard_pid"
        
        # Save PID for later cleanup
        echo $dashboard_pid > dashboard.pid
        
        return 0
    else
        error "Failed to start web dashboard"
    fi
}

# Stop web dashboard
stop_dashboard() {
    if [ -f "dashboard.pid" ]; then
        local dashboard_pid=$(cat dashboard.pid)
        if kill -0 $dashboard_pid 2>/dev/null; then
            log "Stopping web dashboard (PID: $dashboard_pid)..."
            kill $dashboard_pid
            rm -f dashboard.pid
            success "Web dashboard stopped"
        fi
    fi
}

# Show system status
show_status() {
    step "Checking system status..."
    
    local config=$(cat "$CONFIG_FILE")
    
    echo -e "\n${CYAN}=== MongoDB Replication Status ===${NC}"
    
    # Check each node
    while IFS= read -r node; do
        local ip=$(echo "$node" | jq -r '.ip')
        local hostname=$(echo "$node" | jq -r '.hostname')
        local role=$(echo "$node" | jq -r '.role')
        
        log "Checking $hostname ($ip) - $role..."
        
        # Test MongoDB connection
        if mongo --host "$ip:27017" --eval "db.runCommand('ping')" &>/dev/null; then
            success "MongoDB on $hostname is running"
        else
            warning "MongoDB on $hostname is not responding"
        fi
    done < <(echo "$config" | jq -c '.nodes[]')
    
    # Check replica set status
    local primary_node=$(echo "$config" | jq -r '.nodes[] | select(.role == "primary") | .ip')
    if [ -n "$primary_node" ]; then
        log "Checking replica set status..."
        mongo --host "$primary_node:27017" --eval "rs.status()" 2>/dev/null || warning "Could not get replica set status"
    fi
    
    # Check dashboard status
    if [ -f "dashboard.pid" ]; then
        local dashboard_pid=$(cat dashboard.pid)
        if kill -0 $dashboard_pid 2>/dev/null; then
            success "Web dashboard is running (PID: $dashboard_pid)"
        else
            warning "Web dashboard is not running"
        fi
    else
        info "Web dashboard is not running"
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up..."
    stop_dashboard
    exit 0
}

# Main menu
show_menu() {
    echo -e "\n${CYAN}=== MongoDB Replication Automation System ===${NC}"
    echo "1. Install MongoDB and Setup Replication"
    echo "2. Generate Dummy Data"
    echo "3. Run Load Testing"
    echo "4. Start Web Dashboard"
    echo "5. Stop Web Dashboard"
    echo "6. Show System Status"
    echo "7. Run Complete Setup (1-4)"
    echo "8. Exit"
    echo -e "${CYAN}===============================================${NC}"
}

# Main execution
main() {
    # Set up signal handlers
    trap cleanup SIGINT SIGTERM
    
    log "Starting MongoDB Replication Automation System"
    
    # Check if not running as root
    check_root
    
    # Check dependencies
    check_dependencies
    
    # Install Python dependencies
    install_python_deps
    
    # Check configuration
    check_config
    
    # Test SSH connections
    test_ssh_connections
    
    # Main menu loop
    while true; do
        show_menu
        read -p "Select an option (1-8): " choice
        
        case $choice in
            1)
                install_mongodb
                ;;
            2)
                generate_data
                ;;
            3)
                run_load_test
                ;;
            4)
                start_dashboard
                ;;
            5)
                stop_dashboard
                ;;
            6)
                show_status
                ;;
            7)
                log "Running complete setup..."
                install_mongodb
                generate_data
                run_load_test
                start_dashboard
                success "Complete setup finished!"
                log "System is ready. Dashboard available at http://$DASHBOARD_HOST:$DASHBOARD_PORT"
                ;;
            8)
                log "Exiting..."
                cleanup
                ;;
            *)
                warning "Invalid option. Please select 1-8."
                ;;
        esac
        
        echo -e "\nPress Enter to continue..."
        read
    done
}

# Check if script is being sourced or run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi