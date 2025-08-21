#!/usr/bin/env python3
import argparse
import base64
import io
import json
import os
import posixpath
import random
import socket
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_fixed

import paramiko
from paramiko.client import SSHClient
from paramiko import AutoAddPolicy

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure


# ------------------------------
# Models and helpers
# ------------------------------


@dataclass
class Node:
    name: str
    ip: str
    ssh_user: str
    ssh_password: str
    ssh_port: int
    role: str  # primary | secondary | analytics
    sudo_password: Optional[str] = None


@dataclass
class ClusterConfig:
    replica_set_name: str
    mongo_version: str
    cluster_admin_username: str
    cluster_admin_password: str
    db_path: str
    log_path: str
    key_file_path: str
    nodes: List[Node]


def load_config(accounts_path: str) -> ClusterConfig:
    with open(accounts_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = []
    for n in data["nodes"]:
        sudo_password = n.get("sudo_password") or n.get("ssh_password", "")
        nodes.append(
            Node(
                name=n["name"],
                ip=n["ip"],
                ssh_user=n.get("ssh_user", "ubuntu"),
                ssh_password=n.get("ssh_password", ""),
                ssh_port=int(n.get("ssh_port", 22)),
                role=n.get("role", "secondary"),
                sudo_password=sudo_password,
            )
        )

    paths = data.get("paths", {})
    return ClusterConfig(
        replica_set_name=data.get("replicaSetName", "rs0"),
        mongo_version=str(data.get("mongoVersion", "7.0")),
        cluster_admin_username=data.get("clusterAdmin", {}).get("username", "clusterAdmin"),
        cluster_admin_password=data.get("clusterAdmin", {}).get("password", "ChangeMe-StrongPass!"),
        db_path=paths.get("dbPath", "/var/lib/mongo"),
        log_path=paths.get("logPath", "/var/log/mongodb/mongod.log"),
        key_file_path=paths.get("keyFile", "/etc/mongod.key"),
        nodes=nodes,
    )


def get_primary_node(cfg: ClusterConfig) -> Node:
    primaries = [n for n in cfg.nodes if n.role == "primary"]
    if not primaries:
        raise ValueError("No primary node defined in accounts.json")
    return primaries[0]


def get_analytics_node(cfg: ClusterConfig) -> Optional[Node]:
    analytics = [n for n in cfg.nodes if n.role == "analytics"]
    return analytics[0] if analytics else None


def make_ssh_client(node: Node) -> SSHClient:
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(
        node.ip,
        port=node.ssh_port,
        username=node.ssh_user,
        password=node.ssh_password,
        look_for_keys=False,
        allow_agent=False,
        timeout=20,
    )
    return client


def run_ssh_command(client: SSHClient, command: str, sudo: bool = False, sudo_password: Optional[str] = None) -> Tuple[int, str, str]:
    full_cmd = command
    if sudo:
        # Use -S to read password from stdin, -n for non-interactive
        full_cmd = f"sudo -S -n bash -lc {json.dumps(command)}"
    stdin, stdout, stderr = client.exec_command(full_cmd, get_pty=False)
    if sudo and sudo_password:
        stdin.write(sudo_password + "\n")
        stdin.flush()
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    return exit_status, out, err


def sftp_write_file(client: SSHClient, remote_path: str, data: bytes, mode: int = 0o644):
    sftp = client.open_sftp()
    try:
        remote_dir = posixpath.dirname(remote_path)
        _ensure_remote_dir(sftp, remote_dir)
        with sftp.file(remote_path, "wb") as f:
            f.write(data)
        sftp.chmod(remote_path, mode)
    finally:
        sftp.close()


def _ensure_remote_dir(sftp, remote_dir: str):
    parts = remote_dir.strip("/").split("/") if remote_dir.strip("/") else []
    cur = "/"
    for p in parts:
        cur = posixpath.join(cur, p)
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def random_keyfile_bytes() -> bytes:
    key = base64.b64encode(os.urandom(756))
    return key + b"\n"


def build_mongod_conf(db_path: str, log_path: str, repl_set_name: str, key_file_path: Optional[str], authorization: bool) -> str:
    # Minimal, production-minded config with journaling and replication
    conf = [
        "storage:",
        f"  dbPath: {db_path}",
        "  journal:",
        "    enabled: true",
        "systemLog:",
        "  destination: file",
        f"  path: {log_path}",
        "  logAppend: true",
        "processManagement:",
        "  fork: false",
        "net:",
        "  bindIp: 0.0.0.0",
        "  port: 27017",
        "replication:",
        f"  replSetName: {repl_set_name}",
    ]
    if key_file_path:
        conf += [
            "security:",
            f"  keyFile: {key_file_path}",
        ]
        if authorization:
            conf += [
                "  authorization: enabled",
            ]
    elif authorization:
        conf += [
            "security:",
            "  authorization: enabled",
        ]
    return "\n".join(conf) + "\n"


def build_logrotate_conf(log_path: str) -> str:
    # Rotate when file exceeds 100M or weekly, keep 12 rotations, compress
    return f"""
{log_path} {{
    weekly
    size 100M
    rotate 12
    compress
    delaycompress
    missingok
    notifempty
    create 640 mongodb adm
    sharedscripts
    postrotate
        /bin/systemctl kill -s USR1 mongod 2>/dev/null || true
    endscript
}}
"""


@retry(stop=stop_after_attempt(20), wait=wait_fixed(3))
def wait_for_mongo(ip: str, port: int = 27017, timeout: int = 3):
    sock = socket.create_connection((ip, port), timeout=timeout)
    sock.close()


def ensure_mongodb_installed(client: SSHClient, mongo_version: str, sudo_password: Optional[str]):
    code, out, err = run_ssh_command(client, "mongod --version || true")
    if "db version" in out or "db version" in err or code == 0 and out.strip() != "":
        return  # Already available (very naive check)

    # Detect Ubuntu codename
    _, codename, _ = run_ssh_command(client, "source /etc/os-release && echo $UBUNTU_CODENAME || echo focal")
    codename = codename.strip() or "focal"

    # Add MongoDB official repository
    run_ssh_command(
        client,
        (
            "set -e; "
            "sudo install -d -m 0755 -o root -g root /usr/share/keyrings; "
            f"curl -fsSL https://pgp.mongodb.com/server-{mongo_version}.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-{mongo_version}.gpg; "
            f"echo \"deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-{mongo_version}.gpg ] https://repo.mongodb.org/apt/ubuntu {codename}/mongodb-org/{mongo_version} multiverse\" | sudo tee /etc/apt/sources.list.d/mongodb-org-{mongo_version}.list > /dev/null; "
            "sudo apt-get update; "
            "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mongodb-org jq curl gnupg; "
        ),
        sudo=True,
        sudo_password=sudo_password,
    )


def configure_mongod_service(client: SSHClient, db_path: str, log_path: str, repl_set_name: str, key_file_path: str, authorization: bool, sudo_password: Optional[str]):
    # Prepare filesystem
    run_ssh_command(client, f"sudo install -d -o mongodb -g mongodb -m 0755 {db_path}", sudo=True, sudo_password=sudo_password)
    log_dir = posixpath.dirname(log_path)
    run_ssh_command(client, f"sudo install -d -o mongodb -g adm -m 0755 {log_dir}", sudo=True, sudo_password=sudo_password)

    # Write mongod.conf
    conf_text = build_mongod_conf(db_path, log_path, repl_set_name, key_file_path, authorization)
    sftp_write_file(client, "/tmp/mongod.conf", conf_text.encode("utf-8"), 0o644)
    run_ssh_command(client, "sudo mv /tmp/mongod.conf /etc/mongod.conf && sudo chown root:root /etc/mongod.conf && sudo chmod 0644 /etc/mongod.conf", sudo=True, sudo_password=sudo_password)

    # Enable and restart
    run_ssh_command(client, "sudo systemctl enable mongod", sudo=True, sudo_password=sudo_password)
    run_ssh_command(client, "sudo systemctl restart mongod", sudo=True, sudo_password=sudo_password)


def install_logrotate(client: SSHClient, log_path: str, sudo_password: Optional[str]):
    lr = build_logrotate_conf(log_path)
    sftp_write_file(client, "/tmp/mongod-logrotate", lr.encode("utf-8"), 0o644)
    run_ssh_command(client, "sudo mv /tmp/mongod-logrotate /etc/logrotate.d/mongod && sudo chown root:root /etc/logrotate.d/mongod && sudo chmod 0644 /etc/logrotate.d/mongod", sudo=True, sudo_password=sudo_password)


def distribute_keyfile(clients: Dict[str, SSHClient], keyfile_path: str, node_passwords: Dict[str, Optional[str]]):
    key_bytes = random_keyfile_bytes()
    for name, client in clients.items():
        sftp_write_file(client, "/tmp/mongod.key", key_bytes, 0o400)
        # mongod must be able to read the key file
        run_ssh_command(client, f"sudo mv /tmp/mongod.key {keyfile_path} && sudo chown mongodb:mongodb {keyfile_path} && sudo chmod 0400 {keyfile_path}", sudo=True, sudo_password=node_passwords.get(name))


def initiate_replica_set(cfg: ClusterConfig):
    primary = get_primary_node(cfg)
    uri = f"mongodb://{primary.ip}:27017"  # No auth yet
    client = MongoClient(uri, directConnection=True, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        raise RuntimeError(f"Cannot reach primary at {primary.ip}:27017 before rs.initiate: {exc}")

    members = []
    member_id = 0
    for n in cfg.nodes:
        member = {
            "_id": member_id,
            "host": f"{n.ip}:27017",
        }
        if n.role == "primary":
            member["priority"] = 2
        elif n.role == "analytics":
            member["priority"] = 0
            member["hidden"] = True
            member["votes"] = 0
            member["tags"] = {"usage": "analytics"}
        else:
            member["priority"] = 1
        members.append(member)
        member_id += 1

    cfg_doc = {
        "_id": cfg.replica_set_name,
        "members": members,
        "settings": {
            "heartbeatIntervalMillis": 2000,
            "electionTimeoutMillis": 10000,
        },
    }

    try:
        rs_status = client.admin.command("replSetGetStatus")
        if rs_status.get("ok") == 1:
            print("Replica set already initiated, skipping rs.initiate().")
            return
    except Exception:
        pass

    client.admin.command("replSetInitiate", cfg_doc)
    time.sleep(5)
    # Wait until primary is elected
    for _ in range(30):
        try:
            status = client.admin.command("replSetGetStatus")
            primary_members = [m for m in status.get("members", []) if m.get("stateStr") == "PRIMARY"]
            if primary_members:
                print("Replica set PRIMARY elected.")
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Replica set initiation timed out.")


def create_cluster_admin(cfg: ClusterConfig):
    primary = get_primary_node(cfg)
    client = MongoClient(f"mongodb://{primary.ip}:27017", directConnection=True, serverSelectionTimeoutMS=10000)
    # If authorization disabled, this will work unauthenticated
    try:
        client.admin.add_user(
            cfg.cluster_admin_username,
            cfg.cluster_admin_password,
            roles=[{"role": "root", "db": "admin"}],
        )
        print("Admin user created")
    except OperationFailure as e:
        if "already exists" in str(e).lower():
            print("Admin user already exists, skipping")
        else:
            raise


def enable_authorization_on_all_nodes(clients: Dict[str, SSHClient], cfg: ClusterConfig, node_passwords: Dict[str, Optional[str]]):
    for node_name, client in clients.items():
        conf_text = build_mongod_conf(cfg.db_path, cfg.log_path, cfg.replica_set_name, cfg.key_file_path, authorization=True)
        sftp_write_file(client, "/tmp/mongod.conf", conf_text.encode("utf-8"), 0o644)
        run_ssh_command(client, "sudo mv /tmp/mongod.conf /etc/mongod.conf && sudo chown root:root /etc/mongod.conf && sudo chmod 0644 /etc/mongod.conf", sudo=True, sudo_password=node_passwords.get(node_name))
        run_ssh_command(client, "sudo systemctl restart mongod", sudo=True, sudo_password=node_passwords.get(node_name))


def build_replset_uri(cfg: ClusterConfig, auth: bool = True, direct: bool = False, target_host: Optional[str] = None) -> str:
    hosts = ",".join([f"{n.ip}:27017" for n in cfg.nodes])
    if auth:
        creds = f"{cfg.cluster_admin_username}:{cfg.cluster_admin_password}@"
    else:
        creds = ""
    params = f"replicaSet={cfg.replica_set_name}"
    if direct and target_host:
        params += f"&directConnection=true"
        hosts = target_host
    return f"mongodb://{creds}{hosts}/?{params}&authSource=admin"


def print_status(cfg: ClusterConfig, auth: bool = True):
    uri = build_replset_uri(cfg, auth=auth)
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        status = client.admin.command("replSetGetStatus")
    except Exception as e:
        print(f"Failed to get replSet status: {e}")
        return
    primary_optime = None
    for m in status.get("members", []):
        if m.get("stateStr") == "PRIMARY":
            primary_optime = m.get("optimeDate")
    print(json.dumps(status, default=str, indent=2))
    if primary_optime:
        for m in status.get("members", []):
            if "optimeDate" in m and m.get("stateStr") != "PRIMARY":
                lag = (primary_optime - m.get("optimeDate")).total_seconds()
                print(f"Member {m.get('name')} lag: {lag:.3f}s")


# ------------------------------
# CLI orchestration
# ------------------------------


def cmd_install(cfg: ClusterConfig):
    clients: Dict[str, SSHClient] = {}
    node_passwords: Dict[str, Optional[str]] = {}
    try:
        for n in cfg.nodes:
            print(f"Connecting to {n.name} ({n.ip})...")
            client = make_ssh_client(n)
            clients[n.name] = client
            node_passwords[n.name] = n.sudo_password
            print(f"Ensuring MongoDB installed on {n.name}...")
            ensure_mongodb_installed(client, cfg.mongo_version, sudo_password=n.sudo_password)
        print("Distributing keyfile to all nodes...")
        distribute_keyfile(clients, cfg.key_file_path, node_passwords)
        print("Configuring mongod service on all nodes...")
        for n in cfg.nodes:
            client = clients[n.name]
            configure_mongod_service(client, cfg.db_path, cfg.log_path, cfg.replica_set_name, cfg.key_file_path, authorization=False, sudo_password=n.sudo_password)
            install_logrotate(client, cfg.log_path, sudo_password=n.sudo_password)
            print(f"Waiting for mongod TCP on {n.ip}:27017...")
            wait_for_mongo(n.ip)
        print("All nodes prepared and mongod running.")
    finally:
        for c in clients.values():
            c.close()


def cmd_configure(cfg: ClusterConfig):
    # In this implementation, install() already performs configuration
    # This function is kept for explicit step separation and idempotency
    print("Configure step completed (handled in install phase).")


def cmd_init_replica(cfg: ClusterConfig):
    print("Initiating replica set and waiting for PRIMARY...")
    initiate_replica_set(cfg)


def cmd_create_admin(cfg: ClusterConfig):
    print("Creating cluster admin user (root role)...")
    create_cluster_admin(cfg)


def cmd_enable_auth(cfg: ClusterConfig):
    print("Enabling authorization on all nodes and restarting mongod...")
    clients: Dict[str, SSHClient] = {}
    node_passwords: Dict[str, Optional[str]] = {}
    try:
        for n in cfg.nodes:
            clients[n.name] = make_ssh_client(n)
            node_passwords[n.name] = n.sudo_password
        enable_authorization_on_all_nodes(clients, cfg, node_passwords)
        # Validate auth by fetching status with auth
        print("Validating authenticated connection...")
        time.sleep(3)
        print_status(cfg, auth=True)
    finally:
        for c in clients.values():
            c.close()


def cmd_status(cfg: ClusterConfig, auth: bool):
    print_status(cfg, auth=auth)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MongoDB 3-node replicaset manager")
    p.add_argument("command", choices=[
        "install", "configure", "init-replica", "create-admin", "enable-auth", "status"
    ])
    p.add_argument("--accounts", default="./accounts.json", help="Path to accounts.json")
    p.add_argument("--no-auth", action="store_true", help="Use unauthenticated connection for status")
    return p.parse_args(argv)


def main():
    args = parse_args()
    cfg = load_config(args.accounts)
    if args.command == "install":
        cmd_install(cfg)
    elif args.command == "configure":
        cmd_configure(cfg)
    elif args.command == "init-replica":
        cmd_init_replica(cfg)
    elif args.command == "create-admin":
        cmd_create_admin(cfg)
    elif args.command == "enable-auth":
        cmd_enable_auth(cfg)
    elif args.command == "status":
        cmd_status(cfg, auth=not args.no_auth)
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

