from __future__ import annotations

"""Locust load-test against the MongoDB replica-set.

Two user types:
1. CRUDUser – 80% of the traffic: performs random inserts, updates & queries.
2. AnalyticsUser – 20% of the traffic: heavy aggregation (e.g. payroll summarisation) on the analytics secondary.

Run headless:
```
locust -f loadtest/locustfile.py --headless -u 500 -r 50 -t 10m --mongo-uri "mongodb://admin:pass@host1,host2,host3/?replicaSet=rs0"
```
"""

import os
import random
from statistics import mean
from time import time

from locust import User, TaskSet, task, events, between
from pymongo import MongoClient
from pymongo.read_preferences import ReadPreference

MONGO_URI = os.getenv("MONGO_URI") or os.getenv("LOCUST_MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("Provide Mongo URI via env var MONGO_URI or --mongo-uri CLI flag.")

# Locust allows custom CLI flags via env – parse on spawn

class MongoTaskSet(TaskSet):
    def on_start(self):
        # Standard read/write operations use primary
        self.client = MongoClient(MONGO_URI)
        self.db = self.client.hr

    @task(2)
    def read_employee(self):
        start = time()
        emp = self.db.employees.aggregate([{"$sample": {"size": 1}}]).next()
        _ = self.db.payroll.find_one({"employee_id": emp["_id"]})
        events.request_success.fire(request_type="mongo", name="read_employee", response_time=(time()-start)*1000, response_length=1)

    @task(1)
    def write_attendance(self):
        start = time()
        emp = self.db.employees.aggregate([{"$sample": {"size": 1}}]).next()
        doc = {
            "employee_id": emp["_id"],
            "company_id": emp["company_id"],
            "date": datetime.utcnow(),
            "clock_in": datetime.utcnow(),
            "clock_out": datetime.utcnow(),
        }
        self.db.attendance.insert_one(doc)
        events.request_success.fire(request_type="mongo", name="write_attendance", response_time=(time()-start)*1000, response_length=1)

class AnalyticsTaskSet(TaskSet):
    def on_start(self):
        # Prefer reading from secondary analytics
        uri_secondary = MONGO_URI + "&readPreference=secondaryPreferred"
        self.client = MongoClient(uri_secondary, read_preference=ReadPreference.SECONDARY_PREFERRED)
        self.db = self.client.hr

    @task
    def payroll_summary(self):
        start = time()
        pipeline = [
            {"$group": {"_id": "$company_id", "total": {"$sum": "$amount"}, "cnt": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": 5},
        ]
        list(self.db.payroll.aggregate(pipeline))
        events.request_success.fire(request_type="mongo", name="payroll_summary", response_time=(time()-start)*1000, response_length=5)

from datetime import datetime
class CRUDUser(User):
    tasks = {MongoTaskSet: 1}
    wait_time = between(0.01, 0.5)

class AnalyticsUser(User):
    tasks = {AnalyticsTaskSet: 1}
    wait_time = between(1, 3)