# Self/src/engine/ai_document_analyzer.py
import os
import sys
import json
import re
import urllib.request
import urllib.error
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    STATE_MATRIX_FILE,
    SRC_DIR
)
from universal_ingestor import parse_pdf_text, parse_markdown_text, parse_docx_text
from verification_engine import load_verification_cards, save_verification_cards, VerificationState
from task_manager import load_tasks, save_tasks

# Clean base URL (strip /v1 if present)
raw_api_base = os.getenv("LOCAL_LLM_API_BASE", "http://localhost:11434")
OLLAMA_API_BASE = raw_api_base.rstrip("/").removesuffix("/v1")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

def get_available_local_models() -> list[str]:
    """Queries Ollama for installed local models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_API_BASE}/api/tags", headers={"User-Agent": "Self-OS/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def select_best_model(preferred: str = None) -> str:
    """Picks the best available local model (prioritizing custom Arkitech model or llama3.2)."""
    installed = get_available_local_models()
    if not installed:
        return None

    if preferred and preferred in installed:
        return preferred

    # Priority order
    for candidate in ["_beautifulDATA:latest", "llama3.2:3b", "gemma2:2b", "qwen3.5:4b"]:
        if candidate in installed:
            return candidate

    return installed[0]

def query_ollama_json(prompt: str, model_name: str, timeout: int = 35) -> dict:
    """Executes local inference with strict JSON schema enforcement."""
    url = f"{OLLAMA_API_BASE}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 1024
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_response = data.get("response", "").strip()
            # Clean markdown codeblocks if model wrapped output in ```json
            clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response, flags=re.MULTILINE).strip()
            return json.loads(clean_json)
    except Exception as e:
        print(f"[!] Ollama local inference error: {e}")
        return None

def analyze_document_with_ai(file_path: Path, domain: str = "Self.knowledge") -> dict:
    """
    Ingests any document, extracts cognitive sections, queries local AI for quizzes & tasks,
    and updates verification_cards.json and tasks.json.
    """
    ext = file_path.suffix.lower()
    text = ""
    if ext == ".pdf":
        _, text = parse_pdf_text(file_path)
    elif ext in (".md", ".markdown", ".txt"):
        text = parse_markdown_text(file_path)
    elif ext == ".docx":
        text = parse_docx_text(file_path)
    else:
        return {"error": f"Unsupported format: {ext}"}

    if not text.strip():
        return {"error": f"No extractable text found in {file_path.name}"}

    # Take high-density excerpt (first 5,000 characters to fit context cleanly)
    excerpt = text[:5500]

    model_name = select_best_model(DEFAULT_MODEL)
    print(f"[*] Analyzing '{file_path.name}' using local model: {model_name or 'Heuristic Engine'}...")

    analysis_result = None
    if model_name:
        prompt = f"""
You are the Master Verification Engine for the 'Self.' Personal Evolution OS.
Analyze the following documentation excerpt from domain '{domain}':

---
{excerpt}
---

Generate a structured JSON response with exactly two arrays:
1. "quizzes": 2 high-yield Active Recall questions testing deep conceptual comprehension.
   Each item must have:
   - "title": short concept title (string)
   - "question": clear, direct question (string)
   - "options": exactly 4 distinct answer choices (array of strings)
   - "correct_index": integer 0-3 indicating the correct choice
   - "explanation": rationale explaining why the answer is correct (string)
   - "xp_value": integer between 35 and 60

2. "missions": 2 practical, real-world action execution tasks.
   Each item must have:
   - "title": actionable imperative verb title (e.g. "Identify...", "Perform...", "Execute...") (string)
   - "priority": "HIGH" or "MEDIUM" (string)
   - "xp_value": integer between 40 and 75
   - "notes": specific pass criteria or measurement metric (string)

