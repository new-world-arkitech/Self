# Self/src/engine/verification_engine.py
import os
import sys
import json
import math
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import (
    STATE_MATRIX_FILE,
    JOURNAL_LEDGER_FILE,
    QUIZ_PASS_THRESHOLD,
    DOMAINS
)
from task_manager import sync_to_state_matrix, log_to_journal

VERIFICATION_DATA_FILE = Path(__file__).resolve().parent / "verification_cards.json"

# ==============================================================================
# 1. COGNITIVE VERIFICATION STATE MACHINE
# ==============================================================================
class VerificationState:
    UNTESTED = "UNTESTED"
    ACTIVE_STUDY = "ACTIVE_STUDY"
    VERIFIED_PASS = "VERIFIED_PASS"
    DUE_FOR_REVIEW = "DUE_FOR_REVIEW"
    RELAPSED = "RELAPSED"
    MASTERED = "MASTERED"

# ==============================================================================
# 2. SM-2 / FSRS RETENTION ALGORITHMS
# ==============================================================================
def update_sm2(repetitions: int, ease_factor: float, interval_days: int, grade: int) -> tuple[int, float, int]:
    """
    SuperMemo-2 (SM-2) Spaced Repetition Algorithm.
    grade: 0 to 5 (0 = blackout, 3 = pass with difficulty, 5 = perfect recall)
    Returns: (new_repetitions, new_ease_factor, new_interval_days)
    """
    # Ease factor formula
    new_ef = ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    new_ef = max(1.3, round(new_ef, 3))

    if grade >= 3:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = math.ceil(interval_days * new_ef)
        new_reps = repetitions + 1
    else:
        # Relapse: reset repetitions and interval to 1 day
        new_reps = 0
        new_interval = 1

    return new_reps, new_ef, new_interval

def calculate_retention_probability(last_review_iso: str, interval_days: int) -> float:
    """Computes retention R(t) = exp(-delta_t / Stability) where Stability ~ interval_days."""
    if not last_review_iso or interval_days <= 0:
        return 0.0

    last_dt = datetime.fromisoformat(last_review_iso)
    elapsed_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400.0

    # Exponential forgetting curve
    stability = max(1.0, float(interval_days))
    retention = math.exp(-elapsed_days / stability)
    return round(max(0.0, min(1.0, retention)), 3)

