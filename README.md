# MongoDB Replication Automation System

Sistem automation lengkap untuk instalasi, konfigurasi, dan monitoring MongoDB replication dengan 3 node, termasuk dashboard web real-time dan load testing tools.

## 🚀 Fitur Utama

### 🔧 Installation & Setup
- **Auto-install MongoDB** pada semua node (local dan remote)
- **Konfigurasi replication 3-node** otomatis
- **Logrotate configuration** untuk setiap node
- **SSH key-based** remote installation

### 📊 Data Generation
- **Dummy data generator** untuk HR management system
- **Ratusan perusahaan** dengan ribuan karyawan
- **Dokumen dummy** (PDF, PNG, JPG) otomatis
- **Data realistik** untuk testing dan development

### 🧪 Load Testing
- **Concurrent read/write** testing di semua node
- **Analytics query** testing di secondary nodes
- **Replication lag monitoring** real-time
- **Performance metrics** dan reporting

### 📈 Web Dashboard
- **Real-time monitoring** replication lag
- **Node status** dan health monitoring
- **Query tester** dengan visual interface
- **SSH terminal** untuk remote management
- **Configuration manager** dengan save/load dari JSON

## 📋 Prerequisites

### System Requirements
- Ubuntu 20.04+ / CentOS 7+ / RHEL 7+
- Python 3.8+
- SSH access ke semua node
- Sudo privileges pada semua node

### Network Requirements
- Port 27017 terbuka antar node
- SSH access (port 22) ke semua node
- Web dashboard port (default: 5000)

## 🛠️ Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd mongodb-replication-automation
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure SSH Keys
```bash
# Generate SSH key jika belum ada
ssh-keygen -t rsa -b 4096 -C "mongodb-automation"

# Copy SSH key ke semua node
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@192.168.1.10
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@192.168.1.11
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@192.168.1.12
```

### 4. Configure Node Settings
Edit file `accounts.json` sesuai dengan environment Anda:

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
      "hostname": "mongo-secondary-1", 
      "user": "admin",
      "password": "admin123",
      "role": "secondary",
      "port": 27017,
      "ssh_user": "ubuntu",
      "ssh_key_path": "~/.ssh/id_rsa"
    },
    {
      "ip": "192.168.1.12",
      "hostname": "mongo-secondary-2",
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
  "admin_password": "hr_admin_secure_2024"
}
```

## 🚀 Quick Start

### 1. Install MongoDB dan Setup Replication
```bash
# Make script executable
chmod +x install_mongodb.sh

# Run installation
./install_mongodb.sh
```

### 2. Generate Dummy Data
```bash
# Generate data untuk 100 perusahaan dengan 50 karyawan per perusahaan
python3 generate_dummy_data.py --companies 100 --employees 50 --mongodb

# Atau generate ke JSON file
python3 generate_dummy_data.py --companies 100 --employees 50 --output hr_data.json
```

### 3. Start Web Dashboard
```bash
# Start dashboard dengan default settings
python3 web_dashboard.py

# Atau dengan custom settings
python3 web_dashboard.py --host 0.0.0.0 --port 8080 --debug
```

### 4. Run Load Testing
```bash
# Basic load test (60 detik)
python3 load_testing.py

