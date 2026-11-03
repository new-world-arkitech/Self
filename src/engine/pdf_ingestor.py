import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import fitz  # PyMuPDF

# Base paths relative to Self/src/
SRC_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = SRC_DIR / "engine" / "state_matrix.json"

DOMAINS = {
    "Self.career": {
        "attribute": "armor_and_gear",
        "xp_per_page": 15,
        "xp_per_task": 50
    },
    "Self.credit": {
        "attribute": "material_shader_and_aura",
        "xp_per_page": 10,
        "xp_per_task": 75
    },
    "Self.knowledge": {
        "attribute": "neural_hud_and_glyphs",
        "xp_per_page": 25,
        "xp_per_task": 40
    },
    "Self.temple": {
        "attribute": "base_mesh_and_vitality",
        "xp_per_page": 20,
        "xp_per_task": 60
    }
}

# Regex patterns to auto-detect actionable milestones/goals inside PDF text
ACTION_PATTERNS = [
    re.compile(r"^\s*(?:[-*•]|\[\s*\]|\d+\.)\s+(.*)", re.MULTILINE),
    re.compile(r"(?:Goal|Milestone|Target|Objective|Action)\s*[:\-]\s*(.*)", re.IGNORECASE)
]


def compute_file_hash(filepath: Path) -> str:
    """Generates a SHA-256 hash so modified or renamed PDFs are tracked accurately."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def extract_pdf_milestones(pdf_path: Path, domain_cfg: dict) -> dict:
    """Parses PDF pages, word count, and actionable milestone nodes."""
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    total_words = 0
    extracted_tasks = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        total_words += len(text.split())

        for pattern in ACTION_PATTERNS:
            matches = pattern.findall(text)
            for match in matches:
                cleaned = match.strip()
                # Filter out noise (too short or overly long paragraph fragments)
                if 12 <= len(cleaned) <= 140:
                    task_id = hashlib.md5(f"{page_num}:{cleaned}".encode()).hexdigest()[:10]
                    if not any(t["id"] == task_id for t in extracted_tasks):
                        extracted_tasks.append({
                            "id": task_id,
                            "label": cleaned,
                            "page": page_num,
                            "xp_value": domain_cfg["xp_per_task"],
                            "completed": False
                        })

    doc.close()

    # Always include a baseline reading/review milestone if no explicit bullets are found
    if not extracted_tasks:
        extracted_tasks.append({
            "id": "complete_doc",
            "label": f"Complete review & mastery of {pdf_path.stem}",
            "page": page_count,
            "xp_value": page_count * domain_cfg["xp_per_page"],
            "completed": False
        })

    base_xp = (page_count * domain_cfg["xp_per_page"]) + sum(t["xp_value"] for t in extracted_tasks)

    return {
        "file_name": pdf_path.name,
        "title": pdf_path.stem.replace("_", " ").replace("-", " ").title(),
        "file_hash": compute_file_hash(pdf_path),
        "pages": page_count,
        "pages_read": 0,
        "word_count": total_words,
        "total_xp_available": base_xp,
        "earned_xp": 0,
        "status": "UNSTARTED",  # UNSTARTED | IN_PROGRESS | MASTERED
        "milestones": extracted_tasks
    }


def calculate_tier(xp: int) -> dict:
    """Maps domain XP to a 1-5 visual evolution tier."""
    thresholds = [0, 500, 1500, 3500, 7000]
    tier = 1
    for i, req in enumerate(thresholds):
        if xp >= req:
            tier = i + 1
    next_threshold = thresholds[tier] if tier < len(thresholds) else thresholds[-1]
    return {
        "level": tier,
        "current_xp": xp,
        "next_level_xp": next_threshold
    }


def load_existing_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def sync_state():
    existing_state = load_existing_state()
    existing_domains = existing_state.get("domains", {})

    new_state = {
        "app": "Self",
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "avatar_composite": {
            "overall_level": 1,
            "total_xp": 0,
            "visual_layers": {}
        },
        "domains": {}
    }

    global_xp = 0

    for domain_key, cfg in DOMAINS.items():
        folder_path = SRC_DIR / domain_key
        folder_path.mkdir(parents=True, exist_ok=True)

        prev_docs = {
            d["file_hash"]: d
            for d in existing_domains.get(domain_key, {}).get("documents", [])
        }

        documents = []
        domain_earned_xp = 0
        domain_total_xp = 0

        for pdf_file in sorted(folder_path.glob("*.pdf")):
            file_hash = compute_file_hash(pdf_file)

            # Preserve user checkmarks and reading progress if file hasn't changed
            if file_hash in prev_docs:
                doc_data = prev_docs[file_hash]
            else:
                print(f"[+] Ingesting {domain_key}/{pdf_file.name}...")
                doc_data = extract_pdf_milestones(pdf_file, cfg)

            # Recompute earned XP for the document
            task_xp = sum(m["xp_value"] for m in doc_data["milestones"] if m["completed"])
            page_xp = doc_data.get("pages_read", 0) * cfg["xp_per_page"]
            doc_data["earned_xp"] = task_xp + page_xp

            if doc_data["earned_xp"] >= doc_data["total_xp_available"] and doc_data["total_xp_available"] > 0:
                doc_data["status"] = "MASTERED"
            elif doc_data["earned_xp"] > 0:
                doc_data["status"] = "IN_PROGRESS"

            domain_earned_xp += doc_data["earned_xp"]
            domain_total_xp += doc_data["total_xp_available"]
            documents.append(doc_data)

        tier_info = calculate_tier(domain_earned_xp)
        global_xp += domain_earned_xp

        new_state["domains"][domain_key] = {
            "avatar_attribute": cfg["attribute"],
            "tier": tier_info["level"],
            "earned_xp": domain_earned_xp,
            "next_tier_xp": tier_info["next_level_xp"],
            "max_available_xp": domain_total_xp,
            "document_count": len(documents),
            "documents": documents
        }

        new_state["avatar_composite"]["visual_layers"][cfg["attribute"]] = f"tier_{tier_info['level']}"

    new_state["avatar_composite"]["total_xp"] = global_xp
    new_state["avatar_composite"]["overall_level"] = max(1, (global_xp // 2000) + 1)

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2)

    print(f"[✓] State matrix synced -> {STATE_FILE}")


if __name__ == "__main__":
    sync_state()