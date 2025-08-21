import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import paramiko

from tools.common import load_config, build_replset_uri, get_analytics_node


ACCOUNTS_PATH = os.environ.get("ACCOUNTS_PATH", os.path.abspath(os.path.join(os.getcwd(), "accounts.json")))

app = FastAPI(title="MongoDB Cluster Dashboard")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def _status_payload() -> Dict[str, Any]:
    try:
        cfg = load_config(ACCOUNTS_PATH)
        uri = build_replset_uri(cfg, auth=True)
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        status = client.admin.command("replSetGetStatus")
        primary_optime = None
        for m in status.get("members", []):
            if m.get("stateStr") == "PRIMARY":
                primary_optime = m.get("optimeDate")
        rows = []
        for m in status.get("members", []):
            lag = None
            if primary_optime and m.get("optimeDate"):
                try:
                    lag = (primary_optime - m.get("optimeDate")).total_seconds()
                except Exception:
                    lag = None
            rows.append({
                "name": m.get("name"),
                "state": m.get("stateStr"),
                "optime": str(m.get("optimeDate")),
                "lag_seconds": lag,
            })
        return {"ok": True, "members": rows, "time": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status")
async def api_status():
    return JSONResponse(_status_payload())


@app.get("/api/stream/status")
async def stream_status():
    async def event_generator():
        while True:
            payload = _status_payload()
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/config")
async def get_config():
    try:
        with open(ACCOUNTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse({"ok": True, "config": data})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/config")
async def set_config(request: Request):
    try:
        payload = await request.json()
        with open(ACCOUNTS_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/query/test")
async def query_test(request: Request):
    body = await request.json()
    qtype = body.get("type", "employees_top")
    try:
        cfg = load_config(ACCOUNTS_PATH)
        uri = build_replset_uri(cfg, auth=True)
        client = MongoClient(uri)
        db = client.hr
        if qtype == "employees_top":
            docs = list(db.employees.aggregate([
                {"$group": {"_id": "$company_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ]))
        elif qtype == "recent_absent":
            docs = list(db.attendance.aggregate([
                {"$match": {"status": "absent"}},
                {"$sort": {"date": -1}},
                {"$limit": 50},
            ]))
        else:
            docs = []
        return JSONResponse({"ok": True, "docs": docs})
    except PyMongoError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


ALLOWED_COMMANDS = {
    "uptime": "uptime",
    "disk": "df -h",
    "memory": "free -h",
    "mongod": "systemctl is-active mongod",
    "log_tail": "tail -n 100 /var/log/mongodb/mongod.log | tail -n 100",
}


@app.post("/api/ssh")
async def ssh_exec(request: Request):
    body = await request.json()
    node_name = body.get("node")
    cmd_key = body.get("cmd")
    if cmd_key not in ALLOWED_COMMANDS:
        return JSONResponse({"ok": False, "error": "Command not allowed"}, status_code=400)
    try:
        cfg = load_config(ACCOUNTS_PATH)
        node = next((n for n in cfg.nodes if n.name == node_name), None)
        if not node:
            return JSONResponse({"ok": False, "error": "Node not found"}, status_code=404)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(node.ip, port=node.ssh_port, username=node.ssh_user, password=node.ssh_password, look_for_keys=False, allow_agent=False, timeout=15)
        try:
            _, stdout, stderr = client.exec_command(ALLOWED_COMMANDS[cmd_key])
            out = stdout.read().decode()
            err = stderr.read().decode()
        finally:
            client.close()
        return JSONResponse({"ok": True, "stdout": out, "stderr": err})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=False)

