#!/usr/bin/env node

/**
 * MongoDB Cluster Dashboard Server
 * Provides web interface for monitoring and managing MongoDB replica set
 */

const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const path = require('path');
const fs = require('fs').promises;
const { MongoClient } = require('mongodb');
const bodyParser = require('body-parser');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const morgan = require('morgan');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { Client } = require('ssh2');
const cron = require('node-cron');
const winston = require('winston');
const moment = require('moment');

// Environment configuration
require('dotenv').config();

// Logger setup
const logger = winston.createLogger({
    level: 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.errors({ stack: true }),
        winston.format.json()
    ),
    defaultMeta: { service: 'mongodb-dashboard' },
    transports: [
        new winston.transports.File({ filename: '../logs/dashboard-error.log', level: 'error' }),
        new winston.transports.File({ filename: '../logs/dashboard.log' }),
        new winston.transports.Console({
            format: winston.format.combine(
                winston.format.colorize(),
                winston.format.simple()
            )
        })
    ]
});

// Express app setup
const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Middleware
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net"],
            styleSrc: ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
            fontSrc: ["'self'", "https://fonts.gstatic.com"],
            imgSrc: ["'self'", "data:", "https:"],
            connectSrc: ["'self'", "ws:", "wss:"]
        }
    }
}));
app.use(compression());
app.use(cors());
app.use(morgan('combined', { stream: { write: message => logger.info(message.trim()) } }));
app.use(bodyParser.json({ limit: '50mb' }));
app.use(bodyParser.urlencoded({ extended: true, limit: '50mb' }));

// Static files
app.use(express.static(path.join(__dirname, 'public')));

// Configuration
let config = {};
let mongoClients = {};
let clusterStatus = {};
let realTimeMetrics = {};

// Load configuration
async function loadConfig() {
    try {
        const configData = await fs.readFile('../config/accounts.json', 'utf8');
        config = JSON.parse(configData);
        logger.info('Configuration loaded successfully');
        return config;
    } catch (error) {
        logger.error('Failed to load configuration:', error);
        throw error;
    }
}

// Setup MongoDB connections
async function setupMongoConnections() {
    try {
        // Connect to replica set
        const primaryNode = config.mongodb_cluster.nodes.find(node => node.role === 'primary');
        const hosts = config.mongodb_cluster.nodes.map(node => `${node.ip}:${node.port}`);
        
        const replicaSetUri = `mongodb://${primaryNode.user}:${primaryNode.password}@${hosts.join(',')}/${config.hr_database.name}?replicaSet=${config.mongodb_cluster.replica_set_name}`;
        
        mongoClients.replicaSet = new MongoClient(replicaSetUri, {
            maxPoolSize: 10,
            serverSelectionTimeoutMS: 5000,
            socketTimeoutMS: 45000,
        });
        
        await mongoClients.replicaSet.connect();
        
        // Connect to individual nodes
        for (const node of config.mongodb_cluster.nodes) {
            const nodeUri = `mongodb://${node.user}:${node.password}@${node.ip}:${node.port}/${config.hr_database.name}`;
            mongoClients[`node_${node.id}`] = new MongoClient(nodeUri, {
                maxPoolSize: 5,
                serverSelectionTimeoutMS: 3000,
                socketTimeoutMS: 30000,
                directConnection: true
            });
            
            try {
                await mongoClients[`node_${node.id}`].connect();
                logger.info(`Connected to node ${node.id} (${node.hostname})`);
            } catch (error) {
                logger.error(`Failed to connect to node ${node.id}:`, error);
            }
        }
        
        logger.info('MongoDB connections established');
    } catch (error) {
        logger.error('Failed to setup MongoDB connections:', error);
        throw error;
    }
}

// Authentication middleware
function authenticateToken(req, res, next) {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];
    
    if (!token) {
        return res.sendStatus(401);
    }
    
    jwt.verify(token, process.env.JWT_SECRET || 'dashboard-secret-key', (err, user) => {
        if (err) return res.sendStatus(403);
        req.user = user;
        next();
    });
}

// Routes

// Authentication
app.post('/api/auth/login', async (req, res) => {
    try {
        const { username, password } = req.body;
        
        // Simple authentication (in production, use proper user management)
        const validUsername = process.env.DASHBOARD_USERNAME || 'admin';
        const validPassword = process.env.DASHBOARD_PASSWORD || 'admin123';
        
        if (username === validUsername && password === validPassword) {
            const token = jwt.sign(
                { username, role: 'admin' },
                process.env.JWT_SECRET || 'dashboard-secret-key',
                { expiresIn: '24h' }
            );
            
            res.json({
                success: true,
                token,
                user: { username, role: 'admin' }
            });
        } else {
            res.status(401).json({ success: false, message: 'Invalid credentials' });
        }
    } catch (error) {
        logger.error('Login error:', error);
        res.status(500).json({ success: false, message: 'Internal server error' });
    }
});

