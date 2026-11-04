# Self/src/engine/psychometrics.py
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from config import STATE_MATRIX_FILE, JOURNAL_LEDGER_FILE
from task_manager import load_tasks
from verification_engine import get_cognitive_retention_summary

def compute_psychometrics() -> dict:
    """Computes high-achiever psychometric markers, Grit score, and domain balance."""
    tasks_data = load_tasks()
    tasks = tasks_data.get("tasks", [])
    
    total_tasks = len(tasks)
    completed_tasks = [t for t in tasks if t.get("status") == "COMPLETED"]
    abandoned_tasks = [t for t in tasks if t.get("status") == "ABANDONED"]
    pending_tasks = [t for t in tasks if t.get("status") in ("PENDING", "IN_PROGRESS")]
    
    conquered_count = len(completed_tasks)
    abandoned_count = len(abandoned_tasks)
    
    # 1. Grit Calculation
    # Distinguish strategic pivots from friction abandonments
    friction_abandonments = 0
    strategic_pivots = 0
    for t in abandoned_tasks:
        reason = (t.get("abandon_reason") or "").lower()
        if any(w in reason for w in ["pivot", "obsolete", "re-prioritized", "rescheduled", "superseded"]):
            strategic_pivots += 1
        else:
            friction_abandonments += 1
            
    completion_rate = (conquered_count / total_tasks * 100.0) if total_tasks > 0 else 70.0
    
    # Grit formula: Baseline 60 + Completion momentum - Friction penalty + Perseverance weight
    grit_score = 60.0 + (conquered_count * 4.0) + (completion_rate * 0.25) - (friction_abandonments * 7.5) - (strategic_pivots * 1.5)
    grit_score = round(max(15.0, min(100.0, grit_score)), 1)
    
    # 2. Cognitive Retention Index
    retention_summary = get_cognitive_retention_summary()
    cognitive_retention = retention_summary.get("average_retention_pct", 85.0)
    
    # 3. Execution Velocity (Action-to-Theory Ratio)
    # Tasks completed vs passive document pages
    state = {}
    if STATE_MATRIX_FILE.exists():
        try:
            with open(STATE_MATRIX_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
            
    domains = state.get("domains", {})
    total_xp = state.get("avatar_composite", {}).get("total_xp", 0)
    overall_level = state.get("avatar_composite", {}).get("overall_level", 1)
    
    # 4. Domain Balance Radar & Entropy
    domain_scores = {}
    total_domain_xp = 0
    for dom_key in ["Self.knowledge", "Self.temple", "Self.career", "Self.credit", "Self.legal"]:
        dom_xp = domains.get(dom_key, {}).get("earned_xp", 0)
        tier = domains.get(dom_key, {}).get("tier", 1)
        domain_scores[dom_key] = {
            "earned_xp": dom_xp,
            "tier": tier,
            "next_tier_xp": domains.get(dom_key, {}).get("next_tier_xp", 500)
        }
        total_domain_xp += dom_xp
        
    # Execution Velocity: Kinetic action tasks completed per unit time
    kinetic_tasks = len([t for t in completed_tasks if t.get("domain") in ("Self.temple", "Self.career")])
    cognitive_tasks = len([t for t in completed_tasks if t.get("domain") in ("Self.knowledge", "Self.credit")])
    
    exec_velocity = round((conquered_count / max(1, total_tasks)) * 10.0, 1)
    
    return {
        "grit_score": grit_score,
        "cognitive_retention_pct": cognitive_retention,
        "execution_velocity": exec_velocity,
        "completion_rate_pct": round(completion_rate, 1),
        "total_missions_conquered": conquered_count,
        "total_missions_abandoned": abandoned_count,
        "strategic_pivots": strategic_pivots,
        "friction_abandonments": friction_abandonments,
        "overall_level": overall_level,
        "total_xp": total_xp,
        "domains": domain_scores,
        "retention_summary": retention_summary
    }

if __name__ == "__main__":
    metrics = compute_psychometrics()
    print("\n--- SELF. PSYCHOMETRIC EVALUATION ---")
    print(f"Grit Score: {metrics['grit_score']}/100")
    print(f"Cognitive Retention: {metrics['cognitive_retention_pct']}%")
    print(f"Execution Velocity: {metrics['execution_velocity']}/10")
    print(f"Missions Conquered: {metrics['total_missions_conquered']}")
