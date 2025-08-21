#!/bin/bash

# MongoDB Cluster Production Deployment Script
# Master deployment script for complete MongoDB cluster setup

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config/accounts.json"
LOG_FILE="/var/log/mongodb-cluster-deployment.log"
DEPLOYMENT_START_TIME=$(date +%s)

# Logging functions
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() { log "INFO" "${BLUE}$*${NC}"; }
log_warn() { log "WARN" "${YELLOW}$*${NC}"; }
log_error() { log "ERROR" "${RED}$*${NC}"; }
log_success() { log "SUCCESS" "${GREEN}$*${NC}"; }
log_header() { log "HEADER" "${PURPLE}$*${NC}"; }

# Print banner
print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        MongoDB Cluster Production Deployment System         ║
║                                                              ║
║  ✓ Auto-installation & Configuration                        ║
║  ✓ 3-Node Replica Set Setup                                 ║
║  ✓ HR Management Data Generation                             ║
║  ✓ Load Testing & Performance Monitoring                    ║
║  ✓ Web Dashboard & Management Interface                     ║
║  ✓ Production-Ready Security & Logging                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Check prerequisites
check_prerequisites() {
    log_header "Checking Prerequisites"
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Check if configuration file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Check required commands
    local required_commands=("jq" "curl" "wget" "systemctl")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_warn "$cmd not found, will be installed"
        else
            log_info "✓ $cmd found"
        fi
    done
    
    # Check network connectivity
    if ping -c 1 google.com &> /dev/null; then
        log_info "✓ Network connectivity confirmed"
    else
        log_warn "Network connectivity check failed"
    fi
    
    # Check available disk space
    local available_space=$(df / | awk 'NR==2 {print $4}')
    local required_space=5242880  # 5GB in KB
    
    if [[ $available_space -gt $required_space ]]; then
        log_info "✓ Sufficient disk space available ($(($available_space / 1024 / 1024))GB)"
    else
        log_error "Insufficient disk space. Required: 5GB, Available: $(($available_space / 1024 / 1024))GB"
        exit 1
    fi
    
    log_success "Prerequisites check completed"
}

# Install system dependencies
install_dependencies() {
    log_header "Installing System Dependencies"
    
    # Update package list
    log_info "Updating package lists..."
    apt-get update -y
    
    # Install required packages
    local packages=(
        "curl" "wget" "jq" "git" "htop" "iotop" "nethogs"
        "python3" "python3-pip" "python3-venv"
        "nodejs" "npm"
        "logrotate" "rsyslog"
        "ufw" "fail2ban"
        "software-properties-common" "apt-transport-https" "ca-certificates"
    )
    
    log_info "Installing required packages..."
    apt-get install -y "${packages[@]}"
    
    # Install Python packages
    log_info "Installing Python packages..."
    pip3 install --upgrade pip
    pip3 install -r data-generator/requirements.txt
    pip3 install -r load-testing/requirements.txt
    
    # Install Node.js packages for dashboard
    log_info "Installing Node.js packages..."
    cd dashboard
    npm install --production
    cd ..
    
    log_success "System dependencies installed"
}

# Deploy MongoDB cluster
deploy_mongodb_cluster() {
    log_header "Deploying MongoDB Cluster"
    
    log_info "Running MongoDB installation script..."
    if ./scripts/install_mongodb.sh; then
        log_success "MongoDB cluster deployed successfully"
    else
        log_error "MongoDB cluster deployment failed"
        exit 1
    fi
}

