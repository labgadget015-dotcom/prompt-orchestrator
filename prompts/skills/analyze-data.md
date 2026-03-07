# Skill: Analyze Data

## Description
Analyze a dataset using the `ai-analyze-think-act-core` pipeline and return structured insights with recommendations.

## Trigger phrases
- "Analyze this data"
- "What does this data tell me?"
- "Run analysis on [dataset]"
- "Give me insights from [file]"

## Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | DataFrame / CSV / JSON | Yes | The data to analyze |
| `analysis_type` | string | No | One of: `ecommerce`, `forecast`, `segmentation`, `anomaly`. Default: auto-detect |
| `focus` | string | No | Specific question to answer about the data |

## Implementation
```python
from orchestrator.core_bridge import CoreAnalysisBridge

bridge = CoreAnalysisBridge()
result = bridge.analyze(data=data, analysis_type=analysis_type)
# Returns: result.insights, result.actions, result.confidence
```

## Example
**Input**: "Analyze this week's sales data for anomalies"
**Output**: Structured JSON with anomalies flagged, severity scores, and recommended actions

## Fallback
If `ai-analyze-think-act-core` is unavailable, return descriptive statistics (mean, std, nulls, top values) with a note that LLM insights require the core pipeline.
