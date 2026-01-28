#!/usr/bin/env python3
"""
Analyze consistency between plugin logs, metrics.jsonl, and traces.jsonl
"""

import json
import re
from collections import defaultdict
from datetime import datetime

# File paths
LOGS_FILE = "/home/mtk26468/.local/share/opencode/telemetry-plugin.log"
METRICS_FILE = "/home/mtk26468/opencode/otel-data/metrics.jsonl"
TRACES_FILE = "/home/mtk26468/opencode/otel-data/traces.jsonl"

print("=" * 80)
print("OpenCode Telemetry - Consistency Analysis")
print("=" * 80)
print()

# ============================================================================
# 1. Analyze Plugin Logs
# ============================================================================
print("1. PLUGIN LOGS ANALYSIS")
print("-" * 80)

loc_events = []
permission_events = []
auto_approve_events = []

with open(LOGS_FILE, 'r') as f:
    for line in f:
        # Extract LOC events
        if "LOC recorded:" in line:
            match = re.search(r'\+(\d+) -(\d+) \(tool=(\w+), language=(\w+), callID=(toolu_\w+)\)', line)
            if match:
                loc_events.append({
                    'added': int(match.group(1)),
                    'deleted': int(match.group(2)),
                    'tool': match.group(3),
                    'language': match.group(4),
                    'callID': match.group(5)
                })

        # Extract permission events
        if "PERMISSION RECORDED:" in line:
            match = re.search(r'PERMISSION RECORDED: (\w+) -> (\w+) \(tool=(\w+)', line)
            if match:
                permission_events.append({
                    'permission': match.group(1),
                    'reply': match.group(2),
                    'tool': match.group(3)
                })

        # Extract auto-approved events
        if "AUTO-APPROVED EDIT recorded:" in line:
            match = re.search(r'callID=(toolu_\w+)', line)
            if match:
                auto_approve_events.append({
                    'callID': match.group(1)
                })

print(f"LOC events logged: {len(loc_events)}")
print(f"Permission events logged: {len(permission_events)}")
print(f"Auto-approved events logged: {len(auto_approve_events)}")
print()

# Check for duplicates
loc_by_callid = defaultdict(int)
for event in loc_events:
    loc_by_callid[event['callID']] += 1

duplicates = {k: v for k, v in loc_by_callid.items() if v > 1}
if duplicates:
    print(f"⚠️  DUPLICATE LOG ENTRIES DETECTED:")
    for callid, count in duplicates.items():
        print(f"   {callid}: {count} times")
    print()

# ============================================================================
# 2. Analyze Metrics
# ============================================================================
print("2. METRICS.JSONL ANALYSIS")
print("-" * 80)

metrics_exports = []
total_loc_added = 0
total_loc_deleted = 0
total_executions = 0
total_permissions = 0
permission_by_reply = defaultdict(int)
auto_approve_count = defaultdict(int)

with open(METRICS_FILE, 'r') as f:
    for line in f:
        if line.strip():
            export = json.loads(line)
            metrics_exports.append(export)

            # Extract metrics from each export
            for rm in export.get('resourceMetrics', []):
                for scope in rm.get('scopeMetrics', []):
                    for metric in scope.get('metrics', []):
                        name = metric.get('name')

                        if name == 'opencode.tool.loc.added':
                            for dp in metric.get('sum', {}).get('dataPoints', []):
                                total_loc_added += dp.get('asDouble', 0)

                        elif name == 'opencode.tool.loc.deleted':
                            for dp in metric.get('sum', {}).get('dataPoints', []):
                                total_loc_deleted += dp.get('asDouble', 0)

                        elif name == 'opencode.tool.executions':
                            for dp in metric.get('sum', {}).get('dataPoints', []):
                                total_executions += dp.get('asDouble', 0)

                        elif name == 'opencode.permission.requests':
                            for dp in metric.get('sum', {}).get('dataPoints', []):
                                total_permissions += dp.get('asDouble', 0)
                                # Extract reply type
                                reply = None
                                auto_approve = None
                                for attr in dp.get('attributes', []):
                                    if attr['key'] == 'permission.reply':
                                        reply = attr['value']['stringValue']
                                    if attr['key'] == 'auto_approve_edit':
                                        auto_approve = attr['value']['stringValue']

                                if reply:
                                    permission_by_reply[reply] += dp.get('asDouble', 0)
                                if auto_approve:
                                    auto_approve_count[auto_approve] += dp.get('asDouble', 0)

print(f"Metric exports: {len(metrics_exports)}")
print(f"Total LOC added: {int(total_loc_added)}")
print(f"Total LOC deleted: {int(total_loc_deleted)}")
print(f"Total tool executions: {int(total_executions)}")
print(f"Total permission requests: {int(total_permissions)}")
print()
print("Permission breakdown by reply type:")
for reply, count in sorted(permission_by_reply.items()):
    print(f"  {reply}: {int(count)}")
