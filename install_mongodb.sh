#!/bin/bash

# MongoDB Replication Setup Script
# Author: AI Generator
# Version: 1.0
# Description: Auto install MongoDB and configure 3-node replication

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONFIG_FILE="accounts.json"
LOG_FILE="mongodb_setup.log"
TEMP_DIR="/tmp/mongodb_setup"

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

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Please run as a regular user with sudo privileges."
    fi
}

# Check dependencies
check_dependencies() {
    log "Checking system dependencies..."
    
    # Check if jq is installed
    if ! command -v jq &> /dev/null; then
        log "Installing jq..."
        sudo apt-get update
        sudo apt-get install -y jq
    fi
    
    # Check if curl is installed
    if ! command -v curl &> /dev/null; then
        log "Installing curl..."
        sudo apt-get install -y curl
    fi
    
    # Check if wget is installed
    if ! command -v wget &> /dev/null; then
        log "Installing wget..."
        sudo apt-get install -y wget
    fi
}

# Install MongoDB on local machine
install_mongodb_local() {
    log "Installing MongoDB on local machine..."
    
    # Check if MongoDB is already installed
    if command -v mongod &> /dev/null; then
        warning "MongoDB is already installed. Checking version..."
        mongod --version
        return 0
    fi
    
    # Add MongoDB GPG key
    log "Adding MongoDB GPG key..."
    wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
    
    # Add MongoDB repository
    log "Adding MongoDB repository..."
    echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
    
    # Update package list
    sudo apt-get update
    
    # Install MongoDB
    log "Installing MongoDB..."
    sudo apt-get install -y mongodb-org
    
    # Start and enable MongoDB service
    log "Starting MongoDB service..."
    sudo systemctl start mongod
    sudo systemctl enable mongod
    
    # Wait for MongoDB to start
    sleep 5
    
    # Check if MongoDB is running
    if sudo systemctl is-active --quiet mongod; then
        log "MongoDB installed and running successfully"
    else
        error "Failed to start MongoDB service"
    fi
}

# Install MongoDB on remote node
install_mongodb_remote() {
    local ip=$1
    local ssh_user=$2
    local ssh_key_path=$3
    
    log "Installing MongoDB on remote node: $ip"
    
    # Create installation script for remote node
    cat > $TEMP_DIR/install_mongodb_remote.sh << 'EOF'
#!/bin/bash
set -e

# Check if MongoDB is already installed
if command -v mongod &> /dev/null; then
    echo "MongoDB is already installed"
    mongod --version
    exit 0
fi

# Add MongoDB GPG key
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Update package list
sudo apt-get update

# Install MongoDB
sudo apt-get install -y mongodb-org

# Create MongoDB configuration
sudo mkdir -p /etc/mongodb
sudo tee /etc/mongodb/mongod.conf > /dev/null << 'MONGO_CONF'
systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

processManagement:
  timeZoneInfo: /usr/share/zoneinfo

net:
  port: 27017
  bindIp: 0.0.0.0

security:
  authorization: enabled

replication:
  replSetName: hr_replica_set
MONGO_CONF

# Create logrotate configuration
sudo tee /etc/logrotate.d/mongodb > /dev/null << 'LOGROTATE_CONF'
/var/log/mongodb/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 mongodb mongodb
    postrotate
        /bin/kill -SIGUSR1 `cat /var/lib/mongodb/mongod.lock 2>/dev/null` 2>/dev/null || true
    endscript
}
LOGROTATE_CONF

# Create necessary directories
sudo mkdir -p /var/lib/mongodb
sudo mkdir -p /var/log/mongodb
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chown -R mongodb:mongodb /var/log/mongodb

# Start and enable MongoDB service
sudo systemctl start mongod
sudo systemctl enable mongod

# Wait for MongoDB to start
sleep 5

# Check if MongoDB is running
if sudo systemctl is-active --quiet mongod; then
    echo "MongoDB installed and running successfully"
else
    echo "Failed to start MongoDB service"
    exit 1
