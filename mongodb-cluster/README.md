# MongoDB Cluster Production Deployment System

Sistem otomasi lengkap untuk deployment dan management MongoDB replica set 3-node dengan dashboard monitoring, load testing, dan data generation untuk sistem HR management.

## 🚀 Fitur Utama

### 📦 Auto Installation & Configuration
- ✅ Auto-install MongoDB 7.0 dengan replica set 3-node
- ✅ Konfigurasi otomatis berdasarkan `accounts.json`
- ✅ Setup authentication dan security
- ✅ SSL/TLS certificates
- ✅ Firewall dan fail2ban configuration

### 🎯 HR Management Data Generation
- ✅ Generator data dummy ratusan perusahaan
- ✅ Ribuan karyawan per perusahaan
- ✅ Data absensi, cuti, payroll, dokumen
- ✅ File dummy PDF/PNG/JPG
- ✅ Database indexes untuk performa optimal

### ⚡ Load Testing Tools
- ✅ Concurrent read/write testing
- ✅ Multi-node load balancing
- ✅ Analytics node testing
- ✅ Real-time performance metrics
- ✅ Web-based Locust interface
- ✅ Automated reporting

### 📊 Web Dashboard Monitoring
- ✅ Real-time cluster monitoring
- ✅ Replication lag tracking
- ✅ Node status visualization
- ✅ Query interface dengan syntax highlighting
- ✅ SSH remote access ke nodes
- ✅ Configuration management
- ✅ Performance charts dan metrics

### 🔧 Production Ready
- ✅ Logrotate configuration
- ✅ Health monitoring dan alerting
- ✅ Automated backups
- ✅ Performance monitoring
- ✅ Management scripts
- ✅ Error handling dan recovery

## 📋 Persyaratan Sistem

### Minimum Requirements
- **OS**: Ubuntu 20.04+ / Debian 11+
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 50GB minimum, 100GB recommended
- **Network**: Internet connection untuk download packages
- **Privileges**: Root access

### Node Configuration
- **Primary Node**: 4GB RAM, 2 CPU cores
- **Secondary Nodes**: 2GB RAM, 1-2 CPU cores
- **Network**: All nodes must be able to communicate on port 27017

## 🛠️ Quick Start

### 1. Clone Repository
```bash
git clone <repository-url>
cd mongodb-cluster
```

### 2. Configure Cluster
Edit `config/accounts.json` dengan informasi nodes:
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
        "user": "admin",
        "password": "AdminPass123!",
        "ssh_user": "ubuntu",
        "ssh_password": "UbuntuPass123!"
      }
    ]
  }
}
```

### 3. Deploy Cluster
```bash
sudo ./deploy.sh
```

### 4. Access Dashboard
```
URL: http://your-server-ip:3000
Username: admin
Password: admin123
```

## 📁 Struktur Project

```
mongodb-cluster/
├── config/
│   └── accounts.json           # Konfigurasi cluster
├── scripts/
│   ├── install_mongodb.sh      # Script instalasi MongoDB
│   └── setup_logrotate.sh      # Setup log rotation
├── data-generator/
│   ├── generate_hr_data.py     # Generator data HR
│   └── requirements.txt
├── load-testing/
│   ├── load_test_runner.py     # Load testing tools
│   ├── locustfile.py          # Web-based load testing
│   └── requirements.txt
├── dashboard/
│   ├── server.js              # Dashboard backend
│   ├── public/                # Frontend files
│   └── package.json
├── logs/                      # Log files
└── deploy.sh                  # Master deployment script
```

## 🔧 Management Commands

### Cluster Management
```bash
# Status cluster
mongodb-cluster status

# Start/stop services
mongodb-cluster start
mongodb-cluster stop
mongodb-cluster restart

# View logs
mongodb-cluster logs

# Create backup
mongodb-cluster backup

# Health check
mongodb-health-check
```

### Data Generation
```bash
# Generate sample data
cd data-generator
python3 generate_hr_data.py --companies 100 --employees-per-company 1000

# Custom options
python3 generate_hr_data.py --companies 50 --employees-per-company 500 --months 6
```

### Load Testing
```bash
# Command line testing
cd load-testing
python3 load_test_runner.py --threads 10 --operations 100

# Web-based testing (Locust)
python3 locustfile.py
# Access: http://localhost:8089
```

### Dashboard
```bash
# Start dashboard manually
cd dashboard
npm start

