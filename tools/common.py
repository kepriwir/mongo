import json
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Node:
    name: str
    ip: str
    ssh_user: str
    ssh_password: str
    ssh_port: int
    role: str
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
    for n in data.get("nodes", []):
        sudo_password = n.get("sudo_password") or n.get("ssh_password")
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


def build_replset_uri(cfg: ClusterConfig, auth: bool = True, direct: bool = False, target_host: Optional[str] = None) -> str:
    hosts = ",".join([f"{n.ip}:27017" for n in cfg.nodes])
    creds = f"{cfg.cluster_admin_username}:{cfg.cluster_admin_password}@" if auth else ""
    params = f"replicaSet={cfg.replica_set_name}"
    if direct and target_host:
        hosts = target_host
        params += "&directConnection=true"
    return f"mongodb://{creds}{hosts}/?{params}&authSource=admin"


def get_primary_node(cfg: ClusterConfig) -> Node:
    for n in cfg.nodes:
        if n.role == "primary":
            return n
    return cfg.nodes[0]


def get_analytics_node(cfg: ClusterConfig) -> Optional[Node]:
    for n in cfg.nodes:
        if n.role == "analytics":
            return n
    return None