// Cluster status
app.get('/api/cluster/status', authenticateToken, async (req, res) => {
    try {
        const status = await getClusterStatus();
        res.json(status);
    } catch (error) {
        logger.error('Failed to get cluster status:', error);
        res.status(500).json({ error: 'Failed to get cluster status' });
    }
});

// Node details
app.get('/api/nodes/:nodeId', authenticateToken, async (req, res) => {
    try {
        const nodeId = req.params.nodeId;
        const nodeDetails = await getNodeDetails(nodeId);
        res.json(nodeDetails);
    } catch (error) {
        logger.error(`Failed to get node details for ${req.params.nodeId}:`, error);
        res.status(500).json({ error: 'Failed to get node details' });
    }
});

// Database statistics
app.get('/api/database/stats', authenticateToken, async (req, res) => {
    try {
        const stats = await getDatabaseStats();
        res.json(stats);
    } catch (error) {
        logger.error('Failed to get database stats:', error);
        res.status(500).json({ error: 'Failed to get database stats' });
    }
});

// Run query
app.post('/api/database/query', authenticateToken, async (req, res) => {
    try {
        const { query, collection, nodeId } = req.body;
        const result = await runQuery(query, collection, nodeId);
        res.json(result);
    } catch (error) {
        logger.error('Failed to run query:', error);
        res.status(500).json({ error: 'Failed to run query', details: error.message });
    }
});

// SSH to node
app.post('/api/nodes/:nodeId/ssh', authenticateToken, async (req, res) => {
    try {
        const nodeId = req.params.nodeId;
        const { command } = req.body;
        const result = await executeSSHCommand(nodeId, command);
        res.json(result);
    } catch (error) {
        logger.error(`SSH command failed for node ${req.params.nodeId}:`, error);
        res.status(500).json({ error: 'SSH command failed', details: error.message });
    }
});

// Configuration management
app.get('/api/config', authenticateToken, async (req, res) => {
    try {
        res.json(config);
    } catch (error) {
        logger.error('Failed to get configuration:', error);
        res.status(500).json({ error: 'Failed to get configuration' });
    }
});

app.post('/api/config', authenticateToken, async (req, res) => {
    try {
        const newConfig = req.body;
        await saveConfig(newConfig);
        config = newConfig;
        res.json({ success: true, message: 'Configuration saved successfully' });
        
        // Restart connections with new config
        await setupMongoConnections();
    } catch (error) {
        logger.error('Failed to save configuration:', error);
        res.status(500).json({ error: 'Failed to save configuration', details: error.message });
    }
});

// Replication lag monitoring
app.get('/api/replication/lag', authenticateToken, async (req, res) => {
    try {
        const lagInfo = await getReplicationLag();
        res.json(lagInfo);
    } catch (error) {
        logger.error('Failed to get replication lag:', error);
        res.status(500).json({ error: 'Failed to get replication lag' });
    }
});

// Performance metrics
app.get('/api/metrics/performance', authenticateToken, async (req, res) => {
    try {
        const metrics = await getPerformanceMetrics();
        res.json(metrics);
    } catch (error) {
        logger.error('Failed to get performance metrics:', error);
        res.status(500).json({ error: 'Failed to get performance metrics' });
    }
});

// Serve main dashboard
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Helper functions

async function getClusterStatus() {
    try {
        const client = mongoClients.replicaSet;
        const admin = client.db('admin');
        
        // Get replica set status
        const rsStatus = await admin.command({ replSetGetStatus: 1 });
        
        // Get server status for each node
        const nodeStatuses = [];
        
        for (const node of config.mongodb_cluster.nodes) {
            try {
                const nodeClient = mongoClients[`node_${node.id}`];
                if (nodeClient) {
                    const nodeAdmin = nodeClient.db('admin');
                    const serverStatus = await nodeAdmin.command({ serverStatus: 1 });
                    const dbStats = await nodeClient.db(config.hr_database.name).stats();
                    
                    nodeStatuses.push({
                        id: node.id,
                        hostname: node.hostname,
                        ip: node.ip,
                        port: node.port,
                        role: node.role,
                        status: 'online',
                        serverStatus,
                        dbStats,
                        uptime: serverStatus.uptime,
                        connections: serverStatus.connections,
                        memory: serverStatus.mem,
                        opcounters: serverStatus.opcounters
                    });
                }
            } catch (error) {
                nodeStatuses.push({
                    id: node.id,
                    hostname: node.hostname,
                    ip: node.ip,
                    port: node.port,
                    role: node.role,
                    status: 'offline',
                    error: error.message
                });
            }
        }
        
        return {
            replicaSet: rsStatus,
            nodes: nodeStatuses,
            timestamp: new Date()
        };
    } catch (error) {
        logger.error('Error getting cluster status:', error);
        throw error;
    }
}

