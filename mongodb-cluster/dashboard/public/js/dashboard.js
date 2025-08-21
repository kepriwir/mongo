/**
 * MongoDB Cluster Dashboard JavaScript
 * Handles UI interactions, real-time updates, and API communication
 */

// Global variables
let socket;
let authToken = localStorage.getItem('authToken');
let config = {};
let charts = {};
let updateInterval;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    if (authToken) {
        showDashboard();
        initializeDashboard();
    } else {
        showLogin();
    }
});

// Authentication
function showLogin() {
    document.getElementById('dashboard').style.display = 'none';
    const loginModal = new bootstrap.Modal(document.getElementById('loginModal'));
    loginModal.show();
}

function showDashboard() {
    document.getElementById('dashboard').style.display = 'block';
    const loginModal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
    if (loginModal) {
        loginModal.hide();
    }
}

function logout() {
    localStorage.removeItem('authToken');
    authToken = null;
    if (socket) {
        socket.disconnect();
    }
    showLogin();
}

// Login form handler
document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            authToken = data.token;
            localStorage.setItem('authToken', authToken);
            showDashboard();
            initializeDashboard();
            errorDiv.style.display = 'none';
        } else {
            errorDiv.textContent = data.message || 'Login failed';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Login error:', error);
        errorDiv.textContent = 'Connection error';
        errorDiv.style.display = 'block';
    }
});

// Dashboard initialization
async function initializeDashboard() {
    try {
        // Setup Socket.IO connection
        setupSocketConnection();
        
        // Load initial data
        await loadConfiguration();
        await updateClusterStatus();
        await updateDatabaseStats();
        
        // Setup charts
        initializeCharts();
        
        // Setup periodic updates
        startPeriodicUpdates();
        
        // Populate dropdowns
        populateDropdowns();
        
        showNotification('Dashboard initialized successfully', 'success');
    } catch (error) {
        console.error('Dashboard initialization error:', error);
        showNotification('Failed to initialize dashboard', 'danger');
    }
}

// Socket.IO setup
function setupSocketConnection() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('Connected to server');
        document.getElementById('connectionStatus').innerHTML = 
            '<i class="bi bi-circle-fill text-success"></i> Connected';
        socket.emit('subscribe_monitoring');
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        document.getElementById('connectionStatus').innerHTML = 
            '<i class="bi bi-circle-fill text-danger"></i> Disconnected';
    });
    
    socket.on('cluster_update', function(data) {
        updateDashboardData(data);
    });
}

// API helper function
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        }
    };
    
    const response = await fetch(url, { ...defaultOptions, ...options });
    
    if (response.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    
    return response.json();
}

// Load configuration
async function loadConfiguration() {
    try {
        config = await apiRequest('/api/config');
        document.getElementById('replicaSetName').value = config.mongodb_cluster.replica_set_name;
        updateRawConfig();
        updateNodesConfig();
    } catch (error) {
        console.error('Failed to load configuration:', error);
        showNotification('Failed to load configuration', 'danger');
    }
}

// Update cluster status
async function updateClusterStatus() {
    try {
        const status = await apiRequest('/api/cluster/status');
        updateStatusCards(status);
        updateClusterTopology(status);
        updateReplicationTable(status);
        updateNodesTab(status);
    } catch (error) {
        console.error('Failed to update cluster status:', error);
    }
}

// Update database statistics
async function updateDatabaseStats() {
    try {
        const stats = await apiRequest('/api/database/stats');
        updateDatabaseStatsDisplay(stats);
    } catch (error) {
        console.error('Failed to update database stats:', error);
    }
}

// Update status cards
function updateStatusCards(status) {
    const activeNodes = status.nodes.filter(node => node.status === 'online').length;
    const totalDocuments = status.nodes.reduce((sum, node) => {
        return sum + (node.dbStats ? node.dbStats.count : 0);
    }, 0);
    
    document.getElementById('replicaSetStatus').textContent = status.replicaSet.set;
    document.getElementById('activeNodes').textContent = `${activeNodes}/${status.nodes.length}`;
    document.getElementById('totalDocuments').textContent = formatNumber(totalDocuments);
}

