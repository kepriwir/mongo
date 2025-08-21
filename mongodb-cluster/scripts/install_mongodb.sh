#!/bin/bash

# MongoDB Auto-Installation and Replication Setup Script
# Production-ready MongoDB cluster deployment with 3-node replication

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/../config/accounts.json"
LOG_FILE="/var/log/mongodb-cluster-install.log"

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    log "INFO" "${BLUE}$*${NC}"
}

log_warn() {
    log "WARN" "${YELLOW}$*${NC}"
}

log_error() {
    log "ERROR" "${RED}$*${NC}"
}

log_success() {
    log "SUCCESS" "${GREEN}$*${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Check if MongoDB is already installed
check_mongodb_installed() {
    if command -v mongod &> /dev/null; then
        log_warn "MongoDB is already installed"
        return 0
    else
        log_info "MongoDB not found, proceeding with installation"
        return 1
    fi
}

# Install MongoDB
install_mongodb() {
    log_info "Starting MongoDB installation..."
    
    # Update system packages
    log_info "Updating system packages..."
    apt-get update -y
    apt-get upgrade -y
    
    # Install required packages
    log_info "Installing required packages..."
    apt-get install -y wget curl gnupg2 software-properties-common apt-transport-https ca-certificates lsb-release jq
    
    # Add MongoDB GPG key
    log_info "Adding MongoDB GPG key..."
    wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | apt-key add -
    
    # Add MongoDB repository
    log_info "Adding MongoDB repository..."
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    
    # Update package list
    apt-get update -y
    
    # Install MongoDB
    log_info "Installing MongoDB packages..."
    apt-get install -y mongodb-org mongodb-org-tools
    
    # Hold MongoDB packages to prevent accidental upgrades
    apt-mark hold mongodb-org mongodb-org-database mongodb-org-server mongodb-org-shell mongodb-org-mongos mongodb-org-tools
    
    log_success "MongoDB installation completed"
}

# Parse configuration from accounts.json
parse_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    log_info "Parsing configuration from $CONFIG_FILE"
    
    # Extract configuration values
    REPLICA_SET_NAME=$(jq -r '.mongodb_cluster.replica_set_name' "$CONFIG_FILE")
    DATA_DIR=$(jq -r '.mongodb_cluster.directories.data_dir' "$CONFIG_FILE")
    LOG_DIR=$(jq -r '.mongodb_cluster.directories.log_dir' "$CONFIG_FILE")
    CONFIG_DIR=$(jq -r '.mongodb_cluster.directories.config_dir' "$CONFIG_FILE")
    KEYFILE_PATH=$(jq -r '.mongodb_cluster.auth.keyfile_path' "$CONFIG_FILE")
    KEYFILE_CONTENT=$(jq -r '.mongodb_cluster.auth.keyfile_content' "$CONFIG_FILE")
    CACHE_SIZE_GB=$(jq -r '.mongodb_cluster.performance.cache_size_gb' "$CONFIG_FILE")
    MAX_CONNECTIONS=$(jq -r '.mongodb_cluster.performance.max_connections' "$CONFIG_FILE")
    OPLOG_SIZE_MB=$(jq -r '.mongodb_cluster.performance.oplog_size_mb' "$CONFIG_FILE")
    
    log_success "Configuration parsed successfully"
}

# Create MongoDB directories and keyfile
setup_directories() {
    log_info "Setting up MongoDB directories..."
    
    # Create directories
    mkdir -p "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"
    
    # Set ownership
    chown -R mongodb:mongodb "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"
    
    # Create keyfile for replica set authentication
    log_info "Creating replica set keyfile..."
    echo "$KEYFILE_CONTENT" > "$KEYFILE_PATH"
    chown mongodb:mongodb "$KEYFILE_PATH"
    chmod 600 "$KEYFILE_PATH"
    
    log_success "Directories and keyfile created"
}

# Get current node information
get_current_node_info() {
    local current_ip
    current_ip=$(hostname -I | awk '{print $1}')
    
    # Find current node in configuration
    local node_count
    node_count=$(jq '.mongodb_cluster.nodes | length' "$CONFIG_FILE")
    
    for ((i=0; i<node_count; i++)); do
        local node_ip
        node_ip=$(jq -r ".mongodb_cluster.nodes[$i].ip" "$CONFIG_FILE")
        if [[ "$node_ip" == "$current_ip" ]]; then
            CURRENT_NODE_ID=$i
            CURRENT_NODE_IP=$node_ip
            CURRENT_NODE_PORT=$(jq -r ".mongodb_cluster.nodes[$i].port" "$CONFIG_FILE")
            CURRENT_NODE_ROLE=$(jq -r ".mongodb_cluster.nodes[$i].role" "$CONFIG_FILE")
            CURRENT_NODE_PRIORITY=$(jq -r ".mongodb_cluster.nodes[$i].priority" "$CONFIG_FILE")
            log_info "Current node detected: ID=$CURRENT_NODE_ID, IP=$CURRENT_NODE_IP, Role=$CURRENT_NODE_ROLE"
            return 0
        fi
    done
    
    log_error "Current node not found in configuration"
    exit 1
}

