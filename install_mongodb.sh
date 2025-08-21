#!/bin/bash

# MongoDB Replication Setup Script
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
LOG_FILE="mongodb_setup.log"
TEMP_DIR="/tmp/mongodb_setup"

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a $LOG_FILE
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" | tee -a $LOG_FILE
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}" | tee -a $LOG_FILE
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}" | tee -a $LOG_FILE
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root"
    fi
}

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."
    
    local deps=("jq" "ssh" "scp" "wget" "curl")
    for dep in "${deps[@]}"; do
        if ! command -v $dep &> /dev/null; then
            error "$dep is required but not installed"
        fi
    done
    
    log "All dependencies are available"
}

# Install MongoDB on a single node
install_mongodb_node() {
    local ip=$1
    local ssh_user=$2
    local ssh_key=$3
    
    log "Installing MongoDB on $ip..."
    
    # Create installation script
    cat > $TEMP_DIR/install_mongo_$ip.sh << 'EOF'
#!/bin/bash
set -e

# Update system
sudo apt-get update

# Install MongoDB GPG key
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/6.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

# Update package list
sudo apt-get update

# Install MongoDB
sudo apt-get install -y mongodb-org

# Create data directory
sudo mkdir -p /var/lib/mongodb
sudo mkdir -p /var/log/mongodb
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chown -R mongodb:mongodb /var/log/mongodb

# Create MongoDB configuration
sudo tee /etc/mongod.conf > /dev/null << 'MONGO_CONF'
# mongod.conf

# for documentation of all options, see:
#   http://docs.mongodb.org/manual/reference/configuration-options/

# Where and how to store data.
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

# where to write logging data.
systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

# network interfaces
net:
  port: 27017
  bindIp: 0.0.0.0

# how the process runs
processManagement:
  timeZoneInfo: /usr/share/zoneinfo

# security
security:
  authorization: enabled

# replication
replication:
  replSetName: hr_replica_set
MONGO_CONF

# Enable and start MongoDB
sudo systemctl enable mongod
sudo systemctl start mongod

# Wait for MongoDB to start
sleep 10

# Check if MongoDB is running
if sudo systemctl is-active --quiet mongod; then
    echo "MongoDB installed and running successfully"
else
    echo "Failed to start MongoDB"
    exit 1
fi
EOF

    # Copy and execute installation script
    scp -i $ssh_key -o StrictHostKeyChecking=no $TEMP_DIR/install_mongo_$ip.sh $ssh_user@$ip:/tmp/
    ssh -i $ssh_key -o StrictHostKeyChecking=no $ssh_user@$ip "chmod +x /tmp/install_mongo_$ip.sh && /tmp/install_mongo_$ip.sh"
    
    log "MongoDB installed successfully on $ip"
}

# Configure replication
configure_replication() {
    local config=$1
    local primary_ip=$(echo $config | jq -r '.nodes[] | select(.role=="primary") | .ip')
    local primary_user=$(echo $config | jq -r '.nodes[] | select(.role=="primary") | .user')
    local primary_password=$(echo $config | jq -r '.nodes[] | select(.role=="primary") | .password')
    local replica_set_name=$(echo $config | jq -r '.replica_set_name')
    
    log "Configuring replication on primary node $primary_ip..."
    
    # Create replication configuration script
    cat > $TEMP_DIR/configure_replication.sh << EOF
#!/bin/bash
set -e

# Wait for all nodes to be ready
sleep 30

# Get all node addresses
NODES=(
EOF

    # Add all nodes to the script
    echo $config | jq -r '.nodes[] | "  \"\(.ip):27017\""' >> $TEMP_DIR/configure_replication.sh
    
    cat >> $TEMP_DIR/configure_replication.sh << 'EOF'
)

# Create replication configuration
CONFIG='{
  "_id": "'$replica_set_name'",
  "members": [
EOF

    # Add members configuration
    local member_id=0
    echo $config | jq -r '.nodes[] | "    { \"_id\": \($member_id), \"host\": \"\(.ip):27017\", \"priority\": \(if .role=="primary" then 2 else 1 end) },"' | sed '$ s/,$//' >> $TEMP_DIR/configure_replication.sh
    
    cat >> $TEMP_DIR/configure_replication.sh << 'EOF'
  ]
}'

