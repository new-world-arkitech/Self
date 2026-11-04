# Self/src/engine/server.py
import sys
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

# UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import APP_PORT, APP_HOST, STATE_MATRIX_FILE, JOURNAL_LEDGER_FILE, ROOT_DIR
from task_manager import (
    load_tasks,
    add_task,
    complete_task,
    abandon_task,
    list_tasks,
    get_task_stats
)
from verification_engine import (
    load_verification_cards,
    get_due_quizzes,
    submit_quiz_answer,
    get_cognitive_retention_summary
)
from psychometrics import compute_psychometrics
from ai_document_analyzer import analyze_document_with_ai, scan_and_analyze_all_domains

app = FastAPI(title="SELF. // Sovereign Life OS & Avatar Evolution Engine")

# CORS middleware for local development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount public directory for 3D models (.glb, .stl) and textures
public_dir = ROOT_DIR / "public"
public_dir.mkdir(parents=True, exist_ok=True)
app.mount("/public", StaticFiles(directory=str(public_dir)), name="public")

# ------------------------------------------------------------------------------
# Request Models
# ------------------------------------------------------------------------------
class TaskCreateRequest(BaseModel):
    title: str
    domain: str = "Self.knowledge"
    xp_value: Optional[int] = None
    priority: str = "MEDIUM"
    category: str = "CUSTOM"
    notes: str = ""

class TaskAbandonRequest(BaseModel):
    reason: str = "Deprioritized / Pivoted"

class QuizSubmitRequest(BaseModel):
    selected_option_index: int

class ReflectionCreateRequest(BaseModel):
    content: str
    focus_domain: Optional[str] = "Self.knowledge"

# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------

@app.get("/api/tasks")
def get_all_tasks(status: Optional[str] = None, domain: Optional[str] = None):
    return {
        "tasks": list_tasks(status=status, domain=domain),
        "stats": get_task_stats()
    }

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

@app.get("/api/quizzes")
def get_quizzes(domain: Optional[str] = None):
    all_cards = load_verification_cards()
    due_cards = get_due_quizzes(domain=domain)
    return {
        "cards": all_cards,
        "due_count": len(due_cards),
        "summary": get_cognitive_retention_summary()
    }

@app.post("/api/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: str, req: QuizSubmitRequest):
    result = submit_quiz_answer(quiz_id, req.selected_option_index)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/api/psychometrics")
def get_psychometrics():
    return compute_psychometrics()

@app.get("/api/state")
def get_state():
    if STATE_MATRIX_FILE.exists():
        with open(STATE_MATRIX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/api/journal")
def get_journal():
    if JOURNAL_LEDGER_FILE.exists():
        with open(JOURNAL_LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"conquered_missions": [], "abandoned_missions": [], "daily_reflections": []}

@app.post("/api/journal/reflection")
def add_journal_reflection(req: ReflectionCreateRequest):
    ledger = {"conquered_missions": [], "abandoned_missions": [], "daily_reflections": []}
    if JOURNAL_LEDGER_FILE.exists():
        try:
            with open(JOURNAL_LEDGER_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": f"ref_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "timestamp": now,
        "domain": req.focus_domain,
        "content": req.content.strip()
    }
    ledger.setdefault("daily_reflections", []).append(entry)

    with open(JOURNAL_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

    return {"success": True, "entry": entry}

@app.post("/api/ai/scan-all")
def trigger_ai_scan_all():
    """Scans domain folders and extracts quizzes & missions with local Ollama model."""
    results = scan_and_analyze_all_domains()
    return {
        "success": True,
        "results": results,
        "message": f"Processed {len(results)} document(s) with local AI."
    }

@app.get("/models/avatar.obj")
def get_avatar_obj():
    for p in [
        ROOT_DIR / "public" / "models" / "woman_avatar.obj",
        ROOT_DIR / "src" / "avatar" / "woman_avatar.obj"
    ]:
        if p.exists():
            return FileResponse(p, media_type="text/plain")
    raise HTTPException(status_code=404, detail="Avatar OBJ not found")

@app.get("/models/avatar.glb")
def get_avatar_glb():
    for p in [
        ROOT_DIR / "public" / "models" / "woman_avatar.glb",
        ROOT_DIR / "src" / "avatar" / "avatar.glb"
    ]:
        if p.exists():
            return FileResponse(p, media_type="model/gltf-binary")
    raise HTTPException(status_code=404, detail="Avatar GLB not found")

@app.get("/", response_class=HTMLResponse)
def get_tasklist_dashboard():
    dashboard_file = Path(__file__).resolve().parent / "task_dashboard.html"
    if dashboard_file.exists():
        with open(dashboard_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>SELF. // Mission Server Running</h1>"

if __name__ == "__main__":
    import uvicorn
    print(f"[*] Starting SELF. AAA Sovereign Server on http://{APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
