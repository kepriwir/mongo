#!/usr/bin/env python3
"""
MongoDB Monitoring Dashboard
Author: AI Generator
Version: 1.0
Description: Web dashboard for MongoDB replication monitoring and management
"""

import json
import time
import threading
import subprocess
import paramiko
import asyncio
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pymongo
from pymongo import MongoClient
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import os
import uuid
import base64
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mongodb-dashboard-secret-key-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

class MongoDBDashboard:
    def __init__(self, config_file="accounts.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.clients = {}
        self.monitoring_data = {
            "replication_lag": [],
            "node_status": {},
            "performance_metrics": {},
            "alerts": []
        }
        self.monitoring_active = False
        self.monitoring_thread = None
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found")
            return {"nodes": [], "replica_set_name": "", "database_name": "", "admin_user": "", "admin_password": ""}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in configuration file {self.config_file}")
            return {"nodes": [], "replica_set_name": "", "database_name": "", "admin_user": "", "admin_password": ""}
    
    def save_config(self):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def connect_to_nodes(self):
        """Connect to all MongoDB nodes"""
        logger.info("Connecting to MongoDB nodes...")
        
        for node in self.config["nodes"]:
            try:
                connection_string = f"mongodb://{node['ip']}:{node['port']}"
                client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
                
                # Test connection
                client.admin.command('ping')
                
                # Authenticate
                admin_db = client.admin
                admin_db.authenticate(self.config["admin_user"], self.config["admin_password"])
                
                self.clients[node["ip"]] = {
                    "client": client,
                    "db": client[self.config["database_name"]],
                    "role": node["role"],
                    "hostname": node["hostname"],
                    "status": "connected",
                    "last_check": datetime.now()
                }
                
                logger.info(f"Connected to {node['hostname']} ({node['ip']}) - {node['role']}")
                
            except Exception as e:
                logger.error(f"Failed to connect to {node['ip']}: {e}")
                self.clients[node["ip"]] = {
                    "status": "disconnected",
                    "error": str(e),
                    "last_check": datetime.now()
                }
    
    def get_primary_client(self):
        """Get the primary node client"""
        for ip, client_info in self.clients.items():
            if client_info.get("role") == "primary" and client_info.get("status") == "connected":
                return client_info
        return None
    
    def get_secondary_clients(self):
        """Get all secondary node clients"""
        return [client_info for client_info in self.clients.values() 
                if client_info.get("role") == "secondary" and client_info.get("status") == "connected"]
    
    def measure_replication_lag(self) -> Dict[str, Any]:
        """Measure replication lag between nodes"""
        try:
            primary_client = self.get_primary_client()
            if not primary_client:
                return {"error": "No primary node found"}
            
            # Get primary oplog timestamp
            primary_oplog = primary_client["client"].local.oplog.rs.find().sort("$natural", -1).limit(1)
            primary_timestamp = None
            for doc in primary_oplog:
                primary_timestamp = doc["ts"]
                break
            
            if not primary_timestamp:
                return {"error": "Could not get primary oplog timestamp"}
            
            lag_results = {}
            
            for ip, client_info in self.clients.items():
                if client_info.get("role") == "secondary" and client_info.get("status") == "connected":
                    try:
                        # Get secondary oplog timestamp
                        secondary_oplog = client_info["client"].local.oplog.rs.find().sort("$natural", -1).limit(1)
                        secondary_timestamp = None
                        for doc in secondary_oplog:
                            secondary_timestamp = doc["ts"]
                            break
                        
                        if secondary_timestamp:
                            # Calculate lag in milliseconds
                            lag_ms = (primary_timestamp.time - secondary_timestamp.time) * 1000
                            lag_results[ip] = {
                                "hostname": client_info["hostname"],
                                "lag_ms": lag_ms,
                                "timestamp": datetime.now().isoformat()
                            }
                        else:
                            lag_results[ip] = {"error": "Could not get secondary oplog timestamp"}
                    
                    except Exception as e:
                        lag_results[ip] = {"error": str(e)}
            
            return lag_results
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_node_status(self) -> Dict[str, Any]:
        """Get status of all nodes"""
        status = {}
        
        for ip, client_info in self.clients.items():
            try:
                if client_info.get("status") == "connected":
                    # Get server status
                    server_status = client_info["client"].admin.command("serverStatus")
                    
                    # Get replica set status
                    rs_status = client_info["client"].admin.command("replSetGetStatus")
                    
                    status[ip] = {
                        "hostname": client_info["hostname"],
                        "role": client_info["role"],
                        "status": "connected",
                        "uptime": server_status.get("uptime", 0),
                        "connections": server_status.get("connections", {}),
                        "opcounters": server_status.get("opcounters", {}),
                        "mem": server_status.get("mem", {}),
                        "replica_set_state": rs_status.get("myState", 0),
                        "last_check": datetime.now().isoformat()
                    }
                else:
                    status[ip] = {
                        "status": "disconnected",
                        "error": client_info.get("error", "Unknown error"),
                        "last_check": datetime.now().isoformat()
                    }
                    
            except Exception as e:
                status[ip] = {
                    "status": "error",
                    "error": str(e),
                    "last_check": datetime.now().isoformat()
                }
        
        return status
    
    def execute_query(self, query: str, node_ip: str = None) -> Dict[str, Any]:
        """Execute a MongoDB query"""
        try:
            if node_ip and node_ip in self.clients:
                client_info = self.clients[node_ip]
            else:
                # Use primary node by default
                client_info = self.get_primary_client()
                if not client_info:
                    return {"error": "No available nodes"}
            
            if client_info.get("status") != "connected":
                return {"error": f"Node {client_info.get('hostname', node_ip)} is not connected"}
            
            db = client_info["db"]
            
            # Execute query (this is a simplified version - in production, you'd want more security)
            start_time = time.time()
            
            # Parse and execute query
            if query.strip().startswith("db."):
                # Remove 'db.' prefix and execute
                collection_query = query.strip()[3:]
                result = eval(f"db.{collection_query}")
                
                # Convert cursor to list if needed
                if hasattr(result, 'limit'):
                    result = list(result.limit(100))  # Limit results for safety
                elif hasattr(result, '__iter__') and not isinstance(result, (str, int, float, bool)):
                    result = list(result)
                
            else:
                return {"error": "Invalid query format. Use 'db.collection.operation()'"}
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            return {
                "success": True,
                "result": result,
                "duration_ms": duration,
                "node": client_info["hostname"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def ssh_connect(self, node_ip: str, command: str) -> Dict[str, Any]:
        """Execute SSH command on a node"""
        try:
            node = next((n for n in self.config["nodes"] if n["ip"] == node_ip), None)
            if not node:
                return {"error": f"Node {node_ip} not found in configuration"}
            
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using SSH key
            ssh_key_path = os.path.expanduser(node["ssh_key_path"])
            ssh_client.connect(
                hostname=node["ip"],
                username=node["ssh_user"],
                key_filename=ssh_key_path,
                timeout=10
            )
            
            # Execute command
            stdin, stdout, stderr = ssh_client.exec_command(command, timeout=30)
            
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            ssh_client.close()
            
            return {
                "success": exit_code == 0,
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "command": command,
                "node": node["hostname"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join()
        logger.info("Monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Measure replication lag
                lag_data = self.measure_replication_lag()
                self.monitoring_data["replication_lag"].append(lag_data)
                
                # Keep only last 100 measurements
                if len(self.monitoring_data["replication_lag"]) > 100:
                    self.monitoring_data["replication_lag"] = self.monitoring_data["replication_lag"][-100:]
                
                # Get node status
                node_status = self.get_node_status()
                self.monitoring_data["node_status"] = node_status
                
                # Emit data to connected clients
                socketio.emit('monitoring_update', {
                    'replication_lag': lag_data,
                    'node_status': node_status,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Check for alerts
                self._check_alerts(lag_data, node_status)
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)
    
    def _check_alerts(self, lag_data: Dict[str, Any], node_status: Dict[str, Any]):
        """Check for alerts and add them to the monitoring data"""
        alerts = []
        
        # Check replication lag
        for node_ip, lag_info in lag_data.items():
            if isinstance(lag_info, dict) and "lag_ms" in lag_info:
                lag_ms = lag_info["lag_ms"]
                if lag_ms > 1000:  # Alert if lag > 1 second
                    alerts.append({
                        "type": "replication_lag",
                        "severity": "warning" if lag_ms < 5000 else "critical",
                        "message": f"High replication lag on {lag_info['hostname']}: {lag_ms:.0f}ms",
                        "timestamp": datetime.now().isoformat()
                    })
        
        # Check node status
        for node_ip, status_info in node_status.items():
            if status_info.get("status") != "connected":
                alerts.append({
                    "type": "node_status",
                    "severity": "critical",
                    "message": f"Node {status_info.get('hostname', node_ip)} is {status_info.get('status')}",
                    "timestamp": datetime.now().isoformat()
                })
        
        # Add new alerts
        self.monitoring_data["alerts"].extend(alerts)
        
        # Keep only last 50 alerts
        if len(self.monitoring_data["alerts"]) > 50:
            self.monitoring_data["alerts"] = self.monitoring_data["alerts"][-50:]
        
        # Emit alerts
        if alerts:
            socketio.emit('alerts', alerts)

# Initialize dashboard
dashboard = MongoDBDashboard()

# Flask routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/nodes')
def get_nodes():
    """Get all nodes information"""
    return jsonify(dashboard.config["nodes"])

@app.route('/api/status')
def get_status():
    """Get current monitoring status"""
    return jsonify({
        "monitoring_active": dashboard.monitoring_active,
        "node_status": dashboard.monitoring_data["node_status"],
        "replication_lag": dashboard.monitoring_data["replication_lag"][-1] if dashboard.monitoring_data["replication_lag"] else {},
        "alerts": dashboard.monitoring_data["alerts"][-10:] if dashboard.monitoring_data["alerts"] else []
    })

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute MongoDB query"""
    data = request.get_json()
    query = data.get('query', '')
    node_ip = data.get('node_ip')
    
    if not query:
        return jsonify({"error": "Query is required"})
    
    result = dashboard.execute_query(query, node_ip)
    return jsonify(result)

@app.route('/api/ssh', methods=['POST'])
def ssh_command():
    """Execute SSH command"""
    data = request.get_json()
    node_ip = data.get('node_ip')
    command = data.get('command', '')
    
    if not node_ip or not command:
        return jsonify({"error": "Node IP and command are required"})
    
    result = dashboard.ssh_connect(node_ip, command)
    return jsonify(result)

@app.route('/api/config', methods=['GET', 'POST'])
def manage_config():
    """Get or update configuration"""
    if request.method == 'GET':
        return jsonify(dashboard.config)
    else:
        try:
            new_config = request.get_json()
            dashboard.config = new_config
            
            if dashboard.save_config():
                # Reconnect to nodes with new config
                dashboard.connect_to_nodes()
                return jsonify({"success": True, "message": "Configuration updated successfully"})
            else:
                return jsonify({"error": "Failed to save configuration"})
        except Exception as e:
            return jsonify({"error": str(e)})

@app.route('/api/monitoring', methods=['POST'])
def toggle_monitoring():
    """Start or stop monitoring"""
    data = request.get_json()
    action = data.get('action')
    
    if action == 'start':
        dashboard.start_monitoring()
        return jsonify({"success": True, "message": "Monitoring started"})
    elif action == 'stop':
        dashboard.stop_monitoring()
        return jsonify({"success": True, "message": "Monitoring stopped"})
    else:
        return jsonify({"error": "Invalid action"})

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to MongoDB Dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('request_status')
def handle_status_request():
    """Handle status request from client"""
    emit('status_update', {
        'node_status': dashboard.monitoring_data["node_status"],
        'replication_lag': dashboard.monitoring_data["replication_lag"][-1] if dashboard.monitoring_data["replication_lag"] else {},
        'alerts': dashboard.monitoring_data["alerts"][-10:] if dashboard.monitoring_data["alerts"] else []
    })

# Create templates directory and HTML files
def create_templates():
    """Create HTML templates for the dashboard"""
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    # Main dashboard template
    dashboard_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MongoDB Replication Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        .status-card { transition: all 0.3s ease; }
        .status-card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        .lag-indicator { font-size: 0.8em; padding: 2px 6px; border-radius: 3px; }
        .lag-low { background-color: #d4edda; color: #155724; }
        .lag-medium { background-color: #fff3cd; color: #856404; }
        .lag-high { background-color: #f8d7da; color: #721c24; }
        .alert-item { border-left: 4px solid #dc3545; padding: 10px; margin: 5px 0; background-color: #f8f9fa; }
        .query-result { max-height: 400px; overflow-y: auto; background-color: #f8f9fa; padding: 10px; border-radius: 5px; }
        .ssh-output { font-family: 'Courier New', monospace; background-color: #000; color: #00ff00; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#"><i class="fas fa-database"></i> MongoDB Replication Dashboard</a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text" id="monitoring-status">
                    <i class="fas fa-circle text-danger"></i> Monitoring Stopped
                </span>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-3">
        <!-- Control Panel -->
        <div class="row mb-3">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-cogs"></i> Control Panel</h5>
                    </div>
                    <div class="card-body">
                        <button class="btn btn-success me-2" onclick="startMonitoring()">
                            <i class="fas fa-play"></i> Start Monitoring
                        </button>
                        <button class="btn btn-danger me-2" onclick="stopMonitoring()">
                            <i class="fas fa-stop"></i> Stop Monitoring
                        </button>
                        <button class="btn btn-primary" onclick="refreshStatus()">
                            <i class="fas fa-sync"></i> Refresh Status
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Node Status -->
        <div class="row mb-3">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-server"></i> Node Status</h5>
                    </div>
                    <div class="card-body">
                        <div class="row" id="node-status-container">
                            <!-- Node status cards will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Replication Lag Chart -->
        <div class="row mb-3">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-chart-line"></i> Replication Lag (ms)</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="lagChart" width="400" height="200"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-exclamation-triangle"></i> Recent Alerts</h5>
                    </div>
                    <div class="card-body">
                        <div id="alerts-container">
                            <!-- Alerts will be populated here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Query Tester -->
        <div class="row mb-3">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-search"></i> Query Tester</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-3">
                                <select class="form-select" id="query-node-select">
                                    <option value="">Auto-select (Primary)</option>
                                </select>
                            </div>
                            <div class="col-md-9">
                                <div class="input-group">
                                    <input type="text" class="form-control" id="query-input" 
                                           placeholder="Enter MongoDB query (e.g., db.employees.find().limit(5))">
                                    <button class="btn btn-primary" onclick="executeQuery()">
                                        <i class="fas fa-play"></i> Execute
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <div id="query-result" class="query-result" style="display: none;">
                                <!-- Query results will be shown here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- SSH Terminal -->
        <div class="row mb-3">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-terminal"></i> SSH Terminal</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-3">
                                <select class="form-select" id="ssh-node-select">
                                    <!-- Node options will be populated here -->
                                </select>
                            </div>
                            <div class="col-md-9">
                                <div class="input-group">
                                    <input type="text" class="form-control" id="ssh-command" 
                                           placeholder="Enter SSH command">
                                    <button class="btn btn-success" onclick="executeSSH()">
                                        <i class="fas fa-terminal"></i> Execute
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="mt-3">
                            <div id="ssh-output" class="ssh-output" style="display: none;">
                                <!-- SSH output will be shown here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Configuration Manager -->
        <div class="row mb-3">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-cog"></i> Configuration Manager</h5>
                    </div>
                    <div class="card-body">
                        <button class="btn btn-info me-2" onclick="loadConfig()">
                            <i class="fas fa-download"></i> Load Configuration
                        </button>
                        <button class="btn btn-warning" onclick="saveConfig()">
                            <i class="fas fa-save"></i> Save Configuration
                        </button>
                        <div class="mt-3">
                            <textarea class="form-control" id="config-editor" rows="10" 
                                      placeholder="Configuration JSON will appear here"></textarea>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Initialize Socket.IO
        const socket = io();
        
        // Chart.js setup
        let lagChart;
        let lagData = {
            labels: [],
            datasets: []
        };

        // Initialize the page
        document.addEventListener('DOMContentLoaded', function() {
            initializeChart();
            loadNodes();
            refreshStatus();
            
            // Socket.IO event handlers
            socket.on('connected', function(data) {
                console.log('Connected to dashboard:', data);
            });
            
            socket.on('monitoring_update', function(data) {
                updateNodeStatus(data.node_status);
                updateReplicationLag(data.replication_lag);
                updateChart(data.replication_lag);
            });
            
            socket.on('alerts', function(alerts) {
                updateAlerts(alerts);
            });
            
            socket.on('status_update', function(data) {
                updateNodeStatus(data.node_status);
                updateReplicationLag(data.replication_lag);
                updateAlerts(data.alerts);
            });
        });

        function initializeChart() {
            const ctx = document.getElementById('lagChart').getContext('2d');
            lagChart = new Chart(ctx, {
                type: 'line',
                data: lagData,
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Lag (ms)'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Time'
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true
                        }
                    }
                }
            });
        }

        function loadNodes() {
            fetch('/api/nodes')
                .then(response => response.json())
                .then(nodes => {
                    const querySelect = document.getElementById('query-node-select');
                    const sshSelect = document.getElementById('ssh-node-select');
                    
                    querySelect.innerHTML = '<option value="">Auto-select (Primary)</option>';
                    sshSelect.innerHTML = '';
                    
                    nodes.forEach(node => {
                        querySelect.innerHTML += `<option value="${node.ip}">${node.hostname} (${node.role})</option>`;
                        sshSelect.innerHTML += `<option value="${node.ip}">${node.hostname} (${node.role})</option>`;
                    });
                });
        }

        function refreshStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    updateNodeStatus(data.node_status);
                    updateReplicationLag(data.replication_lag);
                    updateAlerts(data.alerts);
                    updateMonitoringStatus(data.monitoring_active);
                });
        }

        function updateNodeStatus(nodeStatus) {
            const container = document.getElementById('node-status-container');
            container.innerHTML = '';
            
            Object.entries(nodeStatus).forEach(([ip, status]) => {
                const statusClass = status.status === 'connected' ? 'success' : 
                                  status.status === 'disconnected' ? 'danger' : 'warning';
                const statusIcon = status.status === 'connected' ? 'check-circle' : 
                                 status.status === 'disconnected' ? 'times-circle' : 'exclamation-triangle';
                
                const card = document.createElement('div');
                card.className = 'col-md-4 mb-2';
                card.innerHTML = `
                    <div class="card status-card border-${statusClass}">
                        <div class="card-body">
                            <h6 class="card-title">
                                <i class="fas fa-${statusIcon} text-${statusClass}"></i>
                                ${status.hostname || ip}
                            </h6>
                            <p class="card-text">
                                <strong>Role:</strong> ${status.role || 'Unknown'}<br>
                                <strong>Status:</strong> <span class="text-${statusClass}">${status.status}</span><br>
                                <strong>Last Check:</strong> ${status.last_check ? new Date(status.last_check).toLocaleTimeString() : 'Never'}
                            </p>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function updateReplicationLag(lagData) {
            // This will be handled by the chart update
        }

        function updateChart(lagData) {
            const now = new Date().toLocaleTimeString();
            
            // Update labels
            lagData.labels.push(now);
            if (lagData.labels.length > 20) {
                lagData.labels.shift();
            }
            
            // Update datasets
            Object.entries(lagData).forEach(([ip, lagInfo]) => {
                if (lagInfo && lagInfo.lag_ms !== undefined) {
                    let dataset = lagData.datasets.find(ds => ds.label === lagInfo.hostname);
                    if (!dataset) {
                        dataset = {
                            label: lagInfo.hostname,
                            data: [],
                            borderColor: getRandomColor(),
                            fill: false
                        };
                        lagData.datasets.push(dataset);
                    }
                    
                    dataset.data.push(lagInfo.lag_ms);
                    if (dataset.data.length > 20) {
                        dataset.data.shift();
                    }
                }
            });
            
            lagChart.update();
        }

        function updateAlerts(alerts) {
            const container = document.getElementById('alerts-container');
            container.innerHTML = '';
            
            alerts.forEach(alert => {
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert-item';
                alertDiv.innerHTML = `
                    <strong>${alert.type.toUpperCase()}</strong> - ${alert.message}<br>
                    <small>${new Date(alert.timestamp).toLocaleString()}</small>
                `;
                container.appendChild(alertDiv);
            });
        }

        function updateMonitoringStatus(active) {
            const statusElement = document.getElementById('monitoring-status');
            if (active) {
                statusElement.innerHTML = '<i class="fas fa-circle text-success"></i> Monitoring Active';
            } else {
                statusElement.innerHTML = '<i class="fas fa-circle text-danger"></i> Monitoring Stopped';
            }
        }

        function startMonitoring() {
            fetch('/api/monitoring', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'start'})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateMonitoringStatus(true);
                }
            });
        }

        function stopMonitoring() {
            fetch('/api/monitoring', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'stop'})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateMonitoringStatus(false);
                }
            });
        }

        function executeQuery() {
            const query = document.getElementById('query-input').value;
            const nodeIp = document.getElementById('query-node-select').value;
            
            if (!query) {
                alert('Please enter a query');
                return;
            }
            
            fetch('/api/query', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({query: query, node_ip: nodeIp})
            })
            .then(response => response.json())
            .then(data => {
                const resultDiv = document.getElementById('query-result');
                resultDiv.style.display = 'block';
                
                if (data.error) {
                    resultDiv.innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
                } else {
                    resultDiv.innerHTML = `
                        <div class="alert alert-success">
                            Query executed successfully in ${data.duration_ms.toFixed(2)}ms on ${data.node}
                        </div>
                        <pre>${JSON.stringify(data.result, null, 2)}</pre>
                    `;
                }
            });
        }

        function executeSSH() {
            const command = document.getElementById('ssh-command').value;
            const nodeIp = document.getElementById('ssh-node-select').value;
            
            if (!command || !nodeIp) {
                alert('Please enter both command and select a node');
                return;
            }
            
            fetch('/api/ssh', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command, node_ip: nodeIp})
            })
            .then(response => response.json())
            .then(data => {
                const outputDiv = document.getElementById('ssh-output');
                outputDiv.style.display = 'block';
                
                if (data.error) {
                    outputDiv.innerHTML = `<div class="text-danger">Error: ${data.error}</div>`;
                } else {
                    outputDiv.innerHTML = `
                        <div class="text-success">Command executed on ${data.node} (Exit code: ${data.exit_code})</div>
                        <div class="mt-2">
                            <strong>Output:</strong><br>
                            <pre>${data.output || '(no output)'}</pre>
                        </div>
                        ${data.error ? `<div class="mt-2"><strong>Error:</strong><br><pre class="text-danger">${data.error}</pre></div>` : ''}
                    `;
                }
            });
        }

        function loadConfig() {
            fetch('/api/config')
                .then(response => response.json())
                .then(config => {
                    document.getElementById('config-editor').value = JSON.stringify(config, null, 2);
                });
        }

        function saveConfig() {
            const configText = document.getElementById('config-editor').value;
            try {
                const config = JSON.parse(configText);
                
                fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config)
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Configuration saved successfully');
                        loadNodes();
                    } else {
                        alert('Error saving configuration: ' + data.error);
                    }
                });
            } catch (e) {
                alert('Invalid JSON format');
            }
        }

        function getRandomColor() {
            const letters = '0123456789ABCDEF';
            let color = '#';
            for (let i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 16)];
            }
            return color;
        }
    </script>
</body>
</html>'''
    
    with open(os.path.join(templates_dir, "dashboard.html"), "w") as f:
        f.write(dashboard_html)

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MongoDB Monitoring Dashboard")
    parser.add_argument("--config", type=str, default="accounts.json", help="Configuration file")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Create templates
    create_templates()
    
    # Initialize dashboard
    dashboard.config_file = args.config
    dashboard.connect_to_nodes()
    
    # Start the Flask app
    if args.debug:
        socketio.run(app, host=args.host, port=args.port, debug=True)
    else:
        socketio.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()