Return ONLY valid JSON matching this schema:
{{
  "quizzes": [...],
  "missions": [...]
}}
"""
        analysis_result = query_ollama_json(prompt, model_name)

    # Fallback heuristic if local model returned None or failed
    if not analysis_result or not isinstance(analysis_result, dict):
        print("[i] Utilizing heuristic semantic synthesis fallback...")
        analysis_result = generate_heuristic_quizzes_and_tasks(file_path, excerpt, domain)

    # 1. Merge Quizzes into verification_cards.json
    quizzes_added = 0
    cards = load_verification_cards()
    existing_questions = {c.get("question") for c in cards}

    for q in analysis_result.get("quizzes", []):
        if q.get("question") and q["question"] not in existing_questions:
            quiz_id = f"ai_quiz_{hashlib.md5(q['question'].encode()).hexdigest()[:8]}"
            cards.append({
                "id": quiz_id,
                "domain": domain,
                "source_doc": file_path.name,
                "title": q.get("title", file_path.stem),
                "question": q["question"],
                "options": q.get("options", ["A", "B", "C", "D"])[:4],
                "correct_index": int(q.get("correct_index", 0)),
                "explanation": q.get("explanation", "Verification concept from " + file_path.name),
                "xp_value": int(q.get("xp_value", 45)),
                "state": VerificationState.UNTESTED,
                "repetitions": 0,
                "ease_factor": 2.5,
                "interval_days": 1,
                "next_due": None,
                "last_reviewed": None
            })
            existing_questions.add(q["question"])
            quizzes_added += 1

    save_verification_cards(cards)

    # 2. Merge Missions into tasks.json
    missions_added = 0
    tasks_data = load_tasks()
    existing_titles = {t.get("title") for t in tasks_data.get("tasks", [])}

    for m in analysis_result.get("missions", []):
        if m.get("title") and m["title"] not in existing_titles:
            task_id = f"task_{hashlib.md5(m['title'].encode()).hexdigest()[:8]}"
            tasks_data.setdefault("tasks", []).append({
                "id": task_id,
                "title": m["title"].strip(),
                "domain": domain,
                "xp_value": int(m.get("xp_value", 50)),
                "status": "PENDING",
                "priority": m.get("priority", "MEDIUM"),
                "category": "AI_SYNTHESIZED_MISSION",
                "source_doc": file_path.name,
                "notes": m.get("notes", f"Synthesized from {file_path.name}"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "abandoned_at": None,
                "abandon_reason": None
            })
            existing_titles.add(m["title"])
            missions_added += 1

    save_tasks(tasks_data)

    print(f"[OK] Document Analysis Complete: +{quizzes_added} Quizzes, +{missions_added} Missions generated for {file_path.name}")
    return {
        "success": True,
        "file": file_path.name,
        "model_used": model_name or "heuristic_engine",
        "quizzes_added": quizzes_added,
        "missions_added": missions_added
    }

def generate_heuristic_quizzes_and_tasks(file_path: Path, text: str, domain: str) -> dict:
    """Rule-based fallback for instant extraction without waiting for AI."""
    title = file_path.stem.replace("_", " ").title()
    return {
        "quizzes": [
            {
                "title": f"Core Thesis of {title}",
                "question": f"What is the foundational protocol articulated in {title}?",
                "options": [
                    f"Systematic mastery and deliberate daily application of {domain} principles",
                    "Passive observation without structured metrics or verification",
                    "Ad-hoc task execution without recovery or routine anchors",
                    "Outsourcing accountability to external third parties"
                ],
                "correct_index": 0,
                "explanation": f"{title} emphasizes sovereign execution, active retention, and metric-tracked progress.",
                "xp_value": 45
            }
        ],
        "missions": [
            {
                "title": f"Execute Core Protocol from {title}",
                "priority": "HIGH",
                "xp_value": 55,
                "notes": f"Implement the primary behavioral recommendation from {file_path.name} within 24 hours."
            }
        ]
    }

def scan_and_analyze_all_domains() -> list[dict]:
    """Scans all domain folders and analyzes documents that lack verification cards."""
    results = []
    cards = load_verification_cards()
    analyzed_docs = {c.get("source_doc") for c in cards if c.get("source_doc")}

    domain_dirs = {
        "Self.knowledge": SRC_DIR / "Self.knowledge",
        "Self.temple": SRC_DIR / "Self.temple"
    }

    for domain_key, dir_path in domain_dirs.items():
        if not dir_path.exists():
            continue
        for f in dir_path.iterdir():
            if f.suffix.lower() in (".md", ".docx", ".pdf") and f.name not in analyzed_docs:
                res = analyze_document_with_ai(f, domain=domain_key)
                results.append(res)

    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        dom = sys.argv[2] if len(sys.argv) > 2 else "Self.knowledge"
        if target.exists():
            analyze_document_with_ai(target, dom)
        else:
            print(f"[!] File not found: {target}")
    else:
        print("[*] Running full domain AI scan...")
        scan_and_analyze_all_domains()