# View dashboard logs
journalctl -u mongodb-dashboard -f
```

## 📊 Monitoring & Alerting

### Real-time Monitoring
- **Cluster Status**: Node health, replication lag
- **Performance Metrics**: Operations/sec, memory usage, connections
- **Database Stats**: Collection counts, storage usage
- **System Resources**: CPU, memory, disk usage

### Log Management
- **MongoDB logs**: Daily rotation, 52 weeks retention
- **Application logs**: Weekly/monthly rotation
- **Performance logs**: Automated collection every 5 minutes
- **Health checks**: Every 10 minutes with alerting

### Backup Strategy
- **Automated backups**: Daily at 2 AM
- **Retention**: 30 days local, configurable remote
- **Point-in-time recovery**: Via oplog
- **Configuration backup**: Included in all backups

## 🔐 Security Features

### Authentication & Authorization
- **Database authentication**: Username/password + keyfile
- **Role-based access control**: Admin, read-only users
- **SSL/TLS encryption**: In-transit data protection
- **Network security**: Firewall rules, fail2ban

### Access Control
- **Dashboard authentication**: JWT-based sessions
- **SSH access**: Key-based authentication
- **API endpoints**: Token-based authorization
- **Network isolation**: Configurable IP restrictions

## 🚨 Troubleshooting

### Common Issues

#### MongoDB tidak start
```bash
# Check service status
systemctl status mongod

# Check logs
tail -f /var/log/mongodb/mongod.log

# Check configuration
mongod --config /etc/mongod.conf --configtest
```

#### Replica set issues
```bash
# Check replica set status
mongosh "mongodb://admin:password@localhost:27017/admin" --eval "rs.status()"

# Reconfigure replica set
mongosh "mongodb://admin:password@localhost:27017/admin" --eval "rs.reconfig(config, {force: true})"
```

#### Dashboard tidak accessible
```bash
# Check service
systemctl status mongodb-dashboard

# Check ports
netstat -tlnp | grep 3000

# Check logs
journalctl -u mongodb-dashboard -n 50
```

#### Performance issues
```bash
# Check system resources
htop
iotop
nethogs

# MongoDB performance
mongosh --eval "db.serverStatus()"
mongosh --eval "db.currentOp()"
```

### Log Locations
- **MongoDB**: `/var/log/mongodb/mongod.log`
- **Dashboard**: `/var/log/mongodb-dashboard.log`
- **Deployment**: `/var/log/mongodb-cluster-deployment.log`
- **Health checks**: `/var/log/mongodb-health.log`
- **Performance**: `/var/log/mongodb-cluster/performance/`

## 🔄 Maintenance Tasks

### Daily
- [x] Automated backups
- [x] Health checks
- [x] Log rotation
- [x] Performance monitoring

### Weekly
- [ ] Review performance metrics
- [ ] Check disk usage
- [ ] Update security patches
- [ ] Test backup restoration

### Monthly
- [ ] Review and update configuration
- [ ] Performance optimization
- [ ] Security audit
- [ ] Capacity planning

## 📈 Performance Tuning

### MongoDB Optimization
```javascript
// Enable profiling for slow queries
db.setProfilingLevel(2, {slowms: 100})

// Create appropriate indexes
db.employees.createIndex({company_id: 1, department: 1})
db.attendance.createIndex({employee_id: 1, date: 1})

// Monitor index usage
db.employees.getIndexes()
db.employees.stats({indexDetails: true})
```

### System Optimization
```bash
# Adjust MongoDB configuration
# /etc/mongod.conf
storage:
  wiredTiger:
    engineConfig:
      cacheSizeGB: 4  # Adjust based on available RAM

# System tuning
echo 'vm.swappiness = 1' >> /etc/sysctl.conf
echo 'net.core.somaxconn = 65535' >> /etc/sysctl.conf
sysctl -p
```

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📄 License

MIT License - see LICENSE file for details

## 📞 Support

- **Documentation**: Check README dan inline comments
- **Issues**: Create GitHub issue
- **Health Check**: `mongodb-health-check`
- **Logs**: `mongodb-cluster logs`

## 🎯 Roadmap

### v2.0 Planned Features
- [ ] Multi-datacenter deployment
- [ ] Automated failover testing
- [ ] Advanced monitoring with Prometheus
- [ ] Grafana dashboard integration
- [ ] Kubernetes deployment support
- [ ] CI/CD pipeline integration

---

**🎉 MongoDB Cluster Production System - Ready for Enterprise Deployment!**