#!/usr/bin/env python3
"""
OpenCode Telemetry Traces Analyzer

Analyzes traces.jsonl to extract:
1. AI prompts and completions
2. Token usage and model information
3. Correlation data (session_id, call_id)

Sends to MongoDB collection "prompt" for correlation with "metrics" collection.

Usage:
    python analyze_traces.py [path_to_traces.jsonl]
    python analyze_traces.py --to-mongo  # Convert and send to MongoDB
"""

import argparse
import json
import sys
from collections import defaultdict, Counter
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

def parse_traces_file(filepath: str) -> list:
    """Read and parse the JSONL traces file."""
    traces = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON line: {e}")
    return traces

def get_attribute_value(attributes: list, key: str) -> Any:
    """Extract attribute value by key from OTEL attributes list."""
    for attr in attributes:
        if attr.get("key") == key:
            value = attr.get("value", {})
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
        seconds = int(nano_timestamp) / 1_000_000_000
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except (ValueError, TypeError):
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

def has_attribute(span, attr_key):
    """Check if span has a specific attribute key."""
    for attr in span.get("attributes", []):
        if attr.get("key") == attr_key:
            return True
    return False

def is_tool_call_span(span):
    """Robust detection of tool call spans using attributes, not span name."""
    # Method 1: Check operation.name
    operation_name = get_attribute_value(span.get("attributes", []), "operation.name")
    if operation_name and "toolCall" in operation_name:
        return True

    # Method 2: Check ai.operationId
    operation_id = get_attribute_value(span.get("attributes", []), "ai.operationId")
    if operation_id and "toolCall" in operation_id:
        return True

    # Method 3: Check for ai.toolCall.id attribute (definitive)
    return has_attribute(span, "ai.toolCall.id")

def is_prompt_span(span):
    """Robust detection of spans containing prompts using attribute presence."""
    # Check for prompt attributes (not span name)
    return has_attribute(span, "ai.prompt.messages") or has_attribute(span, "ai.prompt")

def extract_prompt_records(traces: list) -> List[Dict[str, Any]]:
    """
    Extract trace spans and convert to prompt records for MongoDB.

    Improved strategy (ChatGPT feedback):
    1. Group spans by traceId
    2. Find tool call spans using ATTRIBUTE presence (not name matching)
    3. Find prompt spans using ATTRIBUTE presence (not hardcoded span names)
    4. Combine using call_id as join key
    """
    records = []

    # First pass: organize spans by traceId
    traces_by_id = defaultdict(list)

    for export in traces:
        for rs in export.get("resourceSpans", []):
            for ss in rs.get("scopeSpans", []):
                for span in ss.get("spans", []):
                    trace_id = span.get("traceId")
                    traces_by_id[trace_id].append(span)

    # Second pass: correlate spans within each trace
    for trace_id, spans in traces_by_id.items():
        # Find tool call spans using robust detection
        tool_call_spans = [s for s in spans if is_tool_call_span(s)]
        # Find prompt spans using attribute presence
        prompt_spans = [s for s in spans if is_prompt_span(s)]

        if not tool_call_spans:
            continue

        # Get prompt data from prompt span (if available)
        prompt_data = {}
        if prompt_spans:
            # Use first prompt span (or could find best one by timestamp)
            prompt_span = prompt_spans[0]
            attrs = {a["key"]: a.get("value", {}) for a in prompt_span.get("attributes", [])}

            # Extract prompt (try both attribute keys)
            prompt_json = get_attribute_value(prompt_span.get("attributes", []), "ai.prompt.messages") or \
                         get_attribute_value(prompt_span.get("attributes", []), "ai.prompt")

            if prompt_json:
                try:
                    if isinstance(prompt_json, str):
                        prompt_data["prompt_messages"] = json.loads(prompt_json)
                    else:
                        prompt_data["prompt_messages"] = prompt_json
                except:
                    prompt_data["prompt_messages_raw"] = str(prompt_json)

            # Extract other fields
            prompt_data["response_text"] = get_attribute_value(prompt_span.get("attributes", []), "ai.response.text")
            prompt_data["prompt_tokens"] = get_attribute_value(prompt_span.get("attributes", []), "ai.usage.inputTokens") or 0
            prompt_data["completion_tokens"] = get_attribute_value(prompt_span.get("attributes", []), "ai.usage.outputTokens") or 0
            prompt_data["model"] = get_attribute_value(prompt_span.get("attributes", []), "gen_ai.request.model") or "unknown"
            prompt_data["provider"] = get_attribute_value(prompt_span.get("attributes", []), "gen_ai.system") or "unknown"
            prompt_data["temperature"] = get_attribute_value(prompt_span.get("attributes", []), "gen_ai.request.temperature")
            prompt_data["max_tokens"] = get_attribute_value(prompt_span.get("attributes", []), "gen_ai.request.max_tokens")

        # Create record for each toolCall
        for tc_span in tool_call_spans:
            attrs = {a["key"]: a.get("value", {}) for a in tc_span.get("attributes", [])}

            # Extract user prompt from messages
            user_prompt = ""
            if "prompt_messages" in prompt_data:
                for msg in prompt_data["prompt_messages"]:
                    if msg.get("role") == "user":
                        content = msg.get("content")
                        if isinstance(content, str):
                            user_prompt = content
                        elif isinstance(content, list):
                            user_prompt = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
                        break

            # Use get_attribute_value for all extractions (handles OTLP value union)
            call_id = get_attribute_value(tc_span.get("attributes", []), "ai.toolCall.id") or \
                     get_attribute_value(tc_span.get("attributes", []), "call.id") or "unknown"

            tool_name = get_attribute_value(tc_span.get("attributes", []), "ai.toolCall.name") or \
                       get_attribute_value(tc_span.get("attributes", []), "tool.name") or "unknown"

            tool_args = get_attribute_value(tc_span.get("attributes", []), "ai.toolCall.args") or "{}"

            # Extract session context (if injected by plugin)
            session_id = get_attribute_value(tc_span.get("attributes", []), "session.id")
            user = get_attribute_value(tc_span.get("attributes", []), "user")
            file_path = get_attribute_value(tc_span.get("attributes", []), "file.path")
            language = get_attribute_value(tc_span.get("attributes", []), "language")

            # Calculate duration
            start_nano = int(tc_span.get("startTimeUnixNano", 0))
            end_nano = int(tc_span.get("endTimeUnixNano", 0))
            duration_ms = (end_nano - start_nano) / 1_000_000.0 if end_nano > start_nano else 0

            record = {
                # Primary join key
                "call_id": call_id,
                "trace_id": trace_id,

                # Session context (if available)
                "session_id": session_id,
                "user": user,
                "file_path": file_path,
                "language": language,

                # Prompt data
                "prompt_messages": prompt_data.get("prompt_messages", []),
                "user_prompt": user_prompt,
                "ai_response": prompt_data.get("response_text", ""),

                # Model/provider info
                "model": prompt_data.get("model", "unknown"),
                "provider": prompt_data.get("provider", "unknown"),
                "temperature": prompt_data.get("temperature"),
                "max_tokens": prompt_data.get("max_tokens"),

                # Token usage
                "prompt_tokens": prompt_data.get("prompt_tokens", 0),
                "completion_tokens": prompt_data.get("completion_tokens", 0),
                "total_tokens": prompt_data.get("prompt_tokens", 0) + prompt_data.get("completion_tokens", 0),

                # Tool info
                "tool_name": tool_name,
                "tool_args": tool_args,

                # Timing
                "time": nano_to_iso(tc_span.get("startTimeUnixNano", "")),
                "duration_ms": duration_ms,
            }

            records.append(record)

    return records

