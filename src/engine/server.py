# Self/src/engine/server.py
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import APP_PORT, APP_HOST, STATE_MATRIX_FILE, JOURNAL_LEDGER_FILE
from task_manager import (
    load_tasks,
    add_task,
    complete_task,
    abandon_task,
    list_tasks,
    get_task_stats
)

app = FastAPI(title="SELF. // Mission & Evolution Server")

class TaskCreateRequest(BaseModel):
    title: str
    domain: str = "Self.knowledge"
    xp_value: Optional[int] = None
    priority: str = "MEDIUM"
    category: str = "CUSTOM"
    notes: str = ""

class TaskAbandonRequest(BaseModel):
    reason: str = "Deprioritized / Pivoted"

@app.get("/api/tasks")
def get_all_tasks(status: Optional[str] = None, domain: Optional[str] = None):
    return {"tasks": list_tasks(status=status, domain=domain), "stats": get_task_stats()}

@app.post("/api/tasks")
def create_new_task(req: TaskCreateRequest):
    task = add_task(
        title=req.title,
        domain=req.domain,
        xp_value=req.xp_value,
        priority=req.priority,
        category=req.category,
        notes=req.notes
    )
    return {"success": True, "task": task, "stats": get_task_stats()}

@app.post("/api/tasks/{task_id}/complete")
def complete_existing_task(task_id: str, notes: str = ""):
    task = complete_task(task_id, notes=notes)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": task, "stats": get_task_stats()}

@app.post("/api/tasks/{task_id}/abandon")
def abandon_existing_task(task_id: str, req: TaskAbandonRequest):
    task = abandon_task(task_id, reason=req.reason)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": task, "stats": get_task_stats()}

@app.get("/api/state")
def get_state():
    import json
    if STATE_MATRIX_FILE.exists():
        with open(STATE_MATRIX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/api/journal")
def get_journal():
    import json
    if JOURNAL_LEDGER_FILE.exists():
        with open(JOURNAL_LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"conquered_missions": [], "abandoned_missions": []}

@app.get("/", response_class=HTMLResponse)
def get_tasklist_dashboard():
    dashboard_file = Path(__file__).resolve().parent / "task_dashboard.html"
    if dashboard_file.exists():
        with open(dashboard_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SELF. // Mission Server Running</h1>"

if __name__ == "__main__":
    import uvicorn
    print(f"[*] Starting SELF. Mission Server on http://{APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