fi
EOF
    
    # Copy and execute script on remote node
    scp -i $ssh_key_path -o StrictHostKeyChecking=no $TEMP_DIR/install_mongodb_remote.sh $ssh_user@$ip:/tmp/
    ssh -i $ssh_key_path -o StrictHostKeyChecking=no $ssh_user@$ip "chmod +x /tmp/install_mongodb_remote.sh && /tmp/install_mongodb_remote.sh"
    
    log "MongoDB installation completed on $ip"
}

# Configure MongoDB replication
configure_replication() {
    log "Configuring MongoDB replication..."
    
    # Read configuration
    local config=$(cat $CONFIG_FILE)
    local replica_set_name=$(echo $config | jq -r '.replica_set_name')
    local admin_user=$(echo $config | jq -r '.admin_user')
    local admin_password=$(echo $config | jq -r '.admin_password')
    
    # Get primary node
    local primary_node=$(echo $config | jq -r '.nodes[] | select(.role == "primary")')
    local primary_ip=$(echo $primary_node | jq -r '.ip')
    local primary_user=$(echo $primary_node | jq -r '.user')
    local primary_password=$(echo $primary_node | jq -r '.password')
    
    # Create replication configuration
    local members=""
    local member_id=0
    
    while IFS= read -r node; do
        local ip=$(echo $node | jq -r '.ip')
        local hostname=$(echo $node | jq -r '.hostname')
        local role=$(echo $node | jq -r '.role')
        
        if [ "$members" != "" ]; then
            members="$members,"
        fi
        
        if [ "$role" == "primary" ]; then
            members="$members{\"_id\": $member_id, \"host\": \"$ip:27017\", \"priority\": 2}"
        else
            members="$members{\"_id\": $member_id, \"host\": \"$ip:27017\", \"priority\": 1}"
        fi
        
        member_id=$((member_id + 1))
    done < <(echo $config | jq -c '.nodes[]')
    
    # Create replication configuration document
    cat > $TEMP_DIR/replica_config.js << EOF
rs.initiate({
  _id: "$replica_set_name",
  members: [$members]
})
EOF
    
    # Initialize replica set on primary
    log "Initializing replica set on primary node: $primary_ip"
    mongo --host $primary_ip:27017 --eval "$(cat $TEMP_DIR/replica_config.js)"
    
    # Wait for replica set to initialize
    log "Waiting for replica set to initialize..."
    sleep 30
    
    # Create admin user
    log "Creating admin user..."
    cat > $TEMP_DIR/create_admin.js << EOF
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
    
    mongo --host $primary_ip:27017 --eval "$(cat $TEMP_DIR/create_admin.js)"
    
    # Check replica set status
    log "Checking replica set status..."
    mongo --host $primary_ip:27017 --eval "rs.status()"
    
    log "Replication configuration completed successfully"
}

# Main execution
main() {
    log "Starting MongoDB Replication Setup"
    
    # Create temporary directory
    mkdir -p $TEMP_DIR
    
    # Check if config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        error "Configuration file $CONFIG_FILE not found"
    fi
    
    # Check dependencies
    check_dependencies
    
    # Install MongoDB locally
    install_mongodb_local
    
    # Read configuration
    local config=$(cat $CONFIG_FILE)
    
    # Install MongoDB on all remote nodes
    while IFS= read -r node; do
        local ip=$(echo $node | jq -r '.ip')
        local ssh_user=$(echo $node | jq -r '.ssh_user')
        local ssh_key_path=$(echo $node | jq -r '.ssh_key_path')
        
        # Skip localhost
        if [ "$ip" != "127.0.0.1" ] && [ "$ip" != "localhost" ]; then
            install_mongodb_remote $ip $ssh_user $ssh_key_path
        fi
    done < <(echo $config | jq -c '.nodes[]')
    
    # Configure replication
    configure_replication
    
    # Cleanup
    rm -rf $TEMP_DIR
    
    log "MongoDB Replication Setup completed successfully!"
    log "Log file: $LOG_FILE"
}

# Run main function
main "$@"