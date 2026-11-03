# Self/src/engine/acceptance_test_generator.py
import json
from pathlib import Path
from datetime import datetime, timezone

SRC_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = SRC_DIR / "engine" / "state_matrix.json"
OUTPUT_REPORT = SRC_DIR / "engine" / "client_acceptance_test_report.html"

def generate_acceptance_test():
    if not STATE_FILE.exists():
        print(f"[!] State matrix not found at {STATE_FILE}. Run pdf_ingestor.py first.")
        return

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    composite = state.get("avatar_composite", {})
    domains = state.get("domains", {})

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SELF // Client Documentation Acceptance Test</title>
    <style>
        body {{
            background-color: #050508;
            color: #e2e8f0;
            font-family: 'Courier New', Courier, monospace;
            padding: 40px;
            max-width: 900px;
            margin: auto;
        }}
        h1, h2, h3 {{ color: #00f0ff; border-bottom: 1px solid rgba(0, 240, 255, 0.2); padding-bottom: 8px; }}
        .meta-box {{
            background: rgba(10, 10, 16, 0.85);
            border: 1px solid rgba(0, 240, 255, 0.3);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
        }}
        .domain-card {{
            background: rgba(15, 15, 25, 0.7);
            border: 1px solid rgba(99, 102, 241, 0.3);
            padding: 16px;
            margin-bottom: 20px;
            border-radius: 6px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 10px;
            text-align: left;
            font-size: 13px;
        }}
        th {{ background: rgba(0, 240, 255, 0.1); color: #00f0ff; }}
        .checkbox-cell {{ text-align: center; width: 40px; }}
        input[type="checkbox"] {{ transform: scale(1.3); accent-color: #00f0ff; cursor: pointer; }}
        .signoff-section {{
            margin-top: 40px;
            padding: 20px;
            border: 1px dashed #eab308;
            border-radius: 8px;
            background: rgba(234, 179, 8, 0.05);
        }}
        .btn {{
            background: #00f0ff;
            color: #050508;
            border: none;
            padding: 12px 24px;
            font-weight: bold;
            font-family: monospace;
            cursor: pointer;
            border-radius: 4px;
            margin-top: 15px;
        }}
    </style>
</head>
<body>

    <h1>SELF // DOCUMENTATION ACCEPTANCE TEST (DAT)</h1>
    <p>Pre-Evolution Verification Suite for Client Review prior to avatar state mutation.</p>

    <div class="meta-box">
        <strong>Generated Timestamp:</strong> {datetime.now(timezone.utc).isoformat()}<br>
        <strong>Overall System Level:</strong> LEVEL {composite.get('overall_level', 1)} ({composite.get('total_xp', 0)} XP)<br>
        <strong>Active Visual Layers:</strong> <code>{json.dumps(composite.get('visual_layers', {{}}), indent=2)}</code>
    </div>
"""

    for domain_key, domain_data in domains.items():
        html_content += f"""
        <div class="domain-card">
            <h2>{domain_key.upper()}</h2>
            <p><strong>Avatar Attribute Bound:</strong> {domain_data.get('avatar_attribute')} | <strong>Current Tier:</strong> TIER {domain_data.get('tier')} ({domain_data.get('earned_xp')} / {domain_data.get('next_tier_xp')} XP)</p>
            <table>
                <tr>
                    <th class="checkbox-cell">PASS</th>
                    <th>Source Document</th>
                    <th>Milestone / Objective Specification</th>
                    <th>XP Value</th>
                </tr>
"""
        for doc in domain_data.get("documents", []):
            for m in doc.get("milestones", []):
                checked_attr = "checked" if m.get("completed") else ""
                html_content += f"""
                <tr>
                    <td class="checkbox-cell"><input type="checkbox" {checked_attr} disabled></td>
                    <td><code>{doc.get('file_name')}</code></td>
                    <td>{m.get('label')}</td>
                    <td>+{m.get('xp_value')} XP</td>
                </tr>
                """
        html_content += """
            </table>
        </div>
        """

    html_content += """
    <div class="signoff-section">
        <h3>CLIENT SIGN-OFF & APPROVAL</h3>
        <p>By signing below, the client verifies that the documentation standards above are fully understood, and authorizes the system to proceed with writing avatar evolution parameters.</p>
        <br>
        <label>Client Signature / Approver ID: <input type="text" style="background:#111; border:1px solid #555; color:#fff; padding:6px; width:300px;" placeholder="Enter Name or Key"></label>
        <br><br>
        <button class="btn" onclick="alert('Acceptance Test Signed Successfully. Ready for Avatar Evolution.')">AUTHORIZE EVOLUTION</button>
    </div>

</body>
</html>
"""

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[✓] Documentation Acceptance Test generated successfully -> {OUTPUT_REPORT}")

if __name__ == "__main__":
    generate_acceptance_test()