// Update cluster topology visualization
function updateClusterTopology(status) {
    const container = document.getElementById('clusterTopology');
    container.innerHTML = '';
    
    const topology = document.createElement('div');
    topology.className = 'd-flex justify-content-center align-items-center flex-wrap';
    
    status.nodes.forEach(node => {
        const nodeDiv = document.createElement('div');
        nodeDiv.className = `topology-node topology-${node.role} ${node.status === 'offline' ? 'topology-offline' : ''}`;
        nodeDiv.innerHTML = `
            <div style="font-size: 12px;">${node.hostname}</div>
            <div style="font-size: 10px;">${node.role}</div>
            <div style="font-size: 10px;">${node.status}</div>
        `;
        nodeDiv.onclick = () => showNodeDetails(node.id);
        topology.appendChild(nodeDiv);
    });
    
    container.appendChild(topology);
}

// Update replication table
function updateReplicationTable(status) {
    const tbody = document.querySelector('#replicationTable tbody');
    tbody.innerHTML = '';
    
    if (status.replicaSet && status.replicaSet.members) {
        status.replicaSet.members.forEach(member => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${member.name}</td>
                <td><span class="badge bg-${getStateColor(member.state)}">${member.stateStr}</span></td>
                <td><span class="badge bg-${member.health === 1 ? 'success' : 'danger'}">${member.health === 1 ? 'Healthy' : 'Unhealthy'}</span></td>
                <td>${formatDuration(member.optimeDate ? (Date.now() - new Date(member.optimeDate).getTime()) : 0)}</td>
                <td>${member.optimeDate ? new Date(member.optimeDate).toLocaleString() : 'N/A'}</td>
            `;
            tbody.appendChild(row);
        });
    }
}

// Update nodes tab
function updateNodesTab(status) {
    const container = document.getElementById('nodesContainer');
    container.innerHTML = '';
    
    status.nodes.forEach(node => {
        const nodeCard = createNodeCard(node);
        container.appendChild(nodeCard);
    });
}

// Create node card
function createNodeCard(node) {
    const col = document.createElement('div');
    col.className = 'col-md-6 col-lg-4 node-card';
    
    col.innerHTML = `
        <div class="card">
            <div class="node-header node-role-${node.role}">
                <div>
                    <h5 class="mb-1">${node.hostname}</h5>
                    <small>${node.ip}:${node.port}</small>
                </div>
                <div>
                    <span class="badge bg-light text-dark">${node.role.toUpperCase()}</span>
                </div>
            </div>
            <div class="node-stats">
                <div class="stat-item">
                    <div class="stat-value ${node.status === 'online' ? 'text-success' : 'text-danger'}">
                        <i class="bi bi-${node.status === 'online' ? 'check-circle' : 'x-circle'}"></i>
                    </div>
                    <div class="stat-label">Status</div>
                </div>
                ${node.status === 'online' && node.serverStatus ? `
                    <div class="stat-item">
                        <div class="stat-value">${node.connections ? node.connections.current : 'N/A'}</div>
                        <div class="stat-label">Connections</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${node.memory ? formatBytes(node.memory.resident * 1024 * 1024) : 'N/A'}</div>
                        <div class="stat-label">Memory</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${node.uptime ? formatDuration(node.uptime * 1000) : 'N/A'}</div>
                        <div class="stat-label">Uptime</div>
                    </div>
                ` : ''}
            </div>
            <div class="card-footer">
                <button class="btn btn-sm btn-outline-primary" onclick="showNodeDetails(${node.id})">
                    <i class="bi bi-info-circle"></i> Details
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="openSSHTab(${node.id})">
                    <i class="bi bi-terminal"></i> SSH
                </button>
            </div>
        </div>
    `;
    
    return col;
}

// Initialize charts
function initializeCharts() {
    // Operations chart
    const opsCtx = document.getElementById('opsChart').getContext('2d');
    charts.operations = new Chart(opsCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Operations/sec',
                data: [],
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Memory chart
    const memCtx = document.getElementById('memoryChart').getContext('2d');
    charts.memory = new Chart(memCtx, {
        type: 'doughnut',
        data: {
            labels: ['Used', 'Available'],
            datasets: [{
                data: [0, 100],
                backgroundColor: ['#dc3545', '#28a745']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
    
    // Storage chart
    const storageCtx = document.getElementById('storageChart').getContext('2d');
    charts.storage = new Chart(storageCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Storage (GB)',
                data: [],
                backgroundColor: '#17a2b8'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Connections chart
    const connCtx = document.getElementById('connectionsChart').getContext('2d');
    charts.connections = new Chart(connCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Active Connections',
                data: [],
                borderColor: '#ffc107',
                backgroundColor: 'rgba(255, 193, 7, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Update dashboard data from real-time updates
function updateDashboardData(data) {
    if (data.status) {
        updateStatusCards(data.status);
        updateClusterTopology(data.status);
        updateReplicationTable(data.status);
    }
    
    if (data.replicationLag) {
        updateReplicationLag(data.replicationLag);
    }
    
    if (data.metrics) {
        updateCharts(data.metrics);
    }
}

// Update replication lag
function updateReplicationLag(lagInfo) {
    const maxLag = Math.max(...lagInfo.members.map(m => m.lagSeconds));
    document.getElementById('replicationLag').textContent = formatDuration(maxLag * 1000);
}

// Update charts with new data
function updateCharts(metrics) {
    const now = new Date();
    const timeLabel = now.toLocaleTimeString();
    
    // Update operations chart
    if (charts.operations) {
        const totalOps = Object.values(metrics).reduce((sum, node) => {
            if (node.opcounters) {
                return sum + (node.opcounters.insert + node.opcounters.query + node.opcounters.update + node.opcounters.delete);
            }
            return sum;
        }, 0);
        
        charts.operations.data.labels.push(timeLabel);
        charts.operations.data.datasets[0].data.push(totalOps);
        
        // Keep only last 20 data points
        if (charts.operations.data.labels.length > 20) {
            charts.operations.data.labels.shift();
            charts.operations.data.datasets[0].data.shift();
        }
        
        charts.operations.update('none');
    }
    
    // Update memory chart
    if (charts.memory) {
        const totalMemory = Object.values(metrics).reduce((sum, node) => {
            return sum + (node.memory ? node.memory.resident : 0);
        }, 0);
        
        charts.memory.data.datasets[0].data = [totalMemory, Math.max(0, 8192 - totalMemory)]; // Assuming 8GB total
        charts.memory.update('none');
    }
    
    // Update connections chart
    if (charts.connections) {
        const totalConnections = Object.values(metrics).reduce((sum, node) => {
            return sum + (node.connections ? node.connections.current : 0);
        }, 0);
        
        charts.connections.data.labels.push(timeLabel);
        charts.connections.data.datasets[0].data.push(totalConnections);
        
        if (charts.connections.data.labels.length > 20) {
            charts.connections.data.labels.shift();
            charts.connections.data.datasets[0].data.shift();
        }
        
        charts.connections.update('none');
    }
}

// Query form handler
document.getElementById('queryForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const nodeId = document.getElementById('queryNode').value;
    const collection = document.getElementById('queryCollection').value;
    const query = document.getElementById('queryText').value;
    const resultsDiv = document.getElementById('queryResults');
    const statsDiv = document.getElementById('queryStats');
    
    if (!query.trim()) {
        showNotification('Please enter a query', 'warning');
        return;
    }
    
    try {
        resultsDiv.textContent = 'Executing query...';
        statsDiv.textContent = '';
        
        const result = await apiRequest('/api/database/query', {
            method: 'POST',
            body: JSON.stringify({
                query: query,
                collection: collection,
                nodeId: nodeId
            })
        });
        
        if (result.success) {
            resultsDiv.textContent = JSON.stringify(result.result, null, 2);
            statsDiv.textContent = `${result.count} documents, ${result.executionTime}ms`;
            showNotification('Query executed successfully', 'success');
        } else {
            resultsDiv.textContent = `Error: ${result.error}`;
            statsDiv.textContent = '';
            showNotification('Query failed', 'danger');
        }
    } catch (error) {
        console.error('Query error:', error);
        resultsDiv.textContent = `Error: ${error.message}`;
        showNotification('Query failed', 'danger');
    }
});

// SSH form handler
document.getElementById('sshForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const nodeId = document.getElementById('sshNode').value;
    const command = document.getElementById('sshCommand').value;
    const outputDiv = document.getElementById('sshOutput');
    
    if (!command.trim()) {
        showNotification('Please enter a command', 'warning');
        return;
    }
    
    try {
        outputDiv.textContent = 'Executing command...';
        
        const result = await apiRequest(`/api/nodes/${nodeId}/ssh`, {
            method: 'POST',
            body: JSON.stringify({ command })
        });
        
        if (result.success) {
            outputDiv.textContent = result.output || 'Command completed with no output';
            showNotification('Command executed successfully', 'success');
        } else {
            outputDiv.textContent = `Error: ${result.error}\n${result.output || ''}`;
            showNotification('Command failed', 'danger');
        }
    } catch (error) {
        console.error('SSH error:', error);
        outputDiv.textContent = `Error: ${error.message}`;
        showNotification('SSH command failed', 'danger');
    }
});

// Populate dropdowns
function populateDropdowns() {
    if (config.mongodb_cluster && config.mongodb_cluster.nodes) {
        // Query node dropdown
        const queryNodeSelect = document.getElementById('queryNode');
        queryNodeSelect.innerHTML = '<option value="replica_set">Replica Set</option>';
        
        // SSH node dropdown
        const sshNodeSelect = document.getElementById('sshNode');
        sshNodeSelect.innerHTML = '';
        
        config.mongodb_cluster.nodes.forEach(node => {
            const queryOption = document.createElement('option');
            queryOption.value = node.id;
            queryOption.textContent = `${node.hostname} (${node.role})`;
            queryNodeSelect.appendChild(queryOption);
            
            const sshOption = document.createElement('option');
            sshOption.value = node.id;
            sshOption.textContent = `${node.hostname} (${node.ip})`;
            sshNodeSelect.appendChild(sshOption);
        });
    }
}

// Configuration management
function updateRawConfig() {
    document.getElementById('rawConfig').value = JSON.stringify(config, null, 2);
}

function updateNodesConfig() {
    const container = document.getElementById('nodesConfig');
    container.innerHTML = '';
    
    if (config.mongodb_cluster && config.mongodb_cluster.nodes) {
        config.mongodb_cluster.nodes.forEach((node, index) => {
            const nodeDiv = document.createElement('div');
            nodeDiv.className = 'config-node';
            nodeDiv.innerHTML = `
                <div class="config-node-header">
                    <h6>Node ${node.id} - ${node.hostname}</h6>
                    <span class="badge bg-${node.role === 'primary' ? 'success' : 'primary'}">${node.role}</span>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <label class="form-label">IP Address</label>
                        <input type="text" class="form-control" value="${node.ip}" onchange="updateNodeConfig(${index}, 'ip', this.value)">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Port</label>
                        <input type="number" class="form-control" value="${node.port}" onchange="updateNodeConfig(${index}, 'port', parseInt(this.value))">
                    </div>
                </div>
            `;
            container.appendChild(nodeDiv);
        });
    }
}

function updateNodeConfig(nodeIndex, field, value) {
    if (config.mongodb_cluster && config.mongodb_cluster.nodes[nodeIndex]) {
        config.mongodb_cluster.nodes[nodeIndex][field] = value;
        updateRawConfig();
    }
}

async function saveConfiguration() {
    try {
        const rawConfig = document.getElementById('rawConfig').value;
        const newConfig = JSON.parse(rawConfig);
        
        await apiRequest('/api/config', {
            method: 'POST',
            body: JSON.stringify(newConfig)
        });
        
        config = newConfig;
        updateNodesConfig();
        populateDropdowns();
        showNotification('Configuration saved successfully', 'success');
    } catch (error) {
        console.error('Save configuration error:', error);
        showNotification('Failed to save configuration', 'danger');
    }
}

// Utility functions
function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}

function formatBytes(bytes) {
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 B';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDuration(ms) {
    if (ms < 1000) return ms + 'ms';
    if (ms < 60000) return Math.round(ms / 1000) + 's';
    if (ms < 3600000) return Math.round(ms / 60000) + 'm';
    return Math.round(ms / 3600000) + 'h';
}

function getStateColor(state) {
    switch (state) {
        case 1: return 'success'; // PRIMARY
        case 2: return 'primary'; // SECONDARY
        case 7: return 'info';    // ARBITER
        default: return 'secondary';
    }
}

function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-floating alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// SSH helper functions
function setSSHCommand(command) {
    document.getElementById('sshCommand').value = command;
}

function clearSSHOutput() {
    document.getElementById('sshOutput').textContent = 'Ready for SSH commands...';
}

function openSSHTab(nodeId) {
    // Switch to SSH tab
    const sshTab = new bootstrap.Tab(document.getElementById('ssh-tab'));
    sshTab.show();
    
    // Select the node
    document.getElementById('sshNode').value = nodeId;
}

function showNodeDetails(nodeId) {
    // Switch to nodes tab and scroll to node
    const nodesTab = new bootstrap.Tab(document.getElementById('nodes-tab'));
    nodesTab.show();
    
    // You could implement a detailed modal here
    showNotification(`Showing details for node ${nodeId}`, 'info');
}

// Periodic updates
function startPeriodicUpdates() {
    updateInterval = setInterval(async () => {
        try {
            await updateClusterStatus();
            await updateDatabaseStats();
        } catch (error) {
            console.error('Periodic update error:', error);
        }
    }, 30000); // Update every 30 seconds
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (socket) {
        socket.disconnect();
    }
});