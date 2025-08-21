#!/usr/bin/env python3
"""
Locust Load Testing Configuration for MongoDB Cluster
Web-based load testing with real-time monitoring
"""

import os
import sys
import json
import random
import time
from datetime import datetime, timedelta

import pymongo
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MongoDBUser:
    def __init__(self, config_file='../config/accounts.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.client = None
        self.db = None
        self.setup_connection()

    def load_config(self):
        """Load configuration from accounts.json"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")
            sys.exit(1)

    def setup_connection(self):
        """Setup MongoDB connection"""
        try:
            # Get primary node for writes
            primary_node = next(node for node in self.config['mongodb_cluster']['nodes'] 
                               if node['role'] == 'primary')
            
            # Create connection string for replica set
            hosts = []
            for node in self.config['mongodb_cluster']['nodes']:
                hosts.append(f"{node['ip']}:{node['port']}")
            
            connection_string = f"mongodb://{primary_node['user']}:{primary_node['password']}@"
            connection_string += ",".join(hosts)
            connection_string += f"/{self.config['hr_database']['name']}?replicaSet={self.config['mongodb_cluster']['replica_set_name']}"
            
            self.client = pymongo.MongoClient(connection_string)
            self.db = self.client[self.config['hr_database']['name']]
            
            # Test connection
            self.client.admin.command('ping')
            
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

class MongoLoadTestUser(HttpUser):
    wait_time = between(0.1, 2)  # Wait between 0.1 and 2 seconds between tasks
    
    def on_start(self):
        """Initialize MongoDB connection when user starts"""
        self.mongo = MongoDBUser()
        self.collections = ['employees', 'attendance', 'payroll', 'leaves', 'documents']

    def on_stop(self):
        """Clean up when user stops"""
        if self.mongo and self.mongo.client:
            self.mongo.client.close()

    @task(60)  # 60% of operations are reads
    def read_employees(self):
        """Read employee data"""
        start_time = time.time()
        try:
            # Random read operation
            collection = self.mongo.db.employees
            
            # Different types of read operations
            operation_type = random.choice(['find_one', 'find_many', 'aggregate'])
            
            if operation_type == 'find_one':
                result = collection.find_one({'employment_status': 'Active'})
            elif operation_type == 'find_many':
                results = list(collection.find({'employment_status': 'Active'}).limit(random.randint(10, 50)))
            else:  # aggregate
                pipeline = [
                    {'$match': {'employment_status': 'Active'}},
                    {'$group': {'_id': '$department', 'count': {'$sum': 1}}},
                    {'$limit': 10}
                ]
                results = list(collection.aggregate(pipeline))
            
            # Record success
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name=f"read_employees_{operation_type}",
                response_time=total_time,
                response_length=0,
                exception=None,
                context={}
            )
            
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="read_employees_error",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )

    @task(20)  # 20% of operations are attendance reads
    def read_attendance(self):
        """Read attendance data"""
        start_time = time.time()
        try:
            collection = self.mongo.db.attendance
            
            # Read recent attendance data
            recent_date = datetime.now() - timedelta(days=random.randint(1, 30))
            results = list(collection.find({'date': {'$gte': recent_date}}).limit(100))
            
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="read_attendance",
                response_time=total_time,
                response_length=len(results),
                exception=None,
                context={}
            )
            
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="read_attendance_error",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )

    @task(10)  # 10% of operations are writes
    def write_test_data(self):
        """Write test data"""
        start_time = time.time()
        try:
            collection = self.mongo.db.load_test_data
            
            # Create test document
            test_doc = {
                'test_id': f"test_{random.randint(100000, 999999)}",
                'timestamp': datetime.now(),
                'user_id': self.environment.runner.user_count if hasattr(self.environment.runner, 'user_count') else 1,
                'data': {
                    'value1': random.randint(1, 1000),
                    'value2': random.uniform(0, 100),
                    'value3': random.choice(['A', 'B', 'C', 'D']),
                    'array_data': [random.randint(1, 10) for _ in range(5)]
                }
            }
            
            result = collection.insert_one(test_doc)
            
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="write_test_data",
                response_time=total_time,
                response_length=1,
                exception=None,
                context={}
            )
            
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="write_test_data_error",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )

    @task(5)  # 5% of operations are updates
    def update_test_data(self):
        """Update test data"""
        start_time = time.time()
        try:
            collection = self.mongo.db.load_test_data
            
            # Update random test document
            filter_query = {'data.value1': {'$gte': random.randint(1, 500)}}
            update_query = {'$set': {'updated_at': datetime.now(), 'updated_by': 'locust'}}
            
            result = collection.update_one(filter_query, update_query)
            
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="update_test_data",
                response_time=total_time,
                response_length=result.modified_count,
                exception=None,
                context={}
            )
            
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="update_test_data_error",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )

    @task(5)  # 5% of operations are analytics
    def analytics_query(self):
        """Perform analytics query"""
        start_time = time.time()
        try:
            # Random analytics operation
            analytics_type = random.choice(['payroll_summary', 'department_stats', 'attendance_summary'])
            
            if analytics_type == 'payroll_summary':
                collection = self.mongo.db.payroll
                pipeline = [
                    {'$match': {'period': {'$gte': (datetime.now() - timedelta(days=90)).strftime('%Y-%m')}}},
                    {'$group': {
                        '_id': '$period',
                        'total_gross': {'$sum': '$gross_salary'},
                        'avg_gross': {'$avg': '$gross_salary'},
                        'count': {'$sum': 1}
                    }},
                    {'$sort': {'_id': -1}},
                    {'$limit': 12}
                ]
                
            elif analytics_type == 'department_stats':
                collection = self.mongo.db.employees
                pipeline = [
                    {'$match': {'employment_status': 'Active'}},
                    {'$group': {
                        '_id': '$department',
                        'count': {'$sum': 1},
                        'avg_salary': {'$avg': '$salary'}
                    }},
                    {'$sort': {'count': -1}}
                ]
                
            else:  # attendance_summary
                collection = self.mongo.db.attendance
                pipeline = [
                    {'$match': {'date': {'$gte': datetime.now() - timedelta(days=7)}}},
                    {'$group': {
                        '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$date'}},
                        'total_hours': {'$sum': '$work_hours'},
                        'avg_hours': {'$avg': '$work_hours'},
                        'employee_count': {'$sum': 1}
                    }},
                    {'$sort': {'_id': 1}}
                ]
            
            results = list(collection.aggregate(pipeline))
            
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name=f"analytics_{analytics_type}",
                response_time=total_time,
                response_length=len(results),
                exception=None,
                context={}
            )
            
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="MongoDB",
                name="analytics_error",
                response_time=total_time,
                response_length=0,
                exception=e,
                context={}
            )

# Event handlers for additional monitoring
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when a test starts"""
    print("MongoDB Load Test Starting...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when a test stops"""
    print("MongoDB Load Test Completed!")
    
    # Clean up test data if this is the master
    if isinstance(environment.runner, MasterRunner) or not hasattr(environment, 'runner'):
        try:
            mongo = MongoDBUser()
            result = mongo.db.load_test_data.delete_many({})
            print(f"Cleaned up {result.deleted_count} test documents")
        except Exception as e:
            print(f"Failed to clean up test data: {e}")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Log all requests for debugging"""
    if exception:
        print(f"Request failed: {name} - {exception}")

# Custom web UI extensions (optional)
@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--config", type=str, default="../config/accounts.json", 
                       help="MongoDB configuration file")

if __name__ == "__main__":
    # This allows running the locust file directly for testing
    import subprocess
    import sys
    
    # Run locust with web UI
    cmd = [
        sys.executable, "-m", "locust",
        "-f", __file__,
        "--host", "http://localhost",  # Dummy host since we're testing MongoDB directly
        "--web-host", "0.0.0.0",
        "--web-port", "8089"
    ]
    
    print("Starting Locust Web UI on http://localhost:8089")
    subprocess.run(cmd)