# Custom load test
python3 load_testing.py --read-threads 20 --write-threads 10 --analytics-threads 5 --duration 300
```

## 📖 Usage Guide

### MongoDB Installation Script

Script `install_mongodb.sh` akan:
1. Install dependencies (jq, curl, wget)
2. Install MongoDB di local machine
3. Install MongoDB di semua remote nodes via SSH
4. Configure replication dengan primary dan secondary nodes
5. Setup logrotate untuk semua node
6. Create admin user dan security settings

**Logs**: Semua output tersimpan di `mongodb_setup.log`

### Data Generator

Script `generate_dummy_data.py` menghasilkan:

#### Companies Collection
- Company ID, name, industry, size
- Address, contact information
- Founded year, tax ID

#### Employees Collection  
- Employee ID, personal information
- Department, job title, salary
- Hire date, manager relationships

#### Attendance Records
- Daily check-in/check-out times
- Work hours, overtime, break time
- Status (Present, Late, Absent)

#### Leave Records
- Leave type (Annual, Sick, Personal, etc.)
- Start/end dates, duration
- Approval status

#### Payroll Records
- Monthly salary calculations
- Tax deductions, bonuses
- Net salary, payment dates

#### Documents
- Dummy PDF reports
- Employee photos (PNG)
- Text documents

### Load Testing

Script `load_testing.py` melakukan testing:

#### Read Operations
- Simple document reads
- Complex aggregations
- Range queries dengan index
- Join-like queries

#### Write Operations
- Document insertions
- Bulk updates
- Upsert operations
- Document deletions

#### Analytics Operations
- Payroll reports
- Attendance analysis
- Leave statistics
- Company performance metrics

#### Replication Lag Monitoring
- Real-time lag measurement
- Per-node lag tracking
- Statistical analysis (avg, min, max, p95)

### Web Dashboard

Dashboard web menyediakan:

#### Real-time Monitoring
- Node status (connected/disconnected)
- Replication lag charts
- Performance metrics
- Alert notifications

#### Query Tester
- Execute MongoDB queries
- Select target node
- View results dengan formatting
- Query performance metrics

#### SSH Terminal
- Execute SSH commands
- Select target node
- View command output
- Error handling

#### Configuration Manager
- Load configuration dari JSON
- Edit configuration via web interface
- Save configuration ke file
- Apply changes secara real-time

## 🔧 Configuration

### Node Configuration

Setiap node dalam `accounts.json` memiliki:

```json
{
  "ip": "192.168.1.10",           // IP address node
  "hostname": "mongo-primary",    // Hostname untuk identification
  "user": "admin",                // MongoDB user
  "password": "admin123",         // MongoDB password
  "role": "primary",              // primary/secondary
  "port": 27017,                  // MongoDB port
  "ssh_user": "ubuntu",           // SSH username
  "ssh_key_path": "~/.ssh/id_rsa" // SSH private key path
}
```

### Replication Settings

```json
{
  "replica_set_name": "hr_replica_set",     // Nama replica set
  "database_name": "hr_management",         // Database name
  "admin_user": "hr_admin",                 // Admin username
  "admin_password": "hr_admin_secure_2024"  // Admin password
}
```

## 📊 Monitoring & Alerts

### Replication Lag Alerts
- **Warning**: Lag > 1 second
- **Critical**: Lag > 5 seconds

### Node Status Alerts
- **Critical**: Node disconnected
- **Warning**: Node response time > 2 seconds

### Performance Alerts
- **Warning**: Query time > 1 second
- **Critical**: Query time > 5 seconds

## 🧪 Load Testing Scenarios

### Scenario 1: Normal Load
```bash
python3 load_testing.py --read-threads 10 --write-threads 5 --analytics-threads 3 --duration 60
```

### Scenario 2: High Read Load
```bash
python3 load_testing.py --read-threads 50 --write-threads 5 --analytics-threads 10 --duration 300
```

### Scenario 3: High Write Load
```bash
python3 load_testing.py --read-threads 10 --write-threads 20 --analytics-threads 5 --duration 300
```

### Scenario 4: Analytics Heavy
```bash
python3 load_testing.py --read-threads 10 --write-threads 5 --analytics-threads 20 --duration 600
```

## 🔍 Troubleshooting

### Common Issues

#### 1. SSH Connection Failed
```bash
# Test SSH connection
ssh -i ~/.ssh/id_rsa ubuntu@192.168.1.10

# Check SSH key permissions
chmod 600 ~/.ssh/id_rsa
chmod 644 ~/.ssh/id_rsa.pub
```

#### 2. MongoDB Connection Failed
```bash
# Check MongoDB service status
sudo systemctl status mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Check firewall settings
sudo ufw status
```

#### 3. Replication Not Working
```bash
# Check replica set status
mongo --host 192.168.1.10:27017 --eval "rs.status()"

# Check oplog
mongo --host 192.168.1.10:27017 --eval "db.oplog.rs.find().sort({$natural:-1}).limit(1)"
```

#### 4. Dashboard Not Loading
```bash
# Check if port is open
netstat -tlnp | grep 5000

# Check Flask logs
python3 web_dashboard.py --debug
```

### Log Files

- **Installation**: `mongodb_setup.log`
- **Load Testing**: `load_test_results.json`
- **Dashboard**: Console output dengan debug mode

## 🔒 Security Considerations

### Production Deployment

1. **Change Default Passwords**
   - Update semua password di `accounts.json`
   - Use strong, unique passwords

2. **Network Security**
   - Restrict MongoDB port access
   - Use VPN atau private network
   - Configure firewall rules

3. **SSH Security**
   - Disable password authentication
   - Use key-based authentication only
   - Restrict SSH access

4. **MongoDB Security**
   - Enable authentication
   - Use TLS/SSL encryption
   - Configure network access control

### Security Checklist

- [ ] Change default passwords
- [ ] Configure firewall rules
- [ ] Enable MongoDB authentication
- [ ] Use SSH key authentication
- [ ] Restrict network access
- [ ] Enable audit logging
- [ ] Regular security updates

## 📈 Performance Optimization

### MongoDB Optimization

1. **Indexing Strategy**
   ```javascript
   // Create indexes for common queries
   db.employees.createIndex({"company_id": 1})
   db.employees.createIndex({"department": 1})
   db.attendance.createIndex([{"employee_id": 1}, {"date": 1}])
   db.payroll.createIndex([{"employee_id": 1}, {"year": 1}, {"month": 1}])
   ```

2. **Connection Pooling**
   ```python
   # Configure connection pool size
   client = MongoClient(connection_string, maxPoolSize=50)
   ```

3. **Read Preferences**
   ```python
   # Use secondary nodes for reads
   client = MongoClient(connection_string, readPreference='secondary')
   ```

### System Optimization

1. **Memory Settings**
   ```bash
   # Increase MongoDB memory limit
   sudo systemctl set-environment MONGODB_MEMORY_LIMIT=4G
   ```

2. **Disk I/O**
   ```bash
   # Use SSD storage
   # Configure RAID for redundancy
   ```

3. **Network Optimization**
   ```bash
   # Optimize network settings
   echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf
   echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf
   ```

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

Untuk bantuan dan support:

1. Check troubleshooting section
2. Review log files
3. Open issue di GitHub
4. Contact maintainer

---

**Note**: Script ini designed untuk production use dengan proper security configuration. Pastikan untuk review dan customize sesuai dengan environment dan security requirements Anda.