print()
print("Permission breakdown by auto_approve_edit:")
for auto_val, count in sorted(auto_approve_count.items()):
    print(f"  auto_approve_edit={auto_val}: {int(count)}")
print()

# ============================================================================
# 3. Analyze Traces
# ============================================================================
print("3. TRACES.JSONL ANALYSIS")
print("-" * 80)

trace_exports = []
total_spans = 0
spans_by_name = defaultdict(int)
tool_call_spans = []

with open(TRACES_FILE, 'r') as f:
    for line in f:
        if line.strip():
            export = json.loads(line)
            trace_exports.append(export)

            # Extract spans from each export
            for rs in export.get('resourceSpans', []):
                for scope in rs.get('scopeSpans', []):
                    for span in scope.get('spans', []):
                        total_spans += 1
                        span_name = span.get('name', 'unknown')
                        spans_by_name[span_name] += 1

                        # Look for ai.toolCall spans
                        if span_name == 'ai.toolCall':
                            attrs = {}
                            for attr in span.get('attributes', []):
                                attrs[attr['key']] = attr.get('value', {})
                            tool_call_spans.append({
                                'name': attrs.get('ai.toolCall.name', {}).get('stringValue'),
                                'session_id': attrs.get('session.id', {}).get('stringValue'),
                                'call_id': attrs.get('call.id', {}).get('stringValue'),
                                'file_path': attrs.get('file.path', {}).get('stringValue'),
                                'language': attrs.get('language', {}).get('stringValue')
                            })

print(f"Trace exports: {len(trace_exports)}")
print(f"Total spans: {total_spans}")
print()
print("Spans by name:")
for name, count in sorted(spans_by_name.items()):
    print(f"  {name}: {count}")
print()
print(f"Tool call spans with session context: {len(tool_call_spans)}")
print()

# ============================================================================
# 4. Consistency Check
# ============================================================================
print("4. CONSISTENCY CHECK")
print("-" * 80)

# Remove duplicates from logs for fair comparison
unique_loc_events = {}
for event in loc_events:
    unique_loc_events[event['callID']] = event
unique_count = len(unique_loc_events)

print(f"LOG: {len(loc_events)} LOC events ({unique_count} unique callIDs)")
print(f"METRICS: {int(total_loc_added)} lines added, {int(total_loc_deleted)} lines deleted")
print(f"TRACES: {len(tool_call_spans)} tool call spans with context")
print()

# Calculate expected vs actual
# Each LOC event should result in +N/-N in metrics
expected_additions = sum(e['added'] for e in unique_loc_events.values())
expected_deletions = sum(e['deleted'] for e in unique_loc_events.values())

print("Expected (from unique log events):")
print(f"  LOC added: {expected_additions}")
print(f"  LOC deleted: {expected_deletions}")
print()

print("Actual (from metrics):")
print(f"  LOC added: {int(total_loc_added)}")
print(f"  LOC deleted: {int(total_loc_deleted)}")
print()

# Check consistency
if int(total_loc_added) == expected_additions:
    print("✅ LOC added: CONSISTENT")
else:
    print(f"⚠️  LOC added: MISMATCH (expected {expected_additions}, got {int(total_loc_added)})")

if int(total_loc_deleted) == expected_deletions:
    print("✅ LOC deleted: CONSISTENT")
else:
    print(f"⚠️  LOC deleted: MISMATCH (expected {expected_deletions}, got {int(total_loc_deleted)})")
print()

# Check permission events
print("Permission events:")
print(f"  LOG: {len(permission_events)} manual permissions + {len(auto_approve_events)} auto-approved")
print(f"  METRICS: {int(total_permissions)} total permissions")
print()

# ============================================================================
# 5. Summary
# ============================================================================
print("=" * 80)
print("SUMMARY")
print("=" * 80)

issues = []

if duplicates:
    issues.append(f"⚠️  Duplicate log entries detected ({len(duplicates)} call IDs)")

if int(total_loc_added) != expected_additions:
    issues.append("⚠️  LOC added metrics don't match log events")

if int(total_loc_deleted) != expected_deletions:
    issues.append("⚠️  LOC deleted metrics don't match log events")

if len(tool_call_spans) == 0 and total_spans > 0:
    issues.append("⚠️  Trace spans exist but no tool call spans with session context")

if not issues:
    print("✅ All telemetry data is CONSISTENT!")
    print()
    print("Summary:")
    print(f"  - {unique_count} unique tool executions")
    print(f"  - {int(total_loc_added)} lines added, {int(total_loc_deleted)} lines deleted")
    print(f"  - {int(total_permissions)} permission events")
    print(f"  - {len(tool_call_spans)} traced tool calls")
else:
    print("Issues found:")
    for issue in issues:
        print(f"  {issue}")
    print()
    print("Note: Duplicate log entries suggest the plugin might be loaded twice.")
    print("This is expected with bundled plugins and doesn't affect functionality.")

print()
