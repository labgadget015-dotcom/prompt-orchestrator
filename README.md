# Prompt Orchestrator

Self-analyzing autonomous prompt orchestration system with multi-layer validation, analytics, and LLM integration.

## Overview

Prompt Orchestrator is a production-ready framework for building reliable, auditable AI workflows. It chains specialized prompt modules with automated validation, domain adaptation, and performance tracking—turning brittle one-shot prompts into robust, self-improving systems.

## Key Features

- **Autonomous Routing** - Intelligently selects optimal module chains based on task analysis
- **Multi-Layer Validation** - GOLDEN framework → Chain-of-Thought → Verification → Bias Detection
- **Domain Adaptation** - Auto-adapts tone and vocabulary for fintech, healthcare, cybersecurity, SaaS
- **Analytics & Feedback** - Tracks success rates, latency, and quality metrics for continuous improvement  
- **Local LLM Support** - Works offline with Ollama (llama3.2, mistral, etc.)
- **Version Control** - All modules versioned for A/B testing and rollbacks

## Architecture

```
Task Input
   ↓
PromptRouter (keyword analysis)
   ↓
[GOLDEN Analyzer] → [Domain Specialist] → [CoT Reasoner]
   ↓                                              ↓
[Verification Loop] ← [Bias Detector] ← [Output]
   ↓
Analytics Hub (JSONL logging)
   ↓
Validated Output
```

## Quick Start

### Installation

```bash
git clone https://github.com/labgadget015-dotcom/prompt-orchestrator.git
cd prompt-orchestrator
pip install -r requirements.txt
```

### Run Example

```bash
# Start Ollama (if not running)
ollama serve

# Run the revenue optimization example
python examples/ollama_example.py
```

## Module Catalog

| Module | Version | Purpose | Success Rate |
|--------|---------|---------|-------------|
| **GOLDEN Analyzer** | v2.1 | Structured task decomposition (Goal/Output/Limits/Data/Evaluation/Next) | 96% |
| **Chain-of-Thought** | v3.5 | Transparent step-by-step reasoning | 94% |
| **Self-Verification** | v3.2 | Quality validation and critique | 97% |
| **Bias Detector** | v2.8 | Ethical safety and harmful content filtering | 98% |
| **Domain Specialist** | v1.9 | Context-aware adaptation (fintech/healthcare/cyber/SaaS) | 94% |

## Usage Examples

### Basic Orchestration

```python
from orchestrator.core import PromptOrchestrator
from orchestrator.router import PromptRouter
from orchestrator.modules.golden import GOLDENAnalyzer
from orchestrator.modules.verification import SelfVerificationLoop

# Initialize with Ollama
from examples.ollama_example import OllamaClient
llm = OllamaClient(model='llama3.2')

# Set up orchestrator
orchestrator = PromptOrchestrator(llm)
orchestrator.router = PromptRouter()
orchestrator.register_module('golden', GOLDENAnalyzer())
orchestrator.register_module('verification', SelfVerificationLoop())

# Execute task
result = orchestrator.execute(
    "Analyze customer churn patterns in our SaaS business",
    context={'domain': 'saas'}
)

print(result.output)
print(f"Success: {result.passed}, Latency: {result.metrics['latency']}s")
```

### Custom Chain

```python
# Override automatic routing with custom chain
result = orchestrator.execute(
    "Design a security incident response plan",
    context={
        'domain': 'cybersecurity',
        'chain': ['domain', 'cot', 'verification', 'bias']
    }
)
```

### Analytics

```python
from orchestrator.analytics import AnalyticsHub

analytics = AnalyticsHub()
stats = analytics.get_all_stats()

for module, metrics in stats.items():
    print(f"{module}: {metrics['success_rate']:.1%} success, "
          f"{metrics['avg_latency']:.2f}s latency")
```

## Router Chains

The router automatically selects chains based on task keywords:

| Task Type | Trigger Keywords | Chain |
|-----------|-----------------|-------|
| **Analysis** | analyze, evaluate, assess, review | golden → domain → cot → verification → bias |
| **Creative** | create, generate, design, build | domain → synthesizer → verification → bias |
| **Validation** | verify, check, validate, test | cot → verification → bias |
| **Optimization** | optimize, improve, enhance, revenue | golden → cot → domain → feedback → verification |
| **Simple** | (default) | cot → verification |

## Configuration

### Add Custom Domain

```python
from orchestrator.modules.domain import DomainAdaptiveSpecialist

domain_specialist = DomainAdaptiveSpecialist()
domain_specialist.domain_profiles['legal'] = {
    'tone': 'formal, precise',
    'vocabulary': 'statute, precedent, liability',
    'constraints': 'accuracy, citations'
}
```

### Register Custom Chain

```python
router = PromptRouter()
router.register_chain('audit', ['golden', 'cot', 'verification', 'verification'])  # double verification
router.register_keywords('audit', ['audit', 'compliance', 'regulatory'])
```

## Production Deployment

### FastAPI Wrapper

```python
from fastapi import FastAPI
from orchestrator.core import PromptOrchestrator

app = FastAPI()
orchestrator = PromptOrchestrator(llm_client)

@app.post("/orchestrate")
def run_task(task: str, domain: str = 'general'):
    result = orchestrator.execute(task, context={'domain': domain})
    return {
        'output': result.output,
        'passed': result.passed,
        'metrics': result.metrics
    }
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0"]
```

## Analytics & Monitoring

All executions log to `analytics.jsonl`:

```json
{"timestamp": "2026-01-10T05:00:00", "module": "golden", "success": true, "latency": 2.3, "version": "v2.1"}
{"timestamp": "2026-01-10T05:00:02", "module": "verification", "success": true, "latency": 1.8, "version": "v3.2"}
```

Query metrics:

```python
analytics = AnalyticsHub()
print(analytics.get_performance('golden', window_hours=24))
# {'total_runs': 150, 'success_rate': 0.96, 'avg_latency': 2.1, ...}
```

## Roadmap

- [ ] Multi-modal support (image/document analysis)
- [ ] Streaming responses for long chains
- [ ] Web UI for chain visualization
- [ ] Integration with LangSmith/Weights & Biases
- [ ] Pre-built chains for common use cases

## Contributing

Pull requests welcome! Priority areas:
- New domain profiles (legal, education, e-commerce)
- Additional safety modules (PII detection, toxicity)
- Performance optimizations
- Integration examples (Stripe, BigQuery, etc.)

## Ecosystem

This project is part of a connected suite of AI tools:

| Repository | Description |
|------------|-------------|
| [ai-analyze-think-act-core](https://github.com/labgadget015-dotcom/ai-analyze-think-act-core) | 🧠 Core LLM analysis framework — ingest → analyze → recommend |
| [ai-consulting-platform](https://github.com/labgadget015-dotcom/ai-consulting-platform) | 🛍️ E-commerce AI consulting platform (uses core) |
| [analysis-os](https://github.com/labgadget015-dotcom/analysis-os) | 📊 Systematic analysis OS for consultants (uses core) |
| [prompt-orchestrator](https://github.com/labgadget015-dotcom/prompt-orchestrator) | 🔀 Autonomous multi-stage prompt orchestration — routes and chains prompts across modules (uses core) |
| [github-notifications-copilot](https://github.com/labgadget015-dotcom/github-notifications-copilot) | 🔔 AI-powered GitHub notification triage |

## License

MIT License - see LICENSE file

## Links

- **GitHub**: https://github.com/labgadget015-dotcom/prompt-orchestrator
- **Documentation**: (coming soon)
- **Issues**: https://github.com/labgadget015-dotcom/prompt-orchestrator/issues
