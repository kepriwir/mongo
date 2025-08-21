#!/usr/bin/env python3
import argparse
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Dict

from pymongo import MongoClient
from pymongo.read_preferences import SecondaryPreferred
from pymongo.errors import PyMongoError

from tools.common import load_config, build_replset_uri, get_analytics_node


class Counter:
    def __init__(self):
        self.lock = threading.Lock()
        self.counts: Dict[str, int] = {"read": 0, "write": 0, "analytics": 0, "errors": 0}

    def inc(self, key: str, n: int = 1):
        with self.lock:
            self.counts[key] = self.counts.get(key, 0) + n

    def snapshot(self):
        with self.lock:
            return dict(self.counts)


def worker_read(stop_evt: threading.Event, cfg, counter: Counter):
    uri = build_replset_uri(cfg, auth=True)
    client = MongoClient(uri, read_preference=SecondaryPreferred())
    db = client.hr
    while not stop_evt.is_set():
        try:
            # Random employee lookup and recent attendance
            emp = db.employees.aggregate([{ "$sample": {"size": 1} }]).next()
            _ = list(db.attendance.find({"employee_id": emp["_id"]}).sort("date", -1).limit(30))
            _ = list(db.payroll.find({"employee_id": emp["_id"]}).sort("period", -1).limit(6))
            counter.inc("read")
        except PyMongoError:
            counter.inc("errors")
        except StopIteration:
            time.sleep(0.05)


def worker_write(stop_evt: threading.Event, cfg, counter: Counter):
    uri = build_replset_uri(cfg, auth=True)
    client = MongoClient(uri)  # writes go to primary
    db = client.hr
    while not stop_evt.is_set():
        try:
            emp = db.employees.aggregate([{ "$sample": {"size": 1} }]).next()
            d = datetime.utcnow().date()
            db.attendance.insert_one({
                "employee_id": emp["_id"],
                "date": d,
                "status": random.choice(["present", "late", "absent"]),
                "check_in": datetime.utcnow(),
                "check_out": datetime.utcnow() + timedelta(hours=8),
            })
            counter.inc("write")
        except PyMongoError:
            counter.inc("errors")
        except StopIteration:
            time.sleep(0.05)


def worker_analytics(stop_evt: threading.Event, cfg, counter: Counter):
    analytics = get_analytics_node(cfg)
    if not analytics:
        return
    uri = build_replset_uri(cfg, auth=True, direct=True, target_host=f"{analytics.ip}:27017")
    client = MongoClient(uri)
    db = client.hr
    while not stop_evt.is_set():
        try:
            # Company-wise last 30 days absence rate and payroll sum
            pipeline = [
                {"$lookup": {"from": "employees", "localField": "employee_id", "foreignField": "_id", "as": "emp"}},
                {"$unwind": "$emp"},
                {"$match": {"date": {"$gte": datetime.utcnow().date() - timedelta(days=30)}}},
                {"$group": {"_id": "$emp.company_id", "absent": {"$sum": {"$cond": [{"$eq": ["$status", "absent"]}, 1, 0]}}, "total": {"$sum": 1}}},
                {"$project": {"_id": 1, "absence_rate": {"$divide": ["$absent", {"$max": ["$total", 1]}]}}},
                {"$sort": {"absence_rate": -1}},
                {"$limit": 10},
            ]
            list(db.attendance.aggregate(pipeline, allowDiskUse=True))

            payroll_pipeline = [
                {"$lookup": {"from": "employees", "localField": "employee_id", "foreignField": "_id", "as": "emp"}},
                {"$unwind": "$emp"},
                {"$match": {"period": {"$gte": datetime.utcnow().replace(day=1) - timedelta(days=180)}}},
                {"$group": {"_id": "$emp.company_id", "gross_sum": {"$sum": "$gross"}, "net_sum": {"$sum": "$net"}}},
                {"$sort": {"gross_sum": -1}},
                {"$limit": 10},
            ]
            list(db.payroll.aggregate(payroll_pipeline, allowDiskUse=True))

            counter.inc("analytics")
        except PyMongoError:
            counter.inc("errors")
        time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description="Load tester for MongoDB cluster")
    parser.add_argument("--accounts", default="./accounts.json")
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--read-ratio", type=float, default=0.6)
    parser.add_argument("--write-ratio", type=float, default=0.3)
    parser.add_argument("--analytics-ratio", type=float, default=0.1)
    args = parser.parse_args()

    cfg = load_config(args.accounts)
    stop_evt = threading.Event()
    counter = Counter()

    num_read = int(args.concurrency * args.read_ratio)
    num_write = int(args.concurrency * args.write_ratio)
    num_analytics = max(0, args.concurrency - num_read - num_write)

    threads = []
    for _ in range(num_read):
        t = threading.Thread(target=worker_read, args=(stop_evt, cfg, counter), daemon=True)
        t.start(); threads.append(t)
    for _ in range(num_write):
        t = threading.Thread(target=worker_write, args=(stop_evt, cfg, counter), daemon=True)
        t.start(); threads.append(t)
    for _ in range(num_analytics):
        t = threading.Thread(target=worker_analytics, args=(stop_evt, cfg, counter), daemon=True)
        t.start(); threads.append(t)

    start = time.time()
    last = start
    last_counts = counter.snapshot()
    try:
        while time.time() - start < args.duration:
            time.sleep(2)
            snap = counter.snapshot()
            interval = time.time() - last
            rps = (snap["read"] - last_counts["read"]) / interval
            wps = (snap["write"] - last_counts["write"]) / interval
            aps = (snap["analytics"] - last_counts["analytics"]) / interval
            eps = (snap["errors"] - last_counts["errors"]) / interval
            print(f"RPS {rps:.1f} | WPS {wps:.1f} | APS {aps:.1f} | ERR/s {eps:.2f}")
            last = time.time()
            last_counts = snap
    finally:
        stop_evt.set()
        for t in threads:
            t.join(timeout=3)
    total = counter.snapshot()
    print("Totals:", total)


if __name__ == "__main__":
    main()

