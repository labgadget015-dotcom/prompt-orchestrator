# Skill: Forecast Sales

## Description
Generate sales forecasts using Prophet time-series modeling integrated with the ai-consulting-platform.

## Trigger phrases
- "Forecast sales for next [period]"
- "What are my projected revenues?"
- "Run a sales forecast"
- "Predict demand for [product/category]"

## Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | DataFrame / CSV | Yes | Historical sales data with `date` and `value` columns |
| `periods` | int | No | Forecast horizon in days. Default: 30 |
| `seasonality` | string | No | `daily`, `weekly`, `yearly`, or `auto`. Default: auto |
| `confidence` | float | No | Confidence interval width (0.8 = 80%). Default: 0.95 |

## Implementation
Uses Prophet via `ai-consulting-platform`:
```python
from app.core.forecasting import run_forecast

result = run_forecast(data=df, periods=periods, seasonality=seasonality)
# result.forecast_df, result.trend, result.components, result.mape
```

## Output
Returns:
- Forecast DataFrame with `yhat`, `yhat_lower`, `yhat_upper` columns
- Trend direction and key changepoints
- MAPE (accuracy metric) — flag if > 20%
- Seasonal components breakdown

## Caveats
- Requires at least 2 full seasonal cycles of data for reliable results
- Sudden structural breaks (COVID, policy changes) may need manual changepoints
- Forecast accuracy degrades beyond 2× the training window