# Setup security
setup_security() {
    log_header "Setting up Security"
    
    # Configure firewall
    log_info "Configuring UFW firewall..."
    ufw --force enable
    
    # MongoDB ports
    ufw allow 27017/tcp comment "MongoDB"
    
    # Dashboard port
    ufw allow 3000/tcp comment "MongoDB Dashboard"
    
    # SSH
    ufw allow 22/tcp comment "SSH"
    
    # Configure fail2ban for MongoDB
    cat > /etc/fail2ban/jail.d/mongodb.conf << EOF
[mongodb]
enabled = true
port = 27017
filter = mongodb
logpath = /var/log/mongodb/mongod.log
maxretry = 5
bantime = 3600
findtime = 600
EOF
    
    # Create fail2ban filter for MongoDB
    cat > /etc/fail2ban/filter.d/mongodb.conf << EOF
[Definition]
failregex = ^.*\[conn\d+\] authenticate db: admin \{ authenticate: 1, user: ".*", nonce: ".*", key: ".*" \} command failed with exception: AuthenticationFailed.*<HOST>.*$
ignoreregex =
EOF
    
    systemctl restart fail2ban
    
    # Set up SSL/TLS certificates (self-signed for demo)
    log_info "Generating SSL certificates..."
    mkdir -p /etc/ssl/mongodb
    openssl req -new -x509 -days 365 -nodes -out /etc/ssl/mongodb/mongodb.pem -keyout /etc/ssl/mongodb/mongodb.key -subj "/C=ID/ST=Jakarta/L=Jakarta/O=MongoDB Cluster/CN=mongodb-cluster"
    cat /etc/ssl/mongodb/mongodb.key /etc/ssl/mongodb/mongodb.pem > /etc/ssl/mongodb/mongodb-combined.pem
    chown -R mongodb:mongodb /etc/ssl/mongodb
    chmod 600 /etc/ssl/mongodb/*
    
    log_success "Security configuration completed"
}

# Setup logging and monitoring
setup_logging_monitoring() {
    log_header "Setting up Logging and Monitoring"
    
    # Setup logrotate
    log_info "Configuring log rotation..."
    if ./scripts/setup_logrotate.sh; then
        log_success "Log rotation configured"
    else
        log_warn "Log rotation setup had issues"
    fi
    
    # Create monitoring directories
    mkdir -p /var/log/mongodb-cluster/{monitoring,alerts,performance}
    chown -R mongodb:mongodb /var/log/mongodb-cluster
    
    # Setup performance monitoring script
    cat > /usr/local/bin/mongodb-performance-monitor.sh << 'EOF'
#!/bin/bash

# MongoDB Performance Monitoring Script
MONGO_URI="mongodb://admin:AdminPass123!@localhost:27017/admin"
LOG_FILE="/var/log/mongodb-cluster/performance/performance-$(date +%Y%m%d).log"

# Collect performance metrics
{
    echo "=== MongoDB Performance Metrics - $(date) ==="
    echo "Server Status:"
    mongosh "$MONGO_URI" --quiet --eval "printjson(db.serverStatus())" 2>/dev/null || echo "Failed to get server status"
    
    echo -e "\nDatabase Stats:"
    mongosh "$MONGO_URI" --quiet --eval "printjson(db.stats())" 2>/dev/null || echo "Failed to get database stats"
    
    echo -e "\nReplication Status:"
    mongosh "$MONGO_URI" --quiet --eval "printjson(rs.status())" 2>/dev/null || echo "Failed to get replication status"
    
    echo -e "\nTop Operations:"
    mongosh "$MONGO_URI" --quiet --eval "db.currentOp()" 2>/dev/null || echo "Failed to get current operations"
    
    echo -e "\n================================\n"
} >> "$LOG_FILE"
EOF
    
    chmod +x /usr/local/bin/mongodb-performance-monitor.sh
    
    # Add to crontab for regular monitoring
    (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/local/bin/mongodb-performance-monitor.sh") | crontab -
    
    log_success "Logging and monitoring configured"
}

# Generate sample data
generate_sample_data() {
    log_header "Generating Sample HR Data"
    
    log_info "This may take several minutes..."
    cd data-generator
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Generate data with smaller dataset for faster deployment
    if python3 generate_hr_data.py --companies 50 --employees-per-company 500 --months 6; then
        log_success "Sample HR data generated successfully"
    else
        log_warn "Sample data generation had issues, continuing..."
    fi
    
    deactivate
    cd ..
}

# Setup dashboard service
setup_dashboard_service() {
    log_header "Setting up Dashboard Service"
    
    # Create systemd service file
    cat > /etc/systemd/system/mongodb-dashboard.service << EOF
[Unit]
Description=MongoDB Cluster Dashboard
After=mongod.service
Wants=mongod.service

[Service]
Type=simple
User=mongodb
Group=mongodb
WorkingDirectory=${SCRIPT_DIR}/dashboard
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=10
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=DASHBOARD_USERNAME=admin
Environment=DASHBOARD_PASSWORD=admin123
Environment=JWT_SECRET=mongodb-cluster-jwt-secret-$(date +%s)

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${SCRIPT_DIR}

[Install]
WantedBy=multi-user.target
EOF
    
    # Set proper ownership
    chown -R mongodb:mongodb "${SCRIPT_DIR}/dashboard"
    
    # Enable and start service
    systemctl daemon-reload
    systemctl enable mongodb-dashboard
    systemctl start mongodb-dashboard
    
    # Wait for service to start
    sleep 5
    
    if systemctl is-active --quiet mongodb-dashboard; then
        log_success "Dashboard service started successfully"
    else
        log_error "Dashboard service failed to start"
        systemctl status mongodb-dashboard
        exit 1
    fi
}

# Run load tests
run_initial_load_tests() {
    log_header "Running Initial Load Tests"
    
    log_info "Running basic load tests to verify cluster performance..."
    cd load-testing
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Run light load test
    if python3 load_test_runner.py --threads 5 --operations 50 --test-type concurrent; then
        log_success "Initial load tests completed successfully"
    else
        log_warn "Load tests had issues, cluster may still be functional"
    fi
    
    deactivate
    cd ..
}

# Create management scripts
create_management_scripts() {
    log_header "Creating Management Scripts"
    
    # Cluster management script
    cat > /usr/local/bin/mongodb-cluster << 'EOF'
#!/bin/bash

# MongoDB Cluster Management Script

SCRIPT_DIR="/workspace/mongodb-cluster"
CONFIG_FILE="$SCRIPT_DIR/config/accounts.json"

show_usage() {
    echo "MongoDB Cluster Management Tool"
    echo ""
    echo "Usage: mongodb-cluster <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status          Show cluster status"
    echo "  start           Start all services"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services"
    echo "  logs            Show MongoDB logs"
    echo "  dashboard       Show dashboard URL and credentials"
    echo "  backup          Create cluster backup"
    echo "  load-test       Run load tests"
    echo "  generate-data   Generate sample data"
    echo ""
}

show_status() {
    echo "=== MongoDB Cluster Status ==="
    echo ""
    echo "MongoDB Service:"
    systemctl status mongod --no-pager -l
    echo ""
    echo "Dashboard Service:"
    systemctl status mongodb-dashboard --no-pager -l
    echo ""
    echo "Replica Set Status:"
    mongosh "mongodb://admin:AdminPass123!@localhost:27017/admin" --quiet --eval "rs.status()" 2>/dev/null || echo "Failed to connect to replica set"
}

start_services() {
    echo "Starting MongoDB Cluster services..."
    systemctl start mongod
    systemctl start mongodb-dashboard
    echo "Services started"
}

stop_services() {
    echo "Stopping MongoDB Cluster services..."
    systemctl stop mongodb-dashboard
    systemctl stop mongod
    echo "Services stopped"
}

restart_services() {
    echo "Restarting MongoDB Cluster services..."
    systemctl restart mongod
    systemctl restart mongodb-dashboard
    echo "Services restarted"
}

show_logs() {
    echo "=== MongoDB Logs ==="
    tail -50 /var/log/mongodb/mongod.log
    echo ""
    echo "=== Dashboard Logs ==="
    journalctl -u mongodb-dashboard -n 20 --no-pager
}

show_dashboard() {
    local ip_address=$(hostname -I | awk '{print $1}')
    echo "=== MongoDB Cluster Dashboard ==="
    echo ""
    echo "URL: http://$ip_address:3000"
    echo "Username: admin"
    echo "Password: admin123"
    echo ""
    echo "Dashboard Status:"
    systemctl status mongodb-dashboard --no-pager -l
}

create_backup() {
    local backup_dir="/var/backups/mongodb-cluster/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    echo "Creating MongoDB cluster backup in $backup_dir..."
    
    # Backup each database
    mongodump --uri "mongodb://admin:AdminPass123!@localhost:27017" --out "$backup_dir/dump"
    
    # Backup configuration
    cp "$CONFIG_FILE" "$backup_dir/"
    
    # Create archive
    cd /var/backups/mongodb-cluster
    tar -czf "mongodb-backup-$(date +%Y%m%d_%H%M%S).tar.gz" "$(basename $backup_dir)"
    rm -rf "$backup_dir"
    
    echo "Backup completed: /var/backups/mongodb-cluster/mongodb-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
}

run_load_test() {
    echo "Running MongoDB load tests..."
    cd "$SCRIPT_DIR/load-testing"
    python3 load_test_runner.py --threads 10 --operations 100
}

generate_data() {
    echo "Generating sample HR data..."
    cd "$SCRIPT_DIR/data-generator"
    python3 generate_hr_data.py --companies 10 --employees-per-company 100 --months 3
}

case "${1:-}" in
    status)
        show_status
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    dashboard)
        show_dashboard
        ;;
    backup)
        create_backup
        ;;
    load-test)
        run_load_test
        ;;
    generate-data)
        generate_data
        ;;
    *)
        show_usage
        ;;
esac
EOF
    
    chmod +x /usr/local/bin/mongodb-cluster
    
    # Create health check script
    cat > /usr/local/bin/mongodb-health-check << 'EOF'
#!/bin/bash

# MongoDB Cluster Health Check Script

check_mongodb() {
    if systemctl is-active --quiet mongod; then
        echo "✓ MongoDB service is running"
    else
        echo "✗ MongoDB service is not running"
        return 1
    fi
    
    # Check if MongoDB is responding
    if mongosh "mongodb://admin:AdminPass123!@localhost:27017/admin" --quiet --eval "db.runCommand('ping')" &>/dev/null; then
        echo "✓ MongoDB is responding to connections"
    else
        echo "✗ MongoDB is not responding"
        return 1
    fi
    
    # Check replica set status
    local rs_status=$(mongosh "mongodb://admin:AdminPass123!@localhost:27017/admin" --quiet --eval "rs.status().ok" 2>/dev/null)
    if [[ "$rs_status" == "1" ]]; then
        echo "✓ Replica set is healthy"
    else
        echo "✗ Replica set has issues"
        return 1
    fi
}

check_dashboard() {
    if systemctl is-active --quiet mongodb-dashboard; then
        echo "✓ Dashboard service is running"
    else
        echo "✗ Dashboard service is not running"
        return 1
    fi
    
    # Check if dashboard is responding
    if curl -s http://localhost:3000 >/dev/null; then
        echo "✓ Dashboard is responding"
    else
        echo "✗ Dashboard is not responding"
        return 1
    fi
}

check_disk_space() {
    local usage=$(df /var/lib/mongodb | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $usage -lt 80 ]]; then
        echo "✓ Disk space is adequate ($usage% used)"
    else
        echo "⚠ Disk space is getting low ($usage% used)"
        if [[ $usage -gt 90 ]]; then
            return 1
        fi
    fi
}

main() {
    echo "=== MongoDB Cluster Health Check ==="
    echo "Timestamp: $(date)"
    echo ""
    
    local exit_code=0
    
    if ! check_mongodb; then
        exit_code=1
    fi
    
    if ! check_dashboard; then
        exit_code=1
    fi
    
    if ! check_disk_space; then
        exit_code=1
    fi
    
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        echo "✓ All health checks passed"
    else
        echo "✗ Some health checks failed"
    fi
    
    exit $exit_code
}

main "$@"
EOF
    
    chmod +x /usr/local/bin/mongodb-health-check
    
    # Add health check to crontab
    (crontab -l 2>/dev/null; echo "*/10 * * * * /usr/local/bin/mongodb-health-check >> /var/log/mongodb-health.log 2>&1") | crontab -
    
    log_success "Management scripts created"
}