# Initialize replica set
mongosh --eval "rs.initiate($CONFIG)"

# Wait for replica set to be ready
sleep 10

# Create admin user
mongosh --eval "
  use admin;
  db.createUser({
    user: '$primary_user',
    pwd: '$primary_password',
    roles: [
      { role: 'userAdminAnyDatabase', db: 'admin' },
      { role: 'readWriteAnyDatabase', db: 'admin' },
      { role: 'dbAdminAnyDatabase', db: 'admin' },
      { role: 'clusterAdmin', db: 'admin' }
    ]
  });
"

echo "Replication configured successfully"
EOF

    # Copy and execute replication configuration
    local ssh_user=$(echo $config | jq -r '.nodes[] | select(.role=="primary") | .ssh_user')
    local ssh_key=$(echo $config | jq -r '.nodes[] | select(.role=="primary") | .ssh_key_path')
    
    scp -i $ssh_key -o StrictHostKeyChecking=no $TEMP_DIR/configure_replication.sh $ssh_user@$primary_ip:/tmp/
    ssh -i $ssh_key -o StrictHostKeyChecking=no $ssh_user@$primary_ip "chmod +x /tmp/configure_replication.sh && /tmp/configure_replication.sh"
    
    log "Replication configured successfully"
}

# Setup logrotate
setup_logrotate() {
    local config=$1
    
    log "Setting up logrotate for all nodes..."
    
    # Create logrotate configuration
    cat > $TEMP_DIR/mongodb_logrotate << 'EOF'
/var/log/mongodb/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 640 mongodb mongodb
    postrotate
        /bin/kill -SIGUSR1 `cat /var/lib/mongodb/mongod.lock 2>/dev/null` 2>/dev/null || true
    endscript
}
EOF

    # Copy logrotate config to all nodes
    echo $config | jq -r '.nodes[] | "\(.ip) \(.ssh_user) \(.ssh_key_path)"' | while read ip ssh_user ssh_key; do
        log "Setting up logrotate on $ip..."
        scp -i $ssh_key -o StrictHostKeyChecking=no $TEMP_DIR/mongodb_logrotate $ssh_user@$ip:/tmp/
        ssh -i $ssh_key -o StrictHostKeyChecking=no $ssh_user@$ip "sudo cp /tmp/mongodb_logrotate /etc/logrotate.d/mongodb && sudo chmod 644 /etc/logrotate.d/mongodb"
    done
    
    log "Logrotate configured for all nodes"
}

# Main execution
main() {
    log "Starting MongoDB Replication Setup"
    
    # Check if config file exists
    if [[ ! -f $CONFIG_FILE ]]; then
        error "Configuration file $CONFIG_FILE not found"
    fi
    
    # Create temp directory
    mkdir -p $TEMP_DIR
    
    # Check dependencies
    check_dependencies
    
    # Load configuration
    local config=$(cat $CONFIG_FILE)
    
    # Install MongoDB on all nodes
    echo $config | jq -r '.nodes[] | "\(.ip) \(.ssh_user) \(.ssh_key_path)"' | while read ip ssh_user ssh_key; do
        install_mongodb_node $ip $ssh_user $ssh_key
    done
    
    # Configure replication
    configure_replication "$config"
    
    # Setup logrotate
    setup_logrotate "$config"
    
    # Cleanup
    rm -rf $TEMP_DIR
    
    log "MongoDB Replication Setup completed successfully!"
    log "Primary node: $(echo $config | jq -r '.nodes[] | select(.role=="primary") | .ip')"
    log "Replica set name: $(echo $config | jq -r '.replica_set_name')"
}

# Run main function
main "$@"