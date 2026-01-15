#!/bin/bash

# OpenCode Telemetry Metrics Viewer
# Parses metrics.jsonl and displays in human-readable format

METRICS_FILE="${1:-/home/mtk26468/opencode/otel-data/metrics.jsonl}"

if [ ! -f "$METRICS_FILE" ]; then
    echo "Error: Metrics file not found: $METRICS_FILE"
    exit 1
fi

echo "=== OpenCode Telemetry Metrics Viewer ==="
echo "File: $METRICS_FILE"
echo "Last updated: $(stat -c %y "$METRICS_FILE" 2>/dev/null || stat -f %Sm "$METRICS_FILE" 2>/dev/null)"
echo ""

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "Installing jq for better JSON parsing..."
    echo "(jq not found, using basic grep/sed parsing)"
    echo ""
    USE_JQ=0
else
    USE_JQ=1
fi

# Function to parse with jq (better)
parse_with_jq() {
    echo "=== Lines of Code Metrics ==="
    jq -r 'select(.resourceMetrics[].scopeMetrics[].scope.version == "1.0.0") |
        .resourceMetrics[].scopeMetrics[] |
        select(.scope.version == "1.0.0") |
        .metrics[] |
        select(.name | contains("loc")) |
        {
            name: .name,
            value: .sum.dataPoints[0].asDouble,
            tool: .sum.dataPoints[0].attributes[] | select(.key == "tool.name") | .value.stringValue,
            session: .sum.dataPoints[0].attributes[] | select(.key == "session.id") | .value.stringValue,
            language: (.sum.dataPoints[0].attributes[] | select(.key == "language") | .value.stringValue // "N/A"),
            file: (.sum.dataPoints[0].attributes[] | select(.key == "file.path") | .value.stringValue // "N/A"),
            time: .sum.dataPoints[0].timeUnixNano
        } |
        "[\(.time | tonumber / 1000000000 | strftime("%Y-%m-%d %H:%M:%S"))] \(.name | split(".") | .[-1]): \(.value) lines (tool=\(.tool), language=\(.language))"' \
        "$METRICS_FILE" | tail -20

    echo ""
    echo "=== Tool Executions ==="
    jq -r 'select(.resourceMetrics[].scopeMetrics[].scope.version == "1.0.0") |
        .resourceMetrics[].scopeMetrics[] |
        select(.scope.version == "1.0.0") |
        .metrics[] |
        select(.name == "opencode.tool.executions") |
        {
            tool: .sum.dataPoints[0].attributes[] | select(.key == "tool.name") | .value.stringValue,
            count: .sum.dataPoints[0].asDouble,
            language: (.sum.dataPoints[0].attributes[] | select(.key == "language") | .value.stringValue // "N/A"),
            time: .sum.dataPoints[0].timeUnixNano
        } |
        "[\(.time | tonumber / 1000000000 | strftime("%Y-%m-%d %H:%M:%S"))] \(.tool): \(.count) execution(s) (language=\(.language))"' \
        "$METRICS_FILE" | tail -20

    echo ""
    echo "=== Summary (Last 24 Hours) ==="

    TOTAL_ADDED=$(jq -r 'select(.resourceMetrics[].scopeMetrics[].scope.version == "1.0.0") |
        .resourceMetrics[].scopeMetrics[] |
        select(.scope.version == "1.0.0") |
        .metrics[] |
        select(.name == "opencode.tool.loc.added") |
        .sum.dataPoints[0].asDouble' "$METRICS_FILE" | awk '{sum+=$1} END {print sum}')

    TOTAL_DELETED=$(jq -r 'select(.resourceMetrics[].scopeMetrics[].scope.version == "1.0.0") |
        .resourceMetrics[].scopeMetrics[] |
        select(.scope.version == "1.0.0") |
        .metrics[] |
        select(.name == "opencode.tool.loc.deleted") |
        .sum.dataPoints[0].asDouble' "$METRICS_FILE" | awk '{sum+=$1} END {print sum}')

    TOTAL_EXECUTIONS=$(jq -r 'select(.resourceMetrics[].scopeMetrics[].scope.version == "1.0.0") |
        .resourceMetrics[].scopeMetrics[] |
        select(.scope.version == "1.0.0") |
        .metrics[] |
        select(.name == "opencode.tool.executions") |
        .sum.dataPoints[0].asDouble' "$METRICS_FILE" | awk '{sum+=$1} END {print sum}')

    echo "Total lines added: ${TOTAL_ADDED:-0}"
    echo "Total lines deleted: ${TOTAL_DELETED:-0}"
    echo "Net lines: $((${TOTAL_ADDED:-0} - ${TOTAL_DELETED:-0}))"
    echo "Total tool executions: ${TOTAL_EXECUTIONS:-0}"
}

# Function to parse without jq (basic)
parse_without_jq() {
    echo "=== Recent Metrics (Last 20 entries) ==="
    echo ""

    # Extract plugin metrics (version 1.0.0)
    grep -o '"version":"1.0.0"[^}]*"name":"opencode\.[^"]*"[^}]*"asDouble":[0-9.]*' "$METRICS_FILE" | \
        sed 's/"version":"1.0.0".*"name":"//; s/".*"asDouble":/: /' | \
        tail -20

    echo ""
    echo "=== Summary ==="

    # Count total additions
    TOTAL_ADDED=$(grep -o '"name":"opencode.tool.loc.added"[^}]*"asDouble":[0-9.]*' "$METRICS_FILE" | \
        grep -o '"asDouble":[0-9.]*' | cut -d: -f2 | awk '{sum+=$1} END {print sum}')

    TOTAL_DELETED=$(grep -o '"name":"opencode.tool.loc.deleted"[^}]*"asDouble":[0-9.]*' "$METRICS_FILE" | \
        grep -o '"asDouble":[0-9.]*' | cut -d: -f2 | awk '{sum+=$1} END {print sum}')

    echo "Total lines added: ${TOTAL_ADDED:-0}"
    echo "Total lines deleted: ${TOTAL_DELETED:-0}"
    echo "Net lines: $((${TOTAL_ADDED:-0} - ${TOTAL_DELETED:-0}))"
}

# Check if we should look for recent metrics
RECENT_METRICS=$(grep '"version":"1.0.0"' "$METRICS_FILE" | wc -l)
if [ "$RECENT_METRICS" -eq 0 ]; then
    echo "⚠️  No plugin metrics found (version 1.0.0)"
    echo ""
    echo "Possible reasons:"
    echo "  1. Metrics haven't been exported yet (wait 10-12 seconds after operation)"
    echo "  2. No edit operations have been performed"
    echo "  3. Plugin not loading correctly"
    echo ""
    echo "Try performing an edit operation in OpenCode and wait 12 seconds."
    exit 0
fi

echo "Found $RECENT_METRICS plugin metric entries"
echo ""

# Parse based on jq availability
if [ "$USE_JQ" -eq 1 ]; then
    parse_with_jq
else
    parse_without_jq
fi

echo ""
echo "=== Live Tail Mode ==="
echo "To watch metrics in real-time:"
echo "  tail -f $METRICS_FILE | grep --line-buffered '\"version\":\"1.0.0\"'"
echo ""
echo "To see raw JSON for a specific metric:"
echo "  cat $METRICS_FILE | jq 'select(.resourceMetrics[].scopeMetrics[].scope.version == \"1.0.0\")'"
