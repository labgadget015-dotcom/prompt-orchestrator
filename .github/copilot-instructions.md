# Copilot Instructions — prompt-orchestrator

## What this repo is
A prompt orchestration layer that manages, versions, and executes prompts across multiple LLM providers. Integrates with `ai-analyze-think-act-core` for data-aware prompting.

## Key modules
```
orchestrator/
  __init__.py
  core_bridge.py     # Bridge to ai-analyze-think-act-core
  # (add new orchestrator modules here)
prompts/             # Prompt sample library
  agent-instructions/
    triage-agent.md
    analysis-agent.md
    consulting-agent.md
  skills/
    analyze-data.md
    triage-notifications.md
    forecast-sales.md
tests/
  test_core_bridge.py
  test_orchestrator.py
```

## CoreAnalysisBridge
`orchestrator/core_bridge.py` — wraps `ai-analyze-think-act-core`:
```python
from orchestrator.core_bridge import CoreAnalysisBridge
bridge = CoreAnalysisBridge()
result = bridge.analyze(data=my_df, analysis_type="ecommerce")
# result.insights, result.actions, result.confidence
```

## Conventions
- All prompt templates live in `prompts/` as Markdown files
- Use `{{variable}}` for template variables in prompts
- Agent instructions go in `prompts/agent-instructions/`
- Skill definitions go in `prompts/skills/`
- Soft-import core: `try/except ImportError` with `_CORE_AVAILABLE` flag

## Adding a new prompt
1. Create `prompts/agent-instructions/my-agent.md` or `prompts/skills/my-skill.md`
2. Follow the template format (see existing files)
3. Reference it in `orchestrator/` code via `Path(__file__).parent.parent / "prompts" / ...`

## Testing
```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Ecosystem
- [ai-analyze-think-act-core](https://github.com/labgadget015-dotcom/ai-analyze-think-act-core) — core pipeline
- [ai-consulting-platform](https://github.com/labgadget015-dotcom/ai-consulting-platform) — platform using these prompts
- [github-notifications-copilot](https://github.com/labgadget015-dotcom/github-notifications-copilot) — uses triage-agent prompt
