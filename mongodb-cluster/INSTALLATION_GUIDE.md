# MongoDB Cluster Installation Guide

Panduan lengkap instalasi dan konfigurasi MongoDB Cluster Production System.

## 📋 Pre-Installation Checklist

### System Requirements
- [ ] Ubuntu 20.04+ atau Debian 11+
- [ ] Minimum 8GB RAM (16GB recommended)
- [ ] Minimum 50GB storage (100GB recommended)
- [ ] Root/sudo access
- [ ] Internet connection
- [ ] 3 server nodes untuk replica set

### Network Requirements
- [ ] Port 27017 terbuka antar nodes (MongoDB)
- [ ] Port 3000 terbuka untuk dashboard
- [ ] Port 22 untuk SSH access
- [ ] DNS resolution atau /etc/hosts configured

### Prerequisites Installation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install basic tools
sudo apt install -y curl wget jq git htop

# Verify connectivity between nodes
ping node1-ip
ping node2-ip
ping node3-ip
```

## 🚀 Installation Steps

### Step 1: Download dan Setup
```bash
# Clone repository
git clone <repository-url>
cd mongodb-cluster

# Make scripts executable
chmod +x deploy.sh
chmod +x scripts/*.sh
```

### Step 2: Configure Cluster
Edit file `config/accounts.json`:

```json
{
  "mongodb_cluster": {
    "replica_set_name": "rs0",
    "nodes": [
      {
        "id": 0,
        "hostname": "mongo-primary",
        "ip": "10.0.1.10",
        "port": 27017,
        "role": "primary",
        "priority": 10,
        "user": "admin",
        "password": "StrongPassword123!",
        "ssh_user": "ubuntu",
        "ssh_password": "SSHPassword123!",
        "ssh_key_path": "/root/.ssh/mongo_cluster_key"
      },
      {
        "id": 1,
        "hostname": "mongo-secondary1",
        "ip": "10.0.1.11",
        "port": 27017,
        "role": "secondary",
        "priority": 5,
        "user": "admin",
        "password": "StrongPassword123!",
        "ssh_user": "ubuntu",
        "ssh_password": "SSHPassword123!",
        "ssh_key_path": "/root/.ssh/mongo_cluster_key"
      },
      {
        "id": 2,
        "hostname": "mongo-secondary2",
        "ip": "10.0.1.12",
        "port": 27017,
        "role": "secondary",
        "priority": 1,
        "user": "admin",
        "password": "StrongPassword123!",
        "ssh_user": "ubuntu",
        "ssh_password": "SSHPassword123!",
        "ssh_key_path": "/root/.ssh/mongo_cluster_key"
      }
    ],
    "auth": {
      "keyfile_path": "/etc/mongodb-keyfile",
      "keyfile_content": "your-secure-keyfile-content-minimum-6-chars-long"
    },
    "directories": {
      "data_dir": "/var/lib/mongodb",
      "log_dir": "/var/log/mongodb",
      "config_dir": "/etc/mongod"
    },
    "performance": {
      "cache_size_gb": 2,
      "max_connections": 1000,
      "journal_enabled": true,
      "oplog_size_mb": 1024
    }
  },
  "hr_database": {
    "name": "hr_management",
    "collections": {
      "companies": "companies",
      "employees": "employees",
      "attendance": "attendance",
      "leaves": "leaves",
      "payroll": "payroll",
      "departments": "departments",
      "positions": "positions",
      "documents": "documents"
    }
  }
}
```

### Step 3: Configure SSH Keys (Optional)
```bash
# Generate SSH key pair
ssh-keygen -t rsa -b 4096 -f /root/.ssh/mongo_cluster_key

# Copy public key to all nodes
ssh-copy-id -i /root/.ssh/mongo_cluster_key.pub ubuntu@10.0.1.10
ssh-copy-id -i /root/.ssh/mongo_cluster_key.pub ubuntu@10.0.1.11
ssh-copy-id -i /root/.ssh/mongo_cluster_key.pub ubuntu@10.0.1.12

# Test SSH connectivity
ssh -i /root/.ssh/mongo_cluster_key ubuntu@10.0.1.10 "echo 'Connection successful'"
```

### Step 4: Run Deployment
```bash
# Run deployment script as root
sudo ./deploy.sh
```

### Step 5: Verify Installation
```bash
# Check cluster status
mongodb-cluster status

# Check services
systemctl status mongod
systemctl status mongodb-dashboard

# Test database connection
mongosh "mongodb://admin:StrongPassword123!@localhost:27017/admin" --eval "rs.status()"
```

## 🔧 Post-Installation Configuration

### 1. Security Hardening
```bash
# Change default dashboard password
sudo nano /etc/systemd/system/mongodb-dashboard.service
# Update Environment=DASHBOARD_PASSWORD=NewSecurePassword

# Restart dashboard
sudo systemctl daemon-reload
sudo systemctl restart mongodb-dashboard

# Configure firewall rules
sudo ufw allow from 10.0.1.0/24 to any port 27017
sudo ufw allow from trusted-ip to any port 3000
```

### 2. SSL/TLS Configuration (Production)
```bash
# Replace self-signed certificates with proper ones
sudo cp your-certificate.pem /etc/ssl/mongodb/mongodb.pem
sudo cp your-private-key.key /etc/ssl/mongodb/mongodb.key
sudo cat /etc/ssl/mongodb/mongodb.key /etc/ssl/mongodb/mongodb.pem > /etc/ssl/mongodb/mongodb-combined.pem

# Update MongoDB configuration
sudo nano /etc/mongod.conf
```

Add to mongod.conf:
```yaml
net:
  ssl:
    mode: requireSSL
    PEMKeyFile: /etc/ssl/mongodb/mongodb-combined.pem
    CAFile: /etc/ssl/mongodb/ca.pem
```

### 3. Monitoring Setup
```bash
# Configure email alerts
sudo nano /usr/local/bin/mongodb-log-monitor.sh
# Update ALERT_EMAIL variable

# Test monitoring
sudo /usr/local/bin/mongodb-log-monitor.sh

# Check health monitoring
mongodb-health-check
```

### 4. Backup Configuration
```bash
# Create backup directory
sudo mkdir -p /var/backups/mongodb-cluster
sudo chown mongodb:mongodb /var/backups/mongodb-cluster

# Test backup
mongodb-cluster backup

# Configure remote backup (optional)
# Add to crontab for remote sync
sudo crontab -e
# Add: 0 3 * * * rsync -av /var/backups/mongodb-cluster/ user@backup-server:/backups/mongodb/
```

## 🎯 Single Node Installation

Untuk testing atau development pada single node:

### 1. Modify Configuration
Edit `config/accounts.json` untuk single node:
```json
{
  "mongodb_cluster": {
    "replica_set_name": "rs0",
    "nodes": [
      {
        "id": 0,
        "hostname": "mongo-single",
        "ip": "127.0.0.1",
        "port": 27017,
        "role": "primary",
        "priority": 10,
        "user": "admin",
        "password": "AdminPass123!",
        "ssh_user": "ubuntu",
        "ssh_password": "UbuntuPass123!"
      }
    ]
  }
}
```

### 2. Deploy Single Node
```bash
sudo ./deploy.sh
```

## 🐳 Docker Installation (Alternative)

### 1. Create Docker Compose
```yaml
version: '3.8'
services:
  mongo-primary:
    image: mongo:7.0
    container_name: mongo-primary
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: AdminPass123!
    volumes:
      - mongo-primary-data:/data/db
      - ./scripts:/scripts
    command: mongod --replSet rs0 --keyFile /etc/mongo-keyfile
    
  mongo-secondary1:
    image: mongo:7.0
    container_name: mongo-secondary1
    ports:
      - "27018:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: AdminPass123!
    volumes:
      - mongo-secondary1-data:/data/db
    command: mongod --replSet rs0 --keyFile /etc/mongo-keyfile
    
  mongo-secondary2:
    image: mongo:7.0
    container_name: mongo-secondary2
    ports:
      - "27019:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: AdminPass123!
    volumes:
      - mongo-secondary2-data:/data/db
    command: mongod --replSet rs0 --keyFile /etc/mongo-keyfile

  dashboard:
    build: ./dashboard
    container_name: mongodb-dashboard
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DASHBOARD_USERNAME=admin
      - DASHBOARD_PASSWORD=admin123
    depends_on:
      - mongo-primary
      - mongo-secondary1
      - mongo-secondary2

volumes:
  mongo-primary-data:
  mongo-secondary1-data:
  mongo-secondary2-data:
```

### 2. Deploy with Docker
```bash
docker-compose up -d
```

## ✅ Verification Steps

### 1. Basic Connectivity
```bash
# Test MongoDB connection
mongosh "mongodb://admin:password@localhost:27017/admin"

# Check replica set status
rs.status()

# Test database operations
use hr_management
db.test.insertOne({test: "data"})
db.test.findOne()
```

### 2. Dashboard Access
```bash
# Check dashboard
curl http://localhost:3000

# Login test
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 3. Load Testing
```bash
# Run basic load test
cd load-testing
python3 load_test_runner.py --threads 5 --operations 50

# Web-based testing
python3 locustfile.py
# Access http://localhost:8089
```

### 4. Data Generation
```bash
# Generate sample data
cd data-generator
python3 generate_hr_data.py --companies 10 --employees-per-company 100
```

## 🚨 Troubleshooting Installation

### Common Issues

#### 1. Permission Denied
```bash
# Fix script permissions
chmod +x deploy.sh
chmod +x scripts/*.sh

# Fix MongoDB directory permissions
sudo chown -R mongodb:mongodb /var/lib/mongodb
sudo chown -R mongodb:mongodb /var/log/mongodb
```

#### 2. MongoDB Won't Start
```bash
# Check configuration syntax
mongod --config /etc/mongod.conf --configtest

# Check logs
tail -f /var/log/mongodb/mongod.log

# Check port availability
netstat -tlnp | grep 27017
```

#### 3. Replica Set Issues
```bash
# Force reconfigure
mongosh "mongodb://admin:password@localhost:27017/admin"
cfg = rs.conf()
rs.reconfig(cfg, {force: true})

# Check network connectivity
telnet other-node-ip 27017
```

#### 4. Dashboard Not Loading
```bash
# Check service status
systemctl status mongodb-dashboard

# Check port
netstat -tlnp | grep 3000

# Check logs
journalctl -u mongodb-dashboard -f

# Restart service
systemctl restart mongodb-dashboard
```

#### 5. Dependencies Issues
```bash
# Update package lists
sudo apt update

# Install missing dependencies
sudo apt install -y python3-pip nodejs npm

# Fix Python virtual environment
cd data-generator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Log Locations for Debugging
- **Installation**: `/var/log/mongodb-cluster-deployment.log`
- **MongoDB**: `/var/log/mongodb/mongod.log`
- **Dashboard**: `journalctl -u mongodb-dashboard`
- **Health Checks**: `/var/log/mongodb-health.log`

## 🔄 Uninstallation

### Complete Removal
```bash
# Stop services
sudo systemctl stop mongodb-dashboard
sudo systemctl stop mongod

# Remove services
sudo systemctl disable mongodb-dashboard
sudo systemctl disable mongod
sudo rm /etc/systemd/system/mongodb-dashboard.service

# Remove packages
sudo apt remove --purge mongodb-org*

# Remove data and logs
sudo rm -rf /var/lib/mongodb
sudo rm -rf /var/log/mongodb
sudo rm -rf /var/log/mongodb-cluster

# Remove configurations
sudo rm -rf /etc/mongod.conf
sudo rm -rf /etc/logrotate.d/mongodb*

# Remove management scripts
sudo rm /usr/local/bin/mongodb-cluster
sudo rm /usr/local/bin/mongodb-health-check

# Clean crontab
crontab -e  # Remove MongoDB-related entries
```

## 📞 Getting Help

### Documentation
- **README.md**: Overview dan fitur utama
- **INSTALLATION_GUIDE.md**: Panduan instalasi (this file)
- **API Documentation**: `/dashboard/public/api-docs.html`

### Support Channels
- **Health Check**: `mongodb-health-check`
- **Status Check**: `mongodb-cluster status`
- **Log Analysis**: `mongodb-cluster logs`
- **GitHub Issues**: Create issue dengan detail error

### Useful Commands
```bash
# Quick status check
mongodb-cluster status

# View all logs
mongodb-cluster logs

# Emergency restart
mongodb-cluster restart

# Create backup
mongodb-cluster backup

# Health check
mongodb-health-check
```

---

**✅ Installation Complete! Your MongoDB Cluster is ready for production use.**