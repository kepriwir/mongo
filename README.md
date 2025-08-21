# MongoDB 3-Node Replicaset Automation Suite

This repository delivers a **production-ready automation toolkit** that fully provisions a 3-node MongoDB replica-set environment, loads high-volume HR dummy data, stress-tests the cluster, and provides a real-time monitoring & admin dashboard.

## Components

1. **`accounts.json`** – Central inventory of replica-set hosts and credentials.
2. **`deploy/deploy_replica.py`** – Zero-touch installer that SSHs into each host, installs MongoDB, configures authentication, replica-set, log-rotation, and starts the service.
3. **`scripts/generate_dummy_data.py`** – Populates the cluster with hundreds of companies & thousands of employees, including dummy PDF/PNG/JPG files (stored in GridFS).
4. **`loadtest/locustfile.py`** – Locust-based workload generator for concurrent read/write & heavy report generation on the analytics secondary.
5. **`web/`** – Flask + SocketIO dashboard with live replication-lag charts, ad-hoc queries, SSH console, and visual node editor that persists back to `accounts.json`.

## Quick Start

```bash
# 1. Prepare local env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Provision MongoDB replica-set on remote hosts
python deploy/deploy_replica.py --accounts accounts.json --replset rs0

# 3. Generate HR demo data
python scripts/generate_dummy_data.py --mongo-uri "mongodb://admin:StrongPass@192.168.1.101:27017,192.168.1.102:27017,192.168.1.103:27017/?replicaSet=rs0"

# 4. Launch dashboard (runs on http://localhost:5000)
python web/app.py

# 5. Run load-test from another terminal
locust -f loadtest/locustfile.py --headless -u 500 -r 50 -t 5m
```

> **NOTE**: All scripts are idempotent – rerunning them is safe and will skip already completed tasks.

## Security
* All remote execution happens over **SSH** using the credentials provided in `accounts.json`.
* MongoDB authorization is enabled and an **`admin`** user is created; modify the default password in the deploy script or via `--admin-pass`.

## License
MIT