# Generate MongoDB configuration file
generate_mongod_config() {
    log_info "Generating MongoDB configuration file..."
    
    local config_file="/etc/mongod.conf"
    
    cat > "$config_file" << EOF
# MongoDB configuration file for replica set node
# Generated by MongoDB cluster installation script

# Network interfaces
net:
  port: $CURRENT_NODE_PORT
  bindIp: 0.0.0.0
  maxIncomingConnections: $MAX_CONNECTIONS

# Storage
storage:
  dbPath: $DATA_DIR
  journal:
    enabled: true
  wiredTiger:
    engineConfig:
      cacheSizeGB: $CACHE_SIZE_GB

# System log
systemLog:
  destination: file
  logAppend: true
  path: $LOG_DIR/mongod.log
  logRotate: reopen

# Process management
processManagement:
  fork: true
  pidFilePath: /var/run/mongodb/mongod.pid
  timeZoneInfo: /usr/share/zoneinfo

# Security
security:
  authorization: enabled
  keyFile: $KEYFILE_PATH

# Replication
replication:
  replSetName: $REPLICA_SET_NAME
  oplogSizeMB: $OPLOG_SIZE_MB

# Sharding (disabled for replica set)
#sharding:

# Enterprise-Only Options:
#auditLog:
#snmp:
EOF
    
    chown mongodb:mongodb "$config_file"
    log_success "MongoDB configuration file created"
}

# Start MongoDB service
start_mongodb() {
    log_info "Starting MongoDB service..."
    
    # Enable and start MongoDB service
    systemctl enable mongod
    systemctl start mongod
    
    # Wait for MongoDB to start
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if systemctl is-active --quiet mongod && mongod --version &>/dev/null; then
            log_success "MongoDB service started successfully"
            return 0
        fi
        
        log_info "Waiting for MongoDB to start... (attempt $((attempt + 1))/$max_attempts)"
        sleep 5
        ((attempt++))
    done
    
    log_error "Failed to start MongoDB service"
    exit 1
}

# Initialize replica set (only on primary node)
initialize_replica_set() {
    if [[ "$CURRENT_NODE_ROLE" != "primary" ]]; then
        log_info "Skipping replica set initialization (not primary node)"
        return 0
    fi
    
    log_info "Initializing replica set on primary node..."
    
    # Wait for MongoDB to be ready
    sleep 10
    
    # Generate replica set configuration
    local rs_config
    rs_config=$(cat << EOF
rs.initiate({
  _id: "$REPLICA_SET_NAME",
  members: [
EOF
    )
    
    # Add all nodes to replica set configuration
    local node_count
    node_count=$(jq '.mongodb_cluster.nodes | length' "$CONFIG_FILE")
    
    for ((i=0; i<node_count; i++)); do
        local node_ip node_port node_priority
        node_ip=$(jq -r ".mongodb_cluster.nodes[$i].ip" "$CONFIG_FILE")
        node_port=$(jq -r ".mongodb_cluster.nodes[$i].port" "$CONFIG_FILE")
        node_priority=$(jq -r ".mongodb_cluster.nodes[$i].priority" "$CONFIG_FILE")
        
        rs_config+="    { _id: $i, host: \"$node_ip:$node_port\", priority: $node_priority }"
        
        if [[ $i -lt $((node_count - 1)) ]]; then
            rs_config+=","
        fi
        rs_config+=$'\n'
    done
    
    rs_config+="  ]"$'\n'"});"
    
    # Initialize replica set
    echo "$rs_config" | mongosh --quiet
    
    # Wait for replica set to stabilize
    log_info "Waiting for replica set to stabilize..."
    sleep 15
    
    # Create admin user
    log_info "Creating admin user..."
    local admin_user admin_password
    admin_user=$(jq -r '.mongodb_cluster.nodes[0].user' "$CONFIG_FILE")
    admin_password=$(jq -r '.mongodb_cluster.nodes[0].password' "$CONFIG_FILE")
    
    mongosh --quiet << EOF
use admin
db.createUser({
  user: "$admin_user",
  pwd: "$admin_password",
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" },
    { role: "dbAdminAnyDatabase", db: "admin" },
    { role: "clusterAdmin", db: "admin" }
  ]
})
EOF
    
    log_success "Replica set initialized and admin user created"
}

# Setup logrotate for MongoDB
setup_logrotate() {
    log_info "Setting up logrotate for MongoDB..."
    
    cat > /etc/logrotate.d/mongodb << EOF
$LOG_DIR/mongod.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        /bin/kill -SIGUSR1 \$(cat /var/run/mongodb/mongod.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
EOF
    
    log_success "Logrotate configured for MongoDB"
}

# Install additional tools
install_tools() {
    log_info "Installing additional tools..."
    
    # Install Python and pip for data generation and load testing
    apt-get install -y python3 python3-pip python3-venv
    
    # Install Node.js for web dashboard
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
    
    # Install monitoring tools
    apt-get install -y htop iotop nethogs
    
    log_success "Additional tools installed"
}

# Main installation function
main() {
    log_info "Starting MongoDB cluster installation and configuration..."
    
    check_root
    parse_config
    get_current_node_info
    
    if ! check_mongodb_installed; then
        install_mongodb
    fi
    
    setup_directories
    generate_mongod_config
    start_mongodb
    initialize_replica_set
    setup_logrotate
    install_tools
    
    log_success "MongoDB cluster node installation completed successfully!"
    log_info "Node Role: $CURRENT_NODE_ROLE"
    log_info "Node IP: $CURRENT_NODE_IP:$CURRENT_NODE_PORT"
    log_info "Replica Set: $REPLICA_SET_NAME"
    log_info "Log file: $LOG_FILE"
    
    # Display next steps
    echo
    echo "Next steps:"
    echo "1. Run this script on all nodes in the cluster"
    echo "2. Verify replica set status: mongosh --eval 'rs.status()'"
    echo "3. Run the data generator: ./data-generator/generate_hr_data.py"
    echo "4. Start the web dashboard: cd dashboard && npm start"
    echo "5. Run load tests: ./load-testing/run_load_tests.py"
}

# Trap errors
trap 'log_error "Script failed at line $LINENO"' ERR

# Run main function
main "$@"