def send_to_mongodb(records, mongo_uri="mongodb://localhost:27017",
                   db_name="opencode_telemetry", collection_name="prompt"):
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

    result = collection.insert_many(records)
    inserted_count = len(result.inserted_ids)

    print(f"Successfully inserted {inserted_count} records into MongoDB.")
    print(f"  Database: {db_name}")
    print(f"  Collection: {collection_name}")

    client.close()
    return inserted_count

def print_summary(records: List[Dict[str, Any]]):
    """Print summary of extracted trace data."""
    print("=" * 60)
    print("       OPENCODE TRACE ANALYSIS SUMMARY")
    print("=" * 60)
    print()

    print(f"Total prompt records: {len(records)}")
    print()

    if not records:
        return

    # Session breakdown
    sessions = set(r.get("session_id") for r in records if r.get("session_id"))
    print(f"Unique sessions: {len(sessions)}")

    # User breakdown
    users = set(r.get("user") for r in records if r.get("user"))
    if users:
        print(f"Users: {', '.join(users)}")

    # Model breakdown
    models = Counter(r["model"] for r in records)
    print("\nModels used:")
    for model, count in models.items():
        print(f"  {model}: {count}")

    # Token usage
    total_prompt = sum(r["prompt_tokens"] for r in records)
    total_completion = sum(r["completion_tokens"] for r in records)
    print(f"\nTotal tokens:")
    print(f"  Prompt: {total_prompt:,}")
    print(f"  Completion: {total_completion:,}")
    print(f"  Total: {total_prompt + total_completion:,}")

    # Tool breakdown
    tools = Counter(r["tool_name"] for r in records)
    print("\nTool usage:")
    for tool, count in tools.items():
        print(f"  {tool}: {count}")

    # Language breakdown
    languages = Counter(r.get("language") for r in records if r.get("language"))
    if languages:
        print("\nLanguages:")
        for lang, count in languages.items():
            print(f"  {lang}: {count}")

    print("\n" + "=" * 60)

def main():
    parser = argparse.ArgumentParser(description="OpenCode Telemetry Traces Analyzer")
    parser.add_argument("filepath", nargs="?",
                       default="/home/mtk26468/opencode/otel-data/traces.jsonl",
                       help="Path to traces.jsonl file")
    parser.add_argument("--to-mongo", action="store_true",
                       help="Send to MongoDB")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017",
                       help="MongoDB URI")
    parser.add_argument("--db-name", default="opencode_telemetry",
                       help="Database name")
    parser.add_argument("--collection", default="prompt",
                       help="Collection name")
    parser.add_argument("--show-records", action="store_true",
                       help="Print records for debugging")

    args = parser.parse_args()

    print(f"Analyzing: {args.filepath}\n")

    try:
        traces = parse_traces_file(args.filepath)
        print(f"Loaded {len(traces)} trace exports\n")

        records = extract_prompt_records(traces)
        print(f"Extracted {len(records)} prompt records\n")

        if args.show_records and records:
            print("Sample records:")
            for i, rec in enumerate(records[:3], 1):
                print(f"\nRecord {i}:")
                print(json.dumps(rec, indent=2))

        if args.to_mongo and records:
            send_to_mongodb(records, args.mongo_uri, args.db_name, args.collection)

        print_summary(records)

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
