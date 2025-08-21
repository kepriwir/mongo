MongoDB Replicated Cluster Toolkit
=================================

This project automates provisioning a 3-node MongoDB replica set, generates HR dummy data at scale (companies, employees, attendance, leave, payroll), runs load testing for concurrent read/write, and provides a web dashboard for monitoring replication lag, testing queries, SSH actions, and node configuration persisted in `accounts.json`.

Quick Start
-----------

1) Copy the template and edit credentials/roles

```bash
cp accounts.json.template accounts.json
$EDITOR accounts.json
```

2) Install dependencies

```bash
make deps
```

3) Provision and configure the cluster (Ubuntu/Debian-based nodes)

```bash
make configure-cluster
make init-replica
make admin
make enable-auth
```

4) Generate dummy data (hundreds of companies, thousands of employees)

```bash
make dummy
```

5) Load test (concurrent read/write and analytics reports)

```bash
make load-test
```

6) Web dashboard

```bash
make web
```

Features
--------

- Automated MongoDB installation (if missing) via SSH
- Replica set bootstrap from `accounts.json`
- Cluster keyfile distribution and logrotate configuration
- HR dummy data generator with attachments (PDF, PNG, JPG) using GridFS
- Load testing across all nodes with analytics report generation on the analytics node
- Web dashboard for:
  - Real-time replication lag monitoring
  - Query tester
  - Limited SSH execution to each node
  - Config form with save/load from `accounts.json`

Security Notes
--------------

- Restrict access to this toolkit and the web dashboard. It can execute SSH commands on cluster nodes.
- Use strong SSH credentials and firewall rules (allow from trusted IPs only).
- Replace the default cluster admin password before enabling authorization.

# mongo