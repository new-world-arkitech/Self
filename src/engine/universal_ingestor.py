# Self/src/engine/universal_ingestor.py
import os
import sys
import re
import json
import hashlib
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
import fitz  # PyMuPDF

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    STATE_MATRIX_FILE,
    DOMAINS,
    SRC_DIR
)

# Semantic Action & Protocol Extraction Regexes
ACTION_VERBS = r"(?:identify|cultivate|execute|calculate|avoid|hydrate|prepare|complete|deploy|review|audit|practice|build|draft|verify|master|test)"
ACTION_PATTERNS = [
    re.compile(rf"^\s*(?:[-*•]|\d+\.|\bPhase\b|\bStep\b)\s+({ACTION_VERBS}\b.*)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*[-*•]\s+\*\*([^*]+)\*\*:\s*(.*)", re.MULTILINE),
    re.compile(r"^(?:Goal|Milestone|Target|Objective|Protocol|Action)\s*[:\-]\s*(.*)", re.IGNORECASE | re.MULTILINE),
    re.compile(r">\s*\[!(?:IMPORTANT|WARNING|CAUTION)\]\s*\n>\s*(.*)", re.MULTILINE)
]

def compute_file_hash(filepath: Path) -> str:
    """Generates a SHA-256 fingerprint to track modifications without losing progress."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]

def parse_docx_text(docx_path: Path) -> str:
    """Zero-dependency DOCX text extractor via XML parsing."""
    try:
        with zipfile.ZipFile(docx_path) as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for node in tree.iter():
                if node.tag.endswith("p"):
                    p_text = "".join(t.text for t in node.iter() if t.text)
                    if p_text.strip():
                        paragraphs.append(p_text.strip())
            return "\n\n".join(paragraphs)
    except Exception as e:
        print(f"[!] Warning reading DOCX {docx_path.name}: {e}")
        return ""

def parse_markdown_text(md_path: Path) -> str:
    """Reads Markdown text with UTF-8 encoding."""
    try:
        with open(md_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        print(f"[!] Warning reading Markdown {md_path.name}: {e}")
        return ""

def parse_pdf_text(pdf_path: Path) -> tuple[int, str]:
    """Reads PDF page count and text via PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        text = "\n\n".join(page.get_text("text") for page in doc)
        doc.close()
        return page_count, text
    except Exception as e:
        print(f"[!] Warning reading PDF {pdf_path.name}: {e}")
        return 0, ""

def extract_milestones_from_text(raw_text: str, default_xp: int) -> list[dict]:
    """Applies heuristic semantic extraction to generate verifiable action milestones."""
    tasks = []
    seen_ids = set()

    for pattern in ACTION_PATTERNS:
        matches = pattern.findall(raw_text)
        for match in matches:
            if isinstance(match, tuple):
                cleaned = f"{match[0]}: {match[1]}".strip()
            else:
                cleaned = match.strip()

            # Clean markdown formatting artifacts
            cleaned = re.sub(r"[*_`]", "", cleaned)

            if 15 <= len(cleaned) <= 160:
                task_id = hashlib.md5(cleaned.encode()).hexdigest()[:10]
                if task_id not in seen_ids:
                    seen_ids.add(task_id)

                    # Dynamic XP calculation based on action verb complexity
                    xp_value = default_xp
                    lower_clean = cleaned.lower()
                    if any(w in lower_clean for w in ["master", "build", "execute", "audit", "deploy"]):
                        xp_value = int(default_xp * 1.5)
                    elif any(w in lower_clean for w in ["review", "hydrate", "read"]):
                        xp_value = int(default_xp * 0.8)

                    tasks.append({
                        "id": task_id,
                        "label": cleaned,
                        "xp_value": xp_value,
                        "completed": False
                    })

    return tasks