# Print deployment summary
print_deployment_summary() {
    local deployment_end_time=$(date +%s)
    local deployment_duration=$((deployment_end_time - DEPLOYMENT_START_TIME))
    local ip_address=$(hostname -I | awk '{print $1}')
    
    log_header "Deployment Summary"
    
    echo -e "${GREEN}"
    cat << EOF

╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║          MongoDB Cluster Deployment Completed!              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Deployment Duration: $(($deployment_duration / 60)) minutes $(($deployment_duration % 60)) seconds

🌐 Web Dashboard:
   URL: http://$ip_address:3000
   Username: admin
   Password: admin123

🔧 Management Commands:
   mongodb-cluster status      - Show cluster status
   mongodb-cluster dashboard   - Show dashboard info
   mongodb-cluster backup      - Create backup
   mongodb-cluster logs        - View logs

📊 Services Running:
   ✓ MongoDB Replica Set (Port 27017)
   ✓ Web Dashboard (Port 3000)
   ✓ Log Rotation & Monitoring
   ✓ Performance Monitoring
   ✓ Health Checks

📁 Important Directories:
   Configuration: $SCRIPT_DIR/config/
   Logs: /var/log/mongodb/
   Data: /var/lib/mongodb/
   Backups: /var/backups/mongodb-cluster/

🔐 Security:
   ✓ Firewall configured
   ✓ Fail2ban enabled
   ✓ SSL certificates generated
   ✓ Authentication enabled

📈 Load Testing:
   Run: cd $SCRIPT_DIR/load-testing && python3 load_test_runner.py
   Web UI: python3 locustfile.py (Port 8089)

🎯 Next Steps:
   1. Access the web dashboard
   2. Review cluster status
   3. Run load tests
   4. Generate additional sample data
   5. Configure monitoring alerts

For support and documentation:
   Health Check: mongodb-health-check
   Logs: mongodb-cluster logs
   Status: mongodb-cluster status

EOF
    echo -e "${NC}"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f /tmp/mongodb-*.log
    rm -f /tmp/logrotate-test-*.log
}

# Error handling
handle_error() {
    local line_number=$1
    log_error "Deployment failed at line $line_number"
    log_error "Check $LOG_FILE for detailed error information"
    cleanup
    exit 1
}

# Main deployment function
main() {
    # Set up error handling
    trap 'handle_error $LINENO' ERR
    trap cleanup EXIT
    
    print_banner
    
    log_info "Starting MongoDB Cluster deployment..."
    log_info "Deployment log: $LOG_FILE"
    
    check_prerequisites
    install_dependencies
    deploy_mongodb_cluster
    setup_security
    setup_logging_monitoring
    generate_sample_data
    setup_dashboard_service
    run_initial_load_tests
    create_management_scripts
    
    print_deployment_summary
    
    log_success "MongoDB Cluster deployment completed successfully!"
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi