#!/usr/bin/env python3
"""
MongoDB Replication Web Dashboard
Real-time monitoring, query testing, SSH access, and configuration management
"""

import json
import time
import threading
import subprocess
import paramiko
import asyncio
import websockets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import uuid
import os
import base64
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
config_file = "accounts.json"
config = None
clients = {}
monitoring_data = {
    'replication_lag': [],
    'node_status': {},
    'query_results': [],
    'ssh_sessions': {}
}

class MongoDBMonitor:
    def __init__(self):
        self.load_config()
        self.setup_connections()
        self.start_monitoring()
    
    def load_config(self):
        """Load configuration from JSON file"""
        global config
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            config = {"nodes": [], "replica_set_name": "", "database_name": ""}
    
    def setup_connections(self):
        """Setup connections to all MongoDB nodes"""
        global clients
        clients.clear()
        
        for node in config['nodes']:
            try:
                connection_string = f"mongodb://{node['user']}:{node['password']}@{node['ip']}:{node['port']}/admin"
                client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
                
                # Test connection
                client.admin.command('ping')
                clients[node['ip']] = {
                    'client': client,
                    'db': client[config['database_name']],
                    'role': node['role'],
                    'hostname': node['hostname'],
                    'status': 'connected',
                    'last_check': datetime.now()
                }
                print(f"✓ Connected to {node['hostname']} ({node['ip']})")
                
            except Exception as e:
                clients[node['ip']] = {
                    'client': None,
                    'db': None,
                    'role': node['role'],
                    'hostname': node['hostname'],
                    'status': 'disconnected',
                    'last_check': datetime.now(),
                    'error': str(e)
                }
                print(f"✗ Failed to connect to {node['ip']}: {e}")
    
    def measure_replication_lag(self):
        """Measure replication lag between nodes"""
        try:
            primary_client = None
            secondary_clients = []
            
            # Find primary and secondary nodes
            for ip, client_info in clients.items():
                if client_info['status'] == 'connected':
                    if client_info['role'] == 'primary':
                        primary_client = client_info
                    else:
                        secondary_clients.append(client_info)
            
            if not primary_client or not secondary_clients:
                return
            
            # Get primary oplog timestamp
            primary_oplog = primary_client['db'].admin.command('replSetGetStatus')
            primary_optime = primary_oplog['optimes']['lastCommittedOpTime']['ts']
            
            lag_results = {}
            
            for secondary in secondary_clients:
                try:
                    # Get secondary oplog timestamp
                    secondary_oplog = secondary['db'].admin.command('replSetGetStatus')
                    secondary_optime = secondary_oplog['optimes']['lastCommittedOpTime']['ts']
                    
                    # Calculate lag in milliseconds
                    lag_ms = (primary_optime.time - secondary_optime.time) * 1000
                    lag_results[secondary['hostname']] = lag_ms
                    
                except Exception as e:
                    lag_results[secondary['hostname']] = -1
            
            monitoring_data['replication_lag'].append({
                'timestamp': datetime.now(),
                'lags': lag_results
            })
            
            # Keep only last 1000 records
            if len(monitoring_data['replication_lag']) > 1000:
                monitoring_data['replication_lag'] = monitoring_data['replication_lag'][-1000:]
            
            # Emit to WebSocket
            socketio.emit('replication_lag_update', {
                'timestamp': datetime.now().isoformat(),
                'lags': lag_results
            })
            
        except Exception as e:
            print(f"Error measuring replication lag: {e}")
    
    def check_node_status(self):
        """Check status of all nodes"""
        for ip, client_info in clients.items():
            try:
                if client_info['client']:
                    client_info['client'].admin.command('ping')
                    client_info['status'] = 'connected'
                    client_info['last_check'] = datetime.now()
                    
                    # Get node stats
                    stats = client_info['db'].command('dbStats')
                    client_info['stats'] = {
                        'collections': stats.get('collections', 0),
                        'data_size': stats.get('dataSize', 0),
                        'storage_size': stats.get('storageSize', 0),
                        'indexes': stats.get('indexes', 0),
                        'index_size': stats.get('indexSize', 0)
                    }
                else:
                    client_info['status'] = 'disconnected'
                    
            except Exception as e:
                client_info['status'] = 'disconnected'
                client_info['error'] = str(e)
                client_info['last_check'] = datetime.now()
        
        monitoring_data['node_status'] = clients
        
        # Emit to WebSocket
        socketio.emit('node_status_update', {
            'nodes': clients,
            'timestamp': datetime.now().isoformat()
        })
    
    def start_monitoring(self):
        """Start continuous monitoring"""
        def monitor_loop():
            while True:
                try:
                    self.measure_replication_lag()
                    self.check_node_status()
                    time.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    time.sleep(10)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

# Initialize monitor
monitor = MongoDBMonitor()

# SSH Session Manager
class SSHSessionManager:
    def __init__(self):
        self.sessions = {}
    
    def create_session(self, node_ip, ssh_user, ssh_key_path):
        """Create SSH session to a node"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key
            ssh.connect(
                node_ip,
                username=ssh_user,
                key_filename=os.path.expanduser(ssh_key_path),
                timeout=10
            )
            
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                'ssh': ssh,
                'node_ip': node_ip,
                'created_at': datetime.now(),
                'last_activity': datetime.now()
            }
            
            return session_id
            
        except Exception as e:
            raise Exception(f"SSH connection failed: {e}")
    
    def execute_command(self, session_id, command):
        """Execute command on SSH session"""
        if session_id not in self.sessions:
            raise Exception("Session not found")
        
        session = self.sessions[session_id]
        session['last_activity'] = datetime.now()
        
        try:
            stdin, stdout, stderr = session['ssh'].exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            return {
                'output': output,
                'error': error,
                'exit_code': stdout.channel.recv_exit_status()
            }
            
        except Exception as e:
            return {
                'output': '',
                'error': str(e),
                'exit_code': -1
            }
    
    def close_session(self, session_id):
        """Close SSH session"""
        if session_id in self.sessions:
            self.sessions[session_id]['ssh'].close()
            del self.sessions[session_id]

ssh_manager = SSHSessionManager()

# Routes
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/nodes')
def get_nodes():
    """Get all nodes status"""
    return jsonify({
        'nodes': clients,
        'config': config
    })

@app.route('/api/query', methods=['POST'])
def execute_query():
    """Execute MongoDB query"""
    try:
        data = request.json
        node_ip = data.get('node_ip')
        database = data.get('database', config['database_name'])
        collection = data.get('collection')
        query_type = data.get('query_type', 'find')
        query = data.get('query', '{}')
        projection = data.get('projection', '{}')
        limit = data.get('limit', 100)
        
        if node_ip not in clients or clients[node_ip]['status'] != 'connected':
            return jsonify({'error': 'Node not available'}), 400
        
        # Parse query and projection
        try:
            query_dict = json.loads(query)
            projection_dict = json.loads(projection)
        except json.JSONDecodeError as e:
            return jsonify({'error': f'Invalid JSON: {e}'}), 400
        
        client_info = clients[node_ip]
        collection_obj = client_info['db'][collection]
        
        start_time = time.time()
        
        if query_type == 'find':
            cursor = collection_obj.find(query_dict, projection_dict).limit(limit)
            results = list(cursor)
        elif query_type == 'count':
            results = collection_obj.count_documents(query_dict)
        elif query_type == 'aggregate':
            pipeline = json.loads(data.get('pipeline', '[]'))
            cursor = collection_obj.aggregate(pipeline)
            results = list(cursor)
        else:
            return jsonify({'error': 'Invalid query type'}), 400
        
        duration = (time.time() - start_time) * 1000
        
        # Store query result
        query_result = {
            'id': str(uuid.uuid4()),
            'timestamp': datetime.now(),
            'node': node_ip,
            'database': database,
            'collection': collection,
            'query_type': query_type,
            'query': query,
            'duration_ms': duration,
            'result_count': len(results) if isinstance(results, list) else results,
            'results': results[:10] if isinstance(results, list) else results  # Limit result preview
        }
        
        monitoring_data['query_results'].append(query_result)
        
        # Keep only last 100 queries
        if len(monitoring_data['query_results']) > 100:
            monitoring_data['query_results'] = monitoring_data['query_results'][-100:]
        
        return jsonify({
            'success': True,
            'duration_ms': duration,
            'result_count': len(results) if isinstance(results, list) else results,
            'results': results[:10] if isinstance(results, list) else results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ssh/connect', methods=['POST'])
def ssh_connect():
    """Connect to node via SSH"""
    try:
        data = request.json
        node_ip = data.get('node_ip')
        
        # Find node config
        node_config = None
        for node in config['nodes']:
            if node['ip'] == node_ip:
                node_config = node
                break
        
        if not node_config:
            return jsonify({'error': 'Node not found'}), 404
        
        session_id = ssh_manager.create_session(
            node_config['ip'],
            node_config['ssh_user'],
            node_config['ssh_key_path']
        )
        
        return jsonify({
            'success': True,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ssh/execute', methods=['POST'])
def ssh_execute():
    """Execute command via SSH"""
    try:
        data = request.json
        session_id = data.get('session_id')
        command = data.get('command')
        
        if not command:
            return jsonify({'error': 'Command required'}), 400
        
        result = ssh_manager.execute_command(session_id, command)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ssh/disconnect', methods=['POST'])
def ssh_disconnect():
    """Disconnect SSH session"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        ssh_manager.close_session(session_id)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/load')
def load_config():
    """Load configuration from file"""
    try:
        monitor.load_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """Save configuration to file"""
    try:
        data = request.json
        new_config = data.get('config')
        
        if not new_config:
            return jsonify({'error': 'Configuration required'}), 400
        
        # Validate config structure
        required_fields = ['nodes', 'replica_set_name', 'database_name']
        for field in required_fields:
            if field not in new_config:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Save to file
        with open(config_file, 'w') as f:
            json.dump(new_config, f, indent=2)
        
        # Reload configuration
        monitor.load_config()
        monitor.setup_connections()
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/monitoring/data')
def get_monitoring_data():
    """Get monitoring data"""
    return jsonify({
        'replication_lag': monitoring_data['replication_lag'][-100:],  # Last 100 records
        'node_status': monitoring_data['node_status'],
        'query_results': monitoring_data['query_results'][-20:]  # Last 20 queries
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'message': 'Connected to MongoDB Dashboard'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('request_node_status')
def handle_node_status_request():
    emit('node_status_update', {
        'nodes': clients,
        'timestamp': datetime.now().isoformat()
    })

# HTML Templates
@app.route('/templates/dashboard.html')
def dashboard_template():
    return '''
<!DOCTYPE html>
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
        .status-connected { color: #28a745; }
        .status-disconnected { color: #dc3545; }
        .lag-warning { color: #ffc107; }
        .lag-critical { color: #dc3545; }
        .monitoring-card { height: 400px; }
        .query-result { max-height: 300px; overflow-y: auto; }
        .ssh-terminal { background: #000; color: #0f0; font-family: monospace; height: 300px; overflow-y: auto; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-database"></i> MongoDB Replication Dashboard
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text" id="last-update">
                    Last Update: <span id="update-time">Never</span>
                </span>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-3">
        <!-- Node Status -->
        <div class="row mb-3">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-server"></i> Node Status</h5>
                    </div>
                    <div class="card-body">
                        <div class="row" id="node-status-container">
                            <!-- Node status cards will be inserted here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Monitoring Charts -->
        <div class="row mb-3">
            <div class="col-md-6">
                <div class="card monitoring-card">
                    <div class="card-header">
                        <h5><i class="fas fa-chart-line"></i> Replication Lag</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="replication-lag-chart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card monitoring-card">
                    <div class="card-header">
                        <h5><i class="fas fa-chart-bar"></i> Node Performance</h5>
                    </div>
                    <div class="card-body">
                        <canvas id="node-performance-chart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- Query Testing -->
        <div class="row mb-3">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-search"></i> Query Testing</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <form id="query-form">
                                    <div class="mb-3">
                                        <label class="form-label">Node</label>
                                        <select class="form-select" id="query-node" required>
                                            <!-- Nodes will be populated -->
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Database</label>
                                        <input type="text" class="form-control" id="query-database" value="hr_management">
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Collection</label>
                                        <input type="text" class="form-control" id="query-collection" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Query Type</label>
                                        <select class="form-select" id="query-type">
                                            <option value="find">Find</option>
                                            <option value="count">Count</option>
                                            <option value="aggregate">Aggregate</option>
                                        </select>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Query (JSON)</label>
                                        <textarea class="form-control" id="query-json" rows="3">{}</textarea>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Projection (JSON)</label>
                                        <textarea class="form-control" id="query-projection" rows="2">{}</textarea>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Limit</label>
                                        <input type="number" class="form-control" id="query-limit" value="100">
                                    </div>
                                    <button type="submit" class="btn btn-primary">
                                        <i class="fas fa-play"></i> Execute Query
                                    </button>
                                </form>
                            </div>
                            <div class="col-md-6">
                                <div class="query-result" id="query-results">
                                    <p class="text-muted">Query results will appear here...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- SSH Access -->
        <div class="row mb-3">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-terminal"></i> SSH Access</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-3">
                                <div class="mb-3">
                                    <label class="form-label">Select Node</label>
                                    <select class="form-select" id="ssh-node">
                                        <!-- Nodes will be populated -->
                                    </select>
                                </div>
                                <button class="btn btn-success mb-2" id="ssh-connect">
                                    <i class="fas fa-plug"></i> Connect
                                </button>
                                <button class="btn btn-danger mb-2" id="ssh-disconnect">
                                    <i class="fas fa-times"></i> Disconnect
                                </button>
                                <div class="mb-3">
                                    <label class="form-label">Command</label>
                                    <input type="text" class="form-control" id="ssh-command" placeholder="Enter command...">
                                </div>
                                <button class="btn btn-primary" id="ssh-execute">
                                    <i class="fas fa-play"></i> Execute
                                </button>
                            </div>
                            <div class="col-md-9">
                                <div class="ssh-terminal" id="ssh-terminal">
                                    <div class="p-2">SSH Terminal - Select a node and connect to start...</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Configuration Management -->
        <div class="row mb-3">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="fas fa-cog"></i> Configuration Management</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <button class="btn btn-info mb-2" id="load-config">
                                    <i class="fas fa-download"></i> Load Configuration
                                </button>
                                <button class="btn btn-success mb-2" id="save-config">
                                    <i class="fas fa-save"></i> Save Configuration
                                </button>
                                <div class="mb-3">
                                    <label class="form-label">Configuration (JSON)</label>
                                    <textarea class="form-control" id="config-json" rows="20" readonly></textarea>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="alert alert-info">
                                    <h6>Configuration Format:</h6>
                                    <pre>{
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
    }
  ],
  "replica_set_name": "hr_replica_set",
  "database_name": "hr_management"
}</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Initialize Socket.IO
        const socket = io();
        
        // Global variables
        let currentSshSession = null;
        let replicationLagChart = null;
        let nodePerformanceChart = null;
        
        // Initialize charts
        function initCharts() {
            const lagCtx = document.getElementById('replication-lag-chart').getContext('2d');
            replicationLagChart = new Chart(lagCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: []
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Lag (ms)'
                            }
                        }
                    }
                }
            });
            
            const perfCtx = document.getElementById('node-performance-chart').getContext('2d');
            nodePerformanceChart = new Chart(perfCtx, {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Collections',
                        data: [],
                        backgroundColor: 'rgba(54, 162, 235, 0.5)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
        
        // Update node status
        function updateNodeStatus(nodes) {
            const container = document.getElementById('node-status-container');
            container.innerHTML = '';
            
            Object.entries(nodes).forEach(([ip, node]) => {
                const statusClass = node.status === 'connected' ? 'status-connected' : 'status-disconnected';
                const statusIcon = node.status === 'connected' ? 'fa-check-circle' : 'fa-times-circle';
                
                const card = document.createElement('div');
                card.className = 'col-md-3 mb-2';
                card.innerHTML = `
                    <div class="card">
                        <div class="card-body text-center">
                            <h6>${node.hostname}</h6>
                            <p class="mb-1"><small>${ip}</small></p>
                            <p class="mb-1"><span class="${statusClass}">
                                <i class="fas ${statusIcon}"></i> ${node.role}
                            </span></p>
                            <p class="mb-0"><small>Last check: ${new Date(node.last_check).toLocaleTimeString()}</small></p>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
            
            // Update select options
            updateSelectOptions();
        }
        
        // Update select options
        function updateSelectOptions() {
            const nodes = Object.keys(window.currentNodes || {});
            const selects = ['query-node', 'ssh-node'];
            
            selects.forEach(selectId => {
                const select = document.getElementById(selectId);
                select.innerHTML = '';
                nodes.forEach(ip => {
                    const option = document.createElement('option');
                    option.value = ip;
                    option.textContent = `${window.currentNodes[ip].hostname} (${ip})`;
                    select.appendChild(option);
                });
            });
        }
        
        // Update replication lag chart
        function updateReplicationLagChart(lagData) {
            if (!replicationLagChart) return;
            
            const timestamp = new Date(lagData.timestamp).toLocaleTimeString();
            replicationLagChart.data.labels.push(timestamp);
            
            // Keep only last 20 points
            if (replicationLagChart.data.labels.length > 20) {
                replicationLagChart.data.labels.shift();
            }
            
            // Update datasets
            Object.entries(lagData.lags).forEach(([node, lag]) => {
                let dataset = replicationLagChart.data.datasets.find(d => d.label === node);
                if (!dataset) {
                    dataset = {
                        label: node,
                        data: [],
                        borderColor: `hsl(${Math.random() * 360}, 70%, 50%)`,
                        backgroundColor: `hsla(${Math.random() * 360}, 70%, 50%, 0.1)`,
                        tension: 0.1
                    };
                    replicationLagChart.data.datasets.push(dataset);
                }
                
                dataset.data.push(lag);
                if (dataset.data.length > 20) {
                    dataset.data.shift();
                }
            });
            
            replicationLagChart.update();
        }
        
        // Execute query
        async function executeQuery() {
            const formData = {
                node_ip: document.getElementById('query-node').value,
                database: document.getElementById('query-database').value,
                collection: document.getElementById('query-collection').value,
                query_type: document.getElementById('query-type').value,
                query: document.getElementById('query-json').value,
                projection: document.getElementById('query-projection').value,
                limit: parseInt(document.getElementById('query-limit').value)
            };
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                
                const result = await response.json();
                displayQueryResults(result);
                
            } catch (error) {
                console.error('Query error:', error);
                displayQueryResults({ error: error.message });
            }
        }
        
        // Display query results
        function displayQueryResults(result) {
            const container = document.getElementById('query-results');
            
            if (result.error) {
                container.innerHTML = `<div class="alert alert-danger">${result.error}</div>`;
                return;
            }
            
            container.innerHTML = `
                <div class="alert alert-success">
                    Query executed successfully in ${result.duration_ms.toFixed(2)}ms
                </div>
                <div class="mb-2">
                    <strong>Result count:</strong> ${result.result_count}
                </div>
                <div class="mb-2">
                    <strong>Results (first 10):</strong>
                </div>
                <pre class="bg-light p-2" style="max-height: 200px; overflow-y: auto;">${JSON.stringify(result.results, null, 2)}</pre>
            `;
        }
        
        // SSH functions
        async function sshConnect() {
            const nodeIp = document.getElementById('ssh-node').value;
            
            try {
                const response = await fetch('/api/ssh/connect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ node_ip: nodeIp })
                });
                
                const result = await response.json();
                if (result.success) {
                    currentSshSession = result.session_id;
                    appendToTerminal('Connected to ' + nodeIp + '\\n');
                } else {
                    appendToTerminal('Connection failed: ' + result.error + '\\n');
                }
                
            } catch (error) {
                appendToTerminal('Connection error: ' + error.message + '\\n');
            }
        }
        
        async function sshExecute() {
            if (!currentSshSession) {
                appendToTerminal('No active SSH session\\n');
                return;
            }
            
            const command = document.getElementById('ssh-command').value;
            if (!command) return;
            
            appendToTerminal('$ ' + command + '\\n');
            
            try {
                const response = await fetch('/api/ssh/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        session_id: currentSshSession,
                        command: command
                    })
                });
                
                const result = await response.json();
                if (result.success) {
                    if (result.result.output) {
                        appendToTerminal(result.result.output);
                    }
                    if (result.result.error) {
                        appendToTerminal('Error: ' + result.result.error);
                    }
                } else {
                    appendToTerminal('Execution failed: ' + result.error + '\\n');
                }
                
            } catch (error) {
                appendToTerminal('Execution error: ' + error.message + '\\n');
            }
            
            document.getElementById('ssh-command').value = '';
        }
        
        async function sshDisconnect() {
            if (!currentSshSession) return;
            
            try {
                await fetch('/api/ssh/disconnect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ session_id: currentSshSession })
                });
                
                currentSshSession = null;
                appendToTerminal('Disconnected\\n');
                
            } catch (error) {
                appendToTerminal('Disconnect error: ' + error.message + '\\n');
            }
        }
        
        function appendToTerminal(text) {
            const terminal = document.getElementById('ssh-terminal');
            terminal.innerHTML += '<div>' + text.replace(/\\n/g, '<br>') + '</div>';
            terminal.scrollTop = terminal.scrollHeight;
        }
        
        // Configuration functions
        async function loadConfiguration() {
            try {
                const response = await fetch('/api/config/load');
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('config-json').value = JSON.stringify(result.config, null, 2);
                } else {
                    alert('Failed to load configuration: ' + result.error);
                }
                
            } catch (error) {
                alert('Error loading configuration: ' + error.message);
            }
        }
        
        async function saveConfiguration() {
            try {
                const configText = document.getElementById('config-json').value;
                const config = JSON.parse(configText);
                
                const response = await fetch('/api/config/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ config: config })
                });
                
                const result = await response.json();
                if (result.success) {
                    alert('Configuration saved successfully');
                    location.reload();
                } else {
                    alert('Failed to save configuration: ' + result.error);
                }
                
            } catch (error) {
                alert('Error saving configuration: ' + error.message);
            }
        }
        
        // Event listeners
        document.addEventListener('DOMContentLoaded', function() {
            initCharts();
            
            // Query form
            document.getElementById('query-form').addEventListener('submit', function(e) {
                e.preventDefault();
                executeQuery();
            });
            
            // SSH buttons
            document.getElementById('ssh-connect').addEventListener('click', sshConnect);
            document.getElementById('ssh-execute').addEventListener('click', sshExecute);
            document.getElementById('ssh-disconnect').addEventListener('click', sshDisconnect);
            
            // SSH command enter key
            document.getElementById('ssh-command').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sshExecute();
                }
            });
            
            // Configuration buttons
            document.getElementById('load-config').addEventListener('click', loadConfiguration);
            document.getElementById('save-config').addEventListener('click', saveConfiguration);
            
            // Load initial data
            loadConfiguration();
        });
        
        // Socket.IO events
        socket.on('connect', function() {
            console.log('Connected to server');
        });
        
        socket.on('node_status_update', function(data) {
            window.currentNodes = data.nodes;
            updateNodeStatus(data.nodes);
            document.getElementById('update-time').textContent = new Date(data.timestamp).toLocaleTimeString();
        });
        
        socket.on('replication_lag_update', function(data) {
            updateReplicationLagChart(data);
        });
        
        // Request initial data
        socket.emit('request_node_status');
    </script>
</body>
</html>
    '''

if __name__ == '__main__':
    print("Starting MongoDB Replication Dashboard...")
    print("Access the dashboard at: http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)