# ==============================================================================
# 3. VERIFICATION CARDS & QUIZ REGISTRY
# ==============================================================================
# Pre-seeded core cognitive challenges extracted from ingested documentation
BUILTIN_CHALLENGES = [
    {
        "id": "quiz_botanical_01",
        "domain": "Self.knowledge",
        "source_doc": "BOTANICAL_SURVIVAL_AND_MEDICINE_GUIDE.md",
        "title": "Universal Plant Toxicity Identification",
        "question": "Which physical characteristic is a universal red flag that indicates a wild plant should NOT be consumed?",
        "options": [
            "Milky or cloudy latex sap (natural alkaloids/latex)",
            "Deep green serrated leaf edges",
            "Fibrous shallow root system",
            "Flowering in early spring"
        ],
        "correct_index": 0,
        "explanation": "Milky or cloudy sap almost universally indicates toxic alkaloids (e.g. spurges, dogbanes). Umbrella-shaped flowers and almond scents are other lethal indicators.",
        "xp_value": 45,
        "state": VerificationState.UNTESTED,
        "repetitions": 0,
        "ease_factor": 2.5,
        "interval_days": 1,
        "next_due": None,
        "last_reviewed": None
    },
    {
        "id": "quiz_botanical_02",
        "domain": "Self.knowledge",
        "source_doc": "BOTANICAL_SURVIVAL_AND_MEDICINE_GUIDE.md",
        "title": "Soil Composting Ratios",
        "question": "What is the scientifically recommended carbon-to-nitrogen volumetric ratio for thermal composting?",
        "options": [
            "1 part Browns (dry leaves) to 1 part Greens (nitrogen)",
            "3 parts Browns (carbon) to 1 part Greens (nitrogen)",
            "5 parts Greens to 1 part Browns",
            "100% kitchen food scraps with no carbon"
        ],
        "correct_index": 1,
        "explanation": "3 parts Browns to 1 part Greens creates the optimal 30:1 C:N ratio for rapid aerobic microbial decomposition without putrefaction.",
        "xp_value": 40,
        "state": VerificationState.UNTESTED,
        "repetitions": 0,
        "ease_factor": 2.5,
        "interval_days": 1,
        "next_due": None,
        "last_reviewed": None
    },
    {
        "id": "quiz_temple_01",
        "domain": "Self.temple",
        "source_doc": "90_day_evolution_plan.md",
        "title": "Pillar 2: Morning Ritual Anchors",
        "question": "According to the 90-Day Self-Evolution Plan, what are the first non-negotiable actions upon waking?",
        "options": [
            "Immediately hydrate with 500ml water and avoid social media / email",
            "Check client emails and social media in bed",
            "Eat a heavy breakfast within 10 minutes",
            "Open trading terminal immediately"
        ],
        "correct_index": 0,
        "explanation": "Hydrating with 500ml water and keeping phone/social inputs offline preserves dopamine baseline and mental clarity for the 90-minute Deep Work block.",
        "xp_value": 50,
        "state": VerificationState.UNTESTED,
        "repetitions": 0,
        "ease_factor": 2.5,
        "interval_days": 1,
        "next_due": None,
        "last_reviewed": None
    },
    {
        "id": "quiz_temple_02",
        "domain": "Self.temple",
        "source_doc": "90_day_evolution_plan.md",
        "title": "Pillar 2: Evening Digital Sunset",
        "question": "What is the scheduled cutoff time for digital screens to optimize melatonin release?",
        "options": [
            "9:30 PM (Digital Sunset with warm lighting)",
            "11:45 PM right before sleep",
            "No screen curfew is necessary",
            "8:00 AM"
        ],
        "correct_index": 0,
        "explanation": "Digital Sunset at 9:30 PM allows natural melatonin cascade, preparation of the top 3 next-day objectives, and a 10:00 PM sleep target.",
        "xp_value": 40,
        "state": VerificationState.UNTESTED,
        "repetitions": 0,
        "ease_factor": 2.5,
        "interval_days": 1,
        "next_due": None,
        "last_reviewed": None
    },
    {
        "id": "quiz_survival_01",
        "domain": "Self.knowledge",
        "source_doc": "PRACTICAL_SURVIVAL_SCIENCE_AND_PHYSICAL_MASTERY_GUIDE.md",
        "title": "Thermal Layering Physics",
        "question": "Why is cotton strictly avoided in cold/wet survival environments (The 'Cotton Kills' principle)?",
        "options": [
            "Cotton fibers hold 27x their weight in water and lose 100% of insulating value when wet",
            "Cotton is too heavy to carry in a rucksack",
            "Cotton catches fire from ambient static electricity",
            "Cotton restricts shoulder mobility in shelter building"
        ],
        "correct_index": 0,
        "explanation": "Cotton absorbs moisture readily and conducts body heat away up to 25x faster when damp, inducing rapid hypothermia. Wool and synthetic polyesters preserve loft.",
        "xp_value": 50,
        "state": VerificationState.UNTESTED,
        "repetitions": 0,
        "ease_factor": 2.5,
        "interval_days": 1,
        "next_due": None,
        "last_reviewed": None
    }
]

def load_verification_cards() -> list[dict]:
    if not VERIFICATION_DATA_FILE.exists():
        save_verification_cards(BUILTIN_CHALLENGES)
        return BUILTIN_CHALLENGES

    try:
        with open(VERIFICATION_DATA_FILE, "r", encoding="utf-8") as f:
            cards = json.load(f)
            # Update state based on current time (check DUE_FOR_REVIEW)
            now = datetime.now(timezone.utc)
            for c in cards:
                if c.get("next_due") and c.get("state") == VerificationState.VERIFIED_PASS:
                    due_dt = datetime.fromisoformat(c["next_due"])
                    if now >= due_dt:
                        c["state"] = VerificationState.DUE_FOR_REVIEW
            return cards
    except Exception:
        return BUILTIN_CHALLENGES

def save_verification_cards(cards: list[dict]):
    VERIFICATION_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(VERIFICATION_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2)

