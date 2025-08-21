# MongoDB Replication Management System

Sistem automation lengkap untuk setup, monitoring, dan testing MongoDB replication dengan 3 node, termasuk web dashboard real-time, load testing, dan data generation untuk HR management.

## 🚀 Fitur Utama

### 🔧 Installation & Setup
- **Auto-install MongoDB** pada semua node jika belum terinstall
- **Konfigurasi replication 3 node** (1 primary + 2 secondary)
- **Setup logrotate** untuk semua node
- **SSH key authentication** untuk remote management

### 📊 Data Generation
- **200+ perusahaan** dengan data lengkap
- **Ribuan karyawan** per perusahaan
- **Data HR lengkap**: absensi, leave, payroll, dokumen
- **Dummy files**: PDF, PNG, JPG untuk testing
- **Realistic data** menggunakan Faker library

### 🧪 Load Testing
- **Concurrent read/write** operations
- **Report generation** testing
- **Replication lag monitoring** real-time
- **Performance metrics** dan charts
- **Comprehensive reports** dalam CSV format

### 🌐 Web Dashboard
- **Real-time monitoring** replication lag
- **Node status** monitoring
- **Query testing** interface
- **SSH terminal** access ke semua node
- **Configuration management** via web interface
- **Live charts** dan metrics

## 📋 Prerequisites

### System Requirements
- **Linux** (Ubuntu 20.04+ recommended)
- **Python 3.8+**
- **SSH access** ke semua node
- **Internet connection** untuk download packages

### Dependencies
```bash
# System packages
sudo apt-get update
sudo apt-get install -y python3 python3-pip jq ssh scp wget curl

# Python packages (auto-installed)
pip3 install -r requirements.txt
```

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd mongodb-replication-system
```

### 2. Configure Nodes
Edit file `accounts.json` dengan informasi node Anda:

```json
{
  "nodes": [
    {
      "ip": "192.168.1.10",
      "hostname": "mongo-primary",
      "user": "admin",
      "password": "admin123",
      "role": "primary",
      "port": 27017,
      "ssh_user": "ubuntu",
      "ssh_key_path": "~/.ssh/id_rsa"
    },
    {
      "ip": "192.168.1.11",
      "hostname": "mongo-secondary1", 
      "user": "admin",
      "password": "admin123",
      "role": "secondary",
      "port": 27017,
      "ssh_user": "ubuntu",
      "ssh_key_path": "~/.ssh/id_rsa"
    },
    {
      "ip": "192.168.1.12",
      "hostname": "mongo-secondary2",
      "user": "admin", 
      "password": "admin123",
      "role": "secondary",
      "port": 27017,
      "ssh_user": "ubuntu",
      "ssh_key_path": "~/.ssh/id_rsa"
    }
  ],
  "replica_set_name": "hr_replica_set",
  "database_name": "hr_management",
  "admin_user": "hr_admin",
  "admin_password": "hr_admin123"
}
```

### 3. Setup SSH Keys
Pastikan SSH key sudah dikonfigurasi untuk semua node:

```bash
# Generate SSH key jika belum ada
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# Copy public key ke semua node
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@192.168.1.10
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@192.168.1.11
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@192.168.1.12
```

### 4. Run Complete Setup
```bash
# Make scripts executable
chmod +x run_all.sh install_mongodb.sh

# Run complete setup
./run_all.sh all
```

## 📖 Usage

### Master Script Commands

```bash
# Complete setup (recommended)
./run_all.sh all

