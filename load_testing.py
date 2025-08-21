#!/usr/bin/env python3
"""
MongoDB Replication Load Testing Tool
Tests concurrent read/write operations and report generation across all nodes
"""

import json
import time
import threading
import random
import statistics
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import concurrent.futures
import argparse
import csv
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
import queue
import signal
import sys

class MongoDBLoadTester:
    def __init__(self, config_file="accounts.json"):
        self.config = self.load_config(config_file)
        self.clients = {}
        self.results = {
            'read_operations': [],
            'write_operations': [],
            'report_generation': [],
            'replication_lag': [],
            'errors': []
        }
        self.setup_connections()
        self.stop_testing = False
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def setup_connections(self):
        """Setup connections to all MongoDB nodes"""
        print("Setting up connections to MongoDB nodes...")
        
        for node in self.config['nodes']:
            try:
                # Connect to individual node
                connection_string = f"mongodb://{node['user']}:{node['password']}@{node['ip']}:{node['port']}/admin"
                client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
                
                # Test connection
                client.admin.command('ping')
                self.clients[node['ip']] = {
                    'client': client,
                    'db': client[self.config['database_name']],
                    'role': node['role'],
                    'hostname': node['hostname']
                }
                print(f"✓ Connected to {node['hostname']} ({node['ip']}) - {node['role']}")
                
            except Exception as e:
                print(f"✗ Failed to connect to {node['ip']}: {e}")
        
        if not self.clients:
            raise Exception("No MongoDB connections established")
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\nStopping load testing...")
        self.stop_testing = True
    
    def measure_replication_lag(self):
        """Measure replication lag between nodes"""
        try:
            primary_client = None
            secondary_clients = []
            
            # Find primary and secondary nodes
            for ip, client_info in self.clients.items():
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
                    lag_results[secondary['hostname']] = -1  # Error
                    self.results['errors'].append({
                        'timestamp': datetime.now(),
                        'operation': 'replication_lag',
                        'node': secondary['hostname'],
                        'error': str(e)
                    })
            
            self.results['replication_lag'].append({
                'timestamp': datetime.now(),
                'lags': lag_results
            })
            
        except Exception as e:
            self.results['errors'].append({
                'timestamp': datetime.now(),
                'operation': 'replication_lag',
                'error': str(e)
            })
    
    def read_operation(self, client_info, operation_id):
        """Perform read operation"""
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            # Random read operations
            operations = [
                # Count employees
                lambda: client_info['db'].employees.count_documents({}),
                # Find random employee
                lambda: client_info['db'].employees.find_one({}),
                # Aggregate attendance data
                lambda: list(client_info['db'].attendance.aggregate([
                    {'$group': {'_id': '$employee_id', 'total_hours': {'$sum': '$total_hours'}}},
                    {'$limit': 10}
                ])),
                # Find employees by department
                lambda: list(client_info['db'].employees.find({'department_id': {'$exists': True}}).limit(50)),
                # Search companies
                lambda: list(client_info['db'].companies.find({'status': 'Active'}).limit(20))
            ]
            
            operation = random.choice(operations)
            result = operation()
            
            success = True
            
        except Exception as e:
            error_msg = str(e)
            self.results['errors'].append({
                'timestamp': datetime.now(),
                'operation': 'read',
                'node': client_info['hostname'],
                'error': error_msg
            })
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        self.results['read_operations'].append({
            'timestamp': datetime.now(),
            'node': client_info['hostname'],
            'operation_id': operation_id,
            'duration_ms': duration,
            'success': success,
            'error': error_msg
        })
        
        return duration, success
    
    def write_operation(self, client_info, operation_id):
        """Perform write operation"""
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            # Random write operations
            operations = [
                # Update employee
                lambda: client_info['db'].employees.update_one(
                    {'_id': {'$exists': True}},
                    {'$set': {'updated_at': datetime.now()}}
                ),
                # Insert attendance record
                lambda: client_info['db'].attendance.insert_one({
                    '_id': f"test_{operation_id}_{int(time.time())}",
                    'employee_id': f"test_emp_{operation_id}",
                    'company_id': f"test_company_{operation_id}",
                    'date': datetime.now().date(),
                    'check_in': datetime.now(),
                    'check_out': datetime.now() + timedelta(hours=8),
                    'total_hours': 8.0,
                    'status': 'Present',
                    'created_at': datetime.now()
                }),
                # Update company
                lambda: client_info['db'].companies.update_one(
                    {'_id': {'$exists': True}},
                    {'$inc': {'employee_count': 1}}
                ),
                # Insert leave request
                lambda: client_info['db'].leave_requests.insert_one({
                    '_id': f"test_leave_{operation_id}_{int(time.time())}",
                    'employee_id': f"test_emp_{operation_id}",
                    'company_id': f"test_company_{operation_id}",
                    'leave_type': 'Annual Leave',
                    'start_date': datetime.now().date(),
                    'end_date': datetime.now().date() + timedelta(days=5),
                    'status': 'Pending',
                    'created_at': datetime.now()
                })
            ]
            
            operation = random.choice(operations)
            result = operation()
            
            success = True
            
        except Exception as e:
            error_msg = str(e)
            self.results['errors'].append({
                'timestamp': datetime.now(),
                'operation': 'write',
                'node': client_info['hostname'],
                'error': error_msg
            })
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        self.results['write_operations'].append({
            'timestamp': datetime.now(),
            'node': client_info['hostname'],
            'operation_id': operation_id,
            'duration_ms': duration,
            'success': success,
            'error': error_msg
        })
        
        return duration, success
    
    def generate_report(self, client_info, operation_id):
        """Generate complex report (analytics node operation)"""
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            # Complex aggregation queries for reports
            reports = [
                # Employee attendance report
                lambda: list(client_info['db'].attendance.aggregate([
                    {'$match': {'date': {'$gte': datetime.now().date() - timedelta(days=30)}}},
                    {'$group': {
                        '_id': '$employee_id',
                        'total_days': {'$sum': 1},
                        'total_hours': {'$sum': '$total_hours'},
                        'avg_hours_per_day': {'$avg': '$total_hours'}
                    }},
                    {'$sort': {'total_hours': -1}},
                    {'$limit': 100}
                ])),
                
                # Department salary analysis
                lambda: list(client_info['db'].employees.aggregate([
                    {'$lookup': {
                        'from': 'departments',
                        'localField': 'department_id',
                        'foreignField': '_id',
                        'as': 'department'
                    }},
                    {'$unwind': '$department'},
                    {'$group': {
                        '_id': '$department.name',
                        'avg_salary': {'$avg': '$employment_info.base_salary'},
                        'min_salary': {'$min': '$employment_info.base_salary'},
                        'max_salary': {'$max': '$employment_info.base_salary'},
                        'employee_count': {'$sum': 1}
                    }},
                    {'$sort': {'avg_salary': -1}}
                ])),
                
                # Company performance report
                lambda: list(client_info['db'].companies.aggregate([
                    {'$lookup': {
                        'from': 'employees',
                        'localField': '_id',
                        'foreignField': 'company_id',
                        'as': 'employees'
                    }},
                    {'$addFields': {
                        'actual_employee_count': {'$size': '$employees'}
                    }},
                    {'$project': {
                        'name': 1,
                        'industry': 1,
                        'revenue': 1,
                        'employee_count': 1,
                        'actual_employee_count': 1,
                        'revenue_per_employee': {
                            '$divide': ['$revenue', '$actual_employee_count']
                        }
                    }},
                    {'$sort': {'revenue_per_employee': -1}},
                    {'$limit': 50}
                ])),
                
                # Leave analysis report
                lambda: list(client_info['db'].leave_requests.aggregate([
                    {'$match': {'start_date': {'$gte': datetime.now().date() - timedelta(days=365)}}},
                    {'$group': {
                        '_id': '$leave_type',
                        'total_requests': {'$sum': 1},
                        'approved_requests': {
                            '$sum': {'$cond': [{'$eq': ['$status', 'Approved']}, 1, 0]}
                        },
                        'total_days': {'$sum': '$duration_days'},
                        'avg_duration': {'$avg': '$duration_days'}
                    }},
                    {'$addFields': {
                        'approval_rate': {
                            '$multiply': [
                                {'$divide': ['$approved_requests', '$total_requests']},
                                100
                            ]
                        }
                    }}
                ]))
            ]
            
            report = random.choice(reports)
            result = report()
            
            success = True
            
        except Exception as e:
            error_msg = str(e)
            self.results['errors'].append({
                'timestamp': datetime.now(),
                'operation': 'report',
                'node': client_info['hostname'],
                'error': error_msg
            })
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        self.results['report_generation'].append({
            'timestamp': datetime.now(),
            'node': client_info['hostname'],
            'operation_id': operation_id,
            'duration_ms': duration,
            'success': success,
            'error': error_msg
        })
        
        return duration, success
    
    def run_concurrent_operations(self, num_threads=10, duration_seconds=60):
        """Run concurrent operations across all nodes"""
        print(f"Starting load test with {num_threads} threads for {duration_seconds} seconds...")
        
        start_time = time.time()
        operation_id = 0
        
        def worker():
            nonlocal operation_id
            while not self.stop_testing and (time.time() - start_time) < duration_seconds:
                # Select random node
                node_ip = random.choice(list(self.clients.keys()))
                client_info = self.clients[node_ip]
                
                # Random operation type
                operation_type = random.choices(
                    ['read', 'write', 'report'],
                    weights=[0.6, 0.3, 0.1]  # 60% read, 30% write, 10% report
                )[0]
                
                current_operation_id = operation_id
                operation_id += 1
                
                if operation_type == 'read':
                    self.read_operation(client_info, current_operation_id)
                elif operation_type == 'write':
                    self.write_operation(client_info, current_operation_id)
                elif operation_type == 'report':
                    self.generate_report(client_info, current_operation_id)
                
                # Small delay between operations
                time.sleep(random.uniform(0.01, 0.1))
        
        # Start worker threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)
        
        print("Load test completed")
    
    def run_replication_monitoring(self, duration_seconds=60):
        """Monitor replication lag continuously"""
        print(f"Starting replication monitoring for {duration_seconds} seconds...")
        
        start_time = time.time()
        
        while not self.stop_testing and (time.time() - start_time) < duration_seconds:
            self.measure_replication_lag()
            time.sleep(1)  # Check every second
        
        print("Replication monitoring completed")
    
    def generate_report(self, output_file="load_test_results.csv"):
        """Generate comprehensive test report"""
        print("Generating test report...")
        
        # Calculate statistics
        read_durations = [op['duration_ms'] for op in self.results['read_operations'] if op['success']]
        write_durations = [op['duration_ms'] for op in self.results['write_operations'] if op['success']]
        report_durations = [op['duration_ms'] for op in self.results['report_generation'] if op['success']]
        
        # Calculate replication lag statistics
        lag_stats = defaultdict(list)
        for lag_record in self.results['replication_lag']:
            for node, lag in lag_record['lags'].items():
                if lag >= 0:  # Only include valid measurements
                    lag_stats[node].append(lag)
        
        # Write CSV report
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write summary
            writer.writerow(['LOAD TEST SUMMARY'])
            writer.writerow([''])
            writer.writerow(['Operation Type', 'Total Operations', 'Successful', 'Failed', 'Avg Duration (ms)', 'Min Duration (ms)', 'Max Duration (ms)', '95th Percentile (ms)'])
            
            if read_durations:
                writer.writerow([
                    'Read Operations',
                    len(self.results['read_operations']),
                    len(read_durations),
                    len(self.results['read_operations']) - len(read_durations),
                    f"{statistics.mean(read_durations):.2f}",
                    f"{min(read_durations):.2f}",
                    f"{max(read_durations):.2f}",
                    f"{np.percentile(read_durations, 95):.2f}"
                ])
            
            if write_durations:
                writer.writerow([
                    'Write Operations',
                    len(self.results['write_operations']),
                    len(write_durations),
                    len(self.results['write_operations']) - len(write_durations),
                    f"{statistics.mean(write_durations):.2f}",
                    f"{min(write_durations):.2f}",
                    f"{max(write_durations):.2f}",
                    f"{np.percentile(write_durations, 95):.2f}"
                ])
            
            if report_durations:
                writer.writerow([
                    'Report Generation',
                    len(self.results['report_generation']),
                    len(report_durations),
                    len(self.results['report_generation']) - len(report_durations),
                    f"{statistics.mean(report_durations):.2f}",
                    f"{min(report_durations):.2f}",
                    f"{max(report_durations):.2f}",
                    f"{np.percentile(report_durations, 95):.2f}"
                ])
            
            writer.writerow([''])
            writer.writerow(['REPLICATION LAG STATISTICS'])
            writer.writerow(['Node', 'Avg Lag (ms)', 'Min Lag (ms)', 'Max Lag (ms)', '95th Percentile (ms)'])
            
            for node, lags in lag_stats.items():
                writer.writerow([
                    node,
                    f"{statistics.mean(lags):.2f}",
                    f"{min(lags):.2f}",
                    f"{max(lags):.2f}",
                    f"{np.percentile(lags, 95):.2f}"
                ])
            
            writer.writerow([''])
            writer.writerow(['ERRORS'])
            writer.writerow(['Timestamp', 'Operation', 'Node', 'Error'])
            
            for error in self.results['errors']:
                writer.writerow([
                    error['timestamp'],
                    error.get('operation', 'N/A'),
                    error.get('node', 'N/A'),
                    error['error']
                ])
        
        print(f"Report saved to {output_file}")
        
        # Generate charts
        self.generate_charts()
    
    def generate_charts(self):
        """Generate performance charts"""
        try:
            # Prepare data
            read_durations = [op['duration_ms'] for op in self.results['read_operations'] if op['success']]
            write_durations = [op['duration_ms'] for op in self.results['write_operations'] if op['success']]
            report_durations = [op['duration_ms'] for op in self.results['report_generation'] if op['success']]
            
            # Create subplots
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
            
            # Operation duration distribution
            if read_durations:
                ax1.hist(read_durations, bins=50, alpha=0.7, label='Read Operations', color='blue')
            if write_durations:
                ax1.hist(write_durations, bins=50, alpha=0.7, label='Write Operations', color='red')
            if report_durations:
                ax1.hist(report_durations, bins=50, alpha=0.7, label='Report Generation', color='green')
            
            ax1.set_xlabel('Duration (ms)')
            ax1.set_ylabel('Frequency')
            ax1.set_title('Operation Duration Distribution')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Replication lag over time
            if self.results['replication_lag']:
                timestamps = [lag['timestamp'] for lag in self.results['replication_lag']]
                for node in self.results['replication_lag'][0]['lags'].keys():
                    lags = [lag['lags'].get(node, 0) for lag in self.results['replication_lag']]
                    ax2.plot(timestamps, lags, label=node, marker='o', markersize=2)
                
                ax2.set_xlabel('Time')
                ax2.set_ylabel('Replication Lag (ms)')
                ax2.set_title('Replication Lag Over Time')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            
            # Success rate by node
            node_stats = defaultdict(lambda: {'total': 0, 'success': 0})
            
            for op in self.results['read_operations'] + self.results['write_operations'] + self.results['report_generation']:
                node_stats[op['node']]['total'] += 1
                if op['success']:
                    node_stats[op['node']]['success'] += 1
            
            nodes = list(node_stats.keys())
            success_rates = [node_stats[node]['success'] / node_stats[node]['total'] * 100 for node in nodes]
            
            ax3.bar(nodes, success_rates, color=['blue', 'green', 'red'])
            ax3.set_xlabel('Node')
            ax3.set_ylabel('Success Rate (%)')
            ax3.set_title('Operation Success Rate by Node')
            ax3.grid(True, alpha=0.3)
            
            # Average duration by operation type
            operation_types = ['Read', 'Write', 'Report']
            avg_durations = []
            
            if read_durations:
                avg_durations.append(statistics.mean(read_durations))
            else:
                avg_durations.append(0)
            
            if write_durations:
                avg_durations.append(statistics.mean(write_durations))
            else:
                avg_durations.append(0)
            
            if report_durations:
                avg_durations.append(statistics.mean(report_durations))
            else:
                avg_durations.append(0)
            
            ax4.bar(operation_types, avg_durations, color=['blue', 'red', 'green'])
            ax4.set_xlabel('Operation Type')
            ax4.set_ylabel('Average Duration (ms)')
            ax4.set_title('Average Duration by Operation Type')
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig('load_test_charts.png', dpi=300, bbox_inches='tight')
            print("Charts saved to load_test_charts.png")
            
        except Exception as e:
            print(f"Error generating charts: {e}")
    
    def run_load_test(self, num_threads=10, duration_seconds=60):
        """Run complete load test"""
        print("="*60)
        print("MONGODB REPLICATION LOAD TESTING")
        print("="*60)
        print(f"Nodes: {len(self.clients)}")
        print(f"Threads: {num_threads}")
        print(f"Duration: {duration_seconds} seconds")
        print("="*60)
        
        # Start replication monitoring in separate thread
        monitoring_thread = threading.Thread(
            target=self.run_replication_monitoring,
            args=(duration_seconds,)
        )
        monitoring_thread.start()
        
        # Run concurrent operations
        self.run_concurrent_operations(num_threads, duration_seconds)
        
        # Wait for monitoring to complete
        monitoring_thread.join()
        
        # Generate report
        self.generate_report()
        
        print("="*60)
        print("LOAD TESTING COMPLETED")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description='MongoDB Replication Load Testing Tool')
    parser.add_argument('--config', default='accounts.json', help='Configuration file path')
    parser.add_argument('--threads', type=int, default=10, help='Number of concurrent threads')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    parser.add_argument('--output', default='load_test_results.csv', help='Output CSV file')
    
    args = parser.parse_args()
    
    try:
        tester = MongoDBLoadTester(args.config)
        tester.run_load_test(args.threads, args.duration)
    except KeyboardInterrupt:
        print("\nLoad testing interrupted by user")
    except Exception as e:
        print(f"Error during load testing: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()