async function getNodeDetails(nodeId) {
    try {
        const node = config.mongodb_cluster.nodes.find(n => n.id.toString() === nodeId);
        if (!node) {
            throw new Error('Node not found');
        }
        
        const client = mongoClients[`node_${nodeId}`];
        if (!client) {
            throw new Error('Node client not available');
        }
        
        const admin = client.db('admin');
        const db = client.db(config.hr_database.name);
        
        // Get detailed node information
        const serverStatus = await admin.command({ serverStatus: 1 });
        const dbStats = await db.stats();
        const collections = await db.listCollections().toArray();
        
        // Get collection stats
        const collectionStats = [];
        for (const collection of collections) {
            try {
                const stats = await db.collection(collection.name).stats();
                collectionStats.push({
                    name: collection.name,
                    count: stats.count,
                    size: stats.size,
                    avgObjSize: stats.avgObjSize,
                    storageSize: stats.storageSize,
                    indexes: stats.nindexes
                });
            } catch (error) {
                // Skip collections that can't be accessed
            }
        }
        
        return {
            node,
            serverStatus,
            dbStats,
            collections: collectionStats,
            timestamp: new Date()
        };
    } catch (error) {
        logger.error(`Error getting node details for ${nodeId}:`, error);
        throw error;
    }
}

async function getDatabaseStats() {
    try {
        const client = mongoClients.replicaSet;
        const db = client.db(config.hr_database.name);
        
        const stats = await db.stats();
        const collections = await db.listCollections().toArray();
        
        // Get collection counts
        const collectionCounts = {};
        for (const collection of collections) {
            try {
                const count = await db.collection(collection.name).estimatedDocumentCount();
                collectionCounts[collection.name] = count;
            } catch (error) {
                collectionCounts[collection.name] = 0;
            }
        }
        
        return {
            dbStats: stats,
            collections: collectionCounts,
            timestamp: new Date()
        };
    } catch (error) {
        logger.error('Error getting database stats:', error);
        throw error;
    }
}

async function runQuery(queryString, collectionName, nodeId) {
    try {
        let client;
        if (nodeId && nodeId !== 'replica_set') {
            client = mongoClients[`node_${nodeId}`];
        } else {
            client = mongoClients.replicaSet;
        }
        
        if (!client) {
            throw new Error('Client not available');
        }
        
        const db = client.db(config.hr_database.name);
        const collection = db.collection(collectionName);
        
        // Parse and execute query
        const query = JSON.parse(queryString);
        const startTime = Date.now();
        
        let result;
        if (Array.isArray(query)) {
            // Aggregation pipeline
            result = await collection.aggregate(query).limit(100).toArray();
        } else {
            // Find query
            result = await collection.find(query).limit(100).toArray();
        }
        
        const executionTime = Date.now() - startTime;
        
        return {
            success: true,
            result,
            executionTime,
            count: result.length,
            timestamp: new Date()
        };
    } catch (error) {
        logger.error('Error running query:', error);
        return {
            success: false,
            error: error.message,
            timestamp: new Date()
        };
    }
}

async function executeSSHCommand(nodeId, command) {
    return new Promise((resolve, reject) => {
        const node = config.mongodb_cluster.nodes.find(n => n.id.toString() === nodeId);
        if (!node) {
            return reject(new Error('Node not found'));
        }
        
        const conn = new Client();
        let output = '';
        let error = '';
        
        conn.on('ready', () => {
            conn.exec(command, (err, stream) => {
                if (err) return reject(err);
                
                stream.on('close', (code, signal) => {
                    conn.end();
                    resolve({
                        success: code === 0,
                        exitCode: code,
                        output,
                        error,
                        timestamp: new Date()
                    });
                }).on('data', (data) => {
                    output += data.toString();
                }).stderr.on('data', (data) => {
                    error += data.toString();
                });
            });
        }).connect({
            host: node.ip,
            port: 22,
            username: node.ssh_user,
            password: node.ssh_password,
            // privateKey: node.ssh_key_path ? require('fs').readFileSync(node.ssh_key_path) : undefined
        });
        
        // Timeout after 30 seconds
        setTimeout(() => {
            conn.end();
            reject(new Error('SSH command timeout'));
        }, 30000);
    });
}

