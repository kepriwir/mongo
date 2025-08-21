#!/usr/bin/env python3
"""
MongoDB Load Testing Script
Author: AI Generator
Version: 1.0
Description: Load testing for MongoDB replication with concurrent operations
"""

import json
import time
import threading
import random
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import concurrent.futures
import argparse
import sys
import os

class MongoDBLoadTester:
    def __init__(self, config_file="accounts.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.clients = {}
        self.results = {
            "read_operations": [],
            "write_operations": [],
            "analytics_operations": [],
            "replication_lag": []
        }
        self.lock = threading.Lock()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Configuration file {self.config_file} not found")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in configuration file {self.config_file}")
            sys.exit(1)
    
    def connect_to_nodes(self):
        """Connect to all MongoDB nodes"""
        print("Connecting to MongoDB nodes...")
        
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
                    "hostname": node["hostname"]
                }
                
                print(f"  Connected to {node['hostname']} ({node['ip']}) - {node['role']}")
                
            except Exception as e:
                print(f"  Failed to connect to {node['ip']}: {e}")
        
        if not self.clients:
            raise Exception("No MongoDB nodes could be connected")
    
    def get_primary_client(self):
        """Get the primary node client"""
        for ip, client_info in self.clients.items():
            if client_info["role"] == "primary":
                return client_info
        return None
    
    def get_secondary_clients(self):
        """Get all secondary node clients"""
        return [client_info for client_info in self.clients.values() if client_info["role"] == "secondary"]
    
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
                if client_info["role"] == "secondary":
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
    
    def read_operation(self, client_info: Dict[str, Any], operation_type: str) -> Dict[str, Any]:
        """Perform a read operation"""
        start_time = time.time()
        success = False
        error = None
        
        try:
            db = client_info["db"]
            
            if operation_type == "simple_read":
                # Simple document read
                result = db.employees.find_one({"status": "Active"})
                
            elif operation_type == "aggregation":
                # Complex aggregation
                pipeline = [
                    {"$match": {"status": "Active"}},
                    {"$group": {
                        "_id": "$department",
                        "count": {"$sum": 1},
                        "avg_salary": {"$avg": "$salary"}
                    }},
                    {"$sort": {"count": -1}}
                ]
                result = list(db.employees.aggregate(pipeline))
                
            elif operation_type == "range_query":
                # Range query with index
                start_date = datetime.now() - timedelta(days=30)
                result = list(db.attendance.find({
                    "date": {"$gte": start_date}
                }).limit(100))
                
            elif operation_type == "join_query":
                # Join-like query using lookup
                pipeline = [
                    {"$match": {"status": "Active"}},
                    {"$lookup": {
                        "from": "companies",
                        "localField": "company_id",
                        "foreignField": "_id",
                        "as": "company"
                    }},
                    {"$unwind": "$company"},
                    {"$project": {
                        "employee_name": {"$concat": ["$first_name", " ", "$last_name"]},
                        "company_name": "$company.name",
                        "department": 1,
                        "salary": 1
                    }},
                    {"$limit": 50}
                ]
                result = list(db.employees.aggregate(pipeline))
            
            success = True
            
        except Exception as e:
            error = str(e)
            result = None
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return {
            "operation_type": operation_type,
            "node": client_info["hostname"],
            "role": client_info["role"],
            "duration_ms": duration,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def write_operation(self, client_info: Dict[str, Any], operation_type: str) -> Dict[str, Any]:
        """Perform a write operation"""
        start_time = time.time()
        success = False
        error = None
        
        try:
            db = client_info["db"]
            
            if operation_type == "insert":
                # Insert new document
                doc = {
                    "test_id": f"test_{int(time.time())}_{random.randint(1000, 9999)}",
                    "timestamp": datetime.now(),
                    "data": "Load test data",
                    "random_value": random.randint(1, 1000)
                }
                result = db.load_test.insert_one(doc)
                
            elif operation_type == "update":
                # Update existing document
                filter_doc = {"status": "Active"}
                update_doc = {"$set": {"last_updated": datetime.now()}}
                result = db.employees.update_many(filter_doc, update_doc)
                
            elif operation_type == "upsert":
                # Upsert operation
                filter_doc = {"test_id": f"upsert_test_{random.randint(1, 100)}"}
                update_doc = {
                    "$set": {
                        "timestamp": datetime.now(),
                        "value": random.randint(1, 1000)
                    },
                    "$setOnInsert": {"created_at": datetime.now()}
                }
                result = db.load_test.update_one(filter_doc, update_doc, upsert=True)
                
            elif operation_type == "delete":
                # Delete test documents
                filter_doc = {"test_id": {"$regex": "^test_"}}
                result = db.load_test.delete_many(filter_doc)
            
            success = True
            
        except Exception as e:
            error = str(e)
            result = None
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return {
            "operation_type": operation_type,
            "node": client_info["hostname"],
            "role": client_info["role"],
            "duration_ms": duration,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def analytics_operation(self, client_info: Dict[str, Any], operation_type: str) -> Dict[str, Any]:
        """Perform analytics/reporting operation"""
        start_time = time.time()
        success = False
        error = None
        
        try:
            db = client_info["db"]
            
            if operation_type == "payroll_report":
                # Generate payroll report
                pipeline = [
                    {"$match": {"year": datetime.now().year}},
                    {"$group": {
                        "_id": "$month",
                        "total_payroll": {"$sum": "$net_salary"},
                        "avg_salary": {"$avg": "$net_salary"},
                        "employee_count": {"$sum": 1}
                    }},
                    {"$sort": {"_id": 1}}
                ]
                result = list(db.payroll.aggregate(pipeline))
                
            elif operation_type == "attendance_analysis":
                # Attendance analysis
                start_date = datetime.now() - timedelta(days=30)
                pipeline = [
                    {"$match": {"date": {"$gte": start_date}}},
                    {"$group": {
                        "_id": "$employee_id",
                        "total_hours": {"$sum": "$work_hours"},
                        "avg_hours": {"$avg": "$work_hours"},
                        "overtime_hours": {"$sum": "$overtime_hours"},
                        "attendance_days": {"$sum": 1}
                    }},
                    {"$lookup": {
                        "from": "employees",
                        "localField": "_id",
                        "foreignField": "_id",
                        "as": "employee"
                    }},
                    {"$unwind": "$employee"},
                    {"$project": {
                        "employee_name": {"$concat": ["$employee.first_name", " ", "$employee.last_name"]},
                        "department": "$employee.department",
                        "total_hours": 1,
                        "avg_hours": 1,
                        "overtime_hours": 1,
                        "attendance_days": 1
                    }},
                    {"$sort": {"total_hours": -1}},
                    {"$limit": 100}
                ]
                result = list(db.attendance.aggregate(pipeline))
                
            elif operation_type == "leave_analysis":
                # Leave analysis
                pipeline = [
                    {"$group": {
                        "_id": "$leave_type",
                        "total_leaves": {"$sum": 1},
                        "total_days": {"$sum": "$duration_days"},
                        "avg_duration": {"$avg": "$duration_days"}
                    }},
                    {"$sort": {"total_leaves": -1}}
                ]
                result = list(db.leaves.aggregate(pipeline))
                
            elif operation_type == "company_performance":
                # Company performance analysis
                pipeline = [
                    {"$lookup": {
                        "from": "employees",
                        "localField": "company_id",
                        "foreignField": "_id",
                        "as": "employees"
                    }},
                    {"$unwind": "$employees"},
                    {"$group": {
                        "_id": "$name",
                        "employee_count": {"$sum": 1},
                        "avg_salary": {"$avg": "$employees.salary"},
                        "departments": {"$addToSet": "$employees.department"}
                    }},
                    {"$project": {
                        "company_name": "$_id",
                        "employee_count": 1,
                        "avg_salary": 1,
                        "department_count": {"$size": "$departments"}
                    }},
                    {"$sort": {"employee_count": -1}}
                ]
                result = list(db.companies.aggregate(pipeline))
            
            success = True
            
        except Exception as e:
            error = str(e)
            result = None
        
        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return {
            "operation_type": operation_type,
            "node": client_info["hostname"],
            "role": client_info["role"],
            "duration_ms": duration,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def run_concurrent_reads(self, num_threads: int, duration_seconds: int):
        """Run concurrent read operations"""
        print(f"Starting concurrent read test with {num_threads} threads for {duration_seconds} seconds...")
        
        read_operations = ["simple_read", "aggregation", "range_query", "join_query"]
        
        def read_worker():
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                # Randomly select a client (prefer secondary nodes for reads)
                secondary_clients = self.get_secondary_clients()
                if secondary_clients:
                    client_info = random.choice(secondary_clients)
                else:
                    client_info = random.choice(list(self.clients.values()))
                
                operation_type = random.choice(read_operations)
                result = self.read_operation(client_info, operation_type)
                
                with self.lock:
                    self.results["read_operations"].append(result)
                
                # Small delay between operations
                time.sleep(random.uniform(0.1, 0.5))
        
        # Start threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(read_worker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)
        
        print(f"Read test completed. Total operations: {len(self.results['read_operations'])}")
    
    def run_concurrent_writes(self, num_threads: int, duration_seconds: int):
        """Run concurrent write operations"""
        print(f"Starting concurrent write test with {num_threads} threads for {duration_seconds} seconds...")
        
        write_operations = ["insert", "update", "upsert", "delete"]
        
        def write_worker():
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                # Use primary node for writes
                primary_client = self.get_primary_client()
                if primary_client:
                    client_info = primary_client
                else:
                    client_info = random.choice(list(self.clients.values()))
                
                operation_type = random.choice(write_operations)
                result = self.write_operation(client_info, operation_type)
                
                with self.lock:
                    self.results["write_operations"].append(result)
                
                # Small delay between operations
                time.sleep(random.uniform(0.1, 0.5))
        
        # Start threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_worker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)
        
        print(f"Write test completed. Total operations: {len(self.results['write_operations'])}")
    
    def run_analytics_tests(self, num_threads: int, duration_seconds: int):
        """Run analytics/reporting tests"""
        print(f"Starting analytics test with {num_threads} threads for {duration_seconds} seconds...")
        
        analytics_operations = ["payroll_report", "attendance_analysis", "leave_analysis", "company_performance"]
        
        def analytics_worker():
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                # Use secondary nodes for analytics
                secondary_clients = self.get_secondary_clients()
                if secondary_clients:
                    client_info = random.choice(secondary_clients)
                else:
                    client_info = random.choice(list(self.clients.values()))
                
                operation_type = random.choice(analytics_operations)
                result = self.analytics_operation(client_info, operation_type)
                
                with self.lock:
                    self.results["analytics_operations"].append(result)
                
                # Longer delay for analytics operations
                time.sleep(random.uniform(1, 3))
        
        # Start threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(analytics_worker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)
        
        print(f"Analytics test completed. Total operations: {len(self.results['analytics_operations'])}")
    
    def monitor_replication_lag(self, duration_seconds: int, interval_seconds: int = 5):
        """Monitor replication lag during tests"""
        print(f"Starting replication lag monitoring for {duration_seconds} seconds...")
        
        end_time = time.time() + duration_seconds
        
        while time.time() < end_time:
            lag_result = self.measure_replication_lag()
            
            with self.lock:
                self.results["replication_lag"].append(lag_result)
            
            time.sleep(interval_seconds)
        
        print("Replication lag monitoring completed")
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        report = {
            "test_summary": {
                "total_read_operations": len(self.results["read_operations"]),
                "total_write_operations": len(self.results["write_operations"]),
                "total_analytics_operations": len(self.results["analytics_operations"]),
                "replication_lag_measurements": len(self.results["replication_lag"])
            },
            "read_performance": self.analyze_operations(self.results["read_operations"]),
            "write_performance": self.analyze_operations(self.results["write_operations"]),
            "analytics_performance": self.analyze_operations(self.results["analytics_operations"]),
            "replication_lag_analysis": self.analyze_replication_lag(),
            "node_performance": self.analyze_node_performance(),
            "timestamp": datetime.now().isoformat()
        }
        
        return report
    
    def analyze_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze operation performance"""
        if not operations:
            return {"error": "No operations to analyze"}
        
        successful_ops = [op for op in operations if op["success"]]
        failed_ops = [op for op in operations if not op["success"]]
        
        if not successful_ops:
            return {"error": "No successful operations"}
        
        durations = [op["duration_ms"] for op in successful_ops]
        
        return {
            "total_operations": len(operations),
            "successful_operations": len(successful_ops),
            "failed_operations": len(failed_ops),
            "success_rate": len(successful_ops) / len(operations) * 100,
            "avg_duration_ms": statistics.mean(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "median_duration_ms": statistics.median(durations),
            "p95_duration_ms": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
            "p99_duration_ms": statistics.quantiles(durations, n=100)[98] if len(durations) >= 100 else max(durations),
            "operations_per_second": len(successful_ops) / (max(durations) - min(durations)) * 1000 if len(durations) > 1 else 0
        }
    
    def analyze_replication_lag(self) -> Dict[str, Any]:
        """Analyze replication lag data"""
        if not self.results["replication_lag"]:
            return {"error": "No replication lag data"}
        
        all_lags = []
        node_lags = {}
        
        for lag_data in self.results["replication_lag"]:
            for node_ip, lag_info in lag_data.items():
                if isinstance(lag_info, dict) and "lag_ms" in lag_info:
                    lag_ms = lag_info["lag_ms"]
                    all_lags.append(lag_ms)
                    
                    if node_ip not in node_lags:
                        node_lags[node_ip] = []
                    node_lags[node_ip].append(lag_ms)
        
        if not all_lags:
            return {"error": "No valid lag measurements"}
        
        analysis = {
            "overall": {
                "avg_lag_ms": statistics.mean(all_lags),
                "min_lag_ms": min(all_lags),
                "max_lag_ms": max(all_lags),
                "median_lag_ms": statistics.median(all_lags),
                "p95_lag_ms": statistics.quantiles(all_lags, n=20)[18] if len(all_lags) >= 20 else max(all_lags)
            },
            "by_node": {}
        }
        
        for node_ip, lags in node_lags.items():
            analysis["by_node"][node_ip] = {
                "avg_lag_ms": statistics.mean(lags),
                "min_lag_ms": min(lags),
                "max_lag_ms": max(lags),
                "median_lag_ms": statistics.median(lags)
            }
        
        return analysis
    
    def analyze_node_performance(self) -> Dict[str, Any]:
        """Analyze performance by node"""
        node_stats = {}
        
        for node_ip, client_info in self.clients.items():
            node_ops = []
            
            # Collect all operations for this node
            for op_list in [self.results["read_operations"], self.results["write_operations"], self.results["analytics_operations"]]:
                node_ops.extend([op for op in op_list if op["node"] == client_info["hostname"]])
            
            if node_ops:
                successful_ops = [op for op in node_ops if op["success"]]
                durations = [op["duration_ms"] for op in successful_ops]
                
                node_stats[node_ip] = {
                    "hostname": client_info["hostname"],
                    "role": client_info["role"],
                    "total_operations": len(node_ops),
                    "successful_operations": len(successful_ops),
                    "success_rate": len(successful_ops) / len(node_ops) * 100 if node_ops else 0,
                    "avg_duration_ms": statistics.mean(durations) if durations else 0,
                    "min_duration_ms": min(durations) if durations else 0,
                    "max_duration_ms": max(durations) if durations else 0
                }
        
        return node_stats
    
    def save_results(self, filename: str):
        """Save test results to file"""
        report = self.generate_report()
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"Test results saved to {filename}")
    
    def print_summary(self):
        """Print test summary"""
        report = self.generate_report()
        
        print("\n" + "="*60)
        print("LOAD TEST SUMMARY")
        print("="*60)
        
        print(f"Total Read Operations: {report['test_summary']['total_read_operations']}")
        print(f"Total Write Operations: {report['test_summary']['total_write_operations']}")
        print(f"Total Analytics Operations: {report['test_summary']['total_analytics_operations']}")
        
        if "read_performance" in report and "success_rate" in report["read_performance"]:
            print(f"\nRead Performance:")
            print(f"  Success Rate: {report['read_performance']['success_rate']:.2f}%")
            print(f"  Avg Duration: {report['read_performance']['avg_duration_ms']:.2f} ms")
            print(f"  P95 Duration: {report['read_performance']['p95_duration_ms']:.2f} ms")
        
        if "write_performance" in report and "success_rate" in report["write_performance"]:
            print(f"\nWrite Performance:")
            print(f"  Success Rate: {report['write_performance']['success_rate']:.2f}%")
            print(f"  Avg Duration: {report['write_performance']['avg_duration_ms']:.2f} ms")
            print(f"  P95 Duration: {report['write_performance']['p95_duration_ms']:.2f} ms")
        
        if "replication_lag_analysis" in report and "overall" in report["replication_lag_analysis"]:
            print(f"\nReplication Lag:")
            print(f"  Avg Lag: {report['replication_lag_analysis']['overall']['avg_lag_ms']:.2f} ms")
            print(f"  Max Lag: {report['replication_lag_analysis']['overall']['max_lag_ms']:.2f} ms")
            print(f"  P95 Lag: {report['replication_lag_analysis']['overall']['p95_lag_ms']:.2f} ms")
        
        print("="*60)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="MongoDB Load Testing")
    parser.add_argument("--config", type=str, default="accounts.json", help="Configuration file")
    parser.add_argument("--read-threads", type=int, default=10, help="Number of read threads")
    parser.add_argument("--write-threads", type=int, default=5, help="Number of write threads")
    parser.add_argument("--analytics-threads", type=int, default=3, help="Number of analytics threads")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--output", type=str, default="load_test_results.json", help="Output file")
    
    args = parser.parse_args()
    
    # Initialize load tester
    tester = MongoDBLoadTester(args.config)
    
    try:
        # Connect to nodes
        tester.connect_to_nodes()
        
        # Start replication lag monitoring in background
        lag_thread = threading.Thread(
            target=tester.monitor_replication_lag,
            args=(args.duration + 10, 5)
        )
        lag_thread.daemon = True
        lag_thread.start()
        
        # Run tests
        print(f"Starting load test for {args.duration} seconds...")
        
        # Start all test threads
        read_thread = threading.Thread(
            target=tester.run_concurrent_reads,
            args=(args.read_threads, args.duration)
        )
        write_thread = threading.Thread(
            target=tester.run_concurrent_writes,
            args=(args.write_threads, args.duration)
        )
        analytics_thread = threading.Thread(
            target=tester.run_analytics_tests,
            args=(args.analytics_threads, args.duration)
        )
        
        read_thread.start()
        write_thread.start()
        analytics_thread.start()
        
        # Wait for all tests to complete
        read_thread.join()
        write_thread.join()
        analytics_thread.join()
        
        # Wait a bit more for lag monitoring
        time.sleep(10)
        
        # Generate and save results
        tester.save_results(args.output)
        tester.print_summary()
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error during load test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()