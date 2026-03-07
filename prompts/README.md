# Prompt Samples

This directory contains reusable agent instructions and skill definitions for the labgadget015-dotcom AI ecosystem.

## Agent Instructions
System prompts that define agent behavior and personality:

| Prompt | Description |
|--------|-------------|
| [triage-agent.md](agent-instructions/triage-agent.md) | GitHub notification triage assistant |
| [analysis-agent.md](agent-instructions/analysis-agent.md) | Data analysis and insights agent |
| [consulting-agent.md](agent-instructions/consulting-agent.md) | E-commerce consulting assistant |

## Skills
Callable capabilities with defined inputs, outputs, and trigger phrases:

| Skill | Description |
|-------|-------------|
| [analyze-data.md](skills/analyze-data.md) | Analyze datasets with LLM insights |
| [triage-notifications.md](skills/triage-notifications.md) | Triage GitHub notification inbox |
| [forecast-sales.md](skills/forecast-sales.md) | Prophet-based sales forecasting |

## Usage in GitHub Copilot Chat
**To use an agent instruction:**
Open Copilot Chat and say: "Act as the [agent name] — [your request]"

**To invoke a skill:**
Open Copilot Chat and say: "Use the analyze-data skill on [your data]"

## Contributing
- **New agent instruction**: Create `agent-instructions/my-agent.md`
- **New skill**: Create `skills/my-skill.md`

Follow the existing file format. Include: description, trigger phrases, parameters table, implementation example, and output format.