async function saveConfig(newConfig) {
    try {
        const configPath = '../config/accounts.json';
        await fs.writeFile(configPath, JSON.stringify(newConfig, null, 2));
        logger.info('Configuration saved successfully');
    } catch (error) {
        logger.error('Failed to save configuration:', error);
        throw error;
    }
}

async function getReplicationLag() {
    try {
        const client = mongoClients.replicaSet;
        const admin = client.db('admin');
        
        const rsStatus = await admin.command({ replSetGetStatus: 1 });
        const primary = rsStatus.members.find(member => member.state === 1);
        
        if (!primary) {
            throw new Error('No primary found');
        }
        
        const lagInfo = rsStatus.members.map(member => {
            const lag = primary.optimeDate - member.optimeDate;
            return {
                name: member.name,
                state: member.state,
                stateStr: member.stateStr,
                health: member.health,
                optime: member.optimeDate,
                lag: Math.max(0, lag),
                lagSeconds: Math.max(0, lag / 1000)
            };
        });
        
        return {
            primary: primary.name,
            members: lagInfo,
            timestamp: new Date()
        };
    } catch (error) {
        logger.error('Error getting replication lag:', error);
        throw error;
    }
}

async function getPerformanceMetrics() {
    try {
        const metrics = {};
        
        for (const node of config.mongodb_cluster.nodes) {
            try {
                const client = mongoClients[`node_${node.id}`];
                if (client) {
                    const admin = client.db('admin');
                    const serverStatus = await admin.command({ serverStatus: 1 });
                    
                    metrics[`node_${node.id}`] = {
                        hostname: node.hostname,
                        opcounters: serverStatus.opcounters,
                        connections: serverStatus.connections,
                        memory: serverStatus.mem,
                        network: serverStatus.network,
                        uptime: serverStatus.uptime,
                        timestamp: new Date()
                    };
                }
            } catch (error) {
                metrics[`node_${node.id}`] = {
                    hostname: node.hostname,
                    error: error.message,
                    timestamp: new Date()
                };
            }
        }
        
        return metrics;
    } catch (error) {
        logger.error('Error getting performance metrics:', error);
        throw error;
    }
}

// Real-time monitoring with Socket.IO
io.on('connection', (socket) => {
    logger.info('Client connected to dashboard');
    
    socket.on('subscribe_monitoring', () => {
        logger.info('Client subscribed to monitoring updates');
        socket.join('monitoring');
    });
    
    socket.on('disconnect', () => {
        logger.info('Client disconnected from dashboard');
    });
});

// Periodic monitoring updates
async function sendMonitoringUpdates() {
    try {
        const status = await getClusterStatus();
        const lagInfo = await getReplicationLag();
        const metrics = await getPerformanceMetrics();
        
        io.to('monitoring').emit('cluster_update', {
            status,
            replicationLag: lagInfo,
            metrics,
            timestamp: new Date()
        });
    } catch (error) {
        logger.error('Error sending monitoring updates:', error);
    }
}

// Schedule monitoring updates every 5 seconds
cron.schedule('*/5 * * * * *', sendMonitoringUpdates);

// Startup
async function startServer() {
    try {
        await loadConfig();
        await setupMongoConnections();
        
        const PORT = process.env.PORT || 3000;
        server.listen(PORT, '0.0.0.0', () => {
            logger.info(`MongoDB Cluster Dashboard running on port ${PORT}`);
            console.log(`🚀 Dashboard available at http://localhost:${PORT}`);
            console.log(`📊 Real-time monitoring enabled`);
            console.log(`🔐 Default login: admin / admin123`);
        });
    } catch (error) {
        logger.error('Failed to start server:', error);
        process.exit(1);
    }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
    logger.info('Received SIGTERM, shutting down gracefully');
    
    // Close MongoDB connections
    for (const client of Object.values(mongoClients)) {
        try {
            await client.close();
        } catch (error) {
            logger.error('Error closing MongoDB connection:', error);
        }
    }
    
    server.close(() => {
        logger.info('Server closed');
        process.exit(0);
    });
});

process.on('SIGINT', async () => {
    logger.info('Received SIGINT, shutting down gracefully');
    
    // Close MongoDB connections
    for (const client of Object.values(mongoClients)) {
        try {
            await client.close();
        } catch (error) {
            logger.error('Error closing MongoDB connection:', error);
        }
    }
    
    server.close(() => {
        logger.info('Server closed');
        process.exit(0);
    });
});

// Start the server
startServer();