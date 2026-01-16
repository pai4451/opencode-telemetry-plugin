#!/usr/bin/env python3
"""
OpenCode Telemetry Metrics Analyzer

Analyzes metrics.jsonl to calculate:
1. Edit requests acceptance rate
2. Total LOC accepted (lines added/deleted)

Usage:
    python analyze_metrics.py [path_to_metrics.jsonl]

Default path: /home/mtk26468/opencode/otel-data/metrics.jsonl
"""

import json
import sys
from collections import defaultdict
from typing import Dict, Any

def parse_metrics_file(filepath: str) -> list:
    """Read and parse the JSONL metrics file."""
    metrics = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    metrics.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON line: {e}")
    return metrics

def get_attribute_value(attributes: list, key: str) -> Any:
    """Extract attribute value by key from OTEL attributes list."""
    for attr in attributes:
        if attr.get("key") == key:
            value = attr.get("value", {})
            # Handle different value types
            if "stringValue" in value:
                return value["stringValue"]
            elif "intValue" in value:
                return int(value["intValue"])
            elif "doubleValue" in value:
                return float(value["doubleValue"])
            elif "boolValue" in value:
                return value["boolValue"]
    return None

def analyze_metrics(metrics: list) -> Dict[str, Any]:
    """
    Analyze metrics to extract:
    - Permission acceptance/rejection counts
    - LOC added/deleted (accepted only)
    """
    results = {
        "permissions": defaultdict(int),  # reply_type -> count
        "loc_added": 0,
        "loc_deleted": 0,
        "loc_by_language": defaultdict(lambda: {"added": 0, "deleted": 0}),
        "sessions": set(),
    }

    for export in metrics:
        resource_metrics = export.get("resourceMetrics", [])

        for rm in resource_metrics:
            scope_metrics = rm.get("scopeMetrics", [])

            for sm in scope_metrics:
                metrics_list = sm.get("metrics", [])

                for metric in metrics_list:
                    name = metric.get("name", "")

                    # Process permission requests
                    if name == "opencode.permission.requests":
                        sum_data = metric.get("sum", {})
                        data_points = sum_data.get("dataPoints", [])

                        for dp in data_points:
                            attrs = dp.get("attributes", [])
                            reply = get_attribute_value(attrs, "permission.reply")
                            count = dp.get("asDouble", 0) or dp.get("asInt", 0)
                            session_id = get_attribute_value(attrs, "session.id")

                            if reply:
                                results["permissions"][reply] += int(count)
                            if session_id:
                                results["sessions"].add(session_id)

                    # Process LOC added (only recorded for accepted edits)
                    elif name == "opencode.tool.loc.added":
                        sum_data = metric.get("sum", {})
                        data_points = sum_data.get("dataPoints", [])

                        for dp in data_points:
                            attrs = dp.get("attributes", [])
                            count = dp.get("asDouble", 0) or dp.get("asInt", 0)
                            language = get_attribute_value(attrs, "language") or "unknown"

                            results["loc_added"] += int(count)
                            results["loc_by_language"][language]["added"] += int(count)

                    # Process LOC deleted (only recorded for accepted edits)
                    elif name == "opencode.tool.loc.deleted":
                        sum_data = metric.get("sum", {})
                        data_points = sum_data.get("dataPoints", [])

                        for dp in data_points:
                            attrs = dp.get("attributes", [])
                            count = dp.get("asDouble", 0) or dp.get("asInt", 0)
                            language = get_attribute_value(attrs, "language") or "unknown"

                            results["loc_deleted"] += int(count)
                            results["loc_by_language"][language]["deleted"] += int(count)

    return results

def print_report(results: Dict[str, Any]):
    """Print a formatted report of the metrics analysis."""
    print("=" * 60)
    print("       OPENCODE TELEMETRY METRICS REPORT")
    print("=" * 60)
    print()

    # Permission stats
    permissions = results["permissions"]
    accepted = permissions.get("accept", 0)
    rejected = permissions.get("reject", 0)
    auto_accepted = permissions.get("auto_accept", 0)
    total_requests = accepted + rejected + auto_accepted

    print("1. EDIT REQUESTS ACCEPTANCE RATE")
    print("-" * 40)
    print(f"   Accepted:      {accepted:>6}")
    print(f"   Rejected:      {rejected:>6}")
    print(f"   Auto-accepted: {auto_accepted:>6}")
    print(f"   Total:         {total_requests:>6}")
    print()

    if total_requests > 0:
        acceptance_rate = (accepted + auto_accepted) / total_requests * 100
        print(f"   ACCEPTANCE RATE: {acceptance_rate:.1f}%")
        print(f"   ({accepted + auto_accepted} accepted out of {total_requests} requests)")
    else:
        print("   ACCEPTANCE RATE: N/A (no requests)")
    print()

    # LOC stats
    loc_added = results["loc_added"]
    loc_deleted = results["loc_deleted"]
    net_loc = loc_added - loc_deleted

    print("2. TOTAL LINES OF CODE ACCEPTED")
    print("-" * 40)
    print(f"   Lines Added:   +{loc_added:>6}")
    print(f"   Lines Deleted: -{loc_deleted:>6}")
    print(f"   Net Change:    {net_loc:>+7}")
    print()

    # LOC by language
    if results["loc_by_language"]:
        print("3. LOC BY PROGRAMMING LANGUAGE")
        print("-" * 40)
        for lang, counts in sorted(results["loc_by_language"].items()):
            added = counts["added"]
            deleted = counts["deleted"]
            print(f"   {lang:>12}: +{added:<4} -{deleted:<4} (net: {added - deleted:+d})")
    print()

    # Session info
    print("4. SESSION INFO")
    print("-" * 40)
    print(f"   Unique sessions: {len(results['sessions'])}")
    print()

    print("=" * 60)
    print("  KEY METRICS FOR MANAGEMENT:")
    print("=" * 60)
    if total_requests > 0:
        print(f"  * Acceptance Rate: {acceptance_rate:.1f}%")
    print(f"  * Total LOC Accepted: +{loc_added} / -{loc_deleted}")
    print(f"  * Net Code Change: {net_loc:+d} lines")
    print("=" * 60)

def main():
    # Default path
    default_path = "/home/mtk26468/opencode/otel-data/metrics.jsonl"
    filepath = sys.argv[1] if len(sys.argv) > 1 else default_path

    print(f"Analyzing: {filepath}")
    print()

    try:
        metrics = parse_metrics_file(filepath)
        print(f"Loaded {len(metrics)} metric exports")
        print()

        results = analyze_metrics(metrics)
        print_report(results)

    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
