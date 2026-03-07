#!/usr/bin/env python3
"""
Ecosystem demo — exercises all three agents with sample data.

Usage:
    python demo.py                          # rule-based (no API key needed)
    ANTHROPIC_API_KEY=sk-ant-... python demo.py   # with Claude
"""

from __future__ import annotations

import os
import sys

# Ensure the package is importable when running from the repo root
sys.path.insert(0, os.path.dirname(__file__))

from orchestrator.agents import (
    AnalysisAgent,
    ConsultingAgent,
    EcommerceMetrics,
    TriageAgent,
)
from orchestrator.agents.triage_agent import TriageItem

api_key = os.environ.get("ANTHROPIC_API_KEY")

_DIVIDER = "━" * 50


def section(title: str) -> None:
    print(f"\n{_DIVIDER}")
    print(f"  {title}")
    print(_DIVIDER)


# --------------------------------------------------------------------------- #
# 1. AnalysisAgent                                                             #
# --------------------------------------------------------------------------- #
section("1 / 3  —  AnalysisAgent: monthly revenue data")

SALES_DATA = [
    {"month": "2024-01", "revenue": 48200, "orders": 112},
    {"month": "2024-02", "revenue": 53800, "orders": 131},
    {"month": "2024-03", "revenue": 51500, "orders": 119},
    {"month": "2024-04", "revenue": 60100, "orders": 147},
    {"month": "2024-05", "revenue": 58700, "orders": 143},
    {"month": "2024-06", "revenue": 67400, "orders": 164},
]

analysis_agent = AnalysisAgent(api_key=api_key)
analysis_result = analysis_agent.analyze(SALES_DATA, analysis_type="ecommerce")

print(f"\nSummary  : {analysis_result.summary}")
print(f"Source   : {analysis_result.source}")
if analysis_result.insights:
    print(f"\nInsights ({len(analysis_result.insights)}):")
    for ins in analysis_result.insights:
        print(f"  • {ins.finding}")
if analysis_result.recommendations:
    print(f"\nRecommendations ({len(analysis_result.recommendations)}):")
    for rec in analysis_result.recommendations:
        print(f"  [{rec.priority.upper()}] {rec.action}")


# --------------------------------------------------------------------------- #
# 2. ConsultingAgent                                                           #
# --------------------------------------------------------------------------- #
section("2 / 3  —  ConsultingAgent: e-commerce metrics")

METRICS = EcommerceMetrics(
    revenue=67400,
    orders=164,
    conversion_rate=0.018,       # below avg (2-4%)
    cart_abandonment_rate=0.82,  # above warning threshold (80%)
    ltv=420,
    cac=160,                     # LTV:CAC = 2.6x — below healthy 3:1
    forecast_mape=0.14,
)

consulting_agent = ConsultingAgent(api_key=api_key)
report = consulting_agent.advise(METRICS)

print(f"\nSituation    : {report.situation}")
print(f"Complication : {report.complication}")
print(f"Source       : {report.source}")
if report.flags:
    print(f"\n⚠ Flagged metrics:")
    for flag in report.flags:
        print(f"  ! {flag}")
if report.recommendations:
    print(f"\nRecommendations ({len(report.recommendations)}):")
    for rec in report.recommendations:
        tag = "⚡ quick win" if rec.type == "quick_win" else "📈 strategic"
        print(f"  [{rec.priority.upper()}] {tag}  {rec.action}")
        print(f"         Impact: {rec.expected_impact}")
if report.next_steps:
    print(f"\nNext steps:")
    for step in report.next_steps:
        print(f"  → {step}")


# --------------------------------------------------------------------------- #
# 3. TriageAgent                                                               #
# --------------------------------------------------------------------------- #
section("3 / 3  —  TriageAgent: GitHub notifications")

NOTIFICATIONS = [
    TriageItem(id="n1", title="Fix auth token expiry — critical", reason="review_requested",
               repo="labgadget015-dotcom/ai-consulting-platform", author="alice"),
    TriageItem(id="n2", title="You were mentioned in discussion #42", reason="mention",
               repo="labgadget015-dotcom/ai-analyze-think-act-core", author="bob"),
    TriageItem(id="n3", title="Bump requests from 2.31 to 2.32", reason="subscribed",
               repo="labgadget015-dotcom/prompt-orchestrator", author="dependabot[bot]"),
    TriageItem(id="n4", title="PR assigned to you: add CSV export", reason="assign",
               repo="labgadget015-dotcom/analysis-os", author="carol"),
    TriageItem(id="n5", title="CI passed on main", reason="subscribed",
               repo="labgadget015-dotcom/github-notifications-copilot", author="github-actions[bot]"),
]

triage_agent = TriageAgent(api_key=api_key)
triage_results = triage_agent.triage(NOTIFICATIONS)

priority_emoji = {"P1": "🔴", "P2": "🟡", "P3": "⚪"}
action_width = max(len(r.action.value) for r in triage_results)

print()
for r in triage_results:
    emoji = priority_emoji.get(r.priority.value, "")
    print(f"  {emoji} [{r.priority.value}] {r.action.value:<{action_width}}  {r.reason}")

p1 = sum(1 for r in triage_results if r.priority.value == "P1")
p2 = sum(1 for r in triage_results if r.priority.value == "P2")
p3 = sum(1 for r in triage_results if r.priority.value == "P3")
print(f"\nSummary: {p1} urgent · {p2} review later · {p3} muted/archived  (source: {triage_results[0].source})")


# --------------------------------------------------------------------------- #
# Done                                                                         #
# --------------------------------------------------------------------------- #
section("Done")
print("\nAll three agents completed successfully.")
print("Set ANTHROPIC_API_KEY to enable Claude-powered responses.\n")
