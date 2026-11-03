# Self/src/engine/task_manager.py
import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from config import (
    STATE_MATRIX_FILE,
    JOURNAL_LEDGER_FILE,
    DOMAINS,
    ABANDONMENT_PENALTY_WEIGHT
)

TASKS_FILE = Path(__file__).resolve().parent / "tasks.json"

DEFAULT_TASK_TEMPLATE = {
    "version": "1.0",
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "tasks": []
}

def load_tasks() -> dict:
    if not TASKS_FILE.exists():
        save_tasks(DEFAULT_TASK_TEMPLATE)
        return DEFAULT_TASK_TEMPLATE
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_TASK_TEMPLATE

def save_tasks(data: dict):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def calculate_tier(xp: int) -> int:
    thresholds = [0, 500, 1500, 3500, 7000]
    tier = 1
    for i, req in enumerate(thresholds):
        if xp >= req:
            tier = i + 1
    return min(5, tier)

def sync_to_state_matrix(domain: str, xp_delta: int):
    """Mutates state_matrix.json when tasks are completed."""
    if not STATE_MATRIX_FILE.exists():
        return

    try:
        with open(STATE_MATRIX_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        domains = state.setdefault("domains", {})
        composite = state.setdefault("avatar_composite", {})
        visual_layers = composite.setdefault("visual_layers", {})

        domain_data = domains.setdefault(domain, {
            "avatar_attribute": DOMAINS.get(domain, {}).get("attribute", "base_mesh_and_vitality"),
            "tier": 1,
            "earned_xp": 0,
            "next_tier_xp": 500,
            "max_available_xp": 1000,
            "document_count": 0,
            "documents": []
        })

        domain_data["earned_xp"] = max(0, domain_data.get("earned_xp", 0) + xp_delta)
        new_tier = calculate_tier(domain_data["earned_xp"])
        domain_data["tier"] = new_tier

        attr = domain_data.get("avatar_attribute", "base_mesh_and_vitality")
        visual_layers[attr] = f"tier_{new_tier}"

        # Recompute overall XP and level
        total_xp = sum(d.get("earned_xp", 0) for d in domains.values())
        composite["total_xp"] = total_xp
        composite["overall_level"] = max(1, (total_xp // 2000) + 1)
        state["last_synced"] = datetime.now(timezone.utc).isoformat()

        with open(STATE_MATRIX_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[!] Warning: Failed to sync state matrix: {e}")

def log_to_journal(entry_type: str, task: dict, reason: str = ""):
    """Logs completed or abandoned tasks to journal_ledger.json."""
    ledger = {
        "conquered_missions": [],
        "abandoned_missions": [],
        "daily_reflections": []
    }
    if JOURNAL_LEDGER_FILE.exists():
        try:
            with open(JOURNAL_LEDGER_FILE, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()

    if entry_type == "CONQUERED":
        ledger.setdefault("conquered_missions", []).append({
            "task_id": task["id"],
            "title": task["title"],
            "domain": task["domain"],
            "xp_earned": task["xp_value"],
            "category": task.get("category", "CUSTOM"),
            "completed_at": now,
            "notes": task.get("notes", "")
        })
    elif entry_type == "ABANDONED":
        ledger.setdefault("abandoned_missions", []).append({
            "task_id": task["id"],
            "title": task["title"],
            "domain": task["domain"],
            "xp_value": task["xp_value"],
            "abandoned_at": now,
            "reason": reason or "Deprioritized / Unspecified",
            "notes": task.get("notes", "")
        })

    JOURNAL_LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

def add_task(title: str, domain: str = "Self.knowledge", xp_value: int = None,
             priority: str = "MEDIUM", category: str = "CUSTOM", notes: str = "",
             source_doc: str = None) -> dict:
    """Creates a new mission/task in the tasklist."""
    data = load_tasks()

    if domain not in DOMAINS:
        domain = "Self.knowledge"

    if xp_value is None:
        xp_value = DOMAINS.get(domain, {}).get("xp_per_task", 50)

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    new_task = {
        "id": task_id,
        "title": title.strip(),
        "domain": domain,
        "xp_value": int(xp_value),
        "status": "PENDING",  # PENDING | IN_PROGRESS | COMPLETED | ABANDONED
        "priority": priority.upper(),  # LOW | MEDIUM | HIGH | CRITICAL
        "category": category,
        "source_doc": source_doc,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "abandoned_at": None,
        "abandon_reason": None
    }

    data.setdefault("tasks", []).append(new_task)
    save_tasks(data)
    print(f"[+] Task Created [{task_id}] ({domain}): {title} (+{xp_value} XP)")
    return new_task

def complete_task(task_id: str, notes: str = "") -> dict:
    """Marks a task as conquered, awards XP, and updates Avatar State."""
    data = load_tasks()
    for task in data.get("tasks", []):
        if task["id"] == task_id or task["id"].endswith(task_id):
            if task["status"] == "COMPLETED":
                print(f"[i] Task {task_id} is already completed.")
                return task

            task["status"] = "COMPLETED"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            if notes:
                task["notes"] = f"{task.get('notes', '')} | {notes}".strip(" | ")

            save_tasks(data)
            sync_to_state_matrix(task["domain"], task["xp_value"])
            log_to_journal("CONQUERED", task)
            print(f"[CONQUERED] Mission Conquered [{task['id']}]: {task['title']} (+{task['xp_value']} XP awarded to {task['domain']})")
            return task

    print(f"[!] Task not found: {task_id}")
    return None

def abandon_task(task_id: str, reason: str = "") -> dict:
    """Marks a task as abandoned and records reason for grit calculation."""
    data = load_tasks()
    for task in data.get("tasks", []):
        if task["id"] == task_id or task["id"].endswith(task_id):
            task["status"] = "ABANDONED"
            task["abandoned_at"] = datetime.now(timezone.utc).isoformat()
            task["abandon_reason"] = reason or "Pivoted / Deprioritized"

            save_tasks(data)
            log_to_journal("ABANDONED", task, reason)
            print(f"[-] Task Abandoned [{task['id']}]: {task['title']} (Reason: {task['abandon_reason']})")
            return task

    print(f"[!] Task not found: {task_id}")
    return None

def list_tasks(status: str = None, domain: str = None):
    data = load_tasks()
    tasks = data.get("tasks", [])
    if status:
        tasks = [t for t in tasks if t["status"].lower() == status.lower()]
    if domain:
        tasks = [t for t in tasks if t["domain"].lower() == domain.lower()]

    return tasks

def get_task_stats() -> dict:
    data = load_tasks()
    tasks = data.get("tasks", [])
    total = len(tasks)
    completed = len([t for t in tasks if t["status"] == "COMPLETED"])
    abandoned = len([t for t in tasks if t["status"] == "ABANDONED"])
    pending = len([t for t in tasks if t["status"] in ("PENDING", "IN_PROGRESS")])
    total_xp_earned = sum(t["xp_value"] for t in tasks if t["status"] == "COMPLETED")

    completion_rate = (completed / total * 100) if total > 0 else 0.0

    return {
        "total_tasks": total,
        "completed": completed,
        "abandoned": abandoned,
        "pending": pending,
        "total_xp_earned": total_xp_earned,
        "completion_rate": round(completion_rate, 1)
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "add" and len(sys.argv) > 2:
            title = sys.argv[2]
            domain = sys.argv[3] if len(sys.argv) > 3 else "Self.knowledge"
            xp = int(sys.argv[4]) if len(sys.argv) > 4 else None
            add_task(title, domain, xp)
        elif cmd == "complete" and len(sys.argv) > 2:
            complete_task(sys.argv[2])
        elif cmd == "abandon" and len(sys.argv) > 2:
            reason = sys.argv[3] if len(sys.argv) > 3 else ""
            abandon_task(sys.argv[2], reason)
        elif cmd == "list":
            status_filter = sys.argv[2] if len(sys.argv) > 2 else None
            tasks = list_tasks(status=status_filter)
            print(f"\n--- SELF. TASKLIST ({len(tasks)} items) ---")
            for t in tasks:
                check = "[DONE]" if t["status"] == "COMPLETED" else ("[-]" if t["status"] == "ABANDONED" else "[ ]")
                print(f"{check} {t['id']} | {t['domain']:<14} | {t['xp_value']:>3} XP | [{t['priority']:<6}] {t['title']}")
        elif cmd == "stats":
            stats = get_task_stats()
            print("\n--- TASKLIST STATS ---")
            for k, v in stats.items():
                print(f"{k}: {v}")
    else:
        print("Self. Task Manager Usage:")
        print("  python task_manager.py add \"<title>\" [domain] [xp]")
        print("  python task_manager.py complete <task_id>")
        print("  python task_manager.py abandon <task_id> [reason]")
        print("  python task_manager.py list [pending|completed|abandoned]")
        print("  python task_manager.py stats")