def get_due_quizzes(domain: str = None) -> list[dict]:
    cards = load_verification_cards()
    due = []
    for c in cards:
        if domain and c["domain"].lower() != domain.lower():
            continue
        if c["state"] in (VerificationState.UNTESTED, VerificationState.DUE_FOR_REVIEW, VerificationState.RELAPSED):
            due.append(c)
    return due

def submit_quiz_answer(quiz_id: str, selected_option_index: int) -> dict:
    """
    Submits an answer, executes the SM-2 spaced repetition state transition,
    awards XP upon passing, and returns evaluation diagnostics.
    """
    cards = load_verification_cards()
    target_card = None

    for c in cards:
        if c["id"] == quiz_id:
            target_card = c
            break

    if not target_card:
        return {"error": f"Quiz {quiz_id} not found"}

    is_correct = (selected_option_index == target_card["correct_index"])
    grade = 5 if is_correct else 1  # 5 = perfect recall, 1 = failure

    new_reps, new_ef, new_interval = update_sm2(
        repetitions=target_card.get("repetitions", 0),
        ease_factor=target_card.get("ease_factor", 2.5),
        interval_days=target_card.get("interval_days", 1),
        grade=grade
    )

    now = datetime.now(timezone.utc)
    next_due_dt = now + timedelta(days=new_interval)

    target_card["repetitions"] = new_reps
    target_card["ease_factor"] = new_ef
    target_card["interval_days"] = new_interval
    target_card["last_reviewed"] = now.isoformat()
    target_card["next_due"] = next_due_dt.isoformat()

    # State Machine Transition
    xp_awarded = 0
    if is_correct:
        if target_card["repetitions"] >= 4 and target_card["ease_factor"] >= 2.4:
            target_card["state"] = VerificationState.MASTERED
        else:
            target_card["state"] = VerificationState.VERIFIED_PASS

        xp_awarded = target_card["xp_value"]
        # Sync state matrix & log journal
        sync_to_state_matrix(target_card["domain"], xp_awarded)
        log_to_journal("CONQUERED", {
            "id": target_card["id"],
            "title": f"Cognitive Verification: {target_card['title']}",
            "domain": target_card["domain"],
            "xp_value": xp_awarded,
            "category": "VERIFICATION_QUIZ",
            "notes": f"Score 100% | SM-2 Interval: {new_interval}d | EF: {new_ef}"
        })
    else:
        target_card["state"] = VerificationState.RELAPSED

    save_verification_cards(cards)

    retention_prob = calculate_retention_probability(now.isoformat(), new_interval)

    return {
        "success": True,
        "is_correct": is_correct,
        "correct_index": target_card["correct_index"],
        "explanation": target_card["explanation"],
        "new_state": target_card["state"],
        "next_due_days": new_interval,
        "ease_factor": new_ef,
        "retention_probability": retention_prob,
        "xp_awarded": xp_awarded
    }

def get_cognitive_retention_summary() -> dict:
    """Computes system-wide cognitive retention diagnostics."""
    cards = load_verification_cards()
    total = len(cards)
    if total == 0:
        return {"average_retention": 0.0, "total_verified": 0, "total_mastered": 0}

    total_retention = 0.0
    verified_count = 0
    mastered_count = 0

    for c in cards:
        r = calculate_retention_probability(c.get("last_reviewed"), c.get("interval_days", 1))
        total_retention += r
        if c["state"] in (VerificationState.VERIFIED_PASS, VerificationState.MASTERED):
            verified_count += 1
        if c["state"] == VerificationState.MASTERED:
            mastered_count += 1

    avg_retention = (total_retention / total) * 100.0

    return {
        "total_cards": total,
        "average_retention_pct": round(avg_retention, 1),
        "verified_count": verified_count,
        "mastered_count": mastered_count,
        "due_count": len([c for c in cards if c["state"] in (VerificationState.UNTESTED, VerificationState.DUE_FOR_REVIEW)])
    }

if __name__ == "__main__":
    due = get_due_quizzes()
    print(f"\n--- SELF. COGNITIVE VERIFICATION ENGINE ---")
    print(f"Cards Available: {len(due)} due for evaluation")
    summary = get_cognitive_retention_summary()
    print(f"System Retention Index: {summary['average_retention_pct']}% | Mastered: {summary['mastered_count']}")