# Individual commands
./run_all.sh install     # Install MongoDB on all nodes
./run_all.sh data        # Generate dummy HR data
./run_all.sh test        # Run load testing
./run_all.sh dashboard   # Start web dashboard
./run_all.sh stop        # Stop web dashboard
./run_all.sh status      # Show system status
./run_all.sh cleanup     # Clean up processes
```

### Manual Scripts

#### 1. MongoDB Installation
```bash
./install_mongodb.sh
```

#### 2. Data Generation
```bash
python3 generate_dummy_data.py
```

#### 3. Load Testing
```bash
python3 load_testing.py --threads 20 --duration 120
```

#### 4. Web Dashboard
```bash
python3 web_dashboard.py
```

## 🌐 Web Dashboard Features

### Access Dashboard
```
http://localhost:5000
```

### Dashboard Sections

#### 1. Node Status
- Real-time status semua node
- Connection health monitoring
- Role information (Primary/Secondary)

#### 2. Replication Monitoring
- Live replication lag charts
- Performance metrics
- Historical data visualization

#### 3. Query Testing
- Execute MongoDB queries
- Test different query types (find, count, aggregate)
- View results and performance metrics

#### 4. SSH Terminal
- Direct SSH access ke semua node
- Execute commands remotely
- Real-time terminal output

#### 5. Configuration Management
- Load/save configuration dari web
- Edit node settings
- Validate configuration

## 📊 Generated Data Structure

### Collections Created
- **companies** - 200+ perusahaan dengan data lengkap
- **departments** - Department untuk setiap perusahaan
- **positions** - Job positions dengan salary ranges
- **employees** - Ribuan karyawan dengan data personal
- **attendance** - Attendance records (90 hari terakhir)
- **leave_requests** - Leave requests (1 tahun terakhir)
- **payroll** - Monthly payroll data (12 bulan terakhir)
- **documents** - Dummy PDF, PNG, JPG files

### Sample Data Volumes
- **Companies**: 200+
- **Employees**: 50,000+ (100-2000 per company)
- **Attendance Records**: 4,500,000+ (90 days)
- **Leave Requests**: 150,000+ (1 year)
- **Payroll Records**: 600,000+ (12 months)
- **Documents**: 200,000+ files

## 🧪 Load Testing Features

### Test Types
1. **Read Operations** (60% of traffic)
   - Document queries
   - Aggregation pipelines
   - Count operations

2. **Write Operations** (30% of traffic)
   - Document updates
   - New record insertions
   - Bulk operations

3. **Report Generation** (10% of traffic)
   - Complex aggregations
   - Analytics queries
   - Performance reports

### Metrics Collected
- **Operation duration** (ms)
- **Success/failure rates**
- **Replication lag** (ms)
- **Node performance**
- **Error tracking**

### Output Files
- `load_test_results.csv` - Detailed test results
- `load_test_charts.png` - Performance charts

## 🔧 Configuration

### Environment Variables
```bash
export MONGODB_CONFIG_FILE="accounts.json"
export DASHBOARD_PORT="5000"
export LOG_LEVEL="INFO"
```

### Log Files
- `logs/dashboard.log` - Web dashboard logs
- `mongodb_setup.log` - Installation logs
- `load_test_results.csv` - Load test results

## 🚨 Troubleshooting

### Common Issues

#### 1. SSH Connection Failed
```bash
# Test SSH connection
ssh -i ~/.ssh/id_rsa ubuntu@192.168.1.10

# Check SSH key permissions
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

#### 2. MongoDB Installation Failed
```bash
# Check system requirements
sudo apt-get update
sudo apt-get install -y wget gnupg

# Manual installation
wget -qO - https://www.mongodb.org/static/pgp/server-6.0.asc | sudo apt-key add -
```

#### 3. Python Dependencies Error
```bash
# Upgrade pip
pip3 install --upgrade pip

# Install dependencies manually
pip3 install pymongo flask flask-socketio faker pillow reportlab paramiko matplotlib numpy
```

#### 4. Dashboard Not Starting
```bash
# Check port availability
netstat -tlnp | grep :5000

# Check Python version
python3 --version

# Check logs
tail -f logs/dashboard.log
```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"
python3 web_dashboard.py --debug
```

## 📈 Performance Tuning

### MongoDB Configuration
```yaml
# /etc/mongod.conf
storage:
  dbPath: /var/lib/mongodb
  journal:
    enabled: true

systemLog:
  destination: file
  logAppend: true
  path: /var/log/mongodb/mongod.log

net:
  port: 27017
  bindIp: 0.0.0.0

replication:
  replSetName: hr_replica_set

security:
  authorization: enabled
```

### System Optimization
```bash
# Increase file descriptors
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Disable transparent huge pages
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag
```

## 🔒 Security Considerations

### Network Security
- **Firewall rules** untuk MongoDB ports
- **VPN access** untuk remote management
- **SSH key authentication** only

### MongoDB Security
- **Authentication enabled**
- **Role-based access control**
- **Encrypted connections** (TLS/SSL)

### Application Security
- **Input validation** pada web dashboard
- **Session management**
- **Rate limiting** untuk API endpoints

## 📝 API Documentation

### Dashboard API Endpoints

#### GET /api/nodes
Get status of all MongoDB nodes

#### POST /api/query
Execute MongoDB query
```json
{
  "node_ip": "192.168.1.10",
  "database": "hr_management",
  "collection": "employees",
  "query_type": "find",
  "query": "{}",
  "projection": "{}",
  "limit": 100
}
```

#### POST /api/ssh/connect
Connect to node via SSH
```json
{
  "node_ip": "192.168.1.10"
}
```

#### POST /api/ssh/execute
Execute command via SSH
```json
{
  "session_id": "uuid",
  "command": "ls -la"
}
```

#### GET /api/config/load
Load configuration from file

#### POST /api/config/save
Save configuration to file

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd mongodb-replication-system

# Install development dependencies
pip3 install -r requirements.txt
pip3 install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Code Style
- **PEP 8** compliance
- **Type hints** for functions
- **Docstrings** for all classes and methods
- **Error handling** with proper logging

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Getting Help
1. Check the troubleshooting section
2. Review logs in `logs/` directory
3. Check system requirements
4. Verify network connectivity

### Reporting Issues
Please include:
- System information (OS, Python version)
- Error messages and logs
- Steps to reproduce
- Configuration details (anonymized)

---

**Note**: This system is designed for production use but should be tested thoroughly in a staging environment first. Always backup your data before running any automation scripts.