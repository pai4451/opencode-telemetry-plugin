#!/usr/bin/env python3
"""
OpenCode Telemetry - Incremental JSONL to MongoDB Import

This script processes OTEL JSONL log files incrementally and stores them in MongoDB.
Designed for running as a Jenkins job every 5-15 minutes.

Features:
- Persistent state storage in MongoDB
- Resume from last position
- Safe rewind mechanism (4KB) to handle crashes
- Duplicate prevention via unique IDs + upsert
- File rotation detection via inode
- Incremental state saves every 100 records
- Clear logging with progress and summary

Usage:
    python send-to-mongodb.py                    # Normal incremental run
    python send-to-mongodb.py --status           # Show current state
    python send-to-mongodb.py --reset-state      # Reset and reprocess all
    python send-to-mongodb.py --verbose          # Verbose logging
    python send-to-mongodb.py --dry-run          # Parse but don't insert
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
except ImportError:
    print("Error: pymongo is required. Install with: pip install pymongo")
    sys.exit(1)

# =============================================================================
# Constants
# =============================================================================

REWIND_BYTES = 4096  # 4KB rewind for safety on resume
STATE_SAVE_INTERVAL = 100  # Save state every 100 records

# Default file paths
DEFAULT_TRACES_FILE = "/home/mtk26468/opencode/otel-data/traces.jsonl"
DEFAULT_METRICS_FILE = "/home/mtk26468/opencode/otel-data/metrics.jsonl"

# MongoDB defaults
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB_NAME = "opencode_telemetry"

# Collection names
TRACES_STATE_COLLECTION = "otel_file_traces_state"
METRICS_STATE_COLLECTION = "otel_file_metrics_state"
PROMPT_COLLECTION = "prompt"
METRICS_COLLECTION = "metrics"

# Logger
logger = logging.getLogger(__name__)


# =============================================================================
# OTEL Attribute Extraction Utilities
# =============================================================================

def get_attribute_value(attributes: List[Dict], key: str, default: Any = None) -> Any:
    """
    Extract value from OTEL attributes array.

    OTEL attributes are stored as: [{"key": "name", "value": {"stringValue": "foo"}}]
    """
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
            elif "arrayValue" in value:
                return [get_primitive_value(v) for v in value["arrayValue"].get("values", [])]
    return default


def get_primitive_value(value: Dict) -> Any:
    """Extract primitive value from OTEL value object."""
    if "stringValue" in value:
        return value["stringValue"]
    elif "intValue" in value:
        return int(value["intValue"])
    elif "doubleValue" in value:
        return float(value["doubleValue"])
    elif "boolValue" in value:
        return value["boolValue"]
    return None


def nano_to_iso(nano_timestamp: str) -> Optional[str]:
    """Convert nanosecond timestamp to ISO 8601 format string."""
    try:
        ts = int(nano_timestamp)
        dt = datetime.fromtimestamp(ts / 1e9, tz=timezone.utc)
        # Use strftime to match analyze_traces.py format (no microseconds)
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except (ValueError, TypeError, OSError):
        return None


def infer_language_from_filepath(filepath: str) -> str:
    """Infer programming language from file extension."""
    if not filepath:
        return "unknown"

    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "shell",
        ".bash": "shell",
        ".zsh": "shell",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".xml": "xml",
        ".md": "markdown",
        ".txt": "text",
    }

    ext = Path(filepath).suffix.lower()
    return ext_map.get(ext, "unknown")


# =============================================================================
# State Management
# =============================================================================

def load_state(db, state_collection_name: str) -> Dict:
    """Load processing state from MongoDB."""
    collection = db[state_collection_name]
    state = collection.find_one({"_id": "state"})

    if state:
        logger.debug(f"Loaded state from {state_collection_name}: offset={state.get('offset', 0)}, "
                    f"line={state.get('line_number', 0)}")
        return state

    logger.debug(f"No existing state in {state_collection_name}, starting fresh")
    return {
        "offset": 0,
        "line_number": 0,
        "inode": None,
        "mtime": None,
        "last_total_lines": 0,
        "last_processed": None,
        "records_inserted": 0,
        "file_path": None
    }


def save_state(db, state_collection_name: str, file_path: str, offset: int,
               line_number: int, inode: int, mtime: float,
               records_inserted: int, last_total_lines: Optional[int] = None) -> None:
    """Save processing state to MongoDB."""
    collection = db[state_collection_name]

    state = {
        "_id": "state",
        "file_path": file_path,
        "offset": offset,
        "line_number": line_number,
        "inode": inode,
        "mtime": mtime,
        "records_inserted": records_inserted,
        "last_processed": datetime.now(timezone.utc).isoformat()
    }

    if last_total_lines is not None:
        state["last_total_lines"] = last_total_lines

    collection.replace_one({"_id": "state"}, state, upsert=True)
    logger.debug(f"Saved state: offset={offset}, line={line_number}")


def detect_rotation(state: Dict, current_inode: int, current_size: int) -> bool:
    """
    Detect if the file has been rotated or truncated.

    Returns True if:
    - Inode has changed (file was rotated)
    - Saved offset is beyond current file size (file was truncated)
    """
    saved_inode = state.get("inode")
    saved_offset = state.get("offset", 0)

    if saved_inode is not None and saved_inode != current_inode:
        logger.info(f"File rotation detected: inode changed from {saved_inode} to {current_inode}")
        return True

    if saved_offset > current_size:
        logger.info(f"File truncation detected: saved offset {saved_offset} > current size {current_size}")
        return True

    return False


def reset_state(db) -> None:
    """Reset all processing state collections."""
    logger.info("Resetting all state collections...")

    db[TRACES_STATE_COLLECTION].delete_many({})
    db[METRICS_STATE_COLLECTION].delete_many({})

    logger.info("State reset complete")


def show_status(db, traces_file: str, metrics_file: str) -> None:
    """Display current processing state."""
    print("=" * 80)
    print("OpenCode Telemetry - Current State")
    print("=" * 80)

    for name, collection_name, file_path in [
        ("Traces", TRACES_STATE_COLLECTION, traces_file),
        ("Metrics", METRICS_STATE_COLLECTION, metrics_file)
    ]:
        state = load_state(db, collection_name)
        print(f"\n{name}:")
        print("-" * 40)

        if state.get("last_processed"):
            print(f"  File: {state.get('file_path', 'N/A')}")
            print(f"  Offset: {state.get('offset', 0):,} bytes")
            print(f"  Line number: {state.get('line_number', 0):,}")
            print(f"  Inode: {state.get('inode', 'N/A')}")
            print(f"  Last processed: {state.get('last_processed', 'N/A')}")
            print(f"  Records inserted: {state.get('records_inserted', 0):,}")

            # Check current file status
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                print(f"\n  Current file status:")
                print(f"    Size: {stat.st_size:,} bytes")
                print(f"    Inode: {stat.st_ino}")
                print(f"    Modified: {datetime.fromtimestamp(stat.st_mtime).isoformat()}")

                remaining = stat.st_size - state.get("offset", 0)
                if remaining > 0:
                    print(f"    Unprocessed: ~{remaining:,} bytes")
                else:
                    print(f"    Status: Fully processed")
        else:
            print("  No processing state found (not yet processed)")

    # Show collection counts
    print(f"\n\nMongoDB Collections:")
    print("-" * 40)
    print(f"  {PROMPT_COLLECTION}: {db[PROMPT_COLLECTION].count_documents({}):,} documents")
    print(f"  {METRICS_COLLECTION}: {db[METRICS_COLLECTION].count_documents({}):,} documents")
    print("=" * 80)


# =============================================================================
# Unique ID Generation
# =============================================================================

def generate_unique_id(inode: int, byte_position: int, line_bytes: bytes) -> str:
    """
    Generate a unique ID for a JSONL line.

    Format: {inode}:{byte_position}:{sha1_hash[:12]}

    This ensures:
    - Same line in same file position = same ID (idempotent)
    - Different content at same position = different ID (handles edits)
    - Same content at different position = different ID (handles duplicates)
    """
    line_hash = hashlib.sha1(line_bytes).hexdigest()[:12]
    return f"{inode}:{byte_position}:{line_hash}"


# =============================================================================
# Trace Extraction Functions
# =============================================================================

def extract_traces_lookup(trace_data: Dict) -> Dict[str, Dict]:
    """
    Build a lookup table from trace data.

    Returns dict mapping call_id to trace info (model, tokens, etc.)
    """
    lookup = {}

    resource_spans = trace_data.get("resourceSpans", [])

    for resource_span in resource_spans:
        scope_spans = resource_span.get("scopeSpans", [])

        for scope_span in scope_spans:
            spans = scope_span.get("spans", [])

            for span in spans:
                attributes = span.get("attributes", [])

                # Get call_id
                call_id = get_attribute_value(attributes, "gen_ai.openai.request.service_tier")
                if not call_id:
                    call_id = get_attribute_value(attributes, "call_id")
                if not call_id:
                    call_id = span.get("spanId")

                if call_id:
                    lookup[call_id] = {
                        "model": get_attribute_value(attributes, "gen_ai.request.model", "unknown"),
                        "input_tokens": get_attribute_value(attributes, "gen_ai.usage.input_tokens", 0),
                        "output_tokens": get_attribute_value(attributes, "gen_ai.usage.output_tokens", 0),
                        "total_tokens": (
                            get_attribute_value(attributes, "gen_ai.usage.input_tokens", 0) +
                            get_attribute_value(attributes, "gen_ai.usage.output_tokens", 0)
                        ),
                        "session_id": get_attribute_value(attributes, "session.id"),
                        "span_id": span.get("spanId"),
                        "trace_id": span.get("traceId"),
                        "start_time": nano_to_iso(span.get("startTimeUnixNano", "0")),
                        "end_time": nano_to_iso(span.get("endTimeUnixNano", "0")),
                    }

    return lookup


def has_attribute(span: Dict, attr_key: str) -> bool:
    """Check if span has a specific attribute key."""
    for attr in span.get("attributes", []):
        if attr.get("key") == attr_key:
            return True
    return False


def is_tool_call_span(span: Dict) -> bool:
    """Robust detection of tool call spans using attributes, not span name."""
    # Method 1: Check operation.name
    operation_name = get_attribute_value(span.get("attributes", []), "operation.name")
    if operation_name and "toolCall" in str(operation_name):
        return True

    # Method 2: Check ai.operationId
    operation_id = get_attribute_value(span.get("attributes", []), "ai.operationId")
    if operation_id and "toolCall" in str(operation_id):
        return True

    # Method 3: Check for ai.toolCall.id attribute (definitive)
    return has_attribute(span, "ai.toolCall.id")


def is_prompt_span(span: Dict) -> bool:
    """Robust detection of spans containing prompts using attribute presence."""
    return has_attribute(span, "ai.prompt.messages") or has_attribute(span, "ai.prompt")


def extract_prompt_data_from_span(span: Dict) -> Dict:
    """
    Extract prompt data from a prompt span.

    Returns a dict with: prompt_messages, response_text, prompt_tokens,
    completion_tokens, model, provider, temperature, max_tokens
    """
    prompt_data = {}
    attrs = span.get("attributes", [])

    # Extract prompt messages
    prompt_json = get_attribute_value(attrs, "ai.prompt.messages") or \
                 get_attribute_value(attrs, "ai.prompt")

    if prompt_json:
        try:
            if isinstance(prompt_json, str):
                prompt_data["prompt_messages"] = json.loads(prompt_json)
            else:
                prompt_data["prompt_messages"] = prompt_json
        except:
            prompt_data["prompt_messages_raw"] = str(prompt_json)

    # Extract other fields
    prompt_data["response_text"] = get_attribute_value(attrs, "ai.response.text")
    prompt_data["prompt_tokens"] = get_attribute_value(attrs, "ai.usage.inputTokens") or \
                                   get_attribute_value(attrs, "gen_ai.usage.input_tokens") or 0
    prompt_data["completion_tokens"] = get_attribute_value(attrs, "ai.usage.outputTokens") or \
                                       get_attribute_value(attrs, "gen_ai.usage.output_tokens") or 0
    prompt_data["model"] = get_attribute_value(attrs, "gen_ai.request.model") or "unknown"
    prompt_data["provider"] = get_attribute_value(attrs, "gen_ai.system") or "unknown"
    prompt_data["temperature"] = get_attribute_value(attrs, "gen_ai.request.temperature")
    prompt_data["max_tokens"] = get_attribute_value(attrs, "gen_ai.request.max_tokens")

    return prompt_data


def build_prompt_data_lookup(traces_file: str) -> Dict[str, Dict]:
    """
    Build a lookup table mapping traceId to prompt span data.

    This enables correlation of prompt data with tool call spans
    even when they appear in different JSONL lines (OTEL batching).

    Returns: Dict[traceId, prompt_data]
    """
    lookup = {}  # traceId -> prompt_data

    if not os.path.exists(traces_file):
        return lookup

    with open(traces_file, 'r') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                for rs in data.get("resourceSpans", []):
                    for ss in rs.get("scopeSpans", []):
                        for span in ss.get("spans", []):
                            # Only process prompt spans
                            if not is_prompt_span(span):
                                continue

                            trace_id = span.get("traceId")
                            if not trace_id:
                                continue

                            # Extract prompt data from this span
                            prompt_data = extract_prompt_data_from_span(span)

                            # Store in lookup (merge if exists, prefer non-empty values)
                            if trace_id not in lookup:
                                lookup[trace_id] = prompt_data
                            else:
                                # Merge with existing - prefer non-empty/non-zero values
                                for key, value in prompt_data.items():
                                    existing = lookup[trace_id].get(key)
                                    # Replace if current is empty/zero and new has value
                                    if value and (not existing or existing == "unknown" or existing == 0):
                                        lookup[trace_id][key] = value
            except (json.JSONDecodeError, Exception):
                continue

    return lookup


def extract_prompt_records(trace_data: Dict, global_prompt_lookup: Optional[Dict] = None) -> List[Dict]:
    """
    Extract prompt records from trace data for the prompt collection.

    This follows the schema from analyze_traces.py:
    - Groups spans by traceId
    - Finds tool call spans and prompt spans using attribute presence
    - Uses global_prompt_lookup for cross-line correlation (OTEL batching)
    - Extracts prompt messages, AI response, model, tokens, tool info
    - Creates rich records suitable for analysis

    Args:
        trace_data: Single JSONL line parsed as dict
        global_prompt_lookup: Pre-built lookup of traceId -> prompt_data from ALL traces
                             This enables correlation when prompt and tool spans are
                             in different JSONL lines due to OTEL batching.

    Output schema matches analyze_traces.py:
    {
        call_id, trace_id, session_id, user, file_path, language,
        prompt_messages, user_prompt, ai_response,
        model, provider, temperature, max_tokens,
        prompt_tokens, completion_tokens, total_tokens,
        tool_name, tool_args, time, duration_ms
    }
    """
    records = []
    global_prompt_lookup = global_prompt_lookup or {}

    # First pass: organize spans by traceId
    traces_by_id = {}

    resource_spans = trace_data.get("resourceSpans", [])
    for resource_span in resource_spans:
        scope_spans = resource_span.get("scopeSpans", [])
        for scope_span in scope_spans:
            spans = scope_span.get("spans", [])
            for span in spans:
                trace_id = span.get("traceId")
                if trace_id not in traces_by_id:
                    traces_by_id[trace_id] = []
                traces_by_id[trace_id].append(span)

    # Second pass: correlate spans within each trace
    for trace_id, spans in traces_by_id.items():
        # Find tool call spans using robust detection
        tool_call_spans = [s for s in spans if is_tool_call_span(s)]

        if not tool_call_spans:
            continue

        # ALWAYS use the global prompt lookup if available
        # This ensures we use the FIRST prompt span per traceId (matching analyze_traces.py)
        # which is critical because OTEL may have multiple prompt spans with different data
        prompt_data = {}
        if trace_id in global_prompt_lookup:
            prompt_data = global_prompt_lookup[trace_id].copy()
        else:
            # Fall back to local prompt spans only if not in global lookup
            # (shouldn't happen if global lookup is built correctly)
            prompt_spans = [s for s in spans if is_prompt_span(s)]
            if prompt_spans:
                prompt_data = extract_prompt_data_from_span(prompt_spans[0])
                logger.debug(f"Fallback to local prompt span for trace {trace_id[:12]}...")

        # Create record for each toolCall
        for tc_span in tool_call_spans:
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

            # Extract call_id
            call_id = get_attribute_value(tc_span.get("attributes", []), "ai.toolCall.id") or \
                     get_attribute_value(tc_span.get("attributes", []), "call.id") or \
                     tc_span.get("spanId", "unknown")

            # Extract tool info
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

            # Build record matching analyze_traces.py schema
            record = {
                # Primary join key
                "call_id": call_id,
                "trace_id": trace_id,

                # Session context
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

                # Import metadata
                "imported_at": datetime.now(timezone.utc).isoformat()
            }

            records.append(record)

    return records


# =============================================================================
# Metrics Extraction Functions
# =============================================================================

def extract_enriched_metrics(metrics_data: Dict, traces_lookup: Dict, prompt_lookup: Dict = None) -> List[Dict]:
    """
    Extract metrics and convert to aggregated format for MongoDB.

    This follows the schema from analyze_metrics.py:
    - One record per permission request (not per raw metric)
    - LOC data joined with permission data by call_id
    - Final format suitable for management reporting

    Args:
        metrics_data: Raw metrics JSONL data
        traces_lookup: Legacy traces lookup (for tokens)
        prompt_lookup: {call_id: {model, language, ...}} from prompt records

    Enrichment Priority (for model and language):
        1. Direct from metrics attributes - Use if present and not "unknown"
        2. From LOC data - Use if present and not "unknown"
        3. From prompt lookup by call_id - JOIN with prompt data
        4. Infer language from filepath - As final fallback for language

    Output schema:
    {
        accept: true/false,
        ai_loc: number (lines added if accepted),
        ai_char: 0,
        auto_approve_edit: true/false,
        completion_tokens: number,
        effective: true,
        filepath: string,
        function_category: "opencode",
        language: string,
        model: string,
        prompt_tokens: number,
        sid: string (session_id),
        time: ISO timestamp,
        user: string,
        user_char: 0,
        user_loc: 0,
        version: string,
        call_id: string,
        reply_type: string
    }
    """
    prompt_lookup = prompt_lookup or {}
    records = []

    # First pass: collect LOC data by call_id
    loc_data = {}  # call_id -> {added, deleted, language, filepath, ...}

    resource_metrics = metrics_data.get("resourceMetrics", [])

    for resource_metric in resource_metrics:
        scope_metrics = resource_metric.get("scopeMetrics", [])

        for scope_metric in scope_metrics:
            metrics = scope_metric.get("metrics", [])

            for metric in metrics:
                metric_name = metric.get("name", "")

                # Collect LOC added data
                if metric_name == "opencode.tool.loc.added":
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
                            loc_data[call_id]["time"] = nano_to_iso(dp.get("timeUnixNano", "0"))

                # Collect LOC deleted data
                elif metric_name == "opencode.tool.loc.deleted":
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
    for resource_metric in resource_metrics:
        scope_metrics = resource_metric.get("scopeMetrics", [])

        for scope_metric in scope_metrics:
            metrics = scope_metric.get("metrics", [])

            for metric in metrics:
                metric_name = metric.get("name", "")

                if metric_name == "opencode.permission.requests":
                    sum_data = metric.get("sum", {})
                    data_points = sum_data.get("dataPoints", [])

                    for dp in data_points:
                        attrs = dp.get("attributes", [])
                        call_id = get_attribute_value(attrs, "call.id")
                        reply = get_attribute_value(attrs, "permission.reply")
                        auto_approve = get_attribute_value(attrs, "auto_approve_edit")

                        # Determine accept status
                        # reply_type values: "once", "always", "auto", "reject"
                        is_accepted = reply in ["once", "always", "auto", "accept", "auto_accept"]

                        # Get LOC data for this call
                        loc = loc_data.get(call_id, {})
                        ai_loc = loc.get("added", 0) if is_accepted else 0

                        # Get enrichment from traces lookup
                        trace_info = traces_lookup.get(call_id, {}) if call_id else {}

                        # Get enrichment from prompt lookup (has model/language from prompt records)
                        prompt_info = prompt_lookup.get(call_id, {}) if call_id else {}

                        # Determine filepath with fallback chain
                        filepath = get_attribute_value(attrs, "file.path") or loc.get("filepath", "unknown")

                        # Determine language with fallback chain:
                        # 1. Direct from metrics attributes (if not "unknown")
                        # 2. From LOC data (if not "unknown")
                        # 3. From prompt lookup by call_id
                        # 4. Infer from filepath extension
                        language = get_attribute_value(attrs, "language")
                        if not language or language == "unknown":
                            language = loc.get("language")
                        if not language or language == "unknown":
                            language = prompt_info.get("language")
                        if not language or language == "unknown":
                            language = infer_language_from_filepath(filepath)
                        if not language:
                            language = "unknown"

                        # Determine model with fallback chain:
                        # 1. Direct from metrics attributes (if not "unknown")
                        # 2. From LOC data (if not "unknown")
                        # 3. From prompt lookup by call_id
                        # 4. From traces lookup (legacy)
                        model = get_attribute_value(attrs, "model")
                        if not model or model == "unknown":
                            model = loc.get("model")
                        if not model or model == "unknown":
                            model = prompt_info.get("model")
                        if not model or model == "unknown":
                            model = trace_info.get("model")
                        if not model:
                            model = "unknown"

                        # Build final record matching analyze_metrics.py schema
                        record = {
                            "accept": is_accepted,
                            "ai_loc": ai_loc,
                            "ai_char": 0,
                            "auto_approve_edit": auto_approve == True or str(auto_approve).lower() == "true",
                            "completion_tokens": trace_info.get("output_tokens", 0),
                            "effective": True,
                            "filepath": filepath,
                            "function_category": "opencode",
                            "language": language,
                            "model": model,
                            "prompt_tokens": trace_info.get("input_tokens", 0),
                            "sid": get_attribute_value(attrs, "session.id") or loc.get("session_id", "unknown"),
                            "time": nano_to_iso(dp.get("timeUnixNano", "")),
                            "user": get_attribute_value(attrs, "user") or loc.get("user", "unknown"),
                            "user_char": 0,
                            "user_loc": 0,
                            "version": get_attribute_value(attrs, "version") or loc.get("version", "1.0.0"),
                            "call_id": call_id,
                            "reply_type": reply,
                            "imported_at": datetime.now(timezone.utc).isoformat()
                        }

                        records.append(record)

    return records


# =============================================================================
# Incremental File Processing
# =============================================================================

def process_file_incrementally(
    file_path: str,
    db,
    state_collection_name: str,
    target_collection_name: str,
    record_extractor: Callable[[Dict, Optional[Dict]], List[Dict]],
    traces_lookup: Optional[Dict] = None,
    dry_run: bool = False
) -> Tuple[int, int, int, Dict]:
    """
    Process JSONL file incrementally.

    Args:
        file_path: Path to JSONL file
        db: MongoDB database
        state_collection_name: Name of state collection
        target_collection_name: Name of target collection for records
        record_extractor: Function to extract records from JSON data
        traces_lookup: Optional lookup table for enrichment
        dry_run: If True, parse but don't insert

    Returns:
        Tuple of (new_records, duplicates_skipped, lines_processed, updated_lookup)
    """
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return 0, 0, 0, traces_lookup or {}

    # Load state
    state = load_state(db, state_collection_name)

    # Get file stats
    stat = os.stat(file_path)
    current_inode = stat.st_ino
    current_size = stat.st_size
    current_mtime = stat.st_mtime

    logger.info(f"Processing {os.path.basename(file_path)}")
    logger.info("-" * 60)
    logger.info(f"  File: {file_path}")
    logger.info(f"  Size: {current_size:,} bytes")
    logger.info(f"  Inode: {current_inode}")

    if state.get("last_processed"):
        logger.info(f"  Last processed: {state.get('last_processed')} (offset: {state.get('offset', 0):,})")

    # Detect rotation
    if detect_rotation(state, current_inode, current_size):
        logger.info("  Status: File rotated - starting from beginning")
        start_offset = 0
        start_line = 0
    else:
        # Safe rewind
        saved_offset = state.get("offset", 0)
        start_offset = max(0, saved_offset - REWIND_BYTES)
        start_line = state.get("line_number", 0)

        if saved_offset > 0 and start_offset < saved_offset:
            logger.info(f"  Starting from offset: {start_offset:,} (rewound {REWIND_BYTES:,} bytes for safety)")
        elif saved_offset == 0:
            logger.info("  Status: First run - starting from beginning")
        else:
            logger.info(f"  Starting from offset: {start_offset:,}")

    # Check if there's new data to process
    if start_offset >= current_size:
        logger.info("  Status: No new data to process")
        return 0, 0, 0, traces_lookup or {}

    # Process file
    new_records = 0
    duplicates = 0
    lines_processed = 0
    records_since_save = 0
    cumulative_records = state.get("records_inserted", 0)

    target_collection = db[target_collection_name]
    updated_lookup = traces_lookup.copy() if traces_lookup else {}

    # Track time range
    first_timestamp = None
    last_timestamp = None

    with open(file_path, 'rb') as f:
        f.seek(start_offset)

        # Skip partial line if we rewound
        if start_offset > 0:
            partial = f.readline()
            logger.debug(f"  Skipped partial line: {len(partial)} bytes")

        line_number = start_line

        while True:
            pos_before = f.tell()
            line_bytes = f.readline()

            if not line_bytes:
                break  # EOF

            lines_processed += 1
            line_number += 1

            try:
                line_str = line_bytes.decode('utf-8').strip()
                if not line_str:
                    continue

                data = json.loads(line_str)

                # Generate unique ID for this line
                line_unique_id = generate_unique_id(current_inode, pos_before, line_bytes)

                # Extract records
                records = record_extractor(data, updated_lookup)

                for i, record in enumerate(records):
                    # Create unique ID for each record within the line
                    record_id = record.get("call_id") or record.get("span_id") or f"r{i}"
                    record["_id"] = f"{line_unique_id}:{record_id}"

                    # Track timestamps for summary
                    ts = record.get("timestamp") or record.get("start_time")
                    if ts:
                        if first_timestamp is None:
                            first_timestamp = ts
                        last_timestamp = ts

                    if not dry_run:
                        # Upsert with $setOnInsert to prevent duplicates
                        result = target_collection.update_one(
                            {"_id": record["_id"]},
                            {"$setOnInsert": record},
                            upsert=True
                        )

                        if result.upserted_id:
                            new_records += 1
                            logger.debug(f"  Line {line_number}: Inserted (new)")
                        else:
                            duplicates += 1
                            logger.debug(f"  Line {line_number}: Skipped (duplicate)")
                    else:
                        new_records += 1
                        logger.debug(f"  Line {line_number}: Would insert (dry run)")

                records_since_save += len(records)

                # Update lookup table if this is traces
                if "resourceSpans" in data:
                    line_lookup = extract_traces_lookup(data)
                    updated_lookup.update(line_lookup)

            except json.JSONDecodeError as e:
                logger.warning(f"  Invalid JSON at line {line_number}: {e}")
            except Exception as e:
                logger.error(f"  Error at line {line_number}: {e}")

            # Periodic state save
            if not dry_run and records_since_save >= STATE_SAVE_INTERVAL:
                save_state(
                    db, state_collection_name, file_path,
                    offset=f.tell(),
                    line_number=line_number,
                    inode=current_inode,
                    mtime=current_mtime,
                    records_inserted=cumulative_records + new_records
                )
                records_since_save = 0
                logger.debug(f"  State checkpoint at line {line_number}")

        # Final offset
        final_offset = f.tell()

    # Final state save
    if not dry_run:
        save_state(
            db, state_collection_name, file_path,
            offset=final_offset,
            line_number=line_number,
            inode=current_inode,
            mtime=current_mtime,
            records_inserted=cumulative_records + new_records,
            last_total_lines=line_number
        )

    # Log summary
    logger.info("")
    logger.info("  Summary:")
    logger.info(f"    Lines processed: {lines_processed} ({start_line} -> {line_number})")
    logger.info(f"    New records: {new_records}")
    logger.info(f"    Duplicates skipped: {duplicates}")
    if first_timestamp and last_timestamp:
        logger.info(f"    Time range: {first_timestamp} -> {last_timestamp}")
    if not dry_run:
        logger.info(f"    State saved: offset={final_offset:,}, line={line_number}")
    else:
        logger.info("    (Dry run - no data written)")
    logger.info("")

    return new_records, duplicates, lines_processed, updated_lookup


def process_traces_phase(db, traces_file: str, dry_run: bool = False) -> Tuple[Dict, Dict]:
    """
    Phase 1: Process traces file and build lookup tables.

    Returns:
        Tuple of (traces_lookup, prompt_lookup)
        - traces_lookup: for backwards compatibility (tokens from traces)
        - prompt_lookup: {call_id: {model, language, ...}} for metrics enrichment
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 1: Processing Traces")
    logger.info("=" * 60)

    # First, build lookup from ALL existing traces in the file
    # This ensures we can enrich metrics even with older traces
    logger.info("Building traces lookup table...")
    full_lookup = {}

    if os.path.exists(traces_file):
        with open(traces_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if "resourceSpans" in data:
                        line_lookup = extract_traces_lookup(data)
                        full_lookup.update(line_lookup)
                except (json.JSONDecodeError, Exception):
                    continue

    logger.info(f"  Loaded {len(full_lookup)} trace entries into lookup table")

    # Build prompt data lookup from ALL traces for cross-line correlation
    # This is critical for proper model/token extraction when OTEL batches
    # prompt spans and tool call spans in different JSONL lines
    logger.info("Building prompt data lookup table (for cross-line correlation)...")
    prompt_data_lookup = build_prompt_data_lookup(traces_file)
    logger.info(f"  Loaded {len(prompt_data_lookup)} prompt data entries into lookup table")

    # Now process incrementally for new prompt records
    # Pass the prompt_data_lookup for cross-line correlation
    def prompt_extractor(data: Dict, lookup: Optional[Dict]) -> List[Dict]:
        return extract_prompt_records(data, prompt_data_lookup)

    new_records, duplicates, lines, _ = process_file_incrementally(
        traces_file, db,
        TRACES_STATE_COLLECTION,
        PROMPT_COLLECTION,
        prompt_extractor,
        full_lookup,
        dry_run
    )

    # Build prompt lookup from extracted prompt records for metrics enrichment
    # This lookup maps call_id -> {model, language, ...} from prompt data
    logger.info("Building prompt lookup for metrics enrichment...")
    prompt_lookup = {}

    if os.path.exists(traces_file):
        with open(traces_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    records = extract_prompt_records(data, prompt_data_lookup)
                    for record in records:
                        call_id = record.get("call_id")
                        if call_id:
                            prompt_lookup[call_id] = {
                                "model": record.get("model", "unknown"),
                                "language": record.get("language"),
                                "file_path": record.get("file_path"),
                                "prompt_tokens": record.get("prompt_tokens", 0),
                                "completion_tokens": record.get("completion_tokens", 0),
                            }
                except (json.JSONDecodeError, Exception):
                    continue

    logger.info(f"  Loaded {len(prompt_lookup)} prompt entries for metrics enrichment")

    return full_lookup, prompt_lookup


def process_metrics_phase(db, metrics_file: str, traces_lookup: Dict, prompt_lookup: Dict, dry_run: bool = False) -> None:
    """
    Phase 2: Process metrics file using prompt lookup for enrichment.

    Args:
        db: MongoDB database
        metrics_file: Path to metrics JSONL file
        traces_lookup: Legacy traces lookup (for tokens)
        prompt_lookup: {call_id: {model, language, ...}} from prompt records
        dry_run: If True, parse but don't insert
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("Phase 2: Processing Metrics")
    logger.info("=" * 60)

    def metrics_extractor(data: Dict, lookup: Optional[Dict]) -> List[Dict]:
        return extract_enriched_metrics(data, lookup or {}, prompt_lookup)

    process_file_incrementally(
        metrics_file, db,
        METRICS_STATE_COLLECTION,
        METRICS_COLLECTION,
        metrics_extractor,
        traces_lookup,
        dry_run
    )


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logger(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # Reduce noise from pymongo
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="OpenCode Telemetry - Incremental JSONL to MongoDB Import",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Normal incremental run
  %(prog)s --status                  # Show current state
  %(prog)s --reset-state             # Reset and reprocess all
  %(prog)s --verbose                 # Verbose logging
  %(prog)s --dry-run                 # Parse but don't insert
        """
    )

    parser.add_argument(
        "--traces-file",
        default=DEFAULT_TRACES_FILE,
        help=f"Path to traces JSONL file (default: {DEFAULT_TRACES_FILE})"
    )
    parser.add_argument(
        "--metrics-file",
        default=DEFAULT_METRICS_FILE,
        help=f"Path to metrics JSONL file (default: {DEFAULT_METRICS_FILE})"
    )
    parser.add_argument(
        "--mongo-uri",
        default=DEFAULT_MONGO_URI,
        help=f"MongoDB connection URI (default: {DEFAULT_MONGO_URI})"
    )
    parser.add_argument(
        "--db-name",
        default=DEFAULT_DB_NAME,
        help=f"MongoDB database name (default: {DEFAULT_DB_NAME})"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current state and exit"
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Reset state and reprocess from beginning"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files but don't insert to MongoDB"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logger(args.verbose)

    # Connect to MongoDB
    try:
        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000)
        # Test connection
        client.admin.command('ping')
        db = client[args.db_name]
        logger.debug(f"Connected to MongoDB: {args.mongo_uri}")
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)

    # Handle status command
    if args.status:
        show_status(db, args.traces_file, args.metrics_file)
        return

    # Handle reset command
    if args.reset_state:
        reset_state(db)

    # Print header
    run_time = datetime.now(timezone.utc).isoformat()
    logger.info("=" * 80)
    logger.info("OpenCode Telemetry - Incremental MongoDB Import")
    logger.info(f"Run: {run_time}")
    if args.dry_run:
        logger.info("Mode: DRY RUN (no data will be written)")
    logger.info("=" * 80)

    import time
    start_time = time.time()

    # Phase 1: Process traces (and build lookups)
    traces_lookup, prompt_lookup = process_traces_phase(db, args.traces_file, args.dry_run)

    # Phase 2: Process metrics (using both lookups for enrichment)
    process_metrics_phase(db, args.metrics_file, traces_lookup, prompt_lookup, args.dry_run)

    # Final summary
    elapsed = time.time() - start_time

    logger.info("=" * 80)
    logger.info("Import Complete")
    logger.info("=" * 80)

    # Get final counts
    prompt_count = db[PROMPT_COLLECTION].count_documents({})
    metrics_count = db[METRICS_COLLECTION].count_documents({})

    logger.info(f"  Total documents in MongoDB:")
    logger.info(f"    {PROMPT_COLLECTION}: {prompt_count:,}")
    logger.info(f"    {METRICS_COLLECTION}: {metrics_count:,}")
    logger.info(f"  Total runtime: {elapsed:.2f} seconds")
    logger.info(f"  Next run: Safe to run again immediately (idempotent)")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
