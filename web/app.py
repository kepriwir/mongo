#!/usr/bin/env python3
"""Web dashboard for MongoDB replicaset monitoring & admin.

Features
========
* Live replication lag (ms) using Flask-SocketIO (refresh every 5s)
* Manual ad-hoc query runner
* Node config UI that edits accounts.json
* SSH shell to node (simple command execution)

Run: ``python web/app.py`` then visit http://localhost:5000
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import paramiko
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from pymongo.errors import PyMongoError

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "accounts.json"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "secret-key")
app.config["JSON_SORT_KEYS"] = False
socketio = SocketIO(app, cors_allowed_origins="*")


def load_accounts() -> List[Dict]:
    return json.loads(ACCOUNTS_FILE.read_text())


def mongo_client() -> MongoClient:
    accounts = load_accounts()
    primary_ip = next(a["ip"] for a in accounts if a["role"] == "primary")
    uri = f"mongodb://{primary_ip}:27017/?replicaSet=rs0"
    return MongoClient(uri)


@app.route("/")
def index():
    return render_template("index.html", nodes=load_accounts())


@app.route("/query", methods=["GET", "POST"])
def query():
    result = None
    error = None
    if request.method == "POST":
        q = request.form.get("query")
        try:
            client = mongo_client()
            result = list(client.admin.command("eval", q, nolock=True).values())[-1]
        except PyMongoError as exc:
            error = str(exc)
    return render_template("query.html", result=result, error=error)


@app.route("/config", methods=["GET", "POST"])
def config():
    accounts = load_accounts()
    if request.method == "POST":
        # simple update without validation for brevity
        new_data = request.form.get("accounts_json")
        try:
            parsed = json.loads(new_data)
            ACCOUNTS_FILE.write_text(json.dumps(parsed, indent=2))
            flash("Configuration saved.", "success")
            return redirect(url_for("config"))
        except ValueError as exc:
            flash(f"Invalid JSON: {exc}", "danger")
    return render_template("config.html", accounts_json=json.dumps(accounts, indent=2))


@app.route("/ssh", methods=["POST"])
def ssh_exec():
    data = request.get_json(force=True)
    node_ip = data["ip"]
    cmd = data["cmd"]
    node = next((n for n in load_accounts() if n["ip"] == node_ip), None)
    if not node:
        return jsonify({"error": "Unknown node"}), 400
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(node["ip"], port=node.get("port", 22), username=node["user"], password=node["password"], timeout=5)
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        client.close()
        return jsonify({"stdout": out, "stderr": err})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@socketio.on("connect")
def send_initial_stats():
    emit("replica", fetch_replica_status())


def fetch_replica_status() -> Dict:
    try:
        status = mongo_client().admin.command("replSetGetStatus")
        members = []
        for m in status["members"]:
            members.append({
                "name": m["name"],
                "stateStr": m["stateStr"],
                "lag": int(m.get("optimeDate", datetime.utcnow()).timestamp() * 1000) - int(status["date"].timestamp() * 1000)
            })
        return {"ok": True, "members": members}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


import threading, time

def background_status_thread():
    while True:
        socketio.emit("replica", fetch_replica_status())
        time.sleep(5)

threading.Thread(target=background_status_thread, daemon=True).start()


@app.errorhandler(404)
def not_found(e):
    return redirect(url_for("index"))

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)