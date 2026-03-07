"""CLI entry point for prompt-orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="gh-orchestrate",
        description="Run prompt-orchestrator agents from the command line",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # triage sub-command
    triage_p = subparsers.add_parser("triage", help="Triage a list of items")
    triage_p.add_argument("--input", "-i", help="JSON file with items to triage (default: stdin)")
    triage_p.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    triage_p.add_argument("--output", "-o", choices=["json", "table"], default="table")

    # analyze sub-command
    analyze_p = subparsers.add_parser("analyze", help="Analyze a dataset")
    analyze_p.add_argument("--input", "-i", help="JSON or CSV file to analyze (default: stdin)")
    analyze_p.add_argument("--type", "-t", default="ecommerce",
                           choices=["ecommerce", "forecast", "segmentation", "anomaly"])
    analyze_p.add_argument("--focus", help="Specific question to focus on")
    analyze_p.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    analyze_p.add_argument("--output", "-o", choices=["json", "summary"], default="summary")

    args = parser.parse_args()

    api_key = getattr(args, "api_key", None) or os.environ.get("ANTHROPIC_API_KEY")

    if args.command == "triage":
        _run_triage(args, api_key)
    elif args.command == "analyze":
        _run_analyze(args, api_key)


def _run_triage(args, api_key):
    from orchestrator.agents import TriageAgent
    from orchestrator.agents.triage_agent import TriageItem

    raw = _read_input(args.input)
    items_data = json.loads(raw)
    items = [
        TriageItem(
            id=str(item.get("id", i)),
            title=item.get("title", ""),
            reason=item.get("reason", "subscribed"),
            repo=item.get("repo", ""),
            author=item.get("author", ""),
        )
        for i, item in enumerate(items_data)
    ]

    agent = TriageAgent(api_key=api_key)
    results = agent.triage(items)

    if args.output == "json":
        print(json.dumps([
            {"id": r.id, "priority": r.priority.value, "action": r.action.value, "reason": r.reason}
            for r in results
        ], indent=2))
    else:
        p1 = [r for r in results if r.priority.value == "P1"]
        p2 = [r for r in results if r.priority.value == "P2"]
        p3 = [r for r in results if r.priority.value == "P3"]
        print(f"\n📬 Triage Summary ({len(results)} items)")
        print("━" * 40)
        print(f"🔴 P1 ({len(p1)})  → Review now")
        print(f"🟡 P2 ({len(p2)}) → Review later")
        print(f"⚪ P3 ({len(p3)}) → Mute/archive")
        for r in p1:
            print(f"  • [{r.priority.value}] {r.id}: {r.reason}")


def _run_analyze(args, api_key):
    from orchestrator.agents import AnalysisAgent

    raw = _read_input(args.input)
    agent = AnalysisAgent(api_key=api_key)
    result = agent.analyze(raw, analysis_type=args.type, focus=getattr(args, "focus", None))

    if args.output == "json":
        print(json.dumps({
            "summary": result.summary,
            "insights": [{"finding": i.finding, "evidence": i.evidence} for i in result.insights],
            "recommendations": [{"action": r.action, "priority": r.priority} for r in result.recommendations],
            "source": result.source,
        }, indent=2))
    else:
        print(f"\n📊 Analysis ({result.source})")
        print("━" * 40)
        print(f"Summary: {result.summary}")
        if result.insights:
            print(f"\nInsights ({len(result.insights)}):")
            for ins in result.insights:
                print(f"  • {ins.finding}")
        if result.recommendations:
            print(f"\nRecommendations ({len(result.recommendations)}):")
            for rec in result.recommendations:
                print(f"  [{rec.priority.upper()}] {rec.action}")


def _read_input(path: str | None) -> str:
    if path:
        with open(path) as f:
            return f.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("Error: provide --input or pipe data via stdin", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
