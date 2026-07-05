import os
import sys
import json
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rebalance.ingest.pulse import collect_pulse_snapshot
from rebalance.ingest.config import get_pulse_config, get_github_token, get_gemini_api_key
from rebalance.ingest.querier import _synthesize_gemini

def test_pulse_signal():
    default_db = Path(os.environ.get("HOME")) / "Library/Application Support/rebalance-os/rebalance.db"
    db_path = Path(os.environ.get("REBALANCE_DB", default_db))
    config = get_pulse_config()
    
    print("Collecting pulse snapshot...")
    snapshot = collect_pulse_snapshot(
        database_path=db_path,
        github_login=config["github_login"],
        slack_user_id=config.get("slack_user_id"),
        timezone_name=config.get("pulse_timezone", "UTC"),
        github_token=get_github_token(),
    )
    
    today = asdict(snapshot.today)
    
    print("--- PULSE SNAPSHOT DATA ---")
    print(f"Commits today: {len(today['gh_commits'])}")
    print(f"Items (issues/PRs) today: {len(today['gh_items'])}")
    print(f"Comments today: {len(today['gh_comments'])}")
    print(f"Sleuth activity today: {len(today['sleuth_activity'])}")
    
    prompt = f"""
You are an AI assistant summarizing the daily activity of a software engineer.
Based on the following structured data snapshot of today's activity, write a concise daily summary for the user.
Keep it casual but informative. Group by project or theme if possible. Do NOT hallucinate data.

Activity data:
{json.dumps(today, indent=2, default=str)}
"""

    print("\n--- CALLING GEMINI ---")
    try:
        response = _synthesize_gemini(prompt, api_key=get_gemini_api_key(), thinking_budget=0, max_tokens=2048)
        print("\nResponse:")
        print(response)
        
        # Test exact block markers logic
        vault_mock = Path("scratch/mock_today.md")
        vault_mock.parent.mkdir(exist_ok=True)
        if not vault_mock.exists():
            vault_mock.write_text("# 0. Today's Notes\n\nSome manual notes here.\n")
            
        marker_start = "<!-- AI Daily Summary Start -->"
        marker_end = "<!-- AI Daily Summary End -->"
        
        content = vault_mock.read_text()
        block = f"{marker_start}\n## AI Daily Summary\n\n{response}\n{marker_end}\n"
        
        if marker_start in content and marker_end in content:
            # Replace
            before = content.split(marker_start)[0]
            after = content.split(marker_end)[1]
            new_content = before + block + after
            print("\nAction: Replaced existing block.")
        else:
            # Append at bottom
            if not content.endswith("\n"):
                content += "\n"
            new_content = content + "\n" + block
            print("\nAction: Appended new block at bottom.")
            
        vault_mock.write_text(new_content)
        print("Updated mock_today.md")
        
        # Run again to test idempotency
        content2 = vault_mock.read_text()
        block2 = f"{marker_start}\n## AI Daily Summary\n\n(Idempotent update test)\n{marker_end}\n"
        before2 = content2.split(marker_start)[0]
        after2 = content2.split(marker_end)[1]
        vault_mock.write_text(before2 + block2 + after2)
        print("Idempotency update successful.")
        
    except Exception as e:
        print(f"\nGemini synthesis failed: {e}")

if __name__ == "__main__":
    test_pulse_signal()
