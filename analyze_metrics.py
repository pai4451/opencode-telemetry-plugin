#!/usr/bin/env python3
"""
OpenCode Telemetry Metrics Analyzer

Analyzes metrics.jsonl to calculate:
1. Edit requests acceptance rate
2. Total LOC accepted (lines added/deleted)

Usage:
    python analyze_metrics.py [path_to_metrics.jsonl]
    python analyze_metrics.py --to-mongo  # Convert and send to MongoDB

Default path: /home/mtk26468/opencode/otel-data/metrics.jsonl
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

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

def nano_to_iso(nano_timestamp: str) -> str:
    """Convert nanosecond timestamp to ISO 8601 format."""
    try:
        # Convert nanoseconds to seconds
        seconds = int(nano_timestamp) / 1_000_000_000
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

def extract_records_for_mongo(metrics: list) -> List[Dict[str, Any]]:
    """
    Extract metrics and convert to final JSON format for MongoDB.

    Final format:
    {
        accept: true/false,
        ai_loc: number,
        ai_char: 0,
        auto_approve_edit: true/false,
        completion_tokens: 0,
        effective: true,
        filepath: string,
        function_category: "opencode",
        language: string,
        model: string,
        prompt_tokens: 0,
        sid: string,
        time: ISO timestamp,
        user: string,
        user_char: 0,
        user_loc: 0,
        version: string
    }
    """
    # First pass: collect LOC data by call.id
    loc_data = {}  # call.id -> {added: int, deleted: int, language: str, filepath: str, ...}

    # Second pass: collect permission data and merge with LOC
    records = []

    for export in metrics:
        resource_metrics = export.get("resourceMetrics", [])

        for rm in resource_metrics:
            scope_metrics = rm.get("scopeMetrics", [])

            for sm in scope_metrics:
                metrics_list = sm.get("metrics", [])

                for metric in metrics_list:
                    name = metric.get("name", "")

                    # Collect LOC added data
                    if name == "opencode.tool.loc.added":
                        sum_data = metric.get("sum", {})
                        data_points = sum_data.get("dataPoints", [])

                        for dp in data_points:
                            attrs = dp.get("attributes", [])
                            call_id = get_attribute_value(attrs, "call.id")
                            if call_id:
                                if call_id not in loc_data:
                                    loc_data[call_id] = {"added": 0, "deleted": 0}
                                loc_data[call_id]["added"] = int(dp.get("asDouble", 0) or dp.get("asInt", 0))
                                loc_data[call_id]["language"] = get_attribute_value(attrs, "language") or "unknown"
                                loc_data[call_id]["filepath"] = get_attribute_value(attrs, "file.path") or "unknown"
                                loc_data[call_id]["model"] = get_attribute_value(attrs, "model") or "unknown"
                                loc_data[call_id]["user"] = get_attribute_value(attrs, "user") or "unknown"
                                loc_data[call_id]["version"] = get_attribute_value(attrs, "version") or "1.0.0"
                                loc_data[call_id]["session_id"] = get_attribute_value(attrs, "session.id") or "unknown"
                                loc_data[call_id]["time"] = nano_to_iso(dp.get("timeUnixNano", ""))

                    # Collect LOC deleted data
                    elif name == "opencode.tool.loc.deleted":
                        sum_data = metric.get("sum", {})
                        data_points = sum_data.get("dataPoints", [])

                        for dp in data_points:
                            attrs = dp.get("attributes", [])
                            call_id = get_attribute_value(attrs, "call.id")
                            if call_id:
                                if call_id not in loc_data:
                                    loc_data[call_id] = {"added": 0, "deleted": 0}
                                loc_data[call_id]["deleted"] = int(dp.get("asDouble", 0) or dp.get("asInt", 0))

    # Second pass: process permission requests and create final records
    for export in metrics:
        resource_metrics = export.get("resourceMetrics", [])

        for rm in resource_metrics:
            scope_metrics = rm.get("scopeMetrics", [])

            for sm in scope_metrics:
                metrics_list = sm.get("metrics", [])

                for metric in metrics_list:
                    name = metric.get("name", "")

                    if name == "opencode.permission.requests":
                        sum_data = metric.get("sum", {})
                        data_points = sum_data.get("dataPoints", [])

                        for dp in data_points:
                            attrs = dp.get("attributes", [])
                            call_id = get_attribute_value(attrs, "call.id")
                            reply = get_attribute_value(attrs, "permission.reply")
                            auto_approve = get_attribute_value(attrs, "auto_approve_edit")

                            # Determine accept status
                            # reply_type values: "once", "always", "auto", "reject"
                            # - "once" = user clicked accept once (dialog shown)
                            # - "always" = user clicked accept always (dialog shown)
                            # - "auto" = no dialog shown, system auto-approved
                            # - "reject" = user rejected
                            # Also support legacy values: "accept", "auto_accept"
                            is_accepted = reply in ["once", "always", "auto", "accept", "auto_accept"]

                            # Get LOC data for this call
                            loc = loc_data.get(call_id, {})
                            ai_loc = loc.get("added", 0) if is_accepted else 0

                            # Build final record
                            record = {
                                "accept": is_accepted,
                                "ai_loc": ai_loc,
                                "ai_char": 0,  # Hardcoded
                                "auto_approve_edit": auto_approve == "true",
                                "completion_tokens": 0,  # Hardcoded
                                "effective": True,  # Hardcoded
                                "filepath": get_attribute_value(attrs, "file.path") or loc.get("filepath", "unknown"),
                                "function_category": "opencode",  # Hardcoded
                                "language": get_attribute_value(attrs, "language") or loc.get("language", "unknown"),
                                "model": get_attribute_value(attrs, "model") or loc.get("model", "unknown"),
                                "prompt_tokens": 0,  # Hardcoded
                                "sid": get_attribute_value(attrs, "session.id") or loc.get("session_id", "unknown"),
                                "time": nano_to_iso(dp.get("timeUnixNano", "")),
                                "user": get_attribute_value(attrs, "user") or loc.get("user", "unknown"),
                                "user_char": 0,  # Hardcoded
                                "user_loc": 0,  # Hardcoded
                                "version": get_attribute_value(attrs, "version") or loc.get("version", "1.0.0"),
                                # Extra fields for debugging (optional)
                                "call_id": call_id,
                                "reply_type": reply,
                            }

                            records.append(record)

    return records

def send_to_mongodb(records: List[Dict[str, Any]], mongo_uri: str = "mongodb://localhost:27017", db_name: str = "opencode_telemetry", collection_name: str = "metrics"):
    """Send records to MongoDB."""
    try:
        from pymongo import MongoClient
    except ImportError:
        print("Error: pymongo is not installed. Install it with: pip install pymongo")
        sys.exit(1)

    if not records:
        print("No records to send to MongoDB.")
        return 0

    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]

    # Insert records
    result = collection.insert_many(records)
    inserted_count = len(result.inserted_ids)

    print(f"Successfully inserted {inserted_count} records into MongoDB.")
    print(f"  Database: {db_name}")
    print(f"  Collection: {collection_name}")

    client.close()
    return inserted_count

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
    # New values: "once", "always", "auto", "reject"
    # Legacy values: "accept", "auto_accept"
    permissions = results["permissions"]
    # Manual accepts: "once" (new) or "accept" (legacy)
    manual_once = permissions.get("once", 0) + permissions.get("accept", 0)
    # Manual always: "always" (new) or "auto_accept" (legacy)
    manual_always = permissions.get("always", 0) + permissions.get("auto_accept", 0)
    # Auto-approved (no dialog): "auto" (new)
    auto_approved = permissions.get("auto", 0)
    # Rejected
    rejected = permissions.get("reject", 0)

    total_requests = manual_once + manual_always + auto_approved + rejected
    total_accepted = manual_once + manual_always + auto_approved

    print("1. EDIT REQUESTS ACCEPTANCE RATE")
    print("-" * 40)
    print(f"   Manual (once):   {manual_once:>6}  <- user clicked 'Accept'")
    print(f"   Manual (always): {manual_always:>6}  <- user clicked 'Always'")
    print(f"   Auto-approved:   {auto_approved:>6}  <- no dialog shown")
    print(f"   Rejected:        {rejected:>6}")
    print(f"   Total:           {total_requests:>6}")
    print()

    if total_requests > 0:
        acceptance_rate = total_accepted / total_requests * 100
        print(f"   ACCEPTANCE RATE: {acceptance_rate:.1f}%")
        print(f"   ({total_accepted} accepted out of {total_requests} requests)")
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
    parser = argparse.ArgumentParser(
        description="OpenCode Telemetry Metrics Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze_metrics.py                    # Analyze and print report
    python analyze_metrics.py --to-mongo         # Convert and send to MongoDB
    python analyze_metrics.py --to-mongo --print # Send to MongoDB and print report
    python analyze_metrics.py /path/to/metrics.jsonl  # Custom metrics file
        """
    )
    parser.add_argument(
        "filepath",
        nargs="?",
        default="/home/mtk26468/opencode/otel-data/metrics.jsonl",
        help="Path to metrics.jsonl file (default: /home/mtk26468/opencode/otel-data/metrics.jsonl)"
    )
    parser.add_argument(
        "--to-mongo",
        action="store_true",
        default=False,
        help="Convert metrics to final JSON format and send to MongoDB"
    )
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="MongoDB connection URI (default: mongodb://localhost:27017)"
    )
    parser.add_argument(
        "--db-name",
        default="opencode_telemetry",
        help="MongoDB database name (default: opencode_telemetry)"
    )
    parser.add_argument(
        "--collection",
        default="metrics",
        help="MongoDB collection name (default: metrics)"
    )
    parser.add_argument(
        "--print",
        dest="print_report",
        action="store_true",
        default=False,
        help="Print report even when --to-mongo is used"
    )
    parser.add_argument(
        "--show-records",
        action="store_true",
        default=False,
        help="Print the records that would be sent to MongoDB (for debugging)"
    )

    args = parser.parse_args()

    print(f"Analyzing: {args.filepath}")
    print()

    try:
        metrics = parse_metrics_file(args.filepath)
        print(f"Loaded {len(metrics)} metric exports")
        print()

        if args.to_mongo:
            # Convert to final JSON format and send to MongoDB
            records = extract_records_for_mongo(metrics)
            print(f"Converted to {len(records)} records for MongoDB")
            print()

            if args.show_records:
                print("Records to be inserted:")
                print("-" * 40)
                for i, record in enumerate(records, 1):
                    print(f"Record {i}:")
                    print(json.dumps(record, indent=2))
                    print()

            if records:
                send_to_mongodb(
                    records,
                    mongo_uri=args.mongo_uri,
                    db_name=args.db_name,
                    collection_name=args.collection
                )

            if args.print_report:
                print()
                results = analyze_metrics(metrics)
                print_report(results)
        else:
            # Default: analyze and print report
            results = analyze_metrics(metrics)
            print_report(results)

    except FileNotFoundError:
        print(f"Error: File not found: {args.filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