def process_document(file_path: Path, domain_key: str, domain_cfg: dict) -> dict:
    """Universal extractor handling PDF, Markdown, Word DOCX, and TXT."""
    ext = file_path.suffix.lower()
    page_count = 1
    raw_text = ""

    if ext == ".pdf":
        page_count, raw_text = parse_pdf_text(file_path)
    elif ext in (".md", ".markdown"):
        raw_text = parse_markdown_text(file_path)
        # Approximate 400 words per page for markdown documents
        page_count = max(1, len(raw_text.split()) // 400)
    elif ext == ".docx":
        raw_text = parse_docx_text(file_path)
        page_count = max(1, len(raw_text.split()) // 400)
    elif ext == ".txt":
        raw_text = parse_markdown_text(file_path)
        page_count = max(1, len(raw_text.split()) // 400)

    word_count = len(raw_text.split())
    milestones = extract_milestones_from_text(raw_text, domain_cfg.get("xp_per_task", 40))

    if not milestones:
        milestones.append({
            "id": f"review_{hashlib.md5(file_path.stem.encode()).hexdigest()[:8]}",
            "label": f"Complete in-depth study and conceptual mastery of {file_path.stem}",
            "xp_value": max(25, page_count * domain_cfg.get("xp_per_page", 20)),
            "completed": False
        })

    base_xp = (page_count * domain_cfg.get("xp_per_page", 20)) + sum(m["xp_value"] for m in milestones)

    return {
        "file_name": file_path.name,
        "title": file_path.stem.replace("_", " ").replace("-", " ").title(),
        "file_hash": compute_file_hash(file_path),
        "file_type": ext.lstrip("."),
        "pages": page_count,
        "pages_read": 0,
        "word_count": word_count,
        "total_xp_available": base_xp,
        "earned_xp": 0,
        "status": "UNSTARTED",  # UNSTARTED | IN_PROGRESS | MASTERED
        "milestones": milestones
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
        "level": min(5, tier),
        "current_xp": xp,
        "next_level_xp": next_threshold
    }

def load_existing_state() -> dict:
    if STATE_MATRIX_FILE.exists():
        try:
            with open(STATE_MATRIX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def sync_universal_state():
    """Scans all domain folders for PDF, MD, DOCX, TXT and updates the state matrix."""
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

    SUPPORTED_EXTENSIONS = ("*.pdf", "*.md", "*.markdown", "*.docx", "*.txt")

    for domain_key, cfg in DOMAINS.items():
        folder_path = cfg["path"]
        folder_path.mkdir(parents=True, exist_ok=True)

        # Map previous documents by file_hash to preserve user progress
        prev_docs = {
            d["file_hash"]: d
            for d in existing_domains.get(domain_key, {}).get("documents", [])
            if "file_hash" in d
        }

        # Also map by filename as fallback
        prev_by_name = {
            d["file_name"]: d
            for d in existing_domains.get(domain_key, {}).get("documents", [])
            if "file_name" in d
        }

        discovered_files = []
        for ext_pattern in SUPPORTED_EXTENSIONS:
            discovered_files.extend(folder_path.glob(ext_pattern))

        discovered_files = sorted(set(discovered_files), key=lambda p: p.name)

        documents = []
        domain_earned_xp = 0
        domain_total_xp = 0

        for file_path in discovered_files:
            file_hash = compute_file_hash(file_path)

            if file_hash in prev_docs:
                doc_data = prev_docs[file_hash]
            elif file_path.name in prev_by_name:
                # File modified but name identical: re-extract but preserve existing completions
                doc_data = process_document(file_path, domain_key, cfg)
                prev_completed = {
                    m["label"]: m["completed"]
                    for m in prev_by_name[file_path.name].get("milestones", [])
                }
                for m in doc_data["milestones"]:
                    if m["label"] in prev_completed:
                        m["completed"] = prev_completed[m["label"]]
                doc_data["pages_read"] = prev_by_name[file_path.name].get("pages_read", 0)
            else:
                print(f"[SCAN] Ingesting [{domain_key}] {file_path.name}...")
                doc_data = process_document(file_path, domain_key, cfg)

            # Recompute earned XP
            task_xp = sum(m["xp_value"] for m in doc_data["milestones"] if m["completed"])
            page_xp = doc_data.get("pages_read", 0) * cfg.get("xp_per_page", 20)
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

    STATE_MATRIX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_MATRIX_FILE, "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2)

    print(f"[OK] State Matrix Synced: Level {new_state['avatar_composite']['overall_level']} ({global_xp} XP)")
    return new_state

if __name__ == "__main__":
    sync_universal_state()
