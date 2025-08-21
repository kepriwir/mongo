#!/usr/bin/env python3
"""
MongoDB Cluster Load Testing Tool
Performs concurrent read/write operations across all replica set nodes
Includes analytics node testing for report generation
"""

import os
import sys
import json
import time
import random
import asyncio
import threading
import multiprocessing
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import statistics

import pymongo
import motor.motor_asyncio
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import psutil
import click
import colorama
from colorama import Fore, Back, Style
from tqdm import tqdm

# Initialize colorama
colorama.init()

class MongoLoadTester:
    def __init__(self, config_file='../config/accounts.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.clients = {}
        self.async_clients = {}
        self.test_results = []
        self.start_time = None
        self.end_time = None
        
        # Test configuration
        self.test_collections = ['employees', 'attendance', 'payroll', 'leaves', 'documents']
        self.operation_weights = {
            'read': 0.6,
            'write': 0.25,
            'update': 0.1,
            'delete': 0.05
        }

    def load_config(self):
        """Load configuration from accounts.json"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Failed to load config: {e}{Style.RESET_ALL}")
            sys.exit(1)

    def setup_connections(self):
        """Setup connections to all MongoDB nodes"""
        print(f"{Fore.CYAN}Setting up connections to MongoDB cluster...{Style.RESET_ALL}")
        
        try:
            # Setup connection to replica set (for writes)
            primary_node = next(node for node in self.config['mongodb_cluster']['nodes'] 
                               if node['role'] == 'primary')
            
            # Replica set connection string
            hosts = []
            for node in self.config['mongodb_cluster']['nodes']:
                hosts.append(f"{node['ip']}:{node['port']}")
            
            rs_connection_string = f"mongodb://{primary_node['user']}:{primary_node['password']}@"
            rs_connection_string += ",".join(hosts)
            rs_connection_string += f"/{self.config['hr_database']['name']}?replicaSet={self.config['mongodb_cluster']['replica_set_name']}"
            
            self.clients['replica_set'] = pymongo.MongoClient(rs_connection_string)
            self.async_clients['replica_set'] = motor.motor_asyncio.AsyncIOMotorClient(rs_connection_string)
            
            # Individual node connections (for read testing)
            for node in self.config['mongodb_cluster']['nodes']:
                node_id = f"node_{node['id']}"
                connection_string = f"mongodb://{node['user']}:{node['password']}@{node['ip']}:{node['port']}/{self.config['hr_database']['name']}"
                
                self.clients[node_id] = pymongo.MongoClient(connection_string)
                self.async_clients[node_id] = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
                
                print(f"{Fore.GREEN}✓{Style.RESET_ALL} Connected to {node['hostname']} ({node['role']})")
            
            # Test connections
            for client_name, client in self.clients.items():
                client.admin.command('ping')
                print(f"{Fore.GREEN}✓{Style.RESET_ALL} {client_name} connection verified")
                
        except Exception as e:
            print(f"{Fore.RED}Failed to setup connections: {e}{Style.RESET_ALL}")
            sys.exit(1)

    def get_random_employee_id(self, client):
        """Get random employee ID for testing"""
        try:
            db = client[self.config['hr_database']['name']]
            sample = list(db.employees.aggregate([{'$sample': {'size': 1}}]))
            return sample[0]['employee_id'] if sample else None
        except:
            return None

    def generate_test_data(self):
        """Generate test data for write operations"""
        return {
            'test_record_id': f"TEST_{random.randint(100000, 999999)}",
            'timestamp': datetime.now(),
            'data': {
                'field1': random.randint(1, 1000),
                'field2': f"test_data_{random.randint(1, 10000)}",
                'field3': random.uniform(0, 100),
                'field4': random.choice(['A', 'B', 'C', 'D', 'E']),
                'field5': [random.randint(1, 100) for _ in range(random.randint(1, 5))]
            },
            'metadata': {
                'test_type': 'load_test',
                'created_by': 'load_tester',
                'thread_id': threading.current_thread().ident
            }
        }

    def perform_read_operation(self, client_name, collection_name):
        """Perform a read operation"""
        start_time = time.time()
        success = False
        error = None
        records_read = 0
        
        try:
            client = self.clients[client_name]
            db = client[self.config['hr_database']['name']]
            collection = db[collection_name]
            
            # Random read operation
            operation_type = random.choice(['find_one', 'find_many', 'aggregate', 'count'])
            
            if operation_type == 'find_one':
                if collection_name == 'employees':
                    employee_id = self.get_random_employee_id(client)
                    if employee_id:
                        result = collection.find_one({'employee_id': employee_id})
                        records_read = 1 if result else 0
                else:
                    result = collection.find_one()
                    records_read = 1 if result else 0
                    
            elif operation_type == 'find_many':
                limit = random.randint(10, 100)
                if collection_name == 'employees':
                    results = list(collection.find().limit(limit))
                else:
                    results = list(collection.find().limit(limit))
                records_read = len(results)
                
            elif operation_type == 'aggregate':
                if collection_name == 'employees':
                    pipeline = [
                        {'$match': {'employment_status': 'Active'}},
                        {'$group': {'_id': '$department', 'count': {'$sum': 1}}},
                        {'$limit': 10}
                    ]
                elif collection_name == 'attendance':
                    pipeline = [
                        {'$match': {'date': {'$gte': datetime.now() - timedelta(days=30)}}},
                        {'$group': {'_id': '$employee_id', 'total_hours': {'$sum': '$work_hours'}}},
                        {'$limit': 50}
                    ]
                else:
                    pipeline = [{'$sample': {'size': 10}}]
                
                results = list(collection.aggregate(pipeline))
                records_read = len(results)
                
            else:  # count
                if collection_name == 'employees':
                    records_read = collection.count_documents({'employment_status': 'Active'})
                else:
                    records_read = collection.count_documents({})
            
            success = True
            
        except Exception as e:
            error = str(e)
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'operation': 'read',
            'client': client_name,
            'collection': collection_name,
            'success': success,
            'duration': duration,
            'records_affected': records_read,
            'error': error,
            'timestamp': datetime.now(),
            'thread_id': threading.current_thread().ident
        }

    def perform_write_operation(self, collection_name):
        """Perform a write operation (always to replica set)"""
        start_time = time.time()
        success = False
        error = None
        records_written = 0
        
        try:
            client = self.clients['replica_set']
            db = client[self.config['hr_database']['name']]
            
            # Use test collection to avoid interfering with real data
            collection = db[f"{collection_name}_test"]
            
            # Random write operation
            operation_type = random.choice(['insert_one', 'insert_many', 'update_one', 'delete_one'])
            
            if operation_type == 'insert_one':
                test_data = self.generate_test_data()
                result = collection.insert_one(test_data)
                records_written = 1 if result.inserted_id else 0
                
            elif operation_type == 'insert_many':
                count = random.randint(2, 10)
                test_data = [self.generate_test_data() for _ in range(count)]
                result = collection.insert_many(test_data)
                records_written = len(result.inserted_ids)
                
            elif operation_type == 'update_one':
                # Update a random test record
                filter_query = {'metadata.test_type': 'load_test'}
                update_data = {'$set': {'data.updated_at': datetime.now()}}
                result = collection.update_one(filter_query, update_data)
                records_written = result.modified_count
                
            else:  # delete_one
                # Delete a random test record
                filter_query = {'metadata.test_type': 'load_test'}
                result = collection.delete_one(filter_query)
                records_written = result.deleted_count
            
            success = True
            
        except Exception as e:
            error = str(e)
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'operation': 'write',
            'client': 'replica_set',
            'collection': collection_name,
            'success': success,
            'duration': duration,
            'records_affected': records_written,
            'error': error,
            'timestamp': datetime.now(),
            'thread_id': threading.current_thread().ident
        }

    def perform_analytics_operation(self):
        """Perform analytics/reporting operations"""
        start_time = time.time()
        success = False
        error = None
        records_processed = 0
        
        try:
            # Use secondary node for analytics (read preference)
            secondary_nodes = [node for node in self.config['mongodb_cluster']['nodes'] 
                             if node['role'] == 'secondary']
            if secondary_nodes:
                analytics_node = random.choice(secondary_nodes)
                client_name = f"node_{analytics_node['id']}"
                client = self.clients[client_name]
            else:
                client = self.clients['replica_set']
            
            db = client[self.config['hr_database']['name']]
            
            # Random analytics query
            analytics_type = random.choice([
                'employee_summary', 'attendance_report', 'payroll_analysis', 
                'leave_statistics', 'department_metrics'
            ])
            
            if analytics_type == 'employee_summary':
                pipeline = [
                    {'$group': {
                        '_id': {'department': '$department', 'position': '$position'},
                        'count': {'$sum': 1},
                        'avg_salary': {'$avg': '$salary'},
                        'total_salary': {'$sum': '$salary'}
                    }},
                    {'$sort': {'count': -1}},
                    {'$limit': 50}
                ]
                results = list(db.employees.aggregate(pipeline))
                
            elif analytics_type == 'attendance_report':
                pipeline = [
                    {'$match': {'date': {'$gte': datetime.now() - timedelta(days=30)}}},
                    {'$group': {
                        '_id': '$employee_id',
                        'total_days': {'$sum': 1},
                        'total_hours': {'$sum': '$work_hours'},
                        'avg_hours': {'$avg': '$work_hours'},
                        'total_overtime': {'$sum': '$overtime_hours'}
                    }},
                    {'$lookup': {
                        'from': 'employees',
                        'localField': '_id',
                        'foreignField': 'employee_id',
                        'as': 'employee_info'
                    }},
                    {'$limit': 100}
                ]
                results = list(db.attendance.aggregate(pipeline))
                
            elif analytics_type == 'payroll_analysis':
                pipeline = [
                    {'$match': {'period': {'$gte': (datetime.now() - timedelta(days=90)).strftime('%Y-%m')}}},
                    {'$group': {
                        '_id': '$period',
                        'total_gross': {'$sum': '$gross_salary'},
                        'total_net': {'$sum': '$net_salary'},
                        'total_deductions': {'$sum': '$total_deductions'},
                        'employee_count': {'$sum': 1}
                    }},
                    {'$sort': {'_id': -1}}
                ]
                results = list(db.payroll.aggregate(pipeline))
                
            elif analytics_type == 'leave_statistics':
                pipeline = [
                    {'$match': {'start_date': {'$gte': datetime.now() - timedelta(days=365)}}},
                    {'$group': {
                        '_id': {'leave_type': '$leave_type', 'status': '$status'},
                        'count': {'$sum': 1},
                        'avg_duration': {'$avg': '$duration_days'},
                        'total_duration': {'$sum': '$duration_days'}
                    }},
                    {'$sort': {'count': -1}}
                ]
                results = list(db.leaves.aggregate(pipeline))
                
            else:  # department_metrics
                pipeline = [
                    {'$lookup': {
                        'from': 'attendance',
                        'localField': 'employee_id',
                        'foreignField': 'employee_id',
                        'as': 'attendance_data'
                    }},
                    {'$unwind': {'path': '$attendance_data', 'preserveNullAndEmptyArrays': True}},
                    {'$match': {'attendance_data.date': {'$gte': datetime.now() - timedelta(days=30)}}},
                    {'$group': {
                        '_id': '$department',
                        'employee_count': {'$addToSet': '$employee_id'},
                        'total_work_hours': {'$sum': '$attendance_data.work_hours'},
                        'avg_salary': {'$avg': '$salary'}
                    }},
                    {'$project': {
                        'employee_count': {'$size': '$employee_count'},
                        'total_work_hours': 1,
                        'avg_salary': 1
                    }},
                    {'$sort': {'employee_count': -1}}
                ]
                results = list(db.employees.aggregate(pipeline))
            
            records_processed = len(results)
            success = True
            
        except Exception as e:
            error = str(e)
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'operation': 'analytics',
            'client': client_name if 'client_name' in locals() else 'replica_set',
            'collection': 'multiple',
            'success': success,
            'duration': duration,
            'records_affected': records_processed,
            'error': error,
            'timestamp': datetime.now(),
            'thread_id': threading.current_thread().ident,
            'analytics_type': analytics_type if 'analytics_type' in locals() else 'unknown'
        }

    def worker_thread(self, thread_id, operations_per_thread, progress_bar=None):
        """Worker thread for load testing"""
        thread_results = []
        
        for _ in range(operations_per_thread):
            # Choose operation type based on weights
            operation_type = random.choices(
                list(self.operation_weights.keys()),
                weights=list(self.operation_weights.values())
            )[0]
            
            if operation_type == 'read':
                # Choose random client and collection
                client_name = random.choice(list(self.clients.keys()))
                collection_name = random.choice(self.test_collections)
                result = self.perform_read_operation(client_name, collection_name)
                
            elif operation_type in ['write', 'update', 'delete']:
                collection_name = random.choice(self.test_collections)
                result = self.perform_write_operation(collection_name)
                
            else:  # analytics
                result = self.perform_analytics_operation()
            
            result['thread_id'] = thread_id
            thread_results.append(result)
            
            if progress_bar:
                progress_bar.update(1)
            
            # Small delay to prevent overwhelming the system
            time.sleep(random.uniform(0.001, 0.01))
        
        return thread_results

    async def async_worker(self, worker_id, operations_per_worker, progress_bar=None):
        """Async worker for concurrent operations"""
        worker_results = []
        
        for _ in range(operations_per_worker):
            start_time = time.time()
            success = False
            error = None
            
            try:
                # Choose random async client
                client_name = random.choice(list(self.async_clients.keys()))
                client = self.async_clients[client_name]
                db = client[self.config['hr_database']['name']]
                
                # Perform async read operation
                collection_name = random.choice(self.test_collections)
                collection = db[collection_name]
                
                # Simple async read
                result = await collection.find_one()
                success = True
                records_affected = 1 if result else 0
                
            except Exception as e:
                error = str(e)
                records_affected = 0
            
            end_time = time.time()
            duration = end_time - start_time
            
            result_data = {
                'operation': 'async_read',
                'client': client_name,
                'collection': collection_name,
                'success': success,
                'duration': duration,
                'records_affected': records_affected,
                'error': error,
                'timestamp': datetime.now(),
                'worker_id': worker_id
            }
            
            worker_results.append(result_data)
            
            if progress_bar:
                progress_bar.update(1)
            
            # Small async delay
            await asyncio.sleep(random.uniform(0.001, 0.005))
        
        return worker_results

    def run_concurrent_test(self, num_threads=10, operations_per_thread=100):
        """Run concurrent load test"""
        print(f"{Fore.CYAN}Running concurrent test with {num_threads} threads, {operations_per_thread} operations each{Style.RESET_ALL}")
        
        self.start_time = datetime.now()
        total_operations = num_threads * operations_per_thread
        
        with tqdm(total=total_operations, desc="Load Testing", colour='green') as pbar:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                
                for thread_id in range(num_threads):
                    future = executor.submit(self.worker_thread, thread_id, operations_per_thread, pbar)
                    futures.append(future)
                
                # Collect results
                for future in as_completed(futures):
                    try:
                        thread_results = future.result()
                        self.test_results.extend(thread_results)
                    except Exception as e:
                        print(f"{Fore.RED}Thread failed: {e}{Style.RESET_ALL}")
        
        self.end_time = datetime.now()

    async def run_async_test(self, num_workers=20, operations_per_worker=50):
        """Run async load test"""
        print(f"{Fore.CYAN}Running async test with {num_workers} workers, {operations_per_worker} operations each{Style.RESET_ALL}")
        
        total_operations = num_workers * operations_per_worker
        
        with tqdm(total=total_operations, desc="Async Testing", colour='blue') as pbar:
            tasks = []
            
            for worker_id in range(num_workers):
                task = self.async_worker(worker_id, operations_per_worker, pbar)
                tasks.append(task)
            
            # Run all async tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for result in results:
                if isinstance(result, Exception):
                    print(f"{Fore.RED}Async worker failed: {result}{Style.RESET_ALL}")
                else:
                    self.test_results.extend(result)

    def generate_performance_report(self):
        """Generate comprehensive performance report"""
        if not self.test_results:
            print(f"{Fore.RED}No test results to analyze{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.GREEN}=== PERFORMANCE REPORT ==={Style.RESET_ALL}")
        
        df = pd.DataFrame(self.test_results)
        
        # Overall statistics
        total_operations = len(df)
        successful_operations = len(df[df['success'] == True])
        failed_operations = total_operations - successful_operations
        success_rate = (successful_operations / total_operations) * 100
        
        total_duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        operations_per_second = total_operations / total_duration if total_duration > 0 else 0
        
        print(f"{Fore.CYAN}Total Operations:{Style.RESET_ALL} {total_operations:,}")
        print(f"{Fore.CYAN}Successful:{Style.RESET_ALL} {successful_operations:,}")
        print(f"{Fore.CYAN}Failed:{Style.RESET_ALL} {failed_operations:,}")
        print(f"{Fore.CYAN}Success Rate:{Style.RESET_ALL} {success_rate:.2f}%")
        print(f"{Fore.CYAN}Total Duration:{Style.RESET_ALL} {total_duration:.2f} seconds")
        print(f"{Fore.CYAN}Operations/Second:{Style.RESET_ALL} {operations_per_second:.2f}")
        
        # Response time statistics
        response_times = df[df['success'] == True]['duration']
        if len(response_times) > 0:
            print(f"\n{Fore.YELLOW}Response Time Statistics:{Style.RESET_ALL}")
            print(f"  Mean: {response_times.mean():.4f}s")
            print(f"  Median: {response_times.median():.4f}s")
            print(f"  95th percentile: {response_times.quantile(0.95):.4f}s")
            print(f"  99th percentile: {response_times.quantile(0.99):.4f}s")
            print(f"  Max: {response_times.max():.4f}s")
            print(f"  Min: {response_times.min():.4f}s")
        
        # Operation type breakdown
        print(f"\n{Fore.YELLOW}Operation Type Breakdown:{Style.RESET_ALL}")
        operation_stats = df.groupby('operation').agg({
            'success': ['count', 'sum'],
            'duration': ['mean', 'median', 'max']
        }).round(4)
        print(operation_stats)
        
        # Client performance
        print(f"\n{Fore.YELLOW}Client Performance:{Style.RESET_ALL}")
        client_stats = df.groupby('client').agg({
            'success': ['count', 'sum'],
            'duration': ['mean', 'median']
        }).round(4)
        print(client_stats)
        
        # Error analysis
        if failed_operations > 0:
            print(f"\n{Fore.RED}Error Analysis:{Style.RESET_ALL}")
            error_df = df[df['success'] == False]
            error_counts = error_df['error'].value_counts()
            print(error_counts)
        
        # Generate charts
        self.generate_charts(df)
        
        # Save detailed results
        self.save_results(df)

    def generate_charts(self, df):
        """Generate performance charts"""
        print(f"\n{Fore.CYAN}Generating performance charts...{Style.RESET_ALL}")
        
        # Create results directory
        results_dir = Path('load_test_results')
        results_dir.mkdir(exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Response time distribution
        plt.figure(figsize=(12, 8))
        
        plt.subplot(2, 2, 1)
        successful_ops = df[df['success'] == True]
        plt.hist(successful_ops['duration'], bins=50, alpha=0.7, edgecolor='black')
        plt.xlabel('Response Time (seconds)')
        plt.ylabel('Frequency')
        plt.title('Response Time Distribution')
        plt.grid(True, alpha=0.3)
        
        # Operations per second over time
        plt.subplot(2, 2, 2)
        df['timestamp_numeric'] = pd.to_numeric(df['timestamp'])
        time_buckets = pd.cut(df['timestamp_numeric'], bins=20)
        ops_per_bucket = df.groupby(time_buckets).size()
        bucket_duration = (df['timestamp_numeric'].max() - df['timestamp_numeric'].min()) / 20 / 1e9  # Convert to seconds
        ops_per_second = ops_per_bucket / bucket_duration
        
        plt.plot(range(len(ops_per_second)), ops_per_second, marker='o')
        plt.xlabel('Time Bucket')
        plt.ylabel('Operations/Second')
        plt.title('Throughput Over Time')
        plt.grid(True, alpha=0.3)
        
        # Success rate by operation type
        plt.subplot(2, 2, 3)
        success_by_operation = df.groupby('operation')['success'].agg(['count', 'sum'])
        success_by_operation['success_rate'] = (success_by_operation['sum'] / success_by_operation['count']) * 100
        
        bars = plt.bar(success_by_operation.index, success_by_operation['success_rate'])
        plt.xlabel('Operation Type')
        plt.ylabel('Success Rate (%)')
        plt.title('Success Rate by Operation Type')
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{height:.1f}%', ha='center', va='bottom')
        
        # Response time by client
        plt.subplot(2, 2, 4)
        client_response_times = df[df['success'] == True].groupby('client')['duration'].mean()
        bars = plt.bar(range(len(client_response_times)), client_response_times.values)
        plt.xlabel('Client')
        plt.ylabel('Average Response Time (s)')
        plt.title('Average Response Time by Client')
        plt.xticks(range(len(client_response_times)), client_response_times.index, rotation=45)
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(results_dir / 'load_test_charts.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} Charts saved to {results_dir}/load_test_charts.png")

    def save_results(self, df):
        """Save detailed test results"""
        results_dir = Path('load_test_results')
        results_dir.mkdir(exist_ok=True)
        
        # Save raw data
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # CSV export
        csv_file = results_dir / f'load_test_results_{timestamp}.csv'
        df.to_csv(csv_file, index=False)
        
        # JSON export
        json_file = results_dir / f'load_test_results_{timestamp}.json'
        df.to_json(json_file, orient='records', date_format='iso', indent=2)
        
        # Summary report
        summary_file = results_dir / f'load_test_summary_{timestamp}.txt'
        with open(summary_file, 'w') as f:
            f.write("MongoDB Cluster Load Test Summary\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Test Date: {datetime.now()}\n")
            f.write(f"Configuration: {self.config_file}\n")
            f.write(f"Total Operations: {len(df):,}\n")
            f.write(f"Successful Operations: {len(df[df['success'] == True]):,}\n")
            f.write(f"Success Rate: {(len(df[df['success'] == True]) / len(df)) * 100:.2f}%\n")
            
            if self.start_time and self.end_time:
                duration = (self.end_time - self.start_time).total_seconds()
                f.write(f"Test Duration: {duration:.2f} seconds\n")
                f.write(f"Operations/Second: {len(df) / duration:.2f}\n")
        
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} Results saved to {results_dir}/")

    def cleanup_test_data(self):
        """Clean up test data created during load testing"""
        print(f"{Fore.CYAN}Cleaning up test data...{Style.RESET_ALL}")
        
        try:
            client = self.clients['replica_set']
            db = client[self.config['hr_database']['name']]
            
            # Remove test collections
            test_collections = [f"{col}_test" for col in self.test_collections]
            for collection_name in test_collections:
                if collection_name in db.list_collection_names():
                    result = db[collection_name].delete_many({'metadata.test_type': 'load_test'})
                    print(f"{Fore.GREEN}✓{Style.RESET_ALL} Cleaned {result.deleted_count} test records from {collection_name}")
            
        except Exception as e:
            print(f"{Fore.RED}Failed to cleanup test data: {e}{Style.RESET_ALL}")

    def monitor_system_resources(self, duration=60):
        """Monitor system resources during testing"""
        print(f"{Fore.CYAN}Monitoring system resources for {duration} seconds...{Style.RESET_ALL}")
        
        resource_data = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            resource_data.append({
                'timestamp': datetime.now(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'disk_percent': disk.percent,
                'network_bytes_sent': network.bytes_sent,
                'network_bytes_recv': network.bytes_recv
            })
            
            time.sleep(1)
        
        # Save resource monitoring data
        results_dir = Path('load_test_results')
        results_dir.mkdir(exist_ok=True)
        
        resource_df = pd.DataFrame(resource_data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        resource_df.to_csv(results_dir / f'system_resources_{timestamp}.csv', index=False)
        
        print(f"{Fore.GREEN}✓{Style.RESET_ALL} System resource data saved")

@click.command()
@click.option('--threads', default=10, help='Number of concurrent threads')
@click.option('--operations', default=100, help='Operations per thread')
@click.option('--async-workers', default=20, help='Number of async workers')
@click.option('--async-operations', default=50, help='Operations per async worker')
@click.option('--config', default='../config/accounts.json', help='Configuration file')
@click.option('--cleanup/--no-cleanup', default=True, help='Cleanup test data after testing')
@click.option('--monitor-resources', is_flag=True, help='Monitor system resources during test')
@click.option('--test-type', type=click.Choice(['concurrent', 'async', 'both']), default='both', help='Type of test to run')
def main(threads, operations, async_workers, async_operations, config, cleanup, monitor_resources, test_type):
    """MongoDB Cluster Load Testing Tool"""
    
    print(f"{Fore.GREEN}=== MongoDB Cluster Load Testing Tool ==={Style.RESET_ALL}")
    print(f"Configuration: {config}")
    print(f"Test Type: {test_type}")
    print(f"Concurrent Threads: {threads}")
    print(f"Operations per Thread: {operations}")
    print(f"Async Workers: {async_workers}")
    print(f"Operations per Worker: {async_operations}")
    print()
    
    try:
        # Initialize load tester
        tester = MongoLoadTester(config)
        
        # Setup connections
        tester.setup_connections()
        
        # Start resource monitoring if requested
        monitor_thread = None
        if monitor_resources:
            monitor_thread = threading.Thread(
                target=tester.monitor_system_resources,
                args=(threads * operations // 10,),  # Monitor for estimated test duration
                daemon=True
            )
            monitor_thread.start()
        
        # Run tests based on type
        if test_type in ['concurrent', 'both']:
            tester.run_concurrent_test(threads, operations)
        
        if test_type in ['async', 'both']:
            asyncio.run(tester.run_async_test(async_workers, async_operations))
        
        # Wait for monitoring to complete
        if monitor_thread:
            monitor_thread.join(timeout=10)
        
        # Generate performance report
        tester.generate_performance_report()
        
        # Cleanup test data
        if cleanup:
            tester.cleanup_test_data()
        
        print(f"\n{Fore.GREEN}Load testing completed successfully!{Style.RESET_ALL}")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Load testing interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Load testing failed: {e}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == '__main__':
    main()