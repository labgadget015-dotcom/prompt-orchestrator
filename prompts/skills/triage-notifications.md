# Skill: Triage GitHub Notifications

## Description
Automatically triage GitHub notifications by priority and take smart actions to keep your inbox manageable.

## Trigger phrases
- "Triage my notifications"
- "Clean up my GitHub inbox"
- "What GitHub notifications need my attention?"
- "Run notification triage"

## Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | int | No | Max notifications to process. Default: 50 |
| `dry_run` | bool | No | Preview actions without executing. Default: false |
| `priority_filter` | string | No | Only show `P1`, `P2`, or `P3`. Default: all |

## Implementation
```python
from notification_copilot import NotificationCopilot

copilot = NotificationCopilot(token=GITHUB_TOKEN, api_key=ANTHROPIC_API_KEY)
results = copilot.triage(limit=limit, dry_run=dry_run)
```

## Output
```
📬 Triage Summary (47 notifications)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 P1 (3)  → Review now
🟡 P2 (12) → Review today  
⚪ P3 (32) → Muted/archived

Actions taken: 32 archived, 5 muted, 10 labeled
```

## Scheduled use
Runs automatically every hour via `.github/workflows/triage.yml`.
Manual trigger available in GitHub Actions